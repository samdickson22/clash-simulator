#!/usr/bin/env python3
"""Matched exact-oracle benchmark for row-interval route-goal selection."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import time

from benchmark_inline_position_quantization_rollout import _paired_gain_summary
from benchmark_oracle_scalar_leaf import _ScalarLeafOracle, _snapshots

from clasher import pathfinding


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=2301)
    parser.add_argument("--planner-seed", type=int, default=901)
    parser.add_argument("--states", type=int, default=3)
    parser.add_argument("--state-stride", type=int, default=4)
    parser.add_argument("--repetitions", type=int, default=11)
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


def _run_variant(args, snapshots, mode: str) -> dict[str, float | str]:
    pathfinding._USE_ROW_INTERVAL_NATIVE_ROUTE_GOAL = mode == "row-interval"
    pathfinding._cached_native_route_goal_cell_units.cache_clear()
    pathfinding._cached_native_route_goal_cell_units_full_scan.cache_clear()
    planner = _ScalarLeafOracle(
        decision_interval_ticks=args.decision_interval,
        plan_depth=args.planner_depth,
        num_simulations=args.planner_simulations,
        rollout_action_samples=args.planner_action_samples,
        seed=args.planner_seed,
        reward_profile="defense-v2",
        stable_root_candidates=True,
    )
    hasher = hashlib.sha256()
    started = time.perf_counter()
    for battle in snapshots:
        before = planner._state_key(battle)
        battle_rng_before = battle.rng.getstate()
        actions = planner.select_actions(battle)
        after = planner._state_key(battle)
        battle_rng_after = battle.rng.getstate()
        hasher.update(
            repr(
                (
                    before,
                    actions,
                    after,
                    battle_rng_before,
                    battle_rng_after,
                )
            ).encode()
        )
    elapsed = time.perf_counter() - started
    hasher.update(repr(planner.rng.bit_generator.state).encode())
    return {
        "mode": mode,
        "seconds": elapsed,
        "labels_per_second": len(snapshots) / elapsed,
        "sha256": hasher.hexdigest(),
    }


def main() -> None:
    args = _parse_args()
    original = pathfinding._USE_ROW_INTERVAL_NATIVE_ROUTE_GOAL
    snapshots = _snapshots(args)
    try:
        _run_variant(args, snapshots[:1], "full-scan")
        _run_variant(args, snapshots[:1], "row-interval")
        rows = []
        for repetition in range(args.repetitions):
            order = (
                ("full-scan", "row-interval")
                if repetition % 2 == 0
                else ("row-interval", "full-scan")
            )
            for mode in order:
                row = _run_variant(args, snapshots, mode)
                row["repetition"] = repetition
                rows.append(row)
    finally:
        pathfinding._USE_ROW_INTERVAL_NATIVE_ROUTE_GOAL = original
        pathfinding._cached_native_route_goal_cell_units.cache_clear()
        pathfinding._cached_native_route_goal_cell_units_full_scan.cache_clear()

    summary: dict[str, object] = {}
    for mode in ("full-scan", "row-interval"):
        selected = [row for row in rows if row["mode"] == mode]
        summary[mode] = {
            "seconds_median": statistics.median(
                float(row["seconds"]) for row in selected
            ),
            "labels_per_second_median": statistics.median(
                float(row["labels_per_second"]) for row in selected
            ),
            "hashes": sorted({str(row["sha256"]) for row in selected}),
        }
    reference = float(summary["full-scan"]["seconds_median"])  # type: ignore[index]
    candidate = float(summary["row-interval"]["seconds_median"])  # type: ignore[index]
    summary["row_interval_vs_full_scan_percent"] = 100.0 * (
        reference / candidate - 1.0
    )
    summary["paired_row_interval_vs_full_scan_percent"] = (
        _paired_gain_summary(rows, "full-scan", "row-interval")
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
