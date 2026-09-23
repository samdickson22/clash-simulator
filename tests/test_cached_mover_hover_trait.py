from __future__ import annotations

import pytest

from clasher import battle as battle_module
from clasher import unit_traits
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rl.determinism_check import compute_rollout_digest


def _spawn_troop(
    battle: BattleState,
    card_name: str,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(position, 0, stats)
    return next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )


@pytest.mark.parametrize("card_name", ["Knight", "RoyalGhost"])
def test_cached_mover_hover_trait_matches_card_data_lookup(
    monkeypatch,
    card_name: str,
):
    battle = BattleState()
    mover = _spawn_troop(battle, card_name, Position(9.0, 14.0))
    positions = (
        Position(9.0, 14.0),
        Position(9.0, 15.0),
        Position(0.5, 0.5),
    )

    monkeypatch.setattr(battle_module, "_USE_CACHED_MOVER_HOVER_TRAIT", False)
    reference = [
        battle.is_ground_position_walkable(position, mover) for position in positions
    ]
    monkeypatch.setattr(battle_module, "_USE_CACHED_MOVER_HOVER_TRAIT", True)
    cached = [
        battle.is_ground_position_walkable(position, mover) for position in positions
    ]

    assert cached == reference


def test_cached_mover_hover_trait_avoids_runtime_card_data_lookup(monkeypatch):
    battle = BattleState()
    mover = _spawn_troop(battle, "RoyalGhost", Position(9.0, 14.0))

    def fail_lookup(_card_stats):
        raise AssertionError("cached movement must not reclassify immutable card data")

    monkeypatch.setattr(unit_traits, "is_hover_unit_card", fail_lookup)
    monkeypatch.setattr(battle_module, "_USE_CACHED_MOVER_HOVER_TRAIT", True)

    battle.is_ground_position_walkable(Position(9.0, 15.0), mover)


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_cached_mover_hover_trait_preserves_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path: str,
):
    common = {
        "seed": 8783,
        "decisions": 32,
        "decks_path": "decks.json",
        "decision_interval": 8,
        "max_ticks": 2048,
        "mirror_match": False,
        "quiet_engine": True,
        "engine_fast_path": engine_fast_path,
        "reward_profile": "defense-v2",
    }

    monkeypatch.setattr(battle_module, "_USE_CACHED_MOVER_HOVER_TRAIT", False)
    reference = compute_rollout_digest(**common)
    monkeypatch.setattr(battle_module, "_USE_CACHED_MOVER_HOVER_TRAIT", True)
    cached = compute_rollout_digest(**common)

    assert cached.sha256 == reference.sha256
    assert cached.decisions == reference.decisions
    assert cached.episodes_finished == reference.episodes_finished
    assert cached.mask_shadow_checks == reference.mask_shadow_checks
    assert cached.mask_shadow_mismatches == reference.mask_shadow_mismatches == 0
