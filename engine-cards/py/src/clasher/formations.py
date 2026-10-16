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
            # Batch B1: a wide line of five or more (Royal Recruits) lays its
            # zigzag from the other end on the right lane. Ported from
            # RoyaleSim (MIT), formation.rs member_offset (ring counts 5, 6,
            # 8+ mirror on LANE_RIGHT), measured on Royal Recruits taps. No
            # C56 card has a wide line of five or more.
            or (width_units != 0 and int(lane_id) == 2 and slot_count >= 5 and slot_count != 7)
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


# Ported from RoyaleSim (MIT), formation.rs `line_centre_client` and its constants
# (formation.LINE_CENTRE_SEARCH = client15535_interleaved_first_ring, LINE_FRAME =
# client15535_y_reflection, LINE_KING_BACK_ROW = client16402_open, LINE_TERRITORY =
# client16402_troop_territory). Native units; checks run in the owner's y frame.
LINE_CELL = 1000
LINE_PRINCESS_X = ((2000, 5000), (13000, 16000))
LINE_PRINCESS_Y = (5000, 8000)
LINE_KING_COLUMNS = (7000, 11000)
LINE_KING_BACK_Y = 4000
LINE_KING_BACK_ROW_Y = 1000
LINE_BACK_ROW_OPEN_X = (6000, 12000)
LINE_KING_TILE_COLS = (7, 11)
LINE_KING_TILE_ROWS = 5
LINE_SEARCH_RINGS_CLIENT = 31


def line_centre_client(tap, offsets, ground, owner, may_stand, width=18000, height=32000):
    """Return the absolute tile centre (native units) a SummonWidth line stands on.

    ``tap``, ``ground`` and ``offsets`` are absolute native-unit points/displacements
    (``offsets`` = the members' displacements from the line's ground point).
    ``may_stand(x, y)`` tests an absolute ground point against the owner's troop
    territory. Returns None when no centre within the search rings is valid.
    """
    cell = LINE_CELL
    half = max((abs(int(o[0])) for o in offsets), default=0)

    def own_y(y):
        return height - y if owner == 1 else y

    first_row = LINE_KING_BACK_ROW_Y // cell

    def valid(cx, cy):
        oy = own_y(cy)
        ex, ey = cx + ground[0], cy + ground[1]
        if cx - half < -cell // 2 or cx + half > width + cell // 2 or not may_stand(ex, ey):
            return False
        if oy < LINE_KING_BACK_ROW_Y and not (LINE_BACK_ROW_OPEN_X[0] <= cx < LINE_BACK_ROW_OPEN_X[1]):
            return False
        col, row = cx // cell, oy // cell
        if LINE_KING_TILE_COLS[0] <= col < LINE_KING_TILE_COLS[1] and first_row <= row < LINE_KING_TILE_ROWS:
            return False
        for ox, oy_off in offsets:
            mx, my = ex + int(ox), own_y(ey + int(oy_off))
            if LINE_PRINCESS_Y[0] <= my < LINE_PRINCESS_Y[1] and any(a <= mx < b for a, b in LINE_PRINCESS_X):
                return False
            if LINE_KING_COLUMNS[0] <= mx < LINE_KING_COLUMNS[1] and LINE_KING_BACK_ROW_Y <= my < LINE_KING_BACK_Y:
                return False
        return True

    tx0 = min(max(int(tap[0]), 0), width - 1)
    ty0 = min(max(int(tap[1]), 0), height - 1)
    tx, ty = tx0 // cell, ty0 // cell
    best = None
    for r in range(LINE_SEARCH_RINGS_CLIENT):
        if r == 0:
            ring = [(0, 0)]
        else:
            ring = [d for i in range(2 * r) for d in ((i - r, -r), (-r, r - i), (r - i, r), (r, i - r))]
        for dx, dy in ring:
            cx, cy = (tx + dx) * cell + cell // 2, (ty + dy) * cell + cell // 2
            if valid(cx, cy):
                d = (cx - tx0) ** 2 + (cy - ty0) ** 2
                if best is None or d < best[0]:
                    best = (d, cx, cy)
        if best is not None:
            break
    return None if best is None else (best[1], best[2])
