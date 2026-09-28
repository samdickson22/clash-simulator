from dataclasses import replace

import numpy as np
import pytest
import torch

from clasher.battle import BattleState
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.own_card_history import AcceptedOwnPlay
from clasher.rl.public_policy_contract import PublicPolicySequence
from clasher.rl.structured_obs import StructuredObservationBuilder


def builder():
    return StructuredObservationBuilder(
        card_vocab=["Knight", "Mirror", "Fireball"], max_entities=16
    )


def inputs(sequence):
    count = len(sequence.arrays["own_last_play_ids"])
    return sequence.policy_inputs(
        action_mask=np.ones((count, 2306), dtype=bool),
        previous_actions=np.zeros(count, dtype=np.int64),
        previous_rewards=np.zeros(count, dtype=np.float32),
        episode_starts=np.ones(count, dtype=bool),
    )


def model(b, version):
    return ClasherPolicy(
        PolicyConfig(
            num_tokens=b.spec.num_tokens,
            max_entities=16,
            d_model=16,
            num_heads=4,
            actor_layers=1,
            critic_layers=1,
            memory_size=24,
            public_contract_version=version,
            public_token_names=b.token_names if version == 2 else (),
        ),
        b.card_stat_features,
    ).eval()


def test_public_history_roundtrip_and_policy_consumption(tmp_path):
    b = builder()
    observation = b.build_actor(BattleState(), 0)
    known = replace(observation, own_last_play=AcceptedOwnPlay("Knight", 3))
    sequence = PublicPolicySequence.from_observations(b, [known, observation])
    path = tmp_path / "public.npz"
    sequence.save(path)
    restored = PublicPolicySequence.load(path, token_names=b.token_names)
    assert restored.arrays["own_last_play_ids"].tolist() == [b.token_id("Knight"), 0]
    np.testing.assert_array_equal(
        restored.arrays["own_last_play_features"],
        np.asarray([[1, 0.3], [0, 0]], dtype=np.float32),
    )
    assert not any(name.startswith("critic") for name in restored.arrays)
    network = model(b, 2)
    with torch.no_grad():
        first = network(inputs(PublicPolicySequence.from_observations(b, [known])))
        second = network(
            inputs(PublicPolicySequence.from_observations(b, [observation]))
        )
    assert not torch.equal(first.next_state[0], second.next_state[0])
    assert torch.isfinite(first.values).all()
    with pytest.raises(FileExistsError):
        sequence.save(path)
    with pytest.raises(ValueError, match="vocabulary"):
        PublicPolicySequence.load(path, token_names=(*b.token_names, "extra"))


@pytest.mark.parametrize("owner", [0, 1])
def test_public_wire_excludes_hidden_enemy_state(owner):
    b = builder()
    battle = BattleState()
    before = PublicPolicySequence.from_observations(b, [b.build_actor(battle, owner)])
    enemy = battle.players[1 - owner]
    enemy.elixir = 0.125
    enemy.hand = ["Mirror", "Fireball", "Knight", "Mirror"]
    after = PublicPolicySequence.from_observations(b, [b.build_actor(battle, owner)])
    for name in before.arrays:
        np.testing.assert_array_equal(before.arrays[name], after.arrays[name])


def test_versioned_model_rejects_silently_dropped_history():
    b = builder()
    sequence = PublicPolicySequence.from_observations(
        b, [b.build_actor(BattleState(), 0)]
    )
    batch = inputs(sequence)
    with pytest.raises(ValueError, match="requires public contract v2"):
        model(b, 1)(batch)
    missing = replace(batch, own_last_play_ids=None, own_last_play_features=None)
    with pytest.raises(ValueError, match="requires own accepted-play"):
        model(b, 2)(missing)
    legacy = model(b, 1)
    assert not any(
        name.startswith("own_history_projection.") for name in legacy.state_dict()
    )
    with torch.no_grad():
        assert torch.isfinite(legacy(missing).values).all()


def test_unknown_and_out_of_vocabulary_history_are_distinct():
    b = builder()
    observation = b.build_actor(BattleState(), 0)
    with pytest.raises(ValueError, match="outside the declared vocabulary"):
        PublicPolicySequence.from_observations(
            b, [replace(observation, own_last_play=AcceptedOwnPlay("Golem", 8))]
        )
    sequence = PublicPolicySequence.from_observations(b, [observation])
    arrays = {k: v.copy() for k, v in sequence.arrays.items()}
    arrays["own_last_play_features"][0] = [1, 0.3]
    with pytest.raises(ValueError, match="knowledge disagree"):
        PublicPolicySequence(b.token_names, arrays)
    arrays = {k: v.copy() for k, v in sequence.arrays.items()}
    arrays["critic_global_features"] = np.zeros((1, 20), dtype=np.float32)
    with pytest.raises(ValueError, match="fields missing or unknown"):
        PublicPolicySequence(b.token_names, arrays)


def test_history_survives_visual_projection_and_live_inference():
    from clasher.rl.causal_vision import CausalVisionTracker
    from clasher.rl.dagger_behavior import actor_policy_action
    from clasher.rl.public_observation import (
        TV_ROYALE_PILOT_DEGRADATION,
        degrade_simulator_public_observation,
    )

    b = builder()
    known = replace(
        b.build_actor(BattleState(), 0), own_last_play=AcceptedOwnPlay("Knight", 3)
    )
    degraded = degrade_simulator_public_observation(
        known,
        profile=TV_ROYALE_PILOT_DEGRADATION,
        rng=np.random.default_rng(9),
        accepted_own_play=known.own_last_play,
    )
    tracked = CausalVisionTracker().update(degraded, frame=0)
    assert tracked.observation.own_last_play == known.own_last_play
    sequence = PublicPolicySequence.from_observations(b, [tracked])
    assert "global_feature_confidence" in sequence.arrays
    network = ClasherPolicy(
        replace(
            model(b, 2).config,
            public_observation_confidence=True,
            actor_observation_domain="causal-vision-v1",
        ),
        b.card_stat_features,
    ).eval()
    args = {
        "state": network.initial_state(1),
        "previous_action": 0,
        "previous_reward": 0.0,
        "episode_start": True,
        "deterministic": True,
        "device": torch.device("cpu"),
    }
    action, state = actor_policy_action(
        network, tracked, np.ones(2306, dtype=bool), observation_builder=b, **args
    )
    assert 0 <= action < 2306
    assert torch.isfinite(state[0]).all()
    with pytest.raises(ValueError, match="requires its observation builder"):
        actor_policy_action(network, tracked, np.ones(2306, dtype=bool), **args)
    shuffled = replace(
        network.config,
        public_token_names=(*b.token_names[:2], *reversed(b.token_names[2:])),
    )
    network.config = shuffled
    with pytest.raises(ValueError, match="vocabulary does not match"):
        actor_policy_action(
            network, tracked, np.ones(2306, dtype=bool), observation_builder=b, **args
        )


def test_v2_config_roundtrip_and_shape_rejection():
    import json

    b = builder()
    config = model(b, 2).config
    assert PolicyConfig.from_dict(json.loads(json.dumps(config.to_dict()))) == config
    sequence = PublicPolicySequence.from_observations(
        b, [b.build_actor(BattleState(), 0)]
    )
    arrays = {k: v.copy() for k, v in sequence.arrays.items()}
    arrays["entity_features"] = arrays["entity_features"][:, :, :-1]
    with pytest.raises(ValueError, match="invalid public shape"):
        PublicPolicySequence(b.token_names, arrays)


def test_public_contract_rejects_fractional_ids_and_unconfigured_confidence():
    from clasher.rl.public_observation import exact_public_observation

    b = builder()
    observation = b.build_actor(BattleState(), 0)
    with pytest.raises(ValueError, match="source dtype mismatch"):
        PublicPolicySequence.from_observations(
            b,
            [
                replace(
                    observation,
                    entity_ids=observation.entity_ids.astype(np.float32) + 0.5,
                )
            ],
        )
    confidence = PublicPolicySequence.from_observations(
        b, [exact_public_observation(observation)]
    )
    with pytest.raises(ValueError, match="confidence inputs do not match"):
        model(b, 2)(inputs(confidence))
