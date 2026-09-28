"""Explicit level observations reach the new model without changing legacy input."""
from dataclasses import replace

import numpy as np
import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.causal_vision import CausalVisionTracker
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.public_observation import (
    PublicObservationDegradationProfile,
    degrade_simulator_public_observation,
    exact_public_observation,
)
from clasher.rl.public_policy_contract import PublicPolicySequence
from clasher.rl.structured_obs import StructuredObservationBuilder


def scene():
    builder = StructuredObservationBuilder(card_vocab=['Knight', 'Mirror'], max_entities=16, public_entity_levels=True)
    battle = BattleState()
    battle.players[0].hand = ['Knight', 'Mirror']
    battle.players[0].elixir = 10
    assert battle.deploy_card(0, 'Knight', Position(3.5, 11.5))
    assert battle.deploy_card(0, 'Mirror', Position(3.5, 11.5))
    return builder, battle


def policy_inputs(sequence):
    return sequence.policy_inputs(action_mask=np.ones((1, 2306), dtype=bool), previous_actions=np.zeros(1, dtype=np.int64), previous_rewards=np.zeros(1, dtype=np.float32), episode_starts=np.ones(1, dtype=bool))


def network(builder, version):
    return ClasherPolicy(PolicyConfig(num_tokens=builder.spec.num_tokens, max_entities=16, d_model=16, num_heads=4, actor_layers=1, critic_layers=1, memory_size=24, public_contract_version=version, public_token_names=builder.token_names), builder.card_stat_features).eval()


@pytest.mark.parametrize('owner', [0, 1])
def test_mirrored_unit_levels_align_with_rows_and_survive_archive(owner, tmp_path):
    builder, battle = scene()
    view = builder.build_actor(battle, owner)
    rows = (view.entity_ids == builder.token_id('Knight')) & view.entity_mask
    assert sorted(view.entity_levels[rows].tolist()) == [11, 12]
    assert (view.entity_level_confidence[rows] == 1).all()
    assert (view.entity_features[rows, 9] == 1).all()
    assert not view.entity_levels[~view.entity_mask].any()
    structured = builder.build(battle, owner)
    np.testing.assert_array_equal(structured.entity_levels, view.entity_levels)
    sequence = PublicPolicySequence.from_observations(builder, [view])
    path = tmp_path / 'levels.npz'
    sequence.save(path)
    restored = PublicPolicySequence.load(path, token_names=builder.token_names)
    np.testing.assert_array_equal(restored.arrays['entity_levels'], sequence.arrays['entity_levels'])
    exact_public_observation(view).validate()


def test_model_consumes_level_change_with_all_other_inputs_identical():
    builder, battle = scene()
    view = builder.build_actor(battle, 0)
    levels = view.entity_levels.copy()
    index = int(np.flatnonzero(levels == 11)[0])
    levels[index] = 12
    different = replace(view, entity_levels=levels)
    model = network(builder, 3)
    with torch.no_grad():
        first = model(policy_inputs(PublicPolicySequence.from_observations(builder, [view])))
        second = model(policy_inputs(PublicPolicySequence.from_observations(builder, [different])))
    assert not torch.equal(first.next_state[0], second.next_state[0])
    assert torch.isfinite(first.next_state[0]).all()
    with pytest.raises(ValueError, match='contract v3'):
        network(builder, 2)(policy_inputs(PublicPolicySequence.from_observations(builder, [view])))
    missing = replace(policy_inputs(PublicPolicySequence.from_observations(builder, [view])), entity_levels=None)
    with pytest.raises(ValueError, match='requires entity levels'):
        model(missing)


def test_uncalibrated_visual_levels_remain_unknown_and_tracker_does_not_fill_them():
    builder, battle = scene()
    exact = builder.build_actor(battle, 0)
    view = degrade_simulator_public_observation(exact, profile=PublicObservationDegradationProfile(), rng=np.random.default_rng(1))
    assert not view.observation.entity_levels.any()
    assert not view.observation.entity_level_confidence.any()
    tracked = CausalVisionTracker().update(view, frame=0)
    np.testing.assert_array_equal(tracked.observation.entity_levels, view.observation.entity_levels)
    sequence = PublicPolicySequence.from_observations(builder, [tracked])
    config = PolicyConfig(num_tokens=builder.spec.num_tokens, max_entities=16, d_model=16, num_heads=4, actor_layers=1, critic_layers=1, memory_size=24, public_contract_version=3, public_token_names=builder.token_names, public_observation_confidence=True)
    model = ClasherPolicy(config, builder.card_stat_features).eval()
    with torch.no_grad():
        assert torch.isfinite(model(policy_inputs(sequence)).next_state[0]).all()


@pytest.mark.parametrize('case', ['missing', 'padded', 'unknown', 'fractional', 'confidence'])
def test_invalid_public_level_data_is_rejected(case):
    builder, battle = scene()
    view = builder.build_actor(battle, 0)
    levels, confidence = view.entity_levels.copy(), view.entity_level_confidence.copy()
    if case == 'missing': confidence = None
    elif case == 'padded': levels[-1], confidence[-1] = 11, 1
    elif case == 'unknown': confidence[levels > 0] = 0
    elif case == 'fractional': levels = levels.astype(np.float32)
    elif case == 'confidence': confidence[levels > 0] = 2
    with pytest.raises(ValueError):
        PublicPolicySequence.from_observations(builder, [replace(view, entity_levels=levels, entity_level_confidence=confidence)])


def test_tracker_reordering_keeps_level_attached_to_its_body():
    builder, battle = scene()
    exact = builder.build_actor(battle, 0)
    view = degrade_simulator_public_observation(exact, profile=PublicObservationDegradationProfile(), rng=np.random.default_rng(1))
    ids = np.flatnonzero(exact.entity_levels > 0)
    observed = replace(view.observation, entity_levels=exact.entity_levels.copy(), entity_level_confidence=exact.entity_level_confidence.copy())
    identity_confidence = view.entity_id_confidence.copy()
    identity_confidence[ids[0]], identity_confidence[ids[1]] = 0.2, 0.95
    source = replace(view, observation=observed, entity_id_confidence=identity_confidence)
    tracked = CausalVisionTracker().update(source, frame=0)
    knight_rows = tracked.observation.entity_mask & (tracked.observation.entity_ids == builder.token_id('Knight'))
    assert tracked.observation.entity_levels[knight_rows].tolist() == [12, 11]
    tracked.validate()


def test_observed_level_change_does_not_duplicate_a_tracked_body():
    builder, battle = scene()
    exact = builder.build_actor(battle, 0)
    projected = degrade_simulator_public_observation(exact, profile=PublicObservationDegradationProfile(), rng=np.random.default_rng(1))
    source = replace(projected, observation=replace(projected.observation, entity_levels=exact.entity_levels.copy(), entity_level_confidence=exact.entity_level_confidence.copy()))
    tracker = CausalVisionTracker()
    first = tracker.update(source, frame=0)
    levels = exact.entity_levels.copy()
    levels[levels == 11] = 12
    second = tracker.update(replace(source, observation=replace(source.observation, entity_levels=levels)), frame=1)
    assert first.observation.entity_mask.sum() == second.observation.entity_mask.sum()
    rows = second.observation.entity_mask & (second.observation.entity_ids == builder.token_id('Knight'))
    assert second.observation.entity_levels[rows].tolist() == [12, 12]


def test_fixed_tournament_towers_expose_public_level_not_scaling_placeholder():
    builder = StructuredObservationBuilder(card_vocab=['Knight'], public_entity_levels=True)
    battle = BattleState()
    assert all(t.card_stats.level == 1 for t in battle.entities.values())
    view = builder.build_actor(battle, 0)
    assert (view.entity_levels[view.entity_mask] == 11).all()
    assert (view.entity_level_confidence[view.entity_mask] == 1).all()
    assert sorted(t.hitpoints for t in battle.entities.values()) == [3052,3052,3052,3052,4824,4824]
