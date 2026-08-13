#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from clasher.interaction_matrix import (
    enabled_troop_cards,
    iter_one_v_one_cases,
    iter_two_v_two_cases,
)
from clasher.interaction_scenarios import (
    interaction_case_summary,
    run_python_interaction_case,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one deterministic troop-interaction parity shard"
    )
    parser.add_argument("--kind", choices=("1v1", "2v2"), required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, required=True)
    parser.add_argument("--ticks", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0xC1A5_0000)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="explicitly run a non-exhaustive prefix of this shard",
    )
    parser.add_argument("--dump-directory", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.ticks < 0:
        raise ValueError("ticks must be non-negative")
    if args.limit is not None and args.limit < 0:
        raise ValueError("limit must be non-negative")
    cards = enabled_troop_cards()
    iterator = (
        iter_one_v_one_cases(
            cards,
            shard_index=args.shard_index,
            shard_count=args.shard_count,
        )
        if args.kind == "1v1"
        else iter_two_v_two_cases(
            cards,
            shard_index=args.shard_index,
            shard_count=args.shard_count,
        )
    )
    hasher = hashlib.sha256()
    cases: list[dict[str, object]] = []
    started = time.perf_counter()
    for local_index, case in enumerate(iterator):
        if args.limit is not None and local_index >= args.limit:
            break
        setup, result = run_python_interaction_case(
            case,
            ticks=args.ticks,
            seed=args.seed,
            dump_directory=(
                None if args.dump_directory is None else str(args.dump_directory)
            ),
        )
        if result.expected_sha256 != result.actual_sha256:
            raise AssertionError(f"self-differential drift for {case.case_id}")
        hasher.update(case.case_id.encode("ascii"))
        hasher.update(result.expected_sha256.encode("ascii"))
        cases.append(interaction_case_summary(setup))
    elapsed = time.perf_counter() - started
    payload = {
        "kind": args.kind,
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "ticks_per_case": args.ticks,
        "seed": args.seed,
        "limit": args.limit,
        "coverage_is_full_shard": args.limit is None,
        "cases_run": len(cases),
        "events_applied": sum(bool(case["event_applied"]) for case in cases),
        "elapsed_seconds": elapsed,
        "sha256": hasher.hexdigest(),
        "cases": cases,
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
