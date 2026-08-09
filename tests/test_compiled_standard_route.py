import pytest

from clasher import pathfinding


@pytest.mark.skipif(
    pathfinding._compiled_standard_grid_route_indices is None,
    reason="Numba accelerator unavailable",
)
def test_compiled_standard_routes_match_python_reference(monkeypatch):
    starts = [
        ((index * 11 + 3) % pathfinding.STANDARD_PATH_WIDTH,
         (index * 17 + 5) % pathfinding.STANDARD_PATH_HEIGHT)
        for index in range(24)
    ]
    goals = [
        ((index * 7 + 19) % pathfinding.STANDARD_PATH_WIDTH,
         (index * 13 + 29) % pathfinding.STANDARD_PATH_HEIGHT)
        for index in range(24)
    ]
    starts.extend(((0, 0), (35, 63), (18, 32)))
    goals.extend(((0, 0), (0, 0), (18, 32)))

    for lane_id in (0, 1, 2):
        for jump_height in (False, True):
            for start, goal in zip(starts, goals):
                monkeypatch.setattr(
                    pathfinding,
                    "_USE_COMPILED_STANDARD_ROUTE",
                    False,
                )
                pathfinding._cached_standard_grid_route.cache_clear()
                expected = pathfinding._cached_standard_grid_route(
                    start,
                    goal,
                    lane_id,
                    jump_height,
                )

                monkeypatch.setattr(
                    pathfinding,
                    "_USE_COMPILED_STANDARD_ROUTE",
                    True,
                )
                pathfinding._cached_standard_grid_route.cache_clear()
                actual = pathfinding._cached_standard_grid_route(
                    start,
                    goal,
                    lane_id,
                    jump_height,
                )

                assert actual == expected
