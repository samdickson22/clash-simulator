#!/usr/bin/env python3
"""Benchmark an exact crowded battle state with scalar and fast engines."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import time

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.pathfinding import _cached_standard_grid_route


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=2301)
    parser.add_argument("--card", default="Knight")
    parser.add_argument("--per-side", type=int, default=12, choices=range(1, 13))
    parser.add_argument("--ticks", type=int, default=8)
    parser.add_argument("--repetitions", type=int, default=4)
    parser.add_argument("--mode", choices=("off", "on", "both"), default="both")
    parser.add_argument("--clear-route-cache-per-mode", action="store_true")
    return parser.parse_args()


def _battle(*, seed: int, card: str, per_side: int, fast_path: bool) -> BattleState:
    battle = BattleState(rng=random.Random(seed), fast_path=fast_path)
    stats = battle.card_loader.get_card(card)
    if stats is None:
        raise ValueError(f"unknown card {card!r}")
    for player_id, row_y in ((0, (10.0, 12.0)), (1, (20.0, 22.0))):
        for index in range(per_side):
            entity_id = battle.next_entity_id
            battle._spawn_troop(
                Position(2.5 + (index % 6) * 2.5, row_y[index // 6]),
                player_id,
                stats,
            )
            entity = battle.entities[entity_id]
            entity.deploy_delay_remaining = 0.0
            entity.placement_pending = False
    if fast_path:
        battle._refresh_fast_path_caches()
    return battle


def _digest(battle: BattleState) -> str:
    hasher = hashlib.sha256()
    for entity in sorted(battle.entities.values(), key=lambda item: item.id):
        hasher.update(
            (
                f"{entity.id}:{entity.position.x}:{entity.position.y}:"
                f"{entity.hitpoints}:{entity.target_id}:{entity.is_alive}"
            ).encode()
        )
    return hasher.hexdigest()


def main() -> None:
    args = _parse_args()
    modes = (False, True) if args.mode == "both" else (args.mode == "on",)
    reports = []
    for fast_path in modes:
        if args.clear_route_cache_per_mode:
            _cached_standard_grid_route.cache_clear()
        rows = []
        hashes = []
        for _ in range(args.repetitions):
            battle = _battle(
                seed=args.seed,
                card=args.card,
                per_side=args.per_side,
                fast_path=fast_path,
            )
            started = time.perf_counter()
            for _ in range(args.ticks):
                battle.step()
            rows.append(time.perf_counter() - started)
            hashes.append(_digest(battle))
        reports.append(
            {
                "engine_fast_path": "on" if fast_path else "off",
                "elapsed_s": rows,
                "median_elapsed_s": statistics.median(rows),
                "ticks_per_s": args.ticks / statistics.median(rows),
                "hashes": sorted(set(hashes)),
                "route_cache": str(_cached_standard_grid_route.cache_info()),
            }
        )
    print(
        json.dumps(
            {
                "seed": args.seed,
                "card": args.card,
                "per_side": args.per_side,
                "ticks": args.ticks,
                "repetitions": args.repetitions,
                "results": reports,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
