from __future__ import annotations

import numpy as np
import pytest
import torch

from scripts.evaluate_mechanics_slot_policy_candidate import (
    evaluate_materialized_split,
)
from scripts.fit_mechanics_slot_probe import MechanicsSlotScorer, SlotExamples
from scripts.sweep_mechanics_slot_blend import normalized_legal_logits


def _examples(*, base_logits: torch.Tensor) -> SlotExamples:
    return SlotExamples(
        state=torch.tensor(
            [[0.2, -0.1, 0.4], [-0.3, 0.7, 0.1]],
            dtype=torch.float32,
        ),
        cards=torch.tensor(
            [
                [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5], [0.2, 0.8]],
                [[0.0, 1.0], [1.0, 0.0], [0.3, 0.7], [0.8, 0.2]],
            ],
            dtype=torch.float32,
        ),
        legal=torch.tensor(
            [[True, True, True, False], [True, False, True, True]]
        ),
        target=torch.tensor([2, 0]),
        target_card=torch.tensor([7, 8]),
        episode=np.asarray([10, 11], dtype=np.int64),
        base_logits=base_logits,
    )


def test_materialized_evaluator_requires_exact_blend_logits() -> None:
    model = MechanicsSlotScorer(state_size=3, card_size=2, hidden_size=0).eval()
    with torch.no_grad():
        model.state_query.weight.copy_(
            torch.tensor([[0.5, -0.2, 0.1], [-0.1, 0.3, 0.6]])
        )
    parent = _examples(
        base_logits=torch.tensor(
            [[0.2, 0.5, -0.1, 2.0], [0.8, 3.0, 0.1, -0.2]],
            dtype=torch.float32,
        )
    )
    base = normalized_legal_logits(parent.base_logits, parent.legal)
    mechanics = normalized_legal_logits(
        model(parent.state, parent.cards),
        parent.legal,
    )
    expected = normalized_legal_logits(
        0.7 * base + 0.3 * mechanics,
        parent.legal,
    )
    candidate = _examples(
        base_logits=expected + torch.tensor([[2.0], [-3.0]])
    )

    metrics = evaluate_materialized_split(
        model=model,
        alpha=0.3,
        parent=parent,
        candidate=candidate,
    )

    assert metrics["samples"] == 2
    assert metrics["materialized_logit_parity"] is True


def test_materialized_evaluator_rejects_changed_targets() -> None:
    model = MechanicsSlotScorer(state_size=3, card_size=2, hidden_size=0).eval()
    parent = _examples(base_logits=torch.zeros((2, 4)))
    candidate = _examples(base_logits=torch.zeros((2, 4)))
    candidate.target[0] = 1

    with pytest.raises(ValueError, match="target"):
        evaluate_materialized_split(
            model=model,
            alpha=0.3,
            parent=parent,
            candidate=candidate,
        )
