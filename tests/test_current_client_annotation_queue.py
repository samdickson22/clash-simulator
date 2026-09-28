from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_current_client_annotation_queue import _apply_decisions

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "reports/current_client_annotation_queue_hTG8dM4KtM4_v1.json"


def _load() -> dict:
    return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))


def test_queue_is_video_grouped_and_proposals_are_not_labels() -> None:
    payload = _load()
    assert payload["schema"] == "clasher.current_client.annotation_queue.v1"
    assert payload["source"]["split"] == "test"
    assert {row["source_group_id"] for row in payload["queue"]} == {
        "youtube:hTG8dM4KtM4"
    }
    assert {row["split"] for row in payload["queue"]} == {"test"}
    assert all(
        row["detector_proposal"]["is_label"] is False for row in payload["queue"]
    )
    assert payload["contracts"]["deck_hud_evidence_is_hint_only"] is True


def test_family_only_candidates_remain_unlabelled() -> None:
    payload = _load()
    family_choices = [
        choice
        for row in payload["queue"]
        for choice in row["candidate_choices"]
        if choice["relationship"] == "root_family_only"
    ]
    assert family_choices
    assert all(
        not choice["may_accept_after_visual_review"] for choice in family_choices
    )
    for row in payload["queue"]:
        if row["review"]["status"] != "accepted":
            continue
        selected = next(
            choice
            for choice in row["candidate_choices"]
            if choice["stable_key"] == row["review"]["accepted_stable_key"]
        )
        assert selected["relationship"] != "root_family_only"


def test_yolo_export_contains_only_visual_acceptances() -> None:
    payload = _load()
    assert payload["counts"]["review"] == {
        "pending": 0,
        "accepted": 4,
        "rejected": 8,
    }
    assert payload["yolo_export"]["accepted"] == 4
    assert payload["yolo_export"]["classes"] == [
        "troop_body:GoblinBrawler",
        "troop_body:Recruit",
    ]
    accepted_ids = {
        row["queue_id"]
        for row in payload["queue"]
        if row["review"]["status"] == "accepted"
    }
    artifacts = payload["yolo_export"]["artifacts"]
    assert {row["queue_id"] for row in artifacts} == accepted_ids
    for row in artifacts:
        image = Path(row["image"])
        label = Path(row["label"])
        assert image.is_file()
        assert label.is_file()
        values = label.read_text(encoding="utf-8").split()
        assert len(values) == 5
        assert int(values[0]) in {0, 1}
        assert all(0.0 <= float(value) <= 1.0 for value in values[1:])


def test_family_only_acceptance_fails_closed(tmp_path: Path) -> None:
    payload = _load()
    row = next(
        row
        for row in payload["queue"]
        if any(
            choice["relationship"] == "root_family_only"
            for choice in row["candidate_choices"]
        )
    )
    family = next(
        choice
        for choice in row["candidate_choices"]
        if choice["relationship"] == "root_family_only"
    )
    decision = {
        "schema": "clasher.current_client.annotation_decisions.v1",
        "decisions": [
            {
                "queue_id": row["queue_id"],
                "status": "accepted",
                "accepted_stable_key": family["stable_key"],
                "reviewer": "test",
                "reason": "must fail",
            }
        ],
    }
    path = tmp_path / "decisions.json"
    path.write_text(json.dumps(decision), encoding="utf-8")
    with pytest.raises(ValueError, match="family-only candidate cannot be accepted"):
        _apply_decisions([row], path)
