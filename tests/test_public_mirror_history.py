from dataclasses import replace

import numpy as np
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.common import NUM_TILES
from clasher.rl.own_card_history import AcceptedOwnPlay
from clasher.rl.public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from clasher.rl.public_observation import exact_public_observation
from clasher.rl.structured_obs import StructuredObservationBuilder


def setup(card="Knight"):
    battle = BattleState()
    battle.players[0].hand = [card, "Mirror"]
    battle.players[0].elixir = 10
    builder = StructuredObservationBuilder(card_vocab=["Knight", "Mirror", "Zap"])
    return battle, builder, PublicActionMaskBuilder(builder)


def snapshot(builder, battle):
    return PublicActionMaskInput.from_confidence_observation(
        exact_public_observation(builder.build_actor(battle, 0))
    )


def test_public_mirror_requires_confirmed_history_and_true_cost():
    b, builder, masks = setup()
    assert not masks.build(snapshot(builder, b))[NUM_TILES : 2 * NUM_TILES].any()
    assert b.deploy_card(0, "Knight", Position(8, 10))
    view = snapshot(builder, b)
    assert view.own_last_play == AcceptedOwnPlay("Knight", 3)
    mask = masks.build(view)
    assert mask[NUM_TILES : 2 * NUM_TILES].any()
    assert not mask[NUM_TILES + 17 * 18 : 2 * NUM_TILES].any()
    assert not masks.build(replace(view, own_last_play=None))[
        NUM_TILES : 2 * NUM_TILES
    ].any()
    b.players[0].elixir = 3
    assert not masks.build(snapshot(builder, b))[NUM_TILES : 2 * NUM_TILES].any()


def test_public_history_is_own_only_and_failed_play_does_not_change_it():
    b, builder, masks = setup()
    assert b.deploy_card(0, "Knight", Position(8, 10))
    view = snapshot(builder, b)
    baseline = masks.build(view)
    b.players[1].last_played_card = "Giant"
    b.players[1].last_played_card_cost = 5
    b.players[1].elixir = 0
    assert not b.deploy_card(0, "Mirror", Position(8, 24))
    current = snapshot(builder, b)
    assert current.own_last_play == view.own_last_play
    np.testing.assert_array_equal(masks.build(current), baseline)
    assert builder.build_actor(b, 1).own_last_play.card_name == "Giant"


def test_public_mirrored_spell_can_target_enemy_territory():
    b, builder, masks = setup("Zap")
    assert b.deploy_card(0, "Zap", Position(8, 24))
    view = snapshot(builder, b)
    mask = masks.build(view)
    assert mask[NUM_TILES + 24 * 18 + 8]
    b.players[0].elixir = 2
    assert not masks.build(snapshot(builder, b))[NUM_TILES : 2 * NUM_TILES].any()


@pytest.mark.parametrize("cost", [True, -1, 11, 3.5])
def test_invalid_history_costs_are_rejected(cost):
    with pytest.raises(ValueError):
        AcceptedOwnPlay("Knight", cost)


def test_visual_degradation_does_not_invent_command_acceptance():
    from clasher.rl.public_observation import (
        PublicObservationDegradationProfile,
        degrade_simulator_public_observation,
    )

    b, builder, masks = setup()
    assert b.deploy_card(0, "Knight", Position(8, 10))
    degraded = degrade_simulator_public_observation(
        builder.build_actor(b, 0),
        profile=PublicObservationDegradationProfile(),
        rng=np.random.default_rng(17),
    )
    public = PublicActionMaskInput.from_confidence_observation(degraded)
    assert public.own_last_play is None
    assert not masks.build(public)[NUM_TILES : 2 * NUM_TILES].any()
    # This independent public receipt could come from a live control journal.
    known = replace(public, own_last_play=AcceptedOwnPlay("Knight", 3))
    assert masks.build(known)[NUM_TILES : 2 * NUM_TILES].any()


def test_new_battle_has_no_previous_battle_history():
    b, builder, _ = setup()
    assert b.deploy_card(0, "Knight", Position(8, 10))
    assert builder.build_actor(b, 0).own_last_play is not None
    assert builder.build_actor(BattleState(), 0).own_last_play is None
