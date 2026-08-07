"""Native-grid ground routing around dynamic arena obstacles.

Clash movement plans on the arena's 500-logic-unit grid.  The runtime follows
the center of the next cell in an eight-neighbour A* path, while the character
movement component still applies its ordinary fixed-point speed for the frame.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import TYPE_CHECKING

from .arena import Position
from .kinematics import (
    normalized_vector_logic_units,
    tiles_to_logic_units,
    trunc_div,
)
from .native_tilemap import (
    HALF_TILE_LOGIC_UNITS,
    STANDARD_PATH_HEIGHT,
    STANDARD_PATH_ROWS,
    STANDARD_PATH_WIDTH,
    native_spawn_tile_blocked,
)

if TYPE_CHECKING:
    from .battle import BattleState
    from .entities import Entity


_NATIVE_NEIGHBORS: tuple[tuple[int, int, int], ...] = (
    # LogicPathFinder::ExpandNode visits these in a fixed world-grid order;
    # it does not rotate the order for the owning player.
    (0, -1, 10),
    (0, 1, 10),
    (-1, 0, 10),
    (1, 0, 10),
    (-1, -1, 14),
    (-1, 1, 14),
    (1, 1, 14),
    (1, -1, 14),
)

_NATIVE_EMPTY_TILE_COST = 20
_NATIVE_OTHER_LANE_COST = 5
_NATIVE_SAME_LANE_COST = 1
_NATIVE_WATER_COST = 800


def _cell_for_position(position: Position) -> tuple[int, int]:
    return (
        max(
            0,
            min(
                STANDARD_PATH_WIDTH - 1,
                trunc_div(
                    tiles_to_logic_units(position.x),
                    HALF_TILE_LOGIC_UNITS,
                ),
            ),
        ),
        max(
            0,
            min(
                STANDARD_PATH_HEIGHT - 1,
                trunc_div(
                    tiles_to_logic_units(position.y),
                    HALF_TILE_LOGIC_UNITS,
                ),
            ),
        ),
    )


def _cell_center(cell: tuple[int, int]) -> Position:
    cell_x, cell_y = cell
    return Position(
        (cell_x * HALF_TILE_LOGIC_UNITS + HALF_TILE_LOGIC_UNITS // 2) / 1000.0,
        (cell_y * HALF_TILE_LOGIC_UNITS + HALF_TILE_LOGIC_UNITS // 2) / 1000.0,
    )


def native_route_goal_cell(
    mover: "Entity",
    target: "Entity",
    *,
    required_range_tiles: float | None = None,
) -> tuple[int, int] | None:
    """Return ``getClosestTilePositionToTarget`` for an ordinary attack.

    The movement component does not route to a target object's occupied tile.
    It scans half-tile centers inside the attacker's serialized range of the
    target *center*, then keeps the candidate closest to the mover. The scan
    is y-major/x-minor and replaces only on a strictly smaller distance, so a
    geometric tie keeps the lowest world-grid y and then x.

    Target collision radius deliberately does not participate here. Native
    combat uses it when deciding whether an attack can begin, while route goal
    selection calls the point overload of ``getDistanceToObjectSquared``.
    """

    range_tiles = (
        float(getattr(mover, "range", 0.0) or 0.0)
        if required_range_tiles is None
        else float(required_range_tiles)
    )
    required_range_units = max(0, tiles_to_logic_units(range_tiles))
    search_radius = trunc_div(required_range_units, HALF_TILE_LOGIC_UNITS) + 1
    target_cell_x, target_cell_y = _cell_for_position(target.position)
    min_x = max(0, target_cell_x - search_radius)
    max_x = min(STANDARD_PATH_WIDTH - 1, target_cell_x + search_radius)
    min_y = max(0, target_cell_y - search_radius)
    max_y = min(STANDARD_PATH_HEIGHT - 1, target_cell_y + search_radius)

    mover_x = tiles_to_logic_units(mover.position.x)
    mover_y = tiles_to_logic_units(mover.position.y)
    target_x = tiles_to_logic_units(target.position.x)
    target_y = tiles_to_logic_units(target.position.y)
    required_range_sq = required_range_units * required_range_units
    best_cell: tuple[int, int] | None = None
    best_mover_distance_sq = (1 << 31) - 1

    # LogicTileMap::isPassablePathFinder is only an arena-bounds check. Water
    # and lane data influence A* cost later, not candidate eligibility.
    for cell_y in range(min_y, max_y + 1):
        candidate_y = cell_y * HALF_TILE_LOGIC_UNITS + HALF_TILE_LOGIC_UNITS // 2
        target_dy = candidate_y - target_y
        mover_dy = candidate_y - mover_y
        for cell_x in range(min_x, max_x + 1):
            candidate_x = (
                cell_x * HALF_TILE_LOGIC_UNITS
                + HALF_TILE_LOGIC_UNITS // 2
            )
            target_dx = candidate_x - target_x
            if (
                target_dx * target_dx + target_dy * target_dy
                > required_range_sq
            ):
                continue
            mover_dx = candidate_x - mover_x
            mover_distance_sq = (
                mover_dx * mover_dx + mover_dy * mover_dy
            )
            if mover_distance_sq < best_mover_distance_sq:
                best_cell = (cell_x, cell_y)
                best_mover_distance_sq = mover_distance_sq
    return best_cell


def _heuristic(
    cell: tuple[int, int],
    goal: tuple[int, int],
) -> int:
    # Native LogicPathFinder uses 10 * Chebyshev distance.
    return 10 * max(abs(goal[0] - cell[0]), abs(goal[1] - cell[1]))


def _native_pathfinder_tile_cost(
    mover: "Entity",
    cell: tuple[int, int],
) -> int | None:
    """Return LogicTileMap::getPathFinderCost for the standard arena.

    The immutable tile-map value owns both channels used by routing: bit 5 is
    water, while the low two bits are lane IDs. Water remains traversable at
    a high score for ordinary ground units and costs the normal 20 for a
    JumpHeight character. Non-water lane cells cost 1 on the character's
    spawn-time lane and 5 on the other lane; unlabeled land costs 20.
    """

    cell_x, cell_y = cell
    if not (
        0 <= cell_x < STANDARD_PATH_WIDTH
        and 0 <= cell_y < STANDARD_PATH_HEIGHT
    ):
        return None
    if native_spawn_tile_blocked(cell_x, cell_y):
        return (
            _NATIVE_EMPTY_TILE_COST
            if bool(getattr(mover.card_stats, "jump_height", None))
            else _NATIVE_WATER_COST
        )
    cell_lane = ord(STANDARD_PATH_ROWS[cell_y][cell_x]) - ord("0")
    if cell_lane <= 0:
        return _NATIVE_EMPTY_TILE_COST
    return (
        _NATIVE_SAME_LANE_COST
        if cell_lane == int(getattr(mover, "_native_lane_id", 0) or 0)
        else _NATIVE_OTHER_LANE_COST
    )


def _native_grid_route(
    start: tuple[int, int],
    goal: tuple[int, int],
    tile_cost: Callable[[tuple[int, int]], int | None],
) -> list[tuple[int, int]] | None:
    """Return a route using the native first-discovery score and binary heap.

    The client does not relax a tile already present in either the open or
    closed set. Nor does it retain a separate ``g`` value: each child's stored
    score is its parent's complete score plus terrain-weighted step cost plus
    the child's heuristic. The heap compares only that cumulative score;
    equal priorities retain its binary topology instead of using a secondary
    heuristic or player-relative tie break.
    """

    parents: dict[tuple[int, int], tuple[int, int]] = {}
    priorities: dict[tuple[int, int], int] = {start: 0}
    discovered = {start}
    heap: list[tuple[int, int]] = [start]

    def push(cell: tuple[int, int]) -> None:
        heap.append(cell)
        index = len(heap) - 1
        while index > 0:
            parent_index = (index - 1) // 2
            parent = heap[parent_index]
            if priorities[parent] <= priorities[cell]:
                break
            heap[index] = parent
            index = parent_index
        heap[index] = cell

    def pop() -> tuple[int, int]:
        root = heap[0]
        last = heap.pop()
        if not heap:
            return root
        heap[0] = last
        index = 0
        while True:
            chosen = index
            right = index * 2 + 2
            if (
                right < len(heap)
                and priorities[heap[right]] < priorities[heap[chosen]]
            ):
                chosen = right
            left = index * 2 + 1
            if (
                left < len(heap)
                and priorities[heap[left]] < priorities[heap[chosen]]
            ):
                chosen = left
            if chosen == index:
                break
            heap[index], heap[chosen] = heap[chosen], heap[index]
            index = chosen
        return root

    found = False
    while heap:
        current = pop()
        if current == goal:
            found = True
            break
        for delta_x, delta_y, step_cost in _NATIVE_NEIGHBORS:
            neighbor = (current[0] + delta_x, current[1] + delta_y)
            terrain_cost = tile_cost(neighbor)
            if neighbor in discovered or terrain_cost is None:
                continue
            discovered.add(neighbor)
            parents[neighbor] = current
            priorities[neighbor] = (
                priorities[current]
                + step_cost * terrain_cost
                + _heuristic(neighbor, goal)
            )
            push(neighbor)

    if not found:
        return None
    route = [goal]
    while route[-1] != start:
        parent = parents.get(route[-1])
        if parent is None:
            return None
        route.append(parent)
    route.reverse()
    return route


def native_jump_landing_waypoint(
    battle_state: "BattleState",
    mover: "Entity",
    desired: Position,
    *,
    target_entity: "Entity" | None = None,
) -> Position | None:
    """Return the first native land-cell center beyond a jumpable river run.

    LogicMovementComponent receives the path in reverse order. When its next
    node is marked with tile-map bit 5, it scans across the complete run of
    marked half-tile cells, replaces the route with the first unmarked node,
    and enters movement state 6. Coordinates are reconstructed as
    ``cell * 500 + 250``; they are not a continuous line/river intersection.
    """

    # LogicCharacter::GetPathX/Y divides the positive world coordinate by 500
    # directly. Exact cell boundaries are not re-owned in player space.
    start = _cell_for_position(mover.position)
    desired_cell = (
        native_route_goal_cell(mover, target_entity)
        if target_entity is not None
        else _cell_for_position(desired)
    )
    if desired_cell is None:
        return None
    del battle_state
    cost_cache: dict[tuple[int, int], int | None] = {}

    def tile_cost(cell: tuple[int, int]) -> int | None:
        if cell not in cost_cache:
            cost_cache[cell] = _native_pathfinder_tile_cost(mover, cell)
        return cost_cache[cell]

    goal = desired_cell
    if goal is None or goal == start:
        return None

    retained_route = getattr(mover, "_native_ground_route_cells", None)
    if target_entity is not None and isinstance(retained_route, list):
        future_route = list(retained_route)
    else:
        route_cells = _native_grid_route(start, goal, tile_cost)
        if route_cells is None:
            return None
        future_route = route_cells[1:]

    river_start = next(
        (
            index
            for index, cell in enumerate(future_route)
            if native_spawn_tile_blocked(*cell)
        ),
        None,
    )
    if river_start is None:
        return None
    for cell in future_route[river_start + 1 :]:
        if not native_spawn_tile_blocked(*cell):
            if target_entity is not None and isinstance(retained_route, list):
                # The river state replaces the ordinary route with the first
                # land node beyond the complete water run.
                retained_route[:] = [cell]
            return _cell_center(cell)
    return None


def native_single_node_waypoint(
    mover: "Entity",
    target: "Entity",
) -> Position:
    """Return the retained one-node path used by FlyingHeight characters."""

    goal = native_route_goal_cell(mover, target)
    if goal is None:
        return target.position
    cache_key = ("single", goal)
    if getattr(mover, "_ground_path_cache_key", None) != cache_key:
        mover._ground_path_cache_key = cache_key
        mover._native_ground_route_cells = [goal]
        mover._ground_path_cache_backwards = False
    retained_route = getattr(mover, "_native_ground_route_cells", None)
    if isinstance(retained_route, list) and retained_route:
        return _cell_center(retained_route[0])
    return target.position


def ground_path_waypoint(
    battle_state: "BattleState",
    mover: "Entity",
    desired: Position,
    *,
    target_entity: "Entity" | None = None,
    backwards_reference: Position | None = None,
) -> Position:
    """Return the next LogicPathFinder half-tile waypoint.

    Native ground routing is not an obstacle-triggered detour. Every ordinary
    target move builds a route on the immutable arena grid; placed buildings
    are handled later by movement collision and avoidance, not by A*.
    """

    from .unit_traits import is_hover_unit_card

    reference = backwards_reference or desired
    origin_dx = tiles_to_logic_units(mover.position.x - reference.x)
    origin_dy = tiles_to_logic_units(mover.position.y - reference.y)
    origin_distance = math.isqrt(
        origin_dx * origin_dx + origin_dy * origin_dy
    )

    def route_moves_backwards(route_positions: tuple[Position, ...]) -> bool:
        for route_position in route_positions:
            dx = tiles_to_logic_units(route_position.x - reference.x)
            dy = tiles_to_logic_units(route_position.y - reference.y)
            if math.isqrt(dx * dx + dy * dy) > origin_distance:
                return True
        return False

    start = _cell_for_position(mover.position)
    desired_cell = (
        native_route_goal_cell(mover, target_entity)
        if target_entity is not None
        else _cell_for_position(desired)
    )
    if desired_cell is None:
        mover._ground_path_backwards = route_moves_backwards((desired,))
        return desired
    desired_waypoint = _cell_center(desired_cell)
    if is_hover_unit_card(getattr(mover, "card_stats", None)):
        waypoint = (
            native_single_node_waypoint(mover, target_entity)
            if target_entity is not None
            else desired_waypoint
        )
        mover._ground_path_backwards = route_moves_backwards((waypoint,))
        return waypoint
    cache_key = (
        desired_cell,
        int(getattr(mover, "_native_lane_id", 0) or 0),
        bool(getattr(getattr(mover, "card_stats", None), "jump_height", None)),
    )
    if getattr(mover, "_ground_path_cache_key", None) == cache_key:
        route_cells = getattr(mover, "_native_ground_route_cells", None)
        if isinstance(route_cells, list):
            mover._ground_path_backwards = bool(
                getattr(mover, "_ground_path_cache_backwards", False)
            )
            return _cell_center(route_cells[0]) if route_cells else desired

    del battle_state
    if desired_cell == start:
        mover._ground_path_backwards = route_moves_backwards(
            (desired_waypoint,)
        )
        mover._ground_path_cache_key = cache_key
        mover._native_ground_route_cells = []
        mover._ground_path_cache_backwards = mover._ground_path_backwards
        return desired_waypoint

    def tile_cost(cell: tuple[int, int]) -> int | None:
        return _native_pathfinder_tile_cost(mover, cell)

    route_cells = _native_grid_route(start, desired_cell, tile_cost)
    if route_cells is None or len(route_cells) < 2:
        mover._ground_path_backwards = route_moves_backwards((desired,))
        return desired
    retained_route = list(route_cells[1:])
    waypoint = _cell_center(retained_route[0])
    backwards = route_moves_backwards(
        tuple(_cell_center(cell) for cell in route_cells[1:])
    )
    mover._ground_path_cache_key = cache_key
    mover._native_ground_route_cells = retained_route
    mover._ground_path_cache_backwards = backwards
    mover._ground_path_backwards = backwards
    return waypoint


def advance_native_ground_route(
    mover: "Entity",
    waypoint: Position,
    previous_position: Position,
) -> None:
    """Consume at most one retained route node after native movement.

    ``updateMovementTowards`` projects the node remainder onto the direction
    selected before movement. A value below 1001 logic units marks that node
    reached; the movement component then removes exactly one point and starts
    the following frame with the next retained cell.
    """

    route_cells = getattr(mover, "_native_ground_route_cells", None)
    if not isinstance(route_cells, list) or not route_cells:
        return
    if _cell_center(route_cells[0]) != waypoint:
        return
    direction_x, direction_y = normalized_vector_logic_units(
        tiles_to_logic_units(waypoint.x - previous_position.x),
        tiles_to_logic_units(waypoint.y - previous_position.y),
        256,
    )
    remaining_x = tiles_to_logic_units(waypoint.x - mover.position.x)
    remaining_y = tiles_to_logic_units(waypoint.y - mover.position.y)
    projected_remaining = (
        trunc_div(direction_y * remaining_y, 256)
        + trunc_div(direction_x * remaining_x, 256)
    )
    if projected_remaining < 1001:
        route_cells.pop(0)


def skip_native_ground_route_node_inside_static(
    mover: "Entity",
    static_entity: "Entity",
) -> None:
    """Apply ``checkAvoidance``'s static-object path-node removal."""

    route_cells = getattr(mover, "_native_ground_route_cells", None)
    if not isinstance(route_cells, list) or len(route_cells) < 2:
        return
    waypoint = _cell_center(route_cells[0])
    dx = tiles_to_logic_units(waypoint.x - static_entity.position.x)
    dy = tiles_to_logic_units(waypoint.y - static_entity.position.y)
    radius = max(
        0,
        tiles_to_logic_units(static_entity.get_collision_radius()),
    )
    if dx * dx + dy * dy < radius * radius:
        route_cells.pop(0)
