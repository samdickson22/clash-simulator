#!/usr/bin/env python3
"""Benchmark Python ticks against resident Rust ON publication intervals."""

from __future__ import annotations

import argparse
import json
import random
import statistics
import time
from dataclasses import asdict, dataclass
from functools import partial
from typing import Any

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rust_core import RustBattleMode
from clasher.rust_differential import python_resident_semantic_snapshot
from clasher.rust_runtime import ResidentCompleteTickRuntime


@dataclass(frozen=True)
class TimingSummary:
    mean_seconds: float
    median_seconds: float
    intervals_per_second: float
    ticks_per_second: float


def _spawn_ready(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(card_name)
    if stats is None:  # pragma: no cover - benchmark fixture guard
        raise RuntimeError(f"missing benchmark card {card_name!r}")
    before = set(battle.entities)
    battle._spawn_unit_at_position(position, player_id, stats)
    troop = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )
    troop.deploy_delay_remaining = 0.0
    troop.placement_pending = False
    troop._spawn_hook_pending = False
    troop._spawn_hook_fired = True
    return troop


def _fixture(seed: int) -> BattleState:
    battle = BattleState(rng=random.Random(seed), fast_path=True)
    _spawn_ready(battle, "Knight", 0, Position(7.0, 12.0))
    _spawn_ready(battle, "Knight", 1, Position(11.0, 20.0))
    return battle


def _elapsed(call: Any) -> float:
    started = time.perf_counter_ns()
    call()
    return (time.perf_counter_ns() - started) / 1e9


def _summary(samples: list[float], ticks: int) -> TimingSummary:
    mean = statistics.mean(samples)
    return TimingSummary(
        mean_seconds=mean,
        median_seconds=statistics.median(samples),
        intervals_per_second=1.0 / mean,
        ticks_per_second=float(ticks) / mean,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=99_701)
    parser.add_argument("--ticks", type=int, nargs="+", default=[1, 8, 32])
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--repetitions", type=int, default=30)
    args = parser.parse_args()
    if (
        not args.ticks
        or any(ticks <= 0 for ticks in args.ticks)
        or args.warmups < 0
        or args.repetitions <= 0
    ):
        parser.error("ticks/repetitions must be positive and warmups nonnegative")

    base = _fixture(args.seed)
    results: list[dict[str, Any]] = []
    for ticks in args.ticks:
        for _ in range(args.warmups):
            python_battle = base.clone()
            python_battle.step_logic_ticks(ticks)
            rust_battle = base.clone()
            runtime = ResidentCompleteTickRuntime(rust_battle, RustBattleMode.ON)
            runtime.advance_ticks(ticks)

        python_samples: list[float] = []
        rust_samples: list[float] = []
        for repetition in range(args.repetitions):
            python_battle = base.clone()
            rust_battle = base.clone()
            runtime = ResidentCompleteTickRuntime(rust_battle, RustBattleMode.ON)
            arms = ("python", "rust") if repetition % 2 == 0 else ("rust", "python")
            for arm in arms:
                if arm == "python":
                    python_samples.append(
                        _elapsed(partial(python_battle.step_logic_ticks, ticks))
                    )
                else:
                    rust_samples.append(_elapsed(partial(runtime.advance_ticks, ticks)))
            if python_resident_semantic_snapshot(rust_battle) != (
                python_resident_semantic_snapshot(python_battle)
            ):
                raise AssertionError("Python and Rust ON publication diverged")

        python = _summary(python_samples, ticks)
        rust = _summary(rust_samples, ticks)
        results.append(
            {
                "python": asdict(python),
                "resident_on": asdict(rust),
                "speedup": python.mean_seconds / rust.mean_seconds,
                "ticks": ticks,
            }
        )
    print(
        json.dumps(
            {
                "repetitions": args.repetitions,
                "results": results,
                "seed": args.seed,
                "warmups": args.warmups,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
