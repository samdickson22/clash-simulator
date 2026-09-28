"""Native charge progress multiplies movement work before integer division."""
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop


@pytest.mark.parametrize('work,expected', [(0, 0), (1, 3), (9, 30), (42, 140), (60, 200)])
def test_charge_preserves_fractional_tens_of_movement(work, expected):
    battle = BattleState()
    unit = battle._spawn_entity(Troop, Position(3.5, 8.5), 0, battle.card_loader.get_card('DarkPrince'))
    assert unit.card_stats.charge_range == 300
    unit._native_charge_progress = 0
    unit._advance_native_charge(work)
    assert unit._native_charge_progress == expected


def test_slowed_charge_matches_native_twenty_tick_progress():
    # Native slowed Dark Prince uses42work: twentycalls add2800, not2660.
    battle = BattleState()
    unit = battle._spawn_entity(Troop, Position(3.5, 8.5), 0, battle.card_loader.get_card('DarkPrince'))
    unit._native_charge_progress = 0
    for _ in range(20):
        unit._advance_native_charge(42)
    assert unit._native_charge_progress == 2800
