#!/usr/bin/env python3
"""Matched bounded benchmark for scalar oracle leaf backup."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import time

import numpy as np

from clasher.rl.oracle_direct_path import DirectPathFixedDepthThompsonOracle
from clasher.rl.oracle_sampling import sample_action_subset
from clasher.rl.reward_model import DEFENSE_V2
from clasher.rl.selfplay_env import SelfPlayBattleEnv


class _ScalarLeafOracle(DirectPathFixedDepthThompsonOracle):
    def _sample_actions(self, legal: np.ndarray) -> np.ndarray:
        return sample_action_subset(
            legal,
            sample_limit=self.rollout_action_samples,
            no_op_action=self.action_space.no_op_action,
            rng=self.rng,
        )


class _MappingLeafOracle(_ScalarLeafOracle):
    def _evaluate_state_prob_p0(self, battle) -> float:
        return self._evaluate_state_prob(battle)[0]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=2301)
    parser.add_argument("--planner-seed", type=int, default=901)
    parser.add_argument("--states", type=int, default=3)
    parser.add_argument("--state-stride", type=int, default=4)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--planner-depth", type=int, default=6)
    parser.add_argument("--planner-simulations", type=int, default=32)
    parser.add_argument("--planner-action-samples", type=int, default=64)
    parser.add_argument(
        "--engine-fast-path",
        choices=("off", "shadow", "on"),
        default="on",
    )
    return parser.parse_args()


def _snapshots(args: argparse.Namespace):
    env = SelfPlayBattleEnv(
        seed=args.seed,
        decision_interval_ticks=args.decision_interval,
        max_ticks=4096,
        engine_fast_path=args.engine_fast_path,
        reward_profile=DEFENSE_V2,
    )
    env.reset(seed=args.seed)
    action_rng = np.random.default_rng(args.seed + 1_000_003)
    snapshots = []
    for decision in range((args.states - 1) * args.state_stride + 1):
        assert env.battle is not None
        if decision % args.state_stride == 0:
            snapshots.append(env.battle.clone())
        if len(snapshots) == args.states:
            break
        masks = {player_id: env.get_action_mask(player_id) for player_id in (0, 1)}
        actions = {
            player_id: int(action_rng.choice(np.flatnonzero(masks[player_id])))
            for player_id in (0, 1)
        }
        env.step(actions, pre_action_masks=masks)
    return snapshots


def _run_variant(
    args: argparse.Namespace,
    snapshots,
    variant: str,
) -> dict[str, float | str]:
    planner_type = _MappingLeafOracle if variant == "mapping" else _ScalarLeafOracle
    planner = planner_type(
        decision_interval_ticks=args.decision_interval,
        plan_depth=args.planner_depth,
        num_simulations=args.planner_simulations,
        rollout_action_samples=args.planner_action_samples,
        seed=args.planner_seed,
        reward_profile=DEFENSE_V2,
        stable_root_candidates=True,
    )
    hasher = hashlib.sha256()
    started = time.perf_counter()
    for battle in snapshots:
        before = planner._state_key(battle)
        actions = planner.select_actions(battle)
        after = planner._state_key(battle)
        hasher.update(repr((before, actions, after)).encode())
    elapsed = time.perf_counter() - started
    hasher.update(repr(planner.rng.bit_generator.state).encode())
    return {
        "variant": variant,
        "seconds": elapsed,
        "decisions_per_second": len(snapshots) / elapsed,
        "sha256": hasher.hexdigest(),
    }


def main() -> None:
    args = _parse_args()
    snapshots = _snapshots(args)
    _run_variant(args, snapshots[:1], "mapping")
    _run_variant(args, snapshots[:1], "scalar")
    rows = []
    for repetition in range(args.repetitions):
        order = ("mapping", "scalar") if repetition % 2 == 0 else ("scalar", "mapping")
        for variant in order:
            row = _run_variant(args, snapshots, variant)
            row["repetition"] = repetition
            rows.append(row)

    summary = {}
    for variant in ("mapping", "scalar"):
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
    mapping_seconds = float(summary["mapping"]["seconds_median"])
    scalar_seconds = float(summary["scalar"]["seconds_median"])
    summary["scalar_vs_mapping_percent"] = 100.0 * (
        mapping_seconds / scalar_seconds - 1.0
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
