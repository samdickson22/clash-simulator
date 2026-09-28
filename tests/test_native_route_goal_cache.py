import pytest

from clasher import pathfinding
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rl.determinism_check import compute_rollout_digest


def _spawn_knight(
    battle: BattleState,
    player_id: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    battle._spawn_troop(position, player_id, stats)
    troop = battle.entities[battle.next_entity_id - 1]
    assert isinstance(troop, Troop)
    troop.deploy_delay_remaining = 0.0
    troop.placement_pending = False
    return troop


@pytest.mark.parametrize("required_range", [0.0, 0.5, 1.0, 2.5, 5.5])
def test_native_route_goal_cache_matches_uncached_grid_queries(
    monkeypatch,
    required_range,
):
    battle = BattleState()
    mover = _spawn_knight(battle, 0, Position(0.25, 0.25))
    target = _spawn_knight(battle, 1, Position(17.75, 31.75))
    cases = [
        (Position(0.25, 0.25), Position(17.75, 31.75)),
        (Position(9.0, 15.5), Position(9.0, 16.5)),
        (Position(7.123, 14.987), Position(10.876, 17.012)),
        (Position(17.75, 31.75), Position(0.25, 0.25)),
    ]

    monkeypatch.setattr(pathfinding, "_USE_NATIVE_ROUTE_GOAL_CACHE", False)
    expected = []
    for mover_position, target_position in cases:
        mover.position = mover_position
        target.position = target_position
        expected.append(
            pathfinding.native_route_goal_cell(
                mover,
                target,
                required_range_tiles=required_range,
            )
        )

    pathfinding._cached_native_route_goal_cell_units.cache_clear()
    monkeypatch.setattr(pathfinding, "_USE_NATIVE_ROUTE_GOAL_CACHE", True)
    actual = []
    for mover_position, target_position in cases:
        mover.position = mover_position
        target.position = target_position
        actual.append(
            pathfinding.native_route_goal_cell(
                mover,
                target,
                required_range_tiles=required_range,
            )
        )

    assert actual == expected
    before = pathfinding._cached_native_route_goal_cell_units.cache_info()
    pathfinding.native_route_goal_cell(
        mover,
        target,
        required_range_tiles=required_range,
    )
    after = pathfinding._cached_native_route_goal_cell_units.cache_info()
    assert after.hits == before.hits + 1


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_native_route_goal_cache_preserves_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path,
):
    common = {
        "seed": 2301,
        "decisions": 32,
        "decks_path": "decks.json",
        "decision_interval": 8,
        "max_ticks": 2048,
        "mirror_match": False,
        "quiet_engine": True,
        "engine_fast_path": engine_fast_path,
        "reward_profile": "defense-v2",
    }

    monkeypatch.setattr(pathfinding, "_USE_NATIVE_ROUTE_GOAL_CACHE", False)
    uncached = compute_rollout_digest(**common)
    pathfinding._cached_native_route_goal_cell_units.cache_clear()
    monkeypatch.setattr(pathfinding, "_USE_NATIVE_ROUTE_GOAL_CACHE", True)
    cached = compute_rollout_digest(**common)

    assert cached.sha256 == uncached.sha256
    assert cached.mask_shadow_mismatches == uncached.mask_shadow_mismatches == 0


def test_route_goal_cache_tracks_changed_building_occupancy(monkeypatch):
    battle = BattleState()
    mover = _spawn_knight(battle, 0, Position(4.25, 8.25))
    target = _spawn_knight(battle, 1, Position(4.25, 11.25))
    occupied = {}
    monkeypatch.setattr(pathfinding, "native_building_cost_cells", lambda _: occupied)
    monkeypatch.setattr(pathfinding, "_USE_NATIVE_ROUTE_GOAL_CACHE", True)
    pathfinding._cached_native_route_goal_cell_units.cache_clear()
    original = pathfinding.native_route_goal_cell(mover, target, required_range_tiles=1.5)
    assert original is not None

    occupied[original] = 1
    changed = pathfinding.native_route_goal_cell(mover, target, required_range_tiles=1.5)
    assert changed != original
    monkeypatch.setattr(pathfinding, "_USE_NATIVE_ROUTE_GOAL_CACHE", False)
    assert changed == pathfinding.native_route_goal_cell(
        mover, target, required_range_tiles=1.5
    )
    occupied.clear()
    monkeypatch.setattr(pathfinding, "_USE_NATIVE_ROUTE_GOAL_CACHE", True)
    assert original == pathfinding.native_route_goal_cell(
        mover, target, required_range_tiles=1.5
    )
