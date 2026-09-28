"""Native-grid ground routing around dynamic arena obstacles.

Clash movement plans on the arena's 500-logic-unit grid.  The runtime follows
the center of the next cell in an eight-neighbour A* path, while the character
movement component still applies its ordinary fixed-point speed for the frame.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from functools import lru_cache
from types import MappingProxyType
from typing import TYPE_CHECKING, cast

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

_NATIVE_EMPTY_TILE_COST = 8
_NATIVE_SAMEPATH_EPSILON = 3
_NATIVE_FRIENDLY_ONLY_OCCLUSIONS = True
_NATIVE_OTHER_LANE_COST = 5
_NATIVE_SAME_LANE_COST = 5
_NATIVE_WATER_COST = 50
_NATIVE_JUMP_WATER_COST = 7

# Reference/benchmark switch for exact repeated route-goal queries.
_USE_NATIVE_ROUTE_GOAL_CACHE = True


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


def _compute_native_route_goal_cell_units(
    mover_x: int,
    mover_y: int,
    target_x: int,
    target_y: int,
    required_range_units: int,
    is_air_unit: bool = False,
    occupied_cells: frozenset[tuple[int, int]] = frozenset(),
) -> tuple[int, int] | None:
    """Compute one exact native route goal from integer logic coordinates."""

    search_radius = trunc_div(required_range_units, HALF_TILE_LOGIC_UNITS) + 1
    target_cell_x = max(
        0,
        min(
            STANDARD_PATH_WIDTH - 1,
            trunc_div(target_x, HALF_TILE_LOGIC_UNITS),
        ),
    )
    target_cell_y = max(
        0,
        min(
            STANDARD_PATH_HEIGHT - 1,
            trunc_div(target_y, HALF_TILE_LOGIC_UNITS),
        ),
    )
    min_x = max(0, target_cell_x - search_radius)
    max_x = min(STANDARD_PATH_WIDTH - 1, target_cell_x + search_radius)
    min_y = max(0, target_cell_y - search_radius)
    max_y = min(STANDARD_PATH_HEIGHT - 1, target_cell_y + search_radius)

    required_range_sq = required_range_units * required_range_units
    best_cell: tuple[int, int] | None = None
    best_priority = 0
    best_mover_distance_sq = (1 << 31) - 1
    # LogicTileMap::isPassablePathFinder is only an arena-bounds check. Water
    # and lane data influence A* cost later, not candidate eligibility.
    for cell_y in range(min_y, max_y + 1):
        candidate_y = cell_y * HALF_TILE_LOGIC_UNITS + HALF_TILE_LOGIC_UNITS // 2
        target_dy = candidate_y - target_y
        mover_dy = candidate_y - mover_y
        columns = (
            range(min_x, max_x + 1)
            if mover_x < STANDARD_PATH_WIDTH * HALF_TILE_LOGIC_UNITS // 2
            else range(max_x, min_x - 1, -1)
        )
        for cell_x in columns:
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
            priority = (
                1
                if not is_air_unit
                and (
                    native_spawn_tile_blocked(cell_x, cell_y)
                    or (cell_x, cell_y) in occupied_cells
                )
                else 2
            )
            if priority > best_priority or (
                priority == best_priority and mover_distance_sq < best_mover_distance_sq
            ):
                best_cell = (cell_x, cell_y)
                best_priority = priority
                best_mover_distance_sq = mover_distance_sq
    return best_cell


_cached_native_route_goal_cell_units = lru_cache(maxsize=32_768)(
    _compute_native_route_goal_cell_units
)


def native_route_goal_cell(
    mover: "Entity",
    target: "Entity",
    *,
    required_range_tiles: float | None = None,
) -> tuple[int, int] | None:
    """Return the native approach cell, accounting for occupied building cells.

    Ground movers prefer unblocked cells. Equal candidates retain the native
    world-side scan order. Cache identity includes flight and building occupancy
    so repeated geometry cannot reuse a goal from a different arena state.
    """

    range_tiles = (
        max(
            0.0,
            mover.get_effective_attack_range()
            - mover.get_attack_approach_range_reduction(target),
        )
        if required_range_tiles is None
        else float(required_range_tiles)
    )
    from .unit_traits import is_hover_unit_card

    battle_state = getattr(mover, "battle_state", None)
    occupied_cells = (
        frozenset(native_building_cost_cells(battle_state))
        if (
            battle_state is not None
            and not getattr(mover, "is_air_unit", False)
            and not is_hover_unit_card(getattr(mover, "card_stats", None))
        )
        else frozenset()
    )

    args = (
        tiles_to_logic_units(mover.position.x),
        tiles_to_logic_units(mover.position.y),
        tiles_to_logic_units(target.position.x),
        tiles_to_logic_units(target.position.y),
        max(0, tiles_to_logic_units(range_tiles)),
        bool(getattr(mover, "is_air_unit", False)),
        occupied_cells,
    )
    if _USE_NATIVE_ROUTE_GOAL_CACHE:
        return _cached_native_route_goal_cell_units(*args)
    return _compute_native_route_goal_cell_units(*args)


def _heuristic(
    cell: tuple[int, int],
    goal: tuple[int, int],
) -> int:
    # Native mode1 uses octile distance, scaled by the runtime heuristic cost5.
    dx, dy = abs(goal[0] - cell[0]), abs(goal[1] - cell[1])
    return 5 * (10 * max(dx, dy) + 4 * min(dx, dy))


def _native_pathfinder_tile_cost(
    mover: "Entity",
    cell: tuple[int, int],
) -> int | None:
    """Return LogicTileMap::getPathFinderCost for the standard arena.

    The immutable tile-map value owns both channels used by routing: bit 5 is
    water, while the low two bits are lane IDs. Water remains traversable at
    cost50 for ordinary ground units and cost7 for a JumpHeight character.
    Road and matching-road costs are both5; unlabeled land costs8. These
    values are verified against runtime grid fields and decoded globals.
    """

    return _standard_pathfinder_tile_cost(
        cell,
        lane_id=int(getattr(mover, "_native_lane_id", 0) or 0),
        jump_height=bool(getattr(mover.card_stats, "jump_height", None)),
    )


def _standard_pathfinder_tile_cost(
    cell: tuple[int, int],
    *,
    lane_id: int,
    jump_height: bool,
) -> int | None:
    cell_x, cell_y = cell
    if not (
        0 <= cell_x < STANDARD_PATH_WIDTH
        and 0 <= cell_y < STANDARD_PATH_HEIGHT
    ):
        return None
    if native_spawn_tile_blocked(cell_x, cell_y):
        return (
            _NATIVE_JUMP_WATER_COST
            if jump_height
            else _NATIVE_WATER_COST
        )
    cell_lane = ord(STANDARD_PATH_ROWS[cell_y][cell_x]) - ord("0")
    if cell_lane <= 0:
        return _NATIVE_EMPTY_TILE_COST
    return (
        _NATIVE_SAME_LANE_COST
        if cell_lane == lane_id
        else _NATIVE_OTHER_LANE_COST
    )


@lru_cache(maxsize=16)
def _standard_path_cost_map(
    lane_id: int,
    jump_height: bool,
) -> Mapping[tuple[int, int], int]:
    """Return immutable exact costs for one standard-arena movement profile."""
    return MappingProxyType(
        {
            (cell_x, cell_y): cast(
                int,
                _standard_pathfinder_tile_cost(
                    (cell_x, cell_y),
                    lane_id=lane_id,
                    jump_height=jump_height,
                ),
            )
            for cell_y in range(STANDARD_PATH_HEIGHT)
            for cell_x in range(STANDARD_PATH_WIDTH)
        }
    )


def _native_grid_route(
    start: tuple[int, int],
    goal: tuple[int, int],
    tile_cost: Callable[[tuple[int, int]], int | None],
) -> list[tuple[int, int]] | None:
    """Return a route with native weighted octile A* and binary-heap ties.

    Runtime flags0/1/0 retain separate travel and priority scores, allow
    decreases for open nodes, and never reopen closed nodes. The heap compares
    priority only and checks its right child before its left child.
    """

    parents: dict[tuple[int, int], tuple[int, int]] = {}
    priorities: dict[tuple[int, int], int] = {start: 0}
    travel_costs = {start: 0}
    closed: set[tuple[int, int]] = set()
    heap: list[tuple[int, int]] = [start]

    def push(cell: tuple[int, int]) -> None:
        if cell in heap:
            index = heap.index(cell)
        else:
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
        closed.add(current)
        if current == goal:
            found = True
            break
        for delta_x, delta_y, step_cost in _NATIVE_NEIGHBORS:
            neighbor = (current[0] + delta_x, current[1] + delta_y)
            terrain_cost = tile_cost(neighbor)
            if neighbor in closed or terrain_cost is None:
                continue
            travel = travel_costs[current] + step_cost * terrain_cost
            priority = travel + _heuristic(neighbor, goal)
            if neighbor in priorities and priority >= priorities[neighbor]:
                continue
            parents[neighbor] = current
            travel_costs[neighbor] = travel
            priorities[neighbor] = priority
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


@lru_cache(maxsize=2048)
def _cached_standard_grid_route(
    start: tuple[int, int],
    goal: tuple[int, int],
    lane_id: int,
    jump_height: bool,
) -> tuple[tuple[int, int], ...] | None:
    """Return an immutable exact route on the static standard arena grid."""

    route = _native_grid_route(
        start,
        goal,
        _standard_path_cost_map(lane_id, jump_height).get,
    )
    return None if route is None else tuple(route)


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
    and enters character state 5. Coordinates are reconstructed as
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
    goal = desired_cell
    if goal is None or goal == start:
        return None

    retained_route = getattr(mover, "_native_ground_route_cells", None)
    if target_entity is not None and isinstance(retained_route, list):
        future_route = list(retained_route)
    else:
        route_cells = _cached_standard_grid_route(
            start,
            goal,
            int(getattr(mover, "_native_lane_id", 0) or 0),
            bool(getattr(mover.card_stats, "jump_height", None)),
        )
        if route_cells is None:
            return None
        future_route = list(route_cells[1:])

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


def _set_native_route_direction(mover: "Entity", cell: tuple[int, int] | None) -> None:
    if cell is None:
        mover._native_ground_route_direction = None
        return
    waypoint = _cell_center(cell)
    mover._native_ground_route_direction = normalized_vector_logic_units(
        tiles_to_logic_units(waypoint.x - mover.position.x),
        tiles_to_logic_units(waypoint.y - mover.position.y),
        256,
    )


def native_single_node_waypoint(
    mover: "Entity",
    target: "Entity",
) -> Position:
    """Return the retained one-node path used by FlyingHeight characters."""

    goal = native_route_goal_cell(mover, target)
    if goal is None:
        return target.position
    cache_key = ("single", goal)
    if (
        getattr(mover, "_ground_path_cache_key", None) != cache_key
        or not getattr(mover, "_native_ground_route_cells", None)
    ):
        mover._ground_path_cache_key = cache_key
        mover._native_ground_route_cells = [goal]
        _set_native_route_direction(mover, goal)
        mover._ground_path_cache_backwards = False
    retained_route = getattr(mover, "_native_ground_route_cells", None)
    if isinstance(retained_route, list) and retained_route:
        return _cell_center(retained_route[0])
    return target.position


def native_building_cost_cells(battle_state: "BattleState") -> tuple[tuple[int, int], ...]:
    """Read this tick's overlay, or rasterize live footprints outside a tick."""
    from .entities import Building

    snapshot = getattr(battle_state, "_native_building_cost_snapshot", None)
    if snapshot is not None:
        return snapshot
    cells: set[tuple[int, int]] = set()
    for entity in battle_state.entities.values():
        if not isinstance(entity, Building) or not entity.is_alive:
            continue
        x = tiles_to_logic_units(entity.position.x)
        y = tiles_to_logic_units(entity.position.y)
        radius = tiles_to_logic_units(entity.get_collision_radius())
        # 115d210 rounds each center up to a grid boundary, then rasterizes
        # the half-open square defined by its collision radius.
        x = trunc_div(x - 1, 500) * 500 + 500
        y = trunc_div(y - 1, 500) * 500 + 500
        if (
            x - radius < 0 or y - radius < 0
            or x + radius >= 18000 or y + radius >= 32000
        ):
            continue
        for cell_y in range((y - radius) // 500, (y + radius - 1) // 500 + 1):
            for cell_x in range((x - radius) // 500, (x + radius - 1) // 500 + 1):
                cells.add((cell_x, cell_y))
    return tuple(sorted(cells))


def native_friendly_building_signature(battle_state: BattleState, owner: int) -> tuple[int, ...]:
    """Identify building changes on the mover's side at the component boundary."""
    from .entities import Building

    snapshot = getattr(battle_state, "_native_building_route_signatures", None)
    if snapshot is not None:
        return snapshot[owner]
    return tuple(sorted(
        e.id for e in battle_state.entities.values()
        if isinstance(e, Building) and e.is_alive and e.player_id == owner
    ))


@lru_cache(maxsize=2048)
def _cached_dynamic_grid_route(
    start: tuple[int, int],
    goal: tuple[int, int],
    lane_id: int,
    jump_height: bool,
    building_cells: tuple[tuple[int, int], ...],
) -> tuple[tuple[int, int], ...] | None:
    costs = dict(_standard_path_cost_map(lane_id, jump_height))
    for cell in building_cells:
        costs[cell] = max(costs[cell], 50)
    route = _native_grid_route(start, goal, costs.get)
    return None if route is None else tuple(route)


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
    target move builds a route on the arena grid with a building-cost overlay.
    Movement collision and avoidance then act on the resulting waypoints.
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
    building_cells = native_building_cost_cells(battle_state)
    cache_key = (
        desired_cell,
        building_cells,
        int(getattr(mover, "_native_lane_id", 0) or 0),
        bool(getattr(getattr(mover, "card_stats", None), "jump_height", None)),
    )
    previous_key = getattr(mover, "_ground_path_cache_key", None)
    friendly_signature = native_friendly_building_signature(battle_state, mover.player_id)
    previous_signature = getattr(mover, "_native_friendly_building_signature", None)
    same_goal_and_mode = (
        previous_key is not None
        and len(previous_key) == 4
        and previous_key[0] == cache_key[0]
        and previous_key[2:] == cache_key[2:]
    )
    if same_goal_and_mode and (
        friendly_signature == previous_signature
        if _NATIVE_FRIENDLY_ONLY_OCCLUSIONS else previous_key == cache_key
    ):
        route_cells = getattr(mover, "_native_ground_route_cells", None)
        if isinstance(route_cells, list) and route_cells:
            # PATHFINDING_FRIENDLYONLY_OCCLUSIONS gates invalidation, not the
            # obstacle costs of a new route. Enemy changes alone retain it.
            mover._ground_path_cache_key = cache_key
            mover._ground_path_backwards = bool(
                getattr(mover, "_ground_path_cache_backwards", False)
            )
            return _cell_center(route_cells[0]) if route_cells else desired

    if desired_cell == start:
        mover._ground_path_backwards = route_moves_backwards(
            (desired_waypoint,)
        )
        mover._ground_path_cache_key = cache_key
        mover._native_friendly_building_signature = friendly_signature
        mover._native_ground_route_cells = []
        _set_native_route_direction(mover, None)
        mover._ground_path_cache_backwards = mover._ground_path_backwards
        return desired_waypoint

    route_cells = _cached_dynamic_grid_route(
        start,
        desired_cell,
        int(getattr(mover, "_native_lane_id", 0) or 0),
        bool(getattr(mover.card_stats, "jump_height", None)),
        building_cells,
    )
    if route_cells is None or len(route_cells) < 2:
        mover._ground_path_backwards = route_moves_backwards((desired,))
        return desired
    retained_route = list(route_cells[1:])
    previous_route = getattr(mover, "_native_ground_route_cells", None)
    preserve_route_direction = False
    if (
        _NATIVE_SAMEPATH_EPSILON > 0
        and same_goal_and_mode
        and previous_route
    ):
        # Native115df2c replaces an existing route only when new occupancy
        # affects that route, or removed occupancy benefits the proposed one.
        # Walking refreshes the heading; resuming a retained route keeps its
        # saved direction for the waypoint projection threshold.
        before = set(previous_key[1])
        after = set(building_cells)
        newly_blocked = after - before
        newly_freed = before - after
        if not (
            newly_blocked.intersection(previous_route)
            or newly_freed.intersection(retained_route)
        ):
            retained_route = list(previous_route)
            preserve_route_direction = not mover._native_natural_movement_active
    # Restarting after a completed push first visits the current grid center.
    # Native consumes that waypoint before following the rebuilt forward route.
    if (
        previous_key is None
        and mover._knockback_target is None
        and battle_state.tick > 0
        and getattr(mover, "_native_knockback_movement_tick", -2) == battle_state.tick - 1
    ):
        retained_route.insert(0, (int(mover.position.x * 2), int(mover.position.y * 2)))
    waypoint = _cell_center(retained_route[0])
    backwards = route_moves_backwards(
        tuple(_cell_center(cell) for cell in retained_route)
    )
    mover._ground_path_cache_key = cache_key
    mover._native_friendly_building_signature = friendly_signature
    mover._native_ground_route_cells = retained_route
    if not preserve_route_direction:
        _set_native_route_direction(mover, retained_route[0])
    mover._ground_path_cache_backwards = backwards
    mover._ground_path_backwards = backwards
    return waypoint


def advance_native_ground_route(
    mover: "Entity",
    waypoint: Position,
    previous_position: Position,
) -> bool:
    """Consume at most one retained route node after native movement.

    ``updateMovementTowards`` projects the node remainder onto the direction
    recorded when the node became active. A value below 1001 logic units marks that node
    reached; the movement component then removes exactly one point and starts
    the following frame with the next retained cell.
    """

    route_cells = getattr(mover, "_native_ground_route_cells", None)
    if not isinstance(route_cells, list) or not route_cells:
        return False
    if _cell_center(route_cells[0]) != waypoint:
        return False
    direction = getattr(mover, "_native_ground_route_direction", None)
    if direction is None:
        # Compatibility for explicitly constructed route fixtures. Normal
        # route assignment installs this direction before any movement.
        direction = normalized_vector_logic_units(
            tiles_to_logic_units(waypoint.x - previous_position.x),
            tiles_to_logic_units(waypoint.y - previous_position.y),
            256,
        )
        mover._native_ground_route_direction = direction
    direction_x, direction_y = direction
    remaining_x = tiles_to_logic_units(waypoint.x - mover.position.x)
    remaining_y = tiles_to_logic_units(waypoint.y - mover.position.y)
    projected_remaining = (
        trunc_div(direction_y * remaining_y, 256)
        + trunc_div(direction_x * remaining_x, 256)
    )
    if projected_remaining < 1001:
        route_cells.pop(0)
        _set_native_route_direction(mover, route_cells[0] if route_cells else None)
        return True
    return False


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
