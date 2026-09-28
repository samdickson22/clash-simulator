#!/usr/bin/env python3
"""Benchmark recurrent rollouts against stationary random/strategy opponents."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time

import numpy as np
import torch

from clasher.rl import train_recurrent as train_recurrent_module
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
    parser.add_argument("--rollout-steps", type=int, default=12)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--warmup-steps", type=int, default=2)
    parser.add_argument("--torch-threads", type=int, default=2)
    parser.add_argument("--max-ticks", type=int, default=2048)
    parser.add_argument(
        "--engine-fast-path", choices=("off", "shadow", "on"), default="on"
    )
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--compare-inference-mode", action="store_true")
    parser.add_argument("--compare-entity-trim", action="store_true")
    parser.add_argument(
        "--architecture",
        choices=("attention", "pooled", "wide-pooled"),
        default="attention",
    )
    return parser.parse_args()


def _digest_rollout(rollout: object, envs: list[SelfPlayBattleEnv]) -> str:
    hasher = hashlib.sha256()
    for name, value in vars(rollout).items():
        if isinstance(value, np.ndarray):
            hasher.update(name.encode("utf-8"))
            hasher.update(np.ascontiguousarray(value).tobytes())
        else:
            hasher.update(f"{name}={value}".encode())
    for env in envs:
        assert env.battle is not None
        hasher.update(
            f"{env.battle.tick}:{env.battle.winner}:{len(env.battle.entities)}".encode()
        )
    return hasher.hexdigest()


def _digest_behavior(rollout: object, envs: list[SelfPlayBattleEnv]) -> str:
    hasher = hashlib.sha256()
    for name in ("actions", "rewards", "dones"):
        hasher.update(np.ascontiguousarray(getattr(rollout, name)).tobytes())
    for env in envs:
        assert env.battle is not None
        hasher.update(
            f"{env.battle.tick}:{env.battle.winner}:{len(env.battle.entities)}".encode()
        )
    return hasher.hexdigest()


def main() -> None:
    args = _parse_args()
    torch.set_num_threads(args.torch_threads)
    builder = StructuredObservationBuilder(
        decks_path=args.decks_path,
        max_entities=128,
    )
    pooled = args.architecture in {"pooled", "wide-pooled"}
    wide = args.architecture == "wide-pooled"
    config = PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=builder.spec.max_entities,
        d_model=272 if wide else (192 if pooled else 128),
        num_heads=8 if wide else (6 if pooled else 4),
        actor_layers=5 if pooled else 4,
        critic_layers=3 if pooled else 2,
        memory_size=544 if wide else (384 if pooled else 256),
        encoder_kind="deepsets" if pooled else "attention",
        decoder_kind="global" if pooled else "attention",
    )
    torch.manual_seed(91)
    model = ClasherPolicy(config, builder.card_stat_features)
    model.eval()

    def run_once(steps: int, variant: str = "configured") -> dict[str, float | str]:
        if variant != "configured":
            if args.compare_inference_mode:
                train_recurrent_module._USE_ROLLOUT_INFERENCE_MODE = (
                    variant == "inference"
                )
            if args.compare_entity_trim:
                train_recurrent_module._USE_TRIMMED_ROLLOUT_ENTITY_PADDING = (
                    variant == "trimmed"
                )
        torch.manual_seed(args.seed + 99)
        envs = [
            SelfPlayBattleEnv(
                seed=args.seed + index,
                max_ticks=args.max_ticks,
                engine_fast_path=args.engine_fast_path,
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
            "variant": variant,
            "elapsed_s": elapsed,
            "decisions_per_s": args.num_envs * steps / elapsed,
            "sha256": _digest_rollout(result[0], envs),
            "behavior_sha256": _digest_behavior(result[0], envs),
        }

    if args.compare_inference_mode and args.compare_entity_trim:
        raise ValueError("select only one comparison")
    if args.compare_inference_mode:
        variants = ("no_grad", "inference")
    elif args.compare_entity_trim:
        variants = ("dense", "trimmed")
    else:
        variants = ("configured",)
    if args.warmup_steps:
        for variant in variants:
            run_once(args.warmup_steps, variant)
    rows = []
    for repetition in range(args.repetitions):
        order = variants if repetition % 2 == 0 else tuple(reversed(variants))
        for variant in order:
            row = run_once(args.rollout_steps, variant)
            row["repetition"] = repetition
            rows.append(row)
    elapsed = [float(row["elapsed_s"]) for row in rows]
    rates = [float(row["decisions_per_s"]) for row in rows]
    print(
        json.dumps(
            {
                "workload": args.workload,
                "strategy": args.strategy if args.workload == "strategy" else None,
                "seed": args.seed,
                "num_envs": args.num_envs,
                "rollout_steps": args.rollout_steps,
                "repetitions": args.repetitions,
                "torch_threads": args.torch_threads,
                "engine_fast_path": args.engine_fast_path,
                "elapsed_s": elapsed,
                "median_elapsed_s": statistics.median(elapsed),
                "decisions_per_s": rates,
                "median_decisions_per_s": statistics.median(rates),
                "variant_summaries": {
                    variant: {
                        "median_elapsed_s": statistics.median(
                            float(row["elapsed_s"])
                            for row in rows
                            if row["variant"] == variant
                        ),
                        "median_decisions_per_s": statistics.median(
                            float(row["decisions_per_s"])
                            for row in rows
                            if row["variant"] == variant
                        ),
                        "hashes": sorted(
                            {
                                str(row["sha256"])
                                for row in rows
                                if row["variant"] == variant
                            }
                        ),
                        "behavior_hashes": sorted(
                            {
                                str(row["behavior_sha256"])
                                for row in rows
                                if row["variant"] == variant
                            }
                        ),
                    }
                    for variant in variants
                },
                "hashes": sorted({str(row["sha256"]) for row in rows}),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
