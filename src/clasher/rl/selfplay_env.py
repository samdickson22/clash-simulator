from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from clasher.battle import STANDARD_MATCH_TICKS, BattleState

from .action_space import DiscreteTileActionSpace
from .causal_vision import CausalVisionTracker
from .common import CvObservation
from .deck_pool import (
    DeckMatchup,
    apply_deck_to_player,
    apply_ordered_deck_to_player,
    load_deck_pool,
    load_matchup_pool,
    sample_deck,
    sample_decks,
)
from .defense_scenarios import (
    DefenseScenarioSpec,
    apply_defense_scenario,
    defense_scenario_outcome,
)
from .obs_cv import CvObservationBuilder
from .public_action_mask import PublicActionMaskBuilder
from .public_observation import (
    TV_ROYALE_PILOT_DEGRADATION,
    degrade_simulator_public_observation,
)
from .reward_model import OBJECTIVE_V1, REWARD_PROFILES, reward_potential_p0
from .structured_obs import (
    ActorObservation,
    StructuredObservation,
    StructuredObservationBuilder,
)


@dataclass
class StepInfo:
    action_success: dict[int, bool]
    ticks_advanced: int


class SelfPlayBattleEnv:
    """Two-player self-play environment over the battle simulator."""

    def __init__(
        self,
        decision_interval_ticks: int = 8,
        max_ticks: int = STANDARD_MATCH_TICKS,
        decks_path: str | Path = "decks.json",
        sampling_decks_path: str | Path | None = None,
        player0_sampling_decks_path: str | Path | None = None,
        player1_sampling_decks_path: str | Path | None = None,
        matchups_path: str | Path | None = None,
        matchup_probability: float = 0.0,
        learner_player_id: int = 0,
        seed: int | None = None,
        mirror_match: bool = False,
        canonical_perspective: bool = True,
        canonical_lane_globals: bool = False,
        engine_fast_path: str = "off",
        idle_fast_forward: bool = True,
        reward_profile: str = OBJECTIVE_V1,
        reward_shaping_gamma: float | None = None,
        elixir_leak_penalty_scale: float = 1.0,
        defense_scenario_probability: float = 0.0,
        defense_scenario_minimum_elixir: int = 4,
        defense_scenario_maximum_elixir: int = 7,
        defense_scenario_horizon_ticks: int = 240,
        defense_scenario_reward_scale: float = 1.0,
    ) -> None:
        self.decision_interval_ticks = decision_interval_ticks
        self.max_ticks = max_ticks
        self.mirror_match = mirror_match
        if engine_fast_path not in {"off", "shadow", "on"}:
            raise ValueError("engine_fast_path must be one of: off, shadow, on")
        self.engine_fast_path = engine_fast_path
        self.idle_fast_forward = idle_fast_forward
        if reward_profile not in REWARD_PROFILES:
            raise ValueError(
                f"reward_profile must be one of {REWARD_PROFILES}, got {reward_profile!r}"
            )
        self.reward_profile = reward_profile
        if reward_shaping_gamma is not None and not 0.0 < reward_shaping_gamma <= 1.0:
            raise ValueError("reward_shaping_gamma must be in (0, 1]")
        if elixir_leak_penalty_scale < 0.0:
            raise ValueError("elixir_leak_penalty_scale must be non-negative")
        self.reward_shaping_gamma = reward_shaping_gamma
        self.elixir_leak_penalty_scale = float(elixir_leak_penalty_scale)
        if not 0.0 <= defense_scenario_probability <= 1.0:
            raise ValueError("defense_scenario_probability must be between zero and one")
        if not 1 <= defense_scenario_minimum_elixir <= defense_scenario_maximum_elixir:
            raise ValueError("defense scenario elixir bounds are invalid")
        if defense_scenario_horizon_ticks <= 0:
            raise ValueError("defense scenario horizon must be positive")
        if defense_scenario_reward_scale < 0.0:
            raise ValueError("defense scenario reward scale must be non-negative")
        self.defense_scenario_probability = float(defense_scenario_probability)
        self.defense_scenario_minimum_elixir = int(defense_scenario_minimum_elixir)
        self.defense_scenario_maximum_elixir = int(defense_scenario_maximum_elixir)
        self.defense_scenario_horizon_ticks = int(defense_scenario_horizon_ticks)
        self.defense_scenario_reward_scale = float(defense_scenario_reward_scale)
        if not 0.0 <= matchup_probability <= 1.0:
            raise ValueError("matchup_probability must be between zero and one")
        if learner_player_id not in (0, 1):
            raise ValueError("learner_player_id must be 0 or 1")
        if (matchups_path is None) != (matchup_probability == 0.0):
            raise ValueError(
                "matchups_path and a positive matchup_probability must be used together"
            )
        if mirror_match and matchups_path is not None:
            raise ValueError("exact matchup sampling is incompatible with mirror_match")
        self.rng = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)

        shared_sampling_path = sampling_decks_path or decks_path
        self.decks = load_deck_pool(shared_sampling_path)
        self.player0_decks = (
            load_deck_pool(player0_sampling_decks_path)
            if player0_sampling_decks_path is not None
            else self.decks
        )
        self.player1_decks = (
            load_deck_pool(player1_sampling_decks_path)
            if player1_sampling_decks_path is not None
            else self.decks
        )
        self.decks_path = str(decks_path)
        self.sampling_decks_path = str(shared_sampling_path)
        self.player0_sampling_decks_path = (
            str(player0_sampling_decks_path)
            if player0_sampling_decks_path is not None
            else self.sampling_decks_path
        )
        self.player1_sampling_decks_path = (
            str(player1_sampling_decks_path)
            if player1_sampling_decks_path is not None
            else self.sampling_decks_path
        )
        self.matchups: list[DeckMatchup] | None = (
            load_matchup_pool(matchups_path) if matchups_path is not None else None
        )
        self.matchups_path = str(matchups_path) if matchups_path is not None else None
        self.matchup_probability = matchup_probability
        self.learner_player_id = learner_player_id
        self.obs_builder = CvObservationBuilder(
            card_vocab=None,
            decks_path=decks_path,
            canonical_perspective=canonical_perspective,
        )
        self.action_space = DiscreteTileActionSpace(
            canonical_perspective=canonical_perspective
        )
        # Structured observations are lazy so Gym/CV-only benchmarks do not
        # pay their vocabulary construction cost.
        self._structured_obs_builder: StructuredObservationBuilder | None = None
        self._canonical_perspective = canonical_perspective
        self._canonical_lane_globals = bool(canonical_lane_globals)
        self._causal_vision_trackers = {
            player_id: CausalVisionTracker(
                max_gap_frames=max(6, 2 * decision_interval_ticks)
            )
            for player_id in (0, 1)
        }
        self._causal_vision_observation_cache: dict[
            tuple[int, str], tuple[int, StructuredObservation]
        ] = {}
        self._public_action_mask_builder: PublicActionMaskBuilder | None = None

        self.battle: BattleState | None = None
        self.defense_scenario: DefenseScenarioSpec | None = None
        self._prev_reward_potential_p0 = 0.0
        self._mask_shadow_checks = 0
        self._mask_shadow_mismatches = 0

    def _sample_and_apply_decks(self) -> None:
        assert self.battle is not None
        if (
            self.matchups is not None
            and self.rng.random() < self.matchup_probability
        ):
            matchup = self.rng.choices(
                self.matchups,
                weights=[item.weight for item in self.matchups],
                k=1,
            )[0]
            learner_deck = matchup.learner_cards
            opponent_deck = matchup.opponent_cards
            if self.learner_player_id == 0:
                deck0, deck1 = learner_deck, opponent_deck
            else:
                deck0, deck1 = opponent_deck, learner_deck
        elif self.player0_decks is self.decks and self.player1_decks is self.decks:
            deck0, deck1 = sample_decks(
                self.decks, rng=self.rng, mirror_match=self.mirror_match
            )
        else:
            deck0 = sample_deck(self.player0_decks, self.rng)
            deck1 = (
                list(deck0)
                if self.mirror_match
                else sample_deck(self.player1_decks, self.rng)
            )
        apply_deck_to_player(self.battle.players[0], deck0, rng=self.rng)
        apply_deck_to_player(self.battle.players[1], deck1, rng=self.rng)

    def _reset_reward_trackers(self) -> None:
        assert self.battle is not None
        self._prev_reward_potential_p0 = reward_potential_p0(
            self.battle,
            self.reward_profile,
        )

    def reset(
        self,
        seed: int | None = None,
        *,
        ordered_decks: tuple[Sequence[str], Sequence[str]] | None = None,
    ) -> None:
        if seed is not None:
            self.rng.seed(seed)
            self.np_rng = np.random.default_rng(seed)
        self.battle = BattleState(
            fast_path=self.engine_fast_path in {"shadow", "on"},
            rng=self.rng,
        )
        if ordered_decks is None:
            self._sample_and_apply_decks()
        else:
            apply_ordered_deck_to_player(
                self.battle.players[0], ordered_decks[0]
            )
            apply_ordered_deck_to_player(
                self.battle.players[1], ordered_decks[1]
            )
        self.defense_scenario = None
        if self.rng.random() < self.defense_scenario_probability:
            self.defense_scenario = apply_defense_scenario(
                self.battle,
                self.learner_player_id,
                rng=self.rng,
                minimum_elixir=self.defense_scenario_minimum_elixir,
                maximum_elixir=self.defense_scenario_maximum_elixir,
            )
        self._reset_reward_trackers()
        for tracker in self._causal_vision_trackers.values():
            tracker.reset()
        self._causal_vision_observation_cache.clear()

    def get_observation(self, player_id: int) -> CvObservation:
        assert self.battle is not None
        return self.obs_builder.build(self.battle, player_id)

    @property
    def structured_obs_builder(self) -> StructuredObservationBuilder:
        if self._structured_obs_builder is None:
            self._structured_obs_builder = StructuredObservationBuilder(
                decks_path=self.decks_path,
                canonical_perspective=self._canonical_perspective,
                canonical_lane_globals=self._canonical_lane_globals,
            )
        return self._structured_obs_builder

    def get_structured_observation(
        self,
        player_id: int,
        *,
        actor_observation_domain: str = "simulator-exact",
    ) -> StructuredObservation:
        assert self.battle is not None
        exact = self.structured_obs_builder.build(self.battle, player_id)
        if actor_observation_domain == "simulator-exact":
            return exact
        if actor_observation_domain not in {
            "causal-vision-v1",
            "causal-frame-v1",
        }:
            raise ValueError(f"unknown actor observation domain {actor_observation_domain!r}")
        cache_key = (player_id, actor_observation_domain)
        cached = self._causal_vision_observation_cache.get(cache_key)
        if cached is not None and cached[0] == self.battle.tick:
            return cached[1]
        public = degrade_simulator_public_observation(
            ActorObservation(
                entity_ids=exact.entity_ids,
                entity_features=exact.entity_features,
                entity_mask=exact.entity_mask,
                hand_ids=exact.hand_ids,
                global_features=exact.global_features,
                opponent_history_ids=exact.opponent_history_ids,
                opponent_history_ages=exact.opponent_history_ages,
                opponent_seen_card_ids=exact.opponent_seen_card_ids,
            ),
            profile=TV_ROYALE_PILOT_DEGRADATION,
            rng=self.np_rng,
        )
        if actor_observation_domain == "causal-frame-v1":
            observed = public
        else:
            observed = self._causal_vision_trackers[player_id].update(
                public,
                frame=self.battle.tick,
            )
        actor = observed.observation
        projected = replace(
            exact,
            entity_ids=actor.entity_ids,
            entity_features=actor.entity_features,
            entity_mask=actor.entity_mask,
            hand_ids=actor.hand_ids,
            global_features=actor.global_features,
            opponent_history_ids=actor.opponent_history_ids,
            opponent_history_ages=actor.opponent_history_ages,
            opponent_seen_card_ids=actor.opponent_seen_card_ids,
            entity_id_confidence=observed.entity_id_confidence,
            entity_feature_confidence=observed.entity_feature_confidence,
            hand_id_confidence=observed.hand_id_confidence,
            global_feature_confidence=observed.global_feature_confidence,
        )
        self._causal_vision_observation_cache[cache_key] = (
            self.battle.tick,
            projected,
        )
        return projected

    def get_action_mask(
        self,
        player_id: int,
        *,
        actor_observation_domain: str = "simulator-exact",
        structured_observation: StructuredObservation | None = None,
    ) -> np.ndarray:
        assert self.battle is not None
        if actor_observation_domain in {"causal-vision-v1", "causal-frame-v1"}:
            observation = structured_observation or self.get_structured_observation(
                player_id,
                actor_observation_domain=actor_observation_domain,
            )
            if self._public_action_mask_builder is None:
                self._public_action_mask_builder = PublicActionMaskBuilder(
                    self.structured_obs_builder
                )
            return self._public_action_mask_builder.build(observation)
        if actor_observation_domain != "simulator-exact":
            raise ValueError(f"unknown actor observation domain {actor_observation_domain!r}")
        if self.engine_fast_path == "off":
            return self.action_space.legal_action_mask(
                self.battle, player_id, fast_path=False
            )
        if self.engine_fast_path == "on":
            return self.action_space.legal_action_mask(
                self.battle, player_id, fast_path=True
            )

        fast_mask = self.action_space.legal_action_mask(
            self.battle, player_id, fast_path=True
        )
        # Shadow mode: sample parity checks against legacy mask.
        if float(self.np_rng.random()) < 0.005:
            legacy_mask = self.action_space.legal_action_mask(
                self.battle, player_id, fast_path=False
            )
            self._mask_shadow_checks += 1
            if not np.array_equal(fast_mask, legacy_mask):
                self._mask_shadow_mismatches += 1
        return fast_mask

    def fast_path_metrics(self) -> dict[str, float]:
        checks = max(1, self._mask_shadow_checks)
        return {
            "mask_shadow_checks": float(self._mask_shadow_checks),
            "mask_shadow_mismatches": float(self._mask_shadow_mismatches),
            "mask_shadow_divergence": float(self._mask_shadow_mismatches)
            / float(checks),
        }

    def pop_fast_path_metrics(self) -> dict[str, float]:
        metrics = self.fast_path_metrics()
        self._mask_shadow_checks = 0
        self._mask_shadow_mismatches = 0
        return metrics

    def _compute_dense_rewards(self, *, done: bool) -> dict[int, float]:
        assert self.battle is not None
        current_p0 = reward_potential_p0(self.battle, self.reward_profile)
        if self.reward_shaping_gamma is None:
            # Legacy checkpoint-compatible shaping.
            delta = current_p0 - self._prev_reward_potential_p0
        else:
            # Policy-invariant potential shaping uses an absorbing terminal
            # state with Phi=0, not the final visible battle state's residue.
            next_potential = 0.0 if done else current_p0
            delta = (
                self.reward_shaping_gamma * next_potential
                - self._prev_reward_potential_p0
            )
        self._prev_reward_potential_p0 = current_p0
        return {0: float(delta), 1: float(-delta)}

    def _can_spend_elixir_now(self, player_id: int) -> bool:
        assert self.battle is not None
        # We only need to know if any non-noop legal action exists.
        if self.engine_fast_path == "off":
            mask = self.action_space.legal_action_mask(
                self.battle, player_id, fast_path=False
            )
        else:
            mask = self.action_space.legal_action_mask(
                self.battle, player_id, fast_path=True
            )
        can_deploy = bool(np.any(mask[: self.action_space.no_op_action]))
        can_use_ability = bool(mask[self.action_space.ability_action])
        return can_deploy or can_use_ability

    def _compute_elixir_leak_penalty(
        self,
        *,
        actions: dict[int, int],
        pre_elixir: dict[int, float],
        pre_can_spend: dict[int, bool],
        done: bool,
    ) -> dict[int, float]:
        assert self.battle is not None
        penalties = {0: 0.0, 1: 0.0}
        for player_id in (0, 1):
            attempted = actions.get(player_id, self.action_space.no_op_action)
            if (
                pre_elixir[player_id] >= 9.9
                and pre_can_spend[player_id]
                and attempted == self.action_space.no_op_action
            ):
                # Direct leak: had full elixir and chose not to spend.
                penalties[player_id] += 0.010
            if (
                not done
                and self.battle.players[player_id].elixir >= 9.9
                and self._can_spend_elixir_now(player_id)
            ):
                # Ongoing cap pressure: still floating at max after this decision window.
                penalties[player_id] += 0.005
        return penalties

    def step(
        self,
        actions: dict[int, int],
        *,
        pre_action_masks: dict[int, np.ndarray] | None = None,
    ) -> tuple[dict[int, float], bool, StepInfo]:
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

        action_success: dict[int, bool] = {}
        order = [0, 1]
        self.rng.shuffle(order)

        for player_id in order:
            action_id = actions.get(player_id, self.action_space.no_op_action)
            success = self.action_space.apply_action(self.battle, player_id, action_id)
            action_success[player_id] = success

        ticks = 0
        no_op0 = (
            actions.get(0, self.action_space.no_op_action)
            == self.action_space.no_op_action
        )
        no_op1 = (
            actions.get(1, self.action_space.no_op_action)
            == self.action_space.no_op_action
        )
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

        scenario_done = bool(
            self.defense_scenario is not None
            and self.battle.tick - self.defense_scenario.start_tick
            >= self.defense_scenario_horizon_ticks
        )
        done = self.battle.game_over or self.battle.tick >= self.max_ticks or scenario_done
        rewards = self._compute_dense_rewards(done=done)

        # Tiny invalid-action penalty (no-op is always valid).
        for player_id in (0, 1):
            attempted = actions.get(player_id, self.action_space.no_op_action)
            if attempted != self.action_space.no_op_action and not action_success.get(
                player_id, True
            ):
                rewards[player_id] -= 0.01

        leak_penalty = self._compute_elixir_leak_penalty(
            actions=actions,
            pre_elixir=pre_elixir,
            pre_can_spend=pre_can_spend,
            done=done,
        )
        # Keep reward strictly zero-sum.
        leak_edge = self.elixir_leak_penalty_scale * (
            leak_penalty[1] - leak_penalty[0]
        )
        rewards[0] += leak_edge
        rewards[1] -= leak_edge

        if done and self.defense_scenario is not None:
            scenario_outcome = self.defense_scenario_reward_scale * defense_scenario_outcome(
                self.battle,
                self.defense_scenario,
            )
            learner = self.defense_scenario.learner_player
            rewards[learner] += scenario_outcome
            rewards[1 - learner] -= scenario_outcome
        elif done and self.battle.winner is not None:
            rewards[self.battle.winner] += 1.0
            rewards[1 - self.battle.winner] -= 1.0

        return (
            rewards,
            done,
            StepInfo(action_success=action_success, ticks_advanced=ticks),
        )
