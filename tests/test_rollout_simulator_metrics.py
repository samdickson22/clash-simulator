from __future__ import annotations

from dataclasses import fields

import numpy as np
import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.parallel_rollout import concatenate_rollouts
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import (
    RolloutBatch,
    _checkpoint_simulator_metrics,
    _format_simulator_metrics,
    collect_rollout,
)


def _collect_no_op_rollout(*, backend: str, num_envs: int) -> RolloutBatch:
    envs = [
        SelfPlayBattleEnv(
            seed=7600 + index,
            max_ticks=128,
            simulation_backend=backend,
        )
        for index in range(num_envs)
    ]
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    for index, env in enumerate(envs):
        env._structured_obs_builder = builder
        env.reset(seed=7600 + index)
        assert env.battle is not None
        for player in env.battle.players:
            player.hand = [None, None, None, None]
            player.cycle_queue.clear()
    torch.manual_seed(7600)
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
    agents = 2 * num_envs
    no_op = envs[0].action_space.no_op_action
    rollout, *_ = collect_rollout(
        envs=envs,
        builder=builder,
        model=model,
        device=torch.device("cpu"),
        rollout_steps=2,
        recurrent_state=model.initial_state(agents),
        previous_actions=np.full((agents,), no_op, dtype=np.int64),
        previous_rewards=np.zeros((agents,), dtype=np.float32),
        episode_starts=np.ones((agents,), dtype=np.bool_),
        quiet_engine=True,
    )
    return rollout


def test_python_collector_reports_idle_fast_forward_ticks() -> None:
    rollout = _collect_no_op_rollout(backend="python", num_envs=1)

    assert rollout.simulator_metrics == {
        "step_calls": 2.0,
        "battle_windows": 2.0,
        "tensor_batches": 0.0,
        "max_batch_size": 0.0,
        "python_ticks": 16.0,
        "tensor_ticks": 0.0,
        "shadow_checks": 0.0,
        "shadow_mismatches": 0.0,
        "unsupported_fallbacks": 0.0,
    }


def test_pytorch_collector_reports_batched_tensor_ticks() -> None:
    rollout = _collect_no_op_rollout(backend="pytorch", num_envs=2)

    assert rollout.simulator_metrics == {
        "step_calls": 2.0,
        "battle_windows": 4.0,
        "tensor_batches": 2.0,
        "max_batch_size": 2.0,
        "tensor_ticks": 32.0,
        "python_ticks": 0.0,
        "shadow_checks": 0.0,
        "shadow_mismatches": 0.0,
        "unsupported_fallbacks": 0.0,
    }


def test_parallel_concat_aggregates_counters_and_preserves_legacy_default() -> None:
    python_rollout = _collect_no_op_rollout(backend="python", num_envs=1)
    pytorch_rollout = _collect_no_op_rollout(backend="pytorch", num_envs=2)

    combined = concatenate_rollouts([python_rollout, pytorch_rollout])

    assert combined.simulator_metrics == {
        "battle_windows": 6.0,
        "max_batch_size": 2.0,
        "python_ticks": 16.0,
        "shadow_checks": 0.0,
        "shadow_mismatches": 0.0,
        "step_calls": 4.0,
        "tensor_batches": 2.0,
        "tensor_ticks": 32.0,
        "unsupported_fallbacks": 0.0,
    }
    assert combined.num_sequences == (
        python_rollout.num_sequences + pytorch_rollout.num_sequences
    )

    legacy_payload = {
        field.name: getattr(python_rollout, field.name)
        for field in fields(RolloutBatch)
        if field.name != "simulator_metrics"
    }
    legacy = RolloutBatch(**legacy_payload)
    assert legacy.simulator_metrics == {}


def test_simulator_metrics_have_stable_log_and_checkpoint_names() -> None:
    metrics = {
        "tensor_ticks": 64.0,
        "python_ticks": 8.0,
        "unsupported_fallbacks": 1.0,
        "shadow_mismatches": 2.0,
        "shadow_checks": 9.0,
        "tensor_batches": 4.0,
        "max_batch_size": 6.0,
        "battle_windows": 24.0,
    }

    assert _format_simulator_metrics(metrics) == (
        "sim_ticks=64/8 sim_fallbacks=1 sim_shadow=2/9 "
        "sim_batches=4 sim_max_batch=6 sim_windows=24"
    )
    assert _checkpoint_simulator_metrics(metrics) == {
        f"simulator_{key}": value for key, value in metrics.items()
    }
