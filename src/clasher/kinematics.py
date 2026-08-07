"""Conversions for Clash's fixed-point 50 ms movement system."""

from __future__ import annotations

import math


LOGIC_TICK_MILLISECONDS = 50
LOGIC_TICK_SECONDS = LOGIC_TICK_MILLISECONDS / 1000.0
LOGIC_UNITS_PER_TILE = 1000
NATIVE_MOVEMENT_SUBSTEP_UNITS = 250
# Card commands resolve after this native server action window. Serialized
# action-group deadlines are measured from the command, while runtime spell
# entities are created after the window, so both systems share this constant.
SERVER_ACTION_DELAY_SECONDS = 1.0


def logic_time_milliseconds(seconds: float | int) -> int:
    """Quantize accumulated wall time back to the native integer-ms clock."""
    return round(float(seconds) * 1000.0)


def logic_speed_to_tiles_per_second(speed: float | int) -> float:
    """Convert serialized distance-per-logic-tick to arena tiles per second."""
    return (
        float(speed)
        / LOGIC_UNITS_PER_TILE
        / LOGIC_TICK_SECONDS
    )


def tiles_per_second_to_logic_speed(speed: float | int) -> int:
    """Recover serialized per-tick speed from a tiles/second runtime value."""
    return round(
        float(speed) * LOGIC_UNITS_PER_TILE * LOGIC_TICK_SECONDS
    )


def trunc_div(numerator: int, denominator: int) -> int:
    """Divide like the native signed integer arithmetic (towards zero)."""
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    sign = -1 if numerator < 0 else 1
    return sign * (abs(numerator) // denominator)


def tiles_to_logic_units(value: float | int) -> int:
    """Quantize an arena coordinate/distance to integer logic units."""
    return round(float(value) * LOGIC_UNITS_PER_TILE)


def logic_units_to_tiles(value: int) -> float:
    """Convert an integer native coordinate/distance to arena tiles."""
    return int(value) / LOGIC_UNITS_PER_TILE


def speed_work_for_duration(speed: float | int, dt: float) -> int:
    """Return integer movement work for a duration measured in logic ticks.

    Normal battles call this with exactly one 50 ms tick. Supporting integral
    tick multiples keeps direct mechanic tests and accelerated simulation from
    introducing a second, floating-point speed definition.
    """
    tick_count = max(0.0, float(dt)) / LOGIC_TICK_SECONDS
    rounded_tick_count = round(tick_count)
    if abs(tick_count - rounded_tick_count) <= 1e-9:
        return max(0, round(float(speed))) * rounded_tick_count
    return max(0, round(float(speed) * tick_count))


def spawn_path_travel_tick_count(
    distance_units: int,
    speed_units_per_tick: int,
    *,
    reached_radius_from_speed: bool,
) -> int:
    """Return native frames until a straight spawn path reaches its last node.

    Movement budgets above 250 logic units are processed in collision-safe
    substeps.  The reached test runs after every substep; current clients use
    the full serialized spawn-path speed as the radius, while older clients
    used a fixed one-tile radius.  Completion then snaps the character to its
    stored deploy coordinate, so only the frame count is returned here.
    """
    remaining = max(0, int(distance_units))
    speed = max(1, int(speed_units_per_tick))
    reached_radius = speed if reached_radius_from_speed else LOGIC_UNITS_PER_TILE
    ticks = 0
    while remaining > 0:
        ticks += 1
        budget = speed
        while budget > 0:
            substep = min(budget, NATIVE_MOVEMENT_SUBSTEP_UNITS)
            remaining = max(0, remaining - substep)
            if remaining <= reached_radius:
                return ticks
            budget -= substep
    return ticks


def vector_towards_logic_units(
    dx_units: int,
    dy_units: int,
    distance_units: int,
) -> tuple[int, int]:
    """Normalize a displacement using the client's integer movement grid.

    The result never overshoots the destination. Component division truncates
    toward zero, so mirrored negative vectors remain exact rotations of their
    positive counterparts.
    """
    dx_units = int(dx_units)
    dy_units = int(dy_units)
    distance_units = max(0, int(distance_units))
    if distance_units == 0 or (dx_units == 0 and dy_units == 0):
        return (0, 0)

    remaining = max(1, math.isqrt(dx_units * dx_units + dy_units * dy_units))
    if distance_units >= remaining:
        return (dx_units, dy_units)
    return normalized_vector_logic_units(dx_units, dy_units, distance_units)


def movement_component_vector_logic_units(
    dx_units: int,
    dy_units: int,
    movement_units: int,
) -> tuple[int, int]:
    """Scale a LogicMovementComponent target vector through its 8-bit lane.

    ``updateMovementTowards`` first computes ``(delta << 8) / distance`` with
    signed division truncated toward zero. It then multiplies that direction
    by the capped movement work and arithmetic-shifts by eight. This loses a
    unit on many diagonals compared with direct full-precision normalization;
    the loss (including the signed-shift asymmetry) is serialized behavior.
    """

    dx_units = int(dx_units)
    dy_units = int(dy_units)
    movement_units = max(0, int(movement_units))
    if movement_units == 0 or (dx_units == 0 and dy_units == 0):
        return (0, 0)
    remaining_units = max(
        1,
        math.isqrt(dx_units * dx_units + dy_units * dy_units),
    )
    capped_movement = min(movement_units, remaining_units)
    direction_x = trunc_div(dx_units << 8, remaining_units)
    direction_y = trunc_div(dy_units << 8, remaining_units)
    return (
        direction_x * capped_movement >> 8,
        direction_y * capped_movement >> 8,
    )


def normalized_vector_logic_units(
    dx_units: int,
    dy_units: int,
    magnitude_units: int,
) -> tuple[int, int]:
    """Scale a direction to an integer magnitude without endpoint capping."""
    dx_units = int(dx_units)
    dy_units = int(dy_units)
    magnitude_units = max(0, int(magnitude_units))
    if magnitude_units == 0 or (dx_units == 0 and dy_units == 0):
        return (0, 0)
    direction_magnitude = max(
        1,
        math.isqrt(dx_units * dx_units + dy_units * dy_units),
    )
    return (
        trunc_div(dx_units * magnitude_units, direction_magnitude),
        trunc_div(dy_units * magnitude_units, direction_magnitude),
    )
