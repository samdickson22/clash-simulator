#!/usr/bin/env python3
"""Benchmark exact Python versus resident Rust action-plus-tick intervals."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import random
import statistics
import time
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass
from functools import partial
from typing import Any

from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rust_core import (
    ResidentRustBattle,
    compare_building_lifetime_phase,
    compare_character_object_phase,
    compare_clock_phase,
    compare_death_opcode_state,
    compare_ground_movement_phase,
    compare_locked_direct_combat_phase,
    compare_modifier_phase,
    compare_player_phase,
    compare_point_projectile_phase,
    compare_resident_entities,
    compare_resident_rng,
    compare_shield_state,
)
from clasher.rust_differential import rust_resident_semantic_snapshot


@dataclass(frozen=True)
class TimingSummary:
    median_seconds: float
    mean_seconds: float
    ci95_low_seconds: float
    ci95_high_seconds: float
    decisions_per_second: float
    ticks_per_second: float


def _summarize(samples: list[float], ticks: int) -> TimingSummary:
    mean = statistics.mean(samples)
    if len(samples) > 1:
        # Student-t critical value is 2.045 for the predeclared 30-repetition
        # production attribution. Normal 1.96 is conservative enough for
        # ad-hoc repetition counts above 30 and keeps this driver dependency-free.
        critical = 2.045 if len(samples) == 30 else 1.96
        half_width = critical * statistics.stdev(samples) / math.sqrt(len(samples))
    else:
        half_width = 0.0
    return TimingSummary(
        median_seconds=statistics.median(samples),
        mean_seconds=mean,
        ci95_low_seconds=mean - half_width,
        ci95_high_seconds=mean + half_width,
        decisions_per_second=1.0 / mean,
        ticks_per_second=float(ticks) / mean,
    )


def _time(call: Callable[[], Any]) -> tuple[float, Any]:
    started = time.perf_counter_ns()
    result = call()
    return (time.perf_counter_ns() - started) / 1e9, result


def _assert_parity(battle: BattleState, resident: ResidentRustBattle) -> None:
    compare_clock_phase(battle, resident)
    compare_player_phase(battle, resident)
    compare_locked_direct_combat_phase(battle, resident)
    compare_ground_movement_phase(battle, resident)
    compare_building_lifetime_phase(battle, resident)
    compare_modifier_phase(battle, resident)
    compare_character_object_phase(battle, resident)
    compare_point_projectile_phase(battle, resident)
    compare_death_opcode_state(battle, resident)
    compare_shield_state(battle, resident)
    compare_resident_entities(battle, resident)
    compare_resident_rng(battle.rng, resident)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=9423)
    parser.add_argument("--ticks", type=int, default=32)
    parser.add_argument("--warmups", type=int, default=5)
    parser.add_argument("--repetitions", type=int, default=30)
    args = parser.parse_args()
    if args.ticks <= 0 or args.warmups < 0 or args.repetitions <= 0:
        parser.error("ticks/repetitions must be positive and warmups nonnegative")

    action_space = DiscreteTileActionSpace()
    base = BattleState(rng=random.Random(args.seed))
    for player in base.players:
        player.hand = ["Knight"] * 4
        player.cycle_queue = deque(["Knight"] * 4)
        player.elixir = 10.0
    root = ResidentRustBattle.from_battle(base)
    actions = (
        action_space.encode_action(0, 8, 10, 0),
        action_space.encode_action(0, 9, 21, 1),
    )

    def python_interval(battle: BattleState) -> tuple[int, int]:
        order = [0, 1]
        battle.rng.shuffle(order)
        successes = {
            player_id: action_space.apply_action(
                battle,
                player_id,
                actions[player_id],
            )
            for player_id in order
        }
        assert successes == {0: True, 1: True}
        assert battle.step_logic_ticks(args.ticks) == args.ticks
        return (order[0], order[1])

    def rust_interval(resident: ResidentRustBattle) -> tuple[int, int]:
        successes, order = resident.apply_resident_joint_actions(*actions)
        assert successes == {0: True, 1: True}
        assert resident.advance_complete_ticks(args.ticks) == args.ticks
        return order

    for _ in range(args.warmups):
        python_interval(base.clone())
        rust_interval(root.fork())

    python_samples: list[float] = []
    rust_samples: list[float] = []
    final_python: BattleState | None = None
    final_rust: ResidentRustBattle | None = None
    python_order: tuple[int, int] | None = None
    rust_order: tuple[int, int] | None = None
    for repetition in range(args.repetitions):
        arms = ("python", "rust") if repetition % 2 == 0 else ("rust", "python")
        for arm in arms:
            if arm == "python":
                final_python = base.clone()
                elapsed, python_order = _time(partial(python_interval, final_python))
                python_samples.append(elapsed)
            else:
                final_rust = root.fork()
                elapsed, rust_order = _time(partial(rust_interval, final_rust))
                rust_samples.append(elapsed)

    assert final_python is not None and final_rust is not None
    assert python_order == rust_order
    _assert_parity(final_python, final_rust)
    semantic = rust_resident_semantic_snapshot(final_rust)
    semantic_sha256 = hashlib.sha256(
        json.dumps(semantic, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()
    python_summary = _summarize(python_samples, args.ticks)
    rust_summary = _summarize(rust_samples, args.ticks)
    print(
        json.dumps(
            {
                "action_order": rust_order,
                "machine": platform.machine(),
                "python": platform.python_version(),
                "python_arm": asdict(python_summary),
                "repetitions": args.repetitions,
                "resident_arm": asdict(rust_summary),
                "rng_sha256": final_rust.rng_sha256(),
                "seed": args.seed,
                "semantic_state_sha256": semantic_sha256,
                "speedup": (python_summary.mean_seconds / rust_summary.mean_seconds),
                "ticks_per_decision": args.ticks,
                "wall_reduction": (
                    1.0 - rust_summary.mean_seconds / python_summary.mean_seconds
                ),
                "warmups": args.warmups,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
