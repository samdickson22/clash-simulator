import pytest

from clasher.pathfinding import (
    STANDARD_PATH_HEIGHT,
    STANDARD_PATH_WIDTH,
    _cached_standard_grid_route,
    _native_grid_route,
    _standard_path_cost_map,
    _standard_pathfinder_tile_cost,
)


@pytest.mark.parametrize(
    ("start", "goal", "lane_id", "jump_height"),
    [
        ((5, 18), (5, 48), 1, False),
        ((30, 44), (30, 14), 2, False),
        ((18, 20), (18, 44), 1, True),
    ],
)
def test_cached_standard_route_is_exact_and_immutable(
    start,
    goal,
    lane_id,
    jump_height,
):
    expected = _native_grid_route(
        start,
        goal,
        lambda cell: _standard_pathfinder_tile_cost(
            cell,
            lane_id=lane_id,
            jump_height=jump_height,
        ),
    )

    _cached_standard_grid_route.cache_clear()
    cached = _cached_standard_grid_route(start, goal, lane_id, jump_height)
    cached_again = _cached_standard_grid_route(start, goal, lane_id, jump_height)

    assert cached == (None if expected is None else tuple(expected))
    assert cached_again is cached
    assert _cached_standard_grid_route.cache_info().hits == 1
    if cached:
        mutable_route = list(cached)
        mutable_route.pop()
        assert cached_again == cached


@pytest.mark.parametrize("lane_id", [0, 1, 2])
@pytest.mark.parametrize("jump_height", [False, True])
def test_standard_path_cost_map_is_exact_and_immutable(lane_id, jump_height):
    cost_map = _standard_path_cost_map(lane_id, jump_height)

    assert len(cost_map) == STANDARD_PATH_WIDTH * STANDARD_PATH_HEIGHT
    for cell_y in range(STANDARD_PATH_HEIGHT):
        for cell_x in range(STANDARD_PATH_WIDTH):
            cell = (cell_x, cell_y)
            assert cost_map[cell] == _standard_pathfinder_tile_cost(
                cell,
                lane_id=lane_id,
                jump_height=jump_height,
            )
    assert cost_map.get((-1, 0)) is None
    assert cost_map.get((STANDARD_PATH_WIDTH, STANDARD_PATH_HEIGHT - 1)) is None
    with pytest.raises(TypeError):
        cost_map[(0, 0)] = 999
