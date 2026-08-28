#!/usr/bin/env python3
"""Matched first-legal Python-object versus resident Simple Gym benchmark.

The benchmark deliberately excludes neural policy inference.  Both arms build
policy-visible observations and legal masks, choose the first legal action for
both actors, and advance exactly one native battle tick per measured step.
Runtime construction, reset, warm-up, replay hashing, and report serialization
are outside the timed windows.

This is a throughput comparison, not an exact-semantics claim: the production
Simple Gym follows its projected-gym contract and is not expected to hash to
the Python debug oracle.  Each backend must instead replay deterministically
within its own contract.
"""

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

from clasher.rl.deck_pool import load_deck_pool
from clasher.rl.public_action_mask import PublicActionMaskBuilder
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.torch_sim.simple_standard import (
    STANDARD_REGULATION_TICK,
    STANDARD_TIEBREAK_TICK,
)
from scripts.validate_simple_full_matches import (
    build_simple_runtime,
    select_actions,
    supported_simple_decks,
    update_step_digest,
)

BACKENDS = ("python-exact-mask", "python-public-v2", "simple-pytorch")


@dataclass(frozen=True)
class Trial:
    backend: str
    repetition: int
    elapsed_seconds: float
    row_ticks: int
    row_ticks_per_second: float
    actor_transitions_per_second: float
    digest: str


def paired_order(repetition: int) -> tuple[str, ...]:
    if repetition < 0:
        raise ValueError("repetition must be non-negative")
    if repetition % 2 == 0:
        return BACKENDS
    return tuple(reversed(BACKENDS))


def summarize(trials: list[Trial]) -> dict[str, Any]:
    by_backend = {
        backend: [trial for trial in trials if trial.backend == backend]
        for backend in BACKENDS
    }
    repetitions = {trial.repetition for trial in trials}
    if any(len(rows) != len(repetitions) for rows in by_backend.values()):
        raise ValueError("every repetition must contain all benchmark backends")
    medians = {
        backend: statistics.median(row.row_ticks_per_second for row in rows)
        for backend, rows in by_backend.items()
    }
    simple = medians["simple-pytorch"]
    return {
        "median_row_ticks_per_second": medians,
        "simple_speed_ratio_vs_python_exact": (
            simple / medians["python-exact-mask"]
        ),
        "simple_speed_ratio_vs_python_public_v2": (
            simple / medians["python-public-v2"]
        ),
    }


def _synchronize(device: torch.device) -> None:
    if device.type == "mps":
        torch.mps.synchronize()
    elif device.type == "cuda":
        torch.cuda.synchronize(device)


def _python_envs(args: argparse.Namespace) -> list[SelfPlayBattleEnv]:
    envs: list[SelfPlayBattleEnv] = []
    for index in range(args.batch_size):
        env = SelfPlayBattleEnv(
            decision_interval_ticks=1,
            max_ticks=6_000,
            decks_path=args.python_vocabulary_decks,
            sampling_decks_path=args.decks_path,
            seed=args.seed + index * 100_003,
            canonical_perspective=True,
            canonical_lane_globals=True,
            engine_fast_path="on",
            idle_fast_forward=False,
            reward_profile="objective-v1",
            elixir_leak_penalty_scale=0.0,
        )
        env.reset(seed=args.seed + index * 100_003)
        envs.append(env)
    return envs


def _python_tick(
    envs: list[SelfPlayBattleEnv], *, public_mask: bool
) -> tuple[int, int]:
    action_total = 0
    tick_total = 0
    for env in envs:
        observations = {
            player_id: env.get_structured_observation(player_id)
            for player_id in (0, 1)
        }
        if public_mask:
            builder = PublicActionMaskBuilder(env.structured_obs_builder)
            masks = {
                player_id: builder.build(observations[player_id])
                for player_id in (0, 1)
            }
        else:
            masks = {player_id: env.get_action_mask(player_id) for player_id in (0, 1)}
        actions = {
            player_id: int(np.flatnonzero(mask)[0])
            for player_id, mask in masks.items()
        }
        _rewards, done, info = env.step(actions, pre_action_masks=masks)
        if done:
            raise RuntimeError("Python benchmark reached a terminal row")
        action_total += actions[0] + actions[1]
        tick_total += info.ticks_advanced
    return action_total, tick_total


def _python_digest(args: argparse.Namespace, *, public_mask: bool) -> str:
    envs = _python_envs(args)
    digest = hashlib.sha256()
    for _ in range(args.warmup_ticks + args.measured_ticks):
        action_total, tick_total = _python_tick(envs, public_mask=public_mask)
        digest.update(action_total.to_bytes(8, "little", signed=True))
        digest.update(tick_total.to_bytes(8, "little", signed=True))
        for env in envs:
            assert env.battle is not None
            digest.update(env.battle.tick.to_bytes(8, "little", signed=False))
            for player in env.battle.players:
                digest.update(np.float64(player.elixir).tobytes())
                for value in player.hand:
                    digest.update(str(value).encode("utf-8"))
                    digest.update(b"\0")
    return digest.hexdigest()


def _run_python(
    args: argparse.Namespace, *, backend: str, repetition: int
) -> Trial:
    public_mask = backend == "python-public-v2"
    envs = _python_envs(args)
    for _ in range(args.warmup_ticks):
        _python_tick(envs, public_mask=public_mask)
    started = time.perf_counter()
    for _ in range(args.measured_ticks):
        _python_tick(envs, public_mask=public_mask)
    elapsed = time.perf_counter() - started
    row_ticks = args.batch_size * args.measured_ticks
    return Trial(
        backend=backend,
        repetition=repetition,
        elapsed_seconds=elapsed,
        row_ticks=row_ticks,
        row_ticks_per_second=row_ticks / elapsed,
        actor_transitions_per_second=2 * row_ticks / elapsed,
        digest=_python_digest(args, public_mask=public_mask),
    )


def _simple_decks(args: argparse.Namespace) -> list[list[str]]:
    candidates = [list(deck) for deck in load_deck_pool(args.decks_path)]
    decks = supported_simple_decks(candidates, device=args.simple_device)
    if len(decks) != len(candidates):
        raise RuntimeError("matched benchmark deck pool is not fully Simple-supported")
    return decks


def _simple_digest(args: argparse.Namespace, decks: list[list[str]]) -> str:
    runtime = build_simple_runtime(
        seed=args.seed,
        decks=decks,
        batch_size=args.batch_size,
        device=args.simple_device,
        max_entities=args.max_entities,
        max_effects=args.max_effects,
        regulation_ticks=STANDARD_REGULATION_TICK,
        tiebreak_ticks=STANDARD_TIEBREAK_TICK,
        supported_only=True,
    )
    observation = runtime.observe()
    digest = hashlib.sha256()
    for _ in range(args.warmup_ticks + args.measured_ticks):
        actions = select_actions(observation.legal_mask, "first-legal")
        step = runtime.step_tick(actions)
        update_step_digest(digest, step, actions)
        observation = step.observation
    return digest.hexdigest()


def _run_simple(
    args: argparse.Namespace, *, repetition: int, decks: list[list[str]]
) -> Trial:
    runtime = build_simple_runtime(
        seed=args.seed,
        decks=decks,
        batch_size=args.batch_size,
        device=args.simple_device,
        max_entities=args.max_entities,
        max_effects=args.max_effects,
        regulation_ticks=STANDARD_REGULATION_TICK,
        tiebreak_ticks=STANDARD_TIEBREAK_TICK,
        supported_only=True,
    )
    observation = runtime.observe()
    for _ in range(args.warmup_ticks):
        actions = select_actions(observation.legal_mask, "first-legal")
        observation = runtime.step_tick(actions).observation
    _synchronize(runtime.device)
    started = time.perf_counter()
    for _ in range(args.measured_ticks):
        actions = select_actions(observation.legal_mask, "first-legal")
        step = runtime.step_tick(actions)
        observation = step.observation
    _synchronize(runtime.device)
    elapsed = time.perf_counter() - started
    row_ticks = args.batch_size * args.measured_ticks
    return Trial(
        backend="simple-pytorch",
        repetition=repetition,
        elapsed_seconds=elapsed,
        row_ticks=row_ticks,
        row_ticks_per_second=row_ticks / elapsed,
        actor_transitions_per_second=2 * row_ticks / elapsed,
        digest=_simple_digest(args, decks),
    )


def benchmark(args: argparse.Namespace) -> dict[str, Any]:
    if min(
        args.batch_size,
        args.warmup_ticks,
        args.measured_ticks,
        args.repetitions,
        args.max_entities,
        args.max_effects,
    ) < 1:
        raise ValueError("all benchmark sizes must be positive")
    decks = _simple_decks(args)
    trials: list[Trial] = []
    for repetition in range(args.repetitions):
        for backend in paired_order(repetition):
            if backend == "simple-pytorch":
                trials.append(_run_simple(args, repetition=repetition, decks=decks))
            else:
                trials.append(_run_python(args, backend=backend, repetition=repetition))
    for backend in BACKENDS:
        digests = {trial.digest for trial in trials if trial.backend == backend}
        if len(digests) != 1:
            raise RuntimeError(f"{backend} replay is nondeterministic")
    return {
        "schema_version": 1,
        "scope": "matched raw policy-visible tick without neural inference",
        "simple_device": str(torch.device(args.simple_device)),
        "seed": args.seed,
        "batch_size": args.batch_size,
        "warmup_ticks": args.warmup_ticks,
        "measured_ticks": args.measured_ticks,
        "repetitions": args.repetitions,
        "deck_pool": {
            "path": str(Path(args.decks_path).resolve()),
            "decks": len(decks),
        },
        "semantic_limit": (
            "within-backend determinism only; Simple projected-gym semantics "
            "are not asserted byte-identical to the Python debug oracle"
        ),
        "summary": summarize(trials),
        "trials": [asdict(trial) for trial in trials],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--decks-path", default="training_decks/simple_gym_supported_v1.json"
    )
    parser.add_argument("--python-vocabulary-decks", default="decks.json")
    parser.add_argument("--simple-device", choices=("cpu", "mps", "cuda"), default="mps")
    parser.add_argument("--seed", type=int, default=202_608_281)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--warmup-ticks", type=int, default=2)
    parser.add_argument("--measured-ticks", type=int, default=10)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--max-entities", type=int, default=128)
    parser.add_argument("--max-effects", type=int, default=128)
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
