from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.aggregate_interaction_shards import aggregate_summaries


def _fingerprint(config: dict[str, object]) -> str:
    payload = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _refresh_fingerprint(summary: dict[str, object]) -> None:
    config_fields = (
        "candidate",
        "cards_sha256",
        "journal_schema_version",
        "kind",
        "seed",
        "shard_count",
        "ticks_per_case",
        "limit",
        "shard_index",
        "shard_start",
        "shard_stop",
    )
    summary["fingerprint"] = _fingerprint(
        {field: summary[field] for field in config_fields}
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
) -> Path:
    journal = root / f"shard-{shard_index}.jsonl"
    journal.write_text(f"shard {shard_index}\n")
    config = {
        "candidate": "resident-rust",
        "cards_sha256": "cards",
        "journal_schema_version": 1,
        "kind": kind,
        "seed": 1,
        "shard_count": shard_count,
        "shard_index": shard_index,
        "shard_start": start,
        "shard_stop": stop,
        "ticks_per_case": 8,
        "limit": limit,
    }
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
        "fingerprint": _fingerprint(config),
        "journal_path": str(journal),
        "journal_sha256": hashlib.sha256(journal.read_bytes()).hexdigest(),
        "sha256_chain": f"chain-{shard_index}",
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
            stop=4232,
        ),
        _write_shard(
            tmp_path,
            shard_index=1,
            shard_count=2,
            start=4232,
            stop=8464,
        ),
    ]


def test_aggregate_accepts_exact_full_coverage(tmp_path: Path) -> None:
    payload = aggregate_summaries(_complete_one_v_one(tmp_path))

    assert payload["status"] == "complete"
    assert payload["cases_run"] == 8464
    assert payload["coverage_is_exhaustive_within_declared_horizon"] is True
    assert payload["event_counts"]["ordinary"] == {
        "applied": 8464,
        "attempted": 8464,
        "no_op": 0,
    }
    assert "8-tick horizon" in payload["coverage_claim"]


def test_aggregate_rejects_duplicate_shard_indices(tmp_path: Path) -> None:
    paths = _complete_one_v_one(tmp_path)
    duplicate = json.loads(paths[1].read_text())
    duplicate["shard_index"] = 0
    _refresh_fingerprint(duplicate)
    paths[1].write_text(json.dumps(duplicate))

    with pytest.raises(ValueError, match="duplicate interaction shard index"):
        aggregate_summaries(paths)


def test_aggregate_rejects_range_gap(tmp_path: Path) -> None:
    paths = _complete_one_v_one(tmp_path)
    second = json.loads(paths[1].read_text())
    second["shard_start"] = 4233
    second["cases_run"] = second["shard_stop"] - second["shard_start"]
    _refresh_fingerprint(second)
    paths[1].write_text(json.dumps(second))

    with pytest.raises(ValueError, match="range gap or overlap"):
        aggregate_summaries(paths)


def test_aggregate_rejects_mixed_configuration(tmp_path: Path) -> None:
    paths = _complete_one_v_one(tmp_path)
    second = json.loads(paths[1].read_text())
    second["ticks_per_case"] = 9
    paths[1].write_text(json.dumps(second))

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
    Path(second["journal_path"]).write_text("tampered\n")

    with pytest.raises(ValueError, match="journal hash mismatch"):
        aggregate_summaries(paths)
