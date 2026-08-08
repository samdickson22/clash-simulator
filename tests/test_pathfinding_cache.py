import pytest

from clasher.pathfinding import (
    _cached_standard_grid_route,
    _native_grid_route,
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
