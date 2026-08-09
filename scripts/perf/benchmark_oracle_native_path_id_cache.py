#!/usr/bin/env python3
"""Matched benchmark for the exact native path-ID cell cache."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import time

from benchmark_oracle_scalar_leaf import _ScalarLeafOracle, _snapshots

from clasher import native_tilemap


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
        "--cache-state",
        choices=("cold", "warm"),
        default="cold",
    )
    parser.add_argument(
        "--engine-fast-path",
        choices=("off", "shadow", "on"),
        default="on",
    )
    return parser.parse_args()


def _run_variant(args, snapshots, variant: str) -> dict[str, float | str]:
    native_tilemap._USE_NATIVE_PATH_ID_CELL_CACHE = variant == "cached"
    if args.cache_state == "cold":
        native_tilemap._nearest_native_path_id_for_cell.cache_clear()
    cache_info_before = native_tilemap._nearest_native_path_id_for_cell.cache_info()
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
    cache_info = native_tilemap._nearest_native_path_id_for_cell.cache_info()
    return {
        "variant": variant,
        "seconds": elapsed,
        "labels_per_second": len(snapshots) / elapsed,
        "cache_hits": cache_info.hits - cache_info_before.hits,
        "cache_misses": cache_info.misses - cache_info_before.misses,
        "sha256": hasher.hexdigest(),
    }


def main() -> None:
    args = _parse_args()
    original_flag = native_tilemap._USE_NATIVE_PATH_ID_CELL_CACHE
    try:
        snapshots = _snapshots(args)
        native_tilemap._nearest_native_path_id_for_cell.cache_clear()
        _run_variant(args, snapshots[:1], "full-scan")
        _run_variant(
            args,
            snapshots if args.cache_state == "warm" else snapshots[:1],
            "cached",
        )
        rows = []
        for repetition in range(args.repetitions):
            order = (
                ("full-scan", "cached")
                if repetition % 2 == 0
                else ("cached", "full-scan")
            )
            for variant in order:
                row = _run_variant(args, snapshots, variant)
                row["repetition"] = repetition
                rows.append(row)
    finally:
        native_tilemap._USE_NATIVE_PATH_ID_CELL_CACHE = original_flag
        native_tilemap._nearest_native_path_id_for_cell.cache_clear()

    summary = {}
    for variant in ("full-scan", "cached"):
        selected = [row for row in rows if row["variant"] == variant]
        seconds = [float(row["seconds"]) for row in selected]
        rates = [float(row["labels_per_second"]) for row in selected]
        summary[variant] = {
            "seconds_median": statistics.median(seconds),
            "seconds_mean": statistics.mean(seconds),
            "seconds_stdev": statistics.stdev(seconds),
            "labels_per_second_median": statistics.median(rates),
            "cache_hits": sorted({int(row["cache_hits"]) for row in selected}),
            "cache_misses": sorted(
                {int(row["cache_misses"]) for row in selected}
            ),
            "hashes": sorted({str(row["sha256"]) for row in selected}),
        }
    full_scan = float(summary["full-scan"]["seconds_median"])
    cached = float(summary["cached"]["seconds_median"])
    summary["cached_vs_full_scan_percent"] = 100.0 * (
        full_scan / cached - 1.0
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
