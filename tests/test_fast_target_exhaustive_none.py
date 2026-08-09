import pytest

import clasher.entities as entity_module
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop


def _spawn(battle: BattleState, card: str, player_id: int, position: Position):
    stats = battle.card_loader.get_card(card)
    assert stats is not None
    battle._spawn_troop(position, player_id, stats)
    troop = battle.entities[battle.next_entity_id - 1]
    assert isinstance(troop, Troop)
    troop.deploy_delay_remaining = 0.0
    troop.placement_pending = False
    return troop


@pytest.mark.parametrize("include_crown_fallback", [False, True])
def test_exhaustive_fast_none_matches_scalar_fallback(
    monkeypatch,
    include_crown_fallback,
):
    battle = BattleState(fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker = _spawn(battle, "Knight", 0, Position(2.5, 2.5))
    _spawn(battle, "Knight", 1, Position(15.5, 29.5))
    battle._refresh_fast_path_caches()

    monkeypatch.setattr(
        entity_module,
        "_FAST_TARGET_NONE_IS_EXHAUSTIVE",
        False,
    )
    expected = attacker.get_nearest_target(
        battle.entities,
        include_crown_fallback=include_crown_fallback,
    )
    monkeypatch.setattr(
        entity_module,
        "_FAST_TARGET_NONE_IS_EXHAUSTIVE",
        True,
    )
    actual = attacker.get_nearest_target(
        battle.entities,
        include_crown_fallback=include_crown_fallback,
    )

    assert actual is expected is None


def test_non_null_fast_candidate_keeps_scalar_mechanics_validation(monkeypatch):
    battle = BattleState(fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    attacker = _spawn(battle, "Knight", 0, Position(9.0, 10.0))
    target = _spawn(battle, "Knight", 1, Position(9.0, 11.0))
    alternative = _spawn(battle, "Knight", 1, Position(9.0, 12.0))

    class RejectTarget:
        def allows_target(self, source, candidate):
            return candidate is not target

    attacker.mechanics.append(RejectTarget())
    battle._refresh_fast_path_caches()

    monkeypatch.setattr(
        entity_module,
        "_FAST_TARGET_NONE_IS_EXHAUSTIVE",
        True,
    )
    assert attacker.get_nearest_target(battle.entities) is alternative
