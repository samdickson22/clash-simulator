#!/usr/bin/env python3
"""Benchmark exact ready-BattleState initialization throughput."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import statistics
import time

import numpy as np

from clasher import battle as battle_module
from clasher.data import CardDataLoader


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--comparison",
        choices=("lazy-cards", "princess-data"),
        default="lazy-cards",
    )
    parser.add_argument("--battles", type=int, default=8)
    parser.add_argument("--repetitions", type=int, default=21)
    parser.add_argument("--seed", type=int, default=2301)
    return parser.parse_args()


def _digest(battles: list[battle_module.BattleState]) -> str:
    hasher = hashlib.sha256()
    for battle in battles:
        hasher.update(
            repr(
                (
                    battle.tick,
                    battle.time,
                    [
                        (
                            entity.id,
                            entity.player_id,
                            entity.hitpoints,
                            entity.position.x,
                            entity.position.y,
                        )
                        for entity in battle.entities.values()
                    ],
                    [
                        (
                            player.left_tower_hp,
                            player.right_tower_hp,
                            player.king_tower_hp,
                        )
                        for player in battle.players
                    ],
                )
            ).encode()
        )
    return hasher.hexdigest()


def _paired_summary(
    rows: list[dict[str, object]],
    reference: str,
    candidate: str,
) -> dict[str, object]:
    gains = []
    for repetition in sorted({int(row["repetition"]) for row in rows}):
        pair = {
            str(row["variant"]): float(row["seconds"])
            for row in rows
            if int(row["repetition"]) == repetition
        }
        gains.append(100.0 * (pair[reference] / pair[candidate] - 1.0))
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
        "positive_pairs": sum(gain > 0.0 for gain in gains),
        "pairs": len(gains),
        "mean_95_percentile_bootstrap_ci": [
            float(np.quantile(means, 0.025)),
            float(np.quantile(means, 0.975)),
        ],
    }


def main() -> None:
    args = _parse_args()
    # Definition parsing is process-global in both variants and not the work
    # under test. Warm it once while retaining per-battle mutable wrappers.
    CardDataLoader().load_card_definitions()
    reference, candidate = (
        ("eager", "lazy")
        if args.comparison == "lazy-cards"
        else ("parsed", "cached")
    )
    rows: list[dict[str, object]] = []
    for repetition in range(args.repetitions):
        order = (
            ((reference, False), (candidate, True))
            if repetition % 2 == 0
            else ((candidate, True), (reference, False))
        )
        for variant, candidate_enabled in order:
            if args.comparison == "lazy-cards":
                battle_module._EAGERLY_MATERIALIZE_BATTLE_CARDS = (
                    not candidate_enabled
                )
                battle_module._USE_CACHED_PRINCESS_TOWER_DATA = True
            else:
                battle_module._EAGERLY_MATERIALIZE_BATTLE_CARDS = False
                battle_module._USE_CACHED_PRINCESS_TOWER_DATA = candidate_enabled
            started = time.perf_counter()
            battles = [
                battle_module.BattleState(
                    fast_path=True,
                    rng=random.Random(args.seed + index),
                )
                for index in range(args.battles)
            ]
            elapsed = time.perf_counter() - started
            rows.append(
                {
                    "repetition": repetition,
                    "variant": variant,
                    "seconds": elapsed,
                    "ready_battles_per_second": args.battles / elapsed,
                    "sha256": _digest(battles),
                }
            )

    summary: dict[str, object] = {}
    for variant in (reference, candidate):
        selected = [row for row in rows if row["variant"] == variant]
        summary[variant] = {
            "seconds_median": statistics.median(
                float(row["seconds"]) for row in selected
            ),
            "ready_battles_per_second_median": statistics.median(
                float(row["ready_battles_per_second"]) for row in selected
            ),
            "hashes": sorted({str(row["sha256"]) for row in selected}),
        }
    summary[f"paired_{candidate}_vs_{reference}_percent"] = _paired_summary(
        rows,
        reference,
        candidate,
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
