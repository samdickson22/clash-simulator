#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import time
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from clasher.differential import SNAPSHOT_SCHEMA_VERSION
from clasher.interaction_matrix import (
    enabled_troop_cards,
    iter_one_v_one_cases,
    iter_two_v_two_cases,
    matrix_manifest,
    one_v_one_case_count,
    shard_range,
    two_v_two_composition_count,
)
from clasher.interaction_scenarios import (
    interaction_case_summary,
    run_python_interaction_case,
    run_rust_interaction_case,
)
from clasher.rust_core import rust_core_available
from clasher.rust_differential import RESIDENT_SEMANTIC_SCHEMA_VERSION

try:
    from scripts.interaction_journal import (
        JOURNAL_SCHEMA_VERSION,
        SUPPORTED_CANDIDATES,
        canonical_bytes,
        chain_next,
        fingerprint,
        initial_chain,
        journal_header,
        load_journal,
        relative_artifact_path,
        setup_event_counts,
    )
except ModuleNotFoundError:  # Direct ``python scripts/...`` execution.
    from interaction_journal import (  # type: ignore[no-redef]
        JOURNAL_SCHEMA_VERSION,
        SUPPORTED_CANDIDATES,
        canonical_bytes,
        chain_next,
        fingerprint,
        initial_chain,
        journal_header,
        load_journal,
        relative_artifact_path,
        setup_event_counts,
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
        "--candidate",
        choices=SUPPORTED_CANDIDATES,
        default="python-self",
    )
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


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _source_bundle_sha256(repo_root: Path) -> str:
    candidates = [
        *repo_root.glob("src/clasher/**/*.py"),
        *repo_root.glob("rust/clasher-core/src/**/*.rs"),
        repo_root / "rust/clasher-core/Cargo.toml",
        repo_root / "rust/clasher-core/Cargo.lock",
        repo_root / "scripts/run_interaction_shard.py",
        repo_root / "scripts/aggregate_interaction_shards.py",
        repo_root / "scripts/interaction_journal.py",
    ]
    hasher = hashlib.sha256()
    for path in sorted({path.resolve() for path in candidates if path.is_file()}):
        relative = path.relative_to(repo_root).as_posix().encode("utf-8")
        hasher.update(len(relative).to_bytes(8, "little"))
        hasher.update(relative)
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                hasher.update(chunk)
    return hasher.hexdigest()


def _git_output(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _preflight_candidate(candidate: str) -> dict[str, Any] | None:
    if candidate == "python-self":
        return None
    if not rust_core_available():
        raise RuntimeError(
            "resident-rust-shadow candidate is unavailable: optional Rust "
            "extension is not installed"
        )
    spec = importlib.util.find_spec("_clasher_rust._clasher_rust")
    origin = None if spec is None else spec.origin
    if origin is None or not Path(origin).is_file():
        raise RuntimeError(
            "resident-rust-shadow candidate has no hashable native artifact"
        )
    artifact = Path(origin).resolve()
    return {
        "path_name": artifact.name,
        "sha256": _sha256_file(artifact),
    }


def _local_provenance(
    candidate: str,
    *,
    native_artifact: Mapping[str, Any] | None,
) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    cargo_lock = repo_root / "rust/clasher-core/Cargo.lock"
    cargo_manifest = repo_root / "rust/clasher-core/Cargo.toml"
    return {
        "cargo_lock_sha256": _sha256_file(cargo_lock),
        "cargo_manifest_sha256": _sha256_file(cargo_manifest),
        "git_head": _git_output(repo_root, "rev-parse", "HEAD"),
        "git_tracked_dirty": bool(
            _git_output(repo_root, "status", "--porcelain", "--untracked-files=no")
        ),
        "native_artifact": (None if native_artifact is None else dict(native_artifact)),
        "platform": platform.platform(),
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
        },
        "source_bundle_sha256": _source_bundle_sha256(repo_root),
        "candidate": candidate,
    }


def _run_candidate_case(
    candidate: str,
    case: Any,
    *,
    ticks: int,
    seed: int,
    dump_directory: str | None,
) -> tuple[Any, Any]:
    runner = (
        run_python_interaction_case
        if candidate == "python-self"
        else run_rust_interaction_case
    )
    setup, result = runner(
        case,
        ticks=ticks,
        seed=seed,
        dump_directory=dump_directory,
    )
    if result.expected_sha256 != result.actual_sha256:
        raise AssertionError(
            f"{candidate} differential drift for {case.case_id}: "
            f"expected={result.expected_sha256} actual={result.actual_sha256}"
        )
    return setup, result


def _case_record(
    candidate: str,
    setup: Any,
    result: Any,
) -> dict[str, Any]:
    shadow_checks = (
        int(result.ticks_compared) if candidate == "resident-rust-shadow" else 0
    )
    return {
        **interaction_case_summary(setup),
        "actual_state_sha256": result.actual_sha256,
        "capability_accepted": True,
        "expected_state_sha256": result.expected_sha256,
        "parity_checks": int(result.ticks_compared),
        "parity_mismatches": 0,
        "shadow_checks": shadow_checks,
        "shadow_mismatches": 0,
        "state_sha256": result.expected_sha256,
        "ticks_compared": int(result.ticks_compared),
        "type": "case",
    }


def main() -> None:
    args = _parse_args()
    if args.ticks < 0:
        raise ValueError("ticks must be non-negative")
    if args.limit is not None and args.limit < 0:
        raise ValueError("limit must be non-negative")
    if args.flush_every <= 0:
        raise ValueError("flush-every must be positive")

    native_artifact = _preflight_candidate(args.candidate)
    cards = enabled_troop_cards()
    manifest = matrix_manifest()
    total = (
        one_v_one_case_count(len(cards))
        if args.kind == "1v1"
        else two_v_two_composition_count(len(cards))
    )
    selected = shard_range(total, args.shard_index, args.shard_count)
    target_count = (
        selected.size if args.limit is None else min(selected.size, args.limit)
    )
    config = {
        "candidate": args.candidate,
        "cards_sha256": hashlib.sha256("\n".join(cards).encode("utf-8")).hexdigest(),
        "decks_sha256": str(dict(manifest["decks"])["sha256"]),
        "gamedata_sha256": str(dict(manifest["gamedata"])["sha256"]),
        "interaction_manifest_sha256": fingerprint(manifest),
        "journal_schema_version": JOURNAL_SCHEMA_VERSION,
        "kind": args.kind,
        "limit": args.limit,
        "provenance": _local_provenance(
            args.candidate,
            native_artifact=native_artifact,
        ),
        "semantic_event_trace_schema_version": None,
        "seed": args.seed,
        "shard_count": args.shard_count,
        "shard_index": args.shard_index,
        "shard_start": selected.start,
        "shard_stop": selected.stop,
        "state_schema": {
            "name": (
                "resident-semantic"
                if args.candidate == "resident-rust-shadow"
                else "canonical-battle"
            ),
            "version": (
                RESIDENT_SEMANTIC_SCHEMA_VERSION
                if args.candidate == "resident-rust-shadow"
                else SNAPSHOT_SCHEMA_VERSION
            ),
        },
        "ticks_per_case": args.ticks,
    }
    config_fingerprint = fingerprint(config)
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
    loaded = load_journal(
        journal_path,
        expected_config=config,
        expected_fingerprint=config_fingerprint,
        expected_start=selected.start,
        repair_partial_tail=True,
    )
    records = loaded.records
    completed_count = len(records)
    chain = loaded.sha256_chain
    if completed_count > target_count:
        raise ValueError(
            f"journal has {completed_count} cases but this run targets {target_count}"
        )

    header = journal_header(config, config_fingerprint=config_fingerprint)
    mode = "a" if completed_count else "w"
    started = time.perf_counter()
    with journal_path.open(mode, encoding="utf-8") as journal:
        if completed_count == 0:
            journal.write(canonical_bytes(header).decode("ascii") + "\n")
            journal.flush()
            os.fsync(journal.fileno())
            chain = initial_chain(header)
        for local_index, case in enumerate(_case_iterator(args, cards)):
            if local_index < completed_count:
                continue
            if local_index >= target_count:
                break
            setup, result = _run_candidate_case(
                args.candidate,
                case,
                ticks=args.ticks,
                seed=args.seed,
                dump_directory=(
                    None if args.dump_directory is None else str(args.dump_directory)
                ),
            )
            record_without_chain = _case_record(args.candidate, setup, result)
            chain = chain_next(chain, record_without_chain)
            record = {**record_without_chain, "chain_sha256": chain}
            journal.write(canonical_bytes(record).decode("ascii") + "\n")
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
            0.0 if elapsed <= 0.0 else (len(records) - completed_count) / elapsed
        ),
        "cases_run": len(records),
        "completed_this_run": len(records) - completed_count,
        "coverage_is_full_shard": complete and args.limit is None,
        "elapsed_seconds_this_run": elapsed,
        "event_counts": setup_event_counts(records),
        "event_counts_scope": "scenario-setup-only",
        "fingerprint": config_fingerprint,
        "journal_path": relative_artifact_path(
            journal_path,
            summary_path=summary_path,
        ),
        "journal_sha256": hashlib.sha256(journal_path.read_bytes()).hexdigest(),
        "resume_from_count": completed_count,
        "semantic_event_tracing": "deferred",
        "sha256_chain": chain,
        "shadow_checks": sum(int(record["shadow_checks"]) for record in records),
        "shadow_mismatches": sum(
            int(record["shadow_mismatches"]) for record in records
        ),
        "status": "complete" if complete else "incomplete",
    }
    _write_atomic(summary_path, payload)
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
