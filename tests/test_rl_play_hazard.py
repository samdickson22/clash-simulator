from __future__ import annotations

import math
from dataclasses import fields, replace

import numpy as np
import pytest
import torch
from torch import nn

from clasher.rl.model import ClasherPolicy, PolicyConfig, PolicyInputs
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import _stack_step_inputs


def _hazard_model(builder: StructuredObservationBuilder) -> ClasherPolicy:
    model = ClasherPolicy(
        PolicyConfig(
            num_tokens=builder.spec.num_tokens,
            max_entities=builder.spec.max_entities,
            d_model=32,
            num_heads=4,
            actor_layers=1,
            critic_layers=1,
            memory_size=48,
            memory_kind="structured",
            hierarchical_mode_gate_enabled=True,
            play_hazard_enabled=True,
            play_hazard_positive_weight=1.0,
            play_hazard_threshold=0.5,
            deterministic_hierarchy="hazard",
        ),
        builder.card_stat_features,
    ).eval()
    assert model.play_hazard_head is not None
    hazard_output = model.play_hazard_head[-1]
    mode_output = model.hierarchical_mode_gate[-1]
    assert isinstance(hazard_output, nn.Linear)
    assert isinstance(mode_output, nn.Linear)
    with torch.no_grad():
        hazard_output.weight.zero_()
        hazard_output.bias.fill_(math.log(0.2 / 0.8))
        mode_output.weight.zero_()
        mode_output.bias.copy_(torch.tensor([-10.0, 10.0, -10.0]))
    return model


def _concatenate_step_inputs(steps: list[PolicyInputs]) -> PolicyInputs:
    payload: dict[str, torch.Tensor | None] = {}
    for field in fields(PolicyInputs):
        values = [getattr(step, field.name) for step in steps]
        if values[0] is None:
            assert all(value is None for value in values)
            payload[field.name] = None
        else:
            assert all(isinstance(value, torch.Tensor) for value in values)
            payload[field.name] = torch.cat(values, dim=1)  # type: ignore[arg-type]
    return PolicyInputs(**payload)  # type: ignore[arg-type]


def test_cumulative_play_hazard_triggers_and_resets_inside_model_state() -> None:
    env = SelfPlayBattleEnv(seed=91, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=16)
    env._structured_obs_builder = builder
    model = _hazard_model(builder)
    observation = builder.build(env.battle, 0)
    action_mask = env.get_action_mask(0)[None, :]
    no_op = env.action_space.no_op_action
    state = model.initial_state(1)
    actions: list[int] = []
    for step in range(4):
        inputs = _stack_step_inputs(
            [observation],
            action_mask,
            np.asarray([no_op]),
            np.asarray([0.0], dtype=np.float32),
            np.asarray([step == 0]),
            torch.device("cpu"),
        )
        action, _, _, state, _ = model.act(inputs, state, deterministic=True)
        actions.append(int(action.item()))
    assert actions[:3] == [no_op, no_op, no_op]
    assert actions[3] < no_op
    torch.testing.assert_close(state[0][:, -1], torch.zeros(1))


def test_hazard_conditioned_stochastic_rollout_matches_batched_log_probs() -> None:
    env = SelfPlayBattleEnv(seed=911, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=16)
    env._structured_obs_builder = builder
    model = _hazard_model(builder)
    observation = builder.build(env.battle, 0)
    action_mask = env.get_action_mask(0)[None, :]
    no_op = env.action_space.no_op_action
    initial_state = model.initial_state(1)
    state = tuple(value.clone() for value in initial_state)
    previous_action = no_op
    steps: list[PolicyInputs] = []
    actions: list[torch.Tensor] = []
    log_probs: list[torch.Tensor] = []
    for index in range(4):
        inputs = _stack_step_inputs(
            [observation],
            action_mask,
            np.asarray([previous_action]),
            np.asarray([0.0], dtype=np.float32),
            np.asarray([index == 0]),
            torch.device("cpu"),
        )
        action, log_prob, _, state, _ = model.act(
            inputs,
            state,
            deterministic=False,
            hazard_conditioned_stochastic=True,
        )
        steps.append(inputs)
        actions.append(action)
        log_probs.append(log_prob)
        previous_action = int(action.item())

    assert [int(action.item()) == no_op for action in actions] == [
        True,
        True,
        True,
        False,
    ]
    batched = _concatenate_step_inputs(steps)
    with torch.no_grad():
        output = model(batched, initial_state)
        distribution, gates, stored_hazard = (
            model.hazard_conditioned_distribution(
                output,
                batched.action_mask,
                initial_state[0][:, -1],
                episode_starts=batched.episode_starts,
            )
        )
    assert gates.tolist() == [[False, False, False, True]]
    torch.testing.assert_close(stored_hazard, torch.zeros(1))
    batched_actions = torch.cat(actions, dim=1)
    sequential_log_probs = torch.cat(log_probs, dim=1)
    torch.testing.assert_close(
        distribution.log_prob(batched_actions),
        sequential_log_probs,
    )
    replay_distribution = model.distribution_for_hazard_gate(
        output,
        batched.action_mask,
        batched_actions < env.action_space.no_op_action,
    )
    torch.testing.assert_close(
        replay_distribution.log_prob(batched_actions),
        sequential_log_probs,
    )


def test_hazard_conditioned_sequence_resets_accumulator_on_episode_start() -> None:
    env = SelfPlayBattleEnv(seed=912, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=16)
    env._structured_obs_builder = builder
    model = _hazard_model(builder)
    observation = builder.build(env.battle, 0)
    action_mask = env.get_action_mask(0)[None, :]
    no_op = env.action_space.no_op_action
    steps = [
        _stack_step_inputs(
            [observation],
            action_mask,
            np.asarray([no_op]),
            np.asarray([0.0], dtype=np.float32),
            np.asarray([index in {0, 2}]),
            torch.device("cpu"),
        )
        for index in range(4)
    ]
    batched = _concatenate_step_inputs(steps)
    initial_state = model.initial_state(1)
    with torch.no_grad():
        output = model(batched, initial_state)
        _, gates, stored_hazard = model.hazard_conditioned_distribution(
            output,
            batched.action_mask,
            initial_state[0][:, -1],
            episode_starts=batched.episode_starts,
        )
    assert gates.tolist() == [[False, False, False, False]]
    torch.testing.assert_close(stored_hazard, torch.full((1,), 0.36))


def test_play_hazard_requires_structured_hierarchical_configuration() -> None:
    base = PolicyConfig(num_tokens=4, max_entities=8)
    with pytest.raises(ValueError, match="structured memory"):
        replace(
            base,
            play_hazard_enabled=True,
            hierarchical_mode_gate_enabled=True,
            deterministic_hierarchy="hazard",
        )
    with pytest.raises(ValueError, match="hierarchical mode gate"):
        replace(
            base,
            memory_kind="structured",
            play_hazard_enabled=True,
            deterministic_hierarchy="hazard",
        )
    with pytest.raises(ValueError, match="enabled together"):
        replace(base, deterministic_hierarchy="hazard")
    with pytest.raises(ValueError, match="gain requires the adapter"):
        replace(base, play_hazard_adapter_gain=0.5)
    with pytest.raises(ValueError, match=r"gain must be finite and in \[0, 1\]"):
        replace(
            base,
            memory_kind="structured",
            hierarchical_mode_gate_enabled=True,
            play_hazard_enabled=True,
            deterministic_hierarchy="hazard",
            play_hazard_adapter_size=8,
            play_hazard_adapter_gain=1.1,
        )


def test_zero_initialized_hazard_adapter_preserves_policy_exactly() -> None:
    env = SelfPlayBattleEnv(seed=92, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=16)
    env._structured_obs_builder = builder
    base = _hazard_model(builder)
    adapted = ClasherPolicy(
        replace(base.config, play_hazard_adapter_size=8),
        builder.card_stat_features,
    ).eval()
    incompatible = adapted.load_state_dict(base.state_dict(), strict=False)
    assert not incompatible.unexpected_keys
    assert incompatible.missing_keys
    assert all(
        name.startswith("play_hazard_adapter.")
        for name in incompatible.missing_keys
    )
    observation = builder.build(env.battle, 0)
    action_mask = env.get_action_mask(0)[None, :]
    inputs = _stack_step_inputs(
        [observation],
        action_mask,
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )
    with torch.no_grad():
        expected = base(inputs)
        actual = adapted(inputs)
    assert expected.play_hazard_logits is not None
    assert actual.play_hazard_logits is not None
    torch.testing.assert_close(actual.play_hazard_logits, expected.play_hazard_logits)
    torch.testing.assert_close(actual.joint_logits, expected.joint_logits)


def test_hazard_adapter_enemy_y_gate_is_exactly_local() -> None:
    env = SelfPlayBattleEnv(seed=93, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=16)
    env._structured_obs_builder = builder
    base = _hazard_model(builder)
    adapted = ClasherPolicy(
        replace(
            base.config,
            play_hazard_adapter_size=8,
            play_hazard_adapter_enemy_y_gate=0.4,
        ),
        builder.card_stat_features,
    ).eval()
    adapted.load_state_dict(base.state_dict(), strict=False)
    assert adapted.play_hazard_adapter is not None
    adapter_output = adapted.play_hazard_adapter[-1]
    assert isinstance(adapter_output, nn.Linear)
    with torch.no_grad():
        adapter_output.bias.fill_(1.0)
    observation = builder.build(env.battle, 0)
    action_mask = env.get_action_mask(0)[None, :]
    inputs = _stack_step_inputs(
        [observation],
        action_mask,
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )
    with torch.no_grad():
        peaceful_base = base(inputs)
        peaceful_adapted = adapted(inputs)
    assert peaceful_base.play_hazard_logits is not None
    assert peaceful_adapted.play_hazard_logits is not None
    torch.testing.assert_close(
        peaceful_adapted.play_hazard_logits,
        peaceful_base.play_hazard_logits,
    )

    threatened_features = inputs.entity_features.clone()
    threatened_mask = inputs.entity_mask.clone()
    threatened_mask[..., 0] = True
    threatened_features[..., 0, 1] = 0.2
    threatened_features[..., 0, 3] = 1.0
    threatened_features[..., 0, 4] = 1.0
    threatened_inputs = replace(
        inputs,
        entity_features=threatened_features,
        entity_mask=threatened_mask,
    )
    with torch.no_grad():
        threatened_base = base(threatened_inputs)
        threatened_adapted = adapted(threatened_inputs)
    assert threatened_base.play_hazard_logits is not None
    assert threatened_adapted.play_hazard_logits is not None
    torch.testing.assert_close(
        threatened_adapted.play_hazard_logits,
        threatened_base.play_hazard_logits + 1.0,
    )


@pytest.mark.parametrize(("gain", "expected_delta"), ((0.0, 0.0), (0.25, 0.25)))
def test_hazard_adapter_gain_calibrates_only_adapter_residual(
    gain: float,
    expected_delta: float,
) -> None:
    env = SelfPlayBattleEnv(seed=94, max_ticks=128)
    env.reset()
    builder = StructuredObservationBuilder(card_vocab=["Knight"], max_entities=16)
    env._structured_obs_builder = builder
    base = _hazard_model(builder)
    adapted = ClasherPolicy(
        replace(
            base.config,
            play_hazard_adapter_size=8,
            play_hazard_adapter_enemy_y_gate=0.4,
            play_hazard_adapter_gain=gain,
        ),
        builder.card_stat_features,
    ).eval()
    adapted.load_state_dict(base.state_dict(), strict=False)
    assert adapted.play_hazard_adapter is not None
    adapter_output = adapted.play_hazard_adapter[-1]
    assert isinstance(adapter_output, nn.Linear)
    with torch.no_grad():
        adapter_output.bias.fill_(1.0)
    observation = builder.build(env.battle, 0)
    action_mask = env.get_action_mask(0)[None, :]
    inputs = _stack_step_inputs(
        [observation],
        action_mask,
        np.asarray([env.action_space.no_op_action]),
        np.asarray([0.0], dtype=np.float32),
        np.asarray([True]),
        torch.device("cpu"),
    )
    threatened_features = inputs.entity_features.clone()
    threatened_mask = inputs.entity_mask.clone()
    threatened_mask[..., 0] = True
    threatened_features[..., 0, 1] = 0.2
    threatened_features[..., 0, 3] = 1.0
    threatened_features[..., 0, 4] = 1.0
    threatened_inputs = replace(
        inputs,
        entity_features=threatened_features,
        entity_mask=threatened_mask,
    )
    with torch.no_grad():
        expected = base(threatened_inputs)
        actual = adapted(threatened_inputs)
    assert expected.play_hazard_logits is not None
    assert actual.play_hazard_logits is not None
    torch.testing.assert_close(
        actual.play_hazard_logits,
        expected.play_hazard_logits + expected_delta,
    )
