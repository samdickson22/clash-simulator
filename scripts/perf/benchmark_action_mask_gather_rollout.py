#!/usr/bin/env python3
"""Benchmark canonical occupancy gathering in end-to-end stationary rollouts."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time

import numpy as np
import torch
from benchmark_action_mask_gather import _install_mode
from benchmark_stationary_rollout import _digest_rollout

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
    parser.add_argument("--rollout-steps", type=int, default=64)
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--warmup-steps", type=int, default=8)
    parser.add_argument("--torch-threads", type=int, default=2)
    parser.add_argument("--max-ticks", type=int, default=2048)
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
    model = ClasherPolicy(config, builder.card_stat_features)
    model.eval()

    def run_once(mode: str, steps: int) -> dict[str, float | str]:
        _install_mode(mode)
        torch.manual_seed(args.seed + 99)
        envs = [
            SelfPlayBattleEnv(
                seed=args.seed,
                max_ticks=args.max_ticks,
                engine_fast_path="on",
            )
        ]
        envs[0]._structured_obs_builder = builder
        envs[0].reset()
        no_op = envs[0].action_space.no_op_action
        float_zeros = np.zeros((1,), dtype=np.float32)
        starts = np.ones((1,), dtype=np.bool_)
        started = time.perf_counter()
        result = collect_rollout_stationary_opponents(
            envs=envs,
            learner_players=(0,),
            builder=builder,
            model=model,
            device=torch.device("cpu"),
            rollout_steps=steps,
            recurrent_state=model.initial_state(1),
            previous_actions=np.full((1,), no_op, dtype=np.int64),
            previous_rewards=float_zeros.copy(),
            episode_starts=starts.copy(),
            opponent_model=None,
            opponent_recurrent_state=None,
            opponent_previous_actions=np.full((1,), no_op, dtype=np.int64),
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
            "decisions_per_second": steps / elapsed,
            "sha256": _digest_rollout(result[0], envs),
        }

    if args.warmup_steps:
        run_once("loop", args.warmup_steps)
        run_once("gather", args.warmup_steps)
    rows = []
    for repetition in range(args.repetitions):
        order = ("loop", "gather") if repetition % 2 == 0 else ("gather", "loop")
        for mode in order:
            row = run_once(mode, args.rollout_steps)
            row["repetition"] = repetition
            rows.append(row)

    summary = {}
    for mode in ("loop", "gather"):
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
    loop = float(summary["loop"]["seconds_median"])
    gather = float(summary["gather"]["seconds_median"])
    summary["gather_vs_loop_percent"] = 100.0 * (loop / gather - 1.0)
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
