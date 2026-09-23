import json
from pathlib import Path

import pytest

from clasher.rl.replay_validation import (
    compare_interactions,
    derive_interactions,
    load_public_trace,
)


def _write_trace(path: Path, *, damage: float = 100.0, x: float = 3.5) -> None:
    frames = [
        {
            "schema_version": 1,
            "timestamp_ms": 0,
            "towers": {"0.left": 3000.0},
            "entities": [],
        },
        {
            "schema_version": 1,
            "timestamp_ms": 100,
            "towers": {"0.left": 3000.0},
            "entities": [
                {
                    "track_id": "enemy-1",
                    "player_id": 1,
                    "card": "Knight",
                    "x": x,
                    "y": 9.5,
                    "hp": 690.0,
                }
            ],
        },
        {
            "schema_version": 1,
            "timestamp_ms": 200,
            "towers": {"0.left": 3000.0 - damage},
            "entities": [
                {
                    "track_id": "enemy-1",
                    "player_id": 1,
                    "card": "Knight",
                    "x": x,
                    "y": 8.5,
                    "hp": 600.0,
                }
            ],
        },
        {
            "schema_version": 1,
            "timestamp_ms": 300,
            "towers": {"0.left": 3000.0 - damage},
            "entities": [],
        },
    ]
    path.write_text("\n".join(json.dumps(frame) for frame in frames), encoding="utf-8")


def test_trace_derives_public_interactions_and_matches_within_tolerance(tmp_path: Path):
    observed_path = tmp_path / "observed.jsonl"
    simulated_path = tmp_path / "simulated.jsonl"
    _write_trace(observed_path)
    _write_trace(simulated_path, damage=103.0, x=3.7)

    observed = derive_interactions(load_public_trace(observed_path))
    simulated = derive_interactions(load_public_trace(simulated_path))
    report = compare_interactions(observed, simulated)

    assert [event.kind for event in observed] == [
        "spawn",
        "unit_damage",
        "tower_damage",
        "death_or_hidden",
    ]
    assert report["summary"]["exact_within_tolerance"] is True
    assert report["summary"]["match_rate"] == 1.0


def test_trace_report_preserves_numeric_mismatch_evidence(tmp_path: Path):
    observed_path = tmp_path / "observed.jsonl"
    simulated_path = tmp_path / "simulated.jsonl"
    _write_trace(observed_path)
    _write_trace(simulated_path, damage=160.0, x=7.0)

    report = compare_interactions(
        derive_interactions(load_public_trace(observed_path)),
        derive_interactions(load_public_trace(simulated_path)),
    )

    assert report["summary"]["exact_within_tolerance"] is False
    assert any(item["type"] == "value_mismatch" for item in report["mismatches"])


def test_trace_rejects_non_monotonic_timestamps(tmp_path: Path):
    path = tmp_path / "bad.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"timestamp_ms": 10, "entities": []}),
                json.dumps({"timestamp_ms": 10, "entities": []}),
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="timestamps must increase"):
        load_public_trace(path)
