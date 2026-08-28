from __future__ import annotations

import pytest

from scripts.perf.benchmark_simple_training_collector import Trial, summarize


def _trial(repetition: int, rate: float) -> Trial:
    return Trial(
        repetition=repetition,
        elapsed_seconds=100.0 / rate,
        actor_decisions=100,
        actor_decisions_per_second=rate,
        transition_digest="same",
        execution_mode="cuda-graph",
        max_entities=48,
        max_effects=64,
    )


def test_summary_reports_stable_rate_range() -> None:
    summary = summarize([_trial(0, 100.0), _trial(1, 120.0), _trial(2, 110.0)])
    assert summary["median_actor_decisions_per_second"] == pytest.approx(110.0)
    assert summary["minimum_actor_decisions_per_second"] == pytest.approx(100.0)
    assert summary["maximum_actor_decisions_per_second"] == pytest.approx(120.0)


def test_summary_rejects_empty_trials() -> None:
    with pytest.raises(ValueError, match="at least one"):
        summarize([])
