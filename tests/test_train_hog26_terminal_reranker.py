from __future__ import annotations

import torch

from scripts.train_hog26_terminal_reranker import _root_loss


def test_root_loss_prefers_outcomes_before_dense_ties() -> None:
    outcome_logits = torch.tensor([[0.2, -0.1, 0.0]], requires_grad=True)
    tie_scores = torch.tensor([[0.0, 0.5, -0.5]], requires_grad=True)
    outcomes = torch.tensor([[1.0, -1.0, 1.0]])
    returns = torch.tensor([[0.1, 0.9, 0.3]])

    loss, components = _root_loss(outcome_logits, tie_scores, outcomes, returns)

    assert torch.isfinite(loss)
    assert components["outcome_rank"] > 0.0
    assert components["tie_rank"] > 0.0
    loss.backward()
    assert outcome_logits.grad is not None
    assert tie_scores.grad is not None
