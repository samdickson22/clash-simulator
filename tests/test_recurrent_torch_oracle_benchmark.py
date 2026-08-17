from __future__ import annotations

import argparse
from dataclasses import fields

import numpy as np
import pytest

from clasher.rl.train_recurrent import RolloutBatch
from scripts.perf.benchmark_recurrent_torch_oracle import (
    ProcessRecord,
    _audit_paired_rows,
    _candidate_coverage,
    _exact_differential,
    _find_competing_processes,
    _first_rollout_difference,
    _paired_summary,
    _parse_process_table,
    _rollout_digest,
    _validate_args,
    _validation_exit_code,
)


def _rollout(**overrides) -> RolloutBatch:
    payload = {}
    for field in fields(RolloutBatch):
        if field.name in {
            "episodes_finished",
            "wins",
            "losses",
            "draws",
            "simulator_tensor_ticks",
            "simulator_python_ticks",
            "simulator_shadow_checks",
            "simulator_shadow_mismatches",
            "simulator_unsupported_fallbacks",
        }:
            payload[field.name] = 0
        else:
            payload[field.name] = np.asarray([[1, 2]], dtype=np.int64)
    payload.update(overrides)
    return RolloutBatch(**payload)


def _row(
    repetition: int,
    backend: str,
    *,
    rollout_tensor_ticks: int = 0,
    oracle_tensor_ticks: int = 0,
    rollout_python_ticks: int = 0,
    oracle_python_ticks: int = 0,
    rollout_shadow_mismatches: int = 0,
    oracle_shadow_mismatches: int = 0,
    rollout_fallbacks: int = 0,
    oracle_fallbacks: int = 0,
    oracle_sha256: str = "same",
    rollout_seconds: float = 1.0,
) -> dict:
    def metrics(
        tensor_ticks: int,
        python_ticks: int,
        shadow_mismatches: int,
        fallbacks: int,
    ) -> dict:
        total = tensor_ticks + python_ticks
        return {
            "tensor_ticks": tensor_ticks,
            "python_ticks": python_ticks,
            "shadow_checks": 0,
            "shadow_mismatches": shadow_mismatches,
            "unsupported_fallbacks": fallbacks,
            "total_ticks": total,
            "tensor_tick_fraction": tensor_ticks / total if total else 0.0,
        }

    return {
        "repetition": repetition,
        "backend": backend,
        "rollout_seconds": rollout_seconds,
        "rollout_simulator_backend_metrics": metrics(
            rollout_tensor_ticks,
            rollout_python_ticks,
            rollout_shadow_mismatches,
            rollout_fallbacks,
        ),
        "oracle": {
            "sha256": oracle_sha256,
            "simulator_backend_metrics": metrics(
                oracle_tensor_ticks,
                oracle_python_ticks,
                oracle_shadow_mismatches,
                oracle_fallbacks,
            ),
        },
    }


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


def test_rollout_telemetry_is_not_behavioral_payload() -> None:
    reference = _rollout()
    telemetry_changed = _rollout(
        simulator_tensor_ticks=123,
        simulator_python_ticks=456,
        simulator_shadow_checks=7,
        simulator_shadow_mismatches=8,
        simulator_unsupported_fallbacks=9,
    )

    assert _rollout_digest(reference) == _rollout_digest(telemetry_changed)
    assert _first_rollout_difference(reference, telemetry_changed) is None


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


def test_paired_row_audit_rejects_duplicates_missing_rows_and_gaps() -> None:
    complete = [_row(0, "python"), _row(0, "pytorch")]
    assert _audit_paired_rows(complete, expected_repetitions=1) == {
        "expected_rows": 2,
        "actual_rows": 2,
        "paired_repetitions": 1,
    }

    with pytest.raises(ValueError, match="exactly one row per backend"):
        _paired_summary([*complete, _row(0, "pytorch")])
    with pytest.raises(ValueError, match="exactly one row per backend"):
        _paired_summary([_row(0, "python")])
    with pytest.raises(ValueError, match="repetitions must be exactly"):
        _paired_summary(
            [
                _row(0, "python"),
                _row(0, "pytorch"),
                _row(2, "python"),
                _row(2, "pytorch"),
            ],
            expected_repetitions=3,
        )


def test_candidate_coverage_reports_fractions_fallbacks_and_requires_each_row() -> None:
    rows = [
        _row(0, "python", rollout_python_ticks=10, oracle_python_ticks=12),
        _row(
            0,
            "pytorch",
            rollout_tensor_ticks=6,
            rollout_python_ticks=4,
            oracle_tensor_ticks=9,
            oracle_python_ticks=3,
            rollout_fallbacks=2,
            oracle_fallbacks=5,
        ),
        _row(1, "python", rollout_python_ticks=8, oracle_python_ticks=8),
        _row(
            1,
            "pytorch",
            rollout_python_ticks=10,
            oracle_tensor_ticks=2,
            oracle_python_ticks=6,
            rollout_fallbacks=3,
            oracle_fallbacks=7,
        ),
    ]

    coverage = _candidate_coverage(rows)

    assert coverage["candidate_rows"] == 2
    assert coverage["rollout_rows_with_tensor_ticks"] == 1
    assert coverage["oracle_rows_with_tensor_ticks"] == 2
    assert coverage["minimum_required_tensor_tick_fraction"] == 0.5
    assert coverage["rollout_rows_meeting_min_fraction"] == 1
    assert coverage["oracle_rows_meeting_min_fraction"] == 1
    assert coverage["rollout_min_observed_tensor_tick_fraction"] == 0.0
    assert coverage["oracle_min_observed_tensor_tick_fraction"] == pytest.approx(
        0.25
    )
    assert coverage["rollout"]["tensor_tick_fraction"] == pytest.approx(0.3)
    assert coverage["oracle"]["tensor_tick_fraction"] == pytest.approx(11 / 20)
    assert coverage["rollout"]["unsupported_fallbacks"] == 5
    assert coverage["oracle"]["unsupported_fallbacks"] == 12
    assert not coverage["sufficient_for_throughput_interpretation"]

    sufficient = _candidate_coverage(
        [
            _row(0, "python"),
            _row(
                0,
                "pytorch",
                rollout_tensor_ticks=1,
                rollout_python_ticks=1,
                oracle_tensor_ticks=3,
                oracle_python_ticks=2,
            ),
        ],
        min_tensor_tick_fraction=0.5,
    )
    assert sufficient["sufficient_for_throughput_interpretation"]


def test_exact_differential_rejects_rollout_or_oracle_shadow_mismatch() -> None:
    rollouts = {(0, "python"): _rollout(), (0, "pytorch"): _rollout()}
    rows = [
        _row(0, "python"),
        _row(
            0,
            "pytorch",
            rollout_tensor_ticks=1,
            oracle_tensor_ticks=1,
            oracle_shadow_mismatches=1,
        ),
    ]

    differential, exact = _exact_differential(
        rows,
        rollouts,
        expected_repetitions=1,
    )

    assert not exact
    assert not differential[0]["exact"]
    assert differential[0]["first_rollout_difference"] is None
    assert differential[0]["shadow_mismatches"]["pytorch"] == {
        "rollout": 0,
        "oracle": 1,
    }


def test_validation_exit_codes_distinguish_exactness_from_coverage() -> None:
    sufficient = {"sufficient_for_throughput_interpretation": True}
    insufficient = {"sufficient_for_throughput_interpretation": False}

    assert _validation_exit_code(exact=False, candidate_coverage=sufficient) == 2
    assert _validation_exit_code(exact=True, candidate_coverage=insufficient) == 3
    assert _validation_exit_code(exact=True, candidate_coverage=sufficient) == 0


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
        min_tensor_tick_fraction=0.5,
        timeout=600.0,
        high_cpu_percent=50.0,
    )
    _validate_args(args)

    args.num_workers = 65
    with pytest.raises(ValueError, match="between 2 and num_envs"):
        _validate_args(args)

    args.num_workers = 12
    args.min_tensor_tick_fraction = 0.0
    with pytest.raises(ValueError, match=r"must be in \(0, 1\]"):
        _validate_args(args)
