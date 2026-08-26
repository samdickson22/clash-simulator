"""Runtime-native composition of exact movement kernels.

This module attaches the movement adapter to :class:`TensorTickRuntime`
without introducing Python ``Entity`` calls on the supported path.  Movement
components are visited in stable entity-ID slot order, while every slot
operation remains batched across battle rows.  That preserves the scalar
manager's observable dependency: an earlier mover's new position participates
in a later mover's body-pressure scan.

Unsupported rows are transactional.  They retain both runtime and adapter
tensors byte-for-byte and carry an explicit reason to the caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

import torch

from clasher.kinematics import LOGIC_TICK_MILLISECONDS

from .movement import (
    NATIVE_COLLISION_CAP_UNITS,
    CollisionBatch,
    CollisionResult,
    NaturalMovementResult,
    RiverJumpResult,
    accumulate_collision_vectors,
    advance_native_charge_progress,
    clamp_native_positions,
    consume_accumulated_movement,
    integer_sqrt_tensor,
    river_boundary_crossing_mask,
    river_jump_start_mask,
    river_jump_step,
    target_directed_movement_step,
    trunc_div_tensor,
)
from .movement_adapter import MovementUnsupported, TensorMovementAdapter
from .resident_avoidance import TensorAvoidanceSequence, TensorAvoidanceState
from .runtime import TensorTickRuntime


class MovementEventOpcode(IntEnum):
    ROUTE_NODE_ADVANCED = 1
    RIVER_JUMP_FINISHED = 2


@dataclass(frozen=True)
class TensorMovementEvents:
    count: torch.Tensor
    opcode: torch.Tensor
    source_id: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor

    @classmethod
    def empty(
        cls,
        batch_size: int,
        capacity: int,
        device: torch.device,
    ) -> TensorMovementEvents:
        shape = (batch_size, capacity)
        return cls(
            count=torch.zeros(batch_size, dtype=torch.int32, device=device),
            opcode=torch.zeros(shape, dtype=torch.int16, device=device),
            source_id=torch.zeros(shape, dtype=torch.int64, device=device),
            x_units=torch.zeros(shape, dtype=torch.int64, device=device),
            y_units=torch.zeros(shape, dtype=torch.int64, device=device),
        )


@dataclass(frozen=True)
class RuntimeMovementResult:
    supported_batch: torch.Tensor
    unsupported_reasons: tuple[str | None, ...]
    ordinary_moved: torch.Tensor
    collision_only_moved: torch.Tensor
    river_jump_moved: torch.Tensor
    route_advanced: torch.Tensor
    river_jump_finished: torch.Tensor
    collision: CollisionResult
    events: TensorMovementEvents


def _collision_batch(
    runtime: TensorTickRuntime,
    adapter: TensorMovementAdapter,
    positions: torch.Tensor,
    active_rows: torch.Tensor,
    river_jump_active: torch.Tensor | None = None,
) -> CollisionBatch:
    current_river = (
        adapter.river_jump_active if river_jump_active is None else river_jump_active
    )
    current_in_transit = adapter.in_transit & (
        ~adapter.river_jump_active | current_river
    )
    active = (
        active_rows[:, None]
        & runtime.combat.present
        & runtime.combat.alive
        & adapter.slot_present
    )
    return CollisionBatch(
        position_units=positions,
        active=active,
        entity_id=runtime.combat.entity_id,
        entity_kind=runtime.combat.kind,
        player_id=runtime.combat.owner,
        collision_radius_units=runtime.combat.collision_radius_units,
        mass_milliunits=adapter.mass_milliunits,
        air_collision=(
            adapter.is_air
            | adapter.is_hover
            | current_river
            | adapter.mega_knight_airborne
        ),
        stunned=runtime.combat.stunned,
        in_transit=current_in_transit,
        river_jump_active=current_river,
        death_spawn_travel=adapter.death_spawn_travel,
        mega_knight_airborne=adapter.mega_knight_airborne,
    )


def _identity_support(
    runtime: TensorTickRuntime,
    adapter: TensorMovementAdapter,
) -> torch.Tensor:
    if adapter.batch_size != runtime.batch_size:
        raise ValueError("movement adapter batch does not match runtime")
    if adapter.max_entities != runtime.combat.max_entities:
        raise ValueError("movement adapter capacity does not match runtime")
    if adapter.device != runtime.device:
        raise ValueError("movement adapter and runtime devices differ")
    runtime_slots = runtime.combat.present
    adapter_slots = adapter.slot_present
    # The movement adapter may deliberately omit a live entity whose movement
    # component is owned by a jump, dash, or other special transition. That
    # entity remains present in combat so ordinary movers can still target it.
    # Every adapter slot must therefore be a matching live runtime slot, while
    # extra runtime-only targets are valid.
    return torch.all(
        (~adapter_slots | runtime_slots)
        & (~adapter_slots | (runtime.combat.entity_id == adapter.entity_id)),
        dim=1,
    )


def _collision_pair_for_slot(
    dx: torch.Tensor,
    dy: torch.Tensor,
    collision_distance: torch.Tensor,
    other_mass_milliunits: torch.Tensor,
    own_mass_milliunits: torch.Tensor,
    own_player: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Vectorize the native pair calculation for one mover against all IDs."""

    distance_squared = dx * dx + dy * dy
    collides = (
        (torch.abs(dx) <= collision_distance)
        & (torch.abs(dy) <= collision_distance)
        & (distance_squared <= collision_distance * collision_distance)
    )
    coincident = distance_squared == 0
    adjusted_dy = torch.where(
        coincident,
        torch.where(own_player[:, None] == 0, 1, -1),
        dy,
    )
    distance = torch.where(
        coincident,
        torch.ones_like(distance_squared),
        torch.clamp(integer_sqrt_tensor(distance_squared), min=1),
    )
    overlap = torch.clamp(
        collision_distance - distance,
        min=0,
        max=NATIVE_COLLISION_CAP_UNITS,
    )
    own_mass_whole = torch.div(own_mass_milliunits, 1_000, rounding_mode="floor")
    own_mass_remainder = own_mass_milliunits % 1_000
    own_mass_units = own_mass_whole + (
        (own_mass_remainder > 500)
        | ((own_mass_remainder == 500) & (own_mass_whole % 2 == 1))
    ).to(torch.int64)
    own_mass_units = torch.clamp(own_mass_units, min=1)
    magnitude = (
        torch.div(
            overlap * other_mass_milliunits,
            own_mass_units[:, None] * 1_000,
            rounding_mode="floor",
        )
        + 1
    )
    magnitude = torch.clamp(magnitude, max=NATIVE_COLLISION_CAP_UNITS)
    return (
        torch.stack(
            (
                trunc_div_tensor(dx * magnitude, distance),
                trunc_div_tensor(adjusted_dy * magnitude, distance),
            ),
            dim=-1,
        ),
        collides,
    )


def _collision_for_slot(
    batch: CollisionBatch,
    slot: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Return exact pressure for one ID lane in ``O(batch * entities)``."""

    position = batch.position_units.to(torch.int64)
    active = batch.active.to(torch.bool)
    kind = batch.entity_kind.to(torch.int64)
    radius = torch.clamp(batch.collision_radius_units.to(torch.int64), min=0)
    mass = batch.mass_milliunits.to(torch.int64)
    air = batch.air_collision.to(torch.bool)
    own_position = position[:, slot]
    delta = own_position[:, None] - position
    dx = delta[..., 0]
    dy = delta[..., 1]
    own_active = active[:, slot]
    own_kind = kind[:, slot]
    own_air = air[:, slot]
    own_radius = torch.clamp(radius[:, slot], min=200)
    own_mass = torch.clamp(mass[:, slot], min=1)
    mover_eligible = (
        own_active
        & (own_kind == 0)
        & (
            ~batch.stunned[:, slot]
            | batch.river_jump_active[:, slot]
            | batch.death_spawn_travel[:, slot]
        )
        & (
            ~batch.in_transit[:, slot]
            | batch.river_jump_active[:, slot]
            | batch.mega_knight_airborne[:, slot]
        )
    )
    not_self = torch.arange(position.shape[1], device=position.device) != slot

    troop_vector, troop_contact = _collision_pair_for_slot(
        dx,
        dy,
        own_radius[:, None] + torch.clamp(radius, min=200),
        torch.clamp(mass, min=1),
        own_mass,
        batch.player_id[:, slot].to(torch.int64),
    )
    troop_contact &= (
        mover_eligible[:, None]
        & active
        & (kind == 0)
        & (~batch.in_transit | batch.river_jump_active | batch.mega_knight_airborne)
        & (own_air[:, None] == air)
        & not_self[None, :]
    )

    building_vector, building_contact = _collision_pair_for_slot(
        dx,
        dy,
        torch.minimum(own_radius, torch.full_like(own_radius, 500))[:, None] + radius,
        torch.full_like(mass, 20_000),
        own_mass,
        batch.player_id[:, slot].to(torch.int64),
    )
    building_contact &= (
        mover_eligible[:, None]
        & ~own_air[:, None]
        & active
        & (kind == 1)
        & not_self[None, :]
    )
    vector = torch.where(troop_contact.unsqueeze(-1), troop_vector, 0) + torch.where(
        building_contact.unsqueeze(-1), building_vector, 0
    )
    contacts = troop_contact.to(torch.int64) + building_contact.to(torch.int64)
    return vector.sum(dim=1), contacts.sum(dim=1)


def _support_and_reasons(
    runtime: TensorTickRuntime,
    adapter: TensorMovementAdapter,
) -> tuple[torch.Tensor, tuple[str | None, ...], torch.Tensor, torch.Tensor]:
    identity = _identity_support(runtime, adapter)
    active = runtime.combat.present & runtime.combat.alive & adapter.slot_present
    troop = active & (runtime.combat.kind == 0)
    target_slot = adapter.target_slot.clamp(min=0)
    target_alive = runtime.combat.alive.gather(1, target_slot)
    target_present = runtime.combat.present.gather(1, target_slot)
    has_live_target = (
        (adapter.target_slot >= 0)
        & adapter.target_valid
        & target_alive
        & target_present
    )
    deployed = runtime.combat.deploy_remaining <= 1e-9
    ordinary_intent = (
        troop
        & has_live_target
        & deployed
        & ~runtime.combat.stunned
        & ~adapter.river_jump_active
    )
    river_intent = troop & adapter.river_jump_active

    special_owner = troop & (
        ~adapter.mechanic_free
        | adapter.forced_movement
        | adapter.special_movement & ~adapter.river_jump_active
        | adapter.death_spawn_travel
        | adapter.knockback_active
        | adapter.kamikaze_primed
    )
    unsupported_ordinary = ordinary_intent & ~adapter.ordinary_supported
    unsupported_river = river_intent & ~adapter.river_jump_supported
    building_external = (
        active & (runtime.combat.kind == 1) & (adapter.accumulated_vector_count > 0)
    )

    initial_collision = accumulate_collision_vectors(
        _collision_batch(runtime, adapter, adapter.position_units, identity)
    )
    # River state six performs its avoidance scan before travel. Until that
    # scan has a tensor kernel, any current contact is a conservative fallback.
    river_contact = river_intent & (initial_collision.contact_count > 0)
    may_move_before_targeting = (
        ordinary_intent | river_intent | (troop & (initial_collision.contact_count > 0))
    )
    target_may_move = may_move_before_targeting.gather(1, target_slot)
    own_slots = torch.arange(
        runtime.combat.max_entities,
        dtype=torch.int64,
        device=runtime.device,
    ).view(1, -1)
    earlier_target_moves = (
        ordinary_intent & target_may_move & (adapter.target_slot < own_slots)
    )

    supported = (
        identity
        & initial_collision.supported_batch
        & ~special_owner.any(dim=1)
        & ~unsupported_ordinary.any(dim=1)
        & ~unsupported_river.any(dim=1)
        & ~building_external.any(dim=1)
        & ~river_contact.any(dim=1)
        & ~earlier_target_moves.any(dim=1)
    )
    reasons: list[str | None] = [None] * runtime.batch_size

    def publish(mask: torch.Tensor, reason: str) -> None:
        for row in torch.nonzero(mask & ~supported, as_tuple=False).flatten().tolist():
            if reasons[row] is None:
                reasons[row] = reason

    publish(~identity, "movement adapter entity identity/order mismatch")
    publish(
        ~initial_collision.supported_batch,
        "movement collision traits are not representable",
    )
    publish(special_owner.any(dim=1), "special movement requires Python fallback")
    publish(
        unsupported_ordinary.any(dim=1),
        "ordinary movement support mask rejected an active mover",
    )
    publish(
        unsupported_river.any(dim=1),
        "river-jump support mask rejected an active mover",
    )
    publish(
        building_external.any(dim=1),
        "building external movement is not tensor-plumbed",
    )
    publish(
        river_contact.any(dim=1),
        "river-jump avoidance contact requires Python fallback",
    )
    publish(
        earlier_target_moves.any(dim=1),
        "earlier target movement requires native route refresh",
    )
    return supported, tuple(reasons), ordinary_intent, river_intent


def _emit_events(
    adapter: TensorMovementAdapter,
    route_advanced: torch.Tensor,
    river_finished: torch.Tensor,
) -> TensorMovementEvents:
    events = TensorMovementEvents.empty(
        adapter.batch_size,
        max(1, adapter.max_entities * 2),
        adapter.device,
    )

    def emit(mask: torch.Tensor, opcode: MovementEventOpcode) -> None:
        for slot in range(adapter.max_entities):
            rows = torch.nonzero(mask[:, slot], as_tuple=False).flatten()
            if rows.numel() == 0:
                continue
            event_slot = events.count[rows].to(torch.int64)
            events.opcode[rows, event_slot] = int(opcode)
            events.source_id[rows, event_slot] = adapter.entity_id[rows, slot]
            events.x_units[rows, event_slot] = adapter.position_units[rows, slot, 0]
            events.y_units[rows, event_slot] = adapter.position_units[rows, slot, 1]
            events.count[rows] += 1

    emit(route_advanced, MovementEventOpcode.ROUTE_NODE_ADVANCED)
    emit(river_finished, MovementEventOpcode.RIVER_JUMP_FINISHED)
    return events


def step_runtime_movement_(
    runtime: TensorTickRuntime,
    adapter: TensorMovementAdapter,
    *,
    movement_stop_after_ms: torch.Tensor | None = None,
    movement_wait_ms: torch.Tensor | None = None,
    movement_base_speed_units: torch.Tensor | None = None,
    charge_range_units: torch.Tensor | None = None,
) -> RuntimeMovementResult:
    """Run one native movement component phase over retained tensor state.

    The function does not advance battle clocks or run combat/status/object
    phases.  It is intended for the ``TickPhase.MOVEMENT`` integration point.
    """

    cycle_values = (
        movement_stop_after_ms,
        movement_wait_ms,
        movement_base_speed_units,
    )
    cycle_parameters_present = all(value is not None for value in cycle_values)
    if cycle_parameters_present:
        stop_after_ms = torch.as_tensor(
            movement_stop_after_ms, dtype=torch.int64, device=runtime.device
        )
        wait_ms = torch.as_tensor(
            movement_wait_ms, dtype=torch.int64, device=runtime.device
        )
        base_speed_units = torch.as_tensor(
            movement_base_speed_units, dtype=torch.int64, device=runtime.device
        )
        for value in (stop_after_ms, wait_ms, base_speed_units):
            if value.shape != adapter.entity_id.shape:
                raise ValueError(
                    "movement-cycle tensors must have shape [batch, entity]"
                )
        cycle_bit = int(MovementUnsupported.MOVEMENT_CYCLE)
        cycle_valid = (
            adapter.movement_cycle
            & (stop_after_ms > 0)
            & (wait_ms > 0)
            & (base_speed_units > 0)
        )
        cycle_only = cycle_valid & ((adapter.ordinary_unsupported & ~cycle_bit) == 0)
        adapter.ordinary_unsupported &= ~cycle_bit
        adapter.ordinary_supported |= cycle_only
    else:
        stop_after_ms = torch.zeros_like(adapter.entity_id)
        wait_ms = torch.zeros_like(adapter.entity_id)
        base_speed_units = torch.ones_like(adapter.entity_id)

    charge_parameters_present = charge_range_units is not None
    charge_range = (
        torch.as_tensor(charge_range_units, dtype=torch.int64, device=runtime.device)
        if charge_parameters_present
        else torch.zeros_like(adapter.entity_id)
    )
    if charge_range.shape != adapter.entity_id.shape:
        raise ValueError("charge_range_units must have shape [batch, entity]")
    if charge_parameters_present:
        charge_bit = int(MovementUnsupported.CHARGE_COMPONENT)
        charge_valid = adapter.charge_component & (charge_range > 0)
        charge_only = charge_valid & ((adapter.ordinary_unsupported & ~charge_bit) == 0)
        adapter.ordinary_unsupported &= ~charge_bit
        adapter.ordinary_supported |= charge_only

    avoidance_bit = int(MovementUnsupported.AVOIDANCE_PREPASS)
    avoidance_only = adapter.avoidance_prepass_required & (
        (adapter.ordinary_unsupported & ~avoidance_bit) == 0
    )
    adapter.ordinary_unsupported &= ~avoidance_bit
    adapter.ordinary_supported |= avoidance_only

    supported, reasons, ordinary_intent, river_intent = _support_and_reasons(
        runtime, adapter
    )
    entity_shape = runtime.combat.present.shape
    working_positions = adapter.position_units.clone()
    ordinary_position = adapter.position_units.clone()
    ordinary_vector = torch.zeros_like(adapter.position_units)
    ordinary_intended = torch.zeros(
        entity_shape, dtype=torch.int64, device=runtime.device
    )
    ordinary_moved = torch.zeros(entity_shape, dtype=torch.bool, device=runtime.device)
    collision_only_moved = torch.zeros_like(ordinary_moved)
    river_moved = torch.zeros_like(ordinary_moved)
    river_position = adapter.position_units.clone()
    river_active_after = adapter.river_jump_active.clone()
    working_river_active = adapter.river_jump_active.clone()
    river_finished = torch.zeros_like(ordinary_moved)
    collision_vectors = torch.zeros_like(adapter.position_units)
    collision_counts = torch.zeros(
        entity_shape, dtype=torch.int64, device=runtime.device
    )
    previous_route_count = adapter.route_count.clone()

    active_troop = (
        supported[:, None]
        & runtime.combat.present
        & runtime.combat.alive
        & (runtime.combat.kind == 0)
    )
    target_slot = adapter.target_slot.clamp(min=0)
    current_target_position = torch.stack(
        (
            runtime.combat.x_units.gather(1, target_slot),
            runtime.combat.y_units.gather(1, target_slot),
        ),
        dim=-1,
    )
    adapter.target_position_units.copy_(
        torch.where(
            (supported[:, None] & (adapter.target_slot >= 0)).unsqueeze(-1),
            current_target_position,
            adapter.target_position_units,
        )
    )

    avoidance_state = TensorAvoidanceState.from_movement_adapter(
        adapter,
        stopped=~(ordinary_intent | river_intent)
        | (runtime.combat.deploy_remaining > 1e-9)
        | runtime.combat.stunned
        | adapter.kamikaze_primed,
        charging=adapter.charge_component & (adapter.native_charge_progress >= 10_000),
        leap_clear=adapter.mega_knight_airborne,
    )
    # The sequence and movement kernels share this current-position plane.
    # Each completed ID lane is therefore visible to every later avoidance
    # scan without a host sync or Python entity round-trip.
    avoidance_state.position_units = working_positions
    avoidance_sequence = TensorAvoidanceSequence.begin(
        avoidance_state, battle_mask=supported
    )
    lane_index = torch.arange(
        adapter.max_entities, dtype=torch.int64, device=runtime.device
    ).view(1, -1)
    stable_lanes = (
        ~avoidance_sequence.ordered_valid | (avoidance_sequence.order == lane_index)
    ).all(dim=1)
    avoidance_sequence.supported_batch &= stable_lanes
    supported &= avoidance_sequence.supported_batch
    active_troop &= supported[:, None]
    if not bool(stable_lanes.all().item()):
        mutable_reasons = list(reasons)
        for row in torch.nonzero(~stable_lanes, as_tuple=False).flatten().tolist():
            if mutable_reasons[row] is None:
                mutable_reasons[row] = (
                    "movement slots are not sorted in stable entity-ID order"
                )
        reasons = tuple(mutable_reasons)

    # Stable entity-ID component order. Each iteration is one tensor lane over
    # every battle row, never a Python Entity call.
    for slot in range(adapter.max_entities):
        avoidance_sequence.step_rank_(slot)
        slot_active = active_troop[:, slot]
        slot_vector, slot_count = _collision_for_slot(
            _collision_batch(
                runtime,
                adapter,
                working_positions,
                supported,
                working_river_active,
            ),
            slot,
        )
        collision_vectors[:, slot] = torch.where(
            slot_active.unsqueeze(-1), slot_vector, collision_vectors[:, slot]
        )
        collision_counts[:, slot] = torch.where(
            slot_active, slot_count, collision_counts[:, slot]
        )

        total_vector = adapter.accumulated_vector_units[:, slot] + slot_vector
        total_count = adapter.accumulated_vector_count[:, slot] + slot_count
        external = consume_accumulated_movement(
            total_vector,
            total_count,
            bypasses_cap=adapter.accumulated_vector_bypasses_cap[:, slot],
        )

        ordinary = supported & ordinary_intent[:, slot]
        if adapter.max_entities:
            has_natural_distance = torch.any(
                adapter.waypoint_units[:, slot] != working_positions[:, slot], dim=1
            )
            cycle = (
                ordinary
                & adapter.movement_cycle[:, slot]
                & has_natural_distance
                & cycle_parameters_present
            )
            increment = trunc_div_tensor(
                LOGIC_TICK_MILLISECONDS * adapter.effective_speed_units[:, slot],
                base_speed_units[:, slot].clamp_min(1),
            )
            advanced_timer = adapter.movement_phase_elapsed_ms[:, slot] + increment
            cycle_length = (stop_after_ms[:, slot] + wait_ms[:, slot]).clamp_min(1)
            wrapped = cycle & (advanced_timer >= cycle_length)
            next_timer = torch.where(
                wrapped,
                torch.remainder(advanced_timer, cycle_length),
                advanced_timer,
            )
            adapter.movement_phase_elapsed_ms[:, slot] = torch.where(
                cycle,
                next_timer,
                adapter.movement_phase_elapsed_ms[:, slot],
            )
            paused = cycle & ~wrapped & (next_timer > stop_after_ms[:, slot])
            effective_speed = torch.where(
                paused,
                torch.zeros_like(adapter.effective_speed_units[:, slot]),
                adapter.effective_speed_units[:, slot],
            )
            natural = target_directed_movement_step(
                working_positions[:, slot],
                adapter.waypoint_units[:, slot],
                effective_speed,
                supported=ordinary,
                external_vector_units=external,
                avoidance=adapter.avoidance[:, slot],
            )
            crossing = (
                ordinary
                & ~adapter.is_air[:, slot]
                & ~adapter.is_hover[:, slot]
                & ~torch.any(external != 0, dim=1)
                & river_boundary_crossing_mask(
                    working_positions[:, slot], natural.position_units
                )
            )
            jump_start = (
                crossing
                & ~adapter.river_jump_blocked[:, slot]
                & river_jump_start_mask(
                    natural.position_units,
                    jump_height=adapter.jump_height[:, slot],
                    jump_speed_units=adapter.jump_speed_units[:, slot],
                    landing_valid=adapter.river_target_valid[:, slot],
                )
            )
            landing_missing = (
                crossing
                & adapter.jump_height[:, slot]
                & ~adapter.river_target_valid[:, slot]
            )
            adapter.river_jump_blocked[:, slot] |= landing_missing
            natural = NaturalMovementResult(
                position_units=torch.where(
                    jump_start.unsqueeze(-1),
                    working_positions[:, slot],
                    natural.position_units,
                ),
                movement_vector_units=natural.movement_vector_units,
                intended_movement_units=natural.intended_movement_units,
                supported=natural.supported,
            )
            if charge_parameters_present:
                charge = advance_native_charge_progress(
                    adapter.native_charge_progress[:, slot],
                    natural.intended_movement_units,
                    charge_range[:, slot],
                    active=ordinary & adapter.charge_component[:, slot],
                )
                adapter.native_charge_progress[:, slot] = charge.progress
                distance = (
                    adapter.distance_traveled_bits[:, slot]
                    .contiguous()
                    .view(torch.float64)
                )
                advanced_distance = (
                    (distance + charge.distance_work_units.to(torch.float64) / 1_000.0)
                    .contiguous()
                    .view(torch.int64)
                )
                charge_reset = charge.supported & (natural.intended_movement_units < 10)
                adapter.distance_traveled_bits[:, slot] = torch.where(
                    charge.supported,
                    torch.where(
                        charge_reset,
                        torch.zeros_like(advanced_distance),
                        advanced_distance,
                    ),
                    adapter.distance_traveled_bits[:, slot],
                )
            working_positions[:, slot] = natural.position_units
            ordinary_position[:, slot] = natural.position_units
            ordinary_vector[:, slot] = natural.movement_vector_units
            ordinary_intended[:, slot] = natural.intended_movement_units
            ordinary_moved[:, slot] = ordinary & (
                torch.any(
                    natural.position_units != adapter.position_units[:, slot], dim=-1
                )
            )
            lane_support = torch.zeros_like(ordinary_intent)
            lane_support[:, slot] = ordinary
            adapter.apply_natural_result(
                NaturalMovementResult(
                    position_units=ordinary_position,
                    movement_vector_units=ordinary_vector,
                    intended_movement_units=ordinary_intended,
                    supported=lane_support,
                )
            )
            working_positions[:, slot] = adapter.position_units[:, slot]
            adapter.river_origin_units[:, slot] = torch.where(
                jump_start.unsqueeze(-1),
                working_positions[:, slot],
                adapter.river_origin_units[:, slot],
            )
            adapter.river_origin_valid[:, slot] |= jump_start
            jump_delta = (
                adapter.river_target_units[:, slot] - working_positions[:, slot]
            )
            jump_distance = integer_sqrt_tensor(
                torch.sum(jump_delta * jump_delta, dim=1)
            )
            jump_duration = torch.maximum(
                torch.full(
                    (adapter.batch_size,),
                    0.05,
                    dtype=torch.float64,
                    device=adapter.device,
                ),
                jump_distance.to(torch.float64)
                / adapter.jump_speed_units[:, slot].clamp_min(1).to(torch.float64)
                * 0.05,
            )
            adapter.river_elapsed_bits[:, slot] = torch.where(
                jump_start,
                torch.zeros_like(adapter.river_elapsed_bits[:, slot]),
                adapter.river_elapsed_bits[:, slot],
            )
            adapter.river_duration_bits[:, slot] = torch.where(
                jump_start,
                jump_duration.contiguous().view(torch.int64),
                adapter.river_duration_bits[:, slot],
            )
            adapter.river_jump_active[:, slot] |= jump_start
            adapter.special_movement[:, slot] |= jump_start
            adapter.river_jump_supported[:, slot] |= jump_start
            adapter.river_unsupported[:, slot] = torch.where(
                jump_start,
                torch.zeros_like(adapter.river_unsupported[:, slot]),
                adapter.river_unsupported[:, slot],
            )
            working_river_active[:, slot] |= jump_start
            river_active_after[:, slot] |= jump_start
            avoidance_state.air_collision[:, slot] |= jump_start
            if adapter.route_capacity:
                retained_jump_route = torch.zeros_like(adapter.route_cells[:, slot])
                retained_jump_route[:, 0] = torch.div(
                    adapter.river_target_units[:, slot], 500, rounding_mode="floor"
                )
                adapter.route_cells[:, slot] = torch.where(
                    jump_start[:, None, None],
                    retained_jump_route,
                    adapter.route_cells[:, slot],
                )
                adapter.route_count[:, slot] = torch.where(
                    jump_start,
                    torch.ones_like(adapter.route_count[:, slot]),
                    adapter.route_count[:, slot],
                )
                adapter.waypoint_units[:, slot] = torch.where(
                    jump_start.unsqueeze(-1),
                    adapter.river_target_units[:, slot],
                    adapter.waypoint_units[:, slot],
                )

        river = supported & river_intent[:, slot]
        jump = river_jump_step(
            working_positions[:, slot],
            adapter.river_target_units[:, slot],
            adapter.jump_speed_units[:, slot],
            active=river,
            avoidance=adapter.avoidance[:, slot],
        )
        if charge_parameters_present:
            river_charge = advance_native_charge_progress(
                adapter.native_charge_progress[:, slot],
                torch.minimum(
                    adapter.jump_speed_units[:, slot].clamp_min(0),
                    integer_sqrt_tensor(
                        torch.sum(
                            (
                                adapter.river_target_units[:, slot]
                                - working_positions[:, slot]
                            )
                            ** 2,
                            dim=1,
                        )
                    ),
                ),
                charge_range[:, slot],
                active=river & adapter.charge_component[:, slot],
                ordinary_movement_state=False,
            )
            adapter.native_charge_progress[:, slot] = river_charge.progress
            adapter.distance_traveled_bits[:, slot] = torch.where(
                river_charge.supported,
                torch.zeros_like(adapter.distance_traveled_bits[:, slot]),
                adapter.distance_traveled_bits[:, slot],
            )
        jump_position = clamp_native_positions(jump.position_units + external)
        jump_position = torch.where(
            jump.supported.unsqueeze(-1), jump_position, working_positions[:, slot]
        )
        working_positions[:, slot] = jump_position
        river_position[:, slot] = jump_position
        river_active_after[:, slot] = torch.where(
            jump.supported, jump.active, river_active_after[:, slot]
        )
        working_river_active[:, slot] = torch.where(
            jump.supported, jump.active, working_river_active[:, slot]
        )
        river_finished[:, slot] = jump.finished & jump.supported
        river_moved[:, slot] = jump.supported & (
            torch.any(jump_position != adapter.position_units[:, slot], dim=-1)
        )
        river_facing = (
            adapter.river_target_units[:, slot] - adapter.position_units[:, slot]
        )
        adapter.facing_units[:, slot] = torch.where(
            (jump.supported & torch.any(river_facing != 0, dim=1)).unsqueeze(-1),
            river_facing,
            adapter.facing_units[:, slot],
        )
        avoidance_state.air_collision[:, slot] = torch.where(
            jump.supported,
            adapter.is_air[:, slot]
            | adapter.is_hover[:, slot]
            | jump.active
            | adapter.mega_knight_airborne[:, slot],
            avoidance_state.air_collision[:, slot],
        )

        collision_only = slot_active & ~ordinary & ~river
        collision_position = clamp_native_positions(
            working_positions[:, slot] + external
        )
        collision_changed = collision_only & torch.any(external != 0, dim=-1)
        working_positions[:, slot] = torch.where(
            collision_only.unsqueeze(-1),
            collision_position,
            working_positions[:, slot],
        )
        collision_only_moved[:, slot] = collision_changed

    route_advanced = adapter.route_count < previous_route_count
    adapter.apply_river_result(
        RiverJumpResult(
            position_units=river_position,
            active=river_active_after,
            finished=river_finished,
            supported=river_intent & supported[:, None],
        )
    )
    adapter.position_units.copy_(
        torch.where(
            collision_only_moved.unsqueeze(-1),
            working_positions,
            adapter.position_units,
        )
    )

    processed_troop = active_troop
    adapter.accumulated_vector_units.copy_(
        torch.where(
            processed_troop.unsqueeze(-1),
            torch.zeros_like(adapter.accumulated_vector_units),
            adapter.accumulated_vector_units,
        )
    )
    adapter.accumulated_vector_count.copy_(
        torch.where(
            processed_troop,
            torch.zeros_like(adapter.accumulated_vector_count),
            adapter.accumulated_vector_count,
        )
    )
    adapter.accumulated_vector_bypasses_cap &= ~processed_troop
    adapter.pending_vector_units.copy_(
        torch.where(
            processed_troop.unsqueeze(-1),
            torch.zeros_like(adapter.pending_vector_units),
            adapter.pending_vector_units,
        )
    )
    adapter.pending_vector_consumed |= processed_troop

    final_position = adapter.position_units
    runtime.combat.x_units.copy_(
        torch.where(supported[:, None], final_position[..., 0], runtime.combat.x_units)
    )
    runtime.combat.y_units.copy_(
        torch.where(supported[:, None], final_position[..., 1], runtime.combat.y_units)
    )
    runtime.core.entity_x_units.copy_(
        torch.where(
            supported[:, None],
            runtime.combat.x_units.to(torch.int32),
            runtime.core.entity_x_units,
        )
    )
    runtime.core.entity_y_units.copy_(
        torch.where(
            supported[:, None],
            runtime.combat.y_units.to(torch.int32),
            runtime.core.entity_y_units,
        )
    )
    runtime.facing_x_units.copy_(
        torch.where(
            supported[:, None], adapter.facing_units[..., 0], runtime.facing_x_units
        )
    )
    runtime.facing_y_units.copy_(
        torch.where(
            supported[:, None], adapter.facing_units[..., 1], runtime.facing_y_units
        )
    )
    runtime.combat.airborne.copy_(
        torch.where(
            supported[:, None],
            adapter.is_air | adapter.river_jump_active,
            runtime.combat.airborne,
        )
    )

    collision_result = CollisionResult(
        accumulated_vector_units=collision_vectors,
        contact_count=collision_counts,
        supported_batch=supported,
    )
    events = _emit_events(adapter, route_advanced, river_finished)
    return RuntimeMovementResult(
        supported_batch=supported,
        unsupported_reasons=reasons,
        ordinary_moved=ordinary_moved,
        collision_only_moved=collision_only_moved,
        river_jump_moved=river_moved,
        route_advanced=route_advanced,
        river_jump_finished=river_finished,
        collision=collision_result,
        events=events,
    )
