"""Small contextual action-value head for terminal counterfactual labels.

The reranker is deliberately separate from :class:`ClasherPolicy`.  It consumes
frozen policy state features and data-derived candidate descriptors, so training
it cannot change the retained policy's action distribution.
"""

from __future__ import annotations

import math

import torch
from torch import Tensor, nn

from .common import BOARD_HEIGHT, BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES

SPECIAL_ACTIONS = 2


def candidate_action_features(
    actions: Tensor,
    hand_ids: Tensor,
    policy_logits: Tensor,
    card_features: Tensor,
) -> Tensor:
    """Describe legal actions without encoding a card-name lookup table.

    ``card_features`` is the frozen mechanics/semantic table already stored in
    the policy checkpoint.  Placement actions select the corresponding visible
    hand card; wait and ability receive an all-zero card descriptor.
    """

    if actions.ndim != 1:
        raise ValueError("candidate actions must be one-dimensional")
    if hand_ids.shape != (NUM_HAND_SLOTS,):
        raise ValueError("hand_ids must contain exactly four playable slots")
    if (
        policy_logits.ndim != 1
        or policy_logits.shape[0] != NUM_HAND_SLOTS * NUM_TILES + SPECIAL_ACTIONS
    ):
        raise ValueError("policy logits have the wrong action dimension")
    if card_features.ndim != 2:
        raise ValueError("card_features must be a token-by-feature matrix")
    if bool(((actions < 0) | (actions >= policy_logits.shape[0])).any()):
        raise ValueError("candidate action is outside the policy action space")

    placement_limit = NUM_HAND_SLOTS * NUM_TILES
    placement = actions < placement_limit
    ability = actions == placement_limit + 1
    slot = torch.div(
        actions.clamp_max(placement_limit - 1), NUM_TILES, rounding_mode="floor"
    )
    tile = actions.remainder(NUM_TILES)
    x = tile.remainder(BOARD_WIDTH).to(policy_logits.dtype)
    y = torch.div(tile, BOARD_WIDTH, rounding_mode="floor").to(policy_logits.dtype)
    x = 2.0 * x / float(BOARD_WIDTH - 1) - 1.0
    y = 2.0 * y / float(BOARD_HEIGHT - 1) - 1.0
    x = torch.where(placement, x, torch.zeros_like(x))
    y = torch.where(placement, y, torch.zeros_like(y))

    selected_ids = hand_ids[slot]
    selected_cards = card_features[selected_ids]
    selected_cards = selected_cards * placement.to(selected_cards.dtype).unsqueeze(-1)
    modes = torch.stack([placement, ~placement & ~ability, ability], dim=-1).to(
        policy_logits.dtype
    )
    geometry = torch.stack(
        [x, y, x.square(), y.square(), x * y, x.abs(), y.abs()], dim=-1
    )
    centered_logit = policy_logits[actions] - policy_logits.max()
    parent_prior = torch.stack(
        [centered_logit, centered_logit.clamp(min=-20.0).exp()], dim=-1
    )
    return torch.cat([modes, geometry, selected_cards, parent_prior], dim=-1)


class TerminalActionReranker(nn.Module):
    """Low-rank contextual scorer with separate outcome and tie-break heads."""

    def __init__(self, state_size: int, action_size: int, rank: int = 16) -> None:
        super().__init__()
        if state_size < 1 or action_size < 1 or rank < 1:
            raise ValueError("reranker dimensions must be positive")
        self.state_size = state_size
        self.action_size = action_size
        self.rank = rank
        self.state_norm = nn.LayerNorm(state_size)
        self.action_norm = nn.LayerNorm(action_size)
        self.outcome_state = nn.Linear(state_size, rank, bias=False)
        self.outcome_action = nn.Linear(action_size, rank, bias=False)
        self.outcome_state_bias = nn.Linear(state_size, 1)
        self.outcome_action_bias = nn.Linear(action_size, 1)
        self.tie_state = nn.Linear(state_size, rank, bias=False)
        self.tie_action = nn.Linear(action_size, rank, bias=False)
        self.tie_action_bias = nn.Linear(action_size, 1)

    def forward(self, state: Tensor, actions: Tensor) -> tuple[Tensor, Tensor]:
        if state.shape[:-1] != actions.shape[:-1]:
            raise ValueError("state and action batch dimensions must match")
        if state.shape[-1] != self.state_size or actions.shape[-1] != self.action_size:
            raise ValueError("reranker feature dimension changed")
        state = self.state_norm(state)
        actions = self.action_norm(actions)
        scale = math.sqrt(self.rank)
        outcome = (
            (self.outcome_state(state) * self.outcome_action(actions)).sum(dim=-1)
            / scale
            + self.outcome_state_bias(state).squeeze(-1)
            + self.outcome_action_bias(actions).squeeze(-1)
        )
        tie = (self.tie_state(state) * self.tie_action(actions)).sum(
            dim=-1
        ) / scale + self.tie_action_bias(actions).squeeze(-1)
        return outcome, tie
