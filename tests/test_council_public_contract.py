"""The council actor carries levels without importing simulator-only evidence."""
from collections import deque
from dataclasses import replace
import json

import numpy as np
import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from clasher.rl.public_observation import (
    REAL_PLAY_ENTITY_FEATURE_INDICES, REAL_PLAY_GLOBAL_FEATURE_INDICES,
    PublicObservationDegradationProfile, degrade_simulator_public_observation,
    project_council_public_observation,
)
from clasher.rl.public_policy_contract import PublicPolicySequence
from clasher.rl.structured_obs import StructuredObservationBuilder


def scene():
    builder = StructuredObservationBuilder(
        card_vocab=['Knight', 'Archers', 'Giant', 'Musketeer', 'Fireball'],
        max_entities=16, public_entity_levels=True, public_hand_levels=True,
        card_semantics_version=4, public_history_slots=4, public_seen_card_slots=8,
        canonical_lane_globals=True,
    )
    battle = BattleState()
    player = battle.players[0]
    player.hand = ['Knight', 'Archers', 'Giant', 'Musketeer']
    player.cycle_queue = deque(['Fireball'])
    player.set_card_levels(dict(zip(player.hand + ['Fireball'], [10, 11, 12, 10, 12])))
    return builder, battle


def inputs(builder, observations):
    masks = np.stack([PublicActionMaskBuilder(builder).build(
        PublicActionMaskInput.from_confidence_observation(obs)
    ) for obs in observations])
    count = len(observations)
    return PublicPolicySequence.from_observations(builder, observations).policy_inputs(
        action_mask=masks, previous_actions=np.full(count, 2304, dtype=np.int64),
        previous_rewards=np.full(count, 123, dtype=np.float32),
        episode_starts=np.asarray([True] + [False] * (count - 1)),
    )


def network(builder):
    torch.manual_seed(7)
    return ClasherPolicy(PolicyConfig(
        num_tokens=builder.spec.num_tokens, max_entities=16,
        d_model=16, num_heads=4, actor_layers=1, critic_layers=1, memory_size=24,
        public_contract_version=4, public_token_names=builder.token_names,
        public_observation_confidence=True, card_semantics_version=4,
        public_history_slots=4, public_seen_card_slots=8,
    ), builder.card_stat_features).eval()


def test_own_five_levels_and_towers_roundtrip(tmp_path):
    builder, battle = scene()
    view = project_council_public_observation(builder.build_actor(battle, 0))
    assert view.observation.hand_levels.tolist() == [10, 11, 12, 10, 12]
    assert (view.observation.hand_level_confidence == 1).all()
    assert (view.observation.entity_levels[view.observation.entity_mask] == 11).all()
    structured = builder.build(battle, 0)
    np.testing.assert_array_equal(structured.hand_levels, view.observation.hand_levels)
    seq = PublicPolicySequence.from_observations(builder, [view, view])
    path = tmp_path / 'council.npz'
    seq.save(path)
    with np.load(path) as archive:
        assert json.loads(str(archive['metadata'].item()))['schema'] == 'clasher.public-policy.v6'
    restored = PublicPolicySequence.load(path, token_names=builder.token_names)
    for name, array in seq.arrays.items():
        np.testing.assert_array_equal(array, restored.arrays[name])
    assert not inputs(builder, [view]).previous_rewards.any()


@pytest.mark.parametrize('slot', [0, 4])
def test_model_actually_consumes_own_hand_and_next_levels(slot):
    builder, battle = scene()
    view = project_council_public_observation(builder.build_actor(battle, 0))
    batch = inputs(builder, [view])
    levels = batch.hand_levels.clone()
    levels[..., slot] += 1
    model = network(builder)
    with torch.no_grad():
        first = model(batch)
        second = model(replace(batch, hand_levels=levels))
    assert not torch.equal(first.joint_logits, second.joint_logits)
    assert not torch.equal(first.next_state[0], second.next_state[0])
    assert torch.isfinite(first.values).all()


def test_missing_levels_remain_unknown_and_usable():
    builder, battle = scene()
    raw = builder.build_actor(battle, 0)
    view = degrade_simulator_public_observation(
        raw, profile=PublicObservationDegradationProfile(), rng=np.random.default_rng(9),
    )
    assert not view.observation.hand_levels.any()
    assert not view.observation.hand_level_confidence.any()
    view.validate()
    with torch.no_grad():
        assert torch.isfinite(network(builder)(inputs(builder, [view])).values).all()
    battle.players[0].hand[1] = None
    battle.players[0].cycle_queue.clear()
    missing = builder.build_actor(battle, 0)
    assert missing.hand_levels[[1, 4]].tolist() == [0, 0]
    assert missing.hand_level_confidence[[1, 4]].tolist() == [0, 0]


@pytest.mark.parametrize('case', ['missing', 'dtype', 'shape', 'confidence', 'unknown', 'padded'])
def test_bad_hand_level_contract_fails_at_archive_and_model(case):
    builder, battle = scene()
    view = project_council_public_observation(builder.build_actor(battle, 0))
    levels, confidence = view.observation.hand_levels.copy(), view.observation.hand_level_confidence.copy()
    hand_ids = view.observation.hand_ids.copy()
    if case == 'missing': confidence = None
    elif case == 'dtype': levels = levels.astype(np.float32)
    elif case == 'shape': levels = levels[:-1]
    elif case == 'confidence': confidence[0] = np.nan
    elif case == 'unknown': confidence[0] = 0
    elif case == 'padded': hand_ids[0] = 0
    malformed = replace(view, observation=replace(view.observation, hand_ids=hand_ids, hand_levels=levels, hand_level_confidence=confidence))
    with pytest.raises(ValueError):
        PublicPolicySequence.from_observations(builder, [malformed])
    batch = inputs(builder, [view])
    with pytest.raises(ValueError):
        network(builder)(replace(batch, hand_ids=torch.from_numpy(hand_ids)[None, None], hand_levels=torch.from_numpy(levels)[None, None], hand_level_confidence=None if confidence is None else torch.from_numpy(confidence)[None, None]))


def test_actor_invariant_to_hidden_enemy_state_rewards_and_unsupported_channels():
    builder, battle = scene()
    before = project_council_public_observation(builder.build_actor(battle, 0))
    enemy = battle.players[1]
    enemy.elixir = .123
    enemy.hand = ['Fireball'] * 4
    enemy.cycle_queue = deque(['Giant'])
    enemy.set_card_levels({'Fireball': 12, 'Giant': 10})
    after = project_council_public_observation(builder.build_actor(battle, 0))
    one = PublicPolicySequence.from_observations(builder, [before])
    two = PublicPolicySequence.from_observations(builder, [after])
    for name in one.arrays:
        np.testing.assert_array_equal(one.arrays[name], two.arrays[name])
    batch = inputs(builder, [before])
    features = batch.entity_features.clone()
    globals_ = batch.global_features.clone()
    entity_hidden = sorted(set(range(32)) - REAL_PLAY_ENTITY_FEATURE_INDICES)
    global_hidden = sorted(set(range(18)) - REAL_PLAY_GLOBAL_FEATURE_INDICES)
    features[..., entity_hidden] = 99
    globals_[..., global_hidden] = 99
    changed = replace(batch, entity_features=features, global_features=globals_, previous_rewards=torch.full_like(batch.previous_rewards, -99), critic_entity_ids=batch.entity_ids, critic_entity_features=torch.rand_like(features), critic_entity_mask=batch.entity_mask, critic_card_ids=torch.zeros(1, 1, 10, dtype=torch.long), critic_global_features=torch.rand(1, 1, 20))
    model = network(builder)
    with torch.no_grad():
        first, second = model(batch), model(changed)
    assert torch.equal(first.joint_logits, second.joint_logits)
    for a, b in zip(first.next_state, second.next_state):
        assert torch.equal(a, b)


def test_old_model_cannot_silently_drop_new_levels():
    builder, battle = scene()
    view = project_council_public_observation(builder.build_actor(battle, 0))
    model = network(builder)
    legacy = ClasherPolicy(replace(model.config, public_contract_version=3), builder.card_stat_features)
    with pytest.raises(ValueError, match='hand levels require public contract v4'):
        legacy(inputs(builder, [view]))


def test_v4_requires_float32_entity_level_confidence_and_explicit_confidence_config():
    builder, battle = scene()
    view = project_council_public_observation(builder.build_actor(battle, 0))
    batch = inputs(builder, [view])
    model = network(builder)
    with pytest.raises(ValueError, match="entity level shape or dtype"):
        model(replace(batch, entity_level_confidence=batch.entity_level_confidence.double()))
    with pytest.raises(ValueError, match="v4 requires observation confidence"):
        replace(model.config, public_observation_confidence=False)
