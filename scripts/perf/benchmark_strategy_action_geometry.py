#!/usr/bin/env python3
"""Benchmark exact strategy scoring from canonical action IDs."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import time

from clasher.rl import strategy_bots as strategy_bots_module
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import STRATEGY_NAMES, StrategyBot


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", choices=STRATEGY_NAMES, default="balanced")
    parser.add_argument(
        "--comparison",
        choices=("geometry", "tile-fit-cache"),
        default="geometry",
    )
    parser.add_argument("--seed", type=int, default=2301)
    parser.add_argument("--selections", type=int, default=64)
    parser.add_argument("--repetitions", type=int, default=11)
    parser.add_argument("--warmup-selections", type=int, default=4)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    env = SelfPlayBattleEnv(seed=args.seed, max_ticks=4096, engine_fast_path="on")
    env.reset()
    bot = StrategyBot(args.strategy)
    masks = {player_id: env.get_action_mask(player_id) for player_id in (0, 1)}
    variants = (
        ("decoded", "direct")
        if args.comparison == "geometry"
        else ("uncached", "cached")
    )

    def run_once(variant: str, selections: int) -> dict[str, float | str]:
        strategy_bots_module._USE_DIRECT_CANONICAL_ACTION_GEOMETRY = (
            variant == "direct" if args.comparison == "geometry" else True
        )
        strategy_bots_module._USE_CACHED_STRATEGY_TILE_FITS = (
            variant == "cached" if args.comparison == "tile-fit-cache" else True
        )
        hasher = hashlib.sha256()
        started = time.perf_counter()
        for selection in range(selections):
            player_id = selection % 2
            action = bot.select_action(
                env,
                player_id,
                action_mask=masks[player_id],
            )
            hasher.update(int(action).to_bytes(8, "little", signed=True))
        elapsed = time.perf_counter() - started
        return {
            "variant": variant,
            "seconds": elapsed,
            "selections_per_second": selections / elapsed,
            "sha256": hasher.hexdigest(),
        }

    for variant in variants:
        run_once(variant, args.warmup_selections)
    rows = []
    for repetition in range(args.repetitions):
        order = (
            variants
            if repetition % 2 == 0
            else tuple(reversed(variants))
        )
        for variant in order:
            row = run_once(variant, args.selections)
            row["repetition"] = repetition
            rows.append(row)

    summary = {}
    for variant in variants:
        selected = [row for row in rows if row["variant"] == variant]
        seconds = [float(row["seconds"]) for row in selected]
        rates = [float(row["selections_per_second"]) for row in selected]
        summary[variant] = {
            "seconds_median": statistics.median(seconds),
            "seconds_mean": statistics.mean(seconds),
            "seconds_stdev": statistics.stdev(seconds) if len(seconds) > 1 else 0.0,
            "selections_per_second_median": statistics.median(rates),
            "hashes": sorted({str(row["sha256"]) for row in selected}),
        }
    reference = float(summary[variants[0]]["seconds_median"])
    candidate = float(summary[variants[1]]["seconds_median"])
    summary[f"{variants[1]}_vs_{variants[0]}_percent"] = 100.0 * (
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
