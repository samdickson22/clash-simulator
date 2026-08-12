#!/usr/bin/env python3
"""Benchmark exact scalar entity range clipping on one fixed battle state."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time

import numpy as np

from clasher.rl import structured_obs as structured_obs_module
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.structured_obs import StructuredObservationBuilder


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=2301)
    parser.add_argument("--state-decisions", type=int, default=24)
    parser.add_argument("--builds", type=int, default=512)
    parser.add_argument("--repetitions", type=int, default=11)
    parser.add_argument("--decks-path", default="decks.json")
    return parser.parse_args()


def _fixed_state(args: argparse.Namespace) -> SelfPlayBattleEnv:
    env = SelfPlayBattleEnv(
        seed=args.seed,
        max_ticks=4096,
        engine_fast_path="on",
    )
    env.reset(seed=args.seed)
    action_rng = np.random.default_rng(args.seed + 1_000_003)
    for _ in range(args.state_decisions):
        masks = {player_id: env.get_action_mask(player_id) for player_id in (0, 1)}
        actions = {
            player_id: int(action_rng.choice(np.flatnonzero(masks[player_id])))
            for player_id in (0, 1)
        }
        _, done, _ = env.step(actions, pre_action_masks=masks)
        if done:
            break
    return env


def _observation_digest(observation: object) -> str:
    hasher = hashlib.sha256()
    for name, value in vars(observation).items():
        hasher.update(name.encode())
        hasher.update(np.ascontiguousarray(value).tobytes())
    return hasher.hexdigest()


def main() -> None:
    args = _parse_args()
    env = _fixed_state(args)
    assert env.battle is not None
    builder = StructuredObservationBuilder(
        decks_path=args.decks_path,
        max_entities=128,
    )

    def run_once(variant: str, builds: int) -> dict[str, float | str]:
        structured_obs_module._range_clip = (
            structured_obs_module._range_clip_numpy
            if variant == "numpy"
            else structured_obs_module._range_clip_scalar
        )
        digest = _observation_digest(builder.build(env.battle, 0))
        started = time.perf_counter()
        for build_index in range(builds):
            builder.build(env.battle, build_index % 2)
        elapsed = time.perf_counter() - started
        return {
            "variant": variant,
            "seconds": elapsed,
            "builds_per_second": builds / elapsed,
            "sha256": digest,
        }

    for variant in ("numpy", "scalar"):
        run_once(variant, 8)
    rows = []
    for repetition in range(args.repetitions):
        order = (
            ("numpy", "scalar")
            if repetition % 2 == 0
            else ("scalar", "numpy")
        )
        for variant in order:
            row = run_once(variant, args.builds)
            row["repetition"] = repetition
            rows.append(row)

    summary = {}
    for variant in ("numpy", "scalar"):
        selected = [row for row in rows if row["variant"] == variant]
        seconds = [float(row["seconds"]) for row in selected]
        rates = [float(row["builds_per_second"]) for row in selected]
        summary[variant] = {
            "seconds_median": statistics.median(seconds),
            "seconds_mean": statistics.mean(seconds),
            "seconds_stdev": statistics.stdev(seconds),
            "builds_per_second_median": statistics.median(rates),
            "hashes": sorted({str(row["sha256"]) for row in selected}),
        }
    numpy_seconds = float(summary["numpy"]["seconds_median"])
    scalar_seconds = float(summary["scalar"]["seconds_median"])
    summary["scalar_vs_numpy_percent"] = 100.0 * (
        numpy_seconds / scalar_seconds - 1.0
    )
    print(
        json.dumps(
            {"config": vars(args), "rows": rows, "summary": summary},
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
