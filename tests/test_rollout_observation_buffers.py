from __future__ import annotations

from dataclasses import fields

import numpy as np
import torch

from clasher.rl import train_recurrent as train_recurrent_module
from clasher.rl.model import ClasherPolicy, PolicyConfig, PolicyInputs
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import (
    _empty_rollout_arrays,
    _empty_step_observation_arrays,
    _stack_observation_arrays,
    _stack_step_inputs,
    _step_inputs_from_stacked_observations,
    _store_observations,
    collect_rollout_stationary_opponents,
)


def test_preallocated_observation_buffers_match_stacked_policy_inputs():
    env = SelfPlayBattleEnv(seed=8831, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    observations = [builder.build(env.battle, player_id) for player_id in (0, 1)]
    action_masks = np.stack([env.get_action_mask(player_id) for player_id in (0, 1)])
    previous_actions = np.full((2,), env.action_space.no_op_action, dtype=np.int64)
    previous_rewards = np.asarray([0.25, -0.25], dtype=np.float32)
    episode_starts = np.asarray([True, False], dtype=np.bool_)
    rollout_arrays = _empty_rollout_arrays(
        agents=2,
        steps=2,
        builder=builder,
        num_actions=env.action_space.num_actions,
    )
    buffers = _empty_step_observation_arrays(rollout_arrays)

    returned = _stack_observation_arrays(observations, out=buffers)
    assert returned is buffers
    _store_observations(
        rollout_arrays,
        observations,
        action_masks,
        previous_actions,
        previous_rewards,
        episode_starts,
        1,
        stacked_observations=buffers,
    )
    expected = _stack_step_inputs(
        observations,
        action_masks,
        previous_actions,
        previous_rewards,
        episode_starts,
        torch.device("cpu"),
    )
    actual = _step_inputs_from_stacked_observations(
        buffers,
        action_masks,
        previous_actions,
        previous_rewards,
        episode_starts,
        torch.device("cpu"),
    )

    for field in fields(PolicyInputs):
        expected_tensor = getattr(expected, field.name)
        actual_tensor = getattr(actual, field.name)
        assert expected_tensor is not None
        assert actual_tensor is not None
        torch.testing.assert_close(actual_tensor, expected_tensor, rtol=0, atol=0)

    assert np.shares_memory(actual.entity_ids.numpy(), buffers["entity_ids"])
    for field, buffer in buffers.items():
        np.testing.assert_array_equal(rollout_arrays[field][:, 1], buffer)


def _fixed_stationary_rollout(
    *,
    use_preallocated_buffers: bool,
    use_inference_mode: bool | None = None,
    recurrent_state: tuple[torch.Tensor, torch.Tensor] | None = None,
):
    train_recurrent_module._USE_PREALLOCATED_STEP_OBSERVATION_BUFFERS = (
        use_preallocated_buffers
    )
    if use_inference_mode is not None:
        train_recurrent_module._USE_ROLLOUT_INFERENCE_MODE = use_inference_mode
    torch.manual_seed(8833)
    env = SelfPlayBattleEnv(seed=8833, max_ticks=128)
    env.reset(seed=8833)
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    env._structured_obs_builder = builder
    model = ClasherPolicy(
        PolicyConfig(
            num_tokens=builder.spec.num_tokens,
            max_entities=builder.spec.max_entities,
            d_model=32,
            num_heads=4,
            actor_layers=1,
            critic_layers=1,
            memory_size=32,
        ),
        builder.card_stat_features,
    ).eval()
    no_op = env.action_space.no_op_action
    return collect_rollout_stationary_opponents(
        envs=[env],
        learner_players=(0,),
        builder=builder,
        model=model,
        device=torch.device("cpu"),
        rollout_steps=3,
        recurrent_state=(
            model.initial_state(1)
            if recurrent_state is None
            else recurrent_state
        ),
        previous_actions=np.full((1,), no_op, dtype=np.int64),
        previous_rewards=np.zeros((1,), dtype=np.float32),
        episode_starts=np.ones((1,), dtype=np.bool_),
        opponent_model=None,
        opponent_recurrent_state=None,
        opponent_previous_actions=np.full((1,), no_op, dtype=np.int64),
        opponent_previous_rewards=np.zeros((1,), dtype=np.float32),
        opponent_episode_starts=np.ones((1,), dtype=np.bool_),
        quiet_engine=True,
    )


def test_preallocated_observation_buffers_preserve_fixed_rollout(monkeypatch):
    original = train_recurrent_module._USE_PREALLOCATED_STEP_OBSERVATION_BUFFERS
    monkeypatch.setattr(
        train_recurrent_module,
        "_USE_PREALLOCATED_STEP_OBSERVATION_BUFFERS",
        original,
    )
    stacked = _fixed_stationary_rollout(use_preallocated_buffers=False)
    preallocated = _fixed_stationary_rollout(use_preallocated_buffers=True)

    for stacked_value, preallocated_value in zip(stacked, preallocated):
        if isinstance(stacked_value, tuple):
            for stacked_tensor, preallocated_tensor in zip(
                stacked_value, preallocated_value
            ):
                torch.testing.assert_close(
                    preallocated_tensor,
                    stacked_tensor,
                    rtol=0,
                    atol=0,
                )
        elif isinstance(stacked_value, np.ndarray):
            np.testing.assert_array_equal(preallocated_value, stacked_value)
        elif hasattr(stacked_value, "__dataclass_fields__"):
            for field in fields(stacked_value):
                stacked_field = getattr(stacked_value, field.name)
                preallocated_field = getattr(preallocated_value, field.name)
                if isinstance(stacked_field, np.ndarray):
                    np.testing.assert_array_equal(preallocated_field, stacked_field)
                else:
                    assert preallocated_field == stacked_field
        else:
            assert preallocated_value == stacked_value


def test_inference_mode_preserves_rollout_and_supports_recurrent_continuation():
    reference = _fixed_stationary_rollout(
        use_preallocated_buffers=True,
        use_inference_mode=False,
    )
    inference = _fixed_stationary_rollout(
        use_preallocated_buffers=True,
        use_inference_mode=True,
    )

    for reference_value, inference_value in zip(reference, inference):
        if isinstance(reference_value, tuple):
            for reference_tensor, inference_tensor in zip(
                reference_value,
                inference_value,
            ):
                torch.testing.assert_close(
                    inference_tensor,
                    reference_tensor,
                    rtol=0,
                    atol=0,
                )
        elif isinstance(reference_value, np.ndarray):
            np.testing.assert_array_equal(inference_value, reference_value)
        elif hasattr(reference_value, "__dataclass_fields__"):
            for field in fields(reference_value):
                reference_field = getattr(reference_value, field.name)
                inference_field = getattr(inference_value, field.name)
                if isinstance(reference_field, np.ndarray):
                    np.testing.assert_array_equal(inference_field, reference_field)
                else:
                    assert inference_field == reference_field
        else:
            assert inference_value == reference_value

    assert not reference[1][0].is_inference()
    assert inference[1][0].is_inference()
    continued = _fixed_stationary_rollout(
        use_preallocated_buffers=True,
        use_inference_mode=True,
        recurrent_state=inference[1],
    )
    assert continued[1][0].is_inference()
