#!/usr/bin/env python3
"""Benchmark exact batched tick windows inside the fixed-depth oracle."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import time

from benchmark_oracle_scalar_leaf import _ScalarLeafOracle, _snapshots

from clasher.battle import BattleState


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


def _reference_step_logic_ticks(battle: BattleState, ticks: int) -> int:
    advanced = 0
    for _ in range(max(0, int(ticks))):
        if battle.game_over:
            break
        battle.step()
        advanced += 1
    return advanced


def _run_variant(
    args: argparse.Namespace,
    snapshots,
    variant: str,
) -> dict[str, float | str]:
    candidate = BattleState.step_logic_ticks
    if variant == "reference":
        BattleState.step_logic_ticks = _reference_step_logic_ticks
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
    try:
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
    finally:
        BattleState.step_logic_ticks = candidate
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
    _run_variant(args, snapshots[:1], "reference")
    _run_variant(args, snapshots[:1], "candidate")
    rows = []
    for repetition in range(args.repetitions):
        order = (
            ("reference", "candidate")
            if repetition % 2 == 0
            else ("candidate", "reference")
        )
        for variant in order:
            row = _run_variant(args, snapshots, variant)
            row["repetition"] = repetition
            rows.append(row)

    summary = {}
    for variant in ("reference", "candidate"):
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
