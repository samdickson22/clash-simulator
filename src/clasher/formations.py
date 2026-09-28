"""Native deterministic character-spawn formation geometry."""

from __future__ import annotations

from .balance import LOGIC_LANE_ID_BASED_DEPLOY_SEQUENCE
from .kinematics import logic_units_to_tiles, tiles_to_logic_units, trunc_div
from .logic_math import logic_cos, logic_sin, logic_vector_angle


def formation_offset(
    index: int,
    count: int,
    radius: float,
    player_id: int,
    angle_shift_degrees: float = 0.0,
    *,
    secondary_count: int = 0,
    width: float = 0.0,
    reverse_x: bool = False,
    lane_id: int = 0,
) -> tuple[float, float]:
    """Return the offset produced by the native ``getSpawnOffset`` routine.

    ``count`` is the number of primary characters. A mixed card supplies
    ``secondary_count`` and native reserves two arcs of
    ``2 * max(count, secondary_count)`` slots. ``radius`` is the serialized
    SummonRadius/SpawnRadius (or the primary character collision radius);
    for non-wide formations native converts it to the appropriate ring
    radius. ``angle_shift_degrees`` rotates the whole layout—it is not the
    angle between adjacent characters.
    """
    secondary_count = int(secondary_count)
    count = int(count)
    total_characters = count + secondary_count
    if count <= 0 or secondary_count < 0:
        raise ValueError("formation counts must be non-negative with a primary unit")
    if index < 0 or index >= total_characters:
        raise ValueError("formation index must be within the character count")

    slot_count = (
        2 * max(count, secondary_count)
        if secondary_count > 0
        else total_characters
    )
    if slot_count == 1:
        return 0.0, 0.0

    radius_units = tiles_to_logic_units(radius)
    width_units = tiles_to_logic_units(width)
    angle_shift = int(angle_shift_degrees)
    native_index = int(index)
    base_angle = 0
    lane_flip_x = (
        LOGIC_LANE_ID_BASED_DEPLOY_SEQUENCE
        and (
            (int(lane_id) == 1 and slot_count in {2, 3})
            or (int(lane_id) == 2 and slot_count == 4)
        )
    )

    if slot_count == 2:
        base_angle = 90
    elif slot_count == 3:
        base_angle = 180
    elif slot_count == 4:
        base_angle = 45
    elif slot_count == 5:
        base_angle = 180
    elif slot_count == 7:
        if native_index == 0:
            return 0.0, 0.0
        native_index -= 1
        slot_count = 6

    if width_units == 0 and slot_count > 2:
        denominator = logic_sin(trunc_div(90, count), 1000)
        if denominator == 0:
            raise ValueError("native formation radius is undefined for this count")
        radius_units = trunc_div(radius_units * 577, denominator)

    base_angle += angle_shift
    if slot_count > 6:
        radius_units = trunc_div(
            radius_units * ((native_index * 3) % 7),
            6,
        )

    if secondary_count == 0:
        angle = (
            base_angle
            + 90
            + trunc_div(native_index * 360, slot_count)
        )
        x_units = logic_cos(angle, radius_units)
        y_units = logic_sin(angle, radius_units)
    else:
        half_slot_angle = trunc_div(trunc_div(360, slot_count), 2)
        primary_arc_offset = half_slot_angle
        secondary_arc_offset = half_slot_angle
        if count < secondary_count:
            primary_arc_offset += trunc_div(trunc_div(180, secondary_count), 2)
        elif secondary_count < count:
            secondary_arc_offset += trunc_div(trunc_div(180, count), 2)

        if count == 1:
            base_angle = 0
        if secondary_count < count and secondary_count == 1:
            base_angle = 0
            if native_index < count:
                angle = (
                    trunc_div(90, count)
                    + base_angle
                    + trunc_div(native_index * 360, slot_count)
                )
            else:
                angle = (
                    trunc_div((native_index - count) * 360, slot_count)
                    + 180
                    + secondary_arc_offset
                    + base_angle
                )
        elif native_index < count:
            angle = (
                primary_arc_offset
                + base_angle
                + trunc_div(native_index * 360, slot_count)
            )
        else:
            angle = (
                trunc_div((native_index - count) * 360, slot_count)
                + 180
                + secondary_arc_offset
                + base_angle
            )
        x_units = logic_cos(angle, radius_units)
        y_units = -logic_sin(angle, radius_units)

    if width_units != 0:
        x_units = (
            trunc_div(width_units * native_index, slot_count - 1)
            - trunc_div(width_units, 2)
        )
        y_units = (
            (native_index % 2) * radius_units
            - trunc_div(radius_units, 2)
        )

    if lane_flip_x or reverse_x:
        x_units = -x_units
    # Standard arena ownership reflects only the forward axis. It never
    # reverses left/right spawn order.
    if player_id == 0:
        y_units = -y_units
    return logic_units_to_tiles(x_units), logic_units_to_tiles(y_units)


def mixed_ring_offset(
    index: int,
    front_count: int,
    back_count: int,
    radius: float,
    player_id: int,
    angle_shift_degrees: float = 0.0,
    *,
    lane_id: int = 0,
) -> tuple[float, float]:
    """Compatibility wrapper for native mixed primary/secondary formations."""
    return formation_offset(
        index,
        front_count,
        radius,
        player_id,
        angle_shift_degrees,
        secondary_count=back_count,
        lane_id=lane_id,
    )


def horizontal_line_offset(
    index: int,
    count: int,
    width: float,
    radius: float,
    player_id: int = 0,
    *,
    lane_id: int = 0,
) -> tuple[float, float]:
    """Compatibility wrapper for a native wide, alternating-row formation."""
    return formation_offset(
        index,
        count,
        radius,
        player_id,
        width=width,
        lane_id=lane_id,
    )


def native_radial_spawn_offset(
    index: int,
    count: int,
    radius: float,
    angle_shift_degrees: float = 0.0,
    *,
    facing_x_units: int = 0,
    facing_y_units: int = 0,
    flip_x: bool = False,
    flip_y: bool = False,
) -> tuple[float, float]:
    """Return the fixed-point offset for nonzero Spawn/DeathSpawnRadius.

    Character child waves enumerate the ring from the last slot downward.
    A nonzero SpawnAngleShift is relative to the parent's current direction;
    when it is zero, native deliberately uses a world-fixed zero base angle.
    """
    if count <= 0 or index < 0 or index >= count:
        raise ValueError("radial spawn index must be within a positive count")
    radius_units = tiles_to_logic_units(radius)
    angle_shift = int(angle_shift_degrees)
    base_angle = (
        logic_vector_angle(facing_x_units, facing_y_units) + angle_shift
        if angle_shift != 0
        else 0
    )
    angle = base_angle + trunc_div(
        (count - 1 - index) * 360,
        count,
    )
    x_units = logic_cos(angle, radius_units)
    y_units = logic_sin(angle, radius_units)
    if flip_x:
        x_units = -x_units
    if flip_y:
        y_units = -y_units
    return logic_units_to_tiles(x_units), logic_units_to_tiles(y_units)
