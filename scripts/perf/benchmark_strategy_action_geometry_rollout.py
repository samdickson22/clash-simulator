#!/usr/bin/env python3
"""Benchmark direct strategy action geometry in stationary rollouts."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time

import numpy as np
import torch
from benchmark_stationary_rollout import _digest_rollout

from clasher.rl import strategy_bots as strategy_bots_module
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import STRATEGY_NAMES, StrategyBot
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import collect_rollout_stationary_opponents


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", choices=STRATEGY_NAMES, default="balanced")
    parser.add_argument(
        "--comparison",
        choices=("geometry", "tile-fit-cache"),
        default="geometry",
    )
    parser.add_argument("--seed", type=int, default=2301)
    parser.add_argument("--num-envs", type=int, default=1)
    parser.add_argument("--rollout-steps", type=int, default=64)
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--warmup-steps", type=int, default=8)
    parser.add_argument("--torch-threads", type=int, default=2)
    parser.add_argument("--max-ticks", type=int, default=2048)
    parser.add_argument(
        "--engine-fast-path",
        choices=("off", "shadow", "on"),
        default="on",
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
    variants = (
        ("decoded", "direct")
        if args.comparison == "geometry"
        else ("uncached", "cached")
    )

    def run_once(variant: str, steps: int) -> dict[str, float | str]:
        strategy_bots_module._USE_DIRECT_CANONICAL_ACTION_GEOMETRY = (
            variant == "direct" if args.comparison == "geometry" else True
        )
        strategy_bots_module._USE_CACHED_STRATEGY_TILE_FITS = (
            variant == "cached" if args.comparison == "tile-fit-cache" else True
        )
        torch.manual_seed(args.seed + 99)
        envs = [
            SelfPlayBattleEnv(
                seed=args.seed + env_index,
                max_ticks=args.max_ticks,
                engine_fast_path=args.engine_fast_path,
            )
            for env_index in range(args.num_envs)
        ]
        for env in envs:
            env._structured_obs_builder = builder
            env.reset()
        no_op = envs[0].action_space.no_op_action
        zeros = np.zeros((args.num_envs,), dtype=np.float32)
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
            opponent_bot=StrategyBot(args.strategy),
        )
        elapsed = time.perf_counter() - started
        shadow_checks = sum(
            int(env.fast_path_metrics()["mask_shadow_checks"])
            for env in envs
        )
        shadow_mismatches = sum(
            int(env.fast_path_metrics()["mask_shadow_mismatches"])
            for env in envs
        )
        return {
            "variant": variant,
            "seconds": elapsed,
            "decisions_per_second": args.num_envs * steps / elapsed,
            "sha256": _digest_rollout(result[0], envs),
            "mask_shadow_checks": shadow_checks,
            "mask_shadow_mismatches": shadow_mismatches,
        }

    if args.warmup_steps:
        for variant in variants:
            run_once(variant, args.warmup_steps)
    rows = []
    for repetition in range(args.repetitions):
        order = (
            variants
            if repetition % 2 == 0
            else tuple(reversed(variants))
        )
        for variant in order:
            row = run_once(variant, args.rollout_steps)
            row["repetition"] = repetition
            rows.append(row)

    summary = {}
    for variant in variants:
        selected = [row for row in rows if row["variant"] == variant]
        seconds = [float(row["seconds"]) for row in selected]
        rates = [float(row["decisions_per_second"]) for row in selected]
        summary[variant] = {
            "seconds_median": statistics.median(seconds),
            "seconds_mean": statistics.mean(seconds),
            "seconds_stdev": statistics.stdev(seconds) if len(seconds) > 1 else 0.0,
            "decisions_per_second_median": statistics.median(rates),
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
