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
from clasher.torch_sim.status_payloads import (
    StatusEffectOpcode,
    StatusTriggerOpcode,
    TensorStatusPayloadCatalog,
    apply_status_payloads,
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
    payload_catalog: TensorStatusPayloadCatalog
    payload_catalog_index: torch.Tensor

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
        definitions = battles[0].card_loader.load_card_definitions()
        payload_names = tuple(
            name for name in runtime.battle.card_names[1:] if name in definitions
        )
        payload_catalog = TensorStatusPayloadCatalog.compile(
            battles[0].card_loader,
            payload_names,
            device=runtime.device,
        )
        payload_catalog_index = torch.zeros(
            len(runtime.battle.card_names),
            dtype=torch.int64,
            device=runtime.device,
        )
        for core_card_id, name in enumerate(runtime.battle.card_names[1:], start=1):
            payload_catalog_index[core_card_id] = payload_catalog.name_to_id.get(
                name, 0
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
            payload_catalog=payload_catalog,
            payload_catalog_index=payload_catalog_index,
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
            payload_catalog=self.payload_catalog,
            payload_catalog_index=self.payload_catalog_index.clone(),
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
class RuntimeStatusPayloadResult:
    supported_batch: torch.Tensor
    applied: torch.Tensor
    rng_draws: torch.Tensor


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
    truncated: torch.Tensor


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
    entity_fields = (
        "lifetime_ms",
        "lifetime_elapsed",
        "lifetime_decay_work",
        "lifetime_tick_carry_ms",
        "movement_speed",
        "original_speed",
        "original_speed_valid",
        "movement_mode_multiplier",
    )
    for name in entity_fields:
        value = getattr(phase, name)
        if value.shape != expected:
            raise ValueError(
                f"{name} has shape {tuple(value.shape)}, expected {expected}"
            )
        if value.device != runtime.device:
            raise ValueError(f"{name} is on a different device")
    if phase.payload_catalog.device != runtime.device:
        raise ValueError("status payload catalog is on a different device")
    if phase.payload_catalog_index.shape != (len(runtime.battle.card_names),):
        raise ValueError("status payload card-index shape differs from runtime cards")
    if phase.payload_catalog_index.device != runtime.device:
        raise ValueError("status payload card index is on a different device")


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
    batch_size, entity_count, source_count = counts.shape
    event_capacity = runtime.events.capacity

    # Expand due hits into a fixed event-capacity worklist. Counts remain in
    # entity-ID/source-insertion order, so the first cumulative source crossing
    # for each ordinal exactly matches the oracle's nested loops.
    active_counts = torch.where(
        selection.valid[:, :, None] & schedule_valid & alive[:, :, None],
        counts,
        torch.zeros_like(counts),
    )
    flat_counts = active_counts.flatten(1)
    cumulative = torch.cumsum(flat_counts, dim=1)
    hit_ordinal = torch.arange(event_capacity, device=runtime.device)[None, :]
    raw_valid = hit_ordinal < cumulative[:, -1, None]
    source_flat = (
        (hit_ordinal[:, :, None] < cumulative[:, None, :]).to(torch.int64).argmax(dim=2)
    )
    target_index = torch.div(source_flat, source_count, rounding_mode="floor")
    source_index = torch.remainder(source_flat, source_count)

    flat_damage = damage.flatten(1).to(torch.float64)
    flat_sources = source_ids.flatten(1)
    flat_kinds = source_kind.flatten(1)
    event_damage = torch.gather(flat_damage, 1, source_flat)
    event_sources = torch.gather(flat_sources, 1, source_flat)
    event_kinds = torch.gather(flat_kinds, 1, source_flat)
    event_hitpoints = torch.gather(hitpoints, 1, target_index)

    target_axis = torch.arange(entity_count, device=runtime.device)
    target_lanes = target_index[:, :, None] == target_axis[None, None, :]
    contribution = torch.where(raw_valid, event_damage, 0.0)[:, :, None] * target_lanes
    accumulated = torch.cumsum(contribution, dim=1)
    exclusive = torch.gather(
        accumulated - contribution,
        2,
        target_index[:, :, None],
    )[:, :, 0]
    committed = raw_valid & (exclusive < event_hitpoints)
    lethal = committed & (exclusive + event_damage >= event_hitpoints)
    committed_damage = torch.where(committed, event_damage, 0.0)
    damage_by_target = torch.zeros_like(hitpoints)
    damage_by_target.scatter_add_(1, target_index, committed_damage)
    next_hitpoints = (hitpoints - damage_by_target).clamp_min(0.0)
    next_alive = alive & (next_hitpoints > 0.0)
    died = alive & ~next_alive
    hitpoint_loss = hitpoints - next_hitpoints

    target_ids = torch.gather(selection.entity_ids, 1, target_index)
    ordered_x = _ordered(runtime.battle.entity_x_units, selection)
    ordered_y = _ordered(runtime.battle.entity_y_units, selection)
    event_x = torch.gather(ordered_x, 1, target_index)
    event_y = torch.gather(ordered_y, 1, target_index)

    pair_valid = torch.stack((committed, lethal), dim=2).flatten(1)
    damage_opcode = torch.full_like(event_sources, RuntimeEventOpcode.DAMAGE)
    death_opcode = torch.full_like(event_sources, RuntimeEventOpcode.DEATH)
    pair_opcode = torch.stack((damage_opcode, death_opcode), dim=2).flatten(1)
    pair_source = torch.stack((event_sources, event_sources), dim=2).flatten(1)
    pair_target = torch.stack((target_ids, target_ids), dim=2).flatten(1)
    pair_x = torch.stack((event_x, event_x), dim=2).flatten(1)
    pair_y = torch.stack((event_y, event_y), dim=2).flatten(1)
    pair_amount = torch.stack(
        (event_damage, torch.zeros_like(event_damage)), dim=2
    ).flatten(1)
    pair_payload = torch.stack((event_kinds, event_kinds), dim=2).flatten(1)

    first_lethal_source = torch.full(
        (batch_size, entity_count),
        source_count,
        dtype=torch.int64,
        device=runtime.device,
    )
    first_lethal_source.scatter_reduce_(
        1,
        target_index,
        torch.where(lethal, source_index, source_count),
        reduce="amin",
        include_self=True,
    )
    lethal_any = first_lethal_source < source_count
    source_axis = torch.arange(source_count, device=runtime.device)
    clear_ordered = (
        lethal_any[:, :, None]
        & schedule_valid
        & (source_axis >= first_lethal_source[:, :, None])
    )
    ordered_source_slots = _ordered(schedule.source_slots, selection)
    clear_periodic = torch.zeros_like(schedule.valid)
    clear_batch, clear_entity, clear_source = torch.where(clear_ordered)
    clear_periodic[
        clear_batch,
        selection.slots[clear_batch, clear_entity],
        ordered_source_slots[clear_batch, clear_entity, clear_source],
    ] = True

    represented_by_target = torch.zeros_like(active_counts[:, :, 0])
    represented_by_target.scatter_add_(
        1,
        target_index,
        raw_valid.to(represented_by_target.dtype),
    )
    remaining_hits = active_counts.sum(dim=2) > represented_by_target
    truncated = (remaining_hits & next_alive).any(dim=1)
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
        truncated=truncated,
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


def _append_events_prevalidated(
    runtime: TensorBattleRuntime,
    *,
    phase: int,
    valid: torch.Tensor,
    opcode: torch.Tensor,
    source_id: torch.Tensor,
    target_id: torch.Tensor,
    x_units: torch.Tensor,
    y_units: torch.Tensor,
    amount: torch.Tensor,
    payload: torch.Tensor,
) -> None:
    """Append lanes after the combined status-capacity preflight."""

    events = runtime.events
    local = torch.cumsum(valid.to(torch.int64), dim=1) - 1
    destinations = events.count.to(torch.int64)[:, None] + local
    rows = torch.arange(runtime.batch_size, device=runtime.device)[:, None].expand_as(
        valid
    )
    row_index = rows[valid]
    event_index = destinations[valid]
    for destination, value in (
        (events.phase, torch.full_like(valid, phase, dtype=torch.int8)),
        (events.opcode, opcode.to(torch.int16)),
        (events.source_id, source_id.to(torch.int64)),
        (events.target_id, target_id.to(torch.int64)),
        (events.x_units, x_units.to(torch.int32)),
        (events.y_units, y_units.to(torch.int32)),
        (events.amount, amount.to(torch.float64)),
        (events.payload, payload.to(torch.int64)),
    ):
        destination[row_index, event_index] = value[valid]
    events.count.add_(valid.sum(dim=1, dtype=events.count.dtype))


def apply_runtime_status_payloads_(
    runtime: TensorBattleRuntime,
    phase: TensorRuntimeStatusPhase,
    source_card: torch.Tensor,
    *,
    trigger: StatusTriggerOpcode,
    eligible: bool | torch.Tensor = True,
    tick_duration_seconds: float | torch.Tensor | None = None,
    random_rolls: torch.Tensor | None = None,
) -> RuntimeStatusPayloadResult:
    """Dispatch one target-aligned serialized status event wave.

    ``source_card`` uses the runtime's card-ID plane, not payload-catalog IDs.
    Attack/aura producers invoke this once per ordered event wave.  When rolls
    are omitted, genuine ``Stun`` mechanics draw from the retained CPython
    RNG in entity-ID then mechanic-slot order; ``SerializedOnHitBuff`` stun
    payloads do not consume RNG, matching their Python mechanic.
    """

    _validate_shapes(runtime, phase)
    core_card = torch.as_tensor(source_card, dtype=torch.int64, device=runtime.device)
    expected = (runtime.batch_size, runtime.max_entities)
    if core_card.shape != expected:
        raise ValueError("source_card must have shape [batch, entity]")
    if bool(
        ((core_card < 0) | (core_card >= len(runtime.battle.card_names))).any().item()
    ):
        raise ValueError("source_card contains an out-of-range runtime card ID")

    row_supported = runtime.supported & runtime.phases.supported[:, TickPhase.STATUS]
    character = (runtime.battle.entity_kind == 0) | (runtime.battle.entity_kind == 1)
    event_target = (
        row_supported[:, None]
        & runtime.entity_pool.active
        & runtime.battle.entity_active
        & character
        & (core_card != 0)
    )
    eligible_target = runtime.status._mask(eligible) & event_target
    payload_card = phase.payload_catalog_index[core_card]
    catalog = phase.payload_catalog
    payload_trigger = catalog.trigger[payload_card]
    payload_effect = catalog.effect[payload_card]
    duration = catalog.duration_ms[payload_card].to(torch.float64) / 1000.0
    trigger_match = payload_trigger == int(trigger)
    from_tick = catalog.duration_from_tick[payload_card]
    needs_tick = event_target[:, :, None] & trigger_match & from_tick
    if bool(needs_tick.any().item()):
        if tick_duration_seconds is None:
            raise ValueError("tick_duration_seconds is required for aura payloads")
        tick_duration = runtime.status._entity_tensor(
            tick_duration_seconds,
            dtype=torch.float64,
            name="tick_duration_seconds",
        )
        duration = torch.where(needs_tick, tick_duration[:, :, None], duration)

    # Stun.on_attack_hit always draws before checking its chance.  A
    # SerializedOnHitBuff whose three axes are zero emits a deterministic stun
    # without a draw, and is distinguishable in the compiled multiplier plane.
    genuine_stun = (
        trigger_match
        & (payload_effect == int(StatusEffectOpcode.STUN))
        & (catalog.movement_multiplier[payload_card] == 1.0)
        & (catalog.attack_multiplier[payload_card] == 1.0)
        & (catalog.spawn_multiplier[payload_card] == 1.0)
        & (duration > 0.0)
    )
    rng_draws = torch.zeros(
        runtime.batch_size, dtype=torch.int32, device=runtime.device
    )
    if random_rolls is None:
        rolls = torch.zeros_like(catalog.chance[payload_card])
        ordered = runtime.entity_pool.id_order(event_target)
        rows = torch.arange(runtime.batch_size, device=runtime.device)
        for ordered_index in range(runtime.max_entities):
            physical_slot = ordered.slots[:, ordered_index].clamp_min(0)
            for payload_slot in range(catalog.max_payloads):
                draw_row = (
                    ordered.valid[:, ordered_index]
                    & genuine_stun[rows, physical_slot, payload_slot]
                )
                draw = runtime.battle.rng.random(draw_row)
                selected_rows = rows[draw_row]
                rolls[
                    selected_rows,
                    physical_slot[draw_row],
                    payload_slot,
                ] = draw[draw_row]
                rng_draws.add_(draw_row.to(torch.int32))
    else:
        rolls = torch.as_tensor(
            random_rolls, dtype=torch.float64, device=runtime.device
        )
        if rolls.shape != payload_trigger.shape:
            raise ValueError("random_rolls must have shape [batch, entity, payload]")

    applied = (
        eligible_target[:, :, None]
        & trigger_match
        & (duration > 0.0)
        & (rolls <= catalog.chance[payload_card])
    )
    slow_applied = applied & (payload_effect == int(StatusEffectOpcode.SLOW))
    slow_target = slow_applied.any(dim=2)
    install_original = slow_target & ~phase.original_speed_valid
    phase.original_speed.copy_(
        torch.where(install_original, phase.movement_speed, phase.original_speed)
    )
    phase.original_speed_valid |= slow_target

    apply_status_payloads(
        runtime.status,
        catalog,
        payload_card,
        trigger=trigger,
        eligible=eligible_target,
        tick_duration_seconds=tick_duration_seconds,
        random_rolls=rolls,
    )
    phase.movement_speed.copy_(
        torch.where(
            slow_target,
            phase.original_speed
            * phase.movement_mode_multiplier
            * runtime.status.slow_multiplier,
            phase.movement_speed,
        )
    )
    changed_rows = applied.any(dim=2).any(dim=1)
    runtime.mark_dirty(changed_rows, phase=TickPhase.STATUS)
    return RuntimeStatusPayloadResult(
        supported_batch=row_supported,
        applied=applied,
        rng_draws=rng_draws,
    )


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

    _validate_shapes(runtime, phase)
    selected = (
        torch.ones(runtime.batch_size, dtype=torch.bool, device=runtime.device)
        if battle_mask is None
        else torch.as_tensor(battle_mask, dtype=torch.bool, device=runtime.device)
    )
    if selected.shape != (runtime.batch_size,):
        raise ValueError("battle_mask must have shape [batch_size]")
    trusted_delta = isinstance(dt, (int, float)) or (
        isinstance(dt, torch.Tensor) and dt is runtime.battle.dt
    )
    delta = torch.as_tensor(dt, dtype=torch.float64, device=runtime.device)
    if isinstance(dt, (int, float)) and float(dt) < 0:
        raise ValueError("dt must be non-negative")
    if not trusted_delta and bool((delta < 0).any().item()):
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
    event_delta = torch.where(
        periodic.truncated,
        torch.full_like(event_delta, runtime.events.capacity + 1),
        event_delta,
    )
    overflow = supported & (
        runtime.events.count.to(torch.int64) + event_delta > runtime.events.capacity
    )
    runtime.mark_unsupported(overflow, phase=TickPhase.STATUS)
    supported &= ~overflow
    component = supported[:, None] & present & character
    status_component = component & lifetime.is_alive
    selection = EntitySelection(
        slots=selection.slots,
        entity_ids=selection.entity_ids,
        valid=selection.valid & supported[:, None],
    )
    lifetime_event = (
        lifetime_event[0] & supported[:, None],
        *lifetime_event[1:],
    )
    periodic_event_valid = periodic.event_valid & supported[:, None]

    # Commit only after support and aggregate event-capacity preflight.
    runtime.battle.entity_hp.copy_(
        torch.where(component, lifetime.hitpoints, runtime.battle.entity_hp)
    )
    runtime.battle.entity_active.copy_(
        torch.where(component, lifetime.is_alive, runtime.battle.entity_active)
    )
    phase.lifetime_elapsed.copy_(
        torch.where(component, lifetime.lifetime_elapsed, phase.lifetime_elapsed)
    )
    phase.lifetime_decay_work.copy_(
        torch.where(component, lifetime.lifetime_decay_work, phase.lifetime_decay_work)
    )
    phase.lifetime_tick_carry_ms.copy_(
        torch.where(
            component,
            lifetime.lifetime_tick_carry_ms,
            phase.lifetime_tick_carry_ms,
        )
    )
    # ResidentEngine refreshes phase workspaces from the canonical core at the
    # next combat boundary. Publish every fixed-point lifetime accumulator so
    # the next tick cannot reset fractional decay progress.
    runtime.battle.entity_lifetime_elapsed.copy_(
        torch.where(
            component,
            lifetime.lifetime_elapsed,
            runtime.battle.entity_lifetime_elapsed,
        )
    )
    runtime.battle.entity_lifetime_decay_work.copy_(
        torch.where(
            component,
            lifetime.lifetime_decay_work,
            runtime.battle.entity_lifetime_decay_work,
        )
    )
    runtime.battle.entity_lifetime_tick_carry_ms.copy_(
        torch.where(
            component,
            lifetime.lifetime_tick_carry_ms,
            runtime.battle.entity_lifetime_tick_carry_ms,
        )
    )
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
        destination = getattr(runtime.status, descriptor.name)
        preview = getattr(preview_status, descriptor.name)
        mask = status_component.reshape(
            *status_component.shape,
            *((1,) * (destination.ndim - 2)),
        )
        destination.copy_(torch.where(mask, preview, destination))
    _scatter_ordered(runtime.battle.entity_hp, selection, periodic.hitpoints)
    _scatter_ordered(runtime.battle.entity_active, selection, periodic.alive)
    runtime.status._clear_periodic(periodic.clear_periodic & supported[:, None, None])
    runtime.phases.death_pending |= lifetime.died & component
    ordered_periodic_died = periodic.died
    periodic_died = torch.zeros_like(runtime.battle.entity_active)
    _scatter_ordered(periodic_died, selection, ordered_periodic_died)
    runtime.phases.death_pending |= periodic_died

    _append_events_prevalidated(
        runtime,
        phase=int(TickPhase.BUILDING_LIFETIME),
        valid=lifetime_event[0],
        opcode=lifetime_event[1],
        source_id=lifetime_event[2],
        target_id=lifetime_event[3],
        x_units=lifetime_event[4],
        y_units=lifetime_event[5],
        amount=lifetime_event[6],
        payload=lifetime_event[7],
    )
    _append_events_prevalidated(
        runtime,
        phase=int(TickPhase.STATUS),
        valid=periodic_event_valid,
        opcode=periodic.event_opcode,
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
        lifetime_hitpoint_loss=torch.where(component, lifetime.hitpoint_loss, 0.0),
        periodic_hitpoint_loss=periodic_loss,
        died=(lifetime.died & component) | periodic_died,
        event_count=torch.where(supported, event_delta, 0).to(torch.int32),
    )
