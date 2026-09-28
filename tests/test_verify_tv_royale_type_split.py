from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.verify_tv_royale_type_split import (
    REQUIRED_INVARIANTS,
    SPLIT_MINIMUMS,
    TypeDataInsufficient,
    verify_type_split,
)


def _manifest() -> dict[str, object]:
    splits = {
        name: {
            "samples": minimums["samples"],
            "replays": minimums["replays"],
            "deck_signatures": minimums["deck_signatures"],
            "arenas": {
                f"arena_{index}": 1
                for index in range(minimums["distinct_arenas"])
            },
            "archetypes": {
                f"archetype_{index}": 1
                for index in range(minimums["distinct_archetypes"])
            },
        }
        for name, minimums in SPLIT_MINIMUMS.items()
    }
    return {
        "schema_version": 2,
        "source_replays": 2_000,
        "reserved_final_evaluation_replays": 16,
        "total_samples": sum(int(row["samples"]) for row in splits.values()),
        "total_replays": sum(int(row["replays"]) for row in splits.values()),
        "invariants": dict(REQUIRED_INVARIANTS),
        "splits": splits,
    }


def test_accepts_exact_type_split_minimums(tmp_path: Path) -> None:
    path = tmp_path / "split_manifest.json"
    path.write_text(json.dumps(_manifest()))

    report = verify_type_split(path, target_games=2_000)

    assert report["status"] == "type_split_verified"
    assert report["split_metrics"]["chronology_test"]["samples"] == 1_000


def test_reports_collapsed_split_coverage(tmp_path: Path) -> None:
    payload = _manifest()
    validation = payload["splits"]["validation"]  # type: ignore[index]
    validation["samples"] = 1_999  # type: ignore[index]
    validation["arenas"] = {"arena_31": 1}  # type: ignore[index]
    payload["total_samples"] = sum(  # type: ignore[index]
        int(row["samples"])
        for row in payload["splits"].values()  # type: ignore[union-attr]
    )
    path = tmp_path / "split_manifest.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(TypeDataInsufficient) as caught:
        verify_type_split(path, target_games=2_000)

    assert set(caught.value.details["validation"]) == {
        "samples",
        "distinct_arenas",
    }


def test_rejects_wrong_source_count_and_invariant(tmp_path: Path) -> None:
    payload = _manifest()
    payload["source_replays"] = 1_999
    payload["invariants"]["replay_overlap"] = 1  # type: ignore[index]
    path = tmp_path / "split_manifest.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="source replay count mismatch"):
        verify_type_split(path, target_games=2_000)
