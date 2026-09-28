from __future__ import annotations

import numpy as np
import pytest
import torch

from clasher.rl.common import NUM_TILES
from scripts.fit_terminal_counterfactual_adapter import (
    _expand_placement_timing_logits,
    build_preferences,
    concatenate_preferences,
)


def test_build_preferences_keeps_causal_improvements_and_strict_safe_waits() -> None:
    no_op = 4 * NUM_TILES
    payload = {
        "base_actions": np.asarray([no_op, no_op, no_op], dtype=np.int64),
        "best_actions": np.asarray([2 * NUM_TILES + 7, no_op, no_op], dtype=np.int64),
        "candidate_actions": np.asarray(
            [
                [no_op, 2 * NUM_TILES + 7, -1],
                [no_op, NUM_TILES + 3, 3 * NUM_TILES + 9],
                [no_op, 5, -1],
            ],
            dtype=np.int64,
        ),
        "candidate_scores": np.asarray(
            [
                [0.0, 1.0, np.nan],
                [1.0, 0.0, 0.0],
                [0.0, 0.0, np.nan],
            ],
            dtype=np.float32,
        ),
    }

    rows = build_preferences(payload)

    assert rows.state_indices.tolist() == [0, 1, 1]
    assert rows.positive_types.tolist() == [2, 4, 4]
    assert rows.negative_types.tolist() == [4, 1, 3]
    assert rows.weights.tolist() == [1.0, 0.5, 0.5]
    assert rows.kinds.tolist() == [1, 0, 0]


def test_build_preferences_uses_terminal_crowns_then_tower_damage() -> None:
    no_op = 4 * NUM_TILES
    payload = {
        "base_actions": np.asarray([no_op, no_op, no_op], dtype=np.int64),
        "candidate_actions": np.asarray(
            [
                [no_op, NUM_TILES + 3],
                [no_op, 2 * NUM_TILES + 7],
                [no_op, 3 * NUM_TILES + 9],
            ],
            dtype=np.int64,
        ),
        "candidate_valid": np.ones((3, 2), dtype=np.bool_),
        "candidate_scores": np.asarray(
            [[1.0, 1.0], [1.0, 1.0], [1.0, 0.0]], dtype=np.float32
        ),
        "candidate_crown_differences": np.asarray(
            [[1, 2], [1, 1], [1, 3]], dtype=np.int8
        ),
        "candidate_tower_damage_differences": np.asarray(
            [[500.0, 100.0], [500.0, 900.0], [500.0, 9000.0]],
            dtype=np.float32,
        ),
    }

    rows = build_preferences(payload)

    assert rows.state_indices.tolist() == [0, 1, 2]
    assert rows.positive_types.tolist() == [1, 2, 4]
    assert rows.negative_types.tolist() == [4, 4, 3]
    assert rows.weights[0] == pytest.approx(2.0)
    assert 1.0 < rows.weights[1] <= 2.0
    assert rows.weights[2] == pytest.approx(4.0)
    assert rows.kinds.tolist() == [1, 1, 0]


def test_placement_timing_logits_preserve_conditional_slot_differences() -> None:
    base = torch.tensor([[2.0, -1.0, 0.5, 3.0, 1.25, -4.0]])
    expanded = _expand_placement_timing_logits(torch.tensor([[0.75]]))
    adjusted = base + expanded

    assert expanded.tolist() == [[0.75, 0.75, 0.75, 0.75, 0.0, 0.0]]
    for left in range(4):
        for right in range(4):
            assert float(adjusted[0, left] - adjusted[0, right]) == pytest.approx(
                float(base[0, left] - base[0, right])
            )
    assert float(adjusted[0, 4]) == pytest.approx(float(base[0, 4]))
    assert float(adjusted[0, 5]) == pytest.approx(float(base[0, 5]))


def test_concatenate_preferences_offsets_only_second_state_indices() -> None:
    first = build_preferences(
        {
            "base_actions": np.asarray([4 * NUM_TILES]),
            "best_actions": np.asarray([NUM_TILES + 3]),
            "candidate_actions": np.asarray([[4 * NUM_TILES, NUM_TILES + 3]]),
            "candidate_scores": np.asarray([[0.0, 1.0]], dtype=np.float32),
        }
    )
    second = build_preferences(
        {
            "base_actions": np.asarray([4 * NUM_TILES]),
            "best_actions": np.asarray([2 * NUM_TILES + 9]),
            "candidate_actions": np.asarray(
                [[4 * NUM_TILES, 2 * NUM_TILES + 9]]
            ),
            "candidate_scores": np.asarray([[0.0, 1.0]], dtype=np.float32),
        }
    )

    combined = concatenate_preferences(first, second, second_state_offset=17)

    assert combined.state_indices.tolist() == [0, 17]
    assert combined.positive_types.tolist() == [1, 2]
    assert combined.negative_types.tolist() == [4, 4]
    assert combined.weights.tolist() == [1.0, 1.0]
    assert combined.kinds.tolist() == [1, 1]
