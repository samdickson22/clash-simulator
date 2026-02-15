from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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
        decks_path: str | Path = "decks.json",
        seed: Optional[int] = None,
        mirror_match: bool = False,
        canonical_perspective: bool = True,
        engine_fast_path: str = "off",
    ) -> None:
        self.decision_interval_ticks = decision_interval_ticks
        self.max_ticks = max_ticks
        self.mirror_match = mirror_match
        if engine_fast_path not in {"off", "shadow", "on"}:
            raise ValueError("engine_fast_path must be one of: off, shadow, on")
        self.engine_fast_path = engine_fast_path
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
        self._start_tower_hp = {
            0: {"left": 1.0, "right": 1.0, "king": 1.0},
            1: {"left": 1.0, "right": 1.0, "king": 1.0},
        }
        self._prev_tower_hp = {
            0: {"left": 1.0, "right": 1.0, "king": 1.0},
            1: {"left": 1.0, "right": 1.0, "king": 1.0},
        }
        self._prev_crown_diff = {0: 0.0, 1: 0.0}
        self._mask_shadow_checks = 0
        self._mask_shadow_mismatches = 0

    def _sample_and_apply_decks(self) -> None:
        assert self.battle is not None
        deck0, deck1 = sample_decks(self.decks, rng=self.rng, mirror_match=self.mirror_match)
        apply_deck_to_player(self.battle.players[0], deck0, rng=self.rng)
        apply_deck_to_player(self.battle.players[1], deck1, rng=self.rng)

    def _reset_reward_trackers(self) -> None:
        assert self.battle is not None
        for player_id in (0, 1):
            p = self.battle.players[player_id]
            tower_hp = {
                "left": float(p.left_tower_hp),
                "right": float(p.right_tower_hp),
                "king": float(p.king_tower_hp),
            }
            self._start_tower_hp[player_id] = dict(tower_hp)
            self._prev_tower_hp[player_id] = dict(tower_hp)
        self._prev_crown_diff = {0: 0.0, 1: 0.0}

    def reset(self) -> None:
        self.battle = BattleState(fast_path=self.engine_fast_path in {"shadow", "on"})
        self._sample_and_apply_decks()
        self._reset_reward_trackers()

    def get_observation(self, player_id: int):
        assert self.battle is not None
        return self.obs_builder.build(self.battle, player_id)

    def get_action_mask(self, player_id: int) -> np.ndarray:
        assert self.battle is not None
        if self.engine_fast_path == "off":
            return self.action_space.legal_action_mask(self.battle, player_id, fast_path=False)
        if self.engine_fast_path == "on":
            return self.action_space.legal_action_mask(self.battle, player_id, fast_path=True)

        fast_mask = self.action_space.legal_action_mask(self.battle, player_id, fast_path=True)
        # Shadow mode: sample parity checks against legacy mask.
        if float(self.np_rng.random()) < 0.005:
            legacy_mask = self.action_space.legal_action_mask(self.battle, player_id, fast_path=False)
            self._mask_shadow_checks += 1
            if not np.array_equal(fast_mask, legacy_mask):
                self._mask_shadow_mismatches += 1
        return fast_mask

    def fast_path_metrics(self) -> Dict[str, float]:
        checks = max(1, self._mask_shadow_checks)
        return {
            "mask_shadow_checks": float(self._mask_shadow_checks),
            "mask_shadow_mismatches": float(self._mask_shadow_mismatches),
            "mask_shadow_divergence": float(self._mask_shadow_mismatches) / float(checks),
        }

    def pop_fast_path_metrics(self) -> Dict[str, float]:
        metrics = self.fast_path_metrics()
        self._mask_shadow_checks = 0
        self._mask_shadow_mismatches = 0
        return metrics

    def _compute_dense_rewards(self) -> Dict[int, float]:
        assert self.battle is not None
        rewards = {0: 0.0, 1: 0.0}
        current_tower_hp = {
            0: {
                "left": float(self.battle.players[0].left_tower_hp),
                "right": float(self.battle.players[0].right_tower_hp),
                "king": float(self.battle.players[0].king_tower_hp),
            },
            1: {
                "left": float(self.battle.players[1].left_tower_hp),
                "right": float(self.battle.players[1].right_tower_hp),
                "king": float(self.battle.players[1].king_tower_hp),
            },
        }
        step_tower_damage_taken = {
            0: {
                "left": max(0.0, self._prev_tower_hp[0]["left"] - current_tower_hp[0]["left"]),
                "right": max(0.0, self._prev_tower_hp[0]["right"] - current_tower_hp[0]["right"]),
                "king": max(0.0, self._prev_tower_hp[0]["king"] - current_tower_hp[0]["king"]),
            },
            1: {
                "left": max(0.0, self._prev_tower_hp[1]["left"] - current_tower_hp[1]["left"]),
                "right": max(0.0, self._prev_tower_hp[1]["right"] - current_tower_hp[1]["right"]),
                "king": max(0.0, self._prev_tower_hp[1]["king"] - current_tower_hp[1]["king"]),
            },
        }

        for player_id in (0, 1):
            enemy_id = 1 - player_id
            dealt = step_tower_damage_taken[enemy_id]
            taken = step_tower_damage_taken[player_id]

            enemy_start_princess_hp = max(
                1.0,
                self._start_tower_hp[enemy_id]["left"] + self._start_tower_hp[enemy_id]["right"],
            )
            enemy_start_king_hp = max(1.0, self._start_tower_hp[enemy_id]["king"])
            own_start_princess_hp = max(
                1.0,
                self._start_tower_hp[player_id]["left"] + self._start_tower_hp[player_id]["right"],
            )
            own_start_king_hp = max(1.0, self._start_tower_hp[player_id]["king"])

            dealt_princess_norm = (dealt["left"] + dealt["right"]) / enemy_start_princess_hp
            dealt_king_norm = dealt["king"] / enemy_start_king_hp
            taken_princess_norm = (taken["left"] + taken["right"]) / own_start_princess_hp
            taken_king_norm = taken["king"] / own_start_king_hp

            enemy_princess_alive = int(current_tower_hp[enemy_id]["left"] > 0.0) + int(current_tower_hp[enemy_id]["right"] > 0.0)
            if enemy_princess_alive == 2:
                king_reward_weight = 0.05
            elif enemy_princess_alive == 1:
                king_reward_weight = 0.20
            else:
                king_reward_weight = 0.35

            progress_reward = 0.70 * dealt_princess_norm + king_reward_weight * dealt_king_norm
            damage_taken_penalty = 0.50 * taken_princess_norm + 0.35 * taken_king_norm

            crown_diff_now = (
                self.battle.players[player_id].get_crown_count()
                - self.battle.players[1 - player_id].get_crown_count()
            )
            delta_crown_diff = crown_diff_now - self._prev_crown_diff[player_id]
            self._prev_crown_diff[player_id] = crown_diff_now

            crown_reward = 0.50 * delta_crown_diff
            rewards[player_id] = progress_reward - damage_taken_penalty + crown_reward

        self._prev_tower_hp = {
            0: dict(current_tower_hp[0]),
            1: dict(current_tower_hp[1]),
        }

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
                rewards[self.battle.winner] += 1.5
                rewards[1 - self.battle.winner] -= 1.5

        return rewards, done, StepInfo(action_success=action_success, ticks_advanced=ticks)
