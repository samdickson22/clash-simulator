from __future__ import annotations

import pytest

from scripts.evaluate_tv_royale_hud_identity_holdout import summarize


def test_summary_scores_rows_and_event_votes() -> None:
    records = [
        {"label_id": "event-a", "card_identity": "card_action:Arrows"},
        {"label_id": "event-a", "card_identity": "card_action:Arrows"},
        {"label_id": "event-b", "card_identity": "card_action:HogRider"},
    ]
    decisions = [
        {"candidate": "card_action:Arrows", "valid": True, "value": "card_action:Arrows"},
        {"candidate": "card_action:Arrows", "valid": False, "value": None},
        {"candidate": "card_action:Fireball", "valid": True, "value": "card_action:Fireball"},
    ]

    result = summarize(records, decisions)

    assert result["row_candidate_accuracy"] == pytest.approx(2 / 3)
    assert result["row_valid_precision"] == pytest.approx(1 / 2)
    assert result["event_candidate_accuracy"] == pytest.approx(1 / 2)
    assert result["event_candidate_unanimous_precision"] == pytest.approx(1 / 2)
    assert result["event_candidate_unanimous_recall"] == pytest.approx(1 / 2)
    assert result["event_valid_precision"] == pytest.approx(1 / 2)


def test_summary_requires_all_temporal_candidates_to_agree() -> None:
    records = [
        {"label_id": "event", "card_identity": "card_action:Log"},
        {"label_id": "event", "card_identity": "card_action:Log"},
        {"label_id": "event", "card_identity": "card_action:Log"},
    ]
    decisions = [
        {"candidate": "card_action:Log", "valid": False, "value": None},
        {"candidate": "card_action:Log", "valid": False, "value": None},
        {"candidate": "card_action:Arrows", "valid": False, "value": None},
    ]

    result = summarize(records, decisions)

    assert result["event_candidate_accuracy"] == 1.0
    assert result["event_candidate_unanimous"] == 0
    assert result["event_candidate_unanimous_recall"] == 0.0


def test_summary_rejects_misaligned_rows() -> None:
    with pytest.raises(ValueError, match="counts differ"):
        summarize([{"label_id": "event", "card_identity": "card_action:Arrows"}], [])
