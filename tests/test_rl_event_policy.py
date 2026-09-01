from __future__ import annotations

import math

import torch

from clasher.rl.event_policy import (
    ABILITY_ACTION,
    NUM_ACTIONS,
    WAIT_ACTION,
    continuous_time_action_distribution,
    continuous_time_action_nll,
    deterministic_event_actions,
)


def _inputs(
    *, batch: int = 2, steps: int = 3
) -> tuple[torch.Tensor, ...]:
    shape = (batch, steps)
    play = torch.full(shape, -0.3, requires_grad=True)
    ability = torch.full(shape, -1.1, requires_grad=True)
    cards = torch.randn(*shape, 4, requires_grad=True)
    locations = torch.randn(*shape, 4, 576, requires_grad=True)
    mask = torch.zeros(*shape, NUM_ACTIONS, dtype=torch.bool)
    mask[..., 0:3] = True
    mask[..., 576 + 20 : 576 + 23] = True
    mask[..., WAIT_ACTION] = True
    mask[..., ABILITY_ACTION] = True
    elapsed = torch.full(shape, 0.4)
    return play, ability, cards, locations, mask, elapsed


def test_continuous_time_distribution_is_normalized_and_masked() -> None:
    distribution = continuous_time_action_distribution(*_inputs())
    probabilities = distribution.log_probs.exp()
    torch.testing.assert_close(
        probabilities.sum(dim=-1), torch.ones_like(probabilities[..., 0])
    )
    _play, _ability, _cards, _locations, mask, _elapsed = _inputs()
    assert bool((probabilities[~mask] == 0.0).all())
    assert bool((probabilities[..., WAIT_ACTION] > 0.0).all())


def test_survival_probability_is_invariant_to_cadence_partition() -> None:
    play, ability, cards, locations, mask, _elapsed = _inputs(batch=1, steps=1)
    mask[..., ABILITY_ACTION] = False
    whole = continuous_time_action_distribution(
        play, ability, cards, locations, mask, torch.tensor([[0.4]])
    )
    half = continuous_time_action_distribution(
        play.expand(1, 2),
        ability.expand(1, 2),
        cards.expand(1, 2, 4),
        locations.expand(1, 2, 4, 576),
        mask.expand(1, 2, NUM_ACTIONS),
        torch.full((1, 2), 0.2),
    )
    whole_survival = whole.log_probs[..., WAIT_ACTION].exp().squeeze()
    split_survival = half.log_probs[..., WAIT_ACTION].exp().prod()
    torch.testing.assert_close(whole_survival, split_survival)


def test_illegal_event_types_have_zero_rate() -> None:
    play, ability, cards, locations, mask, elapsed = _inputs(batch=1, steps=1)
    mask[..., :WAIT_ACTION] = False
    mask[..., ABILITY_ACTION] = False
    distribution = continuous_time_action_distribution(
        play, ability, cards, locations, mask, elapsed
    )
    torch.testing.assert_close(distribution.play_rate, torch.zeros_like(play))
    torch.testing.assert_close(distribution.ability_rate, torch.zeros_like(ability))
    assert distribution.log_probs[..., WAIT_ACTION].item() == 0.0
    assert int(torch.count_nonzero(distribution.log_probs.exp())) == 1


def test_deterministic_integrator_is_cadence_invariant() -> None:
    play, ability, cards, locations, mask, _elapsed = _inputs(batch=1, steps=1)
    mask[..., ABILITY_ACTION] = False
    whole = continuous_time_action_distribution(
        play, ability, cards, locations, mask, torch.tensor([[0.4]])
    )
    half = continuous_time_action_distribution(
        play.expand(1, 2),
        ability.expand(1, 2),
        cards.expand(1, 2, 4),
        locations.expand(1, 2, 4, 576),
        mask.expand(1, 2, NUM_ACTIONS),
        torch.full((1, 2), 0.2),
    )
    threshold = float(whole.interval_hazard.item()) * 0.9
    whole_actions, whole_state = deterministic_event_actions(
        whole, torch.zeros(1), threshold=threshold
    )
    half_actions, half_state = deterministic_event_actions(
        half, torch.zeros(1), threshold=threshold
    )
    assert int(whole_actions[0, 0]) != WAIT_ACTION
    assert int(half_actions[0, 0]) == WAIT_ACTION
    assert int(half_actions[0, 1]) == int(whole_actions[0, 0])
    torch.testing.assert_close(whole_state, half_state)


def test_episode_start_resets_accumulated_hazard() -> None:
    play, ability, cards, locations, mask, _elapsed = _inputs(batch=1, steps=2)
    mask[..., ABILITY_ACTION] = False
    distribution = continuous_time_action_distribution(
        play, ability, cards, locations, mask, torch.full((1, 2), 0.2)
    )
    per_step = float(distribution.interval_hazard[0, 0].detach())
    actions, state = deterministic_event_actions(
        distribution,
        torch.tensor([per_step]),
        episode_starts=torch.tensor([[True, False]]),
        threshold=per_step * 2.5,
    )
    assert actions.tolist() == [[WAIT_ACTION, WAIT_ACTION]]
    torch.testing.assert_close(state, torch.tensor([per_step * 2.0]))


def test_event_nll_backpropagates_through_timing_card_and_tile() -> None:
    values = _inputs(batch=1, steps=3)
    play, ability, cards, locations, _mask, _elapsed = values
    distribution = continuous_time_action_distribution(*values)
    actions = torch.tensor([[WAIT_ACTION, 1, ABILITY_ACTION]])
    loss = continuous_time_action_nll(distribution, actions)
    assert math.isfinite(float(loss.detach()))
    loss.backward()
    for tensor in (play, ability, cards, locations):
        assert tensor.grad is not None
        assert bool(torch.isfinite(tensor.grad).all())


def test_empty_supervision_has_finite_differentiable_zero() -> None:
    values = _inputs(batch=1, steps=1)
    distribution = continuous_time_action_distribution(*values)
    loss = continuous_time_action_nll(
        distribution,
        torch.tensor([[WAIT_ACTION]]),
        valid=torch.tensor([[False]]),
    )
    assert loss.item() == 0.0
    loss.backward()
