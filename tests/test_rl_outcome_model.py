from __future__ import annotations

import pytest
import torch

from clasher.rl.outcome_model import (
    ActorOutcomeHead,
    ActorOutcomePrediction,
    actor_outcome_loss,
    outcome_state_sha256,
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


def test_margin_loss_can_use_independent_episode_weights() -> None:
    prediction = ActorOutcomePrediction(
        outcome_logits=torch.tensor([[4.0, 0.0, 0.0], [4.0, 0.0, 0.0]]),
        terminal_tower_margin=torch.tensor([-0.5, 0.5]),
    )
    weighted = actor_outcome_loss(
        prediction,
        torch.tensor([-1, -1]),
        torch.tensor([-0.5, -0.5]),
        margin_coefficient=1.0,
        sample_weights=torch.tensor([1.0, 0.0]),
        margin_sample_weights=torch.tensor([0.0, 1.0]),
    )
    assert float(weighted.outcome_nll) < 0.1
    assert float(weighted.tower_margin_huber) == pytest.approx(0.25)


def test_separate_draw_trunk_does_not_use_tactical_prefix() -> None:
    head = ActorOutcomeHead(32, hidden_size=8, separate_draw_trunk=True)
    first = torch.randn(2, 32)
    second = first.clone()
    second[:, :-18] = torch.randn_like(second[:, :-18])
    first_draw = head(first).outcome_logits[:, 1]
    second_draw = head(second).outcome_logits[:, 1]
    torch.testing.assert_close(first_draw, second_draw)


def test_structured_residual_starts_context_invariant_and_stays_bounded() -> None:
    torch.manual_seed(7)
    head = ActorOutcomeHead(32, hidden_size=8, structured_residual_scale=0.25)
    first_state = torch.randn(3, 32)
    second_state = first_state.clone()
    second_state[:, :-18] = torch.randn_like(second_state[:, :-18]) * 100.0
    initial = head(first_state).outcome_logits
    torch.testing.assert_close(initial, head(second_state).outcome_logits)

    assert head.structured_decisive is not None
    torch.nn.init.constant_(head.structured_decisive.weight, 10.0)
    first = head(first_state).outcome_logits
    second = head(second_state).outcome_logits
    # Conditional decisive logits differ by at most twice the configured scale.
    assert float((first[..., 2] - second[..., 2]).abs().max().detach()) <= 0.5 + 1e-6


def test_margin_residual_starts_at_public_baseline_and_is_trainable() -> None:
    head = ActorOutcomeHead(18, hidden_size=8, margin_residual_scale=0.5)
    state = torch.rand(4, 18)
    baseline = (state[:, 8:11].sum(dim=-1) - state[:, 11:14].sum(dim=-1)) / 3.0
    prediction = head(state)
    torch.testing.assert_close(prediction.terminal_tower_margin, baseline)
    loss = actor_outcome_loss(
        prediction,
        torch.tensor([-1, -1, 1, 1]),
        torch.tensor([-0.8, -0.4, 0.4, 0.8]),
    )
    loss.total.backward()
    assert head.margin_trunk is not None
    final_margin = head.margin_trunk[-1]
    assert isinstance(final_margin, torch.nn.Linear)
    assert final_margin.weight.grad is not None
    assert bool(torch.isfinite(final_margin.weight.grad).all())


def test_factorized_prior_calibration_recovers_empirical_constant_prior() -> None:
    head = ActorOutcomeHead(18, hidden_size=4)
    with torch.no_grad():
        for parameter in head.parameters():
            parameter.zero_()
        head.draw.bias.fill_(torch.logit(torch.tensor(0.1)))
    head.set_prior_calibration(
        torch.tensor([0.6, 0.1, 0.3]),
        torch.tensor([0.45, 0.1, 0.45]),
    )
    probabilities = head(torch.zeros(2, 18)).outcome_logits.exp()
    torch.testing.assert_close(
        probabilities,
        torch.tensor([[0.6, 0.1, 0.3], [0.6, 0.1, 0.3]]),
        atol=1e-6,
        rtol=1e-6,
    )
    uncalibrated = head(torch.zeros(1, 18), calibrated=False).outcome_logits.exp()
    torch.testing.assert_close(
        uncalibrated, torch.tensor([[0.45, 0.1, 0.45]]), atol=1e-6, rtol=1e-6
    )


def test_factorized_prior_calibration_rejects_zero_or_wrong_shape() -> None:
    head = ActorOutcomeHead(18, hidden_size=4)
    with pytest.raises(ValueError, match="vectors"):
        head.set_prior_calibration(torch.ones(2), torch.ones(3))
    with pytest.raises(ValueError, match="positive"):
        head.set_prior_calibration(torch.tensor([0.5, 0.0, 0.5]), torch.ones(3))
    with pytest.raises(ValueError, match="shrinkage"):
        head.set_probability_shrinkage(2.0)


def test_probability_shrinkage_preserves_expected_utility_ranking() -> None:
    head = ActorOutcomeHead(18, hidden_size=4)
    head.set_prior_calibration(
        torch.tensor([0.4, 0.2, 0.4]),
        torch.tensor([0.4, 0.2, 0.4]),
    )
    state = torch.randn(5, 18)
    original = head(state).outcome_logits.exp()
    head.set_probability_shrinkage(0.25)
    shrunk = head(state).outcome_logits.exp()
    original_utility = original[:, 2] - original[:, 0]
    shrunk_utility = shrunk[:, 2] - shrunk[:, 0]
    torch.testing.assert_close(shrunk_utility, 0.25 * original_utility)
    assert torch.equal(torch.argsort(original_utility), torch.argsort(shrunk_utility))


def test_outcome_state_digest_is_order_independent_and_value_sensitive() -> None:
    left = {"b": torch.tensor([2.0]), "a": torch.tensor([1.0])}
    right = {"a": torch.tensor([1.0]), "b": torch.tensor([2.0])}
    assert outcome_state_sha256(left) == outcome_state_sha256(right)
    right["b"][0] = 3.0
    assert outcome_state_sha256(left) != outcome_state_sha256(right)
