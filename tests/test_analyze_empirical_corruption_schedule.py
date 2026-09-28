from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

import numpy as np

from scripts.analyze_empirical_corruption_schedule import (
    _load_jsonl_gz,
    _markdown,
    build_analysis,
)


def _entity(
    key: str | None,
    *,
    team: int = 0,
    confidence: float = 0.8,
    hp_valid: bool = False,
    x: float = 5.0,
    y: float = 10.0,
) -> dict[str, Any]:
    return {
        "confidence": confidence,
        "hp_confidence": 0.7 if hp_valid else 0.0,
        "hp_valid": hp_valid,
        "identity": {"stable_key": key, "valid": key is not None},
        "team_id": team,
        "world_position": [x, y],
    }


def _hud(
    valid: tuple[bool, bool, bool, bool], *, next_valid: bool, elixir_valid: bool
) -> dict[str, Any]:
    return {
        "hand": [{"valid": item, "score": 0.9 if item else 0.2} for item in valid],
        "next_card": {"valid": next_valid, "score": 0.8 if next_valid else 0.1},
        "elixir": {"valid": elixir_valid, "score": 1.0 if elixir_valid else 0.0},
    }


def _write_corpus(path: Path) -> None:
    np.savez_compressed(
        path,
        entity_mask=np.asarray([[True, False], [True, True]], dtype=np.bool_),
        hand_ids=np.asarray([[1, 2, 3, 4, 5], [1, 0, 3, 4, 0]], dtype=np.int64),
        episode_ids=np.asarray([0, 0], dtype=np.int64),
        episode_starts=np.asarray([True, False], dtype=np.bool_),
        expert_actions=np.asarray([99, 100], dtype=np.int64),
    )


def test_analysis_preserves_evidence_bounds_and_never_consumes_targets(
    tmp_path: Path,
) -> None:
    live_rows = [
        {
            "sample_index": 0,
            "timestamp_ms": 0,
            "public": {"entities": [_entity("tower:Tower", hp_valid=True)]},
            "offline_privileged_hud": {
                "0": _hud((True, True, True, True), next_valid=True, elixir_valid=True),
                "1": _hud(
                    (False, True, True, True), next_valid=False, elixir_valid=True
                ),
            },
        },
        {
            "sample_index": 1,
            "timestamp_ms": 1000,
            "public": {
                "entities": [
                    _entity("tower:Tower", hp_valid=False, x=5.1),
                    _entity("troop_body:Knight", team=1, x=8.0),
                    _entity(None, confidence=0.3),
                ]
            },
            "offline_privileged_hud": {
                "0": _hud(
                    (True, False, True, True), next_valid=True, elixir_valid=False
                ),
                "1": _hud((True, True, True, True), next_valid=True, elixir_valid=True),
            },
        },
    ]
    clock_rows = [
        {"sample_index": 0, "public": {"clock": {"valid": True, "confidence": 0.9}}},
        {"sample_index": 1, "public": {"clock": {"valid": False, "confidence": 0.0}}},
    ]
    gold = {
        "labels": [
            {
                "label_id": "a",
                "identity_valid": True,
                "card_identity": "card_action:Knight",
                "placement_valid": True,
                "deployment_tile_absolute": [4, 5],
            },
            {
                "label_id": "b",
                "identity_valid": True,
                "card_identity": "card_action:Arrows",
                "placement_valid": False,
            },
        ]
    }
    predicted = {
        "labels": [
            {
                "label_id": "a",
                "identity_valid": True,
                "card_identity": "card_action:Knight",
                "deployment_tile_absolute": [4, 5],
            },
            {"label_id": "b", "identity_valid": False, "card_identity": None},
        ]
    }
    decisions = {
        "decisions": [
            {"queue_id": "ok", "status": "accepted", "reason": "clear"},
            {
                "queue_id": "bad",
                "status": "rejected",
                "reason": "visible unit does not visually prove suggested family",
            },
        ]
    }
    corpus = tmp_path / "corpus.npz"
    _write_corpus(corpus)
    report = build_analysis(
        live_rows,
        clock_rows,
        gold,
        predicted,
        decisions,
        [corpus],
        {"fixture": "synthetic"},
    )

    assert report["schedule"]["status"] == "bounded_one_replay_diagnostic_only"
    assert report["schedule"]["transform"]["identity_substitution"] == "disabled"
    assert report["measurements"]["entity"]["miss_rate_status"].startswith(
        "unavailable"
    )
    assert report["measurements"]["manual_gold"]["card_identity_accepted_gold"] == {
        "accuracy": 0.5,
        "correct": 1,
        "gold": 2,
        "missed": 1,
        "scope": "Only manually accepted identities count as ground truth; withheld labels are not negatives.",
        "wrong_details": [],
        "wrong_identity": 0,
    }
    assert report["clean_simulator_corpora"][0]["target_arrays_consumed"] == []
    assert (
        "expert_actions" not in report["clean_simulator_corpora"][0]["arrays_consumed"]
    )
    assert len(report["measurements"]["co_missingness"]["strata"]) == 2
    assert "No entity, HP" in str(report["decision"])


def test_jsonl_loading_and_markdown_are_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "rows.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write(json.dumps({"sample_index": 0}) + "\n")
    assert _load_jsonl_gz(path) == [{"sample_index": 0}]

    report = {
        "schema": "analysis",
        "decision": "bounded",
        "measurements": {
            "entity": {"typed_identity_rate_per_detection": 0.5},
            "hp": {"valid_rate_per_detection": 0.25},
            "tower": {"hp_valid_rate": 0.75},
            "clock": {"valid_rate": 0.8},
            "card_hud": {
                "hand_slot_valid_rate": [0.1, 0.2, 0.3, 0.4],
                "next_valid_rate": 0.5,
            },
            "elixir": {"valid_rate": 0.6},
            "manual_gold": {
                "card_identity_accepted_gold": {"correct": 1, "gold": 2, "missed": 1},
                "deployment_tile_accepted_gold": {"exact": 3, "gold": 4},
            },
        },
        "schedule": {
            "status": "diagnostic",
            "schema": "schedule",
            "pattern_rows_sha256": "abc",
            "sampling": {"application_probability": 1.0},
            "disabled_insufficient_evidence": {"hp_noise": "no gold"},
        },
    }
    assert _markdown(report) == _markdown(report)
    assert "`hp_noise`: no gold." in _markdown(report)
