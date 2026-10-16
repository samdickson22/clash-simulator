from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from clasher.battle import BattleState

from .action_space import DiscreteTileActionSpace
from .common import NUM_HAND_SLOTS, NUM_TILES
from .reward_model import DEFENSE_V2, reward_win_prob_p0


@dataclass(frozen=True)
class LocationLookaheadResult:
    action: int
    base_action: int
    base_score: float
    selected_score: float
    candidates: int

    @property
    def overridden(self) -> bool:
        return self.action != self.base_action


class LocationLookahead:
    """Rerank only the policy-selected card's best legal locations.

    The counterfactual advances already-public board state while assuming no new
    opponent deployment during the short horizon. It never changes card choice,
    deploy timing, recurrent state, or action legality, and it never reads the
    opponent's hidden hand, cycle, or elixir.
    """

    def __init__(
        self,
        action_space: DiscreteTileActionSpace,
        *,
        top_k: int = 4,
        horizon_ticks: int = 96,
        prior_weight: float = 0.02,
        min_value_gain: float = 0.0,
        reward_profile: str = DEFENSE_V2,
    ) -> None:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if horizon_ticks <= 0:
            raise ValueError("horizon_ticks must be positive")
        if prior_weight < 0.0:
            raise ValueError("prior_weight must be non-negative")
        if min_value_gain < 0.0:
            raise ValueError("min_value_gain must be non-negative")
        self.action_space = action_space
        self.top_k = top_k
        self.horizon_ticks = horizon_ticks
        self.prior_weight = prior_weight
        self.min_value_gain = min_value_gain
        self.reward_profile = reward_profile

    def candidate_actions(
        self,
        *,
        base_action: int,
        location_logits: np.ndarray,
        action_mask: np.ndarray,
    ) -> list[int]:
        if not 0 <= base_action < NUM_HAND_SLOTS * NUM_TILES:
            return [base_action]
        slot = base_action // NUM_TILES
        start = slot * NUM_TILES
        legal = np.flatnonzero(action_mask[start : start + NUM_TILES])
        if legal.size <= 1:
            return [base_action]
        count = min(self.top_k, int(legal.size))
        slot_logits = np.asarray(location_logits[slot], dtype=np.float64)
        ranked = legal[np.argsort(-slot_logits[legal], kind="stable")[:count]]
        actions = [base_action]
        actions.extend(
            start + int(tile)
            for tile in ranked.tolist()
            if start + int(tile) != base_action
        )
        return actions

    def select_action(
        self,
        battle: BattleState,
        player_id: int,
        *,
        base_action: int,
        location_logits: np.ndarray,
        action_mask: np.ndarray,
    ) -> LocationLookaheadResult:
        candidates = self.candidate_actions(
            base_action=base_action,
            location_logits=location_logits,
            action_mask=action_mask,
        )
        if len(candidates) == 1:
            return LocationLookaheadResult(
                action=base_action,
                base_action=base_action,
                base_score=0.0,
                selected_score=0.0,
                candidates=1,
            )
        slot = base_action // NUM_TILES
        base_tile = base_action % NUM_TILES
        base_logit = float(location_logits[slot, base_tile])
        scores: list[float] = []
        for action in candidates:
            simulation = battle.clone()
            self.action_space.apply_action(simulation, player_id, action)
            for _ in range(self.horizon_ticks):
                if simulation.game_over:
                    break
                simulation.step()
            probability_p0 = reward_win_prob_p0(simulation, self.reward_profile)
            public_value = probability_p0 if player_id == 0 else 1.0 - probability_p0
            tile = action % NUM_TILES
            prior_delta = float(location_logits[slot, tile]) - base_logit
            scores.append(public_value + self.prior_weight * prior_delta)
        best_index = int(np.argmax(np.asarray(scores, dtype=np.float64)))
        if scores[best_index] - scores[0] < self.min_value_gain:
            best_index = 0
        return LocationLookaheadResult(
            action=candidates[best_index],
            base_action=base_action,
            base_score=scores[0],
            selected_score=scores[best_index],
            candidates=len(candidates),
        )
