#!/usr/bin/env python3
"""Benchmark deployment-blocker reuse in stationary rollouts."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time

import numpy as np
import torch
from benchmark_stationary_rollout import _digest_rollout

from clasher import battle as battle_module
from clasher import entities as entities_module
from clasher import pathfinding as pathfinding_module
from clasher.rl import action_space as action_space_module
from clasher.rl import reward_model as reward_model_module
from clasher.rl import train_recurrent as train_recurrent_module
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import StrategyBot
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import collect_rollout_stationary_opponents


def _paired_gain_summary(
    rows: list[dict[str, float | str | int]],
    reference_variant: str,
    candidate_variant: str,
) -> dict[str, object]:
    gains = []
    for repetition in sorted({int(row["repetition"]) for row in rows}):
        pair = {
            str(row["variant"]): float(row["seconds"])
            for row in rows
            if int(row["repetition"]) == repetition
        }
        gains.append(
            100.0
            * (pair[reference_variant] / pair[candidate_variant] - 1.0)
        )
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
    parser.add_argument("--workload", choices=("random", "strategy"), required=True)
    parser.add_argument("--strategy", default="balanced")
    parser.add_argument("--seed", type=int, default=2301)
    parser.add_argument("--num-envs", type=int, default=8)
    parser.add_argument("--rollout-steps", type=int, default=32)
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--warmup-steps", type=int, default=8)
    parser.add_argument("--torch-threads", type=int, default=2)
    parser.add_argument("--max-ticks", type=int, default=2048)
    parser.add_argument(
        "--engine-fast-path",
        choices=("off", "shadow", "on"),
        default="on",
    )
    parser.add_argument(
        "--comparison",
        choices=(
            "guard",
            "inference-mode",
            "targetability-requirement",
            "target-entity-kind",
            "crown-fallback",
            "movement-building-refresh",
            "path-hover-trait",
            "dirty-target-cache",
            "prefiltered-action-candidates",
            "lazy-card-materialization",
            "cached-princess-data",
        ),
        default="guard",
    )
    parser.add_argument(
        "--reward-profile",
        choices=reward_model_module.REWARD_PROFILES,
        default=reward_model_module.OBJECTIVE_V1,
    )
    parser.add_argument("--decks-path", default="decks.json")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
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
    model = ClasherPolicy(config, builder.card_stat_features).eval()

    if args.comparison == "guard":
        reference_variant, candidate_variant = "scanned", "guarded"
    elif args.comparison == "inference-mode":
        reference_variant, candidate_variant = "no-grad", "inference"
    elif args.comparison == "targetability-requirement":
        reference_variant, candidate_variant = "recomputed", "cached"
    elif args.comparison == "target-entity-kind":
        reference_variant, candidate_variant = "getattr", "direct"
    elif args.comparison == "crown-fallback":
        reference_variant, candidate_variant = "partitioned", "single-pass"
    elif args.comparison == "movement-building-refresh":
        reference_variant, candidate_variant = "repeated", "coalesced"
    elif args.comparison == "path-hover-trait":
        reference_variant, candidate_variant = "runtime", "cached"
    elif args.comparison == "dirty-target-cache":
        reference_variant, candidate_variant = "full", "dirty"
    elif args.comparison == "prefiltered-action-candidates":
        reference_variant, candidate_variant = "rechecked", "prefiltered"
    elif args.comparison == "lazy-card-materialization":
        reference_variant, candidate_variant = "eager", "lazy"
    else:
        reference_variant, candidate_variant = "parsed", "cached"

    def run_once(variant: str, steps: int) -> dict[str, float | str | int]:
        pathfinding_module._USE_CACHED_GROUND_PATH_HOVER_TRAIT = True
        entities_module._USE_CACHED_PATHFIND_HOVER_TRAIT = True
        battle_module._USE_DIRTY_TARGET_CACHE_REFRESH = True
        action_space_module._USE_PREFILTERED_ACTION_MASK_CANDIDATES = True
        if args.comparison == "guard":
            action_space_module._USE_DEPLOYMENT_BLOCKER_GUARD = (
                variant == candidate_variant
            )
            train_recurrent_module._USE_ROLLOUT_INFERENCE_MODE = True
            battle_module._USE_CACHED_TARGETABILITY_REQUIREMENT = True
            battle_module._USE_DIRECT_TARGET_ENTITY_KIND = True
            entities_module._USE_SINGLE_PASS_CACHED_CROWN_FALLBACK = True
            battle_module._COALESCE_MOVEMENT_BUILDING_CACHE_REFRESH = True
            battle_module._EAGERLY_MATERIALIZE_BATTLE_CARDS = False
            battle_module._USE_CACHED_PRINCESS_TOWER_DATA = True
        elif args.comparison == "inference-mode":
            action_space_module._USE_DEPLOYMENT_BLOCKER_GUARD = True
            train_recurrent_module._USE_ROLLOUT_INFERENCE_MODE = (
                variant == candidate_variant
            )
            battle_module._USE_CACHED_TARGETABILITY_REQUIREMENT = True
            battle_module._USE_DIRECT_TARGET_ENTITY_KIND = True
            entities_module._USE_SINGLE_PASS_CACHED_CROWN_FALLBACK = True
            battle_module._COALESCE_MOVEMENT_BUILDING_CACHE_REFRESH = True
            battle_module._EAGERLY_MATERIALIZE_BATTLE_CARDS = False
            battle_module._USE_CACHED_PRINCESS_TOWER_DATA = True
        elif args.comparison == "targetability-requirement":
            action_space_module._USE_DEPLOYMENT_BLOCKER_GUARD = True
            train_recurrent_module._USE_ROLLOUT_INFERENCE_MODE = True
            battle_module._USE_CACHED_TARGETABILITY_REQUIREMENT = (
                variant == candidate_variant
            )
            battle_module._USE_DIRECT_TARGET_ENTITY_KIND = True
            entities_module._USE_SINGLE_PASS_CACHED_CROWN_FALLBACK = True
            battle_module._COALESCE_MOVEMENT_BUILDING_CACHE_REFRESH = True
            battle_module._EAGERLY_MATERIALIZE_BATTLE_CARDS = False
            battle_module._USE_CACHED_PRINCESS_TOWER_DATA = True
        elif args.comparison == "target-entity-kind":
            action_space_module._USE_DEPLOYMENT_BLOCKER_GUARD = True
            train_recurrent_module._USE_ROLLOUT_INFERENCE_MODE = True
            battle_module._USE_CACHED_TARGETABILITY_REQUIREMENT = True
            battle_module._USE_DIRECT_TARGET_ENTITY_KIND = (
                variant == candidate_variant
            )
            entities_module._USE_SINGLE_PASS_CACHED_CROWN_FALLBACK = True
            battle_module._COALESCE_MOVEMENT_BUILDING_CACHE_REFRESH = True
            battle_module._EAGERLY_MATERIALIZE_BATTLE_CARDS = False
            battle_module._USE_CACHED_PRINCESS_TOWER_DATA = True
        elif args.comparison == "crown-fallback":
            action_space_module._USE_DEPLOYMENT_BLOCKER_GUARD = True
            train_recurrent_module._USE_ROLLOUT_INFERENCE_MODE = True
            battle_module._USE_CACHED_TARGETABILITY_REQUIREMENT = True
            battle_module._USE_DIRECT_TARGET_ENTITY_KIND = True
            entities_module._USE_SINGLE_PASS_CACHED_CROWN_FALLBACK = (
                variant == candidate_variant
            )
            battle_module._COALESCE_MOVEMENT_BUILDING_CACHE_REFRESH = True
            battle_module._EAGERLY_MATERIALIZE_BATTLE_CARDS = False
            battle_module._USE_CACHED_PRINCESS_TOWER_DATA = True
        elif args.comparison == "movement-building-refresh":
            action_space_module._USE_DEPLOYMENT_BLOCKER_GUARD = True
            train_recurrent_module._USE_ROLLOUT_INFERENCE_MODE = True
            battle_module._USE_CACHED_TARGETABILITY_REQUIREMENT = True
            battle_module._USE_DIRECT_TARGET_ENTITY_KIND = True
            entities_module._USE_SINGLE_PASS_CACHED_CROWN_FALLBACK = True
            battle_module._COALESCE_MOVEMENT_BUILDING_CACHE_REFRESH = (
                variant == candidate_variant
            )
            battle_module._EAGERLY_MATERIALIZE_BATTLE_CARDS = False
            battle_module._USE_CACHED_PRINCESS_TOWER_DATA = True
        elif args.comparison == "path-hover-trait":
            action_space_module._USE_DEPLOYMENT_BLOCKER_GUARD = True
            train_recurrent_module._USE_ROLLOUT_INFERENCE_MODE = True
            battle_module._USE_CACHED_TARGETABILITY_REQUIREMENT = True
            battle_module._USE_DIRECT_TARGET_ENTITY_KIND = True
            entities_module._USE_SINGLE_PASS_CACHED_CROWN_FALLBACK = True
            battle_module._COALESCE_MOVEMENT_BUILDING_CACHE_REFRESH = True
            battle_module._EAGERLY_MATERIALIZE_BATTLE_CARDS = False
            battle_module._USE_CACHED_PRINCESS_TOWER_DATA = True
            pathfinding_module._USE_CACHED_GROUND_PATH_HOVER_TRAIT = (
                variant == candidate_variant
            )
            entities_module._USE_CACHED_PATHFIND_HOVER_TRAIT = (
                variant == candidate_variant
            )
        elif args.comparison == "dirty-target-cache":
            action_space_module._USE_DEPLOYMENT_BLOCKER_GUARD = True
            train_recurrent_module._USE_ROLLOUT_INFERENCE_MODE = True
            battle_module._USE_CACHED_TARGETABILITY_REQUIREMENT = True
            battle_module._USE_DIRECT_TARGET_ENTITY_KIND = True
            entities_module._USE_SINGLE_PASS_CACHED_CROWN_FALLBACK = True
            battle_module._COALESCE_MOVEMENT_BUILDING_CACHE_REFRESH = True
            battle_module._EAGERLY_MATERIALIZE_BATTLE_CARDS = False
            battle_module._USE_CACHED_PRINCESS_TOWER_DATA = True
            battle_module._USE_DIRTY_TARGET_CACHE_REFRESH = (
                variant == candidate_variant
            )
        elif args.comparison == "prefiltered-action-candidates":
            action_space_module._USE_DEPLOYMENT_BLOCKER_GUARD = True
            train_recurrent_module._USE_ROLLOUT_INFERENCE_MODE = True
            battle_module._USE_CACHED_TARGETABILITY_REQUIREMENT = True
            battle_module._USE_DIRECT_TARGET_ENTITY_KIND = True
            entities_module._USE_SINGLE_PASS_CACHED_CROWN_FALLBACK = True
            battle_module._COALESCE_MOVEMENT_BUILDING_CACHE_REFRESH = True
            battle_module._EAGERLY_MATERIALIZE_BATTLE_CARDS = False
            battle_module._USE_CACHED_PRINCESS_TOWER_DATA = True
            action_space_module._USE_PREFILTERED_ACTION_MASK_CANDIDATES = (
                variant == candidate_variant
            )
        elif args.comparison == "lazy-card-materialization":
            action_space_module._USE_DEPLOYMENT_BLOCKER_GUARD = True
            train_recurrent_module._USE_ROLLOUT_INFERENCE_MODE = True
            battle_module._USE_CACHED_TARGETABILITY_REQUIREMENT = True
            battle_module._USE_DIRECT_TARGET_ENTITY_KIND = True
            entities_module._USE_SINGLE_PASS_CACHED_CROWN_FALLBACK = True
            battle_module._COALESCE_MOVEMENT_BUILDING_CACHE_REFRESH = True
            battle_module._EAGERLY_MATERIALIZE_BATTLE_CARDS = (
                variant == reference_variant
            )
            battle_module._USE_CACHED_PRINCESS_TOWER_DATA = True
        else:
            action_space_module._USE_DEPLOYMENT_BLOCKER_GUARD = True
            train_recurrent_module._USE_ROLLOUT_INFERENCE_MODE = True
            battle_module._USE_CACHED_TARGETABILITY_REQUIREMENT = True
            battle_module._USE_DIRECT_TARGET_ENTITY_KIND = True
            entities_module._USE_SINGLE_PASS_CACHED_CROWN_FALLBACK = True
            battle_module._COALESCE_MOVEMENT_BUILDING_CACHE_REFRESH = True
            battle_module._EAGERLY_MATERIALIZE_BATTLE_CARDS = False
            battle_module._USE_CACHED_PRINCESS_TOWER_DATA = (
                variant == candidate_variant
            )
        torch.manual_seed(args.seed + 99)
        include_initialization = args.comparison in {
            "lazy-card-materialization",
            "cached-princess-data",
        }
        if include_initialization:
            started = time.perf_counter()
        envs = [
            SelfPlayBattleEnv(
                seed=args.seed + env_index,
                max_ticks=args.max_ticks,
                engine_fast_path=args.engine_fast_path,
                reward_profile=args.reward_profile,
            )
            for env_index in range(args.num_envs)
        ]
        for env in envs:
            env._structured_obs_builder = builder
            env.reset()
        no_op = envs[0].action_space.no_op_action
        zeros = np.zeros((args.num_envs,), dtype=np.float32)
        starts = np.ones((args.num_envs,), dtype=np.bool_)
        if not include_initialization:
            started = time.perf_counter()
        result = collect_rollout_stationary_opponents(
            envs=envs,
            learner_players=tuple(index % 2 for index in range(args.num_envs)),
            builder=builder,
            model=model,
            device=torch.device("cpu"),
            rollout_steps=steps,
            recurrent_state=model.initial_state(args.num_envs),
            previous_actions=np.full(args.num_envs, no_op, dtype=np.int64),
            previous_rewards=zeros.copy(),
            episode_starts=starts.copy(),
            opponent_model=None,
            opponent_recurrent_state=None,
            opponent_previous_actions=np.full(
                args.num_envs,
                no_op,
                dtype=np.int64,
            ),
            opponent_previous_rewards=zeros.copy(),
            opponent_episode_starts=starts.copy(),
            quiet_engine=True,
            opponent_bot=(
                StrategyBot(args.strategy)
                if args.workload == "strategy"
                else None
            ),
        )
        elapsed = time.perf_counter() - started
        metrics = [env.fast_path_metrics() for env in envs]
        return {
            "variant": variant,
            "seconds": elapsed,
            "decisions_per_second": args.num_envs * steps / elapsed,
            "sha256": _digest_rollout(result[0], envs),
            "mask_shadow_checks": sum(
                int(metric["mask_shadow_checks"])
                for metric in metrics
            ),
            "mask_shadow_mismatches": sum(
                int(metric["mask_shadow_mismatches"])
                for metric in metrics
            ),
        }

    if args.warmup_steps:
        run_once(reference_variant, args.warmup_steps)
        run_once(candidate_variant, args.warmup_steps)
    rows = []
    for repetition in range(args.repetitions):
        order = (
            (reference_variant, candidate_variant)
            if repetition % 2 == 0
            else (candidate_variant, reference_variant)
        )
        for variant in order:
            row = run_once(variant, args.rollout_steps)
            row["repetition"] = repetition
            rows.append(row)

    summary = {}
    for variant in (reference_variant, candidate_variant):
        selected = [row for row in rows if row["variant"] == variant]
        seconds = [float(row["seconds"]) for row in selected]
        rates = [float(row["decisions_per_second"]) for row in selected]
        summary[variant] = {
            "seconds_median": statistics.median(seconds),
            "seconds_mean": statistics.mean(seconds),
            "seconds_stdev": (
                statistics.stdev(seconds) if len(seconds) > 1 else 0.0
            ),
            "decisions_per_second_median": statistics.median(rates),
            "hashes": sorted({str(row["sha256"]) for row in selected}),
        }
    reference = float(summary[reference_variant]["seconds_median"])
    candidate = float(summary[candidate_variant]["seconds_median"])
    summary[f"{candidate_variant}_vs_{reference_variant}_percent"] = 100.0 * (
        reference / candidate - 1.0
    )
    summary[f"paired_{candidate_variant}_vs_{reference_variant}_percent"] = (
        _paired_gain_summary(rows, reference_variant, candidate_variant)
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
