#!/usr/bin/env python3
"""Benchmark exact scalar and fast action masks with live building occupancy."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import time
from collections import deque

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=2301)
    parser.add_argument("--building-card", default="Cannon")
    parser.add_argument(
        "--hand-cards",
        default="Knight,Giant,Archers,Musketeer",
        help="four comma-separated troop cards",
    )
    parser.add_argument("--decisions", type=int, default=64)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--warmup-decisions", type=int, default=2)
    parser.add_argument("--mode", choices=("off", "on", "both"), default="both")
    parser.add_argument(
        "--building-cache-refresh",
        choices=("rebuild", "reuse"),
        default="reuse",
        help="select full membership rebuild or identity-checked cache reuse",
    )
    return parser.parse_args()


def _prepare_battle(
    *,
    seed: int,
    building_card: str,
    hand_cards: list[str],
    fast_path: bool,
) -> BattleState:
    if len(hand_cards) != 4:
        raise ValueError("--hand-cards must contain exactly four cards")
    battle = BattleState(rng=random.Random(seed), fast_path=fast_path)
    building_stats = battle.card_loader.get_card(building_card)
    if building_stats is None:
        raise ValueError(f"unknown building card {building_card!r}")
    if str(getattr(building_stats, "card_type", "")).lower() != "building":
        raise ValueError(f"{building_card!r} is not a building card")

    for player in battle.players:
        player.elixir = player.max_elixir
        player.hand = hand_cards.copy()
        player.deck = (hand_cards * 2)[:8]
        player.cycle_queue = deque(player.deck[4:])

    building_positions = (
        (0, Position(4.5, 10.5)),
        (0, Position(9.5, 12.5)),
        (0, Position(13.5, 10.5)),
        (1, Position(13.5, 21.5)),
        (1, Position(8.5, 19.5)),
        (1, Position(4.5, 21.5)),
    )
    for player_id, position in building_positions:
        entity_id = battle.next_entity_id
        battle._spawn_troop(position, player_id, building_stats)
        entity = battle.entities[entity_id]
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
    if fast_path:
        battle._refresh_fast_path_caches()
    return battle


def _run_decisions(
    action_space: DiscreteTileActionSpace,
    battle: BattleState,
    *,
    fast_path: bool,
    decisions: int,
) -> tuple[float, str]:
    hasher = hashlib.sha256()
    started = time.perf_counter()
    for _ in range(decisions):
        for player_id in (0, 1):
            mask = action_space.legal_action_mask(
                battle, player_id, fast_path=fast_path
            )
            hasher.update(mask.tobytes())
    return time.perf_counter() - started, hasher.hexdigest()


def main() -> None:
    args = _parse_args()
    if args.building_cache_refresh == "rebuild":
        BattleState._refresh_alive_buildings_cache = (
            BattleState._rebuild_alive_buildings_cache
        )
    hand_cards = [card.strip() for card in args.hand_cards.split(",") if card.strip()]
    modes = (False, True) if args.mode == "both" else (args.mode == "on",)
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    reports = []

    for fast_path in modes:
        elapsed_rows = []
        hashes = []
        for _ in range(args.repetitions):
            battle = _prepare_battle(
                seed=args.seed,
                building_card=args.building_card,
                hand_cards=hand_cards,
                fast_path=fast_path,
            )
            if args.warmup_decisions:
                _run_decisions(
                    action_space,
                    battle,
                    fast_path=fast_path,
                    decisions=args.warmup_decisions,
                )
            elapsed, digest = _run_decisions(
                action_space,
                battle,
                fast_path=fast_path,
                decisions=args.decisions,
            )
            elapsed_rows.append(elapsed)
            hashes.append(digest)

        median_elapsed = statistics.median(elapsed_rows)
        reports.append(
            {
                "engine_fast_path": "on" if fast_path else "off",
                "elapsed_s": elapsed_rows,
                "median_elapsed_s": median_elapsed,
                "decisions_per_s": args.decisions / median_elapsed,
                "hashes": sorted(set(hashes)),
            }
        )

    print(
        json.dumps(
            {
                "seed": args.seed,
                "building_card": args.building_card,
                "hand_cards": hand_cards,
                "decisions": args.decisions,
                "repetitions": args.repetitions,
                "warmup_decisions": args.warmup_decisions,
                "building_cache_refresh": args.building_cache_refresh,
                "results": reports,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
