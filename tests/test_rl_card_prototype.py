from __future__ import annotations

import numpy as np
import pytest

from clasher.rl.card_prototype import complete_unique_deck, prototype_decisions


def test_prototype_decisions_max_pool_classes_and_abstain() -> None:
    prototypes = np.asarray([[1.0, 0.0], [0.98, 0.02], [0.0, 1.0]], dtype=np.float32)
    prototypes /= np.linalg.norm(prototypes, axis=1, keepdims=True)
    queries = np.asarray([[1.0, 0.0], [0.72, 0.69]], dtype=np.float32)
    queries /= np.linalg.norm(queries, axis=1, keepdims=True)

    rows = prototype_decisions(
        queries,
        prototypes,
        ["a", "a", "b"],
        minimum_score=0.9,
        minimum_margin=0.1,
    )

    assert rows[0].candidate == "a" and rows[0].accepted
    assert not rows[1].accepted


def test_complete_deck_requires_eight_accepted_unique_cards() -> None:
    prototypes = np.eye(8, dtype=np.float32)
    rows = prototype_decisions(
        prototypes,
        prototypes,
        [str(index) for index in range(8)],
        minimum_score=0.9,
        minimum_margin=0.1,
    )
    assert complete_unique_deck(rows)
    assert not complete_unique_deck(rows[:7])
    duplicate = prototype_decisions(
        prototypes,
        prototypes,
        ["same"] * 8,
        minimum_score=0.9,
        minimum_margin=0.1,
    )
    assert not complete_unique_deck(duplicate)


def test_rejects_bad_shapes_and_thresholds() -> None:
    with pytest.raises(ValueError):
        prototype_decisions(
            np.zeros((1, 2), dtype=np.float32),
            np.zeros((1, 3), dtype=np.float32),
            ["a"],
            minimum_score=0.9,
            minimum_margin=0.1,
        )
