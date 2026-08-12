from __future__ import annotations

import pytest

from clasher import entities as entities_module
from clasher import pathfinding as pathfinding_module
from clasher import unit_traits
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.pathfinding import ground_path_waypoint
from clasher.rl.determinism_check import compute_rollout_digest


def _spawn_troop(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(position, player_id, stats)
    return next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )


@pytest.mark.parametrize("card_name", ["Knight", "RoyalGhost"])
def test_cached_path_hover_trait_matches_runtime_classification(
    monkeypatch,
    card_name: str,
):
    battle = BattleState()
    battle.entities.clear()
    mover = _spawn_troop(battle, card_name, 0, Position(9.0, 12.0))
    target = _spawn_troop(battle, "Knight", 1, Position(9.0, 20.0))

    monkeypatch.setattr(
        pathfinding_module,
        "_USE_CACHED_GROUND_PATH_HOVER_TRAIT",
        False,
    )
    monkeypatch.setattr(
        entities_module,
        "_USE_CACHED_PATHFIND_HOVER_TRAIT",
        False,
    )
    runtime_ground = ground_path_waypoint(
        battle,
        mover,
        target.position,
        target_entity=target,
    )
    runtime_entity = mover._get_pathfind_target(target, battle)

    mover._ground_path_cache_key = None
    mover._native_ground_route_cells = []
    monkeypatch.setattr(
        pathfinding_module,
        "_USE_CACHED_GROUND_PATH_HOVER_TRAIT",
        True,
    )
    monkeypatch.setattr(
        entities_module,
        "_USE_CACHED_PATHFIND_HOVER_TRAIT",
        True,
    )
    cached_ground = ground_path_waypoint(
        battle,
        mover,
        target.position,
        target_entity=target,
    )
    cached_entity = mover._get_pathfind_target(target, battle)

    assert cached_ground == runtime_ground
    assert cached_entity == runtime_entity


def test_cached_path_hover_trait_avoids_runtime_card_lookup(monkeypatch):
    battle = BattleState()
    battle.entities.clear()
    mover = _spawn_troop(battle, "RoyalGhost", 0, Position(9.0, 12.0))
    target = _spawn_troop(battle, "Knight", 1, Position(9.0, 20.0))

    def fail_lookup(_card_stats):
        raise AssertionError("cached path selection must not reclassify card data")

    monkeypatch.setattr(unit_traits, "is_hover_unit_card", fail_lookup)
    monkeypatch.setattr(
        pathfinding_module,
        "_USE_CACHED_GROUND_PATH_HOVER_TRAIT",
        True,
    )
    monkeypatch.setattr(
        entities_module,
        "_USE_CACHED_PATHFIND_HOVER_TRAIT",
        True,
    )

    ground_path_waypoint(
        battle,
        mover,
        target.position,
        target_entity=target,
    )
    mover._get_pathfind_target(target, battle)


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_cached_path_hover_trait_preserves_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path: str,
):
    common = {
        "seed": 8873,
        "decisions": 32,
        "decks_path": "decks.json",
        "decision_interval": 8,
        "max_ticks": 2048,
        "mirror_match": False,
        "quiet_engine": True,
        "engine_fast_path": engine_fast_path,
        "reward_profile": "defense-v2",
    }

    monkeypatch.setattr(
        pathfinding_module,
        "_USE_CACHED_GROUND_PATH_HOVER_TRAIT",
        False,
    )
    monkeypatch.setattr(
        entities_module,
        "_USE_CACHED_PATHFIND_HOVER_TRAIT",
        False,
    )
    runtime = compute_rollout_digest(**common)
    monkeypatch.setattr(
        pathfinding_module,
        "_USE_CACHED_GROUND_PATH_HOVER_TRAIT",
        True,
    )
    monkeypatch.setattr(
        entities_module,
        "_USE_CACHED_PATHFIND_HOVER_TRAIT",
        True,
    )
    cached = compute_rollout_digest(**common)

    assert cached.sha256 == runtime.sha256
    assert cached.mask_shadow_checks == runtime.mask_shadow_checks
    assert cached.mask_shadow_mismatches == runtime.mask_shadow_mismatches == 0
