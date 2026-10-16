"""Factorized actor-visible action values for the fresh Clasher lineage."""

from __future__ import annotations

import math

import torch
from torch import Tensor, nn

from .common import NUM_HAND_SLOTS, NUM_TILES

NUM_SPECIAL_ACTIONS = 2
NUM_ACTION_MODES = 3
NUM_ACTIONS = NUM_HAND_SLOTS * NUM_TILES + NUM_SPECIAL_ACTIONS


class FactorizedActionValueHead(nn.Module):
    """Score complete actions without binding card meaning to physical slots.

    The head consumes representations already produced by the actor-visible
    encoder.  Its value decomposition mirrors the public action contract:
    play/wait/ability, a shared card pointer conditional on play, and a
    card-conditioned placement tile.  No privileged critic feature enters.
    """

    def __init__(self, state_size: int, d_model: int) -> None:
        super().__init__()
        if state_size < 1 or d_model < 1:
            raise ValueError("action-value dimensions must be positive")
        self.state_size = state_size
        self.d_model = d_model
        self.state_norm = nn.LayerNorm(state_size)
        self.card_norm = nn.LayerNorm(d_model)
        self.tile_norm = nn.LayerNorm(d_model)
        self.mode_value = nn.Linear(state_size, NUM_ACTION_MODES)
        self.card_query = nn.Linear(state_size, d_model, bias=False)
        self.tile_state_query = nn.Linear(state_size, d_model, bias=False)
        self.tile_card_query = nn.Linear(d_model, d_model, bias=False)
        self.tile_bias = nn.Linear(d_model, 1)

    def forward(
        self,
        state: Tensor,
        card_context: Tensor,
        tile_context: Tensor,
        action_mask: Tensor,
    ) -> Tensor:
        if state.ndim != 2 or state.shape[-1] != self.state_size:
            raise ValueError("state must be batch-by-state_size")
        batch = state.shape[0]
        if card_context.shape != (batch, NUM_HAND_SLOTS, self.d_model):
            raise ValueError("card context has the wrong shape")
        if tile_context.shape != (batch, NUM_TILES, self.d_model):
            raise ValueError("tile context has the wrong shape")
        if action_mask.shape != (batch, NUM_ACTIONS) or action_mask.dtype != torch.bool:
            raise ValueError("action mask has the wrong shape or dtype")
        if bool((~action_mask).all(dim=-1).any()):
            raise ValueError("every row must contain at least one legal action")

        state = self.state_norm(state)
        cards = self.card_norm(card_context)
        tiles = self.tile_norm(tile_context)
        scale = math.sqrt(self.d_model)
        modes = self.mode_value(state)
        card_values = torch.einsum("bd,bsd->bs", self.card_query(state), cards) / scale
        tile_queries = self.tile_state_query(state).unsqueeze(1)
        tile_queries = tile_queries + self.tile_card_query(cards)
        tile_values = torch.einsum("bsd,btd->bst", tile_queries, tiles) / scale
        tile_values = tile_values + self.tile_bias(tiles).transpose(1, 2)
        placement_values = modes[:, :1, None] + card_values[:, :, None] + tile_values
        values = torch.cat([placement_values.reshape(batch, -1), modes[:, 1:]], dim=-1)
        return values.masked_fill(~action_mask, -torch.inf)

    @staticmethod
    def selected_values(values: Tensor, actions: Tensor) -> Tensor:
        if values.ndim != 2 or values.shape[-1] != NUM_ACTIONS:
            raise ValueError("action values have the wrong shape")
        if actions.shape != values.shape[:1]:
            raise ValueError("actions must contain one index per value row")
        if bool(((actions < 0) | (actions >= NUM_ACTIONS)).any()):
            raise ValueError("selected action is outside the action space")
        return values.gather(-1, actions.unsqueeze(-1)).squeeze(-1)
