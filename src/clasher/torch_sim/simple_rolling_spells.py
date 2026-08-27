"""Fixed-shape rolling-line spells for the practical tensor Gym.

The kernel models a moving capsule rather than a homing projectile.  Setup or
an action adapter supplies only numeric command planes; card identities and
serialized-object traversal stay outside the runtime path.  Each roller keeps
a bounded stable-ID ledger so an entity can intersect several consecutive
segments without receiving repeated damage.

Damage is applied directly to :class:`FastGymState`.  Displacement and an
optional terminal spawn request are returned as dense tensors for the owning
runtime to compose with its ordinary movement and spawn allocators.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import torch

from .simple_modifiers import FastModifierState, intercept_fast_shield_hits_
from .simple_state import FAST_KIND_TROOP, FastGymState

FAST_ROLLING_NO_SPAWN = -1


@dataclass(frozen=True)
class FastRollingSpellCommands:
    """Numeric cast commands with one fixed ``[batch, commands]`` shape.

    ``target_*`` establishes direction only; ``travel_range_units`` controls
    the terminal position.  Positive radial push moves away from the closest
    point on the swept segment, while positive forward push follows the cast
    direction.  Negative values reverse either displacement.

    A nonnegative ``impact_spawn_blueprint_id`` requests one terminal spawn
    command.  The blueprint ID is an opaque row in the caller-owned spawn
    catalog; this module never resolves it or dispatches on card names.
    """

    ready: torch.Tensor
    owner: torch.Tensor
    source_card_id: torch.Tensor
    origin_x_units: torch.Tensor
    origin_y_units: torch.Tensor
    target_x_units: torch.Tensor
    target_y_units: torch.Tensor
    travel_range_units: torch.Tensor
    speed_units_per_tick: torch.Tensor
    half_width_units: torch.Tensor
    damage: torch.Tensor
    ground_only: torch.Tensor
    tower_damage_multiplier: torch.Tensor
    radial_push_units: torch.Tensor
    forward_push_units: torch.Tensor
    impact_spawn_blueprint_id: torch.Tensor
    impact_spawn_count: torch.Tensor
    impact_spawn_deploy_ticks: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.ready.shape[0])

    @property
    def command_count(self) -> int:
        return int(self.ready.shape[1])


@dataclass
class FastRollingSpellState:
    """Reusable fixed-capacity rolling-spell pool.

    Scalar spell planes have shape ``[B, R]``. ``hit_stable_ids`` has shape
    ``[B, R, E]`` and is both the once-only hit ledger and its capacity bound.
    A newly allocated roller always clears its ledger before becoming active.
    """

    device: torch.device
    active: torch.Tensor
    owner: torch.Tensor
    source_card_id: torch.Tensor
    origin_x_units: torch.Tensor
    origin_y_units: torch.Tensor
    target_x_units: torch.Tensor
    target_y_units: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    travel_range_units: torch.Tensor
    distance_travelled_units: torch.Tensor
    speed_units_per_tick: torch.Tensor
    half_width_units: torch.Tensor
    damage: torch.Tensor
    ground_only: torch.Tensor
    tower_damage_multiplier: torch.Tensor
    radial_push_units: torch.Tensor
    forward_push_units: torch.Tensor
    impact_spawn_blueprint_id: torch.Tensor
    impact_spawn_count: torch.Tensor
    impact_spawn_deploy_ticks: torch.Tensor
    hit_stable_ids: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.active.shape[0])

    @property
    def max_rollers(self) -> int:
        return int(self.active.shape[1])

    @property
    def max_hit_records(self) -> int:
        return int(self.hit_stable_ids.shape[2])

    @classmethod
    def empty(
        cls,
        batch_size: int,
        *,
        max_rollers: int = 16,
        max_hit_records: int = 64,
        device: str | torch.device = "cpu",
    ) -> FastRollingSpellState:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if max_rollers < 1 or max_hit_records < 1:
            raise ValueError("roller and hit-record capacities must be positive")
        tensor_device = torch.device(device)
        if tensor_device.type == "cuda" and tensor_device.index is None:
            tensor_device = torch.device("cuda", torch.cuda.current_device())
        shape = (batch_size, max_rollers)

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(shape, dtype=dtype, device=tensor_device)

        return cls(
            device=tensor_device,
            active=zeros(torch.bool),
            owner=zeros(torch.int8),
            source_card_id=zeros(torch.int64),
            origin_x_units=zeros(torch.int32),
            origin_y_units=zeros(torch.int32),
            target_x_units=zeros(torch.int32),
            target_y_units=zeros(torch.int32),
            x_units=zeros(torch.int32),
            y_units=zeros(torch.int32),
            travel_range_units=zeros(torch.int32),
            distance_travelled_units=zeros(torch.int32),
            speed_units_per_tick=zeros(torch.int32),
            half_width_units=zeros(torch.int32),
            damage=zeros(torch.float32),
            ground_only=zeros(torch.bool),
            tower_damage_multiplier=torch.ones(
                shape, dtype=torch.float32, device=tensor_device
            ),
            radial_push_units=zeros(torch.int32),
            forward_push_units=zeros(torch.int32),
            impact_spawn_blueprint_id=torch.full(
                shape,
                FAST_ROLLING_NO_SPAWN,
                dtype=torch.int64,
                device=tensor_device,
            ),
            impact_spawn_count=zeros(torch.int32),
            impact_spawn_deploy_ticks=zeros(torch.int32),
            hit_stable_ids=torch.zeros(
                (batch_size, max_rollers, max_hit_records),
                dtype=torch.int64,
                device=tensor_device,
            ),
        )

    def clone(self) -> FastRollingSpellState:
        values: dict[str, object] = {"device": self.device}
        for descriptor in fields(self):
            if descriptor.name != "device":
                values[descriptor.name] = getattr(self, descriptor.name).clone()
        return type(self)(**values)  # type: ignore[arg-type]


@dataclass(frozen=True)
class FastRollingAllocationResult:
    """Per-command stable allocation telemetry."""

    accepted: torch.Tensor
    invalid: torch.Tensor
    capacity_rejected: torch.Tensor
    roller_slot: torch.Tensor


@dataclass(frozen=True)
class FastRollingSpawnTriggers:
    """Padded terminal-spawn commands ordered by rolling-pool slot."""

    ready: torch.Tensor
    owner: torch.Tensor
    source_card_id: torch.Tensor
    blueprint_id: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    count: torch.Tensor
    deploy_ticks: torch.Tensor


@dataclass(frozen=True)
class FastRollingStepResult:
    """Dense damage, displacement, capacity, and terminal event planes."""

    hit: torch.Tensor
    hit_count: torch.Tensor
    hit_capacity_rejected: torch.Tensor
    damage_by_entity: torch.Tensor
    impulse_dx_units: torch.Tensor
    impulse_dy_units: torch.Tensor
    impulse_affected: torch.Tensor
    ended: torch.Tensor
    spawn: FastRollingSpawnTriggers


_COMMAND_DTYPES = {
    "ready": torch.bool,
    "owner": torch.int8,
    "source_card_id": torch.int64,
    "origin_x_units": torch.int32,
    "origin_y_units": torch.int32,
    "target_x_units": torch.int32,
    "target_y_units": torch.int32,
    "travel_range_units": torch.int32,
    "speed_units_per_tick": torch.int32,
    "half_width_units": torch.int32,
    "damage": torch.float32,
    "ground_only": torch.bool,
    "tower_damage_multiplier": torch.float32,
    "radial_push_units": torch.int32,
    "forward_push_units": torch.int32,
    "impact_spawn_blueprint_id": torch.int64,
    "impact_spawn_count": torch.int32,
    "impact_spawn_deploy_ticks": torch.int32,
}


def _validate_commands(
    state: FastRollingSpellState,
    commands: FastRollingSpellCommands,
) -> None:
    if commands.ready.ndim != 2 or commands.batch_size != state.batch_size:
        raise ValueError("command tensors must have shape [batch, commands]")
    shape = tuple(commands.ready.shape)
    for descriptor in fields(commands):
        value = getattr(commands, descriptor.name)
        if tuple(value.shape) != shape:
            raise ValueError(f"{descriptor.name} must have shape [batch, commands]")
        if value.device != state.device:
            raise ValueError(f"{descriptor.name} is on a different device")
        expected = _COMMAND_DTYPES[descriptor.name]
        if value.dtype != expected:
            raise ValueError(f"{descriptor.name} must use {expected}")


def _validate_state(state: FastRollingSpellState) -> None:
    shape = tuple(state.active.shape)
    if len(shape) != 2:
        raise ValueError("rolling state planes must have shape [batch, rollers]")
    for descriptor in fields(state):
        if descriptor.name in ("device", "hit_stable_ids"):
            continue
        value = getattr(state, descriptor.name)
        if tuple(value.shape) != shape or value.device != state.device:
            raise ValueError(f"{descriptor.name} must match rolling state")
    expected_ledger = (shape[0], shape[1], state.max_hit_records)
    if (
        tuple(state.hit_stable_ids.shape) != expected_ledger
        or state.hit_stable_ids.device != state.device
        or state.hit_stable_ids.dtype != torch.int64
    ):
        raise ValueError("hit_stable_ids must be int64 [batch, rollers, records]")


def allocate_fast_rolling_spells_(
    state: FastRollingSpellState,
    commands: FastRollingSpellCommands,
    *,
    game_over: torch.Tensor | None = None,
) -> FastRollingAllocationResult:
    """Allocate valid commands into the lowest free slots in command order.

    Allocation uses only fixed-shape prefix ranks.  It neither materializes a
    Python event list nor compacts active rollers dynamically.
    """

    _validate_state(state)
    _validate_commands(state, commands)
    if game_over is None:
        game_over = torch.zeros(
            (state.batch_size,), dtype=torch.bool, device=state.device
        )
    elif (
        tuple(game_over.shape) != (state.batch_size,)
        or game_over.device != state.device
        or game_over.dtype != torch.bool
    ):
        raise ValueError("game_over must be bool [batch] on the rolling device")

    direction_valid = (commands.target_x_units != commands.origin_x_units) | (
        commands.target_y_units != commands.origin_y_units
    )
    no_spawn = commands.impact_spawn_blueprint_id == FAST_ROLLING_NO_SPAWN
    valid_spawn = (
        (commands.impact_spawn_blueprint_id >= 0)
        & (commands.impact_spawn_count > 0)
        & (commands.impact_spawn_deploy_ticks >= 0)
    )
    coherent_spawn = valid_spawn | (
        no_spawn
        & (commands.impact_spawn_count == 0)
        & (commands.impact_spawn_deploy_ticks >= 0)
    )
    valid = (
        direction_valid
        & (commands.owner >= 0)
        & (commands.owner < 2)
        & (commands.source_card_id >= 0)
        & (commands.travel_range_units > 0)
        & (commands.speed_units_per_tick > 0)
        & (commands.half_width_units >= 0)
        & (commands.damage >= 0.0)
        & (commands.tower_damage_multiplier >= 0.0)
        & coherent_spawn
    )
    candidate = commands.ready & valid & ~game_over[:, None]
    free = ~state.active
    command_rank = candidate.to(torch.int64).cumsum(dim=1) - 1
    free_rank = free.to(torch.int64).cumsum(dim=1) - 1
    destination = (
        candidate[:, :, None]
        & free[:, None, :]
        & (command_rank[:, :, None] == free_rank[:, None, :])
    )
    accepted = destination.any(dim=2)
    written = destination.any(dim=1)
    slots = torch.arange(
        state.max_rollers, dtype=torch.int64, device=state.device
    ).view(1, 1, -1)
    slot_sentinel = torch.full_like(slots, state.max_rollers)
    allocated_slot = torch.where(destination, slots, slot_sentinel).amin(dim=2)
    roller_slot = torch.where(accepted, allocated_slot, -1)

    def write(field: torch.Tensor, value: torch.Tensor) -> None:
        selected = torch.where(destination, value[:, :, None], 0).sum(dim=1)
        field.copy_(torch.where(written, selected.to(field.dtype), field))

    write(state.owner, commands.owner)
    write(state.source_card_id, commands.source_card_id)
    write(state.origin_x_units, commands.origin_x_units)
    write(state.origin_y_units, commands.origin_y_units)
    write(state.target_x_units, commands.target_x_units)
    write(state.target_y_units, commands.target_y_units)
    write(state.x_units, commands.origin_x_units)
    write(state.y_units, commands.origin_y_units)
    write(state.travel_range_units, commands.travel_range_units)
    write(state.speed_units_per_tick, commands.speed_units_per_tick)
    write(state.half_width_units, commands.half_width_units)
    write(state.damage, commands.damage)
    write(state.ground_only, commands.ground_only)
    write(state.tower_damage_multiplier, commands.tower_damage_multiplier)
    write(state.radial_push_units, commands.radial_push_units)
    write(state.forward_push_units, commands.forward_push_units)
    write(
        state.impact_spawn_blueprint_id,
        commands.impact_spawn_blueprint_id,
    )
    write(state.impact_spawn_count, commands.impact_spawn_count)
    write(state.impact_spawn_deploy_ticks, commands.impact_spawn_deploy_ticks)
    state.distance_travelled_units.masked_fill_(written, 0)
    state.hit_stable_ids.masked_fill_(written[:, :, None], 0)
    state.active.logical_or_(written)

    return FastRollingAllocationResult(
        accepted=accepted,
        invalid=commands.ready & ~valid,
        capacity_rejected=candidate & ~accepted,
        roller_slot=roller_slot,
    )


def _validate_step_inputs(
    gym: FastGymState,
    rolling: FastRollingSpellState,
    entity_is_air: torch.Tensor,
    entity_collision_radius_units: torch.Tensor,
    entity_is_crown_tower: torch.Tensor,
    entity_area_receivable: torch.Tensor | None,
) -> None:
    _validate_state(rolling)
    if gym.device != rolling.device or gym.batch_size != rolling.batch_size:
        raise ValueError("gym and rolling state must share batch and device")
    entity_shape = (gym.batch_size, gym.max_entities)
    for name, value, dtype in (
        ("entity_is_air", entity_is_air, torch.bool),
        (
            "entity_collision_radius_units",
            entity_collision_radius_units,
            torch.int32,
        ),
        ("entity_is_crown_tower", entity_is_crown_tower, torch.bool),
    ):
        if tuple(value.shape) != entity_shape or value.device != gym.device:
            raise ValueError(f"{name} must match Gym entity shape and device")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")
    if entity_area_receivable is not None and (
        tuple(entity_area_receivable.shape) != entity_shape
        or entity_area_receivable.device != gym.device
        or entity_area_receivable.dtype != torch.bool
    ):
        raise ValueError("entity_area_receivable must be bool with Gym entity shape")


def _clamp_int32(value: torch.Tensor) -> torch.Tensor:
    bounds = torch.iinfo(torch.int32)
    return value.clamp(min=bounds.min, max=bounds.max).to(torch.int32)


def step_fast_rolling_spells_(
    gym: FastGymState,
    rolling: FastRollingSpellState,
    *,
    entity_is_air: torch.Tensor,
    entity_collision_radius_units: torch.Tensor,
    entity_is_crown_tower: torch.Tensor,
    modifiers: FastModifierState | None = None,
    entity_area_receivable: torch.Tensor | None = None,
) -> FastRollingStepResult:
    """Advance one tick, apply once-only damage, and return dense side effects.

    Collision is the capsule swept from the previous center to the new center.
    When several rollers hit together, damage and displacement are summed per
    entity before returning.  HP mutation is grouped once, so physical entity
    slot order cannot affect the result.
    """

    _validate_step_inputs(
        gym,
        rolling,
        entity_is_air,
        entity_collision_radius_units,
        entity_is_crown_tower,
        entity_area_receivable,
    )
    batch = gym.batch_size
    rollers = rolling.max_rollers
    entities = gym.max_entities
    if entity_area_receivable is None:
        entity_area_receivable = gym.active & (gym.hp > 0)

    active = rolling.active
    previous_x = rolling.x_units.clone()
    previous_y = rolling.y_units.clone()
    remaining = (rolling.travel_range_units - rolling.distance_travelled_units).clamp(
        min=0
    )
    travel = torch.minimum(
        rolling.speed_units_per_tick.clamp(min=0),
        remaining,
    )
    moving = active & (travel > 0)
    next_distance = rolling.distance_travelled_units + torch.where(moving, travel, 0)

    direction_x = rolling.target_x_units.to(torch.float32) - rolling.origin_x_units.to(
        torch.float32
    )
    direction_y = rolling.target_y_units.to(torch.float32) - rolling.origin_y_units.to(
        torch.float32
    )
    direction_length = torch.sqrt(direction_x.square() + direction_y.square())
    direction_denominator = direction_length.clamp_min(1.0)
    unit_x = direction_x / direction_denominator
    unit_y = direction_y / direction_denominator
    next_x = rolling.origin_x_units + torch.round(
        unit_x * next_distance.to(torch.float32)
    ).to(torch.int32)
    next_y = rolling.origin_y_units + torch.round(
        unit_y * next_distance.to(torch.float32)
    ).to(torch.int32)
    rolling.x_units.copy_(torch.where(moving, next_x, rolling.x_units))
    rolling.y_units.copy_(torch.where(moving, next_y, rolling.y_units))
    rolling.distance_travelled_units.copy_(next_distance)

    segment_x = rolling.x_units.to(torch.float32) - previous_x.to(torch.float32)
    segment_y = rolling.y_units.to(torch.float32) - previous_y.to(torch.float32)
    segment_length_sq = segment_x.square() + segment_y.square()
    relative_x = gym.x_units[:, None, :].to(torch.float32) - previous_x[:, :, None].to(
        torch.float32
    )
    relative_y = gym.y_units[:, None, :].to(torch.float32) - previous_y[:, :, None].to(
        torch.float32
    )
    projection = (
        relative_x * segment_x[:, :, None] + relative_y * segment_y[:, :, None]
    ) / segment_length_sq.clamp_min(1.0)[:, :, None]
    projection = projection.clamp(min=0.0, max=1.0)
    closest_x = (
        previous_x[:, :, None].to(torch.float32) + projection * segment_x[:, :, None]
    )
    closest_y = (
        previous_y[:, :, None].to(torch.float32) + projection * segment_y[:, :, None]
    )
    radial_x = gym.x_units[:, None, :].to(torch.float32) - closest_x
    radial_y = gym.y_units[:, None, :].to(torch.float32) - closest_y
    distance_sq = radial_x.square() + radial_y.square()
    reach = (
        rolling.half_width_units.clamp(min=0).to(torch.float32)[:, :, None]
        + entity_collision_radius_units.clamp(min=0).to(torch.float32)[:, None, :]
    )

    target_plane = ~rolling.ground_only[:, :, None] | ~entity_is_air[:, None, :]
    eligible = (
        moving[:, :, None]
        & gym.active[:, None, :]
        & (gym.hp[:, None, :] > 0.0)
        & (gym.stable_id[:, None, :] > 0)
        & (gym.owner[:, None, :] != rolling.owner[:, :, None])
        & target_plane
        & entity_area_receivable[:, None, :]
    )
    within_capsule = distance_sq <= reach.square()
    already_hit = (
        (gym.stable_id[:, None, :, None] == rolling.hit_stable_ids[:, :, None, :])
        & (gym.stable_id[:, None, :, None] > 0)
    ).any(dim=3)
    hit_candidate = eligible & within_capsule & ~already_hit

    # Rank this tick's candidates by stable identity, using physical slot only
    # as an impossible-duplicate tie break.  Fixed ledger capacity fails closed
    # instead of admitting an unrecorded hit that could repeat next tick.
    maximum_id = torch.iinfo(torch.int64).max
    candidate_id = torch.where(
        hit_candidate,
        gym.stable_id[:, None, :],
        torch.full(
            (batch, rollers, entities),
            maximum_id,
            dtype=torch.int64,
            device=gym.device,
        ),
    )
    entity_slot = torch.arange(entities, dtype=torch.int64, device=gym.device).view(
        1, 1, entities
    )
    other_before = hit_candidate[:, :, None, :] & (
        (candidate_id[:, :, None, :] < candidate_id[:, :, :, None])
        | (
            (candidate_id[:, :, None, :] == candidate_id[:, :, :, None])
            & (entity_slot[:, :, None, :] < entity_slot[:, :, :, None])
        )
    )
    hit_rank = other_before.sum(dim=3, dtype=torch.int64)
    free_record = rolling.hit_stable_ids == 0
    free_record_rank = free_record.to(torch.int64).cumsum(dim=2) - 1
    free_record_count = free_record.sum(dim=2, dtype=torch.int64)
    hit = hit_candidate & (hit_rank < free_record_count[:, :, None])
    ledger_destination = (
        hit[:, :, :, None]
        & free_record[:, :, None, :]
        & (hit_rank[:, :, :, None] == free_record_rank[:, :, None, :])
    )
    ledger_written = ledger_destination.any(dim=2)
    ledger_value = torch.where(
        ledger_destination,
        gym.stable_id[:, None, :, None],
        0,
    ).sum(dim=2, dtype=torch.int64)
    rolling.hit_stable_ids.copy_(
        torch.where(ledger_written, ledger_value, rolling.hit_stable_ids)
    )

    tower_scale = torch.where(
        entity_is_crown_tower[:, None, :],
        rolling.tower_damage_multiplier.clamp(min=0.0)[:, :, None],
        1.0,
    )
    weighted_damage = (
        hit.to(torch.float32) * rolling.damage.clamp(min=0.0)[:, :, None] * tower_scale
    )
    if modifiers is None:
        damage_by_entity = weighted_damage.sum(dim=1)
    else:
        entity_slot = (
            torch.arange(entities, dtype=torch.int64, device=gym.device)
            .view(1, 1, entities)
            .expand(batch, rollers, entities)
        )
        shield = intercept_fast_shield_hits_(
            modifiers,
            valid=hit.reshape(batch, rollers * entities),
            target_slot=entity_slot.reshape(batch, rollers * entities),
            damage=weighted_damage.reshape(batch, rollers * entities),
        )
        damage_by_entity = shield.hp_damage
    gym.hp.sub_(damage_by_entity).clamp_(min=0.0)

    radial_distance = torch.sqrt(distance_sq)
    radial_denominator = radial_distance.clamp_min(1.0)
    fallback_sign = torch.where(
        torch.bitwise_and(gym.stable_id, 1) == 0,
        torch.ones_like(gym.stable_id),
        -torch.ones_like(gym.stable_id),
    ).to(torch.float32)
    fallback_on_x = (
        torch.bitwise_and(torch.bitwise_right_shift(gym.stable_id, 1), 1) == 0
    )
    fallback_x = torch.where(fallback_on_x, fallback_sign, 0.0)[:, None, :]
    fallback_y = torch.where(fallback_on_x, 0.0, fallback_sign)[:, None, :]
    coincident = radial_distance == 0.0
    radial_unit_x = torch.where(coincident, fallback_x, radial_x / radial_denominator)
    radial_unit_y = torch.where(coincident, fallback_y, radial_y / radial_denominator)
    push_x = (
        radial_unit_x * rolling.radial_push_units.to(torch.float32)[:, :, None]
        + unit_x[:, :, None] * rolling.forward_push_units.to(torch.float32)[:, :, None]
    )
    push_y = (
        radial_unit_y * rolling.radial_push_units.to(torch.float32)[:, :, None]
        + unit_y[:, :, None] * rolling.forward_push_units.to(torch.float32)[:, :, None]
    )
    displacement_hit = (
        hit
        & (gym.kind[:, None, :] == FAST_KIND_TROOP)
        & ~entity_is_crown_tower[:, None, :]
    )
    impulse_dx = _clamp_int32(
        torch.where(displacement_hit, torch.round(push_x).to(torch.int64), 0).sum(
            dim=1, dtype=torch.int64
        )
    )
    impulse_dy = _clamp_int32(
        torch.where(displacement_hit, torch.round(push_y).to(torch.int64), 0).sum(
            dim=1, dtype=torch.int64
        )
    )

    ended = active & (
        (rolling.distance_travelled_units >= rolling.travel_range_units) | ~moving
    )
    spawn_ready = (
        ended
        & (rolling.impact_spawn_blueprint_id >= 0)
        & (rolling.impact_spawn_count > 0)
    )
    spawn = FastRollingSpawnTriggers(
        ready=spawn_ready,
        owner=torch.where(spawn_ready, rolling.owner, 0).to(torch.int8),
        source_card_id=torch.where(spawn_ready, rolling.source_card_id, 0).to(
            torch.int64
        ),
        blueprint_id=torch.where(
            spawn_ready,
            rolling.impact_spawn_blueprint_id,
            FAST_ROLLING_NO_SPAWN,
        ),
        x_units=torch.where(spawn_ready, rolling.x_units, 0).to(torch.int32),
        y_units=torch.where(spawn_ready, rolling.y_units, 0).to(torch.int32),
        count=torch.where(spawn_ready, rolling.impact_spawn_count, 0).to(torch.int32),
        deploy_ticks=torch.where(spawn_ready, rolling.impact_spawn_deploy_ticks, 0).to(
            torch.int32
        ),
    )
    rolling.active.logical_and_(~ended)

    return FastRollingStepResult(
        hit=hit,
        hit_count=hit.sum(dim=2, dtype=torch.int64),
        hit_capacity_rejected=hit_candidate & ~hit,
        damage_by_entity=damage_by_entity,
        impulse_dx_units=impulse_dx,
        impulse_dy_units=impulse_dy,
        impulse_affected=(impulse_dx != 0) | (impulse_dy != 0),
        ended=ended,
        spawn=spawn,
    )
