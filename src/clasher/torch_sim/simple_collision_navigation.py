"""Dense body contact and terrain constraints for the practical tensor Gym.

The production kernel resolves every body from one proposed-position snapshot.
That makes contact independent of physical slot order and avoids the scalar
simulator's per-entity mutation sequence.  Card identity never enters this
module: callers provide serialized radius, mass, and movement-plane tensors.

Hovering bodies deliberately share the air contact plane and ignore the river,
matching the native movement trait.  Their combat target plane is owned by the
targeting kernel and remains ground; this module does not conflate the two.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from .simple_navigation import (
    FAST_ARENA_HEIGHT_UNITS,
    FAST_ARENA_WIDTH_UNITS,
    FAST_BRIDGE_MAX_X_UNITS,
    FAST_BRIDGE_MIN_X_UNITS,
    FAST_LOWER_RIVER_EDGE_UNITS,
    FAST_UPPER_RIVER_EDGE_UNITS,
)
from .simple_state import FAST_KIND_BUILDING, FAST_KIND_TROOP

FAST_MAX_CONTACT_CORRECTION_UNITS = 300


@dataclass(frozen=True)
class FastCollisionNavigationResult:
    """Resolved positions and fixed-shape contact telemetry."""

    x_units: torch.Tensor
    y_units: torch.Tensor
    moved_distance_units: torch.Tensor
    correction_x_units: torch.Tensor
    correction_y_units: torch.Tensor
    contacted: torch.Tensor
    troop_contact_count: torch.Tensor
    building_contact_count: torch.Tensor
    terrain_constrained: torch.Tensor


def _validate_inputs(
    named: tuple[tuple[str, torch.Tensor, torch.dtype], ...],
) -> tuple[torch.Size, torch.device]:
    shape = named[0][1].shape
    device = named[0][1].device
    if len(shape) != 2:
        raise ValueError("collision tensors must have shape [batch, entities]")
    for name, value, dtype in named:
        if value.shape != shape:
            raise ValueError(f"{name} must have shape [batch, entities]")
        if value.device != device:
            raise ValueError(f"{name} must use the collision state device")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")
    if device.type not in {"cpu", "cuda"}:
        raise ValueError("collision navigation supports CPU and CUDA only")
    return shape, device


def _stable_overlap_normal(
    own_id: torch.Tensor,
    other_id: torch.Tensor,
    own_owner: torch.Tensor,
    other_owner: torch.Tensor,
    *,
    dtype: torch.dtype,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Return an antisymmetric deterministic unit vector for exact overlap."""

    low = torch.minimum(own_id, other_id)
    high = torch.maximum(own_id, other_id)
    direction_index = torch.bitwise_and(low * 31 + high * 17, 7)
    one = torch.ones_like(direction_index, dtype=dtype)
    zero = one - one
    diagonal = one * (2.0**-0.5)
    selected_x = torch.where(
        direction_index == 0,
        one,
        torch.where(
            direction_index == 1,
            diagonal,
            torch.where(
                direction_index == 2,
                zero,
                torch.where(
                    direction_index == 3,
                    -diagonal,
                    torch.where(
                        direction_index == 4,
                        -one,
                        torch.where(
                            direction_index == 5,
                            -diagonal,
                            torch.where(direction_index == 6, zero, diagonal),
                        ),
                    ),
                ),
            ),
        ),
    )
    selected_y = torch.where(
        direction_index == 0,
        zero,
        torch.where(
            direction_index == 1,
            diagonal,
            torch.where(
                direction_index == 2,
                one,
                torch.where(
                    direction_index == 3,
                    diagonal,
                    torch.where(
                        direction_index == 4,
                        zero,
                        torch.where(
                            direction_index == 5,
                            -diagonal,
                            torch.where(direction_index == 6, -one, -diagonal),
                        ),
                    ),
                ),
            ),
        ),
    )
    low_owner = torch.where(own_id < other_id, own_owner, other_owner)
    perspective = torch.where(
        low_owner == 0,
        torch.ones_like(selected_x),
        -torch.ones_like(selected_x),
    )
    sign = torch.where(
        own_id < other_id,
        torch.ones_like(selected_x),
        -torch.ones_like(selected_x),
    )
    return selected_x * sign * perspective, selected_y * sign * perspective


def _clamp_vector_length(
    x: torch.Tensor,
    y: torch.Tensor,
    maximum: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    length = torch.sqrt(x.square() + y.square())
    scale = torch.minimum(
        torch.ones_like(length),
        torch.full_like(length, maximum) / length.clamp_min(1.0),
    )
    return x * scale, y * scale


def resolve_fast_collision_navigation(
    *,
    active: torch.Tensor,
    stable_id: torch.Tensor,
    owner: torch.Tensor,
    kind: torch.Tensor,
    x_units: torch.Tensor,
    y_units: torch.Tensor,
    intended_x_units: torch.Tensor,
    intended_y_units: torch.Tensor,
    collision_radius_units: torch.Tensor,
    mass: torch.Tensor,
    airborne: torch.Tensor,
    hover: torch.Tensor,
    movement_enabled: torch.Tensor,
    collision_excluded: torch.Tensor | None = None,
) -> FastCollisionNavigationResult:
    """Resolve one simultaneous movement/contact frame.

    ``intended_*`` are per-tick displacement vectors, not destinations.
    Buildings are immobile; troop pairs share separation inversely by mass.
    Every correction is computed from the same proposed-position snapshot and
    the final correction magnitude is capped at native's 300-logic-unit contact
    pressure.  Ground bodies are constrained to the standard arena and bridge
    openings.  Air and hover bodies ignore ground bodies and river terrain.
    """

    if collision_excluded is None:
        collision_excluded = torch.zeros_like(active)
    shape, _device = _validate_inputs(
        (
            ("active", active, torch.bool),
            ("stable_id", stable_id, torch.int64),
            ("owner", owner, torch.int8),
            ("kind", kind, torch.int8),
            ("x_units", x_units, torch.int32),
            ("y_units", y_units, torch.int32),
            ("intended_x_units", intended_x_units, torch.int32),
            ("intended_y_units", intended_y_units, torch.int32),
            ("collision_radius_units", collision_radius_units, torch.int32),
            ("mass", mass, torch.float32),
            ("airborne", airborne, torch.bool),
            ("hover", hover, torch.bool),
            ("movement_enabled", movement_enabled, torch.bool),
            ("collision_excluded", collision_excluded, torch.bool),
        )
    )
    del shape

    troop = kind == FAST_KIND_TROOP
    building = kind == FAST_KIND_BUILDING
    live_body = (
        active
        & (stable_id > 0)
        & (collision_radius_units > 0)
        & (troop | building)
        & ~collision_excluded
    )
    moving = live_body & troop & movement_enabled
    movable = live_body & troop
    intent_x = torch.where(moving, intended_x_units, 0).to(torch.float32)
    intent_y = torch.where(moving, intended_y_units, 0).to(torch.float32)
    proposed_x = x_units.to(torch.float32) + intent_x
    proposed_y = y_units.to(torch.float32) + intent_y

    # Pair axes are [batch, own, other].  Every own-body correction observes
    # the same proposed snapshot, so physical slot order cannot affect motion.
    delta_x = proposed_x[:, :, None] - proposed_x[:, None, :]
    delta_y = proposed_y[:, :, None] - proposed_y[:, None, :]
    distance_sq = delta_x.square() + delta_y.square()
    distance = torch.sqrt(distance_sq)
    own_id = stable_id[:, :, None]
    other_id = stable_id[:, None, :]
    own_owner = owner[:, :, None]
    other_owner = owner[:, None, :]
    same_body = own_id == other_id
    contact_plane = airborne | hover
    pair = (
        live_body[:, :, None]
        & live_body[:, None, :]
        & ~same_body
        & (contact_plane[:, :, None] == contact_plane[:, None, :])
        & (troop[:, :, None] | troop[:, None, :])
    )
    combined_radius = (
        collision_radius_units[:, :, None].clamp_min(0)
        + collision_radius_units[:, None, :].clamp_min(0)
    ).to(torch.float32)
    overlap = (combined_radius - distance).clamp_min(0.0)
    contact = pair & (overlap > 0.0)

    tie_x, tie_y = _stable_overlap_normal(
        own_id,
        other_id,
        own_owner,
        other_owner,
        dtype=proposed_x.dtype,
    )
    ordinary_x = delta_x / distance.clamp_min(1.0)
    ordinary_y = delta_y / distance.clamp_min(1.0)
    exact_overlap = distance_sq == 0.0
    normal_x = torch.where(exact_overlap, tie_x, ordinary_x)
    normal_y = torch.where(exact_overlap, tie_y, ordinary_y)

    own_mass = mass[:, :, None].clamp_min(0.1)
    other_mass = mass[:, None, :].clamp_min(0.1)
    other_is_building = building[:, None, :]
    separation_share = torch.where(
        other_is_building,
        torch.ones_like(other_mass),
        other_mass / (own_mass + other_mass),
    )
    separation = overlap * separation_share * contact.to(overlap.dtype)

    # Projection alone stalls a unit that walks directly into a building.
    # Replace the lost inward component with deterministic tangential travel.
    # Off-centre approaches keep their geometric side; exact head-on cases use
    # stable IDs, which makes replay and slot reuse deterministic.
    static_contact = contact & other_is_building & troop[:, :, None]
    inward = -(intent_x[:, :, None] * normal_x + intent_y[:, :, None] * normal_y)
    inward = inward.clamp_min(0.0) * static_contact.to(proposed_x.dtype)
    perpendicular_x = -normal_y
    perpendicular_y = normal_x
    tangent_alignment = (
        perpendicular_x * intent_x[:, :, None] + perpendicular_y * intent_y[:, :, None]
    )
    stable_side = torch.where(
        own_id < other_id,
        torch.ones_like(tangent_alignment),
        -torch.ones_like(tangent_alignment),
    )
    tangent_sign = torch.where(
        tangent_alignment > 0,
        torch.ones_like(tangent_alignment),
        torch.where(
            tangent_alignment < 0,
            -torch.ones_like(tangent_alignment),
            stable_side,
        ),
    )

    correction_x = (
        normal_x * separation + perpendicular_x * tangent_sign * inward
    ).sum(dim=2)
    correction_y = (
        normal_y * separation + perpendicular_y * tangent_sign * inward
    ).sum(dim=2)
    correction_x, correction_y = _clamp_vector_length(
        correction_x,
        correction_y,
        float(FAST_MAX_CONTACT_CORRECTION_UNITS),
    )
    correction_x = torch.where(movable, correction_x, 0.0)
    correction_y = torch.where(movable, correction_y, 0.0)

    resolved_x = torch.round(proposed_x + correction_x).to(torch.int32)
    resolved_y = torch.round(proposed_y + correction_y).to(torch.int32)
    changed = movable & (
        (intended_x_units != 0)
        | (intended_y_units != 0)
        | (torch.round(correction_x).to(torch.int32) != 0)
        | (torch.round(correction_y).to(torch.int32) != 0)
    )

    radius = collision_radius_units.clamp_min(0)
    max_radius = min(FAST_ARENA_WIDTH_UNITS, FAST_ARENA_HEIGHT_UNITS) // 2
    bound_radius = radius.clamp(max=max_radius)
    arena_x = resolved_x.clamp(
        min=bound_radius,
        max=FAST_ARENA_WIDTH_UNITS - bound_radius,
    )
    arena_y = resolved_y.clamp(
        min=bound_radius,
        max=FAST_ARENA_HEIGHT_UNITS - bound_radius,
    )
    arena_constrained = changed & ((arena_x != resolved_x) | (arena_y != resolved_y))
    resolved_x = torch.where(changed, arena_x, resolved_x)
    resolved_y = torch.where(changed, arena_y, resolved_y)

    # A ground circle may enter the river only while its complete body fits a
    # bridge opening. Hover and air movement bypass this terrain gate.
    ground_surface = live_body & ~(airborne | hover)
    overlaps_river = (resolved_y + radius > FAST_LOWER_RIVER_EDGE_UNITS) & (
        resolved_y - radius < FAST_UPPER_RIVER_EDGE_UNITS
    )
    left_min = FAST_BRIDGE_MIN_X_UNITS[0] + radius
    left_max = FAST_BRIDGE_MAX_X_UNITS[0] - radius
    right_min = FAST_BRIDGE_MIN_X_UNITS[1] + radius
    right_max = FAST_BRIDGE_MAX_X_UNITS[1] - radius
    left_fits = (
        (left_min <= left_max) & (resolved_x >= left_min) & (resolved_x <= left_max)
    )
    right_fits = (
        (right_min <= right_max) & (resolved_x >= right_min) & (resolved_x <= right_max)
    )
    invalid_river = (
        changed & ground_surface & overlaps_river & ~(left_fits | right_fits)
    )

    current_left_fits = (
        (left_min <= left_max) & (x_units >= left_min) & (x_units <= left_max)
    )
    current_right_fits = (
        (right_min <= right_max) & (x_units >= right_min) & (x_units <= right_max)
    )
    current_bridge = current_left_fits | current_right_fits
    left_projection = resolved_x.clamp(min=left_min, max=left_max)
    right_projection = resolved_x.clamp(min=right_min, max=right_max)
    projected_bridge_x = torch.where(
        (resolved_x - left_projection).abs() <= (resolved_x - right_projection).abs(),
        left_projection,
        right_projection,
    )
    # A body already crossing a bridge can be pushed only to the bridge edge.
    # An illegally placed body cannot teleport sideways; retain its X and put
    # it back on the owner-independent nearest bank instead.
    bridge_repair = invalid_river & current_bridge
    bank_repair = invalid_river & ~current_bridge
    resolved_x = torch.where(bridge_repair, projected_bridge_x, resolved_x)
    river_center = (FAST_LOWER_RIVER_EDGE_UNITS + FAST_UPPER_RIVER_EDGE_UNITS) // 2
    lower_bank = torch.full_like(resolved_y, FAST_LOWER_RIVER_EDGE_UNITS) - radius
    upper_bank = torch.full_like(resolved_y, FAST_UPPER_RIVER_EDGE_UNITS) + radius
    nearest_bank = torch.where(y_units <= river_center, lower_bank, upper_bank)
    resolved_y = torch.where(bank_repair, nearest_bank, resolved_y)

    actual_dx = resolved_x - x_units
    actual_dy = resolved_y - y_units
    moved_distance = torch.where(
        changed,
        torch.round(
            torch.sqrt(
                actual_dx.to(torch.float32).square()
                + actual_dy.to(torch.float32).square()
            )
        ).to(torch.int32),
        0,
    )
    troop_contact = contact & troop[:, None, :]
    building_contact = contact & building[:, None, :]
    contacted = contact.any(dim=2) & live_body
    return FastCollisionNavigationResult(
        x_units=torch.where(changed, resolved_x, x_units),
        y_units=torch.where(changed, resolved_y, y_units),
        moved_distance_units=moved_distance,
        correction_x_units=torch.round(correction_x).to(torch.int32),
        correction_y_units=torch.round(correction_y).to(torch.int32),
        contacted=contacted,
        troop_contact_count=troop_contact.sum(dim=2).to(torch.int16),
        building_contact_count=building_contact.sum(dim=2).to(torch.int16),
        terrain_constrained=arena_constrained | invalid_river,
    )
