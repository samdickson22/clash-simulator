#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
import random
import statistics
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.differential import canonical_battle_snapshot, snapshot_bytes
from clasher.rust_core import (
    python_consume_state_bytes,
    require_rust_core,
    rust_consume_state_bytes,
    rust_noop_ticks,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure Python/Rust call and battle-state marshalling overhead"
    )
    parser.add_argument("--repetitions", type=int, default=9)
    parser.add_argument("--calls", type=int, default=100_000)
    parser.add_argument("--state-calls", type=int, default=500)
    parser.add_argument("--json-out", type=Path, default=None)
    return parser.parse_args()


def _machine() -> dict[str, str]:
    try:
        processor = subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        processor = platform.processor()
    return {
        "platform": platform.platform(),
        "processor": processor,
        "python": platform.python_version(),
    }


def _representative_state_bytes() -> bytes:
    battle = BattleState(rng=random.Random(91_337), fast_path=True)
    stats = battle.card_loader.get_card("Skeletons")
    assert stats is not None
    for player_id, base_y in ((0, 13.0), (1, 19.0)):
        for index in range(8):
            battle._spawn_troop(
                Position(3.0 + (index % 4) * 3.5, base_y + index // 4),
                player_id,
                stats,
            )
    battle._refresh_fast_path_caches()
    return snapshot_bytes(canonical_battle_snapshot(battle))


def _measure(function: Callable[[], object], repetitions: int) -> list[float]:
    samples: list[float] = []
    for _ in range(repetitions):
        started = time.perf_counter()
        function()
        samples.append(time.perf_counter() - started)
    return samples


def _summary(samples: list[float], operations: int) -> dict[str, float]:
    median = statistics.median(samples)
    return {
        "median_seconds": median,
        "min_seconds": min(samples),
        "max_seconds": max(samples),
        "median_nanoseconds_per_call": median * 1e9 / operations,
        "median_calls_per_second": operations / median,
    }


def main() -> None:
    args = _parse_args()
    if args.repetitions < 2 or args.calls <= 0 or args.state_calls <= 0:
        raise ValueError("repetitions must be >=2 and call counts must be positive")
    require_rust_core()
    state = _representative_state_bytes()
    expected_state_result = python_consume_state_bytes(state)
    if rust_consume_state_bytes(state) != expected_state_result:
        raise AssertionError("Rust state-byte boundary changed payload semantics")

    def python_noop_loop() -> int:
        value = 0
        for _ in range(args.calls):
            value = 8
        return value

    def rust_noop_loop() -> int:
        value = 0
        for _ in range(args.calls):
            value = rust_noop_ticks(8)
        return value

    def python_state_loop() -> tuple[int, int]:
        result = (0, 0)
        for _ in range(args.state_calls):
            result = python_consume_state_bytes(state)
        return result

    def rust_state_loop() -> tuple[int, int]:
        result = (0, 0)
        for _ in range(args.state_calls):
            result = rust_consume_state_bytes(state)
        return result

    payload = {
        "machine": _machine(),
        "config": {
            "repetitions": args.repetitions,
            "calls": args.calls,
            "state_calls": args.state_calls,
            "state_bytes": len(state),
        },
        "python_noop": _summary(
            _measure(python_noop_loop, args.repetitions),
            args.calls,
        ),
        "rust_noop": _summary(
            _measure(rust_noop_loop, args.repetitions),
            args.calls,
        ),
        "python_state_consume": _summary(
            _measure(python_state_loop, args.repetitions),
            args.state_calls,
        ),
        "rust_state_consume": _summary(
            _measure(rust_state_loop, args.repetitions),
            args.state_calls,
        ),
        "state_result": {
            "size": expected_state_result[0],
            "fnv1a_u64": expected_state_result[1],
        },
    }
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.json_out is not None:
        target = args.json_out.resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(encoded, encoding="utf-8")
        temporary.replace(target)
    print(encoded, end="")


if __name__ == "__main__":
    main()
