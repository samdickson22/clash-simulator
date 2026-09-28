import json
from pathlib import Path

from scripts.apply_reviewed_deck_to_cycle_events import apply_reviewed_deck


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_reviewed_deck_filter_can_only_remove_identity(tmp_path: Path) -> None:
    events = tmp_path / "events.json"
    decks = tmp_path / "decks.json"
    output = tmp_path / "output.json"
    _write(
        events,
        {
            "schema": "clasher.youtube.hud_cycle_events.v3",
            "video_sha256": "abc",
            "contract": {"deck_closure": "unconstrained_diagnostic"},
            "counts": {"identity_valid": 2, "complete_identity_and_placement": 2},
            "events": [
                {
                    "player_id": 0,
                    "card_identity": "card_action:A",
                    "identity_valid": True,
                    "identity_reason": None,
                    "placement_valid": True,
                },
                {
                    "player_id": 1,
                    "card_identity": "card_action:Wrong",
                    "identity_valid": True,
                    "identity_reason": None,
                    "placement_valid": True,
                },
                {
                    "player_id": 0,
                    "card_identity": None,
                    "identity_valid": False,
                    "identity_reason": "public_elixir_cost_mismatch",
                    "placement_valid": True,
                },
            ],
        },
    )
    _write(
        decks,
        {
            "schema": "clasher.youtube.reviewed_public_decks.v1",
            "video_sha256": "abc",
            "players": {
                "0": {
                    "card_identities": [f"card_action:{name}" for name in "ABCDEFGH"]
                },
                "1": {
                    "card_identities": [f"card_action:{name}" for name in "IJKLMNOP"]
                },
            },
        },
    )
    result = apply_reviewed_deck(events, decks, output)
    assert result["events"][0]["card_identity"] == "card_action:A"
    assert result["events"][1]["card_identity"] is None
    assert result["events"][1]["identity_reason"] == "outside_reviewed_public_deck"
    assert result["events"][2]["identity_reason"] == "public_elixir_cost_mismatch"
    assert result["counts"]["identity_valid"] == 1
    assert result["counts"]["complete_identity_and_placement"] == 1
    assert result["counts"]["outside_reviewed_deck_filtered"] == 1
    assert result["contract"]["deck_closure_operation"] == "removal_only_postfilter"
