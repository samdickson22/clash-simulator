"""Batched fixed-point movement kernels for the PyTorch simulator.

The Python oracle stores positions as floats but quantizes every movement
component onto the native 1/1000-tile grid.  These kernels keep that grid in
``int64`` tensors throughout.  Route generation is deliberately outside this
module: natural movement is supported only when a current native route
waypoint has already been compiled into a tensor.  This makes unsupported
path states explicit instead of silently substituting straight-line movement.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

LOGIC_UNITS_PER_TILE = 1000
OUTERMOST_OBJECT_CENTER_UNITS = 250
DEFAULT_ARENA_WIDTH_UNITS = 18_000
DEFAULT_ARENA_HEIGHT_UNITS = 32_000
NATIVE_COLLISION_CAP_UNITS = 300
PENDING_MOVEMENT_CAP_UNITS = 150
ROUTE_REACHED_PROJECTION_UNITS = 1001


def _as_int64(value: torch.Tensor) -> torch.Tensor:
    return value if value.dtype == torch.int64 else value.to(dtype=torch.int64)


def trunc_div_tensor(
    numerator: torch.Tensor,
    denominator: torch.Tensor | int,
) -> torch.Tensor:
    """Signed integer division truncated toward zero, matching the oracle."""

    numerator = _as_int64(numerator)
    denominator_tensor = torch.as_tensor(
        denominator,
        dtype=torch.int64,
        device=numerator.device,
    )
    if bool(torch.any(denominator_tensor <= 0)):
        raise ValueError("denominator must be positive")
    return torch.where(
        numerator < 0,
        -torch.div(-numerator, denominator_tensor, rounding_mode="floor"),
        torch.div(numerator, denominator_tensor, rounding_mode="floor"),
    )


def integer_sqrt_tensor(value: torch.Tensor) -> torch.Tensor:
    """Vectorized exact integer square root for native-coordinate magnitudes."""

    value = _as_int64(value)
    if bool(torch.any(value < 0)):
        raise ValueError("integer square root requires non-negative values")
    # Restoring square root uses only int64 operations, including on MPS where
    # float64 is unavailable. The loop count is a compile-time constant, not
    # an entity loop; every tensor lane advances together.
    remainder = value.clone()
    result = torch.zeros_like(value)
    bit = 1 << 62  # Highest power of four representable in signed int64.
    for _ in range(32):
        trial = result + bit
        accepted = remainder >= trial
        remainder = torch.where(accepted, remainder - trial, remainder)
        result = torch.where(
            accepted,
            torch.bitwise_right_shift(result, 1) + bit,
            torch.bitwise_right_shift(result, 1),
        )
        bit >>= 2
    return result


def normalized_vector_units(
    delta_units: torch.Tensor,
    magnitude_units: torch.Tensor | int,
) -> torch.Tensor:
    """Scale ``[..., 2]`` integer directions without endpoint capping."""

    delta_units = _as_int64(delta_units)
    magnitude = torch.as_tensor(
        magnitude_units,
        dtype=torch.int64,
        device=delta_units.device,
    )
    magnitude = torch.clamp(magnitude, min=0)
    distance = integer_sqrt_tensor(torch.sum(delta_units * delta_units, dim=-1))
    safe_distance = torch.clamp(distance, min=1)
    result = trunc_div_tensor(
        delta_units * magnitude.unsqueeze(-1), safe_distance.unsqueeze(-1)
    )
    return torch.where(
        ((distance > 0) & (magnitude > 0)).unsqueeze(-1),
        result,
        torch.zeros_like(result),
    )


def movement_component_vector_units(
    delta_units: torch.Tensor,
    movement_units: torch.Tensor | int,
) -> torch.Tensor:
    """Port the native movement component's signed 8-bit direction lane."""

    delta_units = _as_int64(delta_units)
    movement = torch.as_tensor(
        movement_units,
        dtype=torch.int64,
        device=delta_units.device,
    )
    movement = torch.clamp(movement, min=0)
    remaining = integer_sqrt_tensor(torch.sum(delta_units * delta_units, dim=-1))
    capped = torch.minimum(movement, remaining)
    safe_remaining = torch.clamp(remaining, min=1)
    direction = trunc_div_tensor(delta_units << 8, safe_remaining.unsqueeze(-1))
    result = torch.bitwise_right_shift(direction * capped.unsqueeze(-1), 8)
    return torch.where(
        ((remaining > 0) & (capped > 0)).unsqueeze(-1),
        result,
        torch.zeros_like(result),
    )


def apply_native_avoidance(
    movement_units: torch.Tensor,
    intended_magnitude_units: torch.Tensor,
    avoidance: torch.Tensor,
) -> torch.Tensor:
    """Apply the client's signed 8-bit avoidance rotation and renormalize."""

    movement_units = _as_int64(movement_units)
    avoidance = torch.clamp(_as_int64(avoidance), min=-256, max=256)
    retained = 256 - torch.abs(avoidance)
    x = movement_units[..., 0]
    y = movement_units[..., 1]
    rotated_x = torch.bitwise_right_shift(retained * x, 8) + torch.bitwise_right_shift(
        avoidance * y, 8
    )
    rotated_y = torch.bitwise_right_shift(retained * y, 8) + torch.bitwise_right_shift(
        -x * avoidance, 8
    )
    rotated = torch.stack((rotated_x, rotated_y), dim=-1)
    normalized = normalized_vector_units(rotated, intended_magnitude_units)
    return torch.where((avoidance != 0).unsqueeze(-1), normalized, movement_units)


def clamp_native_positions(
    position_units: torch.Tensor,
    *,
    arena_width_units: int = DEFAULT_ARENA_WIDTH_UNITS,
    arena_height_units: int = DEFAULT_ARENA_HEIGHT_UNITS,
) -> torch.Tensor:
    """Clip object centers to the native outer half-cell midpoint."""

    position_units = _as_int64(position_units)
    lower = torch.tensor(
        (OUTERMOST_OBJECT_CENTER_UNITS, OUTERMOST_OBJECT_CENTER_UNITS),
        dtype=torch.int64,
        device=position_units.device,
    )
    upper = torch.tensor(
        (
            arena_width_units - OUTERMOST_OBJECT_CENTER_UNITS,
            arena_height_units - OUTERMOST_OBJECT_CENTER_UNITS,
        ),
        dtype=torch.int64,
        device=position_units.device,
    )
    return torch.maximum(lower, torch.minimum(upper, position_units))


@dataclass(frozen=True)
class NaturalMovementResult:
    position_units: torch.Tensor
    movement_vector_units: torch.Tensor
    intended_movement_units: torch.Tensor
    supported: torch.Tensor


def natural_movement_support_mask(
    *,
    active: torch.Tensor,
    target_valid: torch.Tensor,
    waypoint_valid: torch.Tensor,
    deployed: torch.Tensor,
    stunned: torch.Tensor,
    forced_movement: torch.Tensor,
    special_movement: torch.Tensor,
    death_spawn_travel: torch.Tensor,
    river_jump_active: torch.Tensor,
) -> torch.Tensor:
    """Gate the straight waypoint kernel from states owned by other phases."""

    return (
        active
        & target_valid
        & waypoint_valid
        & deployed
        & ~stunned
        & ~forced_movement
        & ~special_movement
        & ~death_spawn_travel
        & ~river_jump_active
    )


def target_directed_movement_step(
    position_units: torch.Tensor,
    waypoint_units: torch.Tensor,
    movement_work_units: torch.Tensor,
    *,
    supported: torch.Tensor,
    external_vector_units: torch.Tensor | None = None,
    avoidance: torch.Tensor | None = None,
    arena_width_units: int = DEFAULT_ARENA_WIDTH_UNITS,
    arena_height_units: int = DEFAULT_ARENA_HEIGHT_UNITS,
) -> NaturalMovementResult:
    """Advance one ordinary movement component frame toward route waypoints.

    ``waypoint_units`` must be the already selected native path node.  Callers
    must pass the result of :func:`natural_movement_support_mask`; unsupported
    slots retain their positions exactly.
    """

    position_units = _as_int64(position_units)
    waypoint_units = _as_int64(waypoint_units)
    movement_work_units = torch.clamp(_as_int64(movement_work_units), min=0)
    external = (
        torch.zeros_like(position_units)
        if external_vector_units is None
        else _as_int64(external_vector_units)
    )
    avoidance_tensor = (
        torch.zeros_like(movement_work_units)
        if avoidance is None
        else _as_int64(avoidance)
    )
    support = supported.to(dtype=torch.bool)
    delta = waypoint_units - position_units
    remaining = integer_sqrt_tensor(torch.sum(delta * delta, dim=-1))
    intended = torch.minimum(movement_work_units, remaining)
    movement = movement_component_vector_units(delta, intended)
    movement = apply_native_avoidance(movement, intended, avoidance_tensor)
    candidate = clamp_native_positions(
        position_units + movement + external,
        arena_width_units=arena_width_units,
        arena_height_units=arena_height_units,
    )
    next_position = torch.where(support.unsqueeze(-1), candidate, position_units)
    return NaturalMovementResult(
        position_units=next_position,
        movement_vector_units=torch.where(
            support.unsqueeze(-1), movement, torch.zeros_like(movement)
        ),
        intended_movement_units=torch.where(
            support, intended, torch.zeros_like(intended)
        ),
        supported=support,
    )


def advance_route_node_mask(
    position_units: torch.Tensor,
    previous_position_units: torch.Tensor,
    waypoint_units: torch.Tensor,
    *,
    route_head_matches: torch.Tensor,
) -> torch.Tensor:
    """Return slots whose retained route should pop exactly one head node."""

    direction = normalized_vector_units(waypoint_units - previous_position_units, 256)
    remaining = waypoint_units - position_units
    projected = trunc_div_tensor(
        direction[..., 1] * remaining[..., 1], 256
    ) + trunc_div_tensor(direction[..., 0] * remaining[..., 0], 256)
    return route_head_matches & (projected < ROUTE_REACHED_PROJECTION_UNITS)


_BLOCKED_TILE_INDICES = (
    14 * 18,
    17 * 18,
    14 * 18 + 17,
    17 * 18 + 17,
    *(range(6)),
    *(range(12, 18)),
    *(31 * 18 + value for value in range(6)),
    *(31 * 18 + value for value in range(12, 18)),
)


def ground_walkable_mask(
    position_units: torch.Tensor,
    *,
    arena_width_tiles: int = 18,
    arena_height_tiles: int = 32,
) -> torch.Tensor:
    """Tensor form of the standard arena's exact continuous walkability test."""

    if arena_width_tiles != 18 or arena_height_tiles != 32:
        raise ValueError("only the serialized standard 18x32 arena is supported")
    position_units = _as_int64(position_units)
    x = position_units[..., 0]
    y = position_units[..., 1]
    valid = (
        (x >= 0)
        & (x < arena_width_tiles * LOGIC_UNITS_PER_TILE)
        & (y >= 0)
        & (y < arena_height_tiles * LOGIC_UNITS_PER_TILE)
    )
    tile_x = torch.div(x, LOGIC_UNITS_PER_TILE, rounding_mode="floor")
    tile_y = torch.div(y, LOGIC_UNITS_PER_TILE, rounding_mode="floor")
    previous_x = torch.where(x % LOGIC_UNITS_PER_TILE == 0, tile_x - 1, tile_x)
    previous_y = torch.where(y % LOGIC_UNITS_PER_TILE == 0, tile_y - 1, tile_y)
    touching_x = torch.stack((tile_x, previous_x), dim=-1)
    touching_y = torch.stack((tile_y, previous_y), dim=-1)
    cell_x = touching_x.unsqueeze(-1).expand(*touching_x.shape, 2)
    cell_y = touching_y.unsqueeze(-2).expand(*touching_y.shape[:-1], 2, 2)
    cells_valid = (
        (cell_x >= 0)
        & (cell_x < arena_width_tiles)
        & (cell_y >= 0)
        & (cell_y < arena_height_tiles)
    )
    cell_index = cell_y * arena_width_tiles + cell_x
    blocked_indices = torch.tensor(
        _BLOCKED_TILE_INDICES,
        dtype=torch.int64,
        device=position_units.device,
    )
    blocked = torch.any(
        cells_valid.unsqueeze(-1) & (cell_index.unsqueeze(-1) == blocked_indices),
        dim=(-3, -2, -1),
    )
    in_river = (y >= 15_000) & (y <= 17_000)
    on_bridge = ((x >= 2_000) & (x <= 5_000)) | ((x >= 13_000) & (x <= 16_000))
    return valid & ~blocked & (~in_river | on_bridge)


def river_boundary_crossing_mask(
    origin_units: torch.Tensor,
    endpoint_units: torch.Tensor,
) -> torch.Tensor:
    """Endpoint-first detection used before attempting a data-driven jump."""

    endpoint_walkable = ground_walkable_mask(endpoint_units)
    return ~endpoint_walkable & ground_walkable_mask(origin_units)


def river_jump_start_mask(
    blocked_endpoint_units: torch.Tensor,
    *,
    jump_height: torch.Tensor,
    jump_speed_units: torch.Tensor,
    landing_valid: torch.Tensor,
) -> torch.Tensor:
    """Gate entry to river state 6 after pathfinding supplied a landing node."""

    y = _as_int64(blocked_endpoint_units)[..., 1]
    return (
        jump_height.to(dtype=torch.bool)
        & (_as_int64(jump_speed_units) > 0)
        & landing_valid.to(dtype=torch.bool)
        & (y >= 15_000)
        & (y <= 17_000)
    )


@dataclass(frozen=True)
class RiverJumpResult:
    position_units: torch.Tensor
    active: torch.Tensor
    finished: torch.Tensor
    supported: torch.Tensor


def river_jump_step(
    position_units: torch.Tensor,
    target_units: torch.Tensor,
    jump_speed_units: torch.Tensor,
    *,
    active: torch.Tensor,
    avoidance: torch.Tensor | None = None,
    tick_count: int = 1,
) -> RiverJumpResult:
    """Advance active native river-jump state by integral 50 ms frames."""

    if tick_count < 0:
        raise ValueError("tick_count must be non-negative")
    position_units = _as_int64(position_units)
    target_units = _as_int64(target_units)
    speed = _as_int64(jump_speed_units)
    active = active.to(dtype=torch.bool)
    support = active & (speed > 0)
    work = torch.clamp(speed, min=0) * int(tick_count)
    delta = target_units - position_units
    remaining = integer_sqrt_tensor(torch.sum(delta * delta, dim=-1))
    movement = movement_component_vector_units(delta, work)
    if avoidance is not None:
        movement = apply_native_avoidance(
            movement,
            torch.minimum(work, remaining),
            _as_int64(avoidance),
        )
    candidate = position_units + movement
    finished = support & (remaining <= work)
    candidate = torch.where(finished.unsqueeze(-1), target_units, candidate)
    next_position = torch.where(support.unsqueeze(-1), candidate, position_units)
    return RiverJumpResult(
        position_units=next_position,
        active=active & ~finished,
        finished=finished,
        supported=support,
    )


@dataclass(frozen=True)
class CollisionBatch:
    """Entity traits needed by the body-pressure phase.

    Shapes are ``[batch, entity]`` except ``position_units``, whose final
    dimension is ``(x, y)``. Active slots must be in increasing entity-ID
    order, the same order used by the Python battle dictionary.
    """

    position_units: torch.Tensor
    active: torch.Tensor
    entity_id: torch.Tensor
    entity_kind: torch.Tensor
    player_id: torch.Tensor
    collision_radius_units: torch.Tensor
    mass_milliunits: torch.Tensor
    air_collision: torch.Tensor
    stunned: torch.Tensor
    in_transit: torch.Tensor
    river_jump_active: torch.Tensor
    death_spawn_travel: torch.Tensor
    mega_knight_airborne: torch.Tensor


@dataclass(frozen=True)
class CollisionResult:
    accumulated_vector_units: torch.Tensor
    contact_count: torch.Tensor
    supported_batch: torch.Tensor


def stable_entity_order_mask(
    active: torch.Tensor, entity_id: torch.Tensor
) -> torch.Tensor:
    """Verify active slots preserve the oracle's increasing entity-ID order."""

    sentinel = torch.iinfo(torch.int64).max
    ordered_ids = torch.where(active, _as_int64(entity_id), sentinel)
    active_count = active.sum(dim=-1)
    sorted_ids = torch.sort(ordered_ids, dim=-1, stable=True).values
    same_prefix = torch.all(ordered_ids == sorted_ids, dim=-1)
    unique = torch.ones_like(active_count, dtype=torch.bool)
    if entity_id.shape[-1] > 1:
        pairs_active = active[..., 1:] & active[..., :-1]
        unique = torch.all(
            ~pairs_active | (entity_id[..., 1:] > entity_id[..., :-1]), dim=-1
        )
    return same_prefix & unique & (active_count >= 0)


def _collision_pair_vector(
    dx: torch.Tensor,
    dy: torch.Tensor,
    collision_distance: torch.Tensor,
    other_mass_milliunits: torch.Tensor,
    own_mass_milliunits: torch.Tensor,
    own_player: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    distance_squared = dx * dx + dy * dy
    collides = (
        (torch.abs(dx) <= collision_distance)
        & (torch.abs(dy) <= collision_distance)
        & (distance_squared <= collision_distance * collision_distance)
    )
    coincident = distance_squared == 0
    adjusted_dy = torch.where(coincident, torch.where(own_player == 0, 1, -1), dy)
    distance = torch.where(
        coincident,
        torch.ones_like(distance_squared),
        torch.clamp(integer_sqrt_tensor(distance_squared), min=1),
    )
    overlap = torch.clamp(
        collision_distance - distance, min=0, max=NATIVE_COLLISION_CAP_UNITS
    )
    own_mass_whole = torch.div(own_mass_milliunits, 1000, rounding_mode="floor")
    own_mass_remainder = own_mass_milliunits % 1000
    own_mass_units = own_mass_whole + (
        (own_mass_remainder > 500)
        | ((own_mass_remainder == 500) & (own_mass_whole % 2 == 1))
    ).to(torch.int64)
    own_mass_units = torch.clamp(own_mass_units, min=1)
    magnitude = (
        torch.div(
            overlap * other_mass_milliunits,
            own_mass_units * 1000,
            rounding_mode="floor",
        )
        + 1
    )
    magnitude = torch.clamp(magnitude, max=NATIVE_COLLISION_CAP_UNITS)
    vector_x = trunc_div_tensor(dx * magnitude, distance)
    vector_y = trunc_div_tensor(adjusted_dy * magnitude, distance)
    vector = torch.stack((vector_x, vector_y), dim=-1)
    return vector, collides, distance_squared


def accumulate_collision_vectors(batch: CollisionBatch) -> CollisionResult:
    """Accumulate exact troop/troop and ground troop/building pressure."""

    position = _as_int64(batch.position_units)
    active = batch.active.to(dtype=torch.bool)
    kind = _as_int64(batch.entity_kind)
    radius = torch.clamp(_as_int64(batch.collision_radius_units), min=0)
    mass_milliunits = _as_int64(batch.mass_milliunits)
    air = batch.air_collision.to(dtype=torch.bool)

    own_position = position.unsqueeze(-2)
    other_position = position.unsqueeze(-3)
    delta = own_position - other_position
    dx = delta[..., 0]
    dy = delta[..., 1]
    own_active = active.unsqueeze(-1)
    other_active = active.unsqueeze(-2)
    own_kind = kind.unsqueeze(-1)
    other_kind = kind.unsqueeze(-2)
    own_air = air.unsqueeze(-1)
    other_air = air.unsqueeze(-2)
    own_radius = torch.clamp(radius.unsqueeze(-1), min=200)
    other_radius = torch.clamp(radius.unsqueeze(-2), min=200)
    own_mass = torch.clamp(mass_milliunits.unsqueeze(-1), min=1)
    other_mass = torch.clamp(mass_milliunits.unsqueeze(-2), min=1)
    own_player = _as_int64(batch.player_id).unsqueeze(-1)

    mover_eligible = (
        own_active
        & (own_kind == 0)
        & (
            ~batch.stunned.unsqueeze(-1)
            | batch.river_jump_active.unsqueeze(-1)
            | batch.death_spawn_travel.unsqueeze(-1)
        )
        & (
            ~batch.in_transit.unsqueeze(-1)
            | batch.river_jump_active.unsqueeze(-1)
            | batch.mega_knight_airborne.unsqueeze(-1)
        )
    )
    other_troop_eligible = (
        other_active
        & (other_kind == 0)
        & (
            ~batch.in_transit.unsqueeze(-2)
            | batch.river_jump_active.unsqueeze(-2)
            | batch.mega_knight_airborne.unsqueeze(-2)
        )
        & (own_air == other_air)
    )
    not_self = ~torch.eye(
        position.shape[-2], dtype=torch.bool, device=position.device
    ).unsqueeze(0)
    troop_vector, troop_contact, _ = _collision_pair_vector(
        dx,
        dy,
        own_radius + other_radius,
        other_mass,
        own_mass,
        own_player,
    )
    troop_contact &= mover_eligible & other_troop_eligible & not_self

    building_radius = torch.clamp(radius.unsqueeze(-2), min=0)
    static_distance = (
        torch.minimum(own_radius, torch.tensor(500, device=position.device))
        + building_radius
    )
    building_vector, building_contact, _ = _collision_pair_vector(
        dx,
        dy,
        static_distance,
        torch.full_like(other_mass, 20_000),
        own_mass,
        own_player,
    )
    building_contact &= (
        mover_eligible & ~own_air & other_active & (other_kind == 1) & not_self
    )

    all_vector = torch.where(
        troop_contact.unsqueeze(-1), troop_vector, 0
    ) + torch.where(building_contact.unsqueeze(-1), building_vector, 0)
    contacts = troop_contact.to(torch.int64) + building_contact.to(torch.int64)
    supported = stable_entity_order_mask(active, batch.entity_id) & torch.all(
        (~active) | (mass_milliunits > 0), dim=-1
    )
    return CollisionResult(
        accumulated_vector_units=torch.sum(all_vector, dim=-2),
        contact_count=torch.sum(contacts, dim=-1),
        supported_batch=supported,
    )


def consume_accumulated_movement(
    accumulated_vector_units: torch.Tensor,
    contact_count: torch.Tensor,
    *,
    bypasses_cap: torch.Tensor | None = None,
) -> torch.Tensor:
    """Average collision contacts and apply the native 0.15-tile cap."""

    accumulated = _as_int64(accumulated_vector_units)
    count = _as_int64(contact_count)
    safe_count = torch.clamp(count, min=1)
    averaged = trunc_div_tensor(accumulated, safe_count.unsqueeze(-1))
    magnitude_squared = torch.sum(averaged * averaged, dim=-1)
    cap = magnitude_squared >= PENDING_MOVEMENT_CAP_UNITS**2 + 1
    if bypasses_cap is not None:
        cap &= ~bypasses_cap.to(dtype=torch.bool)
    capped = normalized_vector_units(averaged, PENDING_MOVEMENT_CAP_UNITS)
    result = torch.where(cap.unsqueeze(-1), capped, averaged)
    return torch.where((count > 0).unsqueeze(-1), result, torch.zeros_like(result))
