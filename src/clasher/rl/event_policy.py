"""Continuous-time event policy for sparse Clash Royale actions.

The ordinary discrete policy asks the network to classify ``wait`` again at
every inference call.  That makes behavior depend on the caller's cadence and
lets the many repeated wait rows dominate supervised metrics.  This module
instead treats placements and champion abilities as competing point-process
events.  The network predicts rates per second; the probability of no event in
an interval of length ``dt`` is exactly ``exp(-rate * dt)``.

The environment-facing action IDs remain unchanged.  Placement probability is
factorized into event timing, card choice, and a card-conditioned tile.  All
factors use the actor-visible legal-action mask.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import cast

import torch
from torch import Tensor
from torch.nn import functional as F

from .common import NUM_HAND_SLOTS, NUM_TILES

PLACEMENT_ACTIONS = NUM_HAND_SLOTS * NUM_TILES
WAIT_ACTION = PLACEMENT_ACTIONS
ABILITY_ACTION = WAIT_ACTION + 1
NUM_ACTIONS = ABILITY_ACTION + 1


def _masked_log_softmax(logits: Tensor, mask: Tensor, *, dim: int) -> Tensor:
    """Return exact negative infinity outside ``mask``, including empty rows."""

    if logits.shape != mask.shape:
        raise ValueError("masked logits and mask must have identical shapes")
    masked = logits.masked_fill(~mask, -torch.inf)
    normalizer = torch.logsumexp(masked, dim=dim, keepdim=True)
    normalized = masked - normalizer
    return torch.where(mask, normalized, torch.full_like(normalized, -torch.inf))


def _log_event_probability(interval_hazard: Tensor) -> Tensor:
    """Compute ``log(1 - exp(-h))`` stably, with ``h=0 -> -inf``."""

    return torch.log(-torch.expm1(-interval_hazard))


@dataclass(frozen=True)
class ContinuousTimeActionDistribution:
    """Exact flattened action probabilities plus their event-rate factors."""

    log_probs: Tensor
    play_rate: Tensor
    ability_rate: Tensor
    interval_hazard: Tensor

    def log_prob(self, actions: Tensor) -> Tensor:
        if actions.shape != self.log_probs.shape[:-1]:
            raise ValueError("actions do not match the distribution batch shape")
        return self.log_probs.gather(-1, actions.unsqueeze(-1)).squeeze(-1)

    def entropy(self) -> Tensor:
        probabilities = self.log_probs.exp()
        terms = torch.where(
            probabilities > 0.0,
            probabilities * self.log_probs,
            torch.zeros_like(probabilities),
        )
        return -terms.sum(dim=-1)

    def sample(self) -> Tensor:
        return cast(
            Tensor, torch.distributions.Categorical(logits=self.log_probs).sample()
        )


def continuous_time_action_distribution(
    raw_play_rate: Tensor,
    raw_ability_rate: Tensor,
    card_logits: Tensor,
    location_logits: Tensor,
    action_mask: Tensor,
    delta_seconds: Tensor,
) -> ContinuousTimeActionDistribution:
    """Build a cadence-invariant distribution over the existing flat actions.

    ``raw_*_rate`` are unconstrained neural outputs.  Softplus converts them to
    non-negative event rates per second.  An illegal event type has exactly zero
    rate, independent of its raw output.  ``delta_seconds`` is the elapsed public
    game time represented by this policy observation.
    """

    batch_shape = raw_play_rate.shape
    if raw_ability_rate.shape != batch_shape or delta_seconds.shape != batch_shape:
        raise ValueError("event rates and elapsed seconds must share a batch shape")
    if card_logits.shape != (*batch_shape, NUM_HAND_SLOTS):
        raise ValueError("card logits must end in the four current hand slots")
    if location_logits.shape != (*batch_shape, NUM_HAND_SLOTS, NUM_TILES):
        raise ValueError("location logits have the wrong action geometry")
    if action_mask.shape != (*batch_shape, NUM_ACTIONS):
        raise ValueError("action mask has the wrong flattened action size")
    if not bool(action_mask[..., WAIT_ACTION].all()):
        raise ValueError("the public action mask must always admit wait")
    if bool((delta_seconds < 0.0).any()) or not bool(torch.isfinite(delta_seconds).all()):
        raise ValueError("elapsed seconds must be finite and non-negative")

    placement_mask = action_mask[..., :PLACEMENT_ACTIONS].reshape(
        *batch_shape, NUM_HAND_SLOTS, NUM_TILES
    )
    card_mask = placement_mask.any(dim=-1)
    play_legal = card_mask.any(dim=-1)
    ability_legal = action_mask[..., ABILITY_ACTION]

    play_rate = torch.where(
        play_legal, F.softplus(raw_play_rate), torch.zeros_like(raw_play_rate)
    )
    ability_rate = torch.where(
        ability_legal,
        F.softplus(raw_ability_rate),
        torch.zeros_like(raw_ability_rate),
    )
    total_rate = play_rate + ability_rate
    interval_hazard = total_rate * delta_seconds
    log_wait = -interval_hazard
    log_event = _log_event_probability(interval_hazard)

    log_total_rate = torch.log(total_rate)
    log_play_cause = torch.where(
        play_rate > 0.0,
        torch.log(play_rate) - log_total_rate,
        torch.full_like(play_rate, -torch.inf),
    )
    log_ability_cause = torch.where(
        ability_rate > 0.0,
        torch.log(ability_rate) - log_total_rate,
        torch.full_like(ability_rate, -torch.inf),
    )
    card_log_probs = _masked_log_softmax(card_logits, card_mask, dim=-1)
    location_log_probs = _masked_log_softmax(
        location_logits, placement_mask, dim=-1
    )
    placement_log_probs = (
        log_event[..., None, None]
        + log_play_cause[..., None, None]
        + card_log_probs[..., :, None]
        + location_log_probs
    ).reshape(*batch_shape, PLACEMENT_ACTIONS)
    ability_log_prob = log_event + log_ability_cause
    log_probs = torch.cat(
        [
            placement_log_probs,
            log_wait.unsqueeze(-1),
            ability_log_prob.unsqueeze(-1),
        ],
        dim=-1,
    )
    log_probs = torch.where(
        action_mask,
        log_probs,
        torch.full_like(log_probs, -torch.inf),
    )
    return ContinuousTimeActionDistribution(
        log_probs=log_probs,
        play_rate=play_rate,
        ability_rate=ability_rate,
        interval_hazard=interval_hazard,
    )


def deterministic_event_actions(
    distribution: ContinuousTimeActionDistribution,
    initial_cumulative_hazard: Tensor,
    *,
    episode_starts: Tensor | None = None,
    threshold: float = math.log(2.0),
) -> tuple[Tensor, Tensor]:
    """Decode a sequence by integrating rate instead of counting model calls.

    The default threshold fires at the median event time of a constant-rate
    process.  Accumulated hazard resets after an emitted event or an episode
    start.  Splitting one time interval into several calls therefore does not
    change the trigger boundary when the predicted rate is unchanged.
    """

    if distribution.log_probs.ndim < 3:
        raise ValueError("deterministic event decoding requires [batch, time, action]")
    batch, steps = distribution.log_probs.shape[:2]
    if distribution.log_probs.shape[-1] != NUM_ACTIONS:
        raise ValueError("distribution has the wrong flattened action size")
    if initial_cumulative_hazard.shape != (batch,):
        raise ValueError("initial cumulative hazard must have shape [batch]")
    if not math.isfinite(threshold) or threshold <= 0.0:
        raise ValueError("event threshold must be finite and positive")
    if episode_starts is None:
        episode_starts = torch.zeros(
            (batch, steps), dtype=torch.bool, device=distribution.log_probs.device
        )
    if episode_starts.shape != (batch, steps) or episode_starts.dtype != torch.bool:
        raise ValueError("episode starts must be bool [batch, time]")

    cumulative = initial_cumulative_hazard
    actions: list[Tensor] = []
    for index in range(steps):
        cumulative = torch.where(
            episode_starts[:, index], torch.zeros_like(cumulative), cumulative
        )
        cumulative = cumulative + distribution.interval_hazard[:, index]
        event_logits = distribution.log_probs[:, index].clone()
        event_logits[:, WAIT_ACTION] = -torch.inf
        best_event = event_logits.argmax(dim=-1)
        has_event = torch.isfinite(event_logits).any(dim=-1)
        fire = (cumulative >= threshold) & has_event
        action = torch.where(
            fire,
            best_event,
            torch.full_like(best_event, WAIT_ACTION),
        )
        actions.append(action)
        cumulative = torch.where(fire, torch.zeros_like(cumulative), cumulative)
    return torch.stack(actions, dim=1), cumulative


def continuous_time_action_nll(
    distribution: ContinuousTimeActionDistribution,
    actions: Tensor,
    *,
    valid: Tensor | None = None,
) -> Tensor:
    """Return the unweighted event-time/action negative log likelihood."""

    losses = -distribution.log_prob(actions)
    if valid is None:
        valid = torch.ones_like(losses, dtype=torch.bool)
    if valid.shape != losses.shape or valid.dtype != torch.bool:
        raise ValueError("valid rows must be bool with the action batch shape")
    selected = losses[valid]
    if not selected.numel():
        finite_log_probs = torch.where(
            torch.isfinite(distribution.log_probs),
            distribution.log_probs,
            torch.zeros_like(distribution.log_probs),
        )
        return finite_log_probs.sum() * 0.0
    if not bool(torch.isfinite(selected).all()):
        raise ValueError("a supervised action has zero probability")
    return selected.mean()


__all__ = [
    "ABILITY_ACTION",
    "NUM_ACTIONS",
    "PLACEMENT_ACTIONS",
    "WAIT_ACTION",
    "ContinuousTimeActionDistribution",
    "continuous_time_action_distribution",
    "continuous_time_action_nll",
    "deterministic_event_actions",
]
