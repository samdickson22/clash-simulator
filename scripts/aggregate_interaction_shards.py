#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from clasher.interaction_matrix import (
    enabled_troop_cards,
    one_v_one_case_count,
    two_v_two_composition_count,
)

AGGREGATE_SCHEMA_VERSION = 1
SHARED_CONFIG_FIELDS = (
    "candidate",
    "cards_sha256",
    "journal_schema_version",
    "kind",
    "seed",
    "shard_count",
    "ticks_per_case",
)
SHARD_CONFIG_FIELDS = (
    *SHARED_CONFIG_FIELDS,
    "limit",
    "shard_index",
    "shard_start",
    "shard_stop",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and aggregate completed interaction parity shards"
    )
    parser.add_argument("summaries", nargs="+", type=Path)
    parser.add_argument("--json-out", required=True, type=Path)
    return parser.parse_args()


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")


def _fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _write_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as target:
        json.dump(payload, target, indent=2, sort_keys=True)
        target.write("\n")
        target.flush()
        os.fsync(target.fileno())
    temporary.replace(path)


def _expected_total(kind: str) -> int:
    card_count = len(enabled_troop_cards())
    if kind == "1v1":
        return one_v_one_case_count(card_count)
    if kind == "2v2":
        return two_v_two_composition_count(card_count)
    raise ValueError(f"unsupported interaction kind {kind!r}")


def _shared_config(summary: Mapping[str, Any]) -> dict[str, Any]:
    missing = [field for field in SHARED_CONFIG_FIELDS if field not in summary]
    if missing:
        raise ValueError(f"interaction summary is missing fields: {missing}")
    return {field: summary[field] for field in SHARED_CONFIG_FIELDS}


def _validate_summary(
    summary: Mapping[str, Any],
    *,
    path: Path,
    shared_config: Mapping[str, Any],
) -> None:
    actual_shared = _shared_config(summary)
    if actual_shared != shared_config:
        raise ValueError(
            f"mixed interaction shard configuration in {path}: "
            f"expected={shared_config!r} actual={actual_shared!r}"
        )
    shard_config = {field: summary[field] for field in SHARD_CONFIG_FIELDS}
    expected_fingerprint = _fingerprint(shard_config)
    if summary.get("fingerprint") != expected_fingerprint:
        raise ValueError(
            f"interaction shard fingerprint mismatch in {path}: "
            f"expected={expected_fingerprint} actual={summary.get('fingerprint')}"
        )
    if summary.get("status") != "complete":
        raise ValueError(f"interaction shard is incomplete: {path}")
    if summary.get("limit") is not None:
        raise ValueError(f"sampled shard cannot be aggregated as exhaustive: {path}")
    if summary.get("coverage_is_full_shard") is not True:
        raise ValueError(f"interaction shard does not cover its full range: {path}")
    start = int(summary["shard_start"])
    stop = int(summary["shard_stop"])
    if stop < start:
        raise ValueError(f"interaction shard has an invalid range: {path}")
    if int(summary["cases_run"]) != stop - start:
        raise ValueError(
            f"interaction shard case count does not match its range: {path}"
        )
    journal_path = Path(str(summary["journal_path"]))
    if not journal_path.is_file():
        raise ValueError(f"interaction shard journal is missing: {journal_path}")
    actual_journal_hash = hashlib.sha256(journal_path.read_bytes()).hexdigest()
    if actual_journal_hash != summary.get("journal_sha256"):
        raise ValueError(f"interaction shard journal hash mismatch: {journal_path}")


def aggregate_summaries(
    summary_paths: Sequence[Path],
) -> dict[str, Any]:
    if not summary_paths:
        raise ValueError("at least one interaction summary is required")
    loaded = [(path.resolve(), json.loads(path.read_text())) for path in summary_paths]
    shared = _shared_config(loaded[0][1])
    shard_count = int(shared["shard_count"])
    if len(loaded) != shard_count:
        raise ValueError(
            f"expected {shard_count} shard summaries, received {len(loaded)}"
        )

    by_index: dict[int, tuple[Path, dict[str, Any]]] = {}
    for path, summary in loaded:
        _validate_summary(summary, path=path, shared_config=shared)
        shard_index = int(summary["shard_index"])
        if shard_index in by_index:
            raise ValueError(f"duplicate interaction shard index {shard_index}")
        by_index[shard_index] = (path, summary)
    expected_indices = set(range(shard_count))
    if set(by_index) != expected_indices:
        missing = sorted(expected_indices - set(by_index))
        extra = sorted(set(by_index) - expected_indices)
        raise ValueError(f"interaction shard index gap: missing={missing} extra={extra}")

    total = _expected_total(str(shared["kind"]))
    cursor = 0
    cases_run = 0
    event_counts: dict[str, Counter[str]] = {}
    shard_records: list[dict[str, Any]] = []
    for shard_index in range(shard_count):
        path, summary = by_index[shard_index]
        start = int(summary["shard_start"])
        stop = int(summary["shard_stop"])
        if start != cursor:
            raise ValueError(
                "interaction shard range gap or overlap: "
                f"index={shard_index} expected_start={cursor} actual_start={start}"
            )
        cursor = stop
        cases_run += int(summary["cases_run"])
        for event, counts in dict(summary["event_counts"]).items():
            aggregate = event_counts.setdefault(str(event), Counter())
            aggregate.update({key: int(value) for key, value in counts.items()})
        shard_records.append(
            {
                "fingerprint": str(summary["fingerprint"]),
                "index": shard_index,
                "journal_sha256": str(summary["journal_sha256"]),
                "sha256_chain": str(summary["sha256_chain"]),
                "start": start,
                "stop": stop,
                "summary_path": str(path),
            }
        )
    if cursor != total or cases_run != total:
        raise ValueError(
            "interaction shard coverage is incomplete: "
            f"expected={total} range_stop={cursor} cases_run={cases_run}"
        )

    aggregate_identity = {
        "aggregate_schema_version": AGGREGATE_SCHEMA_VERSION,
        "shared_config": shared,
        "shards": shard_records,
    }
    kind = str(shared["kind"])
    return {
        **shared,
        "aggregate_schema_version": AGGREGATE_SCHEMA_VERSION,
        "cases_run": cases_run,
        "coverage_claim": (
            "exhaustive ordered/mirrored/scalar-fast 1v1 cases within the "
            f"declared {shared['ticks_per_case']}-tick horizon"
            if kind == "1v1"
            else "exhaustive unordered 2v2 team compositions within the "
            f"declared {shared['ticks_per_case']}-tick horizon; geometry, event, "
            "mirror, targeting, and spawn-order axes are systematic, not "
            "Cartesian exhaustive"
        ),
        "coverage_is_exhaustive_within_declared_horizon": True,
        "event_counts": {
            event: dict(sorted(counts.items()))
            for event, counts in sorted(event_counts.items())
        },
        "fingerprint": _fingerprint(aggregate_identity),
        "shards": shard_records,
        "status": "complete",
    }


def main() -> None:
    args = _parse_args()
    payload = aggregate_summaries(args.summaries)
    _write_atomic(args.json_out.resolve(), payload)
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
