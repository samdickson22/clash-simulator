from __future__ import annotations

import numpy as np
import pytest

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from scripts.audit_symmetrized_teacher_win_conditions import (
    select_manifest_entries,
    summarize_designated_probability,
)
from scripts.train_student_state_symmetry_dagger import PLACEMENT_ACTIONS


def _arrays() -> dict[str, np.ndarray]:
    masks = np.zeros((3, PLACEMENT_ACTIONS + 2), dtype=np.bool_)
    masks[:, -2] = True
    masks[0, NUM_TILES : 2 * NUM_TILES] = True
    masks[2, 3 * NUM_TILES : 4 * NUM_TILES] = True
    return {
        "hand_ids": np.asarray(
            [
                [1, 9, 2, 3, 0],
                [1, 2, 9, 3, 0],
                [1, 2, 3, 9, 0],
            ],
            dtype=np.int64,
        ),
        "action_masks": masks,
        "expert_actions": np.asarray(
            [NUM_TILES + 7, PLACEMENT_ACTIONS, PLACEMENT_ACTIONS], dtype=np.int64
        ),
    }


def test_designated_probability_tracks_moving_slot_and_legal_support() -> None:
    arrays = _arrays()
    probabilities = np.zeros((3, PLACEMENT_ACTIONS + 2), dtype=np.float32)
    probabilities[0, NUM_TILES + 7] = 0.75
    probabilities[0, -2] = 0.25
    probabilities[1, -2] = 1.0
    probabilities[2, 3 * NUM_TILES + 11] = 0.2
    probabilities[2, -2] = 0.8

    actual = summarize_designated_probability(
        probabilities,
        arrays,
        card_token_id=9,
    )

    assert actual["samples"] == 3
    assert actual["in_hand_samples"] == 3
    assert actual["legal_samples"] == 2
    assert actual["mean_probability"] == pytest.approx(0.475)
    assert actual["median_probability"] == pytest.approx(0.475)
    assert actual["maximum_probability"] == pytest.approx(0.75)
    assert actual["greedy_count"] == 1
    assert actual["greedy_rate"] == pytest.approx(0.5)
    assert actual["observed_play_count"] == 1
    assert actual["observed_play_rate"] == pytest.approx(0.5)


def test_designated_probability_reports_no_legal_states_without_nan() -> None:
    arrays = _arrays()
    arrays["action_masks"][:, :PLACEMENT_ACTIONS] = False
    probabilities = np.zeros((3, PLACEMENT_ACTIONS + 2), dtype=np.float32)
    probabilities[:, -2] = 1.0

    actual = summarize_designated_probability(
        probabilities,
        arrays,
        card_token_id=9,
    )

    assert actual["legal_samples"] == 0
    assert actual["mean_probability"] is None
    assert actual["greedy_rate"] is None


def test_designated_probability_rejects_duplicate_current_hand_card() -> None:
    arrays = _arrays()
    arrays["hand_ids"][0, :NUM_HAND_SLOTS] = [9, 9, 2, 3]
    probabilities = np.zeros((3, PLACEMENT_ACTIONS + 2), dtype=np.float32)
    probabilities[:, -2] = 1.0

    with pytest.raises(ValueError, match="multiple current-hand slots"):
        summarize_designated_probability(
            probabilities,
            arrays,
            card_token_id=9,
        )


def test_empty_archetype_selection_means_all_entries() -> None:
    entries = [
        {"archetype": "graveyard"},
        {"archetype": "x-bow"},
    ]

    assert select_manifest_entries(entries, []) == entries


def test_archetype_selection_rejects_unknown_name() -> None:
    entries = [{"archetype": "graveyard"}]

    with pytest.raises(ValueError, match="unknown requested archetypes"):
        select_manifest_entries(entries, ["x-bow"])
