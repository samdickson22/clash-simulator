from __future__ import annotations

import pytest
import torch

from clasher.rl.outcome_model import (
    ActorOutcomeHead,
    ActorOutcomePrediction,
    actor_outcome_loss,
)


def test_actor_outcome_head_predicts_three_classes_and_bounded_margin() -> None:
    head = ActorOutcomeHead(18, hidden_size=8)
    state = torch.rand(5, 18)
    result = head(state)
    assert result.outcome_logits.shape == (5, 3)
    assert result.terminal_tower_margin.shape == (5,)
    assert bool((result.terminal_tower_margin.abs() <= 1.0).all())
    assert torch.allclose(
        result.outcome_logits.exp().sum(dim=-1), torch.ones(5), atol=1e-6
    )
    loss = actor_outcome_loss(
        result,
        torch.tensor([-1, 0, 1, -1, 1]),
        torch.tensor([-0.5, 0.0, 0.7, -0.2, 0.3]),
    )
    loss.total.backward()
    assert all(parameter.grad is not None for parameter in head.parameters())


def test_actor_outcome_loss_rejects_discounted_or_invalid_classes() -> None:
    head = ActorOutcomeHead(18, hidden_size=4)
    prediction = head(torch.zeros(2, 18))
    with pytest.raises(ValueError, match="-1, 0, or 1"):
        actor_outcome_loss(
            prediction,
            torch.tensor([0, 2]),
            torch.zeros(2),
        )


def test_actor_outcome_loss_honors_sample_weights() -> None:
    prediction = ActorOutcomePrediction(
        outcome_logits=torch.tensor([[4.0, 0.0, 0.0], [0.0, 0.0, 4.0]]),
        terminal_tower_margin=torch.tensor([-0.5, 0.5]),
    )
    weighted = actor_outcome_loss(
        prediction,
        torch.tensor([-1, -1]),
        torch.tensor([-0.5, -0.5]),
        sample_weights=torch.tensor([1.0, 0.0]),
    )
    assert float(weighted.total) < 0.1


def test_separate_draw_trunk_does_not_use_tactical_prefix() -> None:
    head = ActorOutcomeHead(32, hidden_size=8, separate_draw_trunk=True)
    first = torch.randn(2, 32)
    second = first.clone()
    second[:, :-18] = torch.randn_like(second[:, :-18])
    first_draw = head(first).outcome_logits[:, 1]
    second_draw = head(second).outcome_logits[:, 1]
    torch.testing.assert_close(first_draw, second_draw)
