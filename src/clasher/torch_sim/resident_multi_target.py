"""Retained serialized simultaneous attack composition.

This owner snapshots ``MultipleTargetAttack`` recipients at attack start and
keeps projectile recipients by identity until impact.  Damage and
``SerializedOnHitBuff`` effects are delegated to ``TensorRuntimeMechanics`` so
shield, HP, scalar-kind, status, death, and public-event behavior stay shared
with the ordinary combat path.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, fields, replace
from typing import TYPE_CHECKING

import torch

from .combat_mechanics import (
    CombatMechanicOpcode,
    TensorCombatMechanicCatalog,
    TensorMechanicWorld,
    select_multiple_targets,
)
from .runtime_mechanics import MechanicHitResult, TensorRuntimeMechanics
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase

if TYPE_CHECKING:
    from clasher.battle import BattleState

    from .mechanic_dispatcher import TensorMechanicDispatcher


@dataclass
class TensorMultiTargetAttackState:
    source_entity_id: torch.Tensor
    primary_target_id: torch.Tensor
    secondary_target_id: torch.Tensor
    secondary_valid: torch.Tensor
    pending_active: torch.Tensor
    pending_target_id: torch.Tensor
    pending_damage: torch.Tensor
    pending_damage_integer_kind: torch.Tensor
    pending_status_eligible: torch.Tensor
    target_entity_id: torch.Tensor
    cooldown_seconds: torch.Tensor

    @classmethod
    def zeros(
        cls,
        runtime: TensorBattleRuntime,
        maximum_secondary: int,
    ) -> TensorMultiTargetAttackState:
        if maximum_secondary < 0:
            raise ValueError("maximum_secondary must be non-negative")
        shape = runtime.battle.entity_id.shape
        grouped = (*shape, maximum_secondary + 1)
        secondary = (*shape, maximum_secondary)
        return cls(
            source_entity_id=torch.zeros_like(runtime.battle.entity_id),
            primary_target_id=torch.zeros_like(runtime.battle.entity_id),
            secondary_target_id=torch.zeros(
                secondary, dtype=torch.int64, device=runtime.device
            ),
            secondary_valid=torch.zeros(
                secondary, dtype=torch.bool, device=runtime.device
            ),
            pending_active=torch.zeros(
                grouped, dtype=torch.bool, device=runtime.device
            ),
            pending_target_id=torch.zeros(
                grouped, dtype=torch.int64, device=runtime.device
            ),
            pending_damage=torch.zeros(
                grouped, dtype=torch.float64, device=runtime.device
            ),
            pending_damage_integer_kind=torch.zeros(
                grouped, dtype=torch.bool, device=runtime.device
            ),
            pending_status_eligible=torch.zeros(
                grouped, dtype=torch.bool, device=runtime.device
            ),
            target_entity_id=torch.zeros_like(runtime.battle.entity_id),
            cooldown_seconds=torch.zeros(
                shape, dtype=torch.float64, device=runtime.device
            ),
        )

    @property
    def batch_size(self) -> int:
        return int(self.source_entity_id.shape[0])

    @property
    def max_entities(self) -> int:
        return int(self.source_entity_id.shape[1])

    @property
    def maximum_secondary(self) -> int:
        return int(self.secondary_target_id.shape[2])

    def clone(self) -> TensorMultiTargetAttackState:
        return type(self)(
            **{
                descriptor.name: getattr(self, descriptor.name).clone()
                for descriptor in fields(self)
            }
        )

    def fork(self, rows: Sequence[int] | torch.Tensor) -> TensorMultiTargetAttackState:
        index = torch.as_tensor(
            rows, dtype=torch.int64, device=self.source_entity_id.device
        )
        return type(self)(
            **{
                descriptor.name: getattr(self, descriptor.name)
                .index_select(0, index)
                .clone()
                for descriptor in fields(self)
            }
        )

    def reset_(self, source_mask: torch.Tensor) -> None:
        selected = torch.as_tensor(
            source_mask, dtype=torch.bool, device=self.source_entity_id.device
        )
        if selected.shape != self.source_entity_id.shape:
            raise ValueError("source_mask must have shape [batch, entity]")
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            expanded = selected.reshape(
                *selected.shape, *((1,) * (value.ndim - selected.ndim))
            ).expand_as(value)
            value.masked_fill_(expanded, False if value.dtype == torch.bool else 0)


@dataclass(frozen=True)
class MultiTargetCommitResult:
    committed: torch.Tensor
    accepted: torch.Tensor
    target_id: torch.Tensor
    target_valid: torch.Tensor
    direct_resolved: torch.Tensor
    projectile_queued: torch.Tensor
    damage_integer_kind: torch.Tensor
    hit: MechanicHitResult


@dataclass(frozen=True)
class MultiTargetProjectileResult:
    committed: torch.Tensor
    arrived: torch.Tensor
    resolved: torch.Tensor
    target_missing: torch.Tensor
    damage_integer_kind: torch.Tensor
    hit: MechanicHitResult


def _empty_hit(shape: tuple[int, int], device: torch.device) -> MechanicHitResult:
    zeros = torch.zeros(shape, dtype=torch.bool, device=device)
    return MechanicHitResult(
        hitpoint_damage=torch.zeros(shape, dtype=torch.float64, device=device),
        shield_absorbed=zeros.clone(),
        shield_broken=zeros.clone(),
        status_dispatched=zeros.clone(),
        target_died=zeros.clone(),
    )


def _compile_attached_catalog(
    dispatcher: TensorMechanicDispatcher,
    battles: Sequence[BattleState],
) -> TensorCombatMechanicCatalog:
    """Resolve on-attach multi-target fields from serialized character data."""

    if len(battles) != dispatcher.batch_size:
        raise ValueError("battle count does not match dispatcher batch")
    catalog = replace(
        dispatcher.combat_catalog,
        multiple_target_count=(dispatcher.combat_catalog.multiple_target_count.clone()),
        multiple_all_hit=dispatcher.combat_catalog.multiple_all_hit.clone(),
        multiple_damage_scale=(dispatcher.combat_catalog.multiple_damage_scale.clone()),
    )
    loader = battles[0].card_loader
    for card_id, name in enumerate(catalog.names[1:], start=1):
        stats = loader.get_card(name)
        if stats is None:
            continue
        slot, present = catalog.mechanic_slot(
            torch.tensor(card_id, dtype=torch.int64, device=catalog.device),
            CombatMechanicOpcode.MULTIPLE_TARGET,
        )
        if not bool(present.item()):
            continue
        raw = getattr(stats, "_raw_entry", {}) or {}
        character = raw.get("summonCharacterData", {}) or {}
        selected = int(slot.item())
        catalog.multiple_target_count[card_id, selected] = max(
            1,
            int(
                character.get(
                    "multipleTargets",
                    catalog.multiple_target_count[card_id, selected].item(),
                )
            ),
        )
        catalog.multiple_all_hit[card_id, selected] = bool(
            character.get(
                "allTargetsHit",
                catalog.multiple_all_hit[card_id, selected].item(),
            )
        )
    return catalog


def _copy_runtime_rows_(
    destination: TensorBattleRuntime,
    source: TensorBattleRuntime,
    rows: torch.Tensor,
) -> None:
    batch = destination.batch_size
    for left_owner, right_owner in (
        (destination.battle, source.battle),
        (destination.battle.rng, source.battle.rng),
        (destination.status, source.status),
        (destination.phases, source.phases),
        (destination.events, source.events),
    ):
        for descriptor in fields(left_owner):  # type: ignore[arg-type]
            left = getattr(left_owner, descriptor.name)
            right = getattr(right_owner, descriptor.name)
            if (
                isinstance(left, torch.Tensor)
                and isinstance(right, torch.Tensor)
                and left.ndim > 0
                and left.shape == right.shape
                and left.shape[0] == batch
            ):
                left[rows] = right[rows]
    destination.entity_pool.active[rows] = source.entity_pool.active[rows]
    destination.entity_pool.next_entity_id[rows] = source.entity_pool.next_entity_id[
        rows
    ]
    destination.supported[rows] = source.supported[rows]
    destination.dirty[rows] = source.dirty[rows]


def _copy_mechanic_rows_(
    destination: TensorRuntimeMechanics,
    source: TensorRuntimeMechanics,
    rows: torch.Tensor,
) -> None:
    for descriptor in fields(destination):
        if descriptor.name == "core_card_to_mechanic_card":
            continue
        left = getattr(destination, descriptor.name)
        right = getattr(source, descriptor.name)
        if (
            isinstance(left, torch.Tensor)
            and isinstance(right, torch.Tensor)
            and left.ndim > 0
            and left.shape == right.shape
            and left.shape[0] == destination.batch_size
        ):
            left[rows] = right[rows]


def _copy_state_rows_(
    destination: TensorMultiTargetAttackState,
    source: TensorMultiTargetAttackState,
    rows: torch.Tensor,
) -> None:
    for descriptor in fields(destination):
        getattr(destination, descriptor.name)[rows] = getattr(source, descriptor.name)[
            rows
        ]


def _expanded_world(
    world: TensorMechanicWorld,
    source_count: int,
    candidate_mask: torch.Tensor,
) -> TensorMechanicWorld:
    values: dict[str, torch.Tensor] = {}
    for descriptor in fields(world):
        value = getattr(world, descriptor.name)
        values[descriptor.name] = (
            value[:, None, :]
            .expand(world.batch_size, source_count, world.max_entities)
            .reshape(world.batch_size * source_count, world.max_entities)
            .clone()
        )
    values["targetable"] &= candidate_mask.reshape(
        world.batch_size * source_count, world.max_entities
    )
    return TensorMechanicWorld(**values)


def _resolve_ordered_hits_(
    runtime: TensorBattleRuntime,
    mechanics: TensorRuntimeMechanics,
    *,
    source_slot: torch.Tensor,
    target_slot: torch.Tensor,
    damage: torch.Tensor,
    valid: torch.Tensor,
    status_eligible: torch.Tensor,
) -> MechanicHitResult:
    """Resolve scalar order: primary damage, secondaries, primary hook."""

    batch, sources, lanes = valid.shape
    primary_shape = (batch, sources)
    primary_damage = mechanics.resolve_attack_hits_(
        runtime,
        source_slot=source_slot[:, :, 0],
        target_slot=target_slot[:, :, 0],
        incoming_damage=damage[:, :, 0],
        valid=valid[:, :, 0],
        status_eligible=torch.zeros(
            primary_shape, dtype=torch.bool, device=valid.device
        ),
    )
    if lanes > 1:
        secondary_shape = (batch, sources * (lanes - 1))
        secondary = mechanics.resolve_attack_hits_(
            runtime,
            source_slot=source_slot[:, :, 1:].reshape(secondary_shape),
            target_slot=target_slot[:, :, 1:].reshape(secondary_shape),
            incoming_damage=damage[:, :, 1:].reshape(secondary_shape),
            valid=valid[:, :, 1:].reshape(secondary_shape),
            status_eligible=status_eligible[:, :, 1:].reshape(secondary_shape),
        )
    else:
        secondary = _empty_hit((batch, 0), valid.device)
    primary_status = mechanics.resolve_attack_hits_(
        runtime,
        source_slot=source_slot[:, :, 0],
        target_slot=target_slot[:, :, 0],
        incoming_damage=torch.zeros(
            primary_shape, dtype=torch.float64, device=valid.device
        ),
        valid=valid[:, :, 0],
        status_eligible=status_eligible[:, :, 0],
    )

    def grouped(name: str) -> torch.Tensor:
        first = getattr(primary_damage, name)[:, :, None]
        rest = getattr(secondary, name).reshape(batch, sources, lanes - 1)
        value = torch.cat((first, rest), dim=2)
        if name == "status_dispatched":
            value[:, :, 0] = primary_status.status_dispatched
        return value

    result = MechanicHitResult(
        hitpoint_damage=grouped("hitpoint_damage"),
        shield_absorbed=grouped("shield_absorbed"),
        shield_broken=grouped("shield_broken"),
        status_dispatched=grouped("status_dispatched"),
        target_died=grouped("target_died"),
    )
    changed = torch.zeros_like(runtime.battle.entity_active)
    changed.scatter_reduce_(
        1,
        target_slot.reshape(batch, -1),
        (result.hitpoint_damage > 0.0).reshape(batch, -1),
        reduce="amax",
        include_self=True,
    )
    runtime.battle.entity_hp_integer_kind &= ~changed
    return result


class TensorResidentMultiTargetAttacks:
    """Transactional retained owner for simultaneous direct/projectile hits."""

    def __init__(
        self,
        catalog: TensorCombatMechanicCatalog,
        core_to_combat_card: torch.Tensor,
        state: TensorMultiTargetAttackState,
    ) -> None:
        self.catalog = catalog
        self.core_to_combat_card = core_to_combat_card
        self.state = state

    @classmethod
    def from_dispatcher(
        cls,
        dispatcher: TensorMechanicDispatcher,
    ) -> TensorResidentMultiTargetAttacks:
        """Construct from an already attached catalog.

        Prefer :meth:`from_battles` at a scalar boundary: serialized
        ``allTargetsHit`` and ``multipleTargets`` fields are attached by the
        character factory and are not guaranteed to exist in a bare mechanic
        definition.
        """
        return cls(
            dispatcher.combat_catalog,
            dispatcher.core_to_combat_card,
            TensorMultiTargetAttackState.zeros(
                dispatcher.runtime, dispatcher.max_multiple_secondary
            ),
        )

    @classmethod
    def from_battles(
        cls,
        dispatcher: TensorMechanicDispatcher,
        battles: Sequence[BattleState],
    ) -> TensorResidentMultiTargetAttacks:
        catalog = _compile_attached_catalog(dispatcher, battles)
        maximum_secondary = max(0, int(catalog.multiple_target_count.max().item()) - 1)
        return cls(
            catalog,
            dispatcher.core_to_combat_card,
            TensorMultiTargetAttackState.zeros(dispatcher.runtime, maximum_secondary),
        )

    @property
    def device(self) -> torch.device:
        return self.state.source_entity_id.device

    @property
    def batch_size(self) -> int:
        return self.state.batch_size

    @property
    def max_entities(self) -> int:
        return self.state.max_entities

    @property
    def lanes(self) -> int:
        return self.state.maximum_secondary + 1

    def clone(self) -> TensorResidentMultiTargetAttacks:
        return type(self)(self.catalog, self.core_to_combat_card, self.state.clone())

    def fork(
        self, rows: Sequence[int] | torch.Tensor
    ) -> TensorResidentMultiTargetAttacks:
        return type(self)(self.catalog, self.core_to_combat_card, self.state.fork(rows))

    def reset_(self, source_mask: torch.Tensor) -> None:
        self.state.reset_(source_mask)

    def tick_cooldowns_(
        self,
        dt_seconds: float | torch.Tensor,
        battle_mask: torch.Tensor | None = None,
    ) -> None:
        dt = torch.as_tensor(dt_seconds, dtype=torch.float64, device=self.device)
        if dt.ndim == 0:
            dt = dt.expand(self.batch_size)
        if dt.shape != (self.batch_size,):
            raise ValueError("dt_seconds must be scalar or shape [batch]")
        selected = (
            torch.ones(self.batch_size, dtype=torch.bool, device=self.device)
            if battle_mask is None
            else torch.as_tensor(battle_mask, dtype=torch.bool, device=self.device)
        )
        if selected.shape != (self.batch_size,):
            raise ValueError("battle_mask must have shape [batch]")
        self.state.cooldown_seconds.copy_(
            torch.where(
                selected[:, None],
                torch.clamp(self.state.cooldown_seconds - dt[:, None], min=0.0),
                self.state.cooldown_seconds,
            )
        )

    def _cards(self, runtime: TensorBattleRuntime) -> torch.Tensor:
        return self.core_to_combat_card[runtime.battle.entity_card].clamp_min(0)

    def commit_attacks_(
        self,
        runtime: TensorBattleRuntime,
        mechanics: TensorRuntimeMechanics,
        world: TensorMechanicWorld,
        *,
        attack_started: torch.Tensor,
        primary_target_slot: torch.Tensor,
        damage: torch.Tensor,
        projectile: torch.Tensor | bool = False,
        status_eligible: torch.Tensor | bool = True,
        damage_integer_kind: torch.Tensor | bool = False,
        cooldown_after_seconds: torch.Tensor | float = 0.0,
        candidate_mask: torch.Tensor | None = None,
    ) -> MultiTargetCommitResult:
        shape = runtime.battle.entity_id.shape
        if shape != (self.batch_size, self.max_entities):
            raise ValueError("runtime and retained multi-target layout differ")
        if mechanics.batch_size != self.batch_size or mechanics.max_entities != (
            self.max_entities
        ):
            raise ValueError("mechanic and retained multi-target layout differ")
        started = torch.as_tensor(attack_started, dtype=torch.bool, device=self.device)
        primary = torch.as_tensor(
            primary_target_slot, dtype=torch.int64, device=self.device
        )
        incoming = torch.as_tensor(damage, dtype=torch.float64, device=self.device)
        if started.shape != shape or primary.shape != shape or incoming.shape != shape:
            raise ValueError("attack inputs must have shape [batch, entity]")

        def plane(
            value: torch.Tensor | bool | float, dtype: torch.dtype
        ) -> torch.Tensor:
            tensor = torch.as_tensor(value, dtype=dtype, device=self.device)
            try:
                return torch.broadcast_to(tensor, shape).clone()
            except RuntimeError as exc:
                raise ValueError("attack plane is not broadcastable") from exc

        projectile_plane = plane(projectile, torch.bool)
        status_plane = plane(status_eligible, torch.bool)
        integer_plane = plane(damage_integer_kind, torch.bool)
        cooldown_plane = plane(cooldown_after_seconds, torch.float64)
        candidates = (
            world.targetable[:, None, :].expand(
                self.batch_size, self.max_entities, self.max_entities
            )
            if candidate_mask is None
            else torch.as_tensor(candidate_mask, dtype=torch.bool, device=self.device)
        )
        if candidates.shape != (
            self.batch_size,
            self.max_entities,
            self.max_entities,
        ):
            raise ValueError("candidate_mask must have shape [batch, source, target]")

        safe_primary = primary.clamp(min=0, max=self.max_entities - 1)
        primary_in_bounds = (primary >= 0) & (primary < self.max_entities)
        primary_active = runtime.entity_pool.active.gather(1, safe_primary)
        source_active = runtime.entity_pool.active & runtime.battle.entity_active
        card = self._cards(runtime)
        mechanic_slot, has_multiple = self.catalog.mechanic_slot(
            card, CombatMechanicOpcode.MULTIPLE_TARGET
        )
        supported_source = (
            source_active & primary_in_bounds & primary_active & has_multiple
        )
        pending_conflict = self.state.pending_active.any(dim=2) & started
        invalid = started & (~supported_source | pending_conflict)

        primary_id = runtime.battle.entity_id.gather(1, safe_primary)
        expanded = _expanded_world(world, self.max_entities, candidates)
        selected, selected_valid = select_multiple_targets(
            expanded,
            owner=runtime.battle.entity_player.reshape(-1),
            origin_x_units=runtime.battle.entity_x_units.reshape(-1),
            origin_y_units=runtime.battle.entity_y_units.reshape(-1),
            primary_id=primary_id.reshape(-1),
            target_count=self.catalog.multiple_target_count[
                card, mechanic_slot
            ].reshape(-1),
            all_targets_hit=self.catalog.multiple_all_hit[card, mechanic_slot].reshape(
                -1
            ),
        )
        selected = selected.reshape(
            self.batch_size, self.max_entities, self.state.maximum_secondary
        )
        selected_valid = selected_valid.reshape_as(selected)
        grouped_id = torch.cat((primary_id[..., None], selected), dim=2)
        grouped_valid = torch.cat(
            (started[..., None] & supported_source[..., None], selected_valid), dim=2
        )
        grouped_valid &= started[..., None] & supported_source[..., None]
        scale = self.catalog.multiple_damage_scale[card, mechanic_slot]
        grouped_damage = torch.cat(
            (incoming[..., None], incoming[..., None] * scale[..., None]), dim=2
        )
        grouped_integer = integer_plane[..., None].expand_as(grouped_valid)
        grouped_status = status_plane[..., None].expand_as(grouped_valid)
        grouped_projectile = projectile_plane[..., None].expand_as(grouped_valid)

        identity = runtime.battle.entity_id[:, None, None, :]
        target_match = grouped_id[..., None] == identity
        target_slot = target_match.to(torch.int64).argmax(dim=3)
        target_exists = target_match.any(dim=3)
        grouped_valid &= target_exists
        source_slots = torch.arange(self.max_entities, device=self.device).view(
            1, -1, 1
        )
        source_slots = source_slots.expand(self.batch_size, -1, self.lanes)
        source_mechanic_card = mechanics.entity_mechanic_card
        has_on_hit = mechanics._source_has_on_hit(source_mechanic_card)
        direct = grouped_valid & ~grouped_projectile
        queued = grouped_valid & grouped_projectile
        additions = queued.sum(dim=(1, 2), dtype=torch.int64)
        additions += (direct & (grouped_damage > 0.0)).sum(
            dim=(1, 2), dtype=torch.int64
        )
        additions += (direct & grouped_status & has_on_hit[..., None]).sum(
            dim=(1, 2), dtype=torch.int64
        )
        capacity = runtime.events.count.to(torch.int64) + additions <= (
            runtime.events.capacity
        )
        committed = runtime.supported & ~invalid.any(dim=1) & capacity
        accepted = started & supported_source & committed[:, None]

        preview_runtime = runtime.clone()
        preview_runtime.battle.rng = runtime.battle.rng.clone()
        preview_mechanics = mechanics.clone()
        preview = self.state.clone()
        preview.source_entity_id.copy_(
            torch.where(accepted, runtime.battle.entity_id, preview.source_entity_id)
        )
        preview.primary_target_id.copy_(
            torch.where(accepted, primary_id, preview.primary_target_id)
        )
        preview.secondary_target_id.copy_(
            torch.where(accepted[..., None], selected, preview.secondary_target_id)
        )
        preview.secondary_valid.copy_(
            torch.where(accepted[..., None], selected_valid, preview.secondary_valid)
        )
        preview.target_entity_id.copy_(
            torch.where(accepted, primary_id, preview.target_entity_id)
        )
        preview.cooldown_seconds.copy_(
            torch.where(accepted, cooldown_plane, preview.cooldown_seconds)
        )
        queued &= committed[:, None, None]
        preview.pending_active |= queued
        preview.pending_target_id.copy_(
            torch.where(queued, grouped_id, preview.pending_target_id)
        )
        preview.pending_damage.copy_(
            torch.where(queued, grouped_damage, preview.pending_damage)
        )
        preview.pending_damage_integer_kind.copy_(
            torch.where(queued, grouped_integer, preview.pending_damage_integer_kind)
        )
        preview.pending_status_eligible.copy_(
            torch.where(queued, grouped_status, preview.pending_status_eligible)
        )
        preview_runtime.events.append(
            phase=TickPhase.COMBAT,
            opcode=RuntimeEventOpcode.PROJECTILE,
            valid=queued.reshape(self.batch_size, -1),
            source_id=preview_runtime.battle.entity_id[:, :, None]
            .expand_as(grouped_id)
            .reshape(self.batch_size, -1),
            target_id=grouped_id.reshape(self.batch_size, -1),
            amount=grouped_damage.reshape(self.batch_size, -1),
            payload=grouped_integer.to(torch.int64).reshape(self.batch_size, -1),
        )
        direct &= committed[:, None, None]
        hit = _resolve_ordered_hits_(
            preview_runtime,
            preview_mechanics,
            source_slot=source_slots,
            target_slot=target_slot,
            damage=grouped_damage,
            valid=direct,
            status_eligible=direct & grouped_status,
        )
        direct_source = accepted & ~projectile_plane
        preview.secondary_target_id.masked_fill_(direct_source[..., None], 0)
        preview.secondary_valid.masked_fill_(direct_source[..., None], False)
        preview.primary_target_id.masked_fill_(direct_source, 0)
        preview_runtime.mark_dirty(accepted.any(dim=1), phase=TickPhase.COMBAT)

        _copy_runtime_rows_(runtime, preview_runtime, committed)
        _copy_mechanic_rows_(mechanics, preview_mechanics, committed)
        _copy_state_rows_(self.state, preview, committed)
        return MultiTargetCommitResult(
            committed,
            accepted,
            grouped_id,
            grouped_valid & committed[:, None, None],
            direct,
            queued,
            grouped_integer,
            hit,
        )

    def resolve_projectiles_(
        self,
        runtime: TensorBattleRuntime,
        mechanics: TensorRuntimeMechanics,
        arrived: torch.Tensor | None = None,
    ) -> MultiTargetProjectileResult:
        selected = (
            self.state.pending_active.clone()
            if arrived is None
            else torch.as_tensor(arrived, dtype=torch.bool, device=self.device)
            & self.state.pending_active
        )
        if selected.shape != self.state.pending_active.shape:
            raise ValueError("arrived must match retained projectile lanes")
        identity = runtime.battle.entity_id[:, None, None, :]
        target_match = self.state.pending_target_id[..., None] == identity
        target_slot = target_match.to(torch.int64).argmax(dim=3)
        target_exists = target_match.any(dim=3)
        target_alive = runtime.battle.entity_active.gather(
            1, target_slot.reshape(self.batch_size, -1)
        ).reshape_as(target_slot)
        resolved = selected & target_exists & target_alive
        missing = selected & ~resolved

        source_slot = torch.arange(self.max_entities, device=self.device).view(1, -1, 1)
        source_slot = source_slot.expand_as(selected)
        source_identity = runtime.battle.entity_id == self.state.source_entity_id
        invalid_source = selected.any(dim=2) & ~source_identity
        has_on_hit = mechanics._source_has_on_hit(mechanics.entity_mechanic_card)
        additions = (resolved & (self.state.pending_damage > 0.0)).sum(
            dim=(1, 2), dtype=torch.int64
        )
        additions += (
            resolved & self.state.pending_status_eligible & has_on_hit[..., None]
        ).sum(dim=(1, 2), dtype=torch.int64)
        capacity = runtime.events.count.to(torch.int64) + additions <= (
            runtime.events.capacity
        )
        committed = runtime.supported & ~invalid_source.any(dim=1) & capacity
        resolved &= committed[:, None, None]
        missing &= committed[:, None, None]

        preview_runtime = runtime.clone()
        preview_runtime.battle.rng = runtime.battle.rng.clone()
        preview_mechanics = mechanics.clone()
        preview = self.state.clone()
        source_needed = selected.any(dim=2) & committed[:, None]
        previous_pool_active = preview_runtime.entity_pool.active.clone()
        preview_runtime.entity_pool.active |= source_needed
        integer_kind = preview.pending_damage_integer_kind.clone()
        hit = _resolve_ordered_hits_(
            preview_runtime,
            preview_mechanics,
            source_slot=source_slot,
            target_slot=target_slot,
            damage=preview.pending_damage,
            valid=resolved,
            status_eligible=resolved & preview.pending_status_eligible,
        )
        preview_runtime.entity_pool.active.copy_(previous_pool_active)
        consumed = (resolved | missing) & committed[:, None, None]
        preview.pending_active &= ~consumed
        preview.pending_target_id.masked_fill_(consumed, 0)
        preview.pending_damage.masked_fill_(consumed, 0.0)
        preview.pending_damage_integer_kind.masked_fill_(consumed, False)
        preview.pending_status_eligible.masked_fill_(consumed, False)
        finished = source_needed & ~preview.pending_active.any(dim=2)
        preview.primary_target_id.masked_fill_(finished, 0)
        preview.secondary_target_id.masked_fill_(finished[..., None], 0)
        preview.secondary_valid.masked_fill_(finished[..., None], False)
        preview_runtime.mark_dirty(consumed.any(dim=(1, 2)), phase=TickPhase.COMBAT)

        _copy_runtime_rows_(runtime, preview_runtime, committed)
        _copy_mechanic_rows_(mechanics, preview_mechanics, committed)
        _copy_state_rows_(self.state, preview, committed)
        return MultiTargetProjectileResult(
            committed,
            selected,
            resolved,
            missing,
            integer_kind,
            hit,
        )


__all__ = [
    "MultiTargetCommitResult",
    "MultiTargetProjectileResult",
    "TensorMultiTargetAttackState",
    "TensorResidentMultiTargetAttacks",
]
