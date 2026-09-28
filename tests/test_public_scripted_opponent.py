"""Public-only scripted opponents must be legal, responsive, and uncertainty-aware."""

import copy
from dataclasses import replace

import numpy as np
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.public_observation import exact_public_observation
from clasher.rl.public_scripted_opponent import SUPPORTED_CARDS, PublicScriptedOpponent
from clasher.rl.structured_obs import StructuredObservationBuilder


def fixture(owner=0):
    battle = BattleState()
    builder = StructuredObservationBuilder(
        card_vocab=sorted(SUPPORTED_CARDS),
        canonical_lane_globals=True,
        public_entity_levels=True,
        card_semantics_version=4,
    )
    battle.players[owner].hand = ["HogRider", "Cannon", "Fireball", "Skeletons"]
    battle.players[owner].elixir = 10
    return battle, builder, PublicScriptedOpponent(builder)


def packet(battle, builder, owner=0):
    return exact_public_observation(builder.build_actor(battle, owner))


def spawn(battle, name, owner, xy):
    before = set(battle.entities)
    battle._spawn_unit_at_position(
        Position(*xy),
        owner,
        battle.card_loader.get_card(name),
        deploy_delay_override=0,
        snap_to_valid=False,
    )
    return battle.entities[(set(battle.entities) - before).pop()]


@pytest.mark.parametrize("owner", [0, 1])
def test_idle_pressure_uses_a_bridge_lane_in_canonical_coordinates(owner):
    battle, builder, bot = fixture(owner)
    choice = bot.decide(packet(battle, builder, owner))
    slot, tile = divmod(choice.action_id, 576)
    assert battle.players[owner].hand[slot] == "HogRider"
    assert tile % 18 + 0.5 in (3.5, 14.5)
    assert tile // 18 + 0.5 == 13.5


@pytest.mark.parametrize("owner", [0, 1])
def test_incoming_hog_draws_central_cannon_instead_of_single_target_fireball(owner):
    battle, builder, bot = fixture(owner)
    xy = (3.5, 11.5) if owner == 0 else (14.5, 20.5)
    spawn(battle, "HogRider", 1 - owner, xy)
    choice = bot.decide(packet(battle, builder, owner))
    slot, tile = divmod(choice.action_id, 576)
    assert battle.players[owner].hand[slot] == "Cannon"
    assert (tile % 18 + 0.5, tile // 18 + 0.5) == (7.5, 10.5)


def test_low_elixir_waits_without_spending_a_cheap_cycle_card():
    battle, builder, bot = fixture()
    battle.players[0].elixir = 2
    assert bot.select_action(packet(battle, builder)) == 2304


def test_fireball_finishes_visible_crown_using_ruleset_damage():
    battle, builder, bot = fixture()
    tower = next(
        e
        for e in battle.entities.values()
        if e.player_id == 1 and getattr(e, "_crown_tower_slot", None) == "left"
    )
    tower.take_damage(tower.hitpoints - 100)
    choice = bot.decide(packet(battle, builder))
    assert choice.action_id // 576 == 2
    assert choice.score >= 100


def test_unknown_own_elixir_fails_explicitly():
    battle, builder, bot = fixture()
    p = packet(battle, builder)
    confidence = p.global_feature_confidence.copy()
    confidence[5] = 0
    values = p.observation.global_features.copy()
    values[5] = 0
    p = replace(
        p,
        global_feature_confidence=confidence,
        observation=replace(p.observation, global_features=values),
    )
    with pytest.raises(ValueError, match="elixir"):
        bot.select_action(p)


def test_unknown_body_level_fails_explicitly():
    battle, builder, bot = fixture()
    spawn(battle, "HogRider", 1, (3.5, 11.5))
    p = packet(battle, builder)
    levels = p.observation.entity_levels.copy()
    certainty = p.observation.entity_level_confidence.copy()
    levels[:], certainty[:] = 0, 0
    p = replace(
        p,
        observation=replace(
            p.observation, entity_levels=levels, entity_level_confidence=certainty
        ),
    )
    with pytest.raises(ValueError, match="body level"):
        bot.select_action(p)


def test_hidden_opponent_cards_elixir_and_targets_do_not_change_decision():
    battle, builder, bot = fixture()
    hog = spawn(battle, "HogRider", 1, (3.5, 11.5))
    first = packet(battle, builder)
    decision = bot.select_action(first)
    battle.players[1].hand = ["Zap"] * 4
    battle.players[1].elixir = 0.1
    hog.target_id = 999999
    second = packet(battle, builder)
    assert bot.select_action(second) == decision
    assert np.array_equal(
        first.observation.entity_features, second.observation.entity_features
    )


def test_decision_does_not_mutate_observation():
    battle, builder, bot = fixture()
    p = packet(battle, builder)
    before = copy.deepcopy(p)
    assert bot.select_action(p) == bot.select_action(p)
    assert np.array_equal(
        p.observation.entity_features, before.observation.entity_features
    )
    assert np.array_equal(p.observation.hand_ids, before.observation.hand_ids)


def test_simulator_object_is_not_an_accepted_input():
    battle, _, bot = fixture()
    with pytest.raises(TypeError, match="public confidence"):
        bot.select_action(battle)


def test_unsupported_roster_fails_instead_of_substituting_card():
    builder = StructuredObservationBuilder(
        card_vocab=["Mirror"],
        canonical_lane_globals=True,
        public_entity_levels=True,
        card_semantics_version=4,
    )
    with pytest.raises(ValueError, match="roster"):
        PublicScriptedOpponent(builder)


def test_archived_deck_aliases_use_the_same_public_card_semantics():
    battle, _, _ = fixture()
    aliases = ["Hog Rider", "Cannon", "Fireball", "Skeleton"]
    builder = StructuredObservationBuilder(
        card_vocab=aliases,
        canonical_lane_globals=True,
        public_entity_levels=True,
        card_semantics_version=4,
    )
    battle.players[0].hand = aliases
    bot = PublicScriptedOpponent(builder)
    assert bot.select_action(packet(battle, builder)) // 576 == 0


def test_unconsumed_simulator_effect_fields_cannot_change_action():
    battle, builder, bot = fixture()
    spawn(battle, "HogRider", 1, (3.5, 11.5))
    p = packet(battle, builder)
    expected = bot.select_action(p)
    features = p.observation.entity_features.copy()
    # Hidden attack/status timelines are outside this fixed controller's inputs.
    features[p.observation.entity_mask, 12:23] = 1
    poisoned = replace(p, observation=replace(p.observation, entity_features=features))
    assert bot.select_action(poisoned) == expected


def test_unknown_shield_is_not_assumed_depleted_for_spell_value():
    battle, builder, bot = fixture()
    spawn(battle, "DarkPrince", 1, (3.5, 11.5))
    p = packet(battle, builder)
    features = p.observation.entity_features.copy()
    confidence = p.entity_feature_confidence.copy()
    features[:, 10] = 0
    confidence[:, 10] = 0
    p = replace(
        p,
        observation=replace(p.observation, entity_features=features),
        entity_feature_confidence=confidence,
    )
    # It may defend with a troop/building, but cannot buy a Fireball using
    # damage value computed from a fabricated empty shield.
    assert bot.select_action(p) // 576 != 2
