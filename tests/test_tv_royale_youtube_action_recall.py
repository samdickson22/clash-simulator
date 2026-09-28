from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.build_tv_royale_youtube_action_recall import build_labels
from scripts.build_tv_royale_youtube_visible_cost_gate import _apply_gate


def _head(value: Any, *, valid: bool = True) -> dict[str, Any]:
    return {"value": value, "valid": valid, "score": 1.0}


def _row(index: int) -> dict[str, Any]:
    before = index < 60
    hand = [
        _head("card_action:A" if before else "card_action:N"),
        _head("card_action:B"),
        _head("card_action:C"),
        _head("card_action:D"),
    ]
    next_card = _head("card_action:N" if before else "card_action:Z")
    elixir = _head(5.0 if before else 2.0)
    hud = {
        "hand": hand,
        "next_card": next_card,
        "elixir": elixir,
        "all_hand_valid": True,
        "complete_valid": True,
    }
    return {
        "timestamp_ms": index * 100,
        "offline_privileged_hud": {"0": hud, "1": json.loads(json.dumps(hud))},
        "public": {"entities": []},
    }


def test_next_rotation_identifies_played_slot_for_both_hud_orientations(
    tmp_path: Path,
) -> None:
    vocabulary = tmp_path / "vocabulary.json"
    vocabulary.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "namespace": "card_action",
                        "stable_key": "card_action:A",
                        "mana_cost": 3,
                    }
                ]
            }
        )
    )

    labels = build_labels([_row(index) for index in range(120)], vocabulary)

    assert len(labels) == 2
    assert {label["player_id"] for label in labels} == {0, 1}
    for label in labels:
        assert label["card_identity"] == "card_action:A"
        assert label["identity_valid"] is True
        assert label["identity_evidence"].endswith("next_rotation")
        assert label["next_rotation_evidence"] == {
            "before": "card_action:N",
            "after": "card_action:Z",
            "before_observations": 12,
            "after_observations": 16,
            "label_only_future_confirmed": True,
            "actor_input": False,
        }


def test_visible_cost_gate_keeps_offline_evidence_out_of_hud_heads() -> None:
    row = _row(0)
    evidence = {"card_action:A": {"official_cost": 5, "quarantined": True}}

    counts = _apply_gate([row], evidence, {"card_action:A"})

    assert counts == {"p0_rejected": 1, "p1_rejected": 1}
    for player_id in ("0", "1"):
        head = row["offline_privileged_hud"][player_id]["hand"][0]
        assert head["valid"] is False
        assert head["value"] is None
        assert head["reason"] == "visible_cost_family_mismatch"
        assert "visible_cost_family_evidence" not in head
        assert "label_only_future_confirmed" not in head
