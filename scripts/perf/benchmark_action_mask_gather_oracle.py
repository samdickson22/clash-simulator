#!/usr/bin/env python3
"""Benchmark canonical occupancy gathering in exact oracle labels."""

from __future__ import annotations

import argparse
import json
import platform
import statistics

from benchmark_action_mask_gather import _install_mode
from benchmark_oracle_scalar_leaf import _run_variant, _snapshots


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=2301)
    parser.add_argument("--planner-seed", type=int, default=901)
    parser.add_argument("--states", type=int, default=3)
    parser.add_argument("--state-stride", type=int, default=4)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--planner-depth", type=int, default=6)
    parser.add_argument("--planner-simulations", type=int, default=32)
    parser.add_argument("--planner-action-samples", type=int, default=64)
    parser.add_argument(
        "--engine-fast-path",
        choices=("off", "shadow", "on"),
        default="on",
    )
    return parser.parse_args()


def _run(args: argparse.Namespace, snapshots, mode: str):
    _install_mode(mode)
    row = _run_variant(args, snapshots, "scalar")
    row["mode"] = mode
    del row["variant"]
    return row


def main() -> None:
    args = _parse_args()
    snapshots = _snapshots(args)
    _run(args, snapshots[:1], "loop")
    _run(args, snapshots[:1], "gather")
    rows = []
    for repetition in range(args.repetitions):
        order = ("loop", "gather") if repetition % 2 == 0 else ("gather", "loop")
        for mode in order:
            row = _run(args, snapshots, mode)
            row["repetition"] = repetition
            rows.append(row)

    summary = {}
    for mode in ("loop", "gather"):
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
    loop = float(summary["loop"]["seconds_median"])
    gather = float(summary["gather"]["seconds_median"])
    summary["gather_vs_loop_percent"] = 100.0 * (loop / gather - 1.0)
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
