from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from scripts.perf.benchmark_simple_gym import _resolve_preset, benchmark


def _args(tmp_path: Path, **overrides: object) -> argparse.Namespace:
    path = tmp_path / "decks.json"
    path.write_text(
        json.dumps(
            {"decks": [{"name": "fixture", "cards": ["Knight"] * 8}]}
        )
    )
    values: dict[str, object] = {
        "preset": "smoke",
        "decks_path": path,
        "device": "cpu",
        "seed": 202_608_264,
        "policy": "noop",
        "batch_size": None,
        "warmup_ticks": None,
        "measured_ticks": None,
        "repetitions": None,
        "max_entities": 16,
        "max_effects": 16,
        "min_row_ticks_per_second": 1.0,
        "profile_cuda": False,
        "out": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_simple_smoke_preset_is_bounded_and_replayed(tmp_path: Path) -> None:
    args = _resolve_preset(_args(tmp_path))

    assert args.batch_size == 2
    assert args.warmup_ticks == 1
    assert args.measured_ticks == 4
    assert args.repetitions == 2


def test_simple_benchmark_reports_absolute_native_row_throughput(
    tmp_path: Path,
) -> None:
    result = benchmark(_args(tmp_path))

    assert result["acceptance"] == {
        "deterministic_replay": True,
        "all_rows_committed": True,
        "all_row_ticks_native": True,
        "zero_fallback": True,
        "no_terminal_rows_in_window": True,
        "absolute_throughput_gate": True,
        "cuda_launches_lt_1000": None,
        "cuda_zero_explicit_host_sync": None,
        "python_parity_evaluated": False,
        "speedup_evaluated": False,
    }
    trials = result["trials"]
    assert isinstance(trials, list) and len(trials) == 2
    assert len({trial["digest"] for trial in trials}) == 1
    assert all(trial["row_ticks"] == 8 for trial in trials)
    assert all(trial["committed_rows"] == 8 for trial in trials)
    assert all(trial["native_ticks"] == 8 for trial in trials)
    assert result["median"]["row_ticks_per_second"] > 0.0


def test_simple_benchmark_enforces_absolute_throughput_gate(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="below gate"):
        benchmark(_args(tmp_path, min_row_ticks_per_second=1e30))

