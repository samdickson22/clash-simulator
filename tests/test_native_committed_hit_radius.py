"""Native Knight release at mix1-forward interval2907 includes its own radius."""
import pytest

from clasher.arena import Position
from clasher.battle import BattleState


def actors():
    battle = BattleState()
    tracked = []
    for name, owner, xy in [('Knight', 1, (14.291, 16.357)), ('HogRider', 0, (14.790, 20.091))]:
        before = set(battle.entities)
        battle._spawn_unit_at_position(Position(*xy), owner, battle.card_loader.get_card(name), deploy_delay_override=0, snap_to_valid=False)
        tracked.append(battle.entities[(set(battle.entities) - before).pop()])
    return tracked


def test_native_connected_knight_hit_is_not_discarded():
    knight, hog = actors()
    assert knight.position.distance_to(hog.position) == pytest.approx(3.767194579523064)
    assert not knight.should_cancel_committed_hit(hog)


def test_hit_beyond_complete_radius_is_discarded():
    knight, hog = actors()
    hog.position = Position(knight.position.x, knight.position.y + 3.801)
    assert knight.should_cancel_committed_hit(hog)


def test_attacker_radius_respects_shared_native_flag(monkeypatch):
    knight, hog = actors()
    monkeypatch.setattr('clasher.entities.ADD_CHARACTER_RANGE_TO_RADIUS', False)
    assert knight.should_cancel_committed_hit(hog)
