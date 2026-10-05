"""Player-owned levels scale independent casts and survive public projection."""
import copy
import random

import numpy as np
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.player import PlayerState
from clasher.rl.deck_pool import apply_deck_to_player, apply_ordered_deck_to_player
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.stat_scaling import scale_stat
from clasher.tower_scaling import tower_stat

PILOT = ['Archers', 'Cannon', 'DarkPrince', 'Fireball', 'Giant', 'Goblins',
         'HogRider', 'IceGolem', 'IceSpirit', 'Knight', 'Log', 'Musketeer',
         'Prince', 'Skeletons', 'Tesla', 'Zap']


@pytest.mark.parametrize('level', [10, 11, 12])
def test_all_pilot_card_stats_resolve_per_player_without_loader_mutation(level):
    battle = BattleState(players=[PlayerState(0, card_levels=dict.fromkeys(PILOT, level)), PlayerState(1)])
    for name in PILOT:
        _, owned, spell = battle.resolve_card_play(0, name)
        _, other, _ = battle.resolve_card_play(1, name)
        assert owned.level == level
        assert other.level == 11
        assert battle.card_loader.get_card(name).level == 11
        if spell is not None:
            assert spell.level == level
        else:
            assert owned.scaled_hitpoints == scale_stat(owned.hitpoints, level)
            assert owned.scaled_damage == scale_stat(owned.damage, level)


@pytest.mark.parametrize('owner', [0, 1])
def test_mixed_deployed_levels_and_towers_emit_actual_public_levels(owner):
    battle = BattleState(players=[PlayerState(0, card_levels={'Knight':10}, tower_level=10),
                                 PlayerState(1, card_levels={'Knight':12}, tower_level=12)])
    for pid, y, level in [(0, 10, 10), (1, 22, 12)]:
        battle.players[pid].hand = ['Knight']
        battle.players[pid].elixir = 10
        assert battle.deploy_card(pid, 'Knight', Position(8, y))
        troop = next(e for e in battle.entities.values() if isinstance(e, Troop) and e.player_id == pid)
        assert troop.max_hitpoints == scale_stat(690, level)
    builder = StructuredObservationBuilder(card_vocab=['Knight'], public_entity_levels=True)
    view = builder.build_actor(battle, owner)
    assert sorted(view.entity_levels[view.entity_mask]) == [10]*4 + [12]*4
    for pid, level in [(0,10), (1,12)]:
        towers = [e for e in battle.entities.values() if e.player_id == pid and not isinstance(e,Troop)]
        assert sorted(e.hitpoints for e in towers) == ([2786,2786,4392] if level == 10 else [3346,3346,5304])
        assert all(e.damage == (99 if level == 10 else 119) for e in towers)
        assert all(e.card_stats.projectile_data['damage'] == e.damage for e in towers)
        assert battle._starting_total_tower_hp[pid] == sum(e.max_hitpoints for e in towers)


def test_explicit_level11_preserves_default_battle_and_action_result():
    default = BattleState()
    explicit = BattleState(players=[PlayerState(0, card_levels={'Knight':11}, tower_level=11),
                                   PlayerState(1, card_levels={'Knight':11}, tower_level=11)])
    builder = StructuredObservationBuilder(card_vocab=['Knight'], public_entity_levels=True)
    for battle in [default, explicit]:
        assert battle.deploy_card(0, 'Knight', Position(8,10))
        for _ in range(12):
            battle.step()
    for key in ['entity_ids','entity_features','entity_mask','entity_levels','global_features']:
        np.testing.assert_array_equal(getattr(builder.build_actor(default,0),key),
                                      getattr(builder.build_actor(explicit,0),key))


def test_queued_spells_capture_owned_level_and_do_not_change_other_seat():
    battle = BattleState(players=[PlayerState(0, card_levels={'Zap':10}), PlayerState(1, card_levels={'Zap':12})])
    for pid in [0,1]:
        battle.players[pid].hand = ['Zap']
        battle._spawn_troop(Position(8, 16), pid, battle.card_loader.get_card('Knight'))
    victims = [e for e in battle.entities.values() if isinstance(e,Troop)]
    before = {e.player_id:e.hitpoints for e in victims}
    assert battle.deploy_card(0,'Zap',Position(8,16))
    assert battle.deploy_card(1,'Zap',Position(8,16))
    battle.players[0].set_card_levels({'Zap':12})
    for state in [battle, copy.deepcopy(battle)]:
        state.step()
        for e in state.entities.values():
            if isinstance(e,Troop):
                assert e.hitpoints == before[e.player_id] - (210 if e.player_id == 0 else 174)


@pytest.mark.parametrize('name', ['GoblinGang','Golem'])
def test_owned_mixed_swarm_and_death_children_keep_parent_level(name):
    battle = BattleState(players=[PlayerState(0,card_levels={name:10}), PlayerState(1)])
    battle.players[0].hand = [name]
    battle.players[0].elixir = 10
    assert battle.deploy_card(0,name,Position(8,10))
    troops = [e for e in battle.entities.values() if isinstance(e,Troop)]
    assert troops and all(e.card_stats.level == 10 for e in troops)
    if name == 'Golem':
        first = battle.next_entity_id
        troops[0].take_damage(100000)
        children = [e for e in battle.entities.values() if e.id >= first and isinstance(e,Troop)]
        assert children and all(e.card_stats.level == 10 for e in children)


def test_deck_level_aliases_reset_and_reject_conflicts():
    p = PlayerState(0,card_levels={'Archers':10})
    assert p.card_level('Archer') == 10
    deck = PILOT[:8]
    apply_ordered_deck_to_player(p,deck,card_levels={'Archers':12})
    assert p.card_level(p.hand[0]) == 12
    assert p.card_level(p.get_next_card()) == 11
    apply_deck_to_player(p,deck,random.Random(7))
    assert not p.card_levels
    with pytest.raises(ValueError,match='Conflicting'):
        p.set_card_levels({'Archers':10,'Archer':12})
    with pytest.raises(TypeError):
        p.set_card_levels({'Knight':True})


def test_tower_stats_fail_closed_outside_declared_range():
    with pytest.raises(ValueError,match='10 through 12'):
        BattleState(players=[PlayerState(0,tower_level=13),PlayerState(1)])
    with pytest.raises(TypeError):
        tower_stat('KingTower','hitpoints',True)
