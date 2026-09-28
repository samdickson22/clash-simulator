from __future__ import annotations

import numpy as np
import pytest

from scripts.collect_hog26_direct_simple_behavior import (
    PLACEMENT_ACTIONS,
    _audit_hazard_reproduction,
    _card_counts,
    _validate_play_probabilities,
    paired_row_opponents,
)


def test_paired_row_opponents_assigns_adjacent_seats() -> None:
    assert paired_row_opponents(("balanced", "random")) == (
        "balanced",
        "balanced",
        "random",
        "random",
    )


@pytest.mark.parametrize(
    ("opponents", "message"),
    (
        (("balanced",), "at least two"),
        (("balanced", "balanced"), "unique"),
        (("balanced", "not-a-strategy"), "unknown"),
    ),
)
def test_paired_row_opponents_rejects_invalid_schedule(
    opponents: tuple[str, ...], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        paired_row_opponents(opponents)


def test_card_counts_uses_the_card_in_the_executed_hand_slot() -> None:
    token_names = ("<pad>", "<unknown>", "hog", "cannon")
    actions = np.asarray([0, 576, 2304], dtype=np.int64)
    hand_ids = np.asarray(
        [
            [2, 3, 1, 1, 1],
            [2, 3, 1, 1, 1],
            [2, 3, 1, 1, 1],
        ],
        dtype=np.int64,
    )
    assert _card_counts(actions, hand_ids, token_names) == {"cannon": 1, "hog": 1}


def test_teacher_hazard_factors_must_align_and_be_probabilities() -> None:
    actions = np.asarray([0, 2304], dtype=np.int64)
    _validate_play_probabilities(actions, np.asarray([0.1, 0.0], dtype=np.float32))
    with pytest.raises(ValueError, match="align"):
        _validate_play_probabilities(actions, np.asarray([0.1], dtype=np.float32))
    with pytest.raises(ValueError, match="finite"):
        _validate_play_probabilities(actions, np.asarray([0.1, np.nan]))
    with pytest.raises(ValueError, match="finite"):
        _validate_play_probabilities(actions, np.asarray([0.1, 1.0]))


def test_teacher_hazard_factors_exactly_reproduce_accumulated_plays() -> None:
    actions = np.asarray([2304, 2304, 7, 2304, 2304, 9], dtype=np.int64)
    probabilities = np.asarray([0.1] * 6, dtype=np.float32)
    masks = np.zeros((6, PLACEMENT_ACTIONS + 2), dtype=np.bool_)
    masks[:, 0] = True
    masks[:, 2304] = True
    result = _audit_hazard_reproduction(
        actions=actions,
        probabilities=probabilities,
        action_masks=masks,
        episode_offsets=np.asarray([0, 3, 6]),
        initial_hidden=np.zeros((2, 4), dtype=np.float32),
        threshold=0.2,
    )
    assert result == {"rows": 6, "mismatches": 0}

    broken = actions.copy()
    broken[2] = 2304
    with pytest.raises(ValueError, match="exact action reproduction"):
        _audit_hazard_reproduction(
            actions=broken,
            probabilities=probabilities,
            action_masks=masks,
            episode_offsets=np.asarray([0, 3, 6]),
            initial_hidden=np.zeros((2, 4), dtype=np.float32),
            threshold=0.2,
        )
