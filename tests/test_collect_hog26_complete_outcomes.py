from __future__ import annotations

from pathlib import Path

import numpy as np

from scripts.collect_hog26_complete_outcomes import (
    _outcome_counts,
    crossed_opponent_rows,
    opponent_decks_for_split,
)

PROCEDURAL = (
    Path(__file__).resolve().parents[1]
    / "training_decks"
    / "hog26_procedural_supported_seed1278401.json"
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


def test_crossed_opponent_rows_accept_one_heldout_style() -> None:
    opponents, decks = crossed_opponent_rows(("split-lane",), ("Log Bait",))
    assert opponents == ("split-lane", "split-lane")
    assert decks == ("Log Bait", "Log Bait")


def test_procedural_split_selection_keeps_holdout_sealed() -> None:
    train = opponent_decks_for_split(PROCEDURAL, "train")
    development = opponent_decks_for_split(PROCEDURAL, "development")
    holdout = opponent_decks_for_split(PROCEDURAL, "holdout")
    assert (len(train), len(development), len(holdout)) == (32, 16, 16)
    assert not (set(train) & set(development))
    assert not (set(train) & set(holdout))
    assert not (set(development) & set(holdout))
    assert "Hog 2.6 Cycle" not in set(train) | set(development) | set(holdout)
    selected = opponent_decks_for_split(
        PROCEDURAL, "development", ("family-009", "family-010")
    )
    assert len(selected) == 8
    assert all(name.startswith("Procedural development") for name in selected)
