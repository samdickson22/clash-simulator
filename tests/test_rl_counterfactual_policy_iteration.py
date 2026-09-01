from __future__ import annotations

import torch

from clasher.rl.counterfactual_policy_iteration import (
    counterfactual_policy_loss,
    forward_policy_kl,
    kl_regularized_candidate_target,
)


def _behavior() -> torch.Tensor:
    probabilities = torch.tensor(
        [[0.50, 0.30, 0.15, 0.05], [0.10, 0.20, 0.30, 0.40]]
    )
    return probabilities.log()


def test_equal_value_target_is_behavior_policy_renormalized_on_candidates() -> None:
    behavior = _behavior()
    actions = torch.tensor([[0, 2, -1], [1, 3, -1]])
    valid = actions >= 0
    values = torch.zeros_like(actions, dtype=torch.float32)
    target = kl_regularized_candidate_target(
        behavior,
        actions,
        values,
        valid,
        behavior_actions=torch.tensor([0, 3]),
        beta=0.5,
    )
    expected = torch.tensor([[0.50 / 0.65, 0.15 / 0.65, 0.0], [1 / 3, 2 / 3, 0.0]])
    torch.testing.assert_close(target.probabilities, expected)


def test_terminal_advantage_shifts_mass_without_erasing_behavior_prior() -> None:
    behavior = _behavior()[:1]
    actions = torch.tensor([[0, 1, 2]])
    valid = torch.ones_like(actions, dtype=torch.bool)
    target = kl_regularized_candidate_target(
        behavior,
        actions,
        torch.tensor([[-1.0, 0.0, 1.0]]),
        valid,
        behavior_actions=torch.tensor([0]),
        beta=0.25,
    )
    assert int(target.probabilities.argmax(dim=-1)) == 2
    assert target.probabilities[0, 0] > 0.0


def test_policy_loss_has_finite_improvement_and_anchor_gradients() -> None:
    behavior = _behavior()
    actions = torch.tensor([[0, 1, 2], [1, 2, 3]])
    valid = torch.ones_like(actions, dtype=torch.bool)
    target = kl_regularized_candidate_target(
        behavior,
        actions,
        torch.tensor([[0.0, 1.0, -1.0], [-1.0, 0.0, 1.0]]),
        valid,
        behavior_actions=torch.tensor([0, 3]),
        beta=0.5,
    )
    logits = torch.zeros_like(behavior, requires_grad=True)
    student = torch.log_softmax(logits, dim=-1)
    loss = counterfactual_policy_loss(
        student,
        behavior,
        target,
        behavior_kl_coefficient=0.2,
    )
    assert torch.isfinite(loss.total)
    assert loss.improvement > 0.0
    assert loss.behavior_kl >= 0.0
    loss.total.backward()
    assert logits.grad is not None
    assert bool(torch.isfinite(logits.grad).all())
    assert float(logits.grad.abs().sum()) > 0.0


def test_forward_kl_is_zero_for_identical_policy() -> None:
    behavior = _behavior()
    torch.testing.assert_close(
        forward_policy_kl(behavior, behavior), torch.tensor(0.0), atol=1e-7, rtol=0.0
    )


def test_candidate_set_must_retain_behavior_action_and_unique_support() -> None:
    behavior = _behavior()[:1]
    valid = torch.tensor([[True, True]])
    for actions, message in (
        (torch.tensor([[1, 2]]), "retain the behavior action"),
        (torch.tensor([[0, 0]]), "unique"),
    ):
        try:
            kl_regularized_candidate_target(
                behavior,
                actions,
                torch.zeros(1, 2),
                valid,
                behavior_actions=torch.tensor([0]),
                beta=0.5,
            )
        except ValueError as error:
            assert message in str(error)
        else:
            raise AssertionError("invalid candidate set must fail closed")


def test_zero_behavior_support_candidate_fails_closed() -> None:
    behavior = torch.tensor([[0.0, -torch.inf, -torch.inf]])
    try:
        kl_regularized_candidate_target(
            behavior,
            torch.tensor([[0, 1]]),
            torch.zeros(1, 2),
            torch.ones(1, 2, dtype=torch.bool),
            behavior_actions=torch.tensor([0]),
            beta=0.5,
        )
    except ValueError as error:
        assert "zero behavior support" in str(error)
    else:
        raise AssertionError("unsupported counterfactual must fail closed")
