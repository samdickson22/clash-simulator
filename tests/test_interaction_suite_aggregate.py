from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import aggregate_interaction_shards as aggregate_module
from scripts.interaction_journal import (
    canonical_bytes,
    chain_next,
    fingerprint,
    initial_chain,
    journal_header,
)

aggregate_summaries = aggregate_module.aggregate_summaries


@pytest.fixture(autouse=True)
def _small_expected_total(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aggregate_module, "_expected_total", lambda kind: 4)


def _refresh_fingerprint(summary: dict[str, object]) -> None:
    summary["fingerprint"] = fingerprint(
        {field: summary[field] for field in aggregate_module.SHARD_CONFIG_FIELDS}
    )


def _write_shard(
    root: Path,
    *,
    shard_index: int,
    shard_count: int,
    start: int,
    stop: int,
    kind: str = "1v1",
    limit: int | None = None,
    ticks: int = 8,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    journal = root / f"shard-{shard_index}.jsonl"
    config = {
        "candidate": "resident-rust-shadow",
        "cards_sha256": "cards",
        "decks_sha256": "decks",
        "gamedata_sha256": "gamedata",
        "interaction_manifest_sha256": "manifest",
        "journal_schema_version": 2,
        "kind": kind,
        "provenance": {
            "git_head": "head",
            "source_bundle_sha256": "source",
        },
        "semantic_event_trace_schema_version": None,
        "seed": 1,
        "shard_count": shard_count,
        "shard_index": shard_index,
        "shard_start": start,
        "shard_stop": stop,
        "state_schema": {"name": "resident-semantic", "version": 1},
        "ticks_per_case": ticks,
        "limit": limit,
    }
    config_fingerprint = fingerprint(config)
    header = journal_header(config, config_fingerprint=config_fingerprint)
    chain = initial_chain(header)
    records: list[dict[str, object]] = []
    for index in range(start, stop):
        digest = hashlib.sha256(str(index).encode()).hexdigest()
        record_without_chain: dict[str, object] = {
            "actual_state_sha256": digest,
            "capability_accepted": True,
            "event_applied": True,
            "event_family": "ordinary",
            "expected_state_sha256": digest,
            "index": index,
            "parity_checks": ticks,
            "parity_mismatches": 0,
            "shadow_checks": ticks,
            "shadow_mismatches": 0,
            "state_sha256": digest,
            "ticks_compared": ticks,
            "type": "case",
        }
        chain = chain_next(chain, record_without_chain)
        records.append({**record_without_chain, "chain_sha256": chain})
    journal.write_bytes(
        b"\n".join(
            [canonical_bytes(header), *(canonical_bytes(record) for record in records)]
        )
        + b"\n"
    )
    summary = {
        **config,
        "cases_run": stop - start,
        "coverage_is_full_shard": limit is None,
        "event_counts": {
            "ordinary": {
                "attempted": stop - start,
                "applied": stop - start,
                "no_op": 0,
            }
        },
        "event_counts_scope": "scenario-setup-only",
        "fingerprint": config_fingerprint,
        "journal_path": journal.name,
        "journal_sha256": hashlib.sha256(journal.read_bytes()).hexdigest(),
        "semantic_event_tracing": "deferred",
        "sha256_chain": chain,
        "shadow_checks": (stop - start) * ticks,
        "shadow_mismatches": 0,
        "status": "complete",
    }
    path = root / f"shard-{shard_index}.json"
    path.write_text(json.dumps(summary))
    return path


def _complete_one_v_one(tmp_path: Path) -> list[Path]:
    return [
        _write_shard(
            tmp_path,
            shard_index=0,
            shard_count=2,
            start=0,
            stop=2,
        ),
        _write_shard(
            tmp_path,
            shard_index=1,
            shard_count=2,
            start=2,
            stop=4,
        ),
    ]


def test_aggregate_accepts_exact_full_coverage(tmp_path: Path) -> None:
    payload = aggregate_summaries(_complete_one_v_one(tmp_path))

    assert payload["status"] == "complete"
    assert payload["cases_run"] == 4
    assert payload["coverage_is_exhaustive_within_declared_horizon"] is True
    assert payload["event_counts"]["ordinary"] == {
        "applied": 4,
        "attempted": 4,
        "no_op": 0,
    }
    assert "8-tick horizon" in payload["coverage_claim"]


def test_aggregate_rejects_duplicate_shard_indices(tmp_path: Path) -> None:
    first = _write_shard(
        tmp_path / "first",
        shard_index=0,
        shard_count=2,
        start=0,
        stop=2,
    )
    second = _write_shard(
        tmp_path / "second",
        shard_index=0,
        shard_count=2,
        start=2,
        stop=4,
    )

    with pytest.raises(ValueError, match="duplicate interaction shard index"):
        aggregate_summaries([first, second])


def test_aggregate_rejects_range_gap(tmp_path: Path) -> None:
    paths = [
        _write_shard(
            tmp_path,
            shard_index=0,
            shard_count=2,
            start=0,
            stop=2,
        ),
        _write_shard(
            tmp_path,
            shard_index=1,
            shard_count=2,
            start=3,
            stop=4,
        ),
    ]

    with pytest.raises(ValueError, match="range gap or overlap"):
        aggregate_summaries(paths)


def test_aggregate_rejects_mixed_configuration(tmp_path: Path) -> None:
    paths = [
        _write_shard(
            tmp_path,
            shard_index=0,
            shard_count=2,
            start=0,
            stop=2,
        ),
        _write_shard(
            tmp_path,
            shard_index=1,
            shard_count=2,
            start=2,
            stop=4,
            ticks=9,
        ),
    ]

    with pytest.raises(ValueError, match="mixed interaction shard configuration"):
        aggregate_summaries(paths)


def test_aggregate_rejects_invalid_shard_fingerprint(tmp_path: Path) -> None:
    paths = _complete_one_v_one(tmp_path)
    second = json.loads(paths[1].read_text())
    second["fingerprint"] = "stale"
    paths[1].write_text(json.dumps(second))

    with pytest.raises(ValueError, match="shard fingerprint mismatch"):
        aggregate_summaries(paths)


def test_aggregate_rejects_sampled_shard(tmp_path: Path) -> None:
    paths = _complete_one_v_one(tmp_path)
    second = json.loads(paths[1].read_text())
    second["limit"] = 1
    second["coverage_is_full_shard"] = False
    _refresh_fingerprint(second)
    paths[1].write_text(json.dumps(second))

    with pytest.raises(ValueError, match="sampled shard"):
        aggregate_summaries(paths)


def test_aggregate_rejects_journal_tampering(tmp_path: Path) -> None:
    paths = _complete_one_v_one(tmp_path)
    second = json.loads(paths[1].read_text())
    (paths[1].parent / str(second["journal_path"])).write_text("tampered\n")

    with pytest.raises(ValueError, match="journal hash mismatch"):
        aggregate_summaries(paths)


def test_aggregate_revalidates_journal_hash_chain(tmp_path: Path) -> None:
    paths = _complete_one_v_one(tmp_path)
    summary = json.loads(paths[1].read_text())
    journal = paths[1].parent / str(summary["journal_path"])
    lines = journal.read_text().splitlines()
    record = json.loads(lines[1])
    record["event_applied"] = False
    lines[1] = json.dumps(record, sort_keys=True, separators=(",", ":"))
    journal.write_text("\n".join(lines) + "\n")
    summary["journal_sha256"] = hashlib.sha256(journal.read_bytes()).hexdigest()
    paths[1].write_text(json.dumps(summary))

    with pytest.raises(ValueError, match="hash-chain mismatch"):
        aggregate_summaries(paths)


def test_aggregate_resolves_journal_relative_to_moved_summary(
    tmp_path: Path,
) -> None:
    original = tmp_path / "original"
    original.mkdir()
    paths = _complete_one_v_one(original)
    moved = tmp_path / "moved"
    original.rename(moved)

    payload = aggregate_summaries([moved / path.name for path in paths])

    assert payload["status"] == "complete"
    assert payload["cases_run"] == 4


def test_aggregate_rejects_valid_chain_with_shadow_mismatch(tmp_path: Path) -> None:
    paths = _complete_one_v_one(tmp_path)
    summary = json.loads(paths[1].read_text())
    journal = paths[1].parent / str(summary["journal_path"])
    parsed = [json.loads(line) for line in journal.read_text().splitlines()]
    header, records = parsed[0], parsed[1:]
    records[0]["shadow_mismatches"] = 1
    chain = initial_chain(header)
    rewritten: list[dict[str, object]] = []
    for record in records:
        without_chain = dict(record)
        without_chain.pop("chain_sha256")
        chain = chain_next(chain, without_chain)
        rewritten.append({**without_chain, "chain_sha256": chain})
    journal.write_bytes(
        b"\n".join(
            [
                canonical_bytes(header),
                *(canonical_bytes(record) for record in rewritten),
            ]
        )
        + b"\n"
    )
    summary["journal_sha256"] = hashlib.sha256(journal.read_bytes()).hexdigest()
    summary["sha256_chain"] = chain
    summary["shadow_mismatches"] = 1
    paths[1].write_text(json.dumps(summary))

    with pytest.raises(ValueError, match="shadow mismatch"):
        aggregate_summaries(paths)
