"""Idle collision pressure obeys native half-cell river boundaries."""
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.native_tilemap import clip_native_ground_pressure
from clasher.unit_traits import is_air_unit_card


@pytest.mark.parametrize("start,delta,expected", [
    ((15954, 14981), (137, 50), (16091, 14999)),
    ((16000, 17020), (20, -50), (16020, 17000)),
    ((14500, 14981), (0, 50), (14500, 15031)),
    ((14500, 17020), (0, -50), (14500, 16970)),
    ((15490, 16000), (50, 0), (15499, 16000)),
    ((13510, 16000), (-50, 0), (13500, 16000)),
    ((14500, 14000), (50, 50), (14550, 14050)),
])
def test_native_half_cell_pressure_edges(start, delta, expected):
    assert clip_native_ground_pressure(*start, *delta) == expected


@pytest.mark.parametrize("card,expected_y", [
    ("Skeletons", 14999), ("Minions", 15031), ("RoyalGhost", 15031),
])
@pytest.mark.parametrize("deploying", [False, True])
def test_idle_ground_pressure_and_water_crossing_controls(card, expected_y, deploying):
    battle = BattleState()
    unit = battle._spawn_entity(Troop, Position(15.954, 14.981), 0, battle.card_loader.get_card(card))
    unit.deploy_delay_remaining = .7 if deploying else 0
    expected_y = expected_y if deploying else 15031
    unit.is_air_unit = is_air_unit_card(unit.card_stats)
    unit._pending_movement_x = .137
    unit._pending_movement_y = .050
    unit._pending_movement_consumed = False
    unit.finish_movement_tick(battle)
    assert (round(unit.position.x * 1000), round(unit.position.y * 1000)) == (16091, expected_y)
