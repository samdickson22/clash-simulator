from __future__ import annotations

import pytest

from scripts.perf.benchmark_python_vs_simple_gym import (
    BACKENDS,
    Trial,
    paired_order,
    summarize,
)


def _trial(backend: str, repetition: int, rate: float) -> Trial:
    return Trial(
        backend=backend,
        repetition=repetition,
        elapsed_seconds=10.0 / rate,
        row_ticks=10,
        row_ticks_per_second=rate,
        actor_transitions_per_second=2.0 * rate,
        digest=f"{backend}-stable",
    )


def test_paired_order_alternates_three_backend_order() -> None:
    assert paired_order(0) == BACKENDS
    assert paired_order(1) == tuple(reversed(BACKENDS))
    with pytest.raises(ValueError, match="non-negative"):
        paired_order(-1)


def test_summary_reports_simple_ratios_against_both_python_contracts() -> None:
    trials = [
        _trial("python-exact-mask", repetition, 100.0)
        for repetition in range(3)
    ]
    trials += [
        _trial("python-public-v2", repetition, 80.0)
        for repetition in range(3)
    ]
    trials += [
        _trial("simple-pytorch", repetition, 200.0)
        for repetition in range(3)
    ]
    summary = summarize(trials)
    assert summary["simple_speed_ratio_vs_python_exact"] == pytest.approx(2.0)
    assert summary["simple_speed_ratio_vs_python_public_v2"] == pytest.approx(2.5)


def test_summary_rejects_incomplete_repetitions() -> None:
    trials = [_trial(backend, 0, 100.0) for backend in BACKENDS]
    trials.pop()
    with pytest.raises(ValueError, match="every repetition"):
        summarize(trials)
