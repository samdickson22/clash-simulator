from __future__ import annotations

import pytest
import torch

from clasher.rl.common import NUM_TILES
from clasher.rl.terminal_action_reranker import (
    TerminalActionReranker,
    candidate_action_features,
    guarded_reranker_actions,
)


def test_candidate_features_use_card_mechanics_and_canonical_geometry() -> None:
    hand = torch.tensor([2, 3, 4, 5])
    cards = torch.arange(6 * 4, dtype=torch.float32).reshape(6, 4)
    logits = torch.linspace(-2.0, 2.0, 4 * NUM_TILES + 2)
    actions = torch.tensor([0, NUM_TILES + 17, 4 * NUM_TILES, 4 * NUM_TILES + 1])

    features = candidate_action_features(actions, hand, logits, cards)

    assert features.shape == (4, 3 + 7 + 4 + 2)
    assert features[:, :3].tolist() == [
        [1.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
    assert torch.equal(features[0, 10:14], cards[2])
    assert torch.equal(features[1, 10:14], cards[3])
    assert torch.count_nonzero(features[2:, 10:14]) == 0


def test_reranker_scores_each_state_action_pair_and_backpropagates() -> None:
    model = TerminalActionReranker(6, 5, rank=3)
    state = torch.randn(2, 4, 6)
    action = torch.randn(2, 4, 5)
    outcome, tie = model(state, action)
    assert outcome.shape == (2, 4)
    assert tie.shape == (2, 4)
    (outcome.square().mean() + tie.square().mean()).backward()
    assert all(parameter.grad is not None for parameter in model.parameters())


def test_reranker_rejects_mismatched_batches() -> None:
    model = TerminalActionReranker(3, 4)
    with pytest.raises(ValueError, match="batch dimensions"):
        model(torch.zeros(2, 3), torch.zeros(3, 4))


def test_guarded_actions_preserve_parent_below_margin() -> None:
    logits = torch.tensor([[0.0, 0.2], [0.0, 2.0]])
    ties = torch.zeros_like(logits)
    selected, improvements = guarded_reranker_actions(
        logits, ties, torch.tensor([0, 0]), probability_margin=0.2
    )
    assert selected.tolist() == [0, 1]
    assert improvements[0] < 0.2
    assert improvements[1] >= 0.2
