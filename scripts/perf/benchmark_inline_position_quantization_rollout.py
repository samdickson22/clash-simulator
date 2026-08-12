#!/usr/bin/env python3
"""Benchmark exact inline position quantization in stationary rollouts."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time

import numpy as np
import torch
from benchmark_deployment_blocker_guard_oracle import _paired_gain_summary
from benchmark_stationary_rollout import _digest_rollout

from clasher import entities as entities_module
from clasher.entities import Entity
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import StrategyBot
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import collect_rollout_stationary_opponents

_INLINE_QUANTIZE_POSITION = Entity.quantize_logic_position


def _quantize_position_reference(self: Entity) -> None:
    self.position.x = entities_module.logic_units_to_tiles(
        entities_module.tiles_to_logic_units(self.position.x)
    )
    self.position.y = entities_module.logic_units_to_tiles(
        entities_module.tiles_to_logic_units(self.position.y)
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload", choices=("random", "strategy"), required=True)
    parser.add_argument("--strategy", default="balanced")
    parser.add_argument("--seed", type=int, default=2301)
    parser.add_argument("--num-envs", type=int, default=4)
    parser.add_argument("--rollout-steps", type=int, default=24)
    parser.add_argument("--repetitions", type=int, default=11)
    parser.add_argument("--warmup-steps", type=int, default=4)
    parser.add_argument("--torch-threads", type=int, default=1)
    parser.add_argument("--max-ticks", type=int, default=2048)
    parser.add_argument(
        "--engine-fast-path",
        choices=("off", "shadow", "on"),
        default="on",
    )
    parser.add_argument("--reward-profile", default="defense-v2")
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

    def run_once(mode: str, steps: int) -> dict[str, object]:
        Entity.quantize_logic_position = (
            _INLINE_QUANTIZE_POSITION
            if mode == "inline"
            else _quantize_position_reference
        )
        torch.manual_seed(args.seed + 99)
        envs = [
            SelfPlayBattleEnv(
                seed=args.seed + index,
                max_ticks=args.max_ticks,
                engine_fast_path=args.engine_fast_path,
                reward_profile=args.reward_profile,
            )
            for index in range(args.num_envs)
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
            opponent_bot=(
                StrategyBot(args.strategy)
                if args.workload == "strategy"
                else None
            ),
        )
        elapsed = time.perf_counter() - started
        metrics = [env.fast_path_metrics() for env in envs]
        return {
            "mode": mode,
            "seconds": elapsed,
            "decisions_per_second": args.num_envs * steps / elapsed,
            "sha256": _digest_rollout(result[0], envs),
            "mask_shadow_checks": sum(
                int(metric["mask_shadow_checks"]) for metric in metrics
            ),
            "mask_shadow_mismatches": sum(
                int(metric["mask_shadow_mismatches"]) for metric in metrics
            ),
        }

    try:
        for mode in ("helpers", "inline"):
            run_once(mode, args.warmup_steps)
        rows = []
        for repetition in range(args.repetitions):
            order = (
                ("helpers", "inline")
                if repetition % 2 == 0
                else ("inline", "helpers")
            )
            for mode in order:
                row = run_once(mode, args.rollout_steps)
                row["repetition"] = repetition
                rows.append(row)
    finally:
        Entity.quantize_logic_position = _INLINE_QUANTIZE_POSITION

    summary: dict[str, object] = {}
    for mode in ("helpers", "inline"):
        selected = [row for row in rows if row["mode"] == mode]
        summary[mode] = {
            "seconds_median": statistics.median(
                float(row["seconds"]) for row in selected
            ),
            "decisions_per_second_median": statistics.median(
                float(row["decisions_per_second"]) for row in selected
            ),
            "hashes": sorted({str(row["sha256"]) for row in selected}),
            "mask_shadow_checks": sum(
                int(row["mask_shadow_checks"]) for row in selected
            ),
            "mask_shadow_mismatches": sum(
                int(row["mask_shadow_mismatches"]) for row in selected
            ),
        }
    helpers = float(summary["helpers"]["seconds_median"])  # type: ignore[index]
    inline = float(summary["inline"]["seconds_median"])  # type: ignore[index]
    summary["inline_vs_helpers_percent"] = 100.0 * (helpers / inline - 1.0)
    summary["paired_inline_vs_helpers_percent"] = _paired_gain_summary(
        rows,
        "helpers",
        "inline",
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
