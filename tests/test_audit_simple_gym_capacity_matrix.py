from __future__ import annotations

import pytest

from scripts.audit_simple_gym_capacity_matrix import Pair, ordered_pairs


def test_ordered_pairs_cover_every_direction_once() -> None:
    pairs = ordered_pairs(3)
    assert len(pairs) == 9
    assert pairs[0] == Pair(index=0, player0_deck=0, player1_deck=0)
    assert pairs[-1] == Pair(index=8, player0_deck=2, player1_deck=2)
    assert len({(pair.player0_deck, pair.player1_deck) for pair in pairs}) == 9
    assert [pair.index for pair in pairs] == list(range(9))


def test_ordered_pairs_reject_empty_deck_pool() -> None:
    with pytest.raises(ValueError, match="positive"):
        ordered_pairs(0)
