import copy

import pytest

from clasher import entities as entities_module
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.rl.determinism_check import compute_rollout_digest


def _spawn_knight(battle: BattleState, player_id: int, position: Position) -> Troop:
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_troop(position, player_id, stats)
    return next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )


def test_cached_crown_membership_matches_full_fallback_scan(monkeypatch):
    battle = BattleState(fast_path=True)
    attacker = _spawn_knight(battle, 0, Position(9.0, 8.0))
    battle._refresh_fast_path_caches()

    monkeypatch.setattr(
        entities_module,
        "_USE_CACHED_CROWN_FALLBACK_MEMBERSHIP",
        False,
    )
    scanned = attacker.get_nearest_target(battle.entities)
    monkeypatch.setattr(
        entities_module,
        "_USE_CACHED_CROWN_FALLBACK_MEMBERSHIP",
        True,
    )
    cached = attacker.get_nearest_target(battle.entities)

    assert cached is scanned
    assert cached in battle._crown_target_entities_by_player[1]
    assert all(
        tower.player_id == 1
        for tower in battle._crown_target_entities_by_player[1]
    )


def test_crown_membership_rebuilds_for_death_and_same_size_replacement():
    battle = BattleState(fast_path=True)
    original = battle._crown_target_entities_by_player[1][0]
    original.is_alive = False
    battle._refresh_fast_path_caches()
    assert original not in battle._crown_target_entities_by_player[1]

    replacement = copy.copy(battle._crown_target_entities_by_player[1][0])
    battle.entities[replacement.id] = replacement
    battle._refresh_fast_path_caches()
    assert replacement in battle._crown_target_entities_by_player[1]
    assert all(
        tower is not original
        for tower in battle._crown_target_entities_by_player[1]
    )


def test_crown_membership_is_clone_isolated():
    source = BattleState(fast_path=True)
    cloned = source.clone()

    assert cloned._crown_target_entities_by_player is not (
        source._crown_target_entities_by_player
    )
    for player_id in (0, 1):
        assert cloned._crown_target_entities_by_player[player_id] is not (
            source._crown_target_entities_by_player[player_id]
        )
        assert [tower.id for tower in cloned._crown_target_entities_by_player[player_id]] == [
            tower.id for tower in source._crown_target_entities_by_player[player_id]
        ]
        assert all(
            cloned_tower is not source_tower
            for cloned_tower, source_tower in zip(
                cloned._crown_target_entities_by_player[player_id],
                source._crown_target_entities_by_player[player_id],
            )
        )


def test_static_crown_classification_change_rebuilds_membership():
    battle = BattleState(fast_path=True)
    stats = battle.card_loader.get_card("Cannon")
    assert stats is not None
    building = battle._spawn_entity(Building, Position(9.0, 20.0), 1, stats)
    battle._refresh_fast_path_caches()
    assert building not in battle._crown_target_entities_by_player[1]

    building._is_king_tower = True
    battle.sync_fast_target_static_entity(building)
    assert building in battle._crown_target_entities_by_player[1]


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_cached_crown_membership_preserves_fixed_seed_rollout(
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
        "_USE_CACHED_CROWN_FALLBACK_MEMBERSHIP",
        False,
    )
    scanned = compute_rollout_digest(**common)
    monkeypatch.setattr(
        entities_module,
        "_USE_CACHED_CROWN_FALLBACK_MEMBERSHIP",
        True,
    )
    cached = compute_rollout_digest(**common)

    assert cached.sha256 == scanned.sha256
    assert cached.mask_shadow_mismatches == scanned.mask_shadow_mismatches == 0
