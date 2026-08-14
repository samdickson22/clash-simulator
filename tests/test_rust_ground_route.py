from __future__ import annotations

import pytest

from clasher.pathfinding import (
    STANDARD_PATH_HEIGHT,
    STANDARD_PATH_WIDTH,
    _native_standard_grid_route,
    _standard_path_cost_grid,
)
from clasher.rust_core import rust_core_available, rust_standard_grid_route

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


@pytest.mark.parametrize("lane_id", [0, 1, 2])
@pytest.mark.parametrize("jump_height", [False, True])
def test_rust_standard_routes_match_exact_python_heap(
    lane_id: int,
    jump_height: bool,
) -> None:
    starts = [
        (
            (index * 11 + 3) % STANDARD_PATH_WIDTH,
            (index * 17 + 5) % STANDARD_PATH_HEIGHT,
        )
        for index in range(16)
    ]
    goals = [
        (
            (index * 7 + 19) % STANDARD_PATH_WIDTH,
            (index * 13 + 29) % STANDARD_PATH_HEIGHT,
        )
        for index in range(16)
    ]
    starts.extend([(0, 0), (35, 63), (18, 32)])
    goals.extend([(0, 0), (0, 0), (18, 32)])
    costs = _standard_path_cost_grid(lane_id, jump_height)

    for start, goal in zip(starts, goals, strict=True):
        expected = _native_standard_grid_route(start, goal, costs)
        actual = rust_standard_grid_route(
            start,
            goal,
            lane_id,
            jump_height,
        )
        assert actual == (None if expected is None else tuple(expected))


@pytest.mark.parametrize(
    ("start", "goal"),
    [
        ((-1, 0), (0, 0)),
        ((0, -1), (0, 0)),
        ((0, 0), (STANDARD_PATH_WIDTH, 0)),
        ((0, 0), (0, STANDARD_PATH_HEIGHT)),
    ],
)
def test_rust_standard_route_rejects_out_of_bounds_cells(
    start: tuple[int, int],
    goal: tuple[int, int],
) -> None:
    assert rust_standard_grid_route(start, goal, 1, False) is None
