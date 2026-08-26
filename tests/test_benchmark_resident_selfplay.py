from __future__ import annotations

import argparse

import pytest

from scripts.perf.benchmark_resident_selfplay import _resolve_preset, benchmark


def _args(**overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "preset": "smoke",
        "decks_path": "decks.json",
        "device": "cpu",
        "seed": 202_608_262,
        "policy": "noop",
        "batch_size": None,
        "warmup_decisions": None,
        "measured_decisions": None,
        "repetitions": None,
        "decision_interval": 1,
        "max_ticks": None,
        "max_entities": 16,
        "max_objects": 16,
        "out": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_smoke_preset_is_bounded_and_replayed() -> None:
    args = _resolve_preset(_args())

    assert args.batch_size == 1
    assert args.warmup_decisions == 0
    assert args.measured_decisions == 1
    assert args.repetitions == 2
    assert args.max_ticks == 2


def test_benchmark_rejects_window_that_reaches_tick_limit() -> None:
    with pytest.raises(ValueError, match="max_ticks must exceed"):
        benchmark(_args(max_ticks=1))


def test_resident_smoke_reports_only_absolute_native_throughput() -> None:
    result = benchmark(_args())

    assert result["acceptance"] == {
        "deterministic_replay": True,
        "all_requested_ticks_native": True,
        "zero_fallback": True,
        "no_terminal_rows_in_window": True,
        "python_parity_evaluated": False,
        "speedup_evaluated": False,
    }
    trials = result["trials"]
    assert isinstance(trials, list) and len(trials) == 2
    assert {trial["digest"] for trial in trials}.__len__() == 1
    assert all(trial["native_ticks"] == 1 for trial in trials)
    assert result["median"]["native_ticks_per_second"] > 0.0
