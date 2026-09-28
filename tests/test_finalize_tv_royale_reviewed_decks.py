from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.finalize_tv_royale_reviewed_decks import finalize_reviewed_decks


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_finalizes_video_bound_current_client_review(tmp_path: Path) -> None:
    cards = [f"card_action:Card{index}" for index in range(16)]
    decisions = tmp_path / "decisions.json"
    vocabulary = tmp_path / "vocabulary.json"
    sheets = tmp_path / "sheets"
    output = tmp_path / "reviewed"
    _write_json(
        decisions,
        {
            "schema": "clasher.youtube.reviewed_deck_decisions.v1",
            "review_contract": {"ambiguous_slots": 0},
            "games": {"video": {"0": cards[:8], "1": cards[8:]}},
        },
    )
    _write_json(
        vocabulary,
        {
            "entries": [
                {
                    "namespace": "card_action",
                    "stable_key": card,
                    "policy_token_eligible": True,
                }
                for card in cards
            ]
        },
    )
    _write_json(
        sheets / "video" / "manifest.json",
        {
            "schema": "clasher.youtube.eight_card_deck_sheet.v1",
            "video_id": "video",
            "video_sha256": "video-sha",
            "artifact": {"sha256": "sheet-sha"},
            "players": {"0": {"cards_exposed": 8}, "1": {"cards_exposed": 8}},
        },
    )

    index = finalize_reviewed_decks(
        decisions_path=decisions,
        sheets_root=sheets,
        vocabulary_path=vocabulary,
        output_dir=output,
    )

    assert index["reviewed_games"] == 1
    payload = json.loads((output / "video.json").read_text(encoding="utf-8"))
    assert payload["video_sha256"] == "video-sha"
    assert payload["review_contract"]["sheet_artifact_sha256"] == "sheet-sha"


def test_rejects_unknown_or_duplicate_cards(tmp_path: Path) -> None:
    decisions = tmp_path / "decisions.json"
    vocabulary = tmp_path / "vocabulary.json"
    sheets = tmp_path / "sheets"
    cards = [f"card_action:Card{index}" for index in range(8)]
    _write_json(
        decisions,
        {
            "schema": "clasher.youtube.reviewed_deck_decisions.v1",
            "review_contract": {},
            "games": {"video": {"0": cards, "1": cards}},
        },
    )
    _write_json(vocabulary, {"entries": []})
    _write_json(
        sheets / "video" / "manifest.json",
        {
            "schema": "clasher.youtube.eight_card_deck_sheet.v1",
            "video_id": "video",
            "video_sha256": "video-sha",
            "artifact": {"sha256": "sheet-sha"},
            "players": {"0": {"cards_exposed": 8}, "1": {"cards_exposed": 8}},
        },
    )

    with pytest.raises(ValueError, match="unknown current-client identities"):
        finalize_reviewed_decks(
            decisions_path=decisions,
            sheets_root=sheets,
            vocabulary_path=vocabulary,
            output_dir=tmp_path / "reviewed",
        )
