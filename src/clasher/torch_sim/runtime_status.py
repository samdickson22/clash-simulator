"""Runtime-native building-lifetime and status phase composition.

The Python oracle runs intrinsic building lifetime before status clocks.  This
adapter preserves that ordering over a retained :class:`TensorBattleRuntime`,
resolves target-local periodic hits in entity-ID/source-insertion order, and
emits deterministic damage/death events.  Python entities are used only by
the explicit load/sync boundary helpers.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, fields

import torch

from clasher.battle import BattleState
from clasher.entities import Building
from clasher.torch_sim.entity_pool import EntitySelection
from clasher.torch_sim.runtime_state import (
    RuntimeEventOpcode,
    TensorBattleRuntime,
    TickPhase,
)
from clasher.torch_sim.status import (
    PeriodicDamageSchedule,
    TensorStatusState,
    tick_building_lifetime,
)


@dataclass
class TensorRuntimeStatusPhase:
    """Retained intrinsic-lifetime clocks aligned with runtime entity slots."""

    lifetime_ms: torch.Tensor
    lifetime_elapsed: torch.Tensor
    lifetime_decay_work: torch.Tensor
    lifetime_tick_carry_ms: torch.Tensor
    movement_speed: torch.Tensor
    original_speed: torch.Tensor
    original_speed_valid: torch.Tensor
    movement_mode_multiplier: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.lifetime_ms.shape[0])

    @property
    def max_entities(self) -> int:
        return int(self.lifetime_ms.shape[1])

    @property
    def device(self) -> torch.device:
        return self.lifetime_ms.device

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
    ) -> TensorRuntimeStatusPhase:
        """Load boundary-only lifetime clocks without card-name classification."""

        if len(battles) != runtime.batch_size:
            raise ValueError("battle count does not match runtime batch")
        shape = (runtime.batch_size, runtime.max_entities)
        lifetime_ms = torch.zeros(shape, dtype=torch.int64, device=runtime.device)
        elapsed = torch.zeros(shape, dtype=torch.float64, device=runtime.device)
        work = torch.zeros(shape, dtype=torch.int64, device=runtime.device)
        carry = torch.zeros(shape, dtype=torch.float64, device=runtime.device)
        movement_speed = torch.zeros(shape, dtype=torch.float64, device=runtime.device)
        original_speed = torch.zeros(shape, dtype=torch.float64, device=runtime.device)
        original_speed_valid = torch.zeros(
            shape, dtype=torch.bool, device=runtime.device
        )
        movement_mode_multiplier = torch.ones(
            shape, dtype=torch.float64, device=runtime.device
        )

        for battle_index, battle in enumerate(battles):
            slot_by_id = {
                int(entity_id): slot
                for slot, entity_id in enumerate(
                    runtime.battle.entity_id[battle_index].tolist()
                )
                if entity_id
            }
            if set(slot_by_id) != set(battle.entities):
                raise ValueError("runtime/oracle entity identity sets differ")
            for entity_id, entity in battle.entities.items():
                slot = slot_by_id[entity_id]
                index = (battle_index, slot)
                speed = getattr(entity, "speed", None)
                if speed is not None:
                    movement_speed[index] = float(speed)
                entity_original_speed = getattr(entity, "original_speed", None)
                if entity_original_speed is not None:
                    original_speed[index] = float(entity_original_speed)
                    original_speed_valid[index] = True
                movement_mode_multiplier[index] = float(
                    getattr(entity, "movement_mode_multiplier", 1.0)
                )
                if not isinstance(entity, Building):
                    continue
                catalog_id = int(
                    runtime.card_catalog_index[runtime.battle.entity_card[index]].item()
                )
                boundary_lifetime = int(
                    getattr(entity.card_stats, "lifetime_ms", 0) or 0
                )
                if catalog_id >= 0:
                    compiled_lifetime = int(
                        runtime.catalog.lifetime_ms[catalog_id].item()
                    )
                    if compiled_lifetime != boundary_lifetime:
                        raise ValueError(
                            "serialized building lifetime differs from tensor catalog"
                        )
                    lifetime_ms[index] = compiled_lifetime
                else:
                    # Runtime-generated arena buildings are absent from the
                    # serialized card catalog. Their generalized boundary
                    # payload has no intrinsic lifetime in the standard arena.
                    lifetime_ms[index] = boundary_lifetime
                elapsed[index] = entity.lifetime_elapsed
                work[index] = entity.lifetime_decay_work
                carry[index] = entity.lifetime_tick_carry_ms
        return cls(
            lifetime_ms=lifetime_ms,
            lifetime_elapsed=elapsed,
            lifetime_decay_work=work,
            lifetime_tick_carry_ms=carry,
            movement_speed=movement_speed,
            original_speed=original_speed,
            original_speed_valid=original_speed_valid,
            movement_mode_multiplier=movement_mode_multiplier,
        )

    def clone(self) -> TensorRuntimeStatusPhase:
        return TensorRuntimeStatusPhase(
            lifetime_ms=self.lifetime_ms.clone(),
            lifetime_elapsed=self.lifetime_elapsed.clone(),
            lifetime_decay_work=self.lifetime_decay_work.clone(),
            lifetime_tick_carry_ms=self.lifetime_tick_carry_ms.clone(),
            movement_speed=self.movement_speed.clone(),
            original_speed=self.original_speed.clone(),
            original_speed_valid=self.original_speed_valid.clone(),
            movement_mode_multiplier=self.movement_mode_multiplier.clone(),
        )

    def sync_to_battles(
        self,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
    ) -> None:
        """Sync runtime/status state and represented lifetime clocks."""

        _validate_shapes(runtime, self)
        runtime.sync_to_battles(battles)
        for battle_index, battle in enumerate(battles):
            for slot in range(runtime.max_entities):
                if not bool(runtime.entity_pool.active[battle_index, slot].item()):
                    continue
                entity_id = int(runtime.battle.entity_id[battle_index, slot].item())
                entity = battle.entities[entity_id]
                index = (battle_index, slot)
                if hasattr(entity, "speed"):
                    entity.speed = float(self.movement_speed[index].item())
                    entity.original_speed = (
                        float(self.original_speed[index].item())
                        if bool(self.original_speed_valid[index].item())
                        else None
                    )
                if not isinstance(entity, Building):
                    continue
                entity.lifetime_elapsed = float(self.lifetime_elapsed[index].item())
                entity.lifetime_decay_work = int(self.lifetime_decay_work[index].item())
                entity.lifetime_tick_carry_ms = float(
                    self.lifetime_tick_carry_ms[index].item()
                )


@dataclass(frozen=True)
class RuntimeStatusPhaseResult:
    supported_batch: torch.Tensor
    lifetime_hitpoint_loss: torch.Tensor
    periodic_hitpoint_loss: torch.Tensor
    died: torch.Tensor
    event_count: torch.Tensor


@dataclass(frozen=True)
class _PeriodicResolution:
    hitpoints: torch.Tensor
    alive: torch.Tensor
    hitpoint_loss: torch.Tensor
    died: torch.Tensor
    clear_periodic: torch.Tensor
    event_valid: torch.Tensor
    event_opcode: torch.Tensor
    event_source_id: torch.Tensor
    event_target_id: torch.Tensor
    event_x_units: torch.Tensor
    event_y_units: torch.Tensor
    event_amount: torch.Tensor
    event_payload: torch.Tensor


def _clone_status(status: TensorStatusState) -> TensorStatusState:
    return TensorStatusState(
        **{
            descriptor.name: getattr(status, descriptor.name).clone()
            for descriptor in fields(status)
        }
    )


def _validate_shapes(
    runtime: TensorBattleRuntime,
    phase: TensorRuntimeStatusPhase,
) -> None:
    expected = (runtime.batch_size, runtime.max_entities)
    for descriptor in fields(phase):
        value = getattr(phase, descriptor.name)
        if value.shape != expected:
            raise ValueError(
                f"{descriptor.name} has shape {tuple(value.shape)}, expected {expected}"
            )
        if value.device != runtime.device:
            raise ValueError(f"{descriptor.name} is on a different device")


def _ordered(values: torch.Tensor, selection: EntitySelection) -> torch.Tensor:
    slots = selection.slots.clamp_min(0)
    suffix = values.shape[2:]
    gather = slots.reshape(*slots.shape, *((1,) * len(suffix))).expand(
        *slots.shape, *suffix
    )
    return torch.gather(values, 1, gather)


def _scatter_ordered(
    destination: torch.Tensor,
    selection: EntitySelection,
    values: torch.Tensor,
) -> None:
    batch, ordered_slot = torch.where(selection.valid)
    physical_slot = selection.slots[batch, ordered_slot]
    destination[batch, physical_slot] = values[batch, ordered_slot]


def _periodic_resolution(
    runtime: TensorBattleRuntime,
    schedule: PeriodicDamageSchedule,
    selection: EntitySelection,
    hitpoints: torch.Tensor,
    alive: torch.Tensor,
) -> _PeriodicResolution:
    counts = _ordered(schedule.hit_counts, selection)
    damage = _ordered(schedule.damage, selection)
    source_ids = _ordered(schedule.source_ids, selection)
    source_kind = _ordered(schedule.source_kind, selection)
    schedule_valid = _ordered(schedule.valid, selection)
    maximum_hits = max(1, int(counts.max().item()))
    hit_index = torch.arange(maximum_hits, device=runtime.device)
    raw_valid = (
        selection.valid[:, :, None, None]
        & schedule_valid[:, :, :, None]
        & (hit_index < counts[:, :, :, None])
        & alive[:, :, None, None]
    )
    raw_damage = damage[:, :, :, None].expand_as(raw_valid).to(torch.float64)
    flat_valid = raw_valid.flatten(2)
    flat_damage = raw_damage.flatten(2)
    accumulated = torch.cumsum(torch.where(flat_valid, flat_damage, 0.0), dim=2)
    exclusive = accumulated - torch.where(flat_valid, flat_damage, 0.0)
    committed = flat_valid & (exclusive < hitpoints[:, :, None])
    lethal = committed & (exclusive + flat_damage >= hitpoints[:, :, None])
    committed_damage = torch.where(committed, flat_damage, 0.0)
    next_hitpoints = (hitpoints - committed_damage.sum(dim=2)).clamp_min(0.0)
    next_alive = alive & (next_hitpoints > 0.0)
    died = alive & ~next_alive
    hitpoint_loss = hitpoints - next_hitpoints

    flattened_sources = source_ids[:, :, :, None].expand_as(raw_valid).flatten(2)
    flattened_kinds = source_kind[:, :, :, None].expand_as(raw_valid).flatten(2)
    target_ids = selection.entity_ids[:, :, None].expand_as(flattened_sources)
    ordered_x = _ordered(runtime.battle.entity_x_units, selection)
    ordered_y = _ordered(runtime.battle.entity_y_units, selection)
    event_x = ordered_x[:, :, None].expand_as(flattened_sources)
    event_y = ordered_y[:, :, None].expand_as(flattened_sources)

    pair_valid = torch.stack((committed, lethal), dim=3).flatten(1)
    damage_opcode = torch.full_like(flattened_sources, RuntimeEventOpcode.DAMAGE)
    death_opcode = torch.full_like(flattened_sources, RuntimeEventOpcode.DEATH)
    pair_opcode = torch.stack((damage_opcode, death_opcode), dim=3).flatten(1)
    pair_source = torch.stack((flattened_sources, flattened_sources), dim=3).flatten(1)
    pair_target = torch.stack((target_ids, target_ids), dim=3).flatten(1)
    pair_x = torch.stack((event_x, event_x), dim=3).flatten(1)
    pair_y = torch.stack((event_y, event_y), dim=3).flatten(1)
    pair_amount = torch.stack(
        (flat_damage, torch.zeros_like(flat_damage)), dim=3
    ).flatten(1)
    pair_payload = torch.stack((flattened_kinds, flattened_kinds), dim=3).flatten(1)
    lethal_any = lethal.any(dim=2)
    lethal_flat_index = lethal.to(torch.int64).argmax(dim=2)
    lethal_source_index = torch.div(
        lethal_flat_index, maximum_hits, rounding_mode="floor"
    )
    source_index = torch.arange(counts.shape[2], device=runtime.device)
    clear_ordered = (
        lethal_any[:, :, None]
        & schedule_valid
        & (source_index >= lethal_source_index[:, :, None])
    )
    ordered_source_slots = _ordered(schedule.source_slots, selection)
    clear_periodic = torch.zeros_like(schedule.valid)
    clear_batch, clear_entity, clear_source = torch.where(clear_ordered)
    clear_periodic[
        clear_batch,
        selection.slots[clear_batch, clear_entity],
        ordered_source_slots[clear_batch, clear_entity, clear_source],
    ] = True
    return _PeriodicResolution(
        hitpoints=next_hitpoints,
        alive=next_alive,
        hitpoint_loss=hitpoint_loss,
        died=died,
        clear_periodic=clear_periodic,
        event_valid=pair_valid,
        event_opcode=pair_opcode,
        event_source_id=pair_source,
        event_target_id=pair_target,
        event_x_units=pair_x,
        event_y_units=pair_y,
        event_amount=pair_amount,
        event_payload=pair_payload,
    )


def _lifetime_events(
    runtime: TensorBattleRuntime,
    selection: EntitySelection,
    hitpoint_loss: torch.Tensor,
    died: torch.Tensor,
) -> tuple[torch.Tensor, ...]:
    ordered_loss = _ordered(hitpoint_loss, selection)
    ordered_died = selection.valid & _ordered(died, selection)
    damage_valid = selection.valid & (ordered_loss > 0)
    event_valid = torch.stack((damage_valid, ordered_died), dim=2).flatten(1)
    damage_opcode = torch.full_like(selection.entity_ids, RuntimeEventOpcode.DAMAGE)
    death_opcode = torch.full_like(selection.entity_ids, RuntimeEventOpcode.DEATH)
    opcode = torch.stack((damage_opcode, death_opcode), dim=2).flatten(1)
    target = torch.stack((selection.entity_ids, selection.entity_ids), dim=2).flatten(1)
    x = _ordered(runtime.battle.entity_x_units, selection)
    y = _ordered(runtime.battle.entity_y_units, selection)
    x = torch.stack((x, x), dim=2).flatten(1)
    y = torch.stack((y, y), dim=2).flatten(1)
    amount = torch.stack(
        (
            ordered_loss.to(torch.float64),
            torch.zeros_like(ordered_loss, dtype=torch.float64),
        ),
        dim=2,
    ).flatten(1)
    zeros = torch.zeros_like(target)
    return event_valid, opcode, zeros, target, x, y, amount, zeros


def step_runtime_status_phase_(
    runtime: TensorBattleRuntime,
    phase: TensorRuntimeStatusPhase,
    *,
    dt: float | torch.Tensor = 0.05,
    battle_mask: torch.Tensor | None = None,
) -> RuntimeStatusPhaseResult:
    """Run lifetime then status over every supported battle row.

    Unsupported periodic-damage modifiers fail closed before any tensor is
    mutated. The supported path contains no Python ``Entity`` calls.
    """

    runtime.assert_invariants()
    _validate_shapes(runtime, phase)
    selected = (
        torch.ones(runtime.batch_size, dtype=torch.bool, device=runtime.device)
        if battle_mask is None
        else torch.as_tensor(battle_mask, dtype=torch.bool, device=runtime.device)
    )
    if selected.shape != (runtime.batch_size,):
        raise ValueError("battle_mask must have shape [batch_size]")
    delta = torch.as_tensor(dt, dtype=torch.float64, device=runtime.device)
    if bool((delta < 0).any().item()):
        raise ValueError("dt must be non-negative")
    try:
        delta = torch.broadcast_to(delta, (runtime.batch_size,))
    except RuntimeError as exc:
        raise ValueError("dt must be scalar or have shape [batch_size]") from exc

    phase_support = (
        runtime.phases.supported[:, TickPhase.BUILDING_LIFETIME]
        & runtime.phases.supported[:, TickPhase.STATUS]
    )
    supported = selected & runtime.supported & phase_support
    if runtime.device.type not in {"cpu", "cuda"}:
        supported &= False

    entity_card = runtime.battle.entity_card.clamp_min(0)
    catalog_id = runtime.card_catalog_index[entity_card]
    known = catalog_id >= 0
    safe_catalog_id = catalog_id.clamp_min(0)
    mechanic_count = runtime.catalog.mechanic_count[safe_catalog_id]
    periodic_live = runtime.status.periodic_active.any(dim=2)
    periodic_due = (
        runtime.status.periodic_active
        & (runtime.status.periodic_next_hit - delta[:, None, None] <= 1e-9)
    ).any(dim=2)
    unsafe_periodic = (
        periodic_live
        & periodic_due
        & (~known | (mechanic_count > 0) | (runtime.battle.entity_kind == 1))
    )
    unsupported_rows = supported & unsafe_periodic.any(dim=1)
    if bool(unsupported_rows.any().item()):
        runtime.mark_unsupported(unsupported_rows, phase=TickPhase.STATUS)
        supported &= ~unsupported_rows

    present = runtime.entity_pool.active
    character = (runtime.battle.entity_kind == 0) | (runtime.battle.entity_kind == 1)
    component = supported[:, None] & present & character
    building = component & (runtime.battle.entity_kind == 1)
    lifetime = tick_building_lifetime(
        hitpoints=runtime.battle.entity_hp,
        max_hitpoints=runtime.battle.entity_max_hp,
        lifetime_ms=phase.lifetime_ms,
        lifetime_elapsed=phase.lifetime_elapsed,
        lifetime_decay_work=phase.lifetime_decay_work,
        lifetime_tick_carry_ms=phase.lifetime_tick_carry_ms,
        is_alive=runtime.battle.entity_active,
        dt=delta[:, None],
        component_mask=building,
    )

    preview_status = _clone_status(runtime.status)
    slow_was_active = runtime.status.slow_active.any(dim=2)
    status_component = component & lifetime.is_alive
    schedule = preview_status.tick(delta[:, None], component_mask=status_component)
    selection = runtime.entity_pool.id_order(component)
    ordered_hp = _ordered(lifetime.hitpoints, selection)
    ordered_alive = _ordered(lifetime.is_alive, selection)
    periodic = _periodic_resolution(
        runtime, schedule, selection, ordered_hp, ordered_alive
    )
    lifetime_event = _lifetime_events(
        runtime, selection, lifetime.hitpoint_loss, lifetime.died
    )
    event_delta = lifetime_event[0].sum(
        dim=1, dtype=torch.int64
    ) + periodic.event_valid.sum(dim=1, dtype=torch.int64)
    if bool(
        (runtime.events.count.to(torch.int64) + event_delta > runtime.events.capacity)
        .any()
        .item()
    ):
        overflow = (
            runtime.events.count.to(torch.int64) + event_delta > runtime.events.capacity
        ) & supported
        runtime.mark_unsupported(overflow, phase=TickPhase.STATUS)
        supported &= ~overflow
        # Recompute with overflow rows masked so no phase mutation leaks.
        component = supported[:, None] & present & character
        building = component & (runtime.battle.entity_kind == 1)
        lifetime = tick_building_lifetime(
            hitpoints=runtime.battle.entity_hp,
            max_hitpoints=runtime.battle.entity_max_hp,
            lifetime_ms=phase.lifetime_ms,
            lifetime_elapsed=phase.lifetime_elapsed,
            lifetime_decay_work=phase.lifetime_decay_work,
            lifetime_tick_carry_ms=phase.lifetime_tick_carry_ms,
            is_alive=runtime.battle.entity_active,
            dt=delta[:, None],
            component_mask=building,
        )
        preview_status = _clone_status(runtime.status)
        slow_was_active = runtime.status.slow_active.any(dim=2)
        status_component = component & lifetime.is_alive
        schedule = preview_status.tick(delta[:, None], component_mask=status_component)
        selection = runtime.entity_pool.id_order(component)
        periodic = _periodic_resolution(
            runtime,
            schedule,
            selection,
            _ordered(lifetime.hitpoints, selection),
            _ordered(lifetime.is_alive, selection),
        )
        lifetime_event = _lifetime_events(
            runtime, selection, lifetime.hitpoint_loss, lifetime.died
        )
        event_delta = lifetime_event[0].sum(
            dim=1, dtype=torch.int64
        ) + periodic.event_valid.sum(dim=1, dtype=torch.int64)

    # Commit only after support and aggregate event-capacity preflight.
    runtime.battle.entity_hp.copy_(lifetime.hitpoints)
    runtime.battle.entity_active.copy_(lifetime.is_alive)
    phase.lifetime_elapsed.copy_(lifetime.lifetime_elapsed)
    phase.lifetime_decay_work.copy_(lifetime.lifetime_decay_work)
    phase.lifetime_tick_carry_ms.copy_(lifetime.lifetime_tick_carry_ms)
    update_speed = component & slow_was_active & phase.original_speed_valid
    phase.movement_speed.copy_(
        torch.where(
            update_speed,
            phase.original_speed
            * phase.movement_mode_multiplier
            * preview_status.slow_multiplier,
            phase.movement_speed,
        )
    )
    for descriptor in fields(runtime.status):
        getattr(runtime.status, descriptor.name).copy_(
            getattr(preview_status, descriptor.name)
        )
    _scatter_ordered(runtime.battle.entity_hp, selection, periodic.hitpoints)
    _scatter_ordered(runtime.battle.entity_active, selection, periodic.alive)
    runtime.status._clear_periodic(periodic.clear_periodic)
    runtime.phases.death_pending |= lifetime.died
    ordered_periodic_died = periodic.died
    periodic_died = torch.zeros_like(runtime.battle.entity_active)
    _scatter_ordered(periodic_died, selection, ordered_periodic_died)
    runtime.phases.death_pending |= periodic_died

    if lifetime_event[0].any():
        runtime.events.append(
            phase=TickPhase.BUILDING_LIFETIME,
            opcode=lifetime_event[1],
            valid=lifetime_event[0],
            source_id=lifetime_event[2],
            target_id=lifetime_event[3],
            x_units=lifetime_event[4],
            y_units=lifetime_event[5],
            amount=lifetime_event[6],
            payload=lifetime_event[7],
        )
    if periodic.event_valid.any():
        runtime.events.append(
            phase=TickPhase.STATUS,
            opcode=periodic.event_opcode,
            valid=periodic.event_valid,
            source_id=periodic.event_source_id,
            target_id=periodic.event_target_id,
            x_units=periodic.event_x_units,
            y_units=periodic.event_y_units,
            amount=periodic.event_amount,
            payload=periodic.event_payload,
        )
    runtime.mark_dirty(supported, phase=TickPhase.BUILDING_LIFETIME)
    runtime.mark_dirty(supported, phase=TickPhase.STATUS)

    periodic_loss = torch.zeros_like(runtime.battle.entity_hp)
    _scatter_ordered(periodic_loss, selection, periodic.hitpoint_loss)
    return RuntimeStatusPhaseResult(
        supported_batch=supported,
        lifetime_hitpoint_loss=lifetime.hitpoint_loss,
        periodic_hitpoint_loss=periodic_loss,
        died=lifetime.died | periodic_died,
        event_count=event_delta.to(torch.int32),
    )
