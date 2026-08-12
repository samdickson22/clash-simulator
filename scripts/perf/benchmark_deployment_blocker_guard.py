#!/usr/bin/env python3
"""Benchmark the exact empty deployment-blocker guard in fast action masks."""

from __future__ import annotations

import argparse
import json
import platform
import statistics

from benchmark_action_mask import _prepare_battle, _run_decisions
from clasher.rl import action_space as action_space_module
from clasher.rl.action_space import DiscreteTileActionSpace


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=2301)
    parser.add_argument("--decisions", type=int, default=64)
    parser.add_argument("--repetitions", type=int, default=11)
    parser.add_argument("--warmup-decisions", type=int, default=2)
    parser.add_argument("--building-card", default="Cannon")
    parser.add_argument(
        "--hand-cards",
        default="Knight,Giant,Archers,Musketeer",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    hand_cards = [card.strip() for card in args.hand_cards.split(",") if card.strip()]
    action_space = DiscreteTileActionSpace(canonical_perspective=True)

    def run(mode: str) -> dict[str, float | str]:
        action_space_module._USE_DEPLOYMENT_BLOCKER_GUARD = mode == "guard"
        battle = _prepare_battle(
            seed=args.seed,
            building_card=args.building_card,
            hand_cards=hand_cards,
            fast_path=True,
        )
        if args.warmup_decisions:
            _run_decisions(
                action_space,
                battle,
                fast_path=True,
                decisions=args.warmup_decisions,
            )
        seconds, digest = _run_decisions(
            action_space,
            battle,
            fast_path=True,
            decisions=args.decisions,
        )
        return {
            "mode": mode,
            "seconds": seconds,
            "decisions_per_second": args.decisions / seconds,
            "sha256": digest,
        }

    for mode in ("scan", "guard"):
        run(mode)

    rows = []
    for repetition in range(args.repetitions):
        order = ("scan", "guard") if repetition % 2 == 0 else ("guard", "scan")
        for mode in order:
            row = run(mode)
            row["repetition"] = repetition
            rows.append(row)

    summary = {}
    for mode in ("scan", "guard"):
        selected = [row for row in rows if row["mode"] == mode]
        seconds = [float(row["seconds"]) for row in selected]
        rates = [float(row["decisions_per_second"]) for row in selected]
        summary[mode] = {
            "seconds_median": statistics.median(seconds),
            "decisions_per_second_median": statistics.median(rates),
            "hashes": sorted({str(row["sha256"]) for row in selected}),
        }
    scan = float(summary["scan"]["seconds_median"])
    guard = float(summary["guard"]["seconds_median"])
    summary["guard_vs_scan_percent"] = 100.0 * (scan / guard - 1.0)
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
