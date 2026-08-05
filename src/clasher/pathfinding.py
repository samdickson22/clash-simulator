"""Native-grid ground routing around dynamic arena obstacles.

Clash movement plans on the arena's 500-logic-unit grid.  The runtime follows
the center of the next cell in an eight-neighbour A* path, while the character
movement component still applies its ordinary fixed-point speed for the frame.
"""

from __future__ import annotations

import heapq
from collections.abc import Callable
from typing import TYPE_CHECKING

from .arena import Position
from .kinematics import tiles_to_logic_units, trunc_div
from .native_tilemap import (
    HALF_TILE_LOGIC_UNITS,
    STANDARD_PATH_HEIGHT,
    STANDARD_PATH_WIDTH,
)

if TYPE_CHECKING:
    from .battle import BattleState
    from .entities import Entity


_PLAYER_ZERO_NEIGHBORS: tuple[tuple[int, int, int], ...] = (
    (0, 1, 10),
    (-1, 1, 14),
    (1, 1, 14),
    (-1, 0, 10),
    (1, 0, 10),
    (-1, -1, 14),
    (1, -1, 14),
    (0, -1, 10),
)


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


def _segment_intersects_building(
    start: Position,
    end: Position,
    building_position: Position,
    collision_radius: float,
) -> bool:
    """Fixed-point point-to-segment collision without a floating projection."""

    start_x = tiles_to_logic_units(start.x)
    start_y = tiles_to_logic_units(start.y)
    end_x = tiles_to_logic_units(end.x)
    end_y = tiles_to_logic_units(end.y)
    point_x = tiles_to_logic_units(building_position.x)
    point_y = tiles_to_logic_units(building_position.y)
    radius = tiles_to_logic_units(collision_radius)

    segment_x = end_x - start_x
    segment_y = end_y - start_y
    point_delta_x = point_x - start_x
    point_delta_y = point_y - start_y
    segment_length_sq = segment_x * segment_x + segment_y * segment_y
    if segment_length_sq == 0:
        return bool(
            point_delta_x * point_delta_x + point_delta_y * point_delta_y
            < radius * radius
        )

    projection = point_delta_x * segment_x + point_delta_y * segment_y
    if projection <= 0:
        distance_sq = (
            point_delta_x * point_delta_x + point_delta_y * point_delta_y
        )
        return bool(distance_sq < radius * radius)
    if projection >= segment_length_sq:
        end_delta_x = point_x - end_x
        end_delta_y = point_y - end_y
        distance_sq = end_delta_x * end_delta_x + end_delta_y * end_delta_y
        return bool(distance_sq < radius * radius)

    cross = point_delta_x * segment_y - point_delta_y * segment_x
    return bool(cross * cross < radius * radius * segment_length_sq)


def _building_topology(
    battle_state: "BattleState",
    mover: "Entity",
    desired: Position,
    ignored_building_id: int | None,
) -> tuple[bool, tuple[tuple[int, int, int, int], ...]]:
    mover_radius = min(float(mover.get_collision_radius()), 0.5)
    topology: list[tuple[int, int, int, int]] = []
    intersects = False
    for entity in battle_state.entities.values():
        if (
            getattr(entity, "entity_kind", 4) != 1
            or not entity.is_alive
            or entity.id == ignored_building_id
        ):
            continue
        building_radius = float(entity.get_collision_radius())
        topology.append(
            (
                entity.id,
                tiles_to_logic_units(entity.position.x),
                tiles_to_logic_units(entity.position.y),
                tiles_to_logic_units(building_radius),
            )
        )
        if _segment_intersects_building(
            mover.position,
            desired,
            entity.position,
            mover_radius + building_radius,
        ):
            intersects = True
    return intersects, tuple(topology)


def _static_path_is_blocked(
    battle_state: "BattleState",
    start: Position,
    desired: Position,
) -> bool:
    """Check the half-tile cells crossed by the direct movement sightline."""

    start_cell = _cell_for_position(start)
    desired_cell = _cell_for_position(desired)
    delta_x = desired_cell[0] - start_cell[0]
    delta_y = desired_cell[1] - start_cell[1]
    steps = max(abs(delta_x), abs(delta_y))
    if steps == 0:
        return not battle_state.arena.is_walkable(desired)
    for step in range(1, steps + 1):
        cell = (
            start_cell[0] + trunc_div(delta_x * step, steps),
            start_cell[1] + trunc_div(delta_y * step, steps),
        )
        if not battle_state.arena.is_walkable(_cell_center(cell)):
            return True
    return False


def _hover_path_is_blocked(
    battle_state: "BattleState",
    start: Position,
    desired: Position,
) -> bool:
    """Check permanent arena blockers while allowing water traversal."""

    start_cell = _cell_for_position(start)
    desired_cell = _cell_for_position(desired)
    delta_x = desired_cell[0] - start_cell[0]
    delta_y = desired_cell[1] - start_cell[1]
    steps = max(abs(delta_x), abs(delta_y))
    if steps == 0:
        return battle_state.arena.is_blocked_position(desired)
    for step in range(1, steps + 1):
        cell = (
            start_cell[0] + trunc_div(delta_x * step, steps),
            start_cell[1] + trunc_div(delta_y * step, steps),
        )
        if battle_state.arena.is_blocked_position(_cell_center(cell)):
            return True
    return False


def _relative_cell_key(
    cell: tuple[int, int],
    player_id: int,
) -> tuple[int, int]:
    if player_id == 0:
        return cell[1], cell[0]
    return (
        STANDARD_PATH_HEIGHT - 1 - cell[1],
        STANDARD_PATH_WIDTH - 1 - cell[0],
    )


def _nearest_passable_goal(
    desired_cell: tuple[int, int],
    player_id: int,
    passable: Callable[[tuple[int, int]], bool],
) -> tuple[int, int] | None:
    if passable(desired_cell):
        return desired_cell

    best_cell: tuple[int, int] | None = None
    best_key: tuple[int, tuple[int, int]] | None = None
    max_radius = max(STANDARD_PATH_WIDTH, STANDARD_PATH_HEIGHT)
    for radius in range(1, max_radius + 1):
        # Every not-yet-visited cell is at least ``radius`` cells away. Once
        # that lower bound exceeds the best Euclidean distance, no wider ring
        # can replace the native closest-cell choice.
        if best_key is not None and radius * radius > best_key[0]:
            break
        min_x = desired_cell[0] - radius
        max_x = desired_cell[0] + radius
        min_y = desired_cell[1] - radius
        max_y = desired_cell[1] + radius
        ring: set[tuple[int, int]] = set()
        for cell_x in range(min_x, max_x + 1):
            ring.add((cell_x, min_y))
            ring.add((cell_x, max_y))
        for cell_y in range(min_y + 1, max_y):
            ring.add((min_x, cell_y))
            ring.add((max_x, cell_y))
        for cell in ring:
            if not passable(cell):
                continue
            key = (
                (cell[0] - desired_cell[0]) ** 2
                + (cell[1] - desired_cell[1]) ** 2,
                _relative_cell_key(cell, player_id),
            )
            if best_key is None or key < best_key:
                best_cell = cell
                best_key = key
    return best_cell


def _heuristic(
    cell: tuple[int, int],
    goal: tuple[int, int],
) -> int:
    # Native LogicPathFinder uses 10 * Chebyshev distance.
    return 10 * max(abs(goal[0] - cell[0]), abs(goal[1] - cell[1]))


def ground_path_waypoint(
    battle_state: "BattleState",
    mover: "Entity",
    desired: Position,
    *,
    ignored_building_id: int | None = None,
) -> Position:
    """Return the next native half-tile waypoint when a building blocks sightline."""

    from .unit_traits import is_hover_unit_card

    hovering = is_hover_unit_card(getattr(mover, "card_stats", None))
    if hovering:
        building_intersects = False
        topology = ()
    else:
        building_intersects, topology = _building_topology(
            battle_state,
            mover,
            desired,
            ignored_building_id,
        )
    crosses_river_band = (
        min(mover.position.y, desired.y)
        <= battle_state.arena.RIVER_Y2 + 1.0
        and max(mover.position.y, desired.y) >= battle_state.arena.RIVER_Y1
    )
    can_jump_directly = bool(
        getattr(getattr(mover, "card_stats", None), "jump_height", None)
        and not getattr(mover, "_river_jump_blocked", False)
        and crosses_river_band
    )
    if hovering:
        static_path_blocked = _hover_path_is_blocked(
            battle_state,
            mover.position,
            desired,
        )
    else:
        static_path_blocked = (
            False
            if can_jump_directly
            else _static_path_is_blocked(
                battle_state,
                mover.position,
                desired,
            )
        )
    if not building_intersects and not static_path_blocked:
        return desired

    start = _cell_for_position(mover.position)
    desired_cell = _cell_for_position(desired)
    cache_key = (
        start,
        desired_cell,
        mover.player_id,
        tiles_to_logic_units(min(float(mover.get_collision_radius()), 0.5)),
        ignored_building_id,
        topology,
    )
    if getattr(mover, "_ground_path_cache_key", None) == cache_key:
        cached_waypoint = getattr(mover, "_ground_path_cache_waypoint", None)
        if isinstance(cached_waypoint, Position):
            return cached_waypoint

    passable_cache: dict[tuple[int, int], bool] = {start: True}

    def passable(cell: tuple[int, int]) -> bool:
        cached = passable_cache.get(cell)
        if cached is not None:
            return cached
        cell_x, cell_y = cell
        result = bool(
            0 <= cell_x < STANDARD_PATH_WIDTH
            and 0 <= cell_y < STANDARD_PATH_HEIGHT
            and battle_state.is_ground_position_walkable(
                _cell_center(cell),
                mover,
                ignore_building_id=ignored_building_id,
            )
        )
        passable_cache[cell] = result
        return result

    goal = _nearest_passable_goal(
        desired_cell,
        mover.player_id,
        passable,
    )
    if goal is None:
        return desired
    if goal == start:
        waypoint = _cell_center(start)
        mover._ground_path_cache_key = cache_key
        mover._ground_path_cache_waypoint = waypoint
        return waypoint

    direction = 1 if mover.player_id == 0 else -1
    neighbors = tuple(
        (delta_x * direction, delta_y * direction, step_cost)
        for delta_x, delta_y, step_cost in _PLAYER_ZERO_NEIGHBORS
    )
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    best_cost: dict[tuple[int, int], int] = {start: 0}
    insertion_order = 0
    frontier: list[tuple[int, int, int, int, tuple[int, int]]] = [
        (_heuristic(start, goal), _heuristic(start, goal), 0, 0, start)
    ]

    while frontier:
        _, _, _, queued_cost, current = heapq.heappop(frontier)
        if queued_cost != best_cost.get(current):
            continue
        if current == goal:
            break
        current_cost = queued_cost
        for delta_x, delta_y, step_cost in neighbors:
            neighbor = (current[0] + delta_x, current[1] + delta_y)
            if not passable(neighbor):
                continue
            new_cost = current_cost + step_cost
            if new_cost >= best_cost.get(neighbor, 1 << 60):
                continue
            best_cost[neighbor] = new_cost
            came_from[neighbor] = current
            insertion_order += 1
            heuristic = _heuristic(neighbor, goal)
            heapq.heappush(
                frontier,
                (
                    new_cost + heuristic,
                    heuristic,
                    insertion_order,
                    new_cost,
                    neighbor,
                ),
            )
    else:
        return desired

    next_cell = goal
    while came_from.get(next_cell) != start:
        parent = came_from.get(next_cell)
        if parent is None:
            return desired
        next_cell = parent
    waypoint = _cell_center(next_cell)
    mover._ground_path_cache_key = cache_key
    mover._ground_path_cache_waypoint = waypoint
    return waypoint
