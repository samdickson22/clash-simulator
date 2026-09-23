from __future__ import annotations

import random

import pytest

from clasher import pathfinding
from clasher.rl.determinism_check import compute_rollout_digest


@pytest.mark.parametrize("seed", range(5))
def test_row_interval_native_route_goal_matches_full_scan(seed: int) -> None:
    rng = random.Random(seed)
    for _ in range(2_000):
        args = (
            rng.randrange(-2_000, 20_001),
            rng.randrange(-2_000, 34_001),
            rng.randrange(-2_000, 20_001),
            rng.randrange(-2_000, 34_001),
            rng.randrange(0, 8_001),
        )
        assert (
            pathfinding._compute_native_route_goal_cell_units_row_interval(
                *args
            )
            == pathfinding._compute_native_route_goal_cell_units(*args)
        )


@pytest.mark.skipif(
    pathfinding._compiled_native_route_goal_cell_units_row_interval_raw is None,
    reason="Numba is unavailable",
)
@pytest.mark.parametrize("seed", range(5))
def test_compiled_row_interval_native_route_goal_matches_python(seed: int) -> None:
    rng = random.Random(seed + 10_000)
    for _ in range(2_000):
        args = (
            rng.randrange(-2_000, 20_001),
            rng.randrange(-2_000, 34_001),
            rng.randrange(-2_000, 20_001),
            rng.randrange(-2_000, 34_001),
            rng.randrange(0, 8_001),
        )
        assert (
            pathfinding._compute_native_route_goal_cell_units_row_interval_compiled(
                *args
            )
            == pathfinding._compute_native_route_goal_cell_units_row_interval(
                *args
            )
        )


def test_compiled_row_interval_native_route_goal_falls_back_without_numba(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pathfinding,
        "_compiled_native_route_goal_cell_units_row_interval_raw",
        None,
    )
    args = (9_000, 28_000, 9_000, 16_000, 5_500)
    assert (
        pathfinding._compute_native_route_goal_cell_units_row_interval_compiled(
            *args
        )
        == pathfinding._compute_native_route_goal_cell_units_row_interval(*args)
    )


@pytest.mark.parametrize(
    "args",
    [
        (250, 250, 250, 250, 0),
        (500, 500, 500, 500, 250),
        (0, 0, 18_000, 32_000, 5_500),
        (18_000, 32_000, 0, 0, 5_500),
        (9_000, 16_000, 9_000, 16_000, 8_000),
        (9_000, 16_000, 9_250, 16_250, 354),
    ],
)
def test_row_interval_native_route_goal_matches_full_scan_boundaries(
    args: tuple[int, int, int, int, int],
) -> None:
    assert pathfinding._compute_native_route_goal_cell_units_row_interval(
        *args
    ) == pathfinding._compute_native_route_goal_cell_units(*args)


def test_row_interval_native_route_goal_preserves_fast_path_rollout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    common = {
        "seed": 4321,
        "decisions": 64,
        "decks_path": "decks.json",
        "decision_interval": 8,
        "max_ticks": 9090,
        "mirror_match": False,
        "quiet_engine": True,
        "reward_profile": "defense-v2",
    }
    results = {}
    for row_interval in (False, True):
        monkeypatch.setattr(
            pathfinding,
            "_USE_ROW_INTERVAL_NATIVE_ROUTE_GOAL",
            row_interval,
        )
        pathfinding._cached_native_route_goal_cell_units.cache_clear()
        pathfinding._cached_native_route_goal_cell_units_full_scan.cache_clear()
        results[row_interval] = {
            mode: compute_rollout_digest(**common, engine_fast_path=mode)
            for mode in ("off", "shadow", "on")
        }

    hashes = {
        digest.sha256
        for variants in results.values()
        for digest in variants.values()
    }
    assert len(hashes) == 1
    for variants in results.values():
        assert variants["shadow"].mask_shadow_checks > 0
        assert variants["shadow"].mask_shadow_mismatches == 0
