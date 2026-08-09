#!/usr/bin/env python3
"""Bounded matched benchmark for immutable standard-arena path costs."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
from functools import lru_cache

from benchmark_crowded_engine import _battle, _digest

from clasher import pathfinding


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=2301)
    parser.add_argument("--card", default="Knight")
    parser.add_argument("--per-side", type=int, default=12)
    parser.add_argument("--ticks", type=int, default=64)
    parser.add_argument("--repetitions", type=int, default=7)
    return parser.parse_args()


def _router(mode: str):
    @lru_cache(maxsize=2048)
    def route(start, goal, lane_id, jump_height):
        if mode == "baseline":
            tile_cost = lambda cell: pathfinding._standard_pathfinder_tile_cost(
                cell,
                lane_id=lane_id,
                jump_height=jump_height,
            )
        else:
            tile_cost = pathfinding._standard_path_cost_map(
                lane_id,
                jump_height,
            ).get
        value = pathfinding._native_grid_route(start, goal, tile_cost)
        return None if value is None else tuple(value)

    return route


def _run(args: argparse.Namespace, mode: str) -> dict[str, float | str]:
    pathfinding._standard_path_cost_map.cache_clear()
    pathfinding._cached_standard_grid_route = _router(mode)
    battle = _battle(
        seed=args.seed,
        card=args.card,
        per_side=args.per_side,
        fast_path=True,
        target_cache_refresh="reuse",
        building_cache_refresh="reuse",
    )
    started = time.perf_counter()
    for _ in range(args.ticks):
        battle.step()
    elapsed = time.perf_counter() - started
    return {
        "mode": mode,
        "seconds": elapsed,
        "ticks_per_second": args.ticks / elapsed,
        "sha256": _digest(battle),
        "route_cache": str(pathfinding._cached_standard_grid_route.cache_info()),
    }


def main() -> None:
    args = _parse_args()
    _run(args, "baseline")
    _run(args, "candidate")
    rows = []
    for repetition in range(args.repetitions):
        order = (
            ("baseline", "candidate")
            if repetition % 2 == 0
            else ("candidate", "baseline")
        )
        for mode in order:
            row = _run(args, mode)
            row["repetition"] = repetition
            rows.append(row)

    summary = {}
    for mode in ("baseline", "candidate"):
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
    baseline = float(summary["baseline"]["seconds_median"])
    candidate = float(summary["candidate"]["seconds_median"])
    summary["candidate_vs_baseline_percent"] = 100.0 * (baseline / candidate - 1.0)
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
