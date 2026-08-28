#!/usr/bin/env python3
"""Benchmark the real learner-only recurrent Simple-PyTorch collector."""

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
from clasher.rl.strategy_bots import STRATEGY_NAMES
from clasher.rl.structured_obs import StructuredObservationBuilder


@dataclass(frozen=True)
class Trial:
    repetition: int
    elapsed_seconds: float
    learner_transitions: int
    learner_transitions_per_second: float
    transition_digest: str
    peak_allocated_bytes: int
    peak_reserved_bytes: int


def _synchronize(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    elif device.type == "mps":
        torch.mps.synchronize()


def _digest(arrays: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    for name in (
        "entity_ids",
        "global_features",
        "action_masks",
        "actions",
        "rewards",
        "dones",
    ):
        value = np.ascontiguousarray(arrays[name])
        digest.update(name.encode("ascii"))
        digest.update(value.dtype.str.encode("ascii"))
        digest.update(repr(value.shape).encode("ascii"))
        digest.update(value.tobytes())
    return digest.hexdigest()


def _load_opponent(
    args: argparse.Namespace,
    *,
    config: PolicyConfig,
    builder: StructuredObservationBuilder,
    device: torch.device,
) -> tuple[ClasherPolicy | None, str | None]:
    if args.opponent_mode != "checkpoint":
        if args.opponent_checkpoint is not None:
            raise ValueError("--opponent-checkpoint requires checkpoint mode")
        return None, None
    if args.opponent_checkpoint is None:
        raise ValueError("checkpoint mode requires --opponent-checkpoint")
    path = args.opponent_checkpoint
    raw = path.read_bytes()
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if int(payload.get("format_version", 0)) != 2:
        raise ValueError("opponent checkpoint must use format version 2")
    if tuple(payload.get("token_names", ())) != tuple(builder.token_names):
        raise ValueError("opponent checkpoint typed vocabulary differs")
    opponent_config = PolicyConfig.from_dict(payload["model_config"])
    comparable = (
        "num_tokens",
        "entity_feature_size",
        "actor_global_size",
        "canonical_lane_globals",
        "d_model",
        "num_heads",
        "actor_layers",
        "critic_layers",
        "memory_size",
    )
    if any(
        getattr(opponent_config, name) != getattr(config, name) for name in comparable
    ):
        raise ValueError("opponent checkpoint policy shape differs")
    opponent = ClasherPolicy(opponent_config, builder.card_stat_features).to(device)
    opponent.load_state_dict(payload["model_state_dict"], strict=True)
    opponent.eval().requires_grad_(False)
    return opponent, hashlib.sha256(raw).hexdigest()


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
    opponent, opponent_sha256 = _load_opponent(
        args,
        config=config,
        builder=builder,
        device=device,
    )
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
        opponent_mode=args.opponent_mode,
        opponent_model=opponent,
        opponent_checkpoint_sha256=opponent_sha256,
        opponent_strategy=(
            args.opponent_strategy if args.opponent_mode == "strategy" else None
        ),
        opponent_strategy_schedule=(
            tuple(args.league_strategy) if args.opponent_mode == "league" else ()
        ),
        learner_deck_name=args.learner_deck,
        max_effects=args.max_effects,
    )
    metadata = collector.checkpoint_metadata()
    names = tuple(metadata["opponent_deck_names"])
    if any(names[index] != names[index + 1] for index in range(0, len(names) - 1, 2)):
        raise RuntimeError("seat-swapped rows do not preserve opponent deck identity")
    return collector, model, device


def _run_trial(args: argparse.Namespace, repetition: int) -> Trial:
    collector, model, device = _build_collector(args)
    state = model.initial_state(args.batch_size, device=device)
    if args.warmup_steps:
        _warmup, state, _actions, _rewards, _starts = collector.collect(
            args.warmup_steps,
            state,
        )
    _synchronize(device)
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    started = time.perf_counter()
    arrays, _state, _actions, _rewards, _starts = collector.collect(
        args.rollout_steps,
        state,
    )
    _synchronize(device)
    elapsed = time.perf_counter() - started
    transitions = args.batch_size * args.rollout_steps
    return Trial(
        repetition=repetition,
        elapsed_seconds=elapsed,
        learner_transitions=transitions,
        learner_transitions_per_second=transitions / elapsed,
        transition_digest=_digest(arrays),
        peak_allocated_bytes=(
            int(torch.cuda.max_memory_allocated(device)) if device.type == "cuda" else 0
        ),
        peak_reserved_bytes=(
            int(torch.cuda.max_memory_reserved(device)) if device.type == "cuda" else 0
        ),
    )


def benchmark(args: argparse.Namespace) -> dict[str, Any]:
    trials = [_run_trial(args, repetition) for repetition in range(args.repetitions)]
    digests = {trial.transition_digest for trial in trials}
    if len(digests) != 1:
        raise RuntimeError("asymmetric collector benchmark replay is nondeterministic")
    rates = [trial.learner_transitions_per_second for trial in trials]
    return {
        "schema_version": 1,
        "scope": "real learner-only recurrent collector including CPU handoff",
        "device": args.device,
        "seed": args.seed,
        "batch_size": args.batch_size,
        "rollout_steps": args.rollout_steps,
        "warmup_steps": args.warmup_steps,
        "decision_interval": args.decision_interval,
        "repetitions": args.repetitions,
        "opponent_mode": args.opponent_mode,
        "learner_deck": args.learner_deck,
        "capacity": {
            "max_entities": args.max_entities,
            "max_effects": args.max_effects,
        },
        "summary": {
            "median_learner_transitions_per_second": statistics.median(rates),
            "minimum_learner_transitions_per_second": min(rates),
            "maximum_learner_transitions_per_second": max(rates),
        },
        "trials": [asdict(trial) for trial in trials],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("mps", "cuda"), required=True)
    parser.add_argument("--seed", type=int, default=1_163_701)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--warmup-steps", type=int, default=2)
    parser.add_argument("--rollout-steps", type=int, default=48)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--max-entities", type=int, default=56)
    parser.add_argument("--max-effects", type=int, default=64)
    parser.add_argument("--d-model", type=int, default=128)
    parser.add_argument("--num-heads", type=int, default=4)
    parser.add_argument("--actor-layers", type=int, default=4)
    parser.add_argument("--critic-layers", type=int, default=2)
    parser.add_argument("--memory-size", type=int, default=256)
    parser.add_argument("--card-semantics-version", type=int, default=1)
    parser.add_argument("--learner-deck", default="Hog 2.6 Cycle")
    parser.add_argument(
        "--opponent-mode",
        choices=("random", "strategy", "league", "checkpoint"),
        default="league",
    )
    parser.add_argument("--opponent-strategy", choices=STRATEGY_NAMES)
    parser.add_argument(
        "--league-strategy",
        action="append",
        choices=STRATEGY_NAMES,
        default=[],
    )
    parser.add_argument("--opponent-checkpoint", type=Path)
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
    if args.opponent_mode == "strategy" and args.opponent_strategy is None:
        args.opponent_strategy = "balanced"
    if args.opponent_mode == "league" and not args.league_strategy:
        args.league_strategy = list(STRATEGY_NAMES)
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
