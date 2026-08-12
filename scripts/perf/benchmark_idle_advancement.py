#!/usr/bin/env python3
"""Matched bounded benchmark for exact tower-only idle advancement."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time

from benchmark_inline_position_quantization_rollout import _paired_gain_summary

from clasher import battle as battle_module
from clasher.rl import selfplay_env as selfplay_env_module
from clasher.rl.selfplay_env import SelfPlayBattleEnv


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=9067)
    parser.add_argument("--decisions", type=int, default=32)
    parser.add_argument("--repetitions", type=int, default=21)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=9090)
    parser.add_argument(
        "--engine-fast-path",
        choices=("off", "shadow", "on"),
        default="on",
    )
    return parser.parse_args()


def _run(args: argparse.Namespace, mode: str) -> dict[str, object]:
    optimized = mode == "sparse"
    battle_module._USE_SPARSE_IDLE_WIN_CHECKS = optimized
    selfplay_env_module._USE_TRUSTED_IDLE_ELIGIBILITY = optimized
    env = SelfPlayBattleEnv(
        seed=args.seed,
        decision_interval_ticks=args.decision_interval,
        max_ticks=args.max_ticks,
        engine_fast_path=args.engine_fast_path,
        reward_profile="defense-v2",
    )
    env.reset(seed=args.seed)
    no_op = env.action_space.no_op_action
    hasher = hashlib.sha256()
    started = time.perf_counter()
    for _ in range(args.decisions):
        masks = {player: env.get_action_mask(player) for player in (0, 1)}
        rewards, done, info = env.step(
            {0: no_op, 1: no_op},
            pre_action_masks=masks,
        )
        assert env.battle is not None
        hasher.update(
            repr(
                (
                    env.battle.tick,
                    env.battle.time,
                    env.battle.rng.getstate(),
                    rewards,
                    done,
                    info,
                    tuple(
                        (
                            player.elixir,
                            tuple(player.hand),
                            tuple(player.cycle_queue),
                            player.next_card_refill_cooldown_ms,
                        )
                        for player in env.battle.players
                    ),
                    tuple(
                        (entity.id, entity.last_attack_time)
                        for entity in env.battle.entities.values()
                    ),
                )
            ).encode()
        )
    elapsed = time.perf_counter() - started
    metrics = env.fast_path_metrics()
    return {
        "mode": mode,
        "seconds": elapsed,
        "decisions_per_second": args.decisions / elapsed,
        "sha256": hasher.hexdigest(),
        "mask_shadow_checks": int(metrics["mask_shadow_checks"]),
        "mask_shadow_mismatches": int(metrics["mask_shadow_mismatches"]),
    }


def main() -> None:
    args = _parse_args()
    original_sparse = battle_module._USE_SPARSE_IDLE_WIN_CHECKS
    original_trusted = selfplay_env_module._USE_TRUSTED_IDLE_ELIGIBILITY
    try:
        _run(args, "per-tick")
        _run(args, "sparse")
        rows = []
        for repetition in range(args.repetitions):
            order = (
                ("per-tick", "sparse")
                if repetition % 2 == 0
                else ("sparse", "per-tick")
            )
            for mode in order:
                row = _run(args, mode)
                row["repetition"] = repetition
                rows.append(row)
    finally:
        battle_module._USE_SPARSE_IDLE_WIN_CHECKS = original_sparse
        selfplay_env_module._USE_TRUSTED_IDLE_ELIGIBILITY = original_trusted

    summary: dict[str, object] = {}
    for mode in ("per-tick", "sparse"):
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
    summary["sparse_vs_per_tick_percent"] = 100.0 * (
        float(summary["per-tick"]["seconds_median"])  # type: ignore[index]
        / float(summary["sparse"]["seconds_median"])  # type: ignore[index]
        - 1.0
    )
    summary["paired_sparse_vs_per_tick_percent"] = _paired_gain_summary(
        rows,
        "per-tick",
        "sparse",
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
