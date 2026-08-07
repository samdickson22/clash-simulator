from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
from typing import Dict, Optional

import numpy as np

from clasher.battle import BattleState, STANDARD_MATCH_TICKS

from .action_space import DiscreteTileActionSpace
from .deck_pool import apply_deck_to_player, load_deck_pool, sample_decks
from .obs_cv import CvObservationBuilder
from .reward_model import objective_potential_p0
from .structured_obs import StructuredObservationBuilder


@dataclass
class StepInfo:
    action_success: Dict[int, bool]
    ticks_advanced: int


class SelfPlayBattleEnv:
    """Two-player self-play environment over the battle simulator."""

    def __init__(
        self,
        decision_interval_ticks: int = 8,
        max_ticks: int = STANDARD_MATCH_TICKS,
        decks_path: str | Path = "decks.json",
        seed: Optional[int] = None,
        mirror_match: bool = False,
        canonical_perspective: bool = True,
        engine_fast_path: str = "off",
        idle_fast_forward: bool = True,
    ) -> None:
        self.decision_interval_ticks = decision_interval_ticks
        self.max_ticks = max_ticks
        self.mirror_match = mirror_match
        if engine_fast_path not in {"off", "shadow", "on"}:
            raise ValueError("engine_fast_path must be one of: off, shadow, on")
        self.engine_fast_path = engine_fast_path
        self.idle_fast_forward = idle_fast_forward
        self.rng = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)

        self.decks = load_deck_pool(decks_path)
        self.decks_path = str(decks_path)
        self.obs_builder = CvObservationBuilder(
            card_vocab=None,
            decks_path=decks_path,
            canonical_perspective=canonical_perspective,
        )
        self.action_space = DiscreteTileActionSpace(canonical_perspective=canonical_perspective)
        # Structured observations are lazy so Gym/CV-only benchmarks do not
        # pay their vocabulary construction cost.
        self._structured_obs_builder: StructuredObservationBuilder | None = None
        self._canonical_perspective = canonical_perspective

        self.battle: Optional[BattleState] = None
        self._prev_objective_p0 = 0.0
        self._mask_shadow_checks = 0
        self._mask_shadow_mismatches = 0

    def _sample_and_apply_decks(self) -> None:
        assert self.battle is not None
        deck0, deck1 = sample_decks(self.decks, rng=self.rng, mirror_match=self.mirror_match)
        apply_deck_to_player(self.battle.players[0], deck0, rng=self.rng)
        apply_deck_to_player(self.battle.players[1], deck1, rng=self.rng)

    def _reset_reward_trackers(self) -> None:
        assert self.battle is not None
        self._prev_objective_p0 = objective_potential_p0(self.battle)

    def reset(self, seed: Optional[int] = None) -> None:
        if seed is not None:
            self.rng.seed(seed)
            self.np_rng = np.random.default_rng(seed)
        self.battle = BattleState(
            fast_path=self.engine_fast_path in {"shadow", "on"},
            rng=self.rng,
        )
        self._sample_and_apply_decks()
        self._reset_reward_trackers()

    def get_observation(self, player_id: int):
        assert self.battle is not None
        return self.obs_builder.build(self.battle, player_id)

    @property
    def structured_obs_builder(self) -> StructuredObservationBuilder:
        if self._structured_obs_builder is None:
            self._structured_obs_builder = StructuredObservationBuilder(
                decks_path=self.decks_path,
                canonical_perspective=self._canonical_perspective,
            )
        return self._structured_obs_builder

    def get_structured_observation(self, player_id: int):
        assert self.battle is not None
        return self.structured_obs_builder.build(self.battle, player_id)

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
        current_p0 = objective_potential_p0(self.battle)
        delta = current_p0 - self._prev_objective_p0
        self._prev_objective_p0 = current_p0
        return {0: float(delta), 1: float(-delta)}

    def _can_spend_elixir_now(self, player_id: int) -> bool:
        assert self.battle is not None
        # We only need to know if any non-noop legal action exists.
        if self.engine_fast_path == "off":
            mask = self.action_space.legal_action_mask(self.battle, player_id, fast_path=False)
        else:
            mask = self.action_space.legal_action_mask(self.battle, player_id, fast_path=True)
        can_deploy = bool(np.any(mask[: self.action_space.no_op_action]))
        can_use_ability = bool(mask[self.action_space.ability_action])
        return can_deploy or can_use_ability

    def _compute_elixir_leak_penalty(
        self,
        *,
        actions: Dict[int, int],
        pre_elixir: Dict[int, float],
        pre_can_spend: Dict[int, bool],
        done: bool,
    ) -> Dict[int, float]:
        assert self.battle is not None
        penalties = {0: 0.0, 1: 0.0}
        for player_id in (0, 1):
            attempted = actions.get(player_id, self.action_space.no_op_action)
            if pre_elixir[player_id] >= 9.9 and pre_can_spend[player_id]:
                if attempted == self.action_space.no_op_action:
                    # Direct leak: had full elixir and chose not to spend.
                    penalties[player_id] += 0.010
            if (not done) and self.battle.players[player_id].elixir >= 9.9:
                if self._can_spend_elixir_now(player_id):
                    # Ongoing cap pressure: still floating at max after this decision window.
                    penalties[player_id] += 0.005
        return penalties

    def step(
        self,
        actions: Dict[int, int],
        *,
        pre_action_masks: Optional[Dict[int, np.ndarray]] = None,
    ) -> tuple[Dict[int, float], bool, StepInfo]:
        assert self.battle is not None

        pre_elixir = {
            0: float(self.battle.players[0].elixir),
            1: float(self.battle.players[1].elixir),
        }
        if pre_action_masks is None:
            pre_can_spend = {
                0: self._can_spend_elixir_now(0),
                1: self._can_spend_elixir_now(1),
            }
        else:
            pre_can_spend = {
                player_id: bool(
                    np.any(mask[: self.action_space.no_op_action])
                    or mask[self.action_space.ability_action]
                )
                for player_id, mask in pre_action_masks.items()
            }
            if set(pre_can_spend) != {0, 1}:
                raise ValueError("pre_action_masks must contain players 0 and 1")

        action_success: Dict[int, bool] = {}
        order = [0, 1]
        self.rng.shuffle(order)

        for player_id in order:
            action_id = actions.get(player_id, self.action_space.no_op_action)
            success = self.action_space.apply_action(self.battle, player_id, action_id)
            action_success[player_id] = success

        ticks = 0
        no_op0 = actions.get(0, self.action_space.no_op_action) == self.action_space.no_op_action
        no_op1 = actions.get(1, self.action_space.no_op_action) == self.action_space.no_op_action
        if (
            self.idle_fast_forward
            and no_op0
            and no_op1
            and hasattr(self.battle, "can_fast_forward_idle")
            and self.battle.can_fast_forward_idle()
        ):
            remaining_ticks = min(
                self.decision_interval_ticks,
                max(0, self.max_ticks - self.battle.tick),
            )
            if remaining_ticks > 0:
                ticks = self.battle.fast_forward_idle_ticks(remaining_ticks)
        else:
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

        leak_penalty = self._compute_elixir_leak_penalty(
            actions=actions,
            pre_elixir=pre_elixir,
            pre_can_spend=pre_can_spend,
            done=done,
        )
        # Keep reward strictly zero-sum.
        leak_edge = leak_penalty[1] - leak_penalty[0]
        rewards[0] += leak_edge
        rewards[1] -= leak_edge

        if done:
            if self.battle.winner is not None:
                rewards[self.battle.winner] += 1.0
                rewards[1 - self.battle.winner] -= 1.0

        return rewards, done, StepInfo(action_success=action_success, ticks_advanced=ticks)
