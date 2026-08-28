"""Device-resident stationary opponents for the practical tensor Gym."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import torch

from clasher.rl.common import BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES
from clasher.torch_sim.actions import ABILITY_ACTION, NO_OP_ACTION
from clasher.torch_sim.simple_public_mask import SimplePublicMaskTypedTables

from .simple_tensor_collector import (
    SimpleTensorPolicyBoundary,
    SimpleTensorPolicyDecision,
)
from .strategy_bots import STRATEGY_NAMES

SIMPLE_NOOP_OPPONENT_CONTRACT: Final = "simple-opponent/noop-v1"
SIMPLE_UNIFORM_OPPONENT_CONTRACT: Final = "simple-opponent/uniform-legal-v1"
SIMPLE_STRATEGY_OPPONENT_CONTRACT: Final = "simple-opponent/public-strategy-v1"


class SimpleNoopOpponentPolicy:
    """Select the always-public no-op action without recurrent state."""

    def __call__(
        self,
        boundary: SimpleTensorPolicyBoundary,
    ) -> SimpleTensorPolicyDecision:
        return SimpleTensorPolicyDecision(
            actions=torch.full(
                boundary.previous_actions.shape,
                NO_OP_ACTION,
                dtype=torch.int64,
                device=boundary.previous_actions.device,
            )
        )


class SimpleUniformLegalOpponentPolicy:
    """Stateless counter-based uniform-rank selection over the public mask."""

    def __init__(self, *, seed: int) -> None:
        if seed < 0:
            raise ValueError("opponent seed must be non-negative")
        self.seed = int(seed)

    def __call__(
        self,
        boundary: SimpleTensorPolicyBoundary,
    ) -> SimpleTensorPolicyDecision:
        masks = boundary.public_action_masks
        batch = masks.shape[0]
        legal_count = masks.sum(dim=2, dtype=torch.int64).clamp_min(1)
        row = torch.arange(batch, dtype=torch.int64, device=masks.device)[:, None]
        counter = (
            self.seed
            + (boundary.decision_index + 1) * 1_103_515_245
            + (row + 1) * 12_345
        )
        rank = torch.remainder(counter, legal_count)
        prefix = masks.to(torch.int64).cumsum(dim=2)
        selected = masks & (prefix == rank[..., None] + 1)
        return SimpleTensorPolicyDecision(
            actions=selected.to(torch.int64).argmax(dim=2)
        )


@dataclass(frozen=True)
class SimpleTensorStrategyConfig:
    """Card-agnostic public placement weights for one stationary style."""

    target_y: float
    target_y_weight: float
    center_lane_weight: float
    edge_lane_weight: float
    cost_weight: float
    spell_bonus: float
    building_bonus: float
    noop_score: float
    ability_score: float = 2.0


def _strategy_config(name: str) -> SimpleTensorStrategyConfig:
    configs = {
        "bridge-pressure": SimpleTensorStrategyConfig(
            14.0, 0.45, 0.0, 0.08, -0.12, 0.0, 0.0, 0.25
        ),
        "slow-push": SimpleTensorStrategyConfig(
            3.5, 0.35, 0.08, 0.0, 0.22, -0.5, 0.0, 0.35
        ),
        "spell-control": SimpleTensorStrategyConfig(
            18.0, 0.08, 0.12, 0.0, -0.06, 4.0, -1.0, 0.5
        ),
        "reactive-defense": SimpleTensorStrategyConfig(
            5.5, 0.4, 0.1, 0.0, -0.1, 0.0, 2.5, 0.4
        ),
        "split-lane": SimpleTensorStrategyConfig(
            12.5, 0.22, 0.0, 0.22, -0.08, 0.0, 0.0, 0.3
        ),
        "balanced": SimpleTensorStrategyConfig(
            11.5, 0.28, 0.1, 0.05, -0.04, 0.7, 0.8, 0.55
        ),
    }
    if name not in STRATEGY_NAMES:
        raise ValueError(f"unknown tensor opponent strategy: {name!r}")
    return configs[name]


class SimpleTensorStrategyOpponentPolicy:
    """Deterministic public-only placement scorer retained on the actor device."""

    def __init__(
        self,
        name: str,
        tables: SimplePublicMaskTypedTables,
        *,
        device: str | torch.device,
    ) -> None:
        self.name = name
        self.config = _strategy_config(name)
        target = torch.device(device)
        self.elixir_cost = tables.elixir_cost.to(target, dtype=torch.float32)
        self.is_spell = tables.is_spell.to(target)
        self.is_building = tables.is_building.to(target)
        placement = torch.arange(
            NUM_HAND_SLOTS * NUM_TILES,
            dtype=torch.int64,
            device=target,
        )
        tile = placement.remainder(NUM_TILES)
        self.slot = torch.div(placement, NUM_TILES, rounding_mode="floor")
        self.x = tile.remainder(BOARD_WIDTH).to(torch.float32) + 0.5
        self.y = (
            torch.div(tile, BOARD_WIDTH, rounding_mode="floor").to(torch.float32) + 0.5
        )

    def __call__(
        self,
        boundary: SimpleTensorPolicyBoundary,
    ) -> SimpleTensorPolicyDecision:
        masks = boundary.public_action_masks
        hand = boundary.actor.hand_ids[..., :NUM_HAND_SLOTS]
        token = hand[:, :, self.slot]
        safe_token = token.clamp(0, self.elixir_cost.shape[0] - 1)
        cost = self.elixir_cost[safe_token]
        spell = self.is_spell[safe_token].to(torch.float32)
        building = self.is_building[safe_token].to(torch.float32)
        config = self.config
        target_y = -torch.abs(self.y - config.target_y) * config.target_y_weight
        center = -torch.abs(self.x - (BOARD_WIDTH / 2.0)) * config.center_lane_weight
        edge = torch.abs(self.x - (BOARD_WIDTH / 2.0)) * config.edge_lane_weight
        placement_score = (
            target_y
            + center
            + edge
            + cost * config.cost_weight
            + spell * config.spell_bonus
            + building * config.building_bonus
        )
        score = torch.full(
            masks.shape,
            -torch.inf,
            dtype=torch.float32,
            device=masks.device,
        )
        score[..., :NO_OP_ACTION] = placement_score
        elixir = boundary.actor.global_features[..., 5] * 10.0
        score[..., NO_OP_ACTION] = config.noop_score + (6.0 - elixir) * 0.1
        score[..., ABILITY_ACTION] = config.ability_score
        score.masked_fill_(~masks, -torch.inf)
        return SimpleTensorPolicyDecision(actions=score.argmax(dim=2))


__all__ = [
    "SIMPLE_NOOP_OPPONENT_CONTRACT",
    "SIMPLE_STRATEGY_OPPONENT_CONTRACT",
    "SIMPLE_UNIFORM_OPPONENT_CONTRACT",
    "SimpleNoopOpponentPolicy",
    "SimpleTensorStrategyConfig",
    "SimpleTensorStrategyOpponentPolicy",
    "SimpleUniformLegalOpponentPolicy",
]
