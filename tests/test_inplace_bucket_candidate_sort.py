from __future__ import annotations

import pytest

from clasher import battle as battle_module
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
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


def test_inplace_bucket_sort_preserves_entity_encounter_order(monkeypatch):
    battle = BattleState(fast_path=True)
    _spawn_troop(battle, "Knight", 0, Position(9.0, 14.0))
    _spawn_troop(battle, "Archers", 1, Position(7.0, 16.0))
    _spawn_troop(battle, "Knight", 1, Position(11.0, 16.0))
    battle._refresh_fast_path_caches()

    monkeypatch.setattr(battle_module, "_USE_INPLACE_BUCKET_ID_SORT", False)
    allocated = battle.iter_entities_in_radius(Position(9.0, 15.0), 5.0)
    monkeypatch.setattr(battle_module, "_USE_INPLACE_BUCKET_ID_SORT", True)
    inplace = battle.iter_entities_in_radius(Position(9.0, 15.0), 5.0)

    assert [entity.id for entity in inplace] == [entity.id for entity in allocated]
    assert inplace == sorted(inplace, key=lambda entity: entity.id)


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_inplace_bucket_sort_preserves_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path: str,
):
    common = {
        "seed": 8849,
        "decisions": 32,
        "decks_path": "decks.json",
        "decision_interval": 8,
        "max_ticks": 2048,
        "mirror_match": False,
        "quiet_engine": True,
        "engine_fast_path": engine_fast_path,
        "reward_profile": "defense-v2",
    }

    monkeypatch.setattr(battle_module, "_USE_INPLACE_BUCKET_ID_SORT", False)
    allocated = compute_rollout_digest(**common)
    monkeypatch.setattr(battle_module, "_USE_INPLACE_BUCKET_ID_SORT", True)
    inplace = compute_rollout_digest(**common)

    assert inplace.sha256 == allocated.sha256
    assert inplace.decisions == allocated.decisions
    assert inplace.episodes_finished == allocated.episodes_finished
    assert inplace.mask_shadow_checks == allocated.mask_shadow_checks
    assert inplace.mask_shadow_mismatches == allocated.mask_shadow_mismatches == 0
