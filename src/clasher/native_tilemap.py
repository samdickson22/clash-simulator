"""Native half-tile path data for the standard 1v1 arena.

The game stores this channel in ``assets/tilemaps/tilemap.csv``.  Each source
cell also contains terrain flags, but the native path lookup masks the value
with ``& 3`` before finding the nearest lane.
"""

from __future__ import annotations

from .kinematics import LOGIC_UNITS_PER_TILE, trunc_div


STANDARD_PATH_ROWS: tuple[str, ...] = (
    "000000000000000000000000000000000000",
    "000000000000000000000000000000000000",
    "000000000000001111222200000000000000",
    "000000000000001111222200000000000000",
    "000000000000001111222200000000000000",
    "000001111111111111222222222222200000",
    "000001111111111111222222222222200000",
    "000001111111111111222222222222200000",
    "000001111111111111222222222222200000",
    "000001111100001111222200002222200000",
    "000011111100000000000000002222220000",
    "000011111100000000000000002222220000",
    "000011111100000000000000002222220000",
    "000011111100000000000000002222220000",
    "000011111100000000000000002222220000",
    "000011111100000000000000002222220000",
    "000011111100000000000000002222220000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000000110000000000000000000022000000",
    "000000110000000000000000000022000000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000001111000000000000000000222200000",
    "000011111100000000000000002222220000",
    "000011111100000000000000002222220000",
    "000011111100000000000000002222220000",
    "000011111100000000000000002222220000",
    "000011111100000000000000002222220000",
    "000011111100000000000000002222220000",
    "000011111100000000000000002222220000",
    "000001111100001111222200002222200000",
    "000001111111111111222222222222200000",
    "000001111111111111222222222222200000",
    "000001111111111111222222222222200000",
    "000001111111111111222222222222200000",
    "000000000000001111222200000000000000",
    "000000000000001111222200000000000000",
    "000000000000001111222200000000000000",
    "000000000000000000000000000000000000",
    "000000000000000000000000000000000000",
)

STANDARD_PATH_WIDTH = 36
STANDARD_PATH_HEIGHT = 64
HALF_TILE_LOGIC_UNITS = 500
# LogicTileMap::moveObject clips a center at the midpoint of the outermost
# half-tile cell. This is independent of the object's collision radius.
OUTERMOST_OBJECT_CENTER_UNITS = HALF_TILE_LOGIC_UNITS // 2
OUTERMOST_OBJECT_CENTER_TILES = (
    OUTERMOST_OBJECT_CENTER_UNITS / LOGIC_UNITS_PER_TILE
)

# Bit 5 of the standard map is the native spawn/movement obstruction channel.
# It is set only across the four half-tile river rows, with two four-cell
# bridge openings.
STANDARD_BLOCKED_RIVER_ROWS = range(30, 34)
STANDARD_BRIDGE_CELL_RANGES = ((5, 8), (27, 30))

if (
    len(STANDARD_PATH_ROWS) != STANDARD_PATH_HEIGHT
    or any(len(row) != STANDARD_PATH_WIDTH for row in STANDARD_PATH_ROWS)
):
    raise RuntimeError("invalid standard native path map dimensions")


def nearest_native_path_id(
    x_units: int,
    y_units: int,
    other_x_units: int = -1,
) -> int:
    """Port the game's nearest-path scan, including its deterministic ties."""

    source_cell_x = trunc_div(int(x_units), HALF_TILE_LOGIC_UNITS)
    source_cell_y = trunc_div(int(y_units), HALF_TILE_LOGIC_UNITS)
    other_cell_x = trunc_div(int(other_x_units), HALF_TILE_LOGIC_UNITS)
    rounded_source_cell_x = trunc_div(
        int(x_units) + 5,
        HALF_TILE_LOGIC_UNITS,
    )

    closest_path = 0
    closest_distance_sq = 0x7FFFFFFF
    closest_to_other_path = -1
    closest_to_other_distance_sq = 0x7FFFFFFF
    crossed_center_tie = False
    center_cell_x = STANDARD_PATH_WIDTH // 2

    # The native array is addressed as [y * width + x], but the lookup scans
    # x first and y second. Strict replacement preserves the first path on a
    # distance tie.
    for cell_x in range(STANDARD_PATH_WIDTH):
        dx = cell_x - source_cell_x
        for cell_y in range(STANDARD_PATH_HEIGHT):
            path_id = ord(STANDARD_PATH_ROWS[cell_y][cell_x]) - ord("0")
            if path_id < 1:
                continue

            dy = cell_y - source_cell_y
            source_distance_sq = dx * dx + dy * dy
            other_distance_sq = (
                (cell_x - other_cell_x) ** 2 + dy * dy
            )

            if (
                other_x_units != -1
                and other_distance_sq < closest_to_other_distance_sq
            ):
                closest_to_other_path = path_id
                closest_to_other_distance_sq = other_distance_sq

            if source_distance_sq < closest_distance_sq:
                closest_path = path_id
            if source_distance_sq <= closest_distance_sq:
                closest_distance_sq = source_distance_sq

            crosses_center = (
                other_x_units < x_units
                and other_cell_x < center_cell_x <= rounded_source_cell_x
            ) or (
                x_units < other_x_units
                and rounded_source_cell_x <= center_cell_x < other_cell_x
            )
            if (
                other_x_units != -1
                and source_distance_sq == closest_distance_sq
                and crosses_center
            ):
                crossed_center_tie = True

    if crossed_center_tie and closest_path == closest_to_other_path:
        if closest_path == 1:
            return 2
        if closest_path == 2:
            return 1
    return closest_path


def native_spawn_tile_blocked(cell_x: int, cell_y: int) -> bool:
    """Return LogicTileMap's bit-5 obstruction value for one map cell."""

    if not (
        0 <= int(cell_x) < STANDARD_PATH_WIDTH
        and 0 <= int(cell_y) < STANDARD_PATH_HEIGHT
    ):
        return True
    if int(cell_y) not in STANDARD_BLOCKED_RIVER_ROWS:
        return False
    return not any(
        start <= int(cell_x) <= end
        for start, end in STANDARD_BRIDGE_CELL_RANGES
    )


def clamp_native_object_axis(value: float, arena_size: int) -> float:
    """Clamp one moving object center like LogicTileMap::moveObject."""

    return max(
        OUTERMOST_OBJECT_CENTER_TILES,
        min(float(arena_size) - OUTERMOST_OBJECT_CENTER_TILES, float(value)),
    )


def recover_native_ground_position(x_units: int, y_units: int) -> tuple[int, int]:
    """Recover an obstructed character center using LogicBattle::cf44d8.

    Candidates are offsets from the current point, not snapped cell centers.
    Row-major scanning and strict replacement preserve the native world-side
    tie break. The distance approximation is max + floor(53 * min / 128).
    """
    x = max(250, min(int(x_units), STANDARD_PATH_WIDTH * 500 - 250))
    y = max(250, min(int(y_units), STANDARD_PATH_HEIGHT * 500 - 250))
    if not native_spawn_tile_blocked(x // 500, y // 500):
        return x, y
    best = (x, y)
    best_distance = 0x7FFFFFFF
    for dy in range(-2250, 2751, 500):
        candidate_y = y + dy
        if not 0 <= candidate_y < STANDARD_PATH_HEIGHT * 500:
            continue
        for dx in range(-2250, 2751, 500):
            candidate_x = x + dx
            if not 0 <= candidate_x < STANDARD_PATH_WIDTH * 500:
                continue
            if native_spawn_tile_blocked(candidate_x // 500, candidate_y // 500):
                continue
            distance = max(abs(dx), abs(dy)) + (53 * min(abs(dx), abs(dy)) >> 7)
            if distance < best_distance:
                best = candidate_x, candidate_y
                best_distance = distance
    return best


def clip_native_ground_pressure(
    x_units: int, y_units: int, dx_units: int, dy_units: int,
) -> tuple[int, int]:
    """Clip idle ground pressure against adjacent river cells.

    LogicTileMap::moveObject (15.535.86, 0x115db8c) tests each axis
    against the original half-tile cell. Positive crossings stop one logic
    unit before the edge; negative crossings stop on the edge itself.
    Outer arena bounds remain the caller's responsibility.
    """
    cell_x, cell_y = trunc_div(x_units, 500), trunc_div(y_units, 500)
    x, y = x_units + dx_units, y_units + dy_units

    def water(cx: int, cy: int) -> bool:
        return cy in STANDARD_BLOCKED_RIVER_ROWS and native_spawn_tile_blocked(cx, cy)

    if dx_units > 0 and x >= (cell_x + 1) * 500 and water(cell_x + 1, cell_y):
        x = (cell_x + 1) * 500 - 1
    elif dx_units < 0 and x < cell_x * 500 and water(cell_x - 1, cell_y):
        x = cell_x * 500
    if dy_units > 0 and y >= (cell_y + 1) * 500 and water(cell_x, cell_y + 1):
        y = (cell_y + 1) * 500 - 1
    elif dy_units < 0 and y < cell_y * 500 and water(cell_x, cell_y - 1):
        y = cell_y * 500
    return x, y
