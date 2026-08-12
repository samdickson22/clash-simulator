from __future__ import annotations

import pytest

from clasher import entities as entities_module
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Entity, Troop
from clasher.rl.determinism_check import compute_rollout_digest


def _spawn_one(
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


def test_singleton_shortcut_skips_distance_tie_classification(monkeypatch) -> None:
    battle = BattleState()
    attacker = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 11.0))

    def fail_if_called(entity: Entity) -> bool:
        del entity
        raise AssertionError("singleton target entered tie classification")

    monkeypatch.setattr(
        entities_module,
        "is_native_building_target",
        fail_if_called,
    )

    assert attacker._select_first_nearest_target([(target, 1.0)]) is target


def test_singleton_shortcut_matches_general_path(monkeypatch) -> None:
    battle = BattleState()
    attacker = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 11.0))

    monkeypatch.setattr(
        entities_module,
        "_USE_SINGLETON_TARGET_SELECTION_SHORTCUT",
        False,
    )
    reference = attacker._select_first_nearest_target([(target, 1.0)])
    monkeypatch.setattr(
        entities_module,
        "_USE_SINGLETON_TARGET_SELECTION_SHORTCUT",
        True,
    )
    candidate = attacker._select_first_nearest_target([(target, 1.0)])

    assert candidate is reference is target


def test_multi_candidate_selection_still_uses_native_encounter_tie_order(
    monkeypatch,
) -> None:
    battle = BattleState()
    attacker = _spawn_one(battle, "Knight", 0, Position(9.0, 10.0))
    first = _spawn_one(battle, "Knight", 1, Position(8.0, 11.0))
    second = _spawn_one(battle, "Knight", 1, Position(10.0, 11.0))
    candidates = [(second, 1.0), (first, 1.0)]

    monkeypatch.setattr(
        entities_module,
        "_USE_SINGLETON_TARGET_SELECTION_SHORTCUT",
        False,
    )
    reference = attacker._select_first_nearest_target(candidates)
    monkeypatch.setattr(
        entities_module,
        "_USE_SINGLETON_TARGET_SELECTION_SHORTCUT",
        True,
    )
    candidate = attacker._select_first_nearest_target(candidates)

    assert candidate is reference is second


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_singleton_shortcut_preserves_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path: str,
) -> None:
    common = {
        "seed": 8947,
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
        "_USE_SINGLETON_TARGET_SELECTION_SHORTCUT",
        False,
    )
    reference = compute_rollout_digest(**common)
    monkeypatch.setattr(
        entities_module,
        "_USE_SINGLETON_TARGET_SELECTION_SHORTCUT",
        True,
    )
    candidate = compute_rollout_digest(**common)

    assert candidate.sha256 == reference.sha256
    assert candidate.mask_shadow_checks == reference.mask_shadow_checks
    assert candidate.mask_shadow_mismatches == reference.mask_shadow_mismatches == 0
