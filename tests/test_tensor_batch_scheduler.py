from __future__ import annotations

from collections.abc import Sequence

import pytest

from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.tensor_batch_scheduler import TensorBatchScheduler
from clasher.torch_sim import first_divergence
from clasher.torch_sim.diagnostics import battle_snapshot


def _make_envs(
    *,
    count: int,
    backend: str,
    max_ticks: int = 7200,
) -> list[SelfPlayBattleEnv]:
    envs = [
        SelfPlayBattleEnv(
            decision_interval_ticks=8,
            max_ticks=max_ticks,
            seed=9100 + index,
            simulation_backend=backend,
        )
        for index in range(count)
    ]
    for index, env in enumerate(envs):
        env.reset(seed=9100 + index)
    return envs


def _assert_battles_match(
    expected: Sequence[SelfPlayBattleEnv],
    actual: Sequence[SelfPlayBattleEnv],
) -> None:
    for index, (reference, candidate) in enumerate(zip(expected, actual)):
        assert reference.battle is not None
        assert candidate.battle is not None
        mismatch = first_divergence(
            battle_snapshot(reference.battle),
            battle_snapshot(candidate.battle),
            path=f"envs[{index}]",
        )
        assert mismatch is None, str(mismatch)


@pytest.mark.parametrize("backend", ["pytorch-shadow", "pytorch"])
def test_twelve_environment_schedule_matches_sequential_steps_exactly(
    backend: str,
) -> None:
    sequential = _make_envs(count=12, backend=backend)
    scheduled = _make_envs(count=12, backend=backend)
    starts = (
        0.0,
        1.25,
        119.9,
        120.0,
        179.9,
        180.0,
        239.9,
        240.0,
        299.9,
        0.05,
        42.0,
        118.0,
    )
    for start, reference, candidate in zip(starts, sequential, scheduled):
        assert reference.battle is not None
        assert candidate.battle is not None
        reference.battle.time = start
        candidate.battle.time = start

    actions = [
        {0: env.action_space.no_op_action, 1: env.action_space.no_op_action}
        for env in scheduled
    ]
    expected_results = [
        env.step(action) for env, action in zip(sequential, actions)
    ]
    scheduler = TensorBatchScheduler(scheduled)
    actual_results = scheduler.step(actions)

    _assert_battles_match(sequential, scheduled)
    assert actual_results == expected_results
    metrics = scheduler.metrics_dict()
    assert metrics["step_calls"] == 1
    assert metrics["battle_windows"] == 12
    assert metrics["tensor_batches"] == 1
    assert metrics["max_batch_size"] == 12
    assert metrics["shadow_mismatches"] == 0


def test_scheduler_groups_unequal_remaining_windows_without_reordering() -> None:
    sequential = _make_envs(count=4, backend="pytorch", max_ticks=8)
    scheduled = _make_envs(count=4, backend="pytorch", max_ticks=8)
    start_ticks = (0, 4, 0, 7)
    for tick, reference, candidate in zip(start_ticks, sequential, scheduled):
        assert reference.battle is not None
        assert candidate.battle is not None
        reference.battle.tick = tick
        candidate.battle.tick = tick
        reference.battle.time = 0.05 * tick
        candidate.battle.time = 0.05 * tick

    actions = [
        {0: env.action_space.no_op_action, 1: env.action_space.no_op_action}
        for env in scheduled
    ]
    expected_results = [
        env.step(action) for env, action in zip(sequential, actions)
    ]
    scheduler = TensorBatchScheduler(scheduled)
    actual_results = scheduler.step(actions)

    _assert_battles_match(sequential, scheduled)
    assert actual_results == expected_results
    assert [result[2].ticks_advanced for result in actual_results] == [8, 4, 8, 1]
    metrics = scheduler.metrics_dict()
    assert metrics["tensor_batches"] == 3
    assert metrics["max_batch_size"] == 2


def test_scheduler_reloads_same_clock_action_mutations_between_windows() -> None:
    sequential = _make_envs(count=2, backend="python")
    scheduled = _make_envs(count=2, backend="pytorch")
    scheduler = TensorBatchScheduler(scheduled)
    no_op_actions = [
        {0: env.action_space.no_op_action, 1: env.action_space.no_op_action}
        for env in scheduled
    ]

    expected_first = [
        env.step(action) for env, action in zip(sequential, no_op_actions)
    ]
    actual_first = scheduler.step(no_op_actions)
    _assert_battles_match(sequential, scheduled)
    assert actual_first == expected_first

    for reference, candidate in zip(sequential, scheduled):
        assert reference.battle is not None
        assert candidate.battle is not None
        for env in (reference, candidate):
            assert env.battle is not None
            env.battle.players[0].elixir = 5.0
            env.battle.players[0].hand[0] = "Knight"

    deploy_action = scheduled[0].action_space.encode_action(0, 9, 10, 0)
    second_actions = [
        {0: deploy_action, 1: scheduled[0].action_space.no_op_action},
        {
            0: scheduled[1].action_space.no_op_action,
            1: scheduled[1].action_space.no_op_action,
        },
    ]
    expected_second = [
        env.step(action) for env, action in zip(sequential, second_actions)
    ]
    actual_second = scheduler.step(second_actions)

    _assert_battles_match(sequential, scheduled)
    assert actual_second == expected_second
    assert actual_second[0][2].action_success[0]
    assert scheduler.metrics_dict()["step_calls"] == 2


def test_python_schedule_preserves_local_idle_fast_forward() -> None:
    sequential = _make_envs(count=3, backend="python")
    scheduled = _make_envs(count=3, backend="python")
    actions = [
        {0: env.action_space.no_op_action, 1: env.action_space.no_op_action}
        for env in scheduled
    ]

    expected_results = [
        env.step(action) for env, action in zip(sequential, actions)
    ]
    scheduler = TensorBatchScheduler(scheduled)
    actual_results = scheduler.step(actions)

    _assert_battles_match(sequential, scheduled)
    assert actual_results == expected_results
    metrics = scheduler.metrics_dict()
    assert metrics["tensor_batches"] == 0
    assert metrics["tensor_ticks"] == 0


def test_scheduler_rejects_mixed_backends() -> None:
    python_env = _make_envs(count=1, backend="python")[0]
    pytorch_env = _make_envs(count=1, backend="pytorch")[0]

    with pytest.raises(ValueError, match="one simulator backend"):
        TensorBatchScheduler([python_env, pytorch_env])
