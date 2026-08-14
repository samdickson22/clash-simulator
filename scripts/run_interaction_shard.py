#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from collections import Counter
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from clasher.interaction_matrix import (
    enabled_troop_cards,
    iter_one_v_one_cases,
    iter_two_v_two_cases,
    one_v_one_case_count,
    shard_range,
    two_v_two_composition_count,
)
from clasher.interaction_scenarios import (
    interaction_case_summary,
    run_python_interaction_case,
)

JOURNAL_SCHEMA_VERSION = 1
CANDIDATE = "python-self"


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
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument(
        "--journal-out",
        type=Path,
        default=None,
        help="append-only JSONL path; defaults to JSON_OUT with .jsonl suffix",
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--flush-every", type=int, default=1)
    return parser.parse_args()


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")


def _fingerprint(config: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(config)).hexdigest()


def _chain_next(previous: str, record: Mapping[str, Any]) -> str:
    hasher = hashlib.sha256()
    hasher.update(bytes.fromhex(previous))
    hasher.update(_canonical_bytes(record))
    return hasher.hexdigest()


def _truncate_partial_tail(path: Path) -> None:
    if not path.exists():
        return
    payload = path.read_bytes()
    if not payload or payload.endswith(b"\n"):
        return
    complete_size = payload.rfind(b"\n") + 1
    with path.open("r+b") as journal:
        journal.truncate(complete_size)


def _load_journal(
    path: Path,
    *,
    expected_fingerprint: str,
    expected_start: int,
) -> tuple[int, str, list[dict[str, Any]]]:
    _truncate_partial_tail(path)
    if not path.exists() or path.stat().st_size == 0:
        return 0, "", []
    records = [json.loads(line) for line in path.read_text().splitlines()]
    header = records[0]
    if header.get("type") != "header":
        raise ValueError("interaction journal does not begin with a header")
    if header.get("fingerprint") != expected_fingerprint:
        raise ValueError(
            "interaction journal fingerprint mismatch: "
            f"expected={expected_fingerprint} actual={header.get('fingerprint')}"
        )
    chain = hashlib.sha256(_canonical_bytes(header)).hexdigest()
    completed: list[dict[str, Any]] = []
    for local_index, record in enumerate(records[1:]):
        if record.get("type") != "case":
            raise ValueError(
                f"unexpected journal record type at line {local_index + 2}"
            )
        expected_index = expected_start + local_index
        if record.get("index") != expected_index:
            raise ValueError(
                "interaction journal is not contiguous: "
                f"expected index {expected_index}, got {record.get('index')}"
            )
        record_without_chain = dict(record)
        recorded_chain = str(record_without_chain.pop("chain_sha256", ""))
        chain = _chain_next(chain, record_without_chain)
        if recorded_chain != chain:
            raise ValueError(
                f"interaction journal hash-chain mismatch at index {expected_index}"
            )
        completed.append(record)
    return len(completed), chain, completed


def _write_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as target:
        json.dump(payload, target, indent=2, sort_keys=True)
        target.write("\n")
        target.flush()
        os.fsync(target.fileno())
    temporary.replace(path)


def _case_iterator(args: argparse.Namespace, cards: tuple[str, ...]) -> Iterator[Any]:
    if args.kind == "1v1":
        return iter_one_v_one_cases(
            cards,
            shard_index=args.shard_index,
            shard_count=args.shard_count,
        )
    return iter_two_v_two_cases(
        cards,
        shard_index=args.shard_index,
        shard_count=args.shard_count,
    )


def _event_counts(records: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    attempted = Counter(str(record["event_family"]) for record in records)
    applied = Counter(
        str(record["event_family"])
        for record in records
        if bool(record["event_applied"])
    )
    return {
        event: {
            "attempted": attempted[event],
            "applied": applied[event],
            "no_op": attempted[event] - applied[event],
        }
        for event in sorted(attempted)
    }


def main() -> None:
    args = _parse_args()
    if args.ticks < 0:
        raise ValueError("ticks must be non-negative")
    if args.limit is not None and args.limit < 0:
        raise ValueError("limit must be non-negative")
    if args.flush_every <= 0:
        raise ValueError("flush-every must be positive")

    cards = enabled_troop_cards()
    total = (
        one_v_one_case_count(len(cards))
        if args.kind == "1v1"
        else two_v_two_composition_count(len(cards))
    )
    selected = shard_range(total, args.shard_index, args.shard_count)
    target_count = (
        selected.size
        if args.limit is None
        else min(selected.size, args.limit)
    )
    config = {
        "candidate": CANDIDATE,
        "cards_sha256": hashlib.sha256(
            "\n".join(cards).encode("utf-8")
        ).hexdigest(),
        "journal_schema_version": JOURNAL_SCHEMA_VERSION,
        "kind": args.kind,
        "limit": args.limit,
        "seed": args.seed,
        "shard_count": args.shard_count,
        "shard_index": args.shard_index,
        "shard_start": selected.start,
        "shard_stop": selected.stop,
        "ticks_per_case": args.ticks,
    }
    fingerprint = _fingerprint(config)
    summary_path = args.json_out.resolve()
    journal_path = (
        args.journal_out.resolve()
        if args.journal_out is not None
        else summary_path.with_suffix(".jsonl")
    )
    journal_path.parent.mkdir(parents=True, exist_ok=True)

    if journal_path.exists() and not args.resume:
        raise FileExistsError(
            "journal already exists; pass --resume or choose another path: "
            f"{journal_path}"
        )
    completed_count, chain, records = _load_journal(
        journal_path,
        expected_fingerprint=fingerprint,
        expected_start=selected.start,
    )
    if completed_count > target_count:
        raise ValueError(
            f"journal has {completed_count} cases but this run targets {target_count}"
        )

    header = {
        "config": config,
        "fingerprint": fingerprint,
        "type": "header",
    }
    mode = "a" if completed_count else "w"
    started = time.perf_counter()
    with journal_path.open(mode, encoding="utf-8") as journal:
        if completed_count == 0:
            journal.write(_canonical_bytes(header).decode("ascii") + "\n")
            journal.flush()
            os.fsync(journal.fileno())
            chain = hashlib.sha256(_canonical_bytes(header)).hexdigest()
        for local_index, case in enumerate(_case_iterator(args, cards)):
            if local_index < completed_count:
                continue
            if local_index >= target_count:
                break
            setup, result = run_python_interaction_case(
                case,
                ticks=args.ticks,
                seed=args.seed,
                dump_directory=(
                    None
                    if args.dump_directory is None
                    else str(args.dump_directory)
                ),
            )
            if result.expected_sha256 != result.actual_sha256:
                raise AssertionError(f"self-differential drift for {case.case_id}")
            record_without_chain = {
                **interaction_case_summary(setup),
                "state_sha256": result.expected_sha256,
                "type": "case",
            }
            chain = _chain_next(chain, record_without_chain)
            record = {**record_without_chain, "chain_sha256": chain}
            journal.write(_canonical_bytes(record).decode("ascii") + "\n")
            records.append(record)
            if (local_index + 1) % args.flush_every == 0:
                journal.flush()
                os.fsync(journal.fileno())
        journal.flush()
        os.fsync(journal.fileno())

    elapsed = time.perf_counter() - started
    complete = len(records) == target_count
    payload = {
        **config,
        "cases_per_second_this_run": (
            0.0
            if elapsed <= 0.0
            else (len(records) - completed_count) / elapsed
        ),
        "cases_run": len(records),
        "completed_this_run": len(records) - completed_count,
        "coverage_is_full_shard": complete and args.limit is None,
        "elapsed_seconds_this_run": elapsed,
        "event_counts": _event_counts(records),
        "fingerprint": fingerprint,
        "journal_path": str(journal_path),
        "journal_sha256": hashlib.sha256(journal_path.read_bytes()).hexdigest(),
        "resume_from_count": completed_count,
        "sha256_chain": chain,
        "status": "complete" if complete else "incomplete",
    }
    _write_atomic(summary_path, payload)
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
