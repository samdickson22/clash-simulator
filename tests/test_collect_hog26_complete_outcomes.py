from __future__ import annotations

import numpy as np

from scripts.collect_hog26_complete_outcomes import (
    _outcome_counts,
    crossed_opponent_rows,
)


def test_outcome_counts_preserve_all_three_classes() -> None:
    assert _outcome_counts(np.asarray([-1, 1, 1], dtype=np.int8)) == {
        "loss": 1,
        "draw": 0,
        "win": 2,
    }


def test_crossed_opponent_rows_pair_every_style_deck_and_seat() -> None:
    opponents, decks = crossed_opponent_rows(
        ("balanced", "random"), ("Log Bait", "Valk Log Bait")
    )
    assert opponents == (
        "balanced",
        "balanced",
        "random",
        "random",
        "balanced",
        "balanced",
        "random",
        "random",
    )
    assert decks == (
        "Log Bait",
        "Log Bait",
        "Log Bait",
        "Log Bait",
        "Valk Log Bait",
        "Valk Log Bait",
        "Valk Log Bait",
        "Valk Log Bait",
    )
