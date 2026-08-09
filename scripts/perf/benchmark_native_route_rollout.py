#!/usr/bin/env python3
"""Benchmark dense native routing in stationary-opponent RL rollouts."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
from functools import lru_cache

import numpy as np
import torch
from benchmark_stationary_rollout import _digest_rollout

from clasher import pathfinding
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
    parser.add_argument("--rollout-steps", type=int, default=32)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--warmup-steps", type=int, default=4)
    parser.add_argument("--torch-threads", type=int, default=2)
    parser.add_argument("--max-ticks", type=int, default=2048)
    parser.add_argument("--decks-path", default="decks.json")
    return parser.parse_args()


def _router(mode: str):
    @lru_cache(maxsize=2048)
    def route(start, goal, lane_id, jump_height):
        if mode == "mapping":
            value = pathfinding._native_grid_route(
                start,
                goal,
                pathfinding._standard_path_cost_map(lane_id, jump_height).get,
            )
        else:
            value = pathfinding._native_standard_grid_route(
                start,
                goal,
                pathfinding._standard_path_cost_grid(lane_id, jump_height),
            )
        return None if value is None else tuple(value)

    return route


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
    model = ClasherPolicy(config, builder.card_stat_features)
    model.eval()

    def run_once(mode: str, steps: int) -> dict[str, float | str]:
        pathfinding._standard_path_cost_grid.cache_clear()
        pathfinding._standard_path_cost_map.cache_clear()
        pathfinding._cached_standard_grid_route = _router(mode)
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
            "mode": mode,
            "seconds": elapsed,
            "decisions_per_second": args.num_envs * steps / elapsed,
            "sha256": _digest_rollout(result[0], envs),
            "route_cache": str(pathfinding._cached_standard_grid_route.cache_info()),
        }

    if args.warmup_steps:
        run_once("mapping", args.warmup_steps)
        run_once("dense", args.warmup_steps)
    rows = []
    for repetition in range(args.repetitions):
        order = (
            ("mapping", "dense")
            if repetition % 2 == 0
            else ("dense", "mapping")
        )
        for mode in order:
            row = run_once(mode, args.rollout_steps)
            row["repetition"] = repetition
            rows.append(row)

    summary = {}
    for mode in ("mapping", "dense"):
        selected = [row for row in rows if row["mode"] == mode]
        seconds = [float(row["seconds"]) for row in selected]
        rates = [float(row["decisions_per_second"]) for row in selected]
        summary[mode] = {
            "seconds_median": statistics.median(seconds),
            "seconds_mean": statistics.mean(seconds),
            "seconds_stdev": statistics.stdev(seconds),
            "decisions_per_second_median": statistics.median(rates),
            "hashes": sorted({str(row["sha256"]) for row in selected}),
        }
    mapping = float(summary["mapping"]["seconds_median"])
    dense = float(summary["dense"]["seconds_median"])
    summary["dense_vs_mapping_percent"] = 100.0 * (mapping / dense - 1.0)
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
