"""Independent M0 software contracts; none of these tests fits gameplay weights."""
from dataclasses import fields, replace
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig, PolicyInputs
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import _sequence_inputs, collect_rollout, compute_gae


@pytest.fixture(scope="module")
def collected():
    torch.manual_seed(289)
    torch.set_num_threads(1)
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=32, public_entity_levels=True, public_hand_levels=True, card_semantics_version=4)
    env = SelfPlayBattleEnv(seed=289, decision_interval_ticks=5, max_ticks=100, public_contract_version=4)
    env._structured_obs_builder = builder
    env.reset()
    model = ClasherPolicy(PolicyConfig(
        num_tokens=builder.spec.num_tokens, max_entities=32,
        public_contract_version=4, public_observation_confidence=True,
        public_token_names=builder.token_names, card_semantics_version=4,
        d_model=32, num_heads=4, actor_layers=1, critic_layers=1, memory_size=48,
    ), builder.card_stat_features).eval()
    rollout, state, *_ = collect_rollout(
        envs=[env], builder=builder, model=model, device=torch.device("cpu"),
        rollout_steps=6, recurrent_state=model.initial_state(2),
        previous_actions=np.full(2, env.action_space.no_op_action, dtype=np.int64),
        previous_rewards=np.zeros(2, dtype=np.float32),
        episode_starts=np.ones(2, dtype=np.bool_), quiet_engine=True,
    )
    return model, rollout, state, env, builder


def _slice(inputs, start, stop):
    return PolicyInputs(**{
        field.name: None if getattr(inputs, field.name) is None
        else getattr(inputs, field.name)[:, start:stop]
        for field in fields(PolicyInputs)
    })


def test_scalar_behavior_likelihood_replays_with_every_legal_factor(collected):
    model, rollout, *_ = collected
    inputs = _sequence_inputs(rollout, slice(None), torch.device("cpu"))
    model.train()
    with torch.no_grad():
        output = model(inputs, tuple(torch.from_numpy(x) for x in
                      (rollout.initial_hidden, rollout.initial_cell)))
    model.eval()
    distribution = output.distribution()
    actions = torch.from_numpy(rollout.actions)
    torch.testing.assert_close(distribution.log_prob(actions),
                               torch.from_numpy(rollout.old_log_probs), atol=2e-6, rtol=2e-6)
    assert inputs.action_mask.gather(-1, actions.unsqueeze(-1)).all()
    assert (distribution.probs[~inputs.action_mask] == 0).all()
    # Independently multiply slot mass by conditional location mass. Illegal
    # cards and different legal tile counts must not silently change slot mass.
    placement = inputs.action_mask[..., :2304].reshape(2, 6, 4, 576)
    legal_types = torch.cat((placement.any(-1), inputs.action_mask[..., 2304:]), -1)
    type_p = output.action_type_logits.masked_fill(~legal_types, -torch.inf).softmax(-1)
    for slot in range(4):
        tile_p = output.location_logits[..., slot, :].masked_fill(
            ~placement[..., slot, :], -torch.inf).softmax(-1).nan_to_num()
        expected = type_p[..., slot, None] * tile_p
        torch.testing.assert_close(distribution.probs[..., slot*576:(slot+1)*576], expected)
    torch.testing.assert_close(distribution.probs[..., 2304:], type_p[..., 4:])


def test_chunked_recurrence_and_episode_reset_match_uninterrupted(collected):
    model, rollout, *_ = collected
    inputs = _sequence_inputs(rollout, slice(None), torch.device("cpu"))
    with torch.no_grad():
        whole = model(inputs)
        prefix = model(_slice(inputs, 0, 3))
        suffix = model(_slice(inputs, 3, None), prefix.next_state)
        reset = replace(_slice(inputs, 3, None),
                        episode_starts=torch.tensor([[True, False, False]]*2))
        independent = model(reset)
        restarted = model(reset, tuple(torch.full_like(x, 100) for x in prefix.next_state))
    torch.testing.assert_close(suffix.joint_logits, whole.joint_logits[:, 3:])
    for actual, expected in zip(suffix.next_state, whole.next_state):
        torch.testing.assert_close(actual, expected)
    torch.testing.assert_close(restarted.joint_logits, independent.joint_logits)
    for actual, expected in zip(restarted.next_state, independent.next_state):
        torch.testing.assert_close(actual, expected)


def test_privileged_critic_cannot_change_actor_or_recurrent_state(collected):
    model, rollout, *_ = collected
    inputs = _sequence_inputs(rollout, slice(None), torch.device("cpu"))
    changed = replace(inputs,
        critic_entity_features=inputs.critic_entity_features + 10,
        critic_card_ids=torch.zeros_like(inputs.critic_card_ids),
        critic_global_features=inputs.critic_global_features - 10)
    with torch.no_grad():
        base, altered = model(inputs), model(changed)
    assert not torch.equal(base.values, altered.values), "critic intervention was ineffective"
    torch.testing.assert_close(base.joint_logits, altered.joint_logits, atol=0, rtol=0)
    for actual, expected in zip(base.next_state, altered.next_state):
        torch.testing.assert_close(actual, expected, atol=0, rtol=0)
    model.zero_grad(set_to_none=True)
    model(inputs).values.sum().backward()
    assert all(p.grad is None for p in model.actor_encoder.parameters())
    model.zero_grad(set_to_none=True)


def test_gamma_one_gae_bootstraps_collection_boundary_but_not_terminal():
    rollout = SimpleNamespace(
        rewards=np.array([[1, 2, 3], [1, 2, 3]], dtype=np.float32),
        old_values=np.array([[4, 5, 6], [4, 5, 6]], dtype=np.float32),
        bootstrap_values=np.array([10, 10], dtype=np.float32),
        dones=np.array([[False, False, False], [False, True, False]]),
        num_sequences=2, sequence_length=3, truncation_bootstrap_values=None,
    )
    advantages, returns = compute_gae(rollout, gamma=1, gae_lambda=.95)
    # At true termination t=1, the reset episode's value and reward must not leak.
    expected = np.array([[11.1675, 9.65, 7], [-.85, -3, 7]], dtype=np.float32)
    np.testing.assert_allclose(advantages, expected, atol=1e-6)
    np.testing.assert_allclose(returns, expected + rollout.old_values, atol=1e-6)


def test_gamma_one_potential_telescopes_and_terminal_potential_is_zero(monkeypatch):
    env = SelfPlayBattleEnv(seed=290, reward_shaping_gamma=1, elixir_leak_penalty_scale=0)
    env.reset()
    env._prev_reward_potential_p0 = .3
    potentials = iter([.8, -.4, .6])
    monkeypatch.setattr("clasher.rl.selfplay_env.reward_potential_p0", lambda *_: next(potentials))
    rewards = [env._compute_dense_rewards(done=terminal) for terminal in [False, False, True]]
    assert rewards[0][0] + rewards[1][0] == pytest.approx(-.4 - .3)
    assert sum(r[0] for r in rewards) == pytest.approx(-.3)
    assert all(r[0] == -r[1] for r in rewards)


def test_current_weight_prefix_replay_replaces_stale_collector_state(collected):
    from copy import deepcopy
    from clasher.rl.council_recurrence import RecurrentHistory, reconstruct_recurrent_state

    original_model, rollout, *_ = collected
    model = deepcopy(original_model)
    inputs = _sequence_inputs(rollout, slice(None), torch.device("cpu"))
    history = RecurrentHistory(2)
    history.append(_slice(inputs, 0, 3))
    history.append(_slice(inputs, 3, None))
    prefixes = history.snapshot()
    with torch.no_grad():
        old = model(inputs).next_state
        # A controlled weight intervention, not gameplay fitting.
        for name, parameter in model.named_parameters():
            if "memory" in name:
                parameter.add_(.1)
        expected = model(inputs).next_state
    refreshed = reconstruct_recurrent_state(model, prefixes, device=torch.device("cpu"),
                                             replay_chunk_steps=2)
    assert any(not torch.allclose(a, b) for a, b in zip(old, expected))
    for actual, target in zip(refreshed, expected):
        torch.testing.assert_close(actual, target, atol=2e-6, rtol=2e-6)
        assert not actual.requires_grad
    # The explicitly bounded path means replaying the retained suffix from zero.
    bounded = reconstruct_recurrent_state(model, prefixes, device=torch.device("cpu"),
                                           burn_in_steps=2)
    with torch.no_grad():
        expected_bounded = model(_slice(inputs, 4, None)).next_state
    for actual, target in zip(bounded, expected_bounded):
        torch.testing.assert_close(actual, target)
    assert any(not torch.allclose(a, b) for a, b in zip(bounded, refreshed))


def test_history_resets_each_seat_and_owns_immutable_snapshots(collected):
    from clasher.rl.council_recurrence import RecurrentHistory, reconstruct_recurrent_state

    model, rollout, *_ = collected
    inputs = _sequence_inputs(rollout, slice(None), torch.device("cpu"))
    history = RecurrentHistory(2)
    history.append(_slice(inputs, 0, 3))
    frozen = history.snapshot()
    assert all(getattr(prefix, field.name) is None for prefix in frozen
               for field in fields(PolicyInputs) if field.name.startswith("critic_"))
    suffix = _slice(inputs, 3, None)
    starts = torch.zeros_like(suffix.episode_starts)
    starts[0, 1] = True
    history.append(replace(suffix, episode_starts=starts))
    current = history.snapshot()
    assert [prefix.sequence_length for prefix in frozen] == [3, 3]
    assert [prefix.sequence_length for prefix in current] == [2, 6]
    combined_starts = inputs.episode_starts.clone()
    combined_starts[0, 4] = True
    with torch.no_grad():
        expected = model(replace(inputs, episode_starts=combined_starts)).next_state
    actual = reconstruct_recurrent_state(model, current, device=torch.device("cpu"))
    for a, b in zip(actual, expected):
        torch.testing.assert_close(a, b)
    current[0].global_features.zero_()
    assert torch.count_nonzero(history.snapshot()[0].global_features)
    invalid = RecurrentHistory(2)
    with pytest.raises(ValueError, match="episode reset"):
        invalid.append(_slice(inputs, 1, 2))


@pytest.mark.parametrize("terminal", [False, True])
def test_v4_env_distinguishes_time_limit_and_absorbing_terminal(monkeypatch, terminal):
    env = SelfPlayBattleEnv(seed=291, decision_interval_ticks=5, max_ticks=1,
                           public_contract_version=4)
    env.reset()
    env._prev_reward_potential_p0 = .3
    monkeypatch.setattr("clasher.rl.selfplay_env.reward_potential_p0", lambda *_: .8)
    if terminal:
        env.battle.game_over = True
        env.battle.winner = 0
    rewards, done, info = env.step({0: env.action_space.no_op_action,
                                    1: env.action_space.no_op_action})
    assert done
    assert info.terminated is terminal
    assert info.truncated is (not terminal)
    expected = (1 - .05 * .3) if terminal else .05 * (.8 - .3)
    assert rewards[0] == pytest.approx(expected)
    assert rewards[1] == pytest.approx(-expected)


def test_v4_rejected_command_is_logged_without_principal_reward_penalty(monkeypatch):
    env = SelfPlayBattleEnv(seed=291, public_contract_version=4)
    env.reset()
    env._prev_reward_potential_p0 = 0
    monkeypatch.setattr("clasher.rl.selfplay_env.reward_potential_p0", lambda *_: 0)
    rewards, done, info = env.step({0: env.action_space.ability_action,
                                    1: env.action_space.no_op_action})
    assert not done
    assert info.action_success[0] is False
    assert rewards == {0: 0, 1: 0}


def test_gae_time_limit_bootstraps_final_observation_and_cuts_reset_episode():
    rollout = SimpleNamespace(
        rewards=np.array([[1, 2, 3]], dtype=np.float32),
        old_values=np.array([[4, 5, 6]], dtype=np.float32),
        bootstrap_values=np.array([10], dtype=np.float32),
        dones=np.array([[False, True, False]]),
        truncation_bootstrap_values=np.array([[0, 20, 0]], dtype=np.float32),
        num_sequences=1, sequence_length=3,
    )
    advantages, returns = compute_gae(rollout, gamma=1, gae_lambda=.95)
    np.testing.assert_allclose(advantages, [[18.15, 17, 7]], atol=1e-6)
    np.testing.assert_allclose(returns, [[22.15, 22, 13]], atol=1e-6)


def test_scalar_collector_refreshes_prefix_after_weight_change(collected):
    from copy import deepcopy
    from clasher.rl.council_recurrence import reconstruct_recurrent_state

    original, first, stale_state, env, builder = collected
    model = deepcopy(original)
    with torch.no_grad():
        for name, parameter in model.named_parameters():
            if "memory" in name:
                parameter.add_(.1)
    expected = reconstruct_recurrent_state(model, model._council_rollout_history.snapshot(),
                                           device=torch.device("cpu"))
    second, *_ = collect_rollout(
        envs=[env], builder=builder, model=model, device=torch.device("cpu"),
        rollout_steps=2, recurrent_state=stale_state,
        previous_actions=first.actions[:, -1], previous_rewards=np.ones(2, dtype=np.float32),
        episode_starts=np.zeros(2, dtype=np.bool_), quiet_engine=True,
    )
    assert any(not torch.allclose(a, b) for a, b in zip(stale_state, expected))
    for actual, target in zip((second.initial_hidden, second.initial_cell), expected):
        np.testing.assert_allclose(actual, target.numpy(), atol=2e-6, rtol=2e-6)
    assert np.count_nonzero(second.previous_rewards) == 0
    assert all(prefix.sequence_length == 6 for prefix in second.recurrent_prefixes)
    with torch.no_grad():
        output = model(_sequence_inputs(second, slice(None), torch.device("cpu")), expected)
    torch.testing.assert_close(output.distribution().log_prob(torch.from_numpy(second.actions)),
                               torch.from_numpy(second.old_log_probs), atol=2e-6, rtol=2e-6)


def test_scalar_time_limit_stores_value_before_reset_not_reset_value(collected, monkeypatch):
    from copy import deepcopy

    original, _, _, _, builder = collected
    model = deepcopy(original)
    del model._council_rollout_history
    env = SelfPlayBattleEnv(seed=292, decision_interval_ticks=5, max_ticks=1,
                           public_contract_version=4)
    env._structured_obs_builder = builder
    env.reset()
    calls = []
    forward = model.forward

    def record(inputs, state=None):
        output = forward(inputs, state)
        calls.append((inputs.episode_starts.clone(), output.values.detach().clone()))
        return output

    monkeypatch.setattr(model, "forward", record)
    rollout, *_ = collect_rollout(
        envs=[env], builder=builder, model=model, device=torch.device("cpu"),
        rollout_steps=1, recurrent_state=model.initial_state(2),
        previous_actions=np.full(2, env.action_space.no_op_action, dtype=np.int64),
        previous_rewards=np.zeros(2, dtype=np.float32),
        episode_starts=np.ones(2, dtype=np.bool_), quiet_engine=True,
    )
    assert len(calls) == 3, "action, final-state bootstrap, then reset bootstrap"
    assert calls[0][0].all() and not calls[1][0].any() and calls[2][0].all()
    assert not torch.equal(calls[1][1], calls[2][1]), "final/reset intervention was ineffective"
    np.testing.assert_allclose(rollout.truncation_bootstrap_values, calls[1][1].numpy())
    assert rollout.dones.all()
    advantages, _ = compute_gae(rollout, gamma=1, gae_lambda=.95)
    np.testing.assert_allclose(advantages, rollout.rewards + calls[1][1].numpy()
                               - rollout.old_values, atol=1e-6)


def test_prefix_history_accepts_changing_trimmed_entity_padding(collected):
    from clasher.rl.council_recurrence import RecurrentHistory, reconstruct_recurrent_state

    model, rollout, *_ = collected
    inputs = _sequence_inputs(rollout, slice(None), torch.device("cpu"))
    prefix = _slice(inputs, 0, 3)
    values = {}
    for field in fields(PolicyInputs):
        value = getattr(prefix, field.name)
        if value is not None and field.name.startswith(("entity_", "critic_entity_")):
            if field.name.endswith("mask"):
                assert not value[:, :, 16:].any()
            value = value[:, :, :16]
        values[field.name] = value
    history = RecurrentHistory(2)
    history.append(PolicyInputs(**values))
    history.append(_slice(inputs, 3, None))
    state = reconstruct_recurrent_state(model, history.snapshot(), device=torch.device("cpu"))
    with torch.no_grad():
        expected = model(inputs).next_state
    for actual, target in zip(state, expected):
        torch.testing.assert_close(actual, target)
