#!/usr/bin/env python3
"""Benchmark exact BattleState cloning and the fixed-depth oracle."""

from __future__ import annotations

import argparse
import copy
import json
import random
import statistics
import time

from clasher.battle import BattleState
from clasher.rl.oracle_planner import FixedDepthThompsonOracle


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("deepcopy", "clone"), required=True)
    parser.add_argument("--seed", type=int, default=2301)
    parser.add_argument("--oracle-seed", type=int, default=901)
    parser.add_argument("--clone-repetitions", type=int, default=5)
    parser.add_argument("--plan-depth", type=int, default=2)
    parser.add_argument("--simulations", type=int, default=4)
    parser.add_argument("--action-samples", type=int, default=16)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--reward-profile", default="defense-v2")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    battle = BattleState(rng=random.Random(args.seed), fast_path=True)
    for _ in range(args.decision_interval):
        battle.step()

    clone_times = []
    for _ in range(args.clone_repetitions):
        started = time.perf_counter()
        if args.mode == "deepcopy":
            copy.deepcopy(battle)
        else:
            battle.clone()
        clone_times.append(time.perf_counter() - started)

    original_clone = BattleState.clone
    if args.mode == "deepcopy":
        BattleState.clone = lambda self: copy.deepcopy(self)
    try:
        planner = FixedDepthThompsonOracle(
            decision_interval_ticks=args.decision_interval,
            plan_depth=args.plan_depth,
            num_simulations=args.simulations,
            rollout_action_samples=args.action_samples,
            seed=args.oracle_seed,
            reward_profile=args.reward_profile,
        )
        started = time.perf_counter()
        actions = planner.select_actions(battle)
        oracle_time = time.perf_counter() - started
    finally:
        BattleState.clone = original_clone

    print(
        json.dumps(
            {
                "mode": args.mode,
                "seed": args.seed,
                "oracle_seed": args.oracle_seed,
                "clone_repetitions": args.clone_repetitions,
                "clone_elapsed_s": clone_times,
                "clone_median_elapsed_s": statistics.median(clone_times),
                "oracle_elapsed_s": oracle_time,
                "actions": actions,
                "plan_depth": args.plan_depth,
                "simulations": args.simulations,
                "action_samples": args.action_samples,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
