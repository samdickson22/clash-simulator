#!/usr/bin/env python3
"""Benchmark scalar/vector crossover for small oracle target sets."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import time

from benchmark_oracle_scalar_leaf import _ScalarLeafOracle, _snapshots

from clasher import entities


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
    parser.add_argument("--candidate-threshold", type=int, default=21)
    parser.add_argument(
        "--engine-fast-path",
        choices=("off", "shadow", "on"),
        default="on",
    )
    return parser.parse_args()


def _run_variant(
    args: argparse.Namespace,
    snapshots,
    variant: str,
) -> dict[str, float | str]:
    entities._FAST_TARGET_VECTOR_MIN_SIZE = (
        0 if variant == "vector" else args.candidate_threshold
    )
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
        "variant": variant,
        "seconds": elapsed,
        "labels_per_second": len(snapshots) / elapsed,
        "sha256": hasher.hexdigest(),
    }


def main() -> None:
    args = _parse_args()
    snapshots = _snapshots(args)
    _run_variant(args, snapshots[:1], "vector")
    _run_variant(args, snapshots[:1], "hybrid")
    rows = []
    for repetition in range(args.repetitions):
        order = (
            ("vector", "hybrid")
            if repetition % 2 == 0
            else ("hybrid", "vector")
        )
        for variant in order:
            row = _run_variant(args, snapshots, variant)
            row["repetition"] = repetition
            rows.append(row)

    summary = {}
    for variant in ("vector", "hybrid"):
        selected = [row for row in rows if row["variant"] == variant]
        seconds = [float(row["seconds"]) for row in selected]
        rates = [float(row["labels_per_second"]) for row in selected]
        summary[variant] = {
            "seconds_median": statistics.median(seconds),
            "seconds_mean": statistics.mean(seconds),
            "seconds_stdev": statistics.stdev(seconds),
            "labels_per_second_median": statistics.median(rates),
            "hashes": sorted({str(row["sha256"]) for row in selected}),
        }
    vector = float(summary["vector"]["seconds_median"])
    hybrid = float(summary["hybrid"]["seconds_median"])
    summary["hybrid_vs_vector_percent"] = 100.0 * (vector / hybrid - 1.0)
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
