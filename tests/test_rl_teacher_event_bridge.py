from __future__ import annotations

import math

import torch

from clasher.rl.event_policy import (
    ABILITY_ACTION,
    NUM_ACTIONS,
    WAIT_ACTION,
    deterministic_event_actions,
)
from clasher.rl.teacher_event_bridge import legacy_hazard_teacher_factors


def _teacher_inputs() -> tuple[torch.Tensor, ...]:
    probabilities = torch.tensor([[0.08, 0.15, 0.28, 0.04, 0.42, 0.12]])
    positive_weight = 80.0
    hazard_logits = (
        torch.logit(probabilities) + math.log(positive_weight)
    )
    card_logits = torch.tensor(
        [
            [
                [4.0, 1.0, 0.0, -1.0],
                [0.0, 5.0, 1.0, -1.0],
                [0.0, 1.0, 6.0, -1.0],
                [0.0, 1.0, 2.0, 7.0],
                [4.0, 1.0, 0.0, -1.0],
                [0.0, 5.0, 1.0, -1.0],
            ]
        ]
    )
    location_logits = torch.zeros(1, 6, 4, 576)
    for step in range(6):
        for slot in range(4):
            location_logits[0, step, slot, step * 10 + slot] = 10.0
    mask = torch.zeros(1, 6, NUM_ACTIONS, dtype=torch.bool)
    for step in range(6):
        for slot in range(4):
            mask[0, step, slot * 576 + step * 10 + slot] = True
    mask[..., WAIT_ACTION] = True
    elapsed = torch.full((1, 6), 0.4)
    return (
        probabilities,
        hazard_logits,
        card_logits,
        location_logits,
        mask,
        elapsed,
        torch.tensor(positive_weight),
    )


def test_teacher_bridge_reproduces_retained_deterministic_actions_and_state() -> None:
    (
        probabilities,
        hazard_logits,
        card_logits,
        location_logits,
        mask,
        elapsed,
        positive_weight,
    ) = _teacher_inputs()
    factors = legacy_hazard_teacher_factors(
        hazard_logits,
        card_logits,
        location_logits,
        mask,
        elapsed,
        positive_weight=float(positive_weight),
    )
    torch.testing.assert_close(
        factors.interval_play_probability, probabilities, rtol=1e-6, atol=1e-7
    )

    initial_probability = torch.tensor([0.18])
    initial_hazard = -torch.log1p(-initial_probability)
    actions, final_hazard = deterministic_event_actions(
        factors.distribution,
        initial_hazard,
        threshold=math.log(2.0),
    )

    retained_accumulator = initial_probability.clone()
    retained_actions: list[int] = []
    for step, probability in enumerate(probabilities[0]):
        retained_accumulator = 1.0 - (1.0 - retained_accumulator) * (
            1.0 - probability
        )
        if bool(retained_accumulator >= 0.5):
            slot = int(card_logits[0, step].argmax())
            tile = int(location_logits[0, step, slot].argmax())
            retained_actions.append(slot * 576 + tile)
            retained_accumulator.zero_()
        else:
            retained_actions.append(WAIT_ACTION)
    assert actions.tolist() == [retained_actions]
    torch.testing.assert_close(
        retained_accumulator,
        1.0 - torch.exp(-final_hazard),
        rtol=1e-6,
        atol=1e-7,
    )


def test_teacher_bridge_rejects_ability_rows() -> None:
    (
        _probabilities,
        hazard_logits,
        card_logits,
        location_logits,
        mask,
        elapsed,
        positive_weight,
    ) = _teacher_inputs()
    mask[..., ABILITY_ACTION] = True
    try:
        legacy_hazard_teacher_factors(
            hazard_logits,
            card_logits,
            location_logits,
            mask,
            elapsed,
            positive_weight=float(positive_weight),
        )
    except ValueError as error:
        assert "champion abilities" in str(error)
    else:
        raise AssertionError("ability-bearing teacher rows must fail closed")
