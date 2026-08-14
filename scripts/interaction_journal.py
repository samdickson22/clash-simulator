from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

JOURNAL_SCHEMA_VERSION = 2
SUPPORTED_CANDIDATES = ("python-self", "resident-rust-shadow")


@dataclass(frozen=True)
class LoadedJournal:
    records: list[dict[str, Any]]
    sha256_chain: str


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")


def fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def chain_next(previous: str, record: Mapping[str, Any]) -> str:
    hasher = hashlib.sha256()
    hasher.update(bytes.fromhex(previous))
    hasher.update(canonical_bytes(record))
    return hasher.hexdigest()


def journal_header(
    config: Mapping[str, Any],
    *,
    config_fingerprint: str,
) -> dict[str, Any]:
    return {
        "config": dict(config),
        "fingerprint": config_fingerprint,
        "type": "header",
    }


def initial_chain(header: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(header)).hexdigest()


def _truncate_partial_tail(path: Path) -> None:
    if not path.exists():
        return
    payload = path.read_bytes()
    if not payload or payload.endswith(b"\n"):
        return
    complete_size = payload.rfind(b"\n") + 1
    with path.open("r+b") as journal:
        journal.truncate(complete_size)


def _require_sha256(value: object, *, field: str, index: int) -> str:
    digest = str(value)
    if len(digest) != 64:
        raise ValueError(f"interaction journal {field} is not SHA-256 at index {index}")
    try:
        bytes.fromhex(digest)
    except ValueError as error:
        raise ValueError(
            f"interaction journal {field} is not SHA-256 at index {index}"
        ) from error
    return digest


def validate_case_parity(
    record: Mapping[str, Any],
    *,
    config: Mapping[str, Any],
) -> None:
    index = int(record["index"])
    candidate = str(config["candidate"])
    if candidate not in SUPPORTED_CANDIDATES:
        raise ValueError(f"unsupported interaction candidate {candidate!r}")
    if record.get("capability_accepted") is not True:
        raise ValueError(f"interaction capability was not accepted at index {index}")
    ticks = int(record.get("ticks_compared", -1))
    expected_ticks = int(config["ticks_per_case"])
    if ticks != expected_ticks:
        raise ValueError(
            "interaction journal tick count mismatch at index "
            f"{index}: expected={expected_ticks} actual={ticks}"
        )
    expected = _require_sha256(
        record.get("expected_state_sha256"),
        field="expected_state_sha256",
        index=index,
    )
    actual = _require_sha256(
        record.get("actual_state_sha256"),
        field="actual_state_sha256",
        index=index,
    )
    combined = _require_sha256(
        record.get("state_sha256"),
        field="state_sha256",
        index=index,
    )
    if expected != actual or combined != expected:
        raise ValueError(f"interaction state mismatch at index {index}")
    if int(record.get("parity_mismatches", -1)) != 0:
        raise ValueError(f"interaction parity mismatch at index {index}")
    if int(record.get("parity_checks", -1)) != ticks:
        raise ValueError(f"interaction parity check count mismatch at index {index}")
    expected_shadow_checks = ticks if candidate == "resident-rust-shadow" else 0
    if int(record.get("shadow_checks", -1)) != expected_shadow_checks:
        raise ValueError(f"interaction shadow check count mismatch at index {index}")
    if int(record.get("shadow_mismatches", -1)) != 0:
        raise ValueError(f"interaction shadow mismatch at index {index}")


def load_journal(
    path: Path,
    *,
    expected_config: Mapping[str, Any],
    expected_fingerprint: str,
    expected_start: int,
    expected_stop: int | None = None,
    repair_partial_tail: bool = False,
) -> LoadedJournal:
    if repair_partial_tail:
        _truncate_partial_tail(path)
    if not path.exists() or path.stat().st_size == 0:
        return LoadedJournal(records=[], sha256_chain="")
    payload = path.read_bytes()
    if not payload.endswith(b"\n"):
        raise ValueError("interaction journal has a partial final record")
    try:
        raw_records = [json.loads(line) for line in payload.splitlines()]
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("interaction journal contains invalid JSON") from error
    header = raw_records[0]
    if header.get("type") != "header":
        raise ValueError("interaction journal does not begin with a header")
    if header.get("fingerprint") != expected_fingerprint:
        raise ValueError(
            "interaction journal fingerprint mismatch: "
            f"expected={expected_fingerprint} actual={header.get('fingerprint')}"
        )
    if header.get("config") != dict(expected_config):
        raise ValueError("interaction journal header configuration mismatch")
    chain = initial_chain(header)
    completed: list[dict[str, Any]] = []
    for local_index, record in enumerate(raw_records[1:]):
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
        chain = chain_next(chain, record_without_chain)
        if recorded_chain != chain:
            raise ValueError(
                f"interaction journal hash-chain mismatch at index {expected_index}"
            )
        validate_case_parity(record, config=expected_config)
        completed.append(record)
    if expected_stop is not None and expected_start + len(completed) != expected_stop:
        raise ValueError(
            "interaction journal range mismatch: "
            f"expected_stop={expected_stop} "
            f"actual_stop={expected_start + len(completed)}"
        )
    return LoadedJournal(records=completed, sha256_chain=chain)


def setup_event_counts(
    records: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
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


def relative_artifact_path(path: Path, *, summary_path: Path) -> str:
    return os.path.relpath(path, start=summary_path.parent)


def resolve_artifact_path(path_text: str, *, summary_path: Path) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return (summary_path.parent / path).resolve()
