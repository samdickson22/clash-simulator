"""Native hit commitment uses cycle phase, not the remaining load alone."""
import pytest

from clasher.arena import Position
from clasher.attack_clock import OrdinaryAttackClock
from clasher.battle import BattleState
from clasher.ordinary_combat_clock import publish


def spawn(battle, name, owner, xy):
    before = set(battle.entities)
    battle._spawn_unit_at_position(Position(*xy), owner, battle.card_loader.get_card(name),
                                  deploy_delay_override=0, snap_to_valid=False)
    return battle.entities[(set(battle.entities)-before).pop()]


@pytest.mark.parametrize('timeline,load,committed', [(2450,650,False), (3750,550,True), (2400,0,False), (2500,650,True)])
def test_knight_commitment_distinguishes_captured_native_phases(timeline, load, committed):
    battle = BattleState()
    knight = spawn(battle, 'Knight', 1, (9,10))
    target = spawn(battle, 'HogRider', 0, (9,14))
    knight._ordinary_clock = OrdinaryAttackClock(1200,700,hit_timeline_ms=timeline,
                                                 load_remaining_ms=load)
    knight._attack_windup_active = True
    publish(knight, knight._ordinary_clock)
    assert not knight.is_within_attack_engagement_reach(target)
    assert knight.is_within_attack_clock_reach(target) is committed


@pytest.mark.parametrize('fast_path', [False,True])
def test_musketeer_releases_lost_hog_for_farther_visible_crown(fast_path):
    battle = BattleState(fast_path=fast_path)
    musketeer = spawn(battle, 'Musketeer', 0, (2.825,17.173))
    hog = spawn(battle, 'HogRider', 1, (4.239,9.690))
    crown = next(e for e in battle.entities.values()
                 if e.player_id == 1 and getattr(e, '_crown_tower_slot', None) == 'left')
    musketeer.target_id = hog.id
    musketeer._last_combat_target_id = hog.id
    musketeer._attack_windup_active = True
    musketeer._has_attacked_once = True
    musketeer._ordinary_clock = OrdinaryAttackClock(1000,650,hit_timeline_ms=4750)
    publish(musketeer,musketeer._ordinary_clock)
    assert not musketeer.is_within_sight(hog)
    assert not musketeer.is_within_target_keep_reach(hog)
    assert musketeer.position.distance_to(crown.position) > musketeer.position.distance_to(hog.position)
    musketeer._update_active_combat(battle.dt,battle)
    assert musketeer.target_id == crown.id
    assert musketeer._ordinary_clock.hit_timeline_ms == 0
