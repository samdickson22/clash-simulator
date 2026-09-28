from __future__ import annotations

import copy
from pathlib import Path

from scripts.build_tv_royale_youtube_fullmatch_masks import (
    ACTOR_SCHEMA,
    NOOP_ACTION,
    build_actor_mask,
    build_public_mask_builder,
    compact_actor_record,
    expand_actor_overlay,
    normalize_offline_events,
)

ROOT = Path(__file__).resolve().parents[1]


def _head(value: str, *, score: float = 0.9) -> dict[str, object]:
    return {
        "value": value,
        "candidate": value,
        "score": score,
        "runner_up_score": 0.1,
        "margin": max(0.0, score - 0.1),
        "valid": True,
        "reason": None,
    }


def _record(*, score: float = 0.9) -> dict[str, object]:
    hand = [
        _head("card_action:Knight", score=score),
        _head("card_action:Arrows", score=score),
        _head("card_action:BabyDragon", score=score),
        _head("card_action:Tombstone", score=score),
    ]
    hud = {
        "hand": hand,
        "next_card": _head("card_action:Tornado", score=score),
        "elixir": {
            "value": 10.0,
            "candidate": 10.0,
            "score": score,
            "runner_up_score": 0.0,
            "margin": score,
            "valid": True,
            "reason": None,
        },
        "all_hand_valid": True,
        "complete_valid": True,
    }
    return {
        "public": {"entities": []},
        "offline_privileged_hud": {"0": copy.deepcopy(hud), "1": copy.deepcopy(hud)},
        "offline_evidence": {"play_events": []},
    }


def test_mask_is_nontrivial_and_invariant_to_offline_targets() -> None:
    builder, mask_builder = build_public_mask_builder(
        ROOT / "reports/current_client_youtube_stable_vocabulary_v1.json"
    )
    record = _record()
    before = build_actor_mask(
        record, actor_id=0, builder=builder, mask_builder=mask_builder
    )
    mutated = copy.deepcopy(record)
    mutated["offline_evidence"] = {
        "play_events": [
            {
                "expert_action": 123,
                "card_identity": "card_action:RoyalGiant",
                "deployment_tile_actor_canonical": [17, 31],
            }
        ]
    }
    after = build_actor_mask(
        mutated, actor_id=0, builder=builder, mask_builder=mask_builder
    )
    assert before == after
    assert before["contract"] == "label_independent_public_action_mask_v2"
    assert before["contract_version"] == 2
    assert before["non_noop_legal_actions"] > 0
    assert NOOP_ACTION in before["legal_action_indices"]


def test_zero_card_confidence_fails_closed_even_with_nonzero_identity() -> None:
    builder, mask_builder = build_public_mask_builder(
        ROOT / "reports/current_client_youtube_stable_vocabulary_v1.json"
    )
    mask = build_actor_mask(
        _record(score=0.0), actor_id=1, builder=builder, mask_builder=mask_builder
    )
    assert mask["legal_action_indices"] == [NOOP_ACTION]
    assert mask["non_noop_legal_actions"] == 0


def test_compact_actor_overlay_round_trips_against_neutral_state() -> None:
    neutral = {
        "match_id": "match",
        "split_group_id": "match",
        "snapshot_id": "match-2",
        "output_pts": 2,
        "output_time_base": "1/10",
        "source_time_base": "1/1000",
        "timestamp_ms": 200,
        "public": {"entities": [{"identity": "public"}]},
    }
    full = {
        "schema": ACTOR_SCHEMA,
        **{key: neutral[key] for key in neutral if key != "public"},
        "actor_id": 1,
        "public": copy.deepcopy(neutral["public"]),
        "own_hud": {"hand": []},
        "public_action_mask": {"legal_action_indices": [NOOP_ACTION]},
        "label_validity": {"hand": []},
    }

    compact = compact_actor_record(full)
    restored = expand_actor_overlay(compact, neutral)

    assert restored == full
    assert "public" not in compact
    assert "match_id" not in compact


def test_cycle_events_require_every_independent_target_gate() -> None:
    accepted = {
        "event_id": "cycle-1",
        "play_confirmed": True,
        "identity_valid": True,
        "placement_valid": True,
        "public_cost_valid": True,
        "offline_label_only": True,
    }
    payload = {
        "schema": "clasher.youtube.hud_cycle_events.v3",
        "events": [
            accepted,
            {**accepted, "event_id": "cycle-2", "public_cost_valid": False},
            {**accepted, "event_id": "cycle-3", "placement_valid": False},
        ],
    }

    rows, source = normalize_offline_events(payload)

    assert source == "precision_gated_hud_cycle_events_v3"
    assert [row["play_valid"] for row in rows] == [True, False, False]
    assert "play_valid" not in accepted


def test_cycle_event_normalization_rejects_unknown_schema() -> None:
    try:
        normalize_offline_events({"schema": "unknown", "events": []})
    except ValueError as error:
        assert str(error) == "unsupported offline event payload"
    else:
        raise AssertionError("unknown offline event schema did not fail closed")
