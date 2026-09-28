from __future__ import annotations

import torch

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.model import PolicyOutput
from scripts.fit_public_observation_adapter import _distillation_loss


def _output(*, shifted: bool = False) -> PolicyOutput:
    num_actions = NUM_HAND_SLOTS * NUM_TILES + 2
    joint_logits = torch.zeros((2, 3, num_actions), dtype=torch.float32)
    action_type_logits = torch.zeros((2, 3, NUM_HAND_SLOTS + 2))
    location_logits = torch.zeros((2, 3, NUM_HAND_SLOTS, NUM_TILES))
    if shifted:
        joint_logits[..., 0] = 2.0
        action_type_logits[..., 0] = 2.0
        location_logits[..., 0, 0] = 2.0
    state = (
        torch.zeros((1, 2, 4), dtype=torch.float32),
        torch.zeros((1, 2, 4), dtype=torch.float32),
    )
    return PolicyOutput(
        joint_logits=joint_logits,
        values=torch.zeros((2, 3), dtype=torch.float32),
        opponent_hand_logits=torch.zeros((2, 3, 1), dtype=torch.float32),
        opponent_elixir=torch.zeros((2, 3), dtype=torch.float32),
        next_state=state,
        action_type_logits=action_type_logits,
        location_logits=location_logits,
    )


def test_distillation_loss_is_zero_for_identical_policy_and_positive_for_drift() -> None:
    teacher = _output()
    action_mask = torch.ones_like(teacher.joint_logits, dtype=torch.bool)

    identical_loss = _distillation_loss(
        teacher,
        teacher,
        action_mask,
        joint_coef=1.0,
        type_coef=1.0,
        location_coef=0.25,
    )
    drifted_loss = _distillation_loss(
        _output(shifted=True),
        teacher,
        action_mask,
        joint_coef=1.0,
        type_coef=1.0,
        location_coef=0.25,
    )

    torch.testing.assert_close(identical_loss, torch.zeros_like(identical_loss))
    assert float(drifted_loss) > 0.0


def test_distillation_loss_supports_independent_factorized_terms() -> None:
    teacher = _output()
    student = _output(shifted=True)
    action_mask = torch.ones_like(teacher.joint_logits, dtype=torch.bool)

    for coefficients in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)):
        loss = _distillation_loss(
            student,
            teacher,
            action_mask,
            joint_coef=coefficients[0],
            type_coef=coefficients[1],
            location_coef=coefficients[2],
        )
        assert torch.isfinite(loss)
        assert float(loss) > 0.0
