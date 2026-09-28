"""Resident fallback Crowns differ from live in-sight combat targets."""
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop


def crowns(battle, owner):
    return {e._crown_tower_slot:e for e in battle.entities.values()
            if e.player_id == owner and getattr(e,'_crown_tower_slot',None)}


@pytest.mark.parametrize('fast_path',[False,True])
def test_depleted_far_crown_remains_a_fallback_only_until_removal(fast_path):
    battle=BattleState(fast_path=fast_path)
    targets=crowns(battle,1)
    troop=battle._spawn_entity(Troop,Position(14.579,13.952),0,battle.card_loader.get_card('IceGolem'))
    princess,king=targets['right'],targets['king']
    assert not troop.is_within_sight(princess)
    before=troop._native_movement_waypoint(princess,battle)
    princess.take_damage(princess.hitpoints)
    battle._combat_phase_eligible_ids=frozenset([troop.id])
    if fast_path:
        battle._refresh_fast_path_caches()
    selected=troop.get_nearest_target(battle.entities)
    assert selected is princess
    assert not troop._is_valid_target(princess)
    assert troop._native_movement_waypoint(selected,battle)==before
    battle._cleanup_dead_entities()
    assert troop.get_nearest_target(battle.entities) is king


@pytest.mark.parametrize('fast_path',[False,True])
def test_skeletons_choose_live_in_sight_king_on_princess_depletion(fast_path):
    # Native mix0 recorded interval2188: Knight kills the right Princess
    # before Skeleton combat. Both Skeletons turn toward the King that frame.
    battle=BattleState(fast_path=fast_path)
    targets=crowns(battle,0)
    troop=battle._spawn_entity(Troop,Position(13.484,8.745),1,battle.card_loader.get_card('Skeletons'))
    princess,king=targets['right'],targets['king']
    old_route=troop._native_movement_waypoint(princess,battle)
    assert troop.is_within_sight(king)
    princess.take_damage(princess.hitpoints)
    battle._combat_phase_eligible_ids=frozenset([troop.id])
    if fast_path:
        battle._refresh_fast_path_caches()
    assert troop.get_nearest_target(battle.entities) is king
    assert troop._native_movement_waypoint(king,battle)!=old_route


def test_depleted_crown_is_not_a_fallback_outside_active_combat_phase():
    battle=BattleState()
    targets=crowns(battle,1)
    troop=battle._spawn_entity(Troop,Position(14.579,13.952),0,battle.card_loader.get_card('IceGolem'))
    targets['right'].take_damage(targets['right'].hitpoints)
    assert troop.get_nearest_target(battle.entities) is targets['king']


def test_live_crown_retarget_is_not_deferred():
    battle=BattleState()
    targets=crowns(battle,1)
    troop=battle._spawn_entity(Troop,Position(14.5,13.5),0,battle.card_loader.get_card('IceGolem'))
    troop._native_movement_waypoint(targets['right'],battle)
    troop._native_movement_waypoint(targets['king'],battle)
    assert troop._native_navigation_target_id==targets['king'].id
