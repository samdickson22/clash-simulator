from __future__ import annotations

import copy
from dataclasses import fields

import numpy as np
import torch

from clasher.arena import Position
from clasher.rl import train_recurrent as train_recurrent_module
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.selfplay_env import SelfPlayBattleEnv, step_selfplay_envs
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import (
    collect_rollout,
    collect_rollout_stationary_opponents,
)
from clasher.torch_sim import TorchBattleExecutor, first_divergence
from clasher.torch_sim.diagnostics import battle_snapshot


def _make_envs(
    *,
    backend: str,
    max_ticks: tuple[int, ...],
    decision_interval_ticks: int = 8,
) -> list[SelfPlayBattleEnv]:
    envs = [
        SelfPlayBattleEnv(
            seed=9100 + index,
            decision_interval_ticks=decision_interval_ticks,
            max_ticks=ticks,
            simulation_backend=backend,
        )
        for index, ticks in enumerate(max_ticks)
    ]
    for index, env in enumerate(envs):
        env.reset(seed=9100 + index)
    return envs


def _assert_envs_exact(
    expected: list[SelfPlayBattleEnv],
    actual: list[SelfPlayBattleEnv],
) -> None:
    for reference, candidate in zip(expected, actual):
        assert reference.battle is not None
        assert candidate.battle is not None
        mismatch = first_divergence(
            battle_snapshot(reference.battle),
            battle_snapshot(candidate.battle),
        )
        assert mismatch is None, str(mismatch)
        assert candidate.rng.getstate() == reference.rng.getstate()
        assert candidate.np_rng.bit_generator.state == (
            reference.np_rng.bit_generator.state
        )


def _metrics_total(envs: list[SelfPlayBattleEnv]) -> dict[str, float]:
    result = {
        "tensor_ticks": 0.0,
        "python_ticks": 0.0,
        "shadow_checks": 0.0,
        "shadow_mismatches": 0.0,
        "unsupported_fallbacks": 0.0,
    }
    for env in envs:
        for name, value in env.pop_simulator_backend_metrics().items():
            result[name] += value
    return result


def test_batched_step_matches_sequential_with_variable_budgets_and_resets(
    monkeypatch,
) -> None:
    reference = _make_envs(backend="pytorch", max_ticks=(16, 16, 5))
    actual = _make_envs(backend="pytorch", max_ticks=(16, 16, 5))
    batch_sizes: list[int] = []
    original_step_battles = TorchBattleExecutor.step_battles

    def counted_step_battles(self, battles, ticks):
        batch_sizes.append(len(battles))
        return original_step_battles(self, battles, ticks)

    monkeypatch.setattr(TorchBattleExecutor, "step_battles", counted_step_battles)
    for _ in range(3):
        actions = [
            {0: env.action_space.no_op_action, 1: env.action_space.no_op_action}
            for env in actual
        ]
        expected_results = [
            env.step(action) for env, action in zip(reference, actions)
        ]
        actual_results = step_selfplay_envs(actual, actions)

        assert actual_results == expected_results
        _assert_envs_exact(reference, actual)
        assert _metrics_total(actual) == _metrics_total(reference)

        for index, (_, done, _) in enumerate(actual_results):
            if done:
                reference[index].reset()
                actual[index].reset()
        _assert_envs_exact(reference, actual)

    assert any(size > 1 for size in batch_sizes)


def test_mixed_supported_batch_preserves_fallback_accounting(monkeypatch) -> None:
    reference = _make_envs(backend="pytorch", max_ticks=(32, 32, 32))
    actual = _make_envs(backend="pytorch", max_ticks=(32, 32, 32))
    for envs in (reference, actual):
        battle = envs[-1].battle
        assert battle is not None
        stats = battle.card_loader.get_card("ArcherQueen")
        assert stats is not None
        battle._spawn_troop(Position(9.0, 10.0), 0, stats)

    batch_sizes: list[int] = []
    original_step_battles = TorchBattleExecutor.step_battles

    def counted_step_battles(self, battles, ticks):
        batch_sizes.append(len(battles))
        return original_step_battles(self, battles, ticks)

    monkeypatch.setattr(TorchBattleExecutor, "step_battles", counted_step_battles)
    actions = [
        {0: env.action_space.no_op_action, 1: env.action_space.no_op_action}
        for env in actual
    ]
    expected_results = [env.step(action) for env, action in zip(reference, actions)]
    actual_results = step_selfplay_envs(actual, actions)

    assert actual_results == expected_results
    _assert_envs_exact(reference, actual)
    expected_metrics = _metrics_total(reference)
    actual_metrics = _metrics_total(actual)
    assert actual_metrics == expected_metrics
    assert actual_metrics["tensor_ticks"] == 16
    assert actual_metrics["python_ticks"] == 8
    assert actual_metrics["unsupported_fallbacks"] == 1
    assert 2 in batch_sizes


def test_python_idle_fast_forward_remains_exact_and_outside_executor() -> None:
    reference = _make_envs(backend="python", max_ticks=(5, 11))
    actual = _make_envs(backend="python", max_ticks=(5, 11))
    actions = [
        {0: env.action_space.no_op_action, 1: env.action_space.no_op_action}
        for env in actual
    ]

    expected_results = [env.step(action) for env, action in zip(reference, actions)]
    actual_results = step_selfplay_envs(actual, actions)

    assert actual_results == expected_results
    _assert_envs_exact(reference, actual)
    assert _metrics_total(actual) == _metrics_total(reference) == {
        "tensor_ticks": 0.0,
        "python_ticks": 0.0,
        "shadow_checks": 0.0,
        "shadow_mismatches": 0.0,
        "unsupported_fallbacks": 0.0,
    }


def _tiny_model(builder: StructuredObservationBuilder) -> ClasherPolicy:
    return ClasherPolicy(
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


def _fixed_rollout(
    *,
    sequential: bool,
    monkeypatch,
):
    envs = _make_envs(
        backend="pytorch",
        max_ticks=(6, 6),
        decision_interval_ticks=2,
    )
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    for env in envs:
        env._structured_obs_builder = builder
        no_op = env.action_space.no_op_action
        no_op_mask = np.zeros((env.action_space.num_actions,), dtype=np.bool_)
        no_op_mask[no_op] = True
        monkeypatch.setattr(
            env,
            "get_action_mask",
            lambda _player_id, mask=no_op_mask: mask.copy(),
        )
    torch.manual_seed(9117)
    model = _tiny_model(builder)
    no_op = envs[0].action_space.no_op_action
    if sequential:
        class SequentialStepper:
            def __init__(self):
                self.metrics = {
                    "tensor_ticks": 0.0,
                    "python_ticks": 0.0,
                    "shadow_checks": 0.0,
                    "shadow_mismatches": 0.0,
                    "unsupported_fallbacks": 0.0,
                }

            def step(self, envs, actions, *, pre_action_masks=None):
                masks = (
                    [None] * len(envs)
                    if pre_action_masks is None
                    else pre_action_masks
                )
                results = [
                    env.step(action, pre_action_masks=env_masks)
                    for env, action, env_masks in zip(envs, actions, masks)
                ]
                for env in envs:
                    for name, value in env.pop_simulator_backend_metrics().items():
                        self.metrics[name] += value
                return results

            def pop_metrics(self):
                result = self.metrics
                self.metrics = {name: 0.0 for name in result}
                return result

        monkeypatch.setattr(
            train_recurrent_module,
            "BatchedSelfPlayStepper",
            SequentialStepper,
        )
    result = collect_rollout(
        envs=envs,
        builder=builder,
        model=model,
        device=torch.device("cpu"),
        rollout_steps=4,
        recurrent_state=model.initial_state(4),
        previous_actions=np.full((4,), no_op, dtype=np.int64),
        previous_rewards=np.zeros((4,), dtype=np.float32),
        episode_starts=np.ones((4,), dtype=np.bool_),
        quiet_engine=True,
    )
    snapshots = [
        copy.deepcopy(battle_snapshot(env.battle))
        for env in envs
    ]
    rng_states = [copy.deepcopy(env.rng.getstate()) for env in envs]
    return result, snapshots, rng_states


def test_recurrent_rollout_arrays_and_terminal_resets_match_sequential(
    monkeypatch,
) -> None:
    reference, reference_snapshots, reference_rng = _fixed_rollout(
        sequential=True,
        monkeypatch=monkeypatch,
    )
    monkeypatch.undo()
    actual, actual_snapshots, actual_rng = _fixed_rollout(
        sequential=False,
        monkeypatch=monkeypatch,
    )

    for expected, candidate in zip(reference, actual):
        if isinstance(expected, tuple):
            for expected_tensor, candidate_tensor in zip(expected, candidate):
                torch.testing.assert_close(
                    candidate_tensor, expected_tensor, rtol=0, atol=0
                )
        elif isinstance(expected, np.ndarray):
            np.testing.assert_array_equal(candidate, expected)
        elif hasattr(expected, "__dataclass_fields__"):
            for field in fields(expected):
                expected_value = getattr(expected, field.name)
                candidate_value = getattr(candidate, field.name)
                if isinstance(expected_value, np.ndarray):
                    np.testing.assert_array_equal(candidate_value, expected_value)
                else:
                    assert candidate_value == expected_value
        else:
            assert candidate == expected
    assert actual_snapshots == reference_snapshots
    assert actual_rng == reference_rng
    assert actual[0].episodes_finished == 2
    assert actual[0].simulator_tensor_ticks > 0


def test_stationary_opponent_rollout_uses_multi_battle_tensor_step(
    monkeypatch,
) -> None:
    envs = _make_envs(
        backend="pytorch",
        max_ticks=(4, 4),
        decision_interval_ticks=2,
    )
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    for env in envs:
        env._structured_obs_builder = builder
        no_op = env.action_space.no_op_action
        no_op_mask = np.zeros((env.action_space.num_actions,), dtype=np.bool_)
        no_op_mask[no_op] = True
        monkeypatch.setattr(
            env,
            "get_action_mask",
            lambda _player_id, mask=no_op_mask: mask.copy(),
        )
    model = _tiny_model(builder)
    no_op = envs[0].action_space.no_op_action
    batch_sizes: list[int] = []
    original_step_battles = TorchBattleExecutor.step_battles

    def counted_step_battles(self, battles, ticks):
        batch_sizes.append(len(battles))
        return original_step_battles(self, battles, ticks)

    monkeypatch.setattr(TorchBattleExecutor, "step_battles", counted_step_battles)
    rollout, *_ = collect_rollout_stationary_opponents(
        envs=envs,
        learner_players=(0, 1),
        builder=builder,
        model=model,
        device=torch.device("cpu"),
        rollout_steps=1,
        recurrent_state=model.initial_state(2),
        previous_actions=np.full((2,), no_op, dtype=np.int64),
        previous_rewards=np.zeros((2,), dtype=np.float32),
        episode_starts=np.ones((2,), dtype=np.bool_),
        opponent_model=None,
        opponent_recurrent_state=None,
        opponent_previous_actions=np.full((2,), no_op, dtype=np.int64),
        opponent_previous_rewards=np.zeros((2,), dtype=np.float32),
        opponent_episode_starts=np.ones((2,), dtype=np.bool_),
        quiet_engine=True,
    )

    assert 2 in batch_sizes
    assert rollout.simulator_tensor_ticks == 4
    assert rollout.simulator_python_ticks == 0
    assert rollout.simulator_unsupported_fallbacks == 0
