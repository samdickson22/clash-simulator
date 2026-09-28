"""Native rolling spell rectangles intersect circular troops and square buildings."""
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, RollingProjectile


def actors():
    battle = BattleState()
    before = set(battle.entities)
    battle._spawn_unit_at_position(Position(3.499, 13.5), 0,
                                  battle.card_loader.get_card('Prince'),
                                  deploy_delay_override=0, snap_to_valid=False)
    prince = battle.entities[(set(battle.entities) - before).pop()]
    rolling = RollingProjectile(
        id=999, position=Position(3.5, 14.7), player_id=1, card_stats=None,
        hitpoints=1, max_hitpoints=1, damage=268, range=1.9,
        sight_range=0, radius_y=.6,
    )
    return battle, prince, rolling


def test_captured_log_prince_contact_excludes_tangency():
    _, prince, log = actors()
    # Native mix0-forward snapshot528: contact at distance1200 does not hit.
    # Next interval moves Log to14500 and applies268damage.
    assert prince.get_collision_radius() == .6
    assert not log._hitbox_overlaps_with_rolling_path(prince)
    log.position.y = 14.699
    assert log._hitbox_overlaps_with_rolling_path(prince)
    log.position.y = 14.5
    assert log._hitbox_overlaps_with_rolling_path(prince)


@pytest.mark.parametrize('dx,dy,hit', [(500,500,False), (360,480,False), (359,480,True)])
def test_troop_circle_must_reach_rectangle_corner(dx, dy, hit):
    _, prince, log = actors()
    # Both axis projections overlap, but the circular radius may not reach.
    prince.position = Position(3.5 + 1.9 + dx/1000, 14.7 + .6 + dy/1000)
    assert log._hitbox_overlaps_with_rolling_path(prince) is hit


@pytest.mark.parametrize('axis', ['x', 'y'])
@pytest.mark.parametrize('side,hit', [(-1,True), (1,False)])
def test_square_building_edges_follow_native_half_open_rectangle(axis, side, hit):
    battle, _, log = actors()
    building = battle._spawn_entity(Building, Position(9,10), 0,
                                   battle.card_loader.get_card('Cannon'))
    building.position = Position(log.position.x, log.position.y)
    extent = log.rolling_radius if axis == 'x' else log.radius_y
    setattr(building.position, axis, getattr(log.position, axis)
            + side * (extent + building.get_collision_radius()))
    assert log._hitbox_overlaps_with_rolling_path(building) is hit


def test_directed_boulder_keeps_circular_contact(monkeypatch):
    _, prince, rolling = actors()
    rolling.target_direction_x, rolling.target_direction_y = 1, 1
    calls = []
    monkeypatch.setattr(prince, 'intersects_native_area',
                        lambda center, radius: calls.append((center, radius)) or True)
    assert rolling._hitbox_overlaps_with_rolling_path(prince)
    assert calls == [(rolling.position, rolling.rolling_radius)]
