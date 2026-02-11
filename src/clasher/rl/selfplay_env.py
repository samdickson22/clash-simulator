from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Dict, Optional

import numpy as np

from clasher.battle import BattleState

from .action_space import DiscreteTileActionSpace
from .deck_pool import apply_deck_to_player, load_deck_pool, sample_decks
from .obs_cv import CvObservationBuilder


@dataclass
class StepInfo:
    action_success: Dict[int, bool]
    ticks_advanced: int


class SelfPlayBattleEnv:
    """Two-player self-play environment over the battle simulator."""

    def __init__(
        self,
        decision_interval_ticks: int = 8,
        max_ticks: int = 9090,
        decks_path: str = "decks.json",
        seed: Optional[int] = None,
        mirror_match: bool = False,
        canonical_perspective: bool = True,
    ) -> None:
        self.decision_interval_ticks = decision_interval_ticks
        self.max_ticks = max_ticks
        self.mirror_match = mirror_match
        self.rng = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)

        self.decks = load_deck_pool(decks_path)
        self.obs_builder = CvObservationBuilder(
            card_vocab=None,
            decks_path=decks_path,
            canonical_perspective=canonical_perspective,
        )
        self.action_space = DiscreteTileActionSpace(canonical_perspective=canonical_perspective)

        self.battle: Optional[BattleState] = None
        self._prev_damage_dealt = {0: 0.0, 1: 0.0}
        self._prev_crown_diff = {0: 0.0, 1: 0.0}

    def _sample_and_apply_decks(self) -> None:
        assert self.battle is not None
        deck0, deck1 = sample_decks(self.decks, rng=self.rng, mirror_match=self.mirror_match)
        apply_deck_to_player(self.battle.players[0], deck0, rng=self.rng)
        apply_deck_to_player(self.battle.players[1], deck1, rng=self.rng)

    def _reset_reward_trackers(self) -> None:
        self._prev_damage_dealt = {0: 0.0, 1: 0.0}
        self._prev_crown_diff = {0: 0.0, 1: 0.0}

    def reset(self) -> None:
        self.battle = BattleState()
        self._sample_and_apply_decks()
        self._reset_reward_trackers()

    def get_observation(self, player_id: int):
        assert self.battle is not None
        return self.obs_builder.build(self.battle, player_id)

    def get_action_mask(self, player_id: int) -> np.ndarray:
        assert self.battle is not None
        return self.action_space.legal_action_mask(self.battle, player_id)

    def _compute_dense_rewards(self) -> Dict[int, float]:
        assert self.battle is not None
        rewards = {0: 0.0, 1: 0.0}

        for player_id in (0, 1):
            damage_now = self.battle._tower_damage_dealt_by_player(player_id)
            enemy_start_hp = float(
                self.battle._starting_total_tower_hp.get(1 - player_id, 1.0)
            )
            delta_damage = damage_now - self._prev_damage_dealt[player_id]
            self._prev_damage_dealt[player_id] = damage_now

            crown_diff_now = (
                self.battle.players[player_id].get_crown_count()
                - self.battle.players[1 - player_id].get_crown_count()
            )
            delta_crown_diff = crown_diff_now - self._prev_crown_diff[player_id]
            self._prev_crown_diff[player_id] = crown_diff_now

            damage_reward = delta_damage / max(1.0, enemy_start_hp)
            crown_reward = 0.25 * delta_crown_diff
            rewards[player_id] = damage_reward + crown_reward

        return rewards

    def step(self, actions: Dict[int, int]) -> tuple[Dict[int, float], bool, StepInfo]:
        assert self.battle is not None

        action_success: Dict[int, bool] = {}
        order = [0, 1]
        self.rng.shuffle(order)

        for player_id in order:
            action_id = actions.get(player_id, self.action_space.no_op_action)
            success = self.action_space.apply_action(self.battle, player_id, action_id)
            action_success[player_id] = success

        ticks = 0
        while (
            ticks < self.decision_interval_ticks
            and not self.battle.game_over
            and self.battle.tick < self.max_ticks
        ):
            self.battle.step()
            ticks += 1

        done = self.battle.game_over or self.battle.tick >= self.max_ticks
        rewards = self._compute_dense_rewards()

        # Tiny invalid-action penalty (no-op is always valid).
        for player_id in (0, 1):
            attempted = actions.get(player_id, self.action_space.no_op_action)
            if attempted != self.action_space.no_op_action and not action_success.get(player_id, True):
                rewards[player_id] -= 0.01

        if done:
            if self.battle.winner is not None:
                rewards[self.battle.winner] += 1.0
                rewards[1 - self.battle.winner] -= 1.0

        return rewards, done, StepInfo(action_success=action_success, ticks_advanced=ticks)
