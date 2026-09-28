from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from scripts.extract_tv_royale_hud_cycle_events import (
    CycleCandidate,
    _associate_placement,
    _load_reviewed_decks,
    _observed_elixir_drop,
    _play_confirmed,
    _unanimous_preplay_identity,
    detect_cycle_candidates,
    detect_visual_cycle_candidates,
)


def test_detects_one_stable_hand_next_cycle_without_marker() -> None:
    states = np.zeros((30, 2, 5), dtype=np.int16)
    states[:, 0] = [10, 11, 12, 13, 14]
    states[:, 1] = [20, 21, 22, 23, 24]
    states[15:, 0] = [10, 11, 14, 15, 16]
    similarities = np.full(states.shape, 0.9, dtype=np.float32)

    candidates = detect_cycle_candidates(states, similarities, sample_hz=10)

    assert len(candidates) == 1
    assert candidates[0].player_id == 0
    assert candidates[0].selected_slot == 2
    assert candidates[0].selected_cluster == 12


def test_rejects_unconfirmed_multi_slot_visual_change() -> None:
    states = np.zeros((30, 2, 5), dtype=np.int16)
    states[:, 0] = [10, 11, 12, 13, 14]
    states[:, 1] = [20, 21, 22, 23, 24]
    states[15:, 0] = [99, 98, 12, 13, 14]
    similarities = np.full(states.shape, 0.9, dtype=np.float32)

    assert detect_cycle_candidates(states, similarities, sample_hz=10) == []


def test_deduplicates_each_players_simultaneous_transition_independently() -> None:
    states = np.zeros((30, 2, 5), dtype=np.int16)
    states[:, 0] = [10, 11, 12, 13, 14]
    states[:, 1] = [20, 21, 22, 23, 24]
    states[15:, 0] = [10, 11, 14, 15, 16]
    states[15:, 1] = [20, 24, 25, 26, 27]
    similarities = np.full(states.shape, 0.9, dtype=np.float32)

    candidates = detect_cycle_candidates(states, similarities, sample_hz=10)

    assert [(row.player_id, row.selected_cluster) for row in candidates] == [
        (0, 12),
        (1, 21),
    ]


def test_placement_is_independent_and_fails_closed_when_ambiguous() -> None:
    candidate = CycleCandidate(
        1, 100, 2, 31, 0.9, "unique_next_enters_changed_slot"
    )
    placement = {
        "player_id": 1,
        "timestamp_ms": 10_050,
        "placement_valid": True,
    }
    selected, reason = _associate_placement(
        candidate, [placement], sample_hz=10
    )
    assert selected is placement
    assert reason is None

    selected, reason = _associate_placement(
        candidate,
        [
            {**placement, "timestamp_ms": 9_950},
            {**placement, "timestamp_ms": 10_050},
        ],
        sample_hz=10,
    )
    assert selected is None
    assert reason == "ambiguous_equidistant_in_grid_markers"


def test_fallback_cycle_requires_independent_marker_but_next_cycle_does_not() -> None:
    next_confirmed = CycleCandidate(
        0, 100, 2, 6, 0.9, "unique_next_enters_changed_slot"
    )
    fallback = CycleCandidate(
        0, 100, 2, 6, 0.9, "unique_changed_slot_without_next_confirmation"
    )
    placement = {"placement_valid": True}

    assert _play_confirmed(next_confirmed, None)
    assert not _play_confirmed(fallback, None)
    assert _play_confirmed(fallback, placement)
    assert not _play_confirmed(next_confirmed, None, elixir_drop_valid=False)


def test_direct_visual_cycle_requires_next_art_transfer_and_slot_replacement() -> None:
    states = np.zeros((30, 2, 5), dtype=np.int16)
    states[:, 0] = [10, 11, 12, 13, 14]
    states[:, 1] = [20, 21, 22, 23, 24]
    vectors = np.zeros((30, 2, 5, 6), dtype=np.float32)
    for player in (0, 1):
        for slot in range(5):
            vectors[:, player, slot, slot] = 1.0
    vectors[15:, 0, 2] = vectors[:15, 0, 4][0]
    vectors[15:, 0, 4] = np.asarray([0, 0, 0, 0, 0, 1], dtype=np.float32)

    candidates = detect_visual_cycle_candidates(states, vectors, sample_hz=10)

    assert len(candidates) == 1
    assert candidates[0].selected_slot == 2
    assert candidates[0].selected_cluster == 12
    assert candidates[0].transition_evidence == "direct_next_art_to_hand_slot"


def test_direct_visual_cycle_rejects_unchanged_slot_despite_next_similarity() -> None:
    states = np.zeros((30, 2, 5), dtype=np.int16)
    vectors = np.zeros((30, 2, 5, 5), dtype=np.float32)
    for slot in range(5):
        vectors[:, :, slot, slot] = 1.0
    vectors[:, :, 4] = vectors[:, :, 2]

    assert detect_visual_cycle_candidates(states, vectors, sample_hz=10) == []


def test_observed_elixir_drop_is_current_public_hud_only() -> None:
    records = []
    for timestamp_ms, value in [(900, 5.0), (1_000, 5.1), (1_100, 2.1)]:
        records.append(
            {
                "timestamp_ms": timestamp_ms,
                "offline_privileged_hud": {
                    "0": {"elixir": {"valid": True, "value": value}},
                    "1": {"elixir": {"valid": False, "value": None}},
                },
            }
        )

    assert _observed_elixir_drop(
        records, player_id=0, timestamp_ms=1_000
    ) == pytest.approx(3.0)
    assert _observed_elixir_drop(records, player_id=1, timestamp_ms=1_000) == 0.0


def test_preplay_identity_requires_three_candidate_frames_to_agree() -> None:
    records = []
    for frame_index in range(30):
        candidate = "card_action:Log" if frame_index in {9, 12, 15} else "empty"
        records.append(
            {
                "offline_privileged_hud": {
                    "0": {
                        "hand": [
                            {
                                "candidate": candidate if slot == 2 else "empty",
                                "valid": False,
                                "score": 0.7,
                                "margin": 0.02,
                            }
                            for slot in range(4)
                        ]
                    }
                }
            }
        )
    event = CycleCandidate(
        0, 20, 2, 6, 0.9, "direct_next_art_to_hand_slot"
    )

    identity, evidence = _unanimous_preplay_identity(
        records, event, sample_hz=10
    )

    assert identity == "card_action:Log"
    assert len(evidence) == 3
    records[12]["offline_privileged_hud"]["0"]["hand"][2]["candidate"] = (
        "card_action:Arrows"
    )
    assert _unanimous_preplay_identity(records, event, sample_hz=10)[0] is None


def test_reviewed_decks_require_exact_video_and_eight_unique_cards(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "decks.json"
    payload = {
        "schema": "clasher.youtube.reviewed_public_decks.v1",
        "video_sha256": "video-a",
        "players": {
            str(player): {
                "card_identities": [f"card_action:P{player}Card{index}" for index in range(8)]
            }
            for player in (0, 1)
        },
    }
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    decks = _load_reviewed_decks(manifest, video_sha256="video-a")

    assert len(decks[0]) == 8
    with pytest.raises(ValueError, match="source video"):
        _load_reviewed_decks(manifest, video_sha256="video-b")
