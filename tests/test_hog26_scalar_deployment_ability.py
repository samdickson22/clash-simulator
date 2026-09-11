"""Real deployment and ability transitions through the public-only scalar view."""

from dataclasses import fields

import numpy as np
import pytest

from clasher.arena import Position
from clasher.rl.simple_pytorch_backend import (
    _compile_public_mask_v2_tables,
    _typed_lookups,
    load_current_client_typed_vocabulary,
)
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.torch_sim.simple_public_mask import SimplePublicMaskV2Provider
from clasher.torch_sim.simple_standard import compile_standard_simple_setup
from scripts.hog26_scalar_actor_projection import build_scalar_reference_actors
from scripts.hog26_scalar_policy_inputs import scalar_policy_inputs
from scripts.hog26_scalar_reference_episode import ScalarReferenceEpisode

DECK = ("ArcherQueen", "Knight", "Skeletons", "Cannon", "Fireball", "Log", "IceGolem", "Musketeer")


@pytest.fixture(scope="module")
def public_setup():
    vocabulary = load_current_client_typed_vocabulary()
    builder = StructuredObservationBuilder(
        token_names=vocabulary.token_names, max_entities=128,
        card_semantics_version=3, canonical_lane_globals=True,
    )
    compiled = compile_standard_simple_setup(
        builder.loader, DECK, device="cpu", canonical_lane_globals=True,
    )
    lookup, _ = _typed_lookups(compiled, builder.loader, vocabulary)
    provider = SimplePublicMaskV2Provider(_compile_public_mask_v2_tables(builder, compiled, lookup))
    return builder, provider


def actors(battle, builder):
    return build_scalar_reference_actors(
        battle, builder, appearances=(),
        visible_to=lambda entity, seat: entity.is_visible_to(seat),
    )


@pytest.mark.parametrize("seat", (0, 1))
def test_real_queen_pending_ready_and_cast_pending_match_scalar_oracle(public_setup, seat):
    builder, provider = public_setup
    episode = ScalarReferenceEpisode.create((DECK, DECK), seed=83101, learner_seat=seat)
    battle = episode.battle
    battle.players[seat].elixir = 10
    assert battle.deploy_card(seat, "ArcherQueen", Position(9, 5 if seat == 0 else 27))
    queen = battle._champion_ability_mechanic(seat)[0]
    token = builder.token_id("ArcherQueen", namespace="troop_body")
    assert provider.tables.ability_supported[token]

    def check(expected, deploying):
        views = actors(battle, builder)
        inputs, masks = scalar_policy_inputs(
            views, provider, previous_actions=[episode.action_space.no_op_action] * 2,
            episode_starts=[False, False],
        )
        index = np.flatnonzero(views[seat].entity_ids == token)
        assert len(index) == 1
        assert views[seat].entity_features[index[0], 12] == deploying
        assert inputs.entity_feature_confidence[seat, 0, index[0], 12] == 1
        assert views[seat].entity_features[index[0], 13] == 0
        assert inputs.entity_feature_confidence[seat, 0, index[0], 13] == 0
        assert bool(masks.masks[0, seat, episode.action_space.ability_action]) is expected
        assert battle.can_activate_champion_ability(seat) is expected
        assert bool(episode.action_space.legal_action_mask(battle, seat)[episode.action_space.ability_action]) is expected

    assert queen.placement_pending
    check(False, True)
    for _ in range(100):
        if not queen.placement_pending:
            break
        battle.step()
    assert not queen.placement_pending
    check(True, False)
    assert battle.activate_champion_ability(seat)
    mechanic = battle._champion_ability_mechanic(seat)[1]
    assert mechanic._cloak_pending_until is not None
    check(False, False)


def test_deployment_timer_and_enemy_private_state_are_not_exposed(public_setup):
    builder, _ = public_setup
    episode = ScalarReferenceEpisode.create((DECK, DECK), seed=83102, learner_seat=0)
    battle = episode.battle
    battle.players[1].elixir = 10
    assert battle.deploy_card(1, "ArcherQueen", Position(9, 27))
    queen = battle._champion_ability_mechanic(1)[0]
    before = actors(battle, builder)[0]
    assert queen.placement_pending
    queen.deploy_delay_remaining *= 0.37
    queen.placement_delay_total *= 4
    queen.target_id = 99999
    battle.players[1].elixir = 0.01
    battle.players[1].hand[:] = ["Rocket"] * 4
    battle.rng.seed(993)
    after = actors(battle, builder)[0]
    for field in fields(before):
        np.testing.assert_array_equal(getattr(before, field.name), getattr(after, field.name))
