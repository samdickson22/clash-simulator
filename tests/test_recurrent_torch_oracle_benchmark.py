from __future__ import annotations

import argparse
from dataclasses import fields

import numpy as np
import pytest

from clasher.rl.train_recurrent import RolloutBatch
from scripts.perf.benchmark_recurrent_torch_oracle import (
    ProcessRecord,
    _find_competing_processes,
    _first_rollout_difference,
    _paired_summary,
    _parse_process_table,
    _rollout_digest,
    _validate_args,
)


def _rollout(**overrides) -> RolloutBatch:
    payload = {}
    for field in fields(RolloutBatch):
        if field.name in {"episodes_finished", "wins", "losses", "draws"}:
            payload[field.name] = 0
        else:
            payload[field.name] = np.asarray([[1, 2]], dtype=np.int64)
    payload.update(overrides)
    return RolloutBatch(**payload)


def test_resource_guard_parses_ps_and_ignores_own_process_tree() -> None:
    records = _parse_process_table(
        """
          10 1 0.0 /Applications/ChatGPT.app/codex
          20 10 0.0 python benchmark_recurrent_torch_oracle.py
          21 20 99.0 python -m clasher.rl.train_recurrent --device mps
          30 1 85.0 python unrelated_cpu_job.py
          40 1 0.0 python -m clasher.rl.train_recurrent --device mps
          41 1 0.0 python evaluate_recurrent_corpus.py --device=mps
        """
    )

    competing = _find_competing_processes(
        records,
        own_pid=20,
        high_cpu_percent=50.0,
    )

    assert [entry["pid"] for entry in competing] == [30, 40, 41]
    assert competing[0]["reasons"] == ["high-cpu-worker"]
    assert "known-training-or-benchmark-workload" in competing[1]["reasons"]
    assert "possible-mps-workload" in competing[1]["reasons"]
    assert "known-training-or-benchmark-workload" in competing[2]["reasons"]
    assert "possible-mps-workload" in competing[2]["reasons"]
    assert "command_sha256" in competing[1]
    assert "command" not in competing[1]


def test_rollout_digest_and_first_difference_are_exact() -> None:
    reference = _rollout()
    identical = _rollout()
    changed = _rollout(actions=np.asarray([[1, 3]], dtype=np.int64))

    assert _rollout_digest(reference) == _rollout_digest(identical)
    assert _first_rollout_difference(reference, identical) is None
    assert _rollout_digest(reference) != _rollout_digest(changed)
    assert _first_rollout_difference(reference, changed) == {
        "field": "actions",
        "index": [0, 1],
        "expected": "2",
        "actual": "3",
    }


def test_paired_summary_uses_matched_wall_times_and_fixed_bootstrap() -> None:
    rows = [
        {"repetition": 0, "backend": "python", "rollout_seconds": 2.0},
        {"repetition": 0, "backend": "pytorch", "rollout_seconds": 1.0},
        {"repetition": 1, "backend": "pytorch", "rollout_seconds": 2.0},
        {"repetition": 1, "backend": "python", "rollout_seconds": 3.0},
    ]

    summary = _paired_summary(rows)

    assert summary["values"] == [100.0, 50.0]
    assert summary["median"] == 75.0
    assert summary["positive_pairs"] == 2
    assert summary["pairs"] == 2
    assert summary["mean_95_percentile_bootstrap_ci"] == [50.0, 100.0]


def test_benchmark_configuration_is_bounded() -> None:
    args = argparse.Namespace(
        num_workers=12,
        num_envs=64,
        rollout_steps=64,
        warmup_steps=8,
        repetitions=7,
        actor_threads=1,
        decision_interval=8,
        max_ticks=2048,
        max_entities=128,
        d_model=128,
        num_heads=4,
        actor_layers=4,
        critic_layers=2,
        memory_size=256,
        oracle_queries=3,
        oracle_depth=6,
        oracle_simulations=32,
        oracle_action_samples=64,
        timeout=600.0,
        high_cpu_percent=50.0,
    )
    _validate_args(args)

    args.num_workers = 65
    with pytest.raises(ValueError, match="between 2 and num_envs"):
        _validate_args(args)
