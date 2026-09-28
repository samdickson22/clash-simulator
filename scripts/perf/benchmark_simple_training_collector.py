#!/usr/bin/env python3
"""Benchmark the real recurrent Simple-PyTorch PPO collector by capacity."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.simple_pytorch_backend import (
    SimplePytorchTrainingCollector,
    load_current_client_typed_vocabulary,
)
from clasher.rl.structured_obs import StructuredObservationBuilder


@dataclass(frozen=True)
class Trial:
    repetition: int
    elapsed_seconds: float
    actor_decisions: int
    actor_decisions_per_second: float
    transition_digest: str
    execution_mode: str
    max_entities: int
    max_effects: int


def summarize(trials: list[Trial]) -> dict[str, float]:
    if not trials:
        raise ValueError("at least one trial is required")
    rates = [trial.actor_decisions_per_second for trial in trials]
    return {
        "median_actor_decisions_per_second": statistics.median(rates),
        "minimum_actor_decisions_per_second": min(rates),
        "maximum_actor_decisions_per_second": max(rates),
    }


def _synchronize(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    elif device.type == "mps":
        torch.mps.synchronize()


def _digest(arrays: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    for name in ("actions", "action_masks", "rewards", "dones"):
        value = np.ascontiguousarray(arrays[name])
        digest.update(name.encode("ascii"))
        digest.update(value.dtype.str.encode("ascii"))
        digest.update(repr(value.shape).encode("ascii"))
        digest.update(value.tobytes())
    return digest.hexdigest()


def _build_collector(
    args: argparse.Namespace,
) -> tuple[SimplePytorchTrainingCollector, ClasherPolicy, torch.device]:
    device = torch.device(args.device)
    torch.manual_seed(args.seed)
    vocabulary = load_current_client_typed_vocabulary(args.typed_vocabulary_path)
    builder = StructuredObservationBuilder(
        decks_path=args.decks_path,
        token_names=vocabulary.token_names,
        max_entities=args.max_entities,
        card_semantics_version=args.card_semantics_version,
        canonical_lane_globals=True,
    )
    config = PolicyConfig(
        num_tokens=builder.spec.num_tokens,
        max_entities=args.max_entities,
        card_semantics_version=args.card_semantics_version,
        canonical_lane_globals=True,
        d_model=args.d_model,
        num_heads=args.num_heads,
        actor_layers=args.actor_layers,
        critic_layers=args.critic_layers,
        memory_size=args.memory_size,
        dropout=0.0,
    )
    model = ClasherPolicy(config, builder.card_stat_features).to(device).eval()
    collector = SimplePytorchTrainingCollector(
        model=model,
        builder=builder,
        batch_size=args.batch_size,
        device=device,
        decision_interval=args.decision_interval,
        gamma=0.995,
        supported_decks_path=args.supported_decks_path,
        typed_vocabulary_path=args.typed_vocabulary_path,
        mirror_match=False,
        max_effects=args.max_effects,
    )
    return collector, model, device


def _run_trial(args: argparse.Namespace, repetition: int) -> Trial:
    collector, model, device = _build_collector(args)
    state = model.initial_state(args.batch_size * 2, device=device)
    if args.warmup_steps:
        _warmup, state, _actions, _rewards, _starts = collector.collect(
            args.warmup_steps, state
        )
    _synchronize(device)
    started = time.perf_counter()
    arrays, _state, _actions, _rewards, _starts = collector.collect(
        args.rollout_steps, state
    )
    _synchronize(device)
    elapsed = time.perf_counter() - started
    actor_decisions = args.batch_size * 2 * args.rollout_steps
    return Trial(
        repetition=repetition,
        elapsed_seconds=elapsed,
        actor_decisions=actor_decisions,
        actor_decisions_per_second=actor_decisions / elapsed,
        transition_digest=_digest(arrays),
        execution_mode=collector.metadata.execution_mode,
        max_entities=args.max_entities,
        max_effects=args.max_effects,
    )


def benchmark(args: argparse.Namespace) -> dict[str, Any]:
    if min(
        args.batch_size,
        args.rollout_steps,
        args.repetitions,
        args.max_entities,
        args.max_effects,
    ) < 1 or args.warmup_steps < 0:
        raise ValueError("benchmark sizes must be positive and warmup non-negative")
    trials = [_run_trial(args, repetition) for repetition in range(args.repetitions)]
    digests = {trial.transition_digest for trial in trials}
    if len(digests) != 1:
        raise RuntimeError("collector benchmark replay is nondeterministic")
    return {
        "schema_version": 1,
        "scope": "real recurrent Simple-PyTorch collector including PPO CPU handoff",
        "device": args.device,
        "seed": args.seed,
        "batch_size": args.batch_size,
        "rollout_steps": args.rollout_steps,
        "warmup_steps": args.warmup_steps,
        "decision_interval": args.decision_interval,
        "repetitions": args.repetitions,
        "model": {
            "d_model": args.d_model,
            "num_heads": args.num_heads,
            "actor_layers": args.actor_layers,
            "critic_layers": args.critic_layers,
            "memory_size": args.memory_size,
        },
        "capacity": {
            "max_entities": args.max_entities,
            "max_effects": args.max_effects,
        },
        "summary": summarize(trials),
        "trials": [asdict(trial) for trial in trials],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("mps", "cuda"), required=True)
    parser.add_argument("--seed", type=int, default=202_608_287)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--warmup-steps", type=int, default=1)
    parser.add_argument("--rollout-steps", type=int, default=8)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--max-entities", type=int, default=48)
    parser.add_argument("--max-effects", type=int, default=64)
    parser.add_argument("--d-model", type=int, default=128)
    parser.add_argument("--num-heads", type=int, default=4)
    parser.add_argument("--actor-layers", type=int, default=4)
    parser.add_argument("--critic-layers", type=int, default=2)
    parser.add_argument("--memory-size", type=int, default=256)
    parser.add_argument("--card-semantics-version", type=int, default=1)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument(
        "--supported-decks-path",
        default="training_decks/simple_gym_supported_v1.json",
    )
    parser.add_argument(
        "--typed-vocabulary-path",
        default="reports/current_client_youtube_stable_vocabulary_v1.json",
    )
    parser.add_argument("--out", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = benchmark(args)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out is None:
        print(encoded, end="")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
