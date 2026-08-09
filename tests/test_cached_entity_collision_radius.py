from __future__ import annotations

import copy

import pytest

from clasher import entities as entities_module
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rl.determinism_check import compute_rollout_digest


def _spawn_troop(battle: BattleState, card_name: str, position: Position) -> Troop:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(position, 0, stats)
    return next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )


@pytest.mark.parametrize("card_name", ["Skeletons", "Knight", "Giant"])
def test_cached_entity_collision_radius_matches_runtime_resolver(card_name: str):
    troop = _spawn_troop(BattleState(), card_name, Position(9.0, 14.0))
    runtime_radius = float(troop.card_stats.collision_radius or 0.5)

    assert troop.get_collision_radius() == runtime_radius


def test_cached_entity_collision_radius_preserves_explicit_custom_radius():
    battle = BattleState()
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    stats = copy.deepcopy(stats)
    stats.collision_radius = 3.25
    troop = battle._spawn_entity(Troop, Position(9.0, 14.0), 0, stats)

    assert troop.get_collision_radius() == 3.25


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_cached_entity_collision_radius_preserves_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path: str,
):
    common = {
        "seed": 8821,
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
        entities_module,
        "_USE_CACHED_ENTITY_COLLISION_RADIUS",
        False,
    )
    reference = compute_rollout_digest(**common)
    monkeypatch.setattr(
        entities_module,
        "_USE_CACHED_ENTITY_COLLISION_RADIUS",
        True,
    )
    cached = compute_rollout_digest(**common)

    assert cached.sha256 == reference.sha256
    assert cached.decisions == reference.decisions
    assert cached.episodes_finished == reference.episodes_finished
    assert cached.mask_shadow_checks == reference.mask_shadow_checks
    assert cached.mask_shadow_mismatches == reference.mask_shadow_mismatches == 0
