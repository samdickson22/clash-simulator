#!/usr/bin/env python3
"""Benchmark recurrent rollouts against stationary random/strategy opponents."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time

import numpy as np
import torch

from clasher import battle as battle_module
from clasher import entities as entities_module
from clasher import unit_traits
from clasher.battle import BattleState
from clasher.rl import structured_obs as structured_obs_module
from clasher.rl import train_recurrent as train_recurrent_module
from clasher.rl import action_space as action_space_module
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import StrategyBot
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import collect_rollout_stationary_opponents


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload", choices=("random", "strategy"), required=True)
    parser.add_argument("--strategy", default="balanced")
    parser.add_argument("--seed", type=int, default=2301)
    parser.add_argument("--num-envs", type=int, default=1)
    parser.add_argument("--rollout-steps", type=int, default=12)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--warmup-steps", type=int, default=2)
    parser.add_argument("--torch-threads", type=int, default=2)
    parser.add_argument("--max-ticks", type=int, default=2048)
    parser.add_argument(
        "--engine-fast-path", choices=("off", "shadow", "on"), default="on"
    )
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
    parser.add_argument(
        "--unit-mass",
        choices=("runtime", "cached"),
        default="cached",
        help="select runtime or entity-cached data-driven collision mass",
    )
    parser.add_argument(
        "--collision-radius",
        choices=("runtime", "cached"),
        default="cached",
        help="select runtime or entity-cached normalized collision radius",
    )
    parser.add_argument(
        "--target-plane-checks",
        choices=("repeated", "coalesced"),
        default="coalesced",
        help="select repeated or single dynamic target-plane classification",
    )
    parser.add_argument(
        "--observation-buffers",
        choices=("stacked", "preallocated", "both"),
        default="preallocated",
        help="select duplicate stacking or reusable CPU actor step buffers",
    )
    parser.add_argument(
        "--unit-clip",
        choices=("numpy", "scalar", "both"),
        default="scalar",
        help="select NumPy-dispatched or exact scalar feature clipping",
    )
    parser.add_argument(
        "--entity-range-clip",
        choices=("numpy", "scalar", "both"),
        default="scalar",
        help="select NumPy-dispatched or exact scalar entity range clipping",
    )
    parser.add_argument(
        "--deployment-blocker-guard",
        choices=("scan", "guard", "both"),
        default="guard",
        help="select unconditional per-tile payload scans or one exact empty guard",
    )
    parser.add_argument("--decks-path", default="decks.json")
    return parser.parse_args()


def _digest_rollout(rollout: object, envs: list[SelfPlayBattleEnv]) -> str:
    hasher = hashlib.sha256()
    for name, value in vars(rollout).items():
        if isinstance(value, np.ndarray):
            hasher.update(name.encode("utf-8"))
            hasher.update(np.ascontiguousarray(value).tobytes())
        else:
            hasher.update(f"{name}={value}".encode("utf-8"))
    for env in envs:
        assert env.battle is not None
        hasher.update(
            f"{env.battle.tick}:{env.battle.winner}:{len(env.battle.entities)}".encode(
                "utf-8"
            )
        )
    return hasher.hexdigest()


def main() -> None:
    args = _parse_args()
    if args.target_cache_refresh == "rebuild":
        BattleState._refresh_target_cache = BattleState._rebuild_target_cache
    if args.building_cache_refresh == "rebuild":
        BattleState._refresh_alive_buildings_cache = (
            BattleState._rebuild_alive_buildings_cache
        )
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
    entities_module._USE_CACHED_ENTITY_UNIT_MASS = args.unit_mass == "cached"
    entities_module._USE_CACHED_ENTITY_COLLISION_RADIUS = (
        args.collision_radius == "cached"
    )
    entities_module._COALESCE_TARGET_PLANE_CHECKS = (
        args.target_plane_checks == "coalesced"
    )
    unit_traits._USE_DIRECT_ENTITY_COLLISION_PLANE = (
        args.collision_plane_fields == "direct"
    )
    torch.set_num_threads(args.torch_threads)
    builder = StructuredObservationBuilder(
        decks_path=args.decks_path,
        max_entities=128,
    )
    config = PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=builder.spec.max_entities,
    )
    torch.manual_seed(91)
    model = ClasherPolicy(config, builder.card_stat_features)
    model.eval()

    scalar_unit_clip = structured_obs_module._unit_clip
    scalar_range_clip = structured_obs_module._range_clip_scalar

    def run_once(
        steps: int,
        observation_buffers: str,
        unit_clip: str,
        entity_range_clip: str,
        deployment_blocker_guard: str,
    ) -> dict[str, float | str]:
        action_space_module._USE_DEPLOYMENT_BLOCKER_GUARD = (
            deployment_blocker_guard == "guard"
        )
        train_recurrent_module._USE_PREALLOCATED_STEP_OBSERVATION_BUFFERS = (
            observation_buffers == "preallocated"
        )
        structured_obs_module._unit_clip = (
            structured_obs_module._unit_clip_numpy
            if unit_clip == "numpy"
            else scalar_unit_clip
        )
        structured_obs_module._range_clip = (
            structured_obs_module._range_clip_numpy
            if entity_range_clip == "numpy"
            else scalar_range_clip
        )
        torch.manual_seed(args.seed + 99)
        envs = [
            SelfPlayBattleEnv(
                seed=args.seed + index,
                max_ticks=args.max_ticks,
                engine_fast_path=args.engine_fast_path,
            )
            for index in range(args.num_envs)
        ]
        for env in envs:
            env._structured_obs_builder = builder
            env.reset()
        no_op = envs[0].action_space.no_op_action
        float_zeros = np.zeros((args.num_envs,), dtype=np.float32)
        starts = np.ones((args.num_envs,), dtype=np.bool_)
        started = time.perf_counter()
        result = collect_rollout_stationary_opponents(
            envs=envs,
            learner_players=tuple(index % 2 for index in range(args.num_envs)),
            builder=builder,
            model=model,
            device=torch.device("cpu"),
            rollout_steps=steps,
            recurrent_state=model.initial_state(args.num_envs),
            previous_actions=np.full((args.num_envs,), no_op, dtype=np.int64),
            previous_rewards=float_zeros.copy(),
            episode_starts=starts.copy(),
            opponent_model=None,
            opponent_recurrent_state=None,
            opponent_previous_actions=np.full(
                (args.num_envs,), no_op, dtype=np.int64
            ),
            opponent_previous_rewards=float_zeros.copy(),
            opponent_episode_starts=starts.copy(),
            quiet_engine=True,
            opponent_bot=(
                StrategyBot(args.strategy) if args.workload == "strategy" else None
            ),
        )
        elapsed = time.perf_counter() - started
        return {
            "observation_buffers": observation_buffers,
            "unit_clip": unit_clip,
            "entity_range_clip": entity_range_clip,
            "deployment_blocker_guard": deployment_blocker_guard,
            "elapsed_s": elapsed,
            "decisions_per_s": args.num_envs * steps / elapsed,
            "sha256": _digest_rollout(result[0], envs),
        }

    observation_buffer_variants = (
        ("stacked", "preallocated")
        if args.observation_buffers == "both"
        else (args.observation_buffers,)
    )
    unit_clip_variants = (
        ("numpy", "scalar") if args.unit_clip == "both" else (args.unit_clip,)
    )
    entity_range_clip_variants = (
        ("numpy", "scalar")
        if args.entity_range_clip == "both"
        else (args.entity_range_clip,)
    )
    deployment_blocker_guard_variants = (
        ("scan", "guard")
        if args.deployment_blocker_guard == "both"
        else (args.deployment_blocker_guard,)
    )
    variants = tuple(
        (
            observation_buffers,
            unit_clip,
            entity_range_clip,
            deployment_blocker_guard,
        )
        for observation_buffers in observation_buffer_variants
        for unit_clip in unit_clip_variants
        for entity_range_clip in entity_range_clip_variants
        for deployment_blocker_guard in deployment_blocker_guard_variants
    )
    if args.warmup_steps:
        for (
            observation_buffers,
            unit_clip,
            entity_range_clip,
            deployment_blocker_guard,
        ) in variants:
            run_once(
                args.warmup_steps,
                observation_buffers,
                unit_clip,
                entity_range_clip,
                deployment_blocker_guard,
            )
    rows = []
    for repetition in range(args.repetitions):
        order = variants if repetition % 2 == 0 else tuple(reversed(variants))
        for (
            observation_buffers,
            unit_clip,
            entity_range_clip,
            deployment_blocker_guard,
        ) in order:
            row = run_once(
                args.rollout_steps,
                observation_buffers,
                unit_clip,
                entity_range_clip,
                deployment_blocker_guard,
            )
            row["repetition"] = repetition
            rows.append(row)
    elapsed = [float(row["elapsed_s"]) for row in rows]
    rates = [float(row["decisions_per_s"]) for row in rows]
    summary = {}
    for (
        observation_buffers,
        unit_clip,
        entity_range_clip,
        deployment_blocker_guard,
    ) in variants:
        varying_parts = []
        if len(observation_buffer_variants) > 1:
            varying_parts.append(observation_buffers)
        if len(unit_clip_variants) > 1:
            varying_parts.append(unit_clip)
        if len(entity_range_clip_variants) > 1:
            varying_parts.append(entity_range_clip)
        if len(deployment_blocker_guard_variants) > 1:
            varying_parts.append(deployment_blocker_guard)
        variant = "/".join(varying_parts) if varying_parts else observation_buffers
        selected = [
            row
            for row in rows
            if row["observation_buffers"] == observation_buffers
            and row["unit_clip"] == unit_clip
            and row["entity_range_clip"] == entity_range_clip
            and row["deployment_blocker_guard"] == deployment_blocker_guard
        ]
        summary[variant] = {
            "median_elapsed_s": statistics.median(
                float(row["elapsed_s"]) for row in selected
            ),
            "median_decisions_per_s": statistics.median(
                float(row["decisions_per_s"]) for row in selected
            ),
            "hashes": sorted({str(row["sha256"]) for row in selected}),
        }
    if (
        args.observation_buffers == "both"
        and args.unit_clip != "both"
        and args.entity_range_clip != "both"
        and args.deployment_blocker_guard != "both"
    ):
        stacked = float(summary["stacked"]["median_elapsed_s"])
        preallocated = float(summary["preallocated"]["median_elapsed_s"])
        summary["preallocated_vs_stacked_percent"] = 100.0 * (
            stacked / preallocated - 1.0
        )
    if (
        args.unit_clip == "both"
        and args.observation_buffers != "both"
        and args.entity_range_clip != "both"
        and args.deployment_blocker_guard != "both"
    ):
        numpy_elapsed = float(summary["numpy"]["median_elapsed_s"])
        scalar_elapsed = float(summary["scalar"]["median_elapsed_s"])
        summary["scalar_vs_numpy_percent"] = 100.0 * (
            numpy_elapsed / scalar_elapsed - 1.0
        )
    if (
        args.entity_range_clip == "both"
        and args.observation_buffers != "both"
        and args.unit_clip != "both"
        and args.deployment_blocker_guard != "both"
    ):
        numpy_elapsed = float(summary["numpy"]["median_elapsed_s"])
        scalar_elapsed = float(summary["scalar"]["median_elapsed_s"])
        summary["scalar_range_vs_numpy_percent"] = 100.0 * (
            numpy_elapsed / scalar_elapsed - 1.0
        )
    if (
        args.deployment_blocker_guard == "both"
        and args.observation_buffers != "both"
        and args.unit_clip != "both"
        and args.entity_range_clip != "both"
    ):
        scan_elapsed = float(summary["scan"]["median_elapsed_s"])
        guard_elapsed = float(summary["guard"]["median_elapsed_s"])
        summary["guard_vs_scan_percent"] = 100.0 * (
            scan_elapsed / guard_elapsed - 1.0
        )
    print(
        json.dumps(
            {
                "workload": args.workload,
                "strategy": args.strategy if args.workload == "strategy" else None,
                "seed": args.seed,
                "num_envs": args.num_envs,
                "rollout_steps": args.rollout_steps,
                "repetitions": args.repetitions,
                "torch_threads": args.torch_threads,
                "engine_fast_path": args.engine_fast_path,
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
                "unit_mass": args.unit_mass,
                "collision_radius": args.collision_radius,
                "target_plane_checks": args.target_plane_checks,
                "observation_buffers": args.observation_buffers,
                "unit_clip": args.unit_clip,
                "entity_range_clip": args.entity_range_clip,
                "deployment_blocker_guard": args.deployment_blocker_guard,
                "elapsed_s": elapsed,
                "median_elapsed_s": statistics.median(elapsed),
                "decisions_per_s": rates,
                "median_decisions_per_s": statistics.median(rates),
                "hashes": sorted({str(row["sha256"]) for row in rows}),
                "rows": rows,
                "summary": summary,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
