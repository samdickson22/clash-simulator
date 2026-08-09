#!/usr/bin/env python3
"""Benchmark exact batching of repeated native logic ticks."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time

from benchmark_crowded_engine import _battle, _digest

from clasher.pathfinding import _cached_standard_grid_route


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=2301)
    parser.add_argument("--card", default="Knight")
    parser.add_argument("--per-side", type=int, default=12)
    parser.add_argument("--windows", type=int, default=8)
    parser.add_argument("--ticks-per-window", type=int, default=8)
    parser.add_argument("--repetitions", type=int, default=11)
    return parser.parse_args()


def _run(args: argparse.Namespace, mode: str) -> dict[str, float | int | str]:
    battle = _battle(
        seed=args.seed,
        card=args.card,
        per_side=args.per_side,
        fast_path=True,
        target_cache_refresh="reuse",
        building_cache_refresh="reuse",
    )
    started = time.perf_counter()
    for _ in range(args.windows):
        if mode == "reference":
            for _ in range(args.ticks_per_window):
                battle.step()
        else:
            advanced = battle.step_logic_ticks(args.ticks_per_window)
            if advanced != args.ticks_per_window:
                raise RuntimeError("battle ended before the fixed benchmark window")
    elapsed = time.perf_counter() - started
    ticks = args.windows * args.ticks_per_window
    return {
        "mode": mode,
        "seconds": elapsed,
        "ticks_per_second": ticks / elapsed,
        "sha256": _digest(battle),
        "route_cache": str(_cached_standard_grid_route.cache_info()),
    }


def main() -> None:
    args = _parse_args()
    _cached_standard_grid_route.cache_clear()
    _run(args, "reference")
    _run(args, "candidate")
    rows = []
    for repetition in range(args.repetitions):
        order = (
            ("reference", "candidate")
            if repetition % 2 == 0
            else ("candidate", "reference")
        )
        for mode in order:
            row = _run(args, mode)
            row["repetition"] = repetition
            rows.append(row)

    summary = {}
    for mode in ("reference", "candidate"):
        selected = [row for row in rows if row["mode"] == mode]
        seconds = [float(row["seconds"]) for row in selected]
        rates = [float(row["ticks_per_second"]) for row in selected]
        summary[mode] = {
            "seconds_median": statistics.median(seconds),
            "seconds_mean": statistics.mean(seconds),
            "seconds_stdev": statistics.stdev(seconds),
            "ticks_per_second_median": statistics.median(rates),
            "hashes": sorted({str(row["sha256"]) for row in selected}),
        }
    paired_gains = []
    for repetition in range(args.repetitions):
        by_mode = {
            str(row["mode"]): float(row["seconds"])
            for row in rows
            if row["repetition"] == repetition
        }
        paired_gains.append(
            100.0 * (by_mode["reference"] / by_mode["candidate"] - 1.0)
        )
    summary["paired_candidate_vs_reference_percent"] = {
        "values": paired_gains,
        "median": statistics.median(paired_gains),
        "mean": statistics.mean(paired_gains),
        "stdev": statistics.stdev(paired_gains),
    }
    reference = float(summary["reference"]["seconds_median"])
    candidate = float(summary["candidate"]["seconds_median"])
    summary["candidate_vs_reference_percent"] = 100.0 * (
        reference / candidate - 1.0
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
