from __future__ import annotations

import pytest
import torch

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from scripts.distill_equivariant_play_timing import (
    top_level_legal_mask,
    top_level_probabilities,
)


def test_top_level_probabilities_sum_slots_into_play() -> None:
    actions = NUM_HAND_SLOTS * NUM_TILES + 2
    mask = torch.zeros((2, actions), dtype=torch.bool)
    mask[0, [0, NUM_TILES, -2]] = True
    mask[1, [2 * NUM_TILES, -2, -1]] = True
    logits = torch.tensor(
        [
            [1.0, 2.0, 99.0, 99.0, 3.0, -9.0],
            [99.0, 99.0, 2.0, 99.0, 1.0, 3.0],
        ]
    )

    actual = top_level_probabilities(logits, mask, temperature=1.0)

    expected0 = torch.softmax(torch.tensor([1.0, 2.0, 3.0]), dim=-1)
    expected1 = torch.softmax(torch.tensor([2.0, 1.0, 3.0]), dim=-1)
    torch.testing.assert_close(
        actual[0], torch.tensor([expected0[:2].sum(), expected0[2], 0.0])
    )
    torch.testing.assert_close(actual[1], expected1)
    torch.testing.assert_close(actual.sum(dim=-1), torch.ones(2))


def test_top_level_legal_mask_tracks_any_card_and_special_actions() -> None:
    actions = NUM_HAND_SLOTS * NUM_TILES + 2
    mask = torch.zeros((2, actions), dtype=torch.bool)
    mask[0, [3 * NUM_TILES + 7, -2]] = True
    mask[1, -2:] = True

    actual = top_level_legal_mask(mask)

    assert actual.tolist() == [[True, True, False], [False, True, True]]


def test_top_level_probabilities_reject_invalid_temperature() -> None:
    with pytest.raises(ValueError, match="positive"):
        top_level_probabilities(
            torch.zeros((1, 6)),
            torch.ones((1, NUM_HAND_SLOTS * NUM_TILES + 2), dtype=torch.bool),
            temperature=0.0,
        )
