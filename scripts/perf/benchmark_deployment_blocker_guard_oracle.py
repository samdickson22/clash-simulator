#!/usr/bin/env python3
"""Benchmark the exact empty deployment-blocker guard in oracle labels."""

from __future__ import annotations

import argparse
import json
import platform
import statistics

import numpy as np
from benchmark_oracle_scalar_leaf import _run_variant, _snapshots

from clasher import battle as battle_module
from clasher import entities as entities_module
from clasher import pathfinding as pathfinding_module
from clasher.rl import action_space as action_space_module


def _paired_gain_summary(
    rows: list[dict[str, object]],
    reference_mode: str,
    candidate_mode: str,
) -> dict[str, object]:
    gains = []
    for repetition in sorted({int(row["repetition"]) for row in rows}):
        pair = {
            str(row["mode"]): float(row["seconds"])
            for row in rows
            if int(row["repetition"]) == repetition
        }
        gains.append(100.0 * (pair[reference_mode] / pair[candidate_mode] - 1.0))
    samples = np.asarray(gains, dtype=np.float64)
    rng = np.random.default_rng(0)
    means = np.mean(
        rng.choice(samples, size=(20_000, len(samples)), replace=True),
        axis=1,
    )
    return {
        "values": gains,
        "median": statistics.median(gains),
        "mean": statistics.mean(gains),
        "stdev": statistics.stdev(gains) if len(gains) > 1 else 0.0,
        "positive_pairs": sum(gain > 0.0 for gain in gains),
        "pairs": len(gains),
        "mean_95_percentile_bootstrap_ci": [
            float(np.quantile(means, 0.025)),
            float(np.quantile(means, 0.975)),
        ],
    }


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
    parser.add_argument(
        "--comparison",
        choices=(
            "guard",
            "targetability-requirement",
            "target-entity-kind",
            "crown-fallback",
            "movement-building-refresh",
            "path-hover-trait",
            "dirty-target-cache",
            "prefiltered-action-candidates",
        ),
        default="guard",
    )
    return parser.parse_args()


def _run(args: argparse.Namespace, snapshots, mode: str):
    pathfinding_module._USE_CACHED_GROUND_PATH_HOVER_TRAIT = True
    entities_module._USE_CACHED_PATHFIND_HOVER_TRAIT = True
    battle_module._USE_DIRTY_TARGET_CACHE_REFRESH = True
    action_space_module._USE_PREFILTERED_ACTION_MASK_CANDIDATES = True
    if args.comparison == "guard":
        action_space_module._USE_DEPLOYMENT_BLOCKER_GUARD = mode == "guard"
        battle_module._USE_CACHED_TARGETABILITY_REQUIREMENT = True
        battle_module._USE_DIRECT_TARGET_ENTITY_KIND = True
        entities_module._USE_SINGLE_PASS_CACHED_CROWN_FALLBACK = True
        battle_module._COALESCE_MOVEMENT_BUILDING_CACHE_REFRESH = True
    elif args.comparison == "targetability-requirement":
        action_space_module._USE_DEPLOYMENT_BLOCKER_GUARD = True
        battle_module._USE_CACHED_TARGETABILITY_REQUIREMENT = mode == "cached"
        battle_module._USE_DIRECT_TARGET_ENTITY_KIND = True
        entities_module._USE_SINGLE_PASS_CACHED_CROWN_FALLBACK = True
        battle_module._COALESCE_MOVEMENT_BUILDING_CACHE_REFRESH = True
    elif args.comparison == "target-entity-kind":
        action_space_module._USE_DEPLOYMENT_BLOCKER_GUARD = True
        battle_module._USE_CACHED_TARGETABILITY_REQUIREMENT = True
        battle_module._USE_DIRECT_TARGET_ENTITY_KIND = mode == "direct"
        entities_module._USE_SINGLE_PASS_CACHED_CROWN_FALLBACK = True
        battle_module._COALESCE_MOVEMENT_BUILDING_CACHE_REFRESH = True
    elif args.comparison == "crown-fallback":
        action_space_module._USE_DEPLOYMENT_BLOCKER_GUARD = True
        battle_module._USE_CACHED_TARGETABILITY_REQUIREMENT = True
        battle_module._USE_DIRECT_TARGET_ENTITY_KIND = True
        entities_module._USE_SINGLE_PASS_CACHED_CROWN_FALLBACK = mode == "single-pass"
        battle_module._COALESCE_MOVEMENT_BUILDING_CACHE_REFRESH = True
    elif args.comparison == "movement-building-refresh":
        action_space_module._USE_DEPLOYMENT_BLOCKER_GUARD = True
        battle_module._USE_CACHED_TARGETABILITY_REQUIREMENT = True
        battle_module._USE_DIRECT_TARGET_ENTITY_KIND = True
        entities_module._USE_SINGLE_PASS_CACHED_CROWN_FALLBACK = True
        battle_module._COALESCE_MOVEMENT_BUILDING_CACHE_REFRESH = mode == "coalesced"
    elif args.comparison == "path-hover-trait":
        action_space_module._USE_DEPLOYMENT_BLOCKER_GUARD = True
        battle_module._USE_CACHED_TARGETABILITY_REQUIREMENT = True
        battle_module._USE_DIRECT_TARGET_ENTITY_KIND = True
        entities_module._USE_SINGLE_PASS_CACHED_CROWN_FALLBACK = True
        battle_module._COALESCE_MOVEMENT_BUILDING_CACHE_REFRESH = True
        pathfinding_module._USE_CACHED_GROUND_PATH_HOVER_TRAIT = mode == "cached"
        entities_module._USE_CACHED_PATHFIND_HOVER_TRAIT = mode == "cached"
    elif args.comparison == "dirty-target-cache":
        action_space_module._USE_DEPLOYMENT_BLOCKER_GUARD = True
        battle_module._USE_CACHED_TARGETABILITY_REQUIREMENT = True
        battle_module._USE_DIRECT_TARGET_ENTITY_KIND = True
        entities_module._USE_SINGLE_PASS_CACHED_CROWN_FALLBACK = True
        battle_module._COALESCE_MOVEMENT_BUILDING_CACHE_REFRESH = True
        battle_module._USE_DIRTY_TARGET_CACHE_REFRESH = mode == "dirty"
    else:
        action_space_module._USE_DEPLOYMENT_BLOCKER_GUARD = True
        battle_module._USE_CACHED_TARGETABILITY_REQUIREMENT = True
        battle_module._USE_DIRECT_TARGET_ENTITY_KIND = True
        entities_module._USE_SINGLE_PASS_CACHED_CROWN_FALLBACK = True
        battle_module._COALESCE_MOVEMENT_BUILDING_CACHE_REFRESH = True
        action_space_module._USE_PREFILTERED_ACTION_MASK_CANDIDATES = (
            mode == "prefiltered"
        )
    row = _run_variant(args, snapshots, "scalar")
    row["mode"] = mode
    del row["variant"]
    return row


def main() -> None:
    args = _parse_args()
    snapshots = _snapshots(args)
    if args.comparison == "guard":
        reference_mode, candidate_mode = "scan", "guard"
    elif args.comparison == "targetability-requirement":
        reference_mode, candidate_mode = "recomputed", "cached"
    elif args.comparison == "target-entity-kind":
        reference_mode, candidate_mode = "getattr", "direct"
    elif args.comparison == "crown-fallback":
        reference_mode, candidate_mode = "partitioned", "single-pass"
    elif args.comparison == "movement-building-refresh":
        reference_mode, candidate_mode = "repeated", "coalesced"
    elif args.comparison == "path-hover-trait":
        reference_mode, candidate_mode = "runtime", "cached"
    elif args.comparison == "dirty-target-cache":
        reference_mode, candidate_mode = "full", "dirty"
    else:
        reference_mode, candidate_mode = "rechecked", "prefiltered"
    for mode in (reference_mode, candidate_mode):
        _run(args, snapshots[:1], mode)

    rows = []
    for repetition in range(args.repetitions):
        order = (
            (reference_mode, candidate_mode)
            if repetition % 2 == 0
            else (candidate_mode, reference_mode)
        )
        for mode in order:
            row = _run(args, snapshots, mode)
            row["repetition"] = repetition
            rows.append(row)

    summary = {}
    for mode in (reference_mode, candidate_mode):
        selected = [row for row in rows if row["mode"] == mode]
        seconds = [float(row["seconds"]) for row in selected]
        rates = [float(row["decisions_per_second"]) for row in selected]
        summary[mode] = {
            "seconds_median": statistics.median(seconds),
            "seconds_mean": statistics.mean(seconds),
            "seconds_stdev": statistics.stdev(seconds) if len(seconds) > 1 else 0.0,
            "decisions_per_second_median": statistics.median(rates),
            "hashes": sorted({str(row["sha256"]) for row in selected}),
        }
    reference = float(summary[reference_mode]["seconds_median"])
    candidate = float(summary[candidate_mode]["seconds_median"])
    summary[f"{candidate_mode}_vs_{reference_mode}_percent"] = 100.0 * (
        reference / candidate - 1.0
    )
    summary[f"paired_{candidate_mode}_vs_{reference_mode}_percent"] = (
        _paired_gain_summary(rows, reference_mode, candidate_mode)
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
