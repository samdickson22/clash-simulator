from __future__ import annotations

from scripts.build_tv_royale_hud_identity_holdout import (
    OFFSETS_MS,
    _frame_targets,
    select_unique_slot_events,
)


def test_unique_transition_selects_slot_without_filtering_by_identity() -> None:
    gold = {
        "labels": [
            {
                "label_id": "p0-0001",
                "player_id": 0,
                "timestamp_ms": 2_000,
                "play_valid": True,
                "identity_valid": True,
                "card_identity": "card_action:HogRider",
            },
            {
                "label_id": "p1-0001",
                "player_id": 1,
                "timestamp_ms": 3_000,
                "play_valid": True,
                "identity_valid": True,
                "card_identity": "card_action:Arrows",
            },
        ]
    }
    actions = {
        "labels": [
            {
                "label_id": "p0-0001",
                "identity_candidates": [
                    {"slot": 2, "card_identity": "card_action:RoyalHogs"}
                ],
            },
            {
                "label_id": "p1-0001",
                "identity_candidates": [
                    {"slot": 0, "card_identity": "card_action:Arrows"},
                    {"slot": 3, "card_identity": "card_action:Fireball"},
                ],
            },
        ]
    }

    selected = select_unique_slot_events(gold, actions)

    assert len(selected) == 1
    assert selected[0]["slot"] == 2
    assert selected[0]["card_identity"] == "card_action:HogRider"
    assert selected[0]["transition_agrees_with_gold"] is False


def test_frame_targets_are_strictly_pre_play_and_deterministic() -> None:
    event = {
        "label_id": "p0-0001",
        "player_id": 0,
        "timestamp_ms": 2_000,
        "card_identity": "card_action:HogRider",
        "slot": 2,
    }

    targets = _frame_targets([event], sample_hz=10)

    assert sorted(targets) == [9, 12, 15]
    assert [targets[index][0]["crop_timestamp_ms"] for index in sorted(targets)] == [
        2_000 + offset for offset in OFFSETS_MS
    ]
    assert all(
        row["crop_timestamp_ms"] < event["timestamp_ms"]
        for rows in targets.values()
        for row in rows
    )


def test_reviewed_cycle_join_selects_slot_without_reusing_gold_identity() -> None:
    gold = {
        "labels": [
            {
                "label_id": "p0-0001",
                "player_id": 0,
                "timestamp_ms": 2_000,
                "play_valid": True,
                "identity_valid": True,
                "card_identity": "card_action:HogRider",
            }
        ]
    }
    join = {
        "rows": [
            {
                "label_id": "p0-0001",
                "selected_slot": 3,
                "transition_evidence": "unique_next_enters_changed_slot",
                "gold_identity": "poisoned-and-ignored",
            }
        ]
    }

    selected = select_unique_slot_events(gold, join)

    assert selected[0]["slot"] == 3
    assert selected[0]["transition_candidate"] is None
    assert selected[0]["transition_agrees_with_gold"] is None
