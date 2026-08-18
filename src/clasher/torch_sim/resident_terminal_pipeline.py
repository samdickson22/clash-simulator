"""Transactional retained object/cleanup pipeline for terminal payloads.

The scalar tick advances existing objects before cleanup. Timed explosions
therefore resolve first, their terminal children replace the expired object,
and only then are the tick's dead characters visited in stable entity-ID order
to materialize direct children or new timed objects. The complete composition
runs on speculative tensor state and publishes whole rows only after every
stage succeeds.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, fields
from enum import IntEnum

import torch

from clasher.battle import BattleState

from .objects import ObjectPhaseResult, TensorObjectState, step_object_phase
from .resident_terminal_payloads import (
    TensorTerminalPayloadResult,
    materialize_terminal_payloads_,
)
from .resident_timed_explosions import (
    TensorTimedExplosionTargets,
    TimedExplosionResult,
    resolve_timed_terminal_explosions_,
)
from .resident_timed_terminal_payloads import (
    TensorTimedTerminalCatalog,
    TensorTimedTerminalEvents,
    TensorTimedTerminalState,
    TimedChildMaterialization,
    TimedParentMaterialization,
    materialize_timed_children_,
    materialize_timed_parents_,
    plan_timed_terminal_events,
)
from .runtime_state import TensorBattleRuntime


class TerminalPipelineReason(IntEnum):
    NONE = 0
    OBJECT_PHASE = 1
    TARGET_TRAITS = 2
    EXPLOSION = 3
    TIMED_CHILD = 4
    DIRECT_CLEANUP = 5
    TIMED_PARENT = 6


@dataclass
class TensorTerminalPipelineTargets:
    """Retained target traits indexed by timed terminal operation."""

    represented_entity_id: torch.Tensor
    collision_radius_units: torch.Tensor
    airborne: torch.Tensor
    building: torch.Tensor
    knockback_immune: torch.Tensor
    has_shield: torch.Tensor
    shield_current: torch.Tensor
    shield_break_count: torch.Tensor
    death_payload_supported: torch.Tensor
    area_receivable_by_operation: torch.Tensor
    knockback_receivable_by_operation: torch.Tensor

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
        catalog: TensorTimedTerminalCatalog,
    ) -> TensorTerminalPipelineTargets:
        """Compile event-specific predicates once at the Python boundary."""

        operations = (
            torch.nonzero(catalog.timed_supported, as_tuple=False)
            .flatten()
            .detach()
            .cpu()
            .tolist()
        )
        operation_count = int(catalog.timed_supported.shape[0])
        entity_shape = runtime.battle.entity_id.shape
        area = torch.zeros(
            (operation_count, *entity_shape),
            dtype=torch.bool,
            device=runtime.device,
        )
        knockback = torch.zeros_like(area)
        if not operations:
            zeros = torch.zeros(entity_shape, dtype=torch.int64, device=runtime.device)
            return cls(
                runtime.battle.entity_id.clone(),
                zeros,
                torch.zeros_like(zeros, dtype=torch.bool),
                runtime.battle.entity_kind == 1,
                torch.zeros_like(zeros, dtype=torch.bool),
                torch.zeros_like(zeros, dtype=torch.bool),
                torch.zeros_like(zeros, dtype=torch.float64),
                torch.zeros_like(zeros, dtype=torch.int32),
                torch.ones_like(zeros, dtype=torch.bool),
                area,
                knockback,
            )

        op = torch.tensor(operations, dtype=torch.int64, device=runtime.device)
        event_operation = op[:, None].expand(-1, runtime.batch_size).reshape(-1)
        batch = torch.arange(runtime.batch_size, device=runtime.device).repeat(
            len(operations)
        )
        width = int(batch.numel())
        zeros_i64 = torch.zeros(width, dtype=torch.int64, device=runtime.device)
        zeros_i32 = torch.zeros(width, dtype=torch.int32, device=runtime.device)
        terminal = TensorTimedTerminalEvents(
            batch_index=batch,
            object_slot=zeros_i64,
            object_id=zeros_i64,
            operation_row=event_operation,
            player=torch.zeros(width, dtype=torch.int8, device=runtime.device),
            x_units=zeros_i32,
            y_units=zeros_i32,
            damage=torch.zeros(width, dtype=torch.float64, device=runtime.device),
            radius_units=zeros_i32,
            knockback_units=zeros_i32,
            child_row=torch.full_like(zeros_i64, -1),
            child_count=torch.zeros(width, dtype=torch.int16, device=runtime.device),
            facing_x_units=zeros_i32,
            facing_y_units=zeros_i32,
            freeze_expiry_time=torch.zeros(
                width, dtype=torch.float64, device=runtime.device
            ),
        )
        source_kinds = [
            catalog.terminal.spawn.root_names[int(value)]
            for value in event_operation.detach().cpu().tolist()
        ]
        traits = TensorTimedExplosionTargets.from_battles(
            runtime,
            battles,
            terminal,
            source_kinds=source_kinds,
        )
        event = 0
        for operation in operations:
            area[operation] = traits.area_receivable[event : event + runtime.batch_size]
            knockback[operation] = traits.knockback_receivable[
                event : event + runtime.batch_size
            ]
            event += runtime.batch_size
        return cls(
            represented_entity_id=runtime.battle.entity_id.clone(),
            collision_radius_units=traits.collision_radius_units,
            airborne=traits.airborne,
            building=traits.building,
            knockback_immune=traits.knockback_immune,
            has_shield=traits.has_shield,
            shield_current=traits.shield_current,
            shield_break_count=traits.shield_break_count,
            death_payload_supported=traits.death_payload_supported,
            area_receivable_by_operation=area,
            knockback_receivable_by_operation=knockback,
        )

    def clone(self) -> TensorTerminalPipelineTargets:
        return type(self)(
            **{
                descriptor.name: getattr(self, descriptor.name).clone()
                for descriptor in fields(self)
            }
        )

    def for_events(
        self,
        runtime: TensorBattleRuntime,
        terminal: TensorTimedTerminalEvents,
    ) -> tuple[TensorTimedExplosionTargets, torch.Tensor]:
        active_character = runtime.entity_pool.active & (
            (runtime.battle.entity_kind == 0) | (runtime.battle.entity_kind == 1)
        )
        represented = (~active_character) | (
            self.represented_entity_id == runtime.battle.entity_id
        )
        event_rows = torch.zeros(
            runtime.batch_size, dtype=torch.bool, device=runtime.device
        )
        event_rows[terminal.batch_index] = True
        row_supported = ~event_rows | represented.all(dim=1)
        operation = terminal.operation_row.clamp_min(0)
        rows = terminal.batch_index
        return (
            TensorTimedExplosionTargets(
                collision_radius_units=self.collision_radius_units,
                airborne=self.airborne,
                building=self.building,
                area_receivable=self.area_receivable_by_operation[operation, rows],
                knockback_receivable=(
                    self.knockback_receivable_by_operation[operation, rows]
                ),
                knockback_immune=self.knockback_immune,
                has_shield=self.has_shield,
                shield_current=self.shield_current.clone(),
                shield_break_count=self.shield_break_count.clone(),
                death_payload_supported=self.death_payload_supported,
            ),
            row_supported,
        )


@dataclass(frozen=True)
class ResidentTerminalPipelineResult:
    committed: torch.Tensor
    reason: torch.Tensor
    object_result: ObjectPhaseResult
    terminal_events: TensorTimedTerminalEvents
    explosion: TimedExplosionResult
    timed_children: TimedChildMaterialization
    direct_cleanup: tuple[TensorTerminalPayloadResult, ...]
    timed_parents: tuple[TimedParentMaterialization, ...]


def _clone_object_state(state: TensorObjectState) -> TensorObjectState:
    values: dict[str, object] = {"catalog": state.catalog}
    for descriptor in fields(state):
        if descriptor.name != "catalog":
            values[descriptor.name] = getattr(state, descriptor.name).clone()
    return TensorObjectState(**values)  # type: ignore[arg-type]


def _clone_timed_state(state: TensorTimedTerminalState) -> TensorTimedTerminalState:
    return TensorTimedTerminalState(
        objects=_clone_object_state(state.objects),
        operation_row=state.operation_row.clone(),
        facing_x_units=state.facing_x_units.clone(),
        facing_y_units=state.facing_y_units.clone(),
        freeze_expiry_time=state.freeze_expiry_time.clone(),
    )


def _copy_rows_(destination: object, source: object, rows: torch.Tensor) -> None:
    batch = int(rows.shape[0])
    for descriptor in fields(destination):  # type: ignore[arg-type]
        left = getattr(destination, descriptor.name)
        right = getattr(source, descriptor.name)
        if (
            isinstance(left, torch.Tensor)
            and isinstance(right, torch.Tensor)
            and left.ndim > 0
            and left.shape[0] == batch
            and left.shape == right.shape
        ):
            left[rows] = right[rows]


def _commit_runtime_rows_(
    destination: TensorBattleRuntime,
    source: TensorBattleRuntime,
    rows: torch.Tensor,
) -> None:
    _copy_rows_(destination.battle, source.battle, rows)
    _copy_rows_(destination.battle.rng, source.battle.rng, rows)
    destination.entity_pool.active[rows] = source.entity_pool.active[rows]
    destination.entity_pool.next_entity_id[rows] = source.entity_pool.next_entity_id[
        rows
    ]
    _copy_rows_(destination.status, source.status, rows)
    _copy_rows_(destination.phases, source.phases, rows)
    _copy_rows_(destination.events, source.events, rows)
    destination.supported[rows] = source.supported[rows]
    destination.dirty[rows] = source.dirty[rows]


class TensorResidentTerminalPipeline:
    """Compose existing terminal kernels under one whole-row transaction."""

    def __init__(
        self,
        catalog: TensorTimedTerminalCatalog,
        state: TensorTimedTerminalState,
        targets: TensorTerminalPipelineTargets,
    ) -> None:
        self.catalog = catalog
        self.state = state
        self.targets = targets

    def step(
        self,
        runtime: TensorBattleRuntime,
        dead: torch.Tensor,
        *,
        facing_x_units: torch.Tensor,
        facing_y_units: torch.Tensor,
    ) -> ResidentTerminalPipelineResult:
        if dead.shape != runtime.entity_pool.active.shape:
            raise ValueError("dead must have shape [batch, entity]")
        if facing_x_units.shape != dead.shape or facing_y_units.shape != dead.shape:
            raise ValueError("facing planes must have shape [batch, entity]")
        if self.state.objects.batch_size != runtime.batch_size:
            raise ValueError("timed object state batch differs from runtime")

        # Both direct and nested child namespaces are stable catalog metadata;
        # install them before taking the speculative transaction snapshot.
        self.catalog.terminal.prepare_runtime(runtime)
        self.catalog.prepare_runtime(runtime)
        working = runtime.clone()
        working.battle.rng = runtime.battle.rng.clone()
        timed_state = _clone_timed_state(self.state)
        targets = self.targets.clone()
        committed = runtime.supported.clone()
        reason = torch.zeros(
            runtime.batch_size, dtype=torch.int16, device=runtime.device
        )

        def reject(mask: torch.Tensor, code: TerminalPipelineReason) -> None:
            nonlocal committed
            selected = committed & mask
            reason.copy_(torch.where(selected, int(code), reason))
            committed &= ~selected
            working.supported.copy_(committed)

        # Object phase precedes cleanup. Newly materialized timed parents below
        # consequently do not consume activation time until the next call.
        object_result = step_object_phase(timed_state.objects)
        reject(object_result.unsupported_batch, TerminalPipelineReason.OBJECT_PHASE)
        terminal = plan_timed_terminal_events(self.catalog, timed_state, object_result)
        event_targets, target_supported = targets.for_events(working, terminal)
        reject(~target_supported, TerminalPipelineReason.TARGET_TRAITS)
        explosion = resolve_timed_terminal_explosions_(
            working,
            terminal,
            event_targets,
        )
        reject(~explosion.committed, TerminalPipelineReason.EXPLOSION)
        targets.shield_current.copy_(event_targets.shield_current)
        targets.shield_break_count.copy_(event_targets.shield_break_count)
        working.supported.copy_(committed)
        children = materialize_timed_children_(
            working,
            self.catalog,
            timed_state,
            terminal,
        )
        reject(~children.committed, TerminalPipelineReason.TIMED_CHILD)

        # Publish surviving object coordinates before the cleanup snapshot.
        matches = (
            timed_state.objects.allocated[:, :, None]
            & working.entity_pool.active[:, None, :]
            & (
                timed_state.objects.object_id[:, :, None]
                == working.battle.entity_id[:, None, :]
            )
        )
        object_found = matches.any(dim=2) & committed[:, None]
        object_slot = matches.to(torch.int64).argmax(dim=2)
        rows, slots = torch.where(object_found)
        entity_slot = object_slot[rows, slots]
        working.battle.entity_x_units[rows, entity_slot] = timed_state.objects.x_units[
            rows, slots
        ]
        working.battle.entity_y_units[rows, entity_slot] = timed_state.objects.y_units[
            rows, slots
        ]

        cleanup_dead = dead.to(torch.bool) | (
            working.entity_pool.active
            & ~working.battle.entity_active
            & ((working.battle.entity_kind == 0) | (working.battle.entity_kind == 1))
        )
        ordered = working.entity_pool.id_order(cleanup_dead)
        direct_results: list[TensorTerminalPayloadResult] = []
        timed_results: list[TimedParentMaterialization] = []
        for ordinal in range(runtime.max_entities):
            parent_id = ordered.entity_ids[:, ordinal]
            valid = ordered.valid[:, ordinal] & committed
            slots = working.entity_pool.slots_for_ids(parent_id[:, None])[:, 0]
            exists = slots >= 0
            safe_slots = slots.clamp_min(0)
            core = working.card_catalog_index[
                working.battle.entity_card.gather(1, safe_slots[:, None])[:, 0]
            ]
            operation = self.catalog.source_row_by_card[core.clamp_min(0)]
            safe_operation = operation.clamp_min(0)
            timed = (
                valid
                & exists
                & (operation >= 0)
                & self.catalog.terminal.spawn.timed_explosive[safe_operation]
            )
            direct = valid & exists & ~timed
            timed_dead = torch.zeros_like(cleanup_dead)
            direct_dead = torch.zeros_like(cleanup_dead)
            row_index = torch.arange(runtime.batch_size, device=runtime.device)
            timed_dead[row_index[timed], safe_slots[timed]] = True
            direct_dead[row_index[direct], safe_slots[direct]] = True

            working.supported.copy_(committed)
            direct_result = materialize_terminal_payloads_(
                working,
                self.catalog.terminal,
                direct_dead,
                facing_x_units=facing_x_units,
                facing_y_units=facing_y_units,
            )
            direct_results.append(direct_result)
            reject(
                direct & ~direct_result.committed, TerminalPipelineReason.DIRECT_CLEANUP
            )

            working.supported.copy_(committed)
            timed_result = materialize_timed_parents_(
                working,
                self.catalog,
                timed_state,
                timed_dead,
                facing_x_units=facing_x_units,
                facing_y_units=facing_y_units,
            )
            timed_results.append(timed_result)
            reject(timed & ~timed_result.committed, TerminalPipelineReason.TIMED_PARENT)

        working.supported.copy_(committed)
        _commit_runtime_rows_(runtime, working, committed)
        _copy_rows_(self.state.objects, timed_state.objects, committed)
        for name in (
            "operation_row",
            "facing_x_units",
            "facing_y_units",
            "freeze_expiry_time",
        ):
            getattr(self.state, name)[committed] = getattr(timed_state, name)[committed]
        for descriptor in fields(self.targets):
            destination = getattr(self.targets, descriptor.name)
            source = getattr(targets, descriptor.name)
            if destination.ndim >= 1 and destination.shape[0] == runtime.batch_size:
                destination[committed] = source[committed]
            elif destination.ndim >= 2 and destination.shape[1] == runtime.batch_size:
                destination[:, committed] = source[:, committed]

        return ResidentTerminalPipelineResult(
            committed,
            reason,
            object_result,
            terminal,
            explosion,
            children,
            tuple(direct_results),
            tuple(timed_results),
        )


__all__ = [
    "ResidentTerminalPipelineResult",
    "TensorResidentTerminalPipeline",
    "TensorTerminalPipelineTargets",
    "TerminalPipelineReason",
]
