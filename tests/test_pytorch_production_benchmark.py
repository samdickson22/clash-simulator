from __future__ import annotations

import pytest

from clasher.rl.production_benchmark import (
    CANDIDATE_BACKEND,
    REFERENCE_BACKEND,
    BenchmarkLease,
    BenchmarkLeaseError,
    aggregate_backend_metrics,
    canonical_digest,
    competing_benchmark_processes,
    oracle_backend_capability,
    paired_bootstrap_summary,
    paired_order,
    semantic_rollout_digest,
    validate_paired_rows,
)


def _row(backend: str, repetition: int, seconds: float, digest: str = "same"):
    metrics = {
        "tensor_ticks": 64 if backend == CANDIDATE_BACKEND else 0,
        "python_ticks": 0 if backend == CANDIDATE_BACKEND else 64,
        "shadow_checks": 0,
        "shadow_mismatches": 0,
        "unsupported_fallbacks": 0,
    }
    return {
        "backend": backend,
        "repetition": repetition,
        "seconds": seconds,
        "sha256": digest,
        "backend_metrics": metrics,
    }


def test_paired_order_alternates_reference_and_candidate() -> None:
    assert paired_order(0) == (REFERENCE_BACKEND, CANDIDATE_BACKEND)
    assert paired_order(1) == (CANDIDATE_BACKEND, REFERENCE_BACKEND)


def test_exact_digest_preserves_numpy_dtype_and_shape() -> None:
    import numpy as np

    left = canonical_digest((("value", np.asarray([1], dtype=np.int32)),))
    different_dtype = canonical_digest((("value", np.asarray([1], dtype=np.int64)),))
    different_shape = canonical_digest((("value", np.asarray([[1]], dtype=np.int32)),))
    assert len(left) == 64
    assert left != different_dtype
    assert left != different_shape


def test_semantic_rollout_digest_excludes_simulator_metrics() -> None:
    import numpy as np

    fields = {
        "actions": np.asarray([[1, 2]], dtype=np.int64),
        "simulator_metrics": {"python_ticks": 16, "tensor_ticks": 0},
    }
    reference = semantic_rollout_digest(fields, ({"tick": 16},))
    fields["simulator_metrics"] = {"python_ticks": 0, "tensor_ticks": 16}
    candidate = semantic_rollout_digest(fields, ({"tick": 16},))
    assert reference == candidate


def test_backend_metric_aggregation_requires_all_counters() -> None:
    summed = aggregate_backend_metrics(
        (
            _row(CANDIDATE_BACKEND, 0, 1.0)["backend_metrics"],
            _row(CANDIDATE_BACKEND, 0, 1.0)["backend_metrics"],
        )
    )
    assert summed["tensor_ticks"] == 128
    assert summed["unsupported_fallbacks"] == 0


def test_validation_rejects_fallback_only_digest_match() -> None:
    reference = _row(REFERENCE_BACKEND, 0, 2.0)
    candidate = _row(CANDIDATE_BACKEND, 0, 1.0)
    candidate["backend_metrics"]["python_ticks"] = 64
    candidate["backend_metrics"]["unsupported_fallbacks"] = 1
    failures = validate_paired_rows(reference, candidate)
    assert "candidate executed Python ticks" in failures
    assert "candidate used unsupported Python fallback" in failures


def test_validation_rejects_partial_candidate_tick_evidence() -> None:
    reference = _row(REFERENCE_BACKEND, 0, 2.0)
    candidate = _row(CANDIDATE_BACKEND, 0, 1.0)
    candidate["backend_metrics"]["tensor_ticks"] = 32
    assert validate_paired_rows(reference, candidate) == (
        "candidate tensor ticks do not match reference Python ticks",
    )


def test_paired_bootstrap_requires_lower_bound_for_two_x_claim() -> None:
    rows = []
    for repetition in range(5):
        rows.extend(
            (
                _row(REFERENCE_BACKEND, repetition, 2.1),
                _row(CANDIDATE_BACKEND, repetition, 1.0),
            )
        )
    summary = paired_bootstrap_summary(rows, bootstrap_samples=1_000)
    assert summary["valid_for_speed_claim"] is True
    assert summary["meets_2x_with_95_percent_confidence"] is True
    assert summary["mean_speedup_95_percentile_bootstrap_ci"] == pytest.approx(
        [110.0, 110.0]
    )


def test_paired_bootstrap_never_claims_speed_on_digest_mismatch() -> None:
    rows = [
        _row(REFERENCE_BACKEND, 0, 3.0, digest="reference"),
        _row(CANDIDATE_BACKEND, 0, 1.0, digest="candidate"),
    ]
    summary = paired_bootstrap_summary(rows, bootstrap_samples=100)
    assert summary["valid_for_speed_claim"] is False
    assert summary["meets_2x_with_95_percent_confidence"] is False
    assert summary["validation_failures"] == [
        "repetition 0: exact evidence digests differ"
    ]


def test_paired_bootstrap_rejects_duplicate_backend_rows() -> None:
    rows = [
        _row(REFERENCE_BACKEND, 0, 3.0),
        _row(CANDIDATE_BACKEND, 0, 1.0),
        _row(CANDIDATE_BACKEND, 0, 1.1),
    ]
    with pytest.raises(ValueError, match="exactly two rows"):
        paired_bootstrap_summary(rows, bootstrap_samples=100)


def test_current_oracle_without_backend_ingress_fails_closed() -> None:
    class PlannerWithoutBackend:
        def __init__(self, *, seed: int):
            del seed

    capability = oracle_backend_capability(PlannerWithoutBackend)
    assert capability.available is False
    assert "Python-vs-Python" in str(capability.reason)


def test_oracle_backend_ingress_without_metrics_fails_closed() -> None:
    class PlannerWithoutMetrics:
        def __init__(self, *, simulation_backend: str):
            del simulation_backend

    capability = oracle_backend_capability(PlannerWithoutMetrics)
    assert capability.available is False
    assert "simulator_backend_metrics" in str(capability.reason)


def test_competing_process_detection_ignores_owned_family_and_sanitizes_scope() -> None:
    rows = (
        (10, 1, "/bin/zsh parent"),
        (20, 10, "/usr/bin/python3 scripts/perf/benchmark_pytorch_production.py"),
        (21, 20, "/usr/bin/python3 -c child"),
        (22, 10, "/other/clasher/.venv/bin/pytest -q sibling_test.py"),
        (
            30,
            1,
            (
                "/work/clasher/.venv/bin/python3 -m "
                "clasher.rl.train_recurrent --device mps"
            ),
        ),
        (40, 1, "/usr/bin/cargo bench --manifest-path /work/clasher/Cargo.toml"),
        (41, 1, "/work/rust-clasher/target/release/rust-clasher benchmark"),
        (42, 1, "/other/clasher/.venv/bin/pytest -q tests/test_engine.py"),
        (43, 1, "/other/clasher/.venv/bin/mypy src/clasher"),
        (44, 1, "/other/clasher/.venv/bin/python run_clasher.py benchmark"),
        (
            45,
            1,
            "/other/clasher/.venv/bin/python -m clasher.rl.benchmark async-queue",
        ),
        (50, 1, "/usr/bin/python3 harmless.py"),
    )
    blockers = competing_benchmark_processes(rows, current_pid=20)
    assert [(blocker.pid, blocker.category) for blocker in blockers] == [
        (22, "clasher-validation"),
        (30, "clasher-compute"),
        (40, "clasher-rust"),
        (41, "clasher-rust"),
        (42, "clasher-validation"),
        (43, "clasher-validation"),
        (44, "clasher-compute"),
        (45, "clasher-compute"),
    ]


def test_generic_rust_compiler_fails_closed_without_cwd_visibility() -> None:
    blockers = competing_benchmark_processes(
        ((60, 1, "/usr/bin/rustc --crate-name unrelated source.rs"),),
        current_pid=99,
    )
    assert [(blocker.pid, blocker.category) for blocker in blockers] == [
        (60, "clasher-rust")
    ]


def test_benchmark_lease_is_nonblocking_and_recoverable(tmp_path) -> None:
    path = tmp_path / "benchmark.lock"
    first = BenchmarkLease(path)
    second = BenchmarkLease(path)
    first.acquire()
    try:
        with pytest.raises(BenchmarkLeaseError, match="lease is unavailable"):
            second.acquire()
    finally:
        first.release()
    second.acquire()
    second.release()
