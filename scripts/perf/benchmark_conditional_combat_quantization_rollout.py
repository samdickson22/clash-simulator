#!/usr/bin/env python3
"""Matched rollout benchmark for conditional combat position quantization."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import platform
import statistics
import sys

import benchmark_stationary_rollout
from benchmark_deployment_blocker_guard_oracle import _paired_gain_summary

from clasher import battle as battle_module
from clasher import entities as entities_module


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--comparison",
        choices=(
            "conditional-combat-quantization",
            "bounded-building-crown-fallback",
        ),
        default="conditional-combat-quantization",
    )
    parser.add_argument("--workload", choices=("random", "strategy"), required=True)
    parser.add_argument("--strategy", default="balanced")
    parser.add_argument("--seed", type=int, default=9079)
    parser.add_argument("--num-envs", type=int, default=4)
    parser.add_argument("--rollout-steps", type=int, default=24)
    parser.add_argument("--warmup-steps", type=int, default=4)
    parser.add_argument("--repetitions", type=int, default=15)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=2048)
    return parser.parse_args()


def _run(args: argparse.Namespace, mode: str) -> dict[str, object]:
    if args.comparison == "conditional-combat-quantization":
        battle_module._USE_CONDITIONAL_COMBAT_POSITION_QUANTIZATION = (
            mode == "conditional"
        )
    else:
        entities_module._USE_RANGE_BOUNDED_BUILDING_CROWN_FALLBACK = (
            mode == "bounded"
        )
    argv = [
        "benchmark_stationary_rollout.py",
        "--workload",
        args.workload,
        "--strategy",
        args.strategy,
        "--seed",
        str(args.seed),
        "--num-envs",
        str(args.num_envs),
        "--rollout-steps",
        str(args.rollout_steps),
        "--warmup-steps",
        str(args.warmup_steps),
        "--repetitions",
        "1",
        "--torch-threads",
        "1",
        "--max-ticks",
        str(args.max_ticks),
        "--reward-profile",
        "defense-v2",
        "--engine-fast-path",
        "on",
    ]
    original_argv = sys.argv
    output = io.StringIO()
    try:
        sys.argv = argv
        with contextlib.redirect_stdout(output):
            benchmark_stationary_rollout.main()
    finally:
        sys.argv = original_argv
    result = json.loads(output.getvalue())
    return {
        "mode": mode,
        "seconds": result["median_elapsed_s"],
        "decisions_per_second": result["median_decisions_per_s"],
        "sha256": result["hashes"][0],
    }


def main() -> None:
    args = _parse_args()
    original_flag = battle_module._USE_CONDITIONAL_COMBAT_POSITION_QUANTIZATION
    original_fallback_flag = (
        entities_module._USE_RANGE_BOUNDED_BUILDING_CROWN_FALLBACK
    )
    reference_mode, candidate_mode = (
        ("per-entity", "conditional")
        if args.comparison == "conditional-combat-quantization"
        else ("unbounded", "bounded")
    )
    rows: list[dict[str, object]] = []
    try:
        for mode in (reference_mode, candidate_mode):
            _run(args, mode)
        for repetition in range(args.repetitions):
            modes = (
                (reference_mode, candidate_mode)
                if repetition % 2 == 0
                else (candidate_mode, reference_mode)
            )
            for mode in modes:
                row = _run(args, mode)
                row["repetition"] = repetition
                rows.append(row)
    finally:
        battle_module._USE_CONDITIONAL_COMBAT_POSITION_QUANTIZATION = original_flag
        entities_module._USE_RANGE_BOUNDED_BUILDING_CROWN_FALLBACK = (
            original_fallback_flag
        )

    summary: dict[str, object] = {}
    for mode in (reference_mode, candidate_mode):
        selected = [row for row in rows if row["mode"] == mode]
        seconds = [float(row["seconds"]) for row in selected]
        rates = [float(row["decisions_per_second"]) for row in selected]
        summary[mode] = {
            "seconds_median": statistics.median(seconds),
            "seconds_mean": statistics.mean(seconds),
            "seconds_stdev": statistics.stdev(seconds),
            "decisions_per_second_median": statistics.median(rates),
            "hashes": sorted({str(row["sha256"]) for row in selected}),
        }
    reference = float(summary[reference_mode]["seconds_median"])  # type: ignore[index]
    candidate = float(summary[candidate_mode]["seconds_median"])  # type: ignore[index]
    summary[f"{candidate_mode}_vs_{reference_mode}_percent"] = 100.0 * (
        reference / candidate - 1.0
    )
    summary[f"paired_{candidate_mode}_vs_{reference_mode}_percent"] = _paired_gain_summary(
        rows,
        reference_mode,
        candidate_mode,
    )
    print(
        json.dumps(
            {
                "machine": {
                    "platform": platform.platform(),
                    "python": platform.python_version(),
                    "processor": platform.processor(),
                },
                "config": vars(args),
                "rows": rows,
                "summary": summary,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
