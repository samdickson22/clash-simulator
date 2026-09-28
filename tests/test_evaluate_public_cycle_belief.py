from __future__ import annotations

import numpy as np

from clasher.rl.common import NUM_TILES
from scripts.evaluate_public_cycle_belief import build_public_cycle_examples


def test_cycle_examples_use_only_prior_plays_and_persist_seen_cards() -> None:
    corpus = {
        "hand_ids": np.asarray(
            [
                [10, 11, 12, 13, 14],
                [14, 11, 12, 13, 15],
                [14, 16, 12, 13, 15],
            ],
            dtype=np.int64,
        ),
        "expert_actions": np.asarray(
            [0 * NUM_TILES, 1 * NUM_TILES, 4 * NUM_TILES], dtype=np.int64
        ),
        "episode_ids": np.zeros((3,), dtype=np.int64),
        "source_frames": np.asarray([100, 220, 400], dtype=np.int64),
    }
    examples = build_public_cycle_examples(corpus)

    assert examples["recent_ids"].tolist() == [
        [0, 0, 0, 0],
        [10, 0, 0, 0],
        [11, 10, 0, 0],
    ]
    assert examples["seen_ids"].tolist() == [
        [0, 0, 0, 0, 0, 0, 0, 0],
        [10, 0, 0, 0, 0, 0, 0, 0],
        [10, 11, 0, 0, 0, 0, 0, 0],
    ]
    np.testing.assert_allclose(examples["recent_ages"][1, 0], 120 / 3600)
    assert examples["targets"][2, [12, 13, 14, 16]].tolist() == [1.0] * 4


def test_cycle_examples_reset_history_between_episodes() -> None:
    corpus = {
        "hand_ids": np.asarray([[10, 11, 12, 13], [20, 21, 22, 23]], dtype=np.int64),
        "expert_actions": np.asarray([0, 4 * NUM_TILES], dtype=np.int64),
        "episode_ids": np.asarray([0, 1], dtype=np.int64),
        "source_frames": np.asarray([100, 50], dtype=np.int64),
    }
    examples = build_public_cycle_examples(corpus)
    assert not examples["recent_ids"][1].any()
    assert not examples["seen_ids"][1].any()
