#!/usr/bin/env python3
"""Benchmark rollout entity trimming through persistent actor processes."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time

import numpy as np
import torch

from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.parallel_rollout import (
    ActorWorkerConfig,
    OpponentSpec,
    ParallelRolloutCollector,
)
from clasher.rl.structured_obs import StructuredObservationBuilder


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload", choices=("random", "strategy"), required=True)
    parser.add_argument("--strategy", default="balanced")
    parser.add_argument("--architecture", choices=("attention", "pooled"), default="attention")
    parser.add_argument("--seed", type=int, default=3531)
    parser.add_argument("--num-envs", type=int, default=8)
    parser.add_argument("--actor-workers", type=int, default=4)
    parser.add_argument("--rollout-steps", type=int, default=32)
    parser.add_argument("--repetitions", type=int, default=7)
    parser.add_argument("--warmup-steps", type=int, default=8)
    return parser.parse_args()


def _digest_arrays(batch: object, fields: tuple[str, ...]) -> str:
    hasher = hashlib.sha256()
    for name in fields:
        value = np.ascontiguousarray(getattr(batch, name))
        hasher.update(name.encode())
        hasher.update(value.tobytes())
    return hasher.hexdigest()


def main() -> None:
    args = _parse_args()
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    pooled = args.architecture == "pooled"
    config = PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=builder.spec.max_entities,
        d_model=192 if pooled else 128,
        num_heads=6 if pooled else 4,
        actor_layers=5 if pooled else 4,
        critic_layers=3 if pooled else 2,
        memory_size=384 if pooled else 256,
        encoder_kind="deepsets" if pooled else "attention",
        decoder_kind="global" if pooled else "attention",
    )
    torch.manual_seed(91)
    model = ClasherPolicy(config, builder.card_stat_features).eval()
    opponent = (
        OpponentSpec(kind="random")
        if args.workload == "random"
        else OpponentSpec(kind="strategy", strategy=args.strategy)
    )

    def actor_config(trimmed: bool) -> ActorWorkerConfig:
        return ActorWorkerConfig(
            decks_path="decks.json",
            token_names=builder.token_names,
            model_config=config.to_dict(),
            decision_interval=8,
            max_ticks=2048,
            mirror_match=False,
            opponent_mode=args.workload,
            opponent_pool=(opponent,),
            engine_fast_path="on",
            quiet_engine=True,
            base_seed=args.seed,
            torch_threads=1,
            trim_rollout_entity_padding=trimmed,
        )

    collectors = {
        name: ParallelRolloutCollector(
            num_workers=args.actor_workers,
            num_envs=args.num_envs,
            config=actor_config(trimmed),
        )
        for name, trimmed in (("dense", False), ("trimmed", True))
    }
    try:
        for collector in collectors.values():
            collector.collect(model=model, rollout_steps=args.warmup_steps, policy_version=0)
        rows = []
        for repetition in range(args.repetitions):
            order = ("dense", "trimmed") if repetition % 2 == 0 else ("trimmed", "dense")
            for variant in order:
                started = time.perf_counter()
                batch = collectors[variant].collect(
                    model=model,
                    rollout_steps=args.rollout_steps,
                    policy_version=repetition + 1,
                )
                elapsed = time.perf_counter() - started
                rows.append(
                    {
                        "repetition": repetition,
                        "variant": variant,
                        "seconds": elapsed,
                        "decisions_per_second": batch.transitions / elapsed,
                        "behavior_sha256": _digest_arrays(
                            batch, ("actions", "rewards", "dones")
                        ),
                        "full_sha256": _digest_arrays(
                            batch,
                            (
                                "actions",
                                "old_log_probs",
                                "old_values",
                                "rewards",
                                "dones",
                                "bootstrap_values",
                            ),
                        ),
                    }
                )
    finally:
        for collector in collectors.values():
            collector.close()

    summary = {}
    for variant in ("dense", "trimmed"):
        selected = [row for row in rows if row["variant"] == variant]
        summary[variant] = {
            "median_seconds": statistics.median(float(row["seconds"]) for row in selected),
            "median_decisions_per_second": statistics.median(
                float(row["decisions_per_second"]) for row in selected
            ),
            "behavior_hashes": [str(row["behavior_sha256"]) for row in selected],
            "full_hashes": [str(row["full_sha256"]) for row in selected],
        }
    print(json.dumps({"config": vars(args), "rows": rows, "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
