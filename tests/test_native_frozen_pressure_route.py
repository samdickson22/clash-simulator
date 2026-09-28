"""Frozen walking routes advance when collision pressure passes a waypoint."""
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop


@pytest.mark.parametrize('fast_path', [False, True])
@pytest.mark.parametrize('frozen_walker,pressure,expected', [
    (True, .1, [(29, 34)]),
    (True, 0, [(29, 33), (29, 34)]),
    (False, .1, [(29, 33), (29, 34)]),
])
def test_pressure_advances_only_retained_frozen_walking_route(fast_path, frozen_walker, pressure, expected):
    battle = BattleState(fast_path=fast_path)
    troop = battle._spawn_entity(Troop, Position(14.75, 15.7), 0, battle.card_loader.get_card('Knight'))
    troop.apply_stun(.5)
    troop._native_moving_when_frozen = frozen_walker
    troop._native_ground_route_cells = [(29, 33), (29, 34)]
    troop._native_ground_route_direction = (0, 256)
    troop._pending_movement_x = 0
    troop._pending_movement_y = pressure
    troop._pending_movement_consumed = False
    troop.finish_movement_tick(battle)
    assert troop._native_ground_route_cells == expected
    assert troop.position.y == pytest.approx(15.7 + pressure)
