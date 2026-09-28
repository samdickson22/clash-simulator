#!/usr/bin/env python3
"""Measure direct strategy geometry and tile-fit caching as a 2x2 factorial."""

from __future__ import annotations

import argparse
import json
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
    parser.add_argument("--seed", type=int, default=2301)
    parser.add_argument("--num-envs", type=int, default=8)
    parser.add_argument("--rollout-steps", type=int, default=16)
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--warmup-steps", type=int, default=8)
    parser.add_argument("--torch-threads", type=int, default=2)
    parser.add_argument("--max-ticks", type=int, default=2048)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    torch.set_num_threads(args.torch_threads)
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    torch.manual_seed(91)
    model = ClasherPolicy(
        PolicyConfig(
            num_tokens=builder.spec.num_tokens,
            max_entities=builder.spec.max_entities,
        ),
        builder.card_stat_features,
    ).eval()
    variants = (
        ("decoded_uncached", False, False),
        ("direct_uncached", True, False),
        ("decoded_cached", False, True),
        ("direct_cached", True, True),
    )

    def run_once(
        name: str,
        direct: bool,
        cached: bool,
        steps: int,
    ) -> dict[str, float | str | bool]:
        strategy_bots_module._USE_DIRECT_CANONICAL_ACTION_GEOMETRY = direct
        strategy_bots_module._USE_CACHED_STRATEGY_TILE_FITS = cached
        torch.manual_seed(args.seed + 99)
        envs = [
            SelfPlayBattleEnv(
                seed=args.seed + index,
                max_ticks=args.max_ticks,
                engine_fast_path="on",
            )
            for index in range(args.num_envs)
        ]
        for env in envs:
            env._structured_obs_builder = builder
            env.reset()
        no_op = envs[0].action_space.no_op_action
        starts = np.ones((args.num_envs,), dtype=np.bool_)
        zeros = np.zeros((args.num_envs,), dtype=np.float32)
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
            opponent_previous_actions=np.full(args.num_envs, no_op, dtype=np.int64),
            opponent_previous_rewards=zeros.copy(),
            opponent_episode_starts=starts.copy(),
            quiet_engine=True,
            opponent_bot=StrategyBot(args.strategy),
        )
        elapsed = time.perf_counter() - started
        return {
            "variant": name,
            "direct": direct,
            "cached": cached,
            "seconds": elapsed,
            "decisions_per_second": args.num_envs * steps / elapsed,
            "sha256": _digest_rollout(result[0], envs),
        }

    for variant in variants:
        run_once(*variant, args.warmup_steps)
    rows: list[dict[str, float | str | bool | int]] = []
    for repetition in range(args.repetitions):
        offset = repetition % len(variants)
        order = variants[offset:] + variants[:offset]
        if repetition % 2:
            order = tuple(reversed(order))
        for variant in order:
            row = run_once(*variant, args.rollout_steps)
            row["repetition"] = repetition
            rows.append(row)

    summary: dict[str, object] = {}
    for name, _, _ in variants:
        selected = [row for row in rows if row["variant"] == name]
        seconds = [float(row["seconds"]) for row in selected]
        rates = [float(row["decisions_per_second"]) for row in selected]
        summary[name] = {
            "seconds_median": statistics.median(seconds),
            "decisions_per_second_median": statistics.median(rates),
            "hashes": sorted({str(row["sha256"]) for row in selected}),
        }
    baseline = float(
        dict(summary["decoded_uncached"])["decisions_per_second_median"]
    )
    for name, _, _ in variants[1:]:
        rate = float(dict(summary[name])["decisions_per_second_median"])
        summary[f"{name}_vs_baseline_percent"] = 100.0 * (rate / baseline - 1.0)
    print(json.dumps({"config": vars(args), "rows": rows, "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
