from __future__ import annotations

import numpy as np
import pytest

from scripts.collect_hog26_direct_simple_behavior import (
    _card_counts,
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
