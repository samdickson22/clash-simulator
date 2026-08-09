#!/usr/bin/env python3
"""Measure scalar/vector target selection crossover by target count."""

from __future__ import annotations

import argparse
import json
import statistics
import time

from benchmark_crowded_engine import _battle, _digest

from clasher import entities
from clasher.pathfinding import _cached_standard_grid_route


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=2301)
    parser.add_argument("--card", default="Knight")
    parser.add_argument("--per-side", default="1,2,4,6,7,8,10,12")
    parser.add_argument("--ticks", type=int, default=32)
    parser.add_argument("--repetitions", type=int, default=5)
    return parser.parse_args()


def _run(
    args: argparse.Namespace,
    *,
    per_side: int,
    threshold: int,
) -> dict[str, float | str]:
    entities._FAST_TARGET_VECTOR_MIN_SIZE = threshold
    battle = _battle(
        seed=args.seed,
        card=args.card,
        per_side=per_side,
        fast_path=True,
        target_cache_refresh="reuse",
        building_cache_refresh="reuse",
    )
    started = time.perf_counter()
    for _ in range(args.ticks):
        battle.step()
    elapsed = time.perf_counter() - started
    return {
        "seconds": elapsed,
        "ticks_per_second": args.ticks / elapsed,
        "sha256": _digest(battle),
    }


def main() -> None:
    args = _parse_args()
    per_side_values = [int(value) for value in args.per_side.split(",")]
    results = []
    for per_side in per_side_values:
        _cached_standard_grid_route.cache_clear()
        _run(args, per_side=per_side, threshold=0)
        _run(args, per_side=per_side, threshold=100)
        rows = {"vector": [], "scalar": []}
        hashes = {"vector": set(), "scalar": set()}
        for repetition in range(args.repetitions):
            order = (
                (("vector", 0), ("scalar", 100))
                if repetition % 2 == 0
                else (("scalar", 100), ("vector", 0))
            )
            for mode, threshold in order:
                row = _run(args, per_side=per_side, threshold=threshold)
                rows[mode].append(float(row["seconds"]))
                hashes[mode].add(str(row["sha256"]))
        vector = statistics.median(rows["vector"])
        scalar = statistics.median(rows["scalar"])
        results.append(
            {
                "target_count": 6 + 2 * per_side,
                "per_side": per_side,
                "vector_seconds_median": vector,
                "scalar_seconds_median": scalar,
                "scalar_vs_vector_percent": 100.0 * (vector / scalar - 1.0),
                "hashes_match": hashes["vector"] == hashes["scalar"],
                "hashes": sorted(hashes["vector"] | hashes["scalar"]),
            }
        )
    print(
        json.dumps(
            {
                "config": vars(args),
                "results": results,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
