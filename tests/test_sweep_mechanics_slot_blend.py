from __future__ import annotations

import numpy as np
import torch

from scripts.fit_mechanics_slot_probe import MechanicsSlotScorer, SlotExamples
from scripts.sweep_mechanics_slot_blend import (
    mixture_metrics,
    normalized_legal_logits,
)


def _examples() -> SlotExamples:
    return SlotExamples(
        state=torch.asarray([[1.0], [1.0]]),
        cards=torch.asarray([[[1.0], [0.0]], [[1.0], [0.0]]]),
        legal=torch.asarray([[True, True], [True, False]]),
        target=torch.asarray([0, 0]),
        target_card=torch.asarray([1, 1]),
        episode=np.asarray([0, 0]),
        base_logits=torch.asarray([[0.0, 1.0], [0.0, 100.0]]),
    )


def test_normalization_excludes_illegal_slots() -> None:
    examples = _examples()
    actual = normalized_legal_logits(examples.base_logits, examples.legal)

    assert torch.isneginf(actual[1, 1])
    assert actual[1, 0] == 0.0


def test_normalized_blend_has_exact_incumbent_and_mechanics_endpoints() -> None:
    examples = _examples()
    model = MechanicsSlotScorer(state_size=1, card_size=1, hidden_size=0)
    with torch.no_grad():
        model.state_query.weight.fill_(2.0)

    base = mixture_metrics(model, examples, alpha=0.0)
    mechanics = mixture_metrics(model, examples, alpha=1.0)

    assert base["accuracy"] == 0.5
    assert base["disagreement_with_base"] == 0.0
    assert mechanics["accuracy"] == 1.0
    assert mechanics["disagreement_with_base"] == 0.5
