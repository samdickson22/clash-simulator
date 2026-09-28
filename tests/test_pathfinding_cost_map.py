from functools import lru_cache

from clasher import pathfinding
from clasher.rl.determinism_check import compute_rollout_digest


@lru_cache(maxsize=2048)
def _reference_standard_grid_route(start, goal, lane_id, jump_height):
    route = pathfinding._native_grid_route(
        start,
        goal,
        lambda cell: pathfinding._standard_pathfinder_tile_cost(
            cell,
            lane_id=lane_id,
            jump_height=jump_height,
        ),
    )
    return None if route is None else tuple(route)


def test_path_cost_map_preserves_scalar_shadow_and_fast_rollout_hashes(monkeypatch):
    common = {
        "seed": 4321,
        "decisions": 64,
        "decks_path": "decks.json",
        "decision_interval": 8,
        "max_ticks": 9090,
        "mirror_match": False,
        "quiet_engine": True,
    }
    candidate_router = pathfinding._cached_standard_grid_route
    monkeypatch.setattr(
        pathfinding,
        "_cached_standard_grid_route",
        _reference_standard_grid_route,
    )
    _reference_standard_grid_route.cache_clear()
    baseline = compute_rollout_digest(**common, engine_fast_path="off")

    monkeypatch.setattr(
        pathfinding,
        "_cached_standard_grid_route",
        candidate_router,
    )
    candidate_router.cache_clear()
    pathfinding._standard_path_cost_map.cache_clear()
    scalar = compute_rollout_digest(**common, engine_fast_path="off")
    shadow = compute_rollout_digest(**common, engine_fast_path="shadow")
    fast = compute_rollout_digest(**common, engine_fast_path="on")

    assert baseline.sha256 == scalar.sha256 == shadow.sha256 == fast.sha256
    # Compare routers at the current physics version; a historical physics
    # checksum cannot validate this cache optimization after mechanic repairs.
