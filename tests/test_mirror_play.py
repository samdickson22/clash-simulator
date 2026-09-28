import copy

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop


def ready(battle, cards, elixir=10):
    battle.players[0].hand = cards
    battle.players[0].elixir = elixir


def test_mirror_cannot_be_first_play_or_spend_on_invalid_placement():
    b = BattleState()
    ready(b, ["Mirror", "Knight"])
    assert not b.deploy_card(0, "Mirror", Position(8, 10))
    assert b.players[0].elixir == 10
    assert b.deploy_card(0, "Knight", Position(8, 10))
    assert not b.deploy_card(0, "Mirror", Position(8, 24))
    assert b.players[0].elixir == 7
    assert b.deploy_card(0, "Mirror", Position(5, 10))
    assert b.players[0].elixir == 3
    troops = [e for e in b.entities.values() if isinstance(e, Troop)]
    assert [e.card_stats.name for e in troops] == ["Knight", "Knight"]
    assert [e.card_stats.level for e in troops] == [11, 12]
    assert [e.max_hitpoints for e in troops] == [1766, 1938]
    assert b.card_loader.get_card("Knight").level == 11


def test_mirror_tracks_successful_play_and_checks_true_cost():
    b = BattleState()
    ready(b, ["Knight", "Giant", "Mirror"])
    assert b.deploy_card(0, "Knight", Position(8, 10))
    assert not b.deploy_card(0, "Giant", Position(8, 25))
    b.players[0].elixir = 3
    assert not b.deploy_card(0, "Mirror", Position(4, 10))
    b.players[0].elixir = 4
    assert b.deploy_card(0, "Mirror", Position(4, 10))
    assert b.players[0].elixir == 0


def test_mirrored_spell_captures_level_before_history_changes_and_resolves_in_object_phase():
    b = BattleState()
    victim_id = b.next_entity_id
    b._spawn_troop(Position(8, 24), 1, b.card_loader.get_card("Knight"))
    victim_hp = b.entities[victim_id].hitpoints
    ready(b, ["Zap", "Mirror", "Knight"])
    assert b.deploy_card(0, "Zap", Position(8, 24))
    assert b.entities[victim_id].hitpoints == victim_hp
    _, _, mirrored_spell = b.resolve_card_play(0, "Mirror")
    assert mirrored_spell.level == 12
    assert mirrored_spell.damage == 210
    assert b.deploy_card(0, "Mirror", Position(8, 24))
    assert b.entities[victim_id].hitpoints == victim_hp
    assert b.deploy_card(0, "Knight", Position(8, 10))
    assert b.players[0].elixir == 2
    copied = copy.deepcopy(b)
    for state in (b, copied):
        assert len(state._pending_spell_casts) == 2
        assert state.players[0].last_played_card == "Knight"
        state.step()
        assert not state._pending_spell_casts
        assert state.entities[victim_id].hitpoints == victim_hp - 192 - 210
        state.step()
        assert state.entities[victim_id].hitpoints == victim_hp - 192 - 210


def test_mirror_uses_own_level_and_preserves_champion_eligibility():
    b = BattleState()
    ready(b, ["ArcherQueen", "Mirror"])
    assert b.deploy_card(0, "ArcherQueen", Position(8, 10))
    b.players[0].elixir = 6
    assert b.deploy_card(0, "Mirror", Position(5, 10))
    queens = [e for e in b.entities.values() if isinstance(e, Troop)]
    assert len(queens) == 2
    assert queens[-1].card_stats.level == 12
    assert not queens[-1].is_clone
    owner = b._refresh_champion_ability_owner(0, b._champion_ability_key(queens[-1]))
    assert owner[0] is queens[-1]


def test_mirror_mixed_swarm_and_death_children_inherit_level():
    for name in ("GoblinGang", "Golem"):
        b = BattleState()
        ready(b, [name, "Mirror"])
        assert b.deploy_card(0, name, Position(8, 10))
        b.players[0].elixir = 10
        first = b.next_entity_id
        assert b.deploy_card(0, "Mirror", Position(4, 10))
        mirrored = [e for e in b.entities.values() if e.id >= first]
        assert all(e.card_stats.level == 12 for e in mirrored)
        if name == "Golem":
            first_child = b.next_entity_id
            mirrored[0].take_damage(100000)
            children = [
                e
                for e in b.entities.values()
                if e.id >= first_child and isinstance(e, Troop)
            ]
            assert children
            assert all(e.card_stats.level == 12 for e in children)


def test_mirror_mask_matches_copied_territory_and_dynamic_cost():
    from clasher.rl.action_space import DiscreteTileActionSpace
    from clasher.rl.common import NUM_TILES

    b = BattleState()
    ready(b, ["Knight", "Mirror"])
    space = DiscreteTileActionSpace()
    assert not space.legal_action_mask(b, 0)[NUM_TILES : 2 * NUM_TILES].any()
    assert b.deploy_card(0, "Knight", Position(8, 10))
    b.players[0].elixir = 3
    assert not space.legal_action_mask(b, 0)[NUM_TILES : 2 * NUM_TILES].any()
    b.players[0].elixir = 4
    mask = space.legal_action_mask(b, 0)
    assert mask[NUM_TILES : 2 * NUM_TILES].any()
    import numpy as np

    for action in np.flatnonzero(mask[NUM_TILES : 2 * NUM_TILES]):
        position = space._positions_by_player[0][action]
        assert position.y < 16
