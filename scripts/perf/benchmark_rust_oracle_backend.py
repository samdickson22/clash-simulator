#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import time
from collections import deque
from dataclasses import asdict, dataclass

import numpy as np

from clasher.battle import BattleState
from clasher.rl.rust_oracle_planner import RustBackendFixedDepthThompsonOracle
from clasher.rust_core import ResidentRustBattle

BENCHMARK_DECK = (
    "BabyDragon",
    "Berserker",
    "BlowdartGoblin",
    "Bomber",
    "DartBarrell",
    "ElectroGiant",
    "Giant",
    "GiantBuffer",
)


@dataclass(frozen=True)
class Sample:
    repetition: int
    python_seconds: float
    rust_seconds: float
    speedup: float
    actions: dict[int, int]
    trace_sha256: str


def _supported_battle(seed: int) -> BattleState:
    battle = BattleState(rng=random.Random(seed))
    resident = ResidentRustBattle.from_battle(battle)
    supported = set(resident.resident_supported_action_cards())
    if not all(name in supported for name in BENCHMARK_DECK):
        raise RuntimeError("resident oracle benchmark deck is no longer supported")
    deck = list(BENCHMARK_DECK)
    for player in battle.players:
        player.hand = list(deck[:4])
        player.deck = deck.copy()
        player.cycle_queue = deque(deck[4:])
        player.elixir = player.max_elixir
    return battle


def _one_label(
    mode: str,
    *,
    battle_seed: int,
    planner_seed: int,
    decision_ticks: int,
    depth: int,
    simulations: int,
    action_samples: int,
) -> tuple[float, dict[int, int], str]:
    battle = _supported_battle(battle_seed)
    planner = RustBackendFixedDepthThompsonOracle(
        decision_interval_ticks=decision_ticks,
        plan_depth=depth,
        num_simulations=simulations,
        rollout_action_samples=action_samples,
        seed=planner_seed,
        reward_profile="defense-v2",
        stable_root_candidates=True,
        rust_mode=mode,
    )
    started = time.perf_counter()
    actions = planner.select_actions(battle)
    elapsed = time.perf_counter() - started
    if planner.metrics.trace_sha256 is None:
        raise RuntimeError("oracle benchmark did not produce a trace digest")
    expected_backend = "python" if mode == "off" else "rust"
    if planner.metrics.active_backend != expected_backend:
        raise RuntimeError(
            f"oracle benchmark {mode=} used {planner.metrics.active_backend!r}: "
            f"{planner.metrics.fallback_reason}"
        )
    return elapsed, actions, planner.metrics.trace_sha256


def _bootstrap_speedup_ci(
    python_seconds: np.ndarray,
    rust_seconds: np.ndarray,
    *,
    samples: int = 10_000,
) -> tuple[float, float]:
    rng = np.random.default_rng(20_260_813)
    indices = rng.integers(0, python_seconds.size, size=(samples, python_seconds.size))
    ratios = python_seconds[indices].mean(axis=1) / rust_seconds[indices].mean(axis=1)
    low, high = np.quantile(ratios, [0.025, 0.975])
    return float(low), float(high)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--battle-seed", type=int, default=9401)
    parser.add_argument("--planner-seed", type=int, default=901)
    parser.add_argument("--decision-ticks", type=int, default=8)
    parser.add_argument("--depth", type=int, default=6)
    parser.add_argument("--simulations", type=int, default=32)
    parser.add_argument("--action-samples", type=int, default=96)
    args = parser.parse_args()
    if args.repetitions < 2 or args.warmups < 0:
        raise ValueError("benchmark requires at least two repetitions and nonnegative warmups")
    parameters = {
        "battle_seed": args.battle_seed,
        "planner_seed": args.planner_seed,
        "decision_ticks": args.decision_ticks,
        "depth": args.depth,
        "simulations": args.simulations,
        "action_samples": args.action_samples,
    }
    for _ in range(args.warmups):
        _one_label("off", **parameters)
        _one_label("on", **parameters)

    results: list[Sample] = []
    for repetition in range(args.repetitions):
        order = ("off", "on") if repetition % 2 == 0 else ("on", "off")
        measured = {
            mode: _one_label(mode, **parameters)
            for mode in order
        }
        python_seconds, python_actions, python_trace = measured["off"]
        rust_seconds, rust_actions, rust_trace = measured["on"]
        if python_actions != rust_actions or python_trace != rust_trace:
            raise RuntimeError("Python/Rust oracle benchmark parity mismatch")
        results.append(
            Sample(
                repetition=repetition,
                python_seconds=python_seconds,
                rust_seconds=rust_seconds,
                speedup=python_seconds / rust_seconds,
                actions=python_actions,
                trace_sha256=python_trace,
            )
        )

    python_samples = np.asarray([sample.python_seconds for sample in results])
    rust_samples = np.asarray([sample.rust_seconds for sample in results])
    speedup = float(python_samples.mean() / rust_samples.mean())
    ci_low, ci_high = _bootstrap_speedup_ci(python_samples, rust_samples)
    print(
        json.dumps(
            {
                "schema_version": 1,
                "workload": "fixed-depth-oracle-supported-resident-closure",
                "parameters": parameters,
                "warmups": args.warmups,
                "repetitions": args.repetitions,
                "python_mean_seconds": float(python_samples.mean()),
                "rust_mean_seconds": float(rust_samples.mean()),
                "paired_mean_speedup": speedup,
                "paired_bootstrap_95_ci": [ci_low, ci_high],
                "parity": {
                    "actions": results[0].actions,
                    "trace_sha256": results[0].trace_sha256,
                    "mismatches": 0,
                },
                "samples": [asdict(sample) for sample in results],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
