from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np

from clasher.rl.common import NUM_TILES

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "evaluate_card_frequency_generalization.py"
)
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("card_frequency_evaluator", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_expert_card_counts_use_played_hand_slot() -> None:
    arrays = {
        "expert_actions": np.asarray([0, NUM_TILES, 4 * NUM_TILES], dtype=np.int64),
        "hand_ids": np.asarray(
            [[7, 8, 9, 10, 11], [7, 8, 9, 10, 11], [7, 8, 9, 10, 11]],
            dtype=np.int64,
        ),
    }
    counts = MODULE._expert_card_counts(arrays, num_tokens=12)
    assert counts[7] == 1
    assert counts[8] == 1
    assert counts.sum() == 2


def test_frequency_metrics_separate_rare_and_common_cards() -> None:
    arrays = {
        "expert_actions": np.asarray([0, NUM_TILES], dtype=np.int64),
        "hand_ids": np.asarray(
            [[1, 2, 0, 0, 0], [1, 2, 0, 0, 0]], dtype=np.int64
        ),
    }
    chosen = np.asarray([0, 2 * NUM_TILES], dtype=np.int64)
    counts = np.zeros(3, dtype=np.int64)
    counts[1] = 5
    counts[2] = 1500
    metrics = MODULE._frequency_metrics(
        arrays=arrays,
        chosen_actions=chosen,
        reference_counts=counts,
        token_names=("<pad>", "Rare", "Common"),
    )
    assert metrics["one_to_9"]["samples"] == 1
    assert metrics["one_to_9"]["action_type_accuracy"] == 1.0
    assert metrics["thousand_plus"]["samples"] == 1
    assert metrics["thousand_plus"]["action_type_accuracy"] == 0.0
