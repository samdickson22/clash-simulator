#!/usr/bin/env python3
"""Benchmark an exact crowded battle state with scalar and fast engines."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import time

from clasher import battle as battle_module
from clasher import entities as entities_module
from clasher import unit_traits
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
    parser.add_argument(
        "--target-cache-refresh",
        choices=("rebuild", "reuse"),
        default="reuse",
        help="select the pre-optimization full rebuild or candidate in-place refresh",
    )
    parser.add_argument(
        "--building-cache-refresh",
        choices=("rebuild", "reuse"),
        default="reuse",
        help="select full membership rebuild or identity-checked cache reuse",
    )
    parser.add_argument(
        "--targetability-refresh",
        choices=("full", "classified"),
        default="classified",
        help="select full dynamic targetability checks or exact static classification",
    )
    parser.add_argument(
        "--crown-fallback-membership",
        choices=("scan", "cached"),
        default="cached",
        help="select full building scan or exact cached Crown membership",
    )
    parser.add_argument(
        "--crown-distance-order",
        choices=("eager", "preferred-first"),
        default="preferred-first",
        help="select eager or preferred-only Crown distance evaluation",
    )
    parser.add_argument(
        "--inactive-stealth-time",
        choices=("eager", "deferred"),
        default="deferred",
        help="select eager or inactive-stealth-deferred battle-time lookup",
    )
    parser.add_argument(
        "--bucket-id-sort",
        choices=("allocated", "inplace"),
        default="inplace",
        help="select allocated or in-place exact bucket candidate ordering",
    )
    parser.add_argument(
        "--targetability-fields",
        choices=("defensive", "direct"),
        default="direct",
        help="select defensive helpers or exact direct Entity field reads",
    )
    parser.add_argument(
        "--bucket-scan-order",
        choices=("column-major", "row-major"),
        default="row-major",
        help="select exact dense bucket traversal before final ID ordering",
    )
    parser.add_argument(
        "--bucket-geometry",
        choices=("recomputed", "cached"),
        default="cached",
        help="select recomputed or rebuild-published exact bucket geometry",
    )
    parser.add_argument(
        "--building-membership",
        choices=("defensive", "trusted"),
        default="trusted",
        help="select defensive checks or exact live-building cache membership",
    )
    parser.add_argument(
        "--mover-hover-trait",
        choices=("runtime", "cached"),
        default="cached",
        help="select runtime or entity-cached data-driven hover classification",
    )
    parser.add_argument(
        "--avoidance-candidates",
        choices=("full-scan", "bucketed"),
        default="bucketed",
        help="select full or exact spatially pruned native-avoidance scans",
    )
    parser.add_argument(
        "--collision-plane-fields",
        choices=("defensive", "direct"),
        default="direct",
        help="select defensive or required Entity collision-plane fields",
    )
    parser.add_argument("--clear-route-cache-per-mode", action="store_true")
    return parser.parse_args()


def _battle(
    *,
    seed: int,
    card: str,
    per_side: int,
    fast_path: bool,
    target_cache_refresh: str,
    building_cache_refresh: str,
) -> BattleState:
    battle = BattleState(rng=random.Random(seed), fast_path=fast_path)
    if target_cache_refresh == "rebuild":
        battle._refresh_target_cache = battle._rebuild_target_cache
    if building_cache_refresh == "rebuild":
        battle._refresh_alive_buildings_cache = (
            battle._rebuild_alive_buildings_cache
        )
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
    battle_module._USE_STATIC_TARGETABILITY_CLASSIFICATION = (
        args.targetability_refresh == "classified"
    )
    battle_module._USE_INPLACE_BUCKET_ID_SORT = args.bucket_id_sort == "inplace"
    battle_module._USE_ROW_MAJOR_BUCKET_SCAN = (
        args.bucket_scan_order == "row-major"
    )
    battle_module._USE_CACHED_BUCKET_GEOMETRY = args.bucket_geometry == "cached"
    battle_module._USE_TRUSTED_ALIVE_BUILDING_MEMBERSHIP = (
        args.building_membership == "trusted"
    )
    battle_module._USE_CACHED_MOVER_HOVER_TRAIT = (
        args.mover_hover_trait == "cached"
    )
    entities_module._USE_CACHED_CROWN_FALLBACK_MEMBERSHIP = (
        args.crown_fallback_membership == "cached"
    )
    entities_module._PREFER_CROWN_FALLBACK_BEFORE_DISTANCE = (
        args.crown_distance_order == "preferred-first"
    )
    entities_module._DEFER_INACTIVE_STEALTH_TIME_LOOKUP = (
        args.inactive_stealth_time == "deferred"
    )
    entities_module._USE_DIRECT_TARGETABILITY_FIELDS = (
        args.targetability_fields == "direct"
    )
    entities_module._USE_AVOIDANCE_BUCKET_CANDIDATES = (
        args.avoidance_candidates == "bucketed"
    )
    unit_traits._USE_DIRECT_ENTITY_COLLISION_PLANE = (
        args.collision_plane_fields == "direct"
    )
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
                target_cache_refresh=args.target_cache_refresh,
                building_cache_refresh=args.building_cache_refresh,
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
                "target_cache_refresh": args.target_cache_refresh,
                "building_cache_refresh": args.building_cache_refresh,
                "targetability_refresh": args.targetability_refresh,
                "crown_fallback_membership": args.crown_fallback_membership,
                "crown_distance_order": args.crown_distance_order,
                "inactive_stealth_time": args.inactive_stealth_time,
                "bucket_id_sort": args.bucket_id_sort,
                "targetability_fields": args.targetability_fields,
                "bucket_scan_order": args.bucket_scan_order,
                "bucket_geometry": args.bucket_geometry,
                "building_membership": args.building_membership,
                "mover_hover_trait": args.mover_hover_trait,
                "avoidance_candidates": args.avoidance_candidates,
                "collision_plane_fields": args.collision_plane_fields,
                "results": reports,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
