#!/usr/bin/env python3
"""Bounded absolute-throughput benchmark for projected resident self-play.

This benchmark does not compare against the scalar Python simulator and never
reports a speedup.  It times a fixed active window of resident Gym decisions,
requires zero fallback, and replays the same workload to prove its projected
transition digest is deterministic before publishing throughput.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

import torch

from clasher.battle import BattleState
from clasher.rl.deck_pool import load_deck_pool
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.policy_validation import PROJECTED_GYM_TRANSITION_PROFILE
from clasher.torch_sim.resident_selfplay import (
    ResidentGymTransitionInputs,
    ResidentSelfPlayStep,
    TensorResidentSelfPlay,
)
from clasher.torch_sim.runtime_state import (
    RESIDENT_EXECUTION_PROFILE_EXACT_DEBUG,
    RESIDENT_EXECUTION_PROFILE_GYM_FAST,
    RESIDENT_EXECUTION_PROFILES,
)


@dataclass(frozen=True)
class BenchmarkTrial:
    repetition: int
    elapsed_seconds: float
    decision_calls: int
    resident_rows: int
    actor_transitions: int
    requested_native_ticks: int
    native_ticks: int
    fallback_rows: int
    terminal_rows: int
    decision_calls_per_second: float
    resident_rows_per_second: float
    actor_transitions_per_second: float
    native_ticks_per_second: float
    peak_device_memory_bytes: int | None
    digest: str


def _battle(seed: int, decks: list[list[str]]) -> BattleState:
    rng = random.Random(seed)
    battle = BattleState(fast_path=False, rng=rng)
    for player in battle.players:
        deck = list(rng.choice(decks))
        rng.shuffle(deck)
        player.hand = cast(list[str | None], deck[:4])
        player.deck = list(deck)
        player.cycle_queue = deque(deck[4:])
        player.elixir = 5.0
    return battle


def _actions(mask: torch.Tensor, policy: str) -> torch.Tensor:
    batch, seats, action_count = mask.shape
    if policy == "noop":
        return torch.full(
            (batch, seats),
            NO_OP_ACTION,
            dtype=torch.int64,
            device=mask.device,
        )
    indices = torch.arange(action_count, dtype=torch.int64, device=mask.device)
    candidates = torch.where(
        mask & (indices != NO_OP_ACTION),
        indices,
        torch.full_like(indices, action_count),
    )
    selected = candidates.amin(dim=2)
    return torch.where(
        selected < action_count,
        selected,
        torch.full_like(selected, NO_OP_ACTION),
    )


def _update_digest(digest: hashlib._Hash, value: torch.Tensor) -> None:
    cpu = value.detach().contiguous().cpu()
    digest.update(str(cpu.dtype).encode())
    digest.update(str(tuple(cpu.shape)).encode())
    digest.update(cpu.numpy().tobytes())


def _synchronize(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def _step(
    bridge: TensorResidentSelfPlay,
    *,
    policy: str,
    previous_actions: torch.Tensor,
    previous_rewards: torch.Tensor,
    episode_starts: torch.Tensor,
) -> tuple[ResidentSelfPlayStep, torch.Tensor]:
    _, _, legal = bridge.observe()
    actions = _actions(legal, policy)
    result = bridge.step(
        actions,
        validation_inputs=ResidentGymTransitionInputs(
            previous_actions=previous_actions,
            previous_rewards=previous_rewards,
            episode_starts=episode_starts,
        ),
    )
    if result.validation is None:
        raise RuntimeError("projected Gym validation boundary is missing")
    return result, actions


def _run_trial(
    args: argparse.Namespace,
    *,
    repetition: int,
    decks: list[list[str]],
) -> tuple[BenchmarkTrial, str]:
    battles = [_battle(args.seed + row, decks) for row in range(args.batch_size)]
    bridge = TensorResidentSelfPlay.from_battles(
        battles,
        device=args.device,
        decision_interval_ticks=args.decision_interval,
        max_ticks=args.max_ticks,
        max_entities=args.max_entities,
        max_objects=args.max_objects,
        event_capacity=(
            1
            if getattr(args, "execution_profile", None)
            == RESIDENT_EXECUTION_PROFILE_GYM_FAST
            else 1_024
        ),
        execution_profile=getattr(
            args, "execution_profile", RESIDENT_EXECUTION_PROFILE_EXACT_DEBUG
        ),
        validation_profile=PROJECTED_GYM_TRANSITION_PROFILE,
    )
    shape = (args.batch_size, 2)
    previous_actions = torch.full(
        shape, NO_OP_ACTION, dtype=torch.int64, device=bridge.device
    )
    previous_rewards = torch.zeros(shape, dtype=torch.float32, device=bridge.device)
    episode_starts = torch.ones(shape, dtype=torch.bool, device=bridge.device)

    for _ in range(args.warmup_decisions):
        result, actions = _step(
            bridge,
            policy=args.policy,
            previous_actions=previous_actions,
            previous_rewards=previous_rewards,
            episode_starts=episode_starts,
        )
        previous_actions = actions.clone()
        previous_rewards = result.rewards.to(torch.float32).clone()
        episode_starts.zero_()
    _synchronize(bridge.device)
    if bridge.device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(bridge.device)

    snapshots: list[tuple[torch.Tensor, ...]] = []
    metadata_snapshots: list[tuple[torch.Tensor, torch.Tensor, int]] = []
    started = time.perf_counter()
    for _ in range(args.measured_decisions):
        result, actions = _step(
            bridge,
            policy=args.policy,
            previous_actions=previous_actions,
            previous_rewards=previous_rewards,
            episode_starts=episode_starts,
        )
        validation = result.validation
        assert validation is not None
        transition = validation.transition
        metadata = validation.metadata
        snapshots.append(
            (
                transition.actor.entity_ids.clone(),
                transition.actor.entity_features.clone(),
                transition.actor.entity_mask.clone(),
                transition.actor.hand_ids.clone(),
                transition.actor.global_features.clone(),
                result.action_masks.clone(),
                torch.as_tensor(transition.action_success).clone(),
                torch.as_tensor(transition.rewards).clone(),
                torch.as_tensor(transition.done).clone(),
                torch.as_tensor(transition.winner).clone(),
                actions.clone(),
            )
        )
        metadata_snapshots.append(
            (
                metadata.requested_native_ticks.clone(),
                metadata.native_ticks.clone(),
                len(metadata.fallback_rows),
            )
        )
        previous_actions = actions.clone()
        previous_rewards = result.rewards.to(torch.float32).clone()
        episode_starts.zero_()
    _synchronize(bridge.device)
    elapsed = time.perf_counter() - started

    requested_native_ticks = sum(
        int(requested.sum().item()) for requested, _, _ in metadata_snapshots
    )
    native_ticks = sum(
        int(native.sum().item()) for _, native, _ in metadata_snapshots
    )
    fallback_rows = sum(fallback for _, _, fallback in metadata_snapshots)
    terminal_rows = sum(
        int(snapshot[8].sum().item()) for snapshot in snapshots
    )
    if fallback_rows or native_ticks != requested_native_ticks:
        raise RuntimeError("resident throughput window was not fully native")
    if terminal_rows:
        raise RuntimeError("resident throughput window contains terminal rows")
    if elapsed <= 0.0:
        raise RuntimeError("resident throughput timer did not advance")

    digest = hashlib.sha256()
    for snapshot in snapshots:
        for tensor in snapshot:
            _update_digest(digest, tensor)
    final_digest = digest.hexdigest()
    resident_rows = args.batch_size * args.measured_decisions
    actor_transitions = resident_rows * 2
    peak_memory = (
        int(torch.cuda.max_memory_allocated(bridge.device))
        if bridge.device.type == "cuda"
        else None
    )
    trial = BenchmarkTrial(
        repetition=repetition,
        elapsed_seconds=elapsed,
        decision_calls=args.measured_decisions,
        resident_rows=resident_rows,
        actor_transitions=actor_transitions,
        requested_native_ticks=requested_native_ticks,
        native_ticks=native_ticks,
        fallback_rows=fallback_rows,
        terminal_rows=terminal_rows,
        decision_calls_per_second=args.measured_decisions / elapsed,
        resident_rows_per_second=resident_rows / elapsed,
        actor_transitions_per_second=actor_transitions / elapsed,
        native_ticks_per_second=native_ticks / elapsed,
        peak_device_memory_bytes=peak_memory,
        digest=final_digest,
    )
    return trial, str(bridge.device)


def _resolve_preset(args: argparse.Namespace) -> argparse.Namespace:
    defaults = {
        "smoke": (1, 0, 1, 2),
        "profile": (4, 1, 4, 3),
    }
    batch_size, warmup, measured, repetitions = defaults[args.preset]
    args.batch_size = args.batch_size or batch_size
    if args.warmup_decisions is None:
        args.warmup_decisions = warmup
    args.measured_decisions = args.measured_decisions or measured
    args.repetitions = args.repetitions or repetitions
    if args.max_ticks is None:
        args.max_ticks = (
            (args.warmup_decisions + args.measured_decisions)
            * args.decision_interval
            + 1
        )
    return args


def benchmark(args: argparse.Namespace) -> dict[str, object]:
    args = _resolve_preset(args)
    positive = (
        args.batch_size,
        args.measured_decisions,
        args.repetitions,
        args.decision_interval,
        args.max_ticks,
        args.max_entities,
        args.max_objects,
    )
    if min(positive) < 1 or args.warmup_decisions < 0:
        raise ValueError("benchmark counts, intervals, and capacities must be valid")
    if args.repetitions < 2:
        raise ValueError("deterministic throughput requires at least two repetitions")
    required_ticks = (
        args.warmup_decisions + args.measured_decisions
    ) * args.decision_interval
    if args.max_ticks <= required_ticks:
        raise ValueError("max_ticks must exceed the complete timed window")

    decks = [list(deck) for deck in load_deck_pool(args.decks_path)]
    trials: list[BenchmarkTrial] = []
    resolved_device = args.device
    for repetition in range(args.repetitions):
        trial, resolved_device = _run_trial(
            args, repetition=repetition, decks=decks
        )
        trials.append(trial)
    reference = trials[0]
    deterministic = all(
        trial.digest == reference.digest
        and trial.native_ticks == reference.native_ticks
        and trial.requested_native_ticks == reference.requested_native_ticks
        for trial in trials[1:]
    )
    if not deterministic:
        raise RuntimeError("resident throughput replay is nondeterministic")

    def median(field: str) -> float:
        return statistics.median(float(getattr(trial, field)) for trial in trials)

    return {
        "schema_version": 1,
        "profile": PROJECTED_GYM_TRANSITION_PROFILE,
        "preset": args.preset,
        "device_requested": args.device,
        "device_resolved": resolved_device,
        "configuration": {
            "seed": args.seed,
            "policy": args.policy,
            "batch_size": args.batch_size,
            "warmup_decisions": args.warmup_decisions,
            "measured_decisions": args.measured_decisions,
            "repetitions": args.repetitions,
            "decision_interval": args.decision_interval,
            "max_ticks": args.max_ticks,
            "max_entities": args.max_entities,
            "max_objects": args.max_objects,
            "execution_profile": getattr(
                args,
                "execution_profile",
                RESIDENT_EXECUTION_PROFILE_EXACT_DEBUG,
            ),
        },
        "timing_scope": {
            "included": "observe, deterministic action selection, validated resident step, and output snapshot clones",
            "excluded": "environment construction, warmup, device-to-host digest copies, and JSON encoding",
        },
        "acceptance": {
            "deterministic_replay": deterministic,
            "all_requested_ticks_native": True,
            "zero_fallback": True,
            "no_terminal_rows_in_window": True,
            "python_parity_evaluated": False,
            "speedup_evaluated": False,
        },
        "median": {
            "elapsed_seconds": median("elapsed_seconds"),
            "decision_calls_per_second": median("decision_calls_per_second"),
            "resident_rows_per_second": median("resident_rows_per_second"),
            "actor_transitions_per_second": median(
                "actor_transitions_per_second"
            ),
            "native_ticks_per_second": median("native_ticks_per_second"),
        },
        "trials": [asdict(trial) for trial in trials],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", choices=("smoke", "profile"), default="smoke")
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--seed", type=int, default=202_608_260)
    parser.add_argument("--policy", choices=("noop", "first-legal"), default="noop")
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--warmup-decisions", type=int)
    parser.add_argument("--measured-decisions", type=int)
    parser.add_argument("--repetitions", type=int)
    parser.add_argument("--decision-interval", type=int, default=1)
    parser.add_argument("--max-ticks", type=int)
    parser.add_argument("--max-entities", type=int, default=32)
    parser.add_argument("--max-objects", type=int, default=32)
    parser.add_argument(
        "--execution-profile",
        choices=sorted(RESIDENT_EXECUTION_PROFILES),
        default=RESIDENT_EXECUTION_PROFILE_EXACT_DEBUG,
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
        args.out.write_text(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
