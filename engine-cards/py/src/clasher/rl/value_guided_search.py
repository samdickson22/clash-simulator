from __future__ import annotations

import copy
import random
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import torch
from torch import Tensor

from .common import BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES
from .eval import LoadedPolicy
from .model import PolicyOutput
from .public_outcome import LoadedPublicOutcomeHead
from .selfplay_env import SelfPlayBattleEnv
from .train_recurrent import _stack_step_inputs

PolicyState = tuple[Tensor, Tensor]
OpponentSelector = Callable[[SelfPlayBattleEnv, int, np.ndarray], int]


@dataclass(frozen=True)
class CandidateValue:
    action: int
    probability: float
    crown_difference: int | None = None
    tower_damage_difference: float | None = None
    terminal_tick: int | None = None


@dataclass(frozen=True)
class CandidateEvaluation:
    probability_p0: float
    crown_difference_p0: int | None
    tower_damage_difference_p0: float | None
    terminal_tick: int | None


@dataclass(frozen=True)
class ValueGuidedDecision:
    player_id: int
    action: int
    base_action: int
    base_probability: float
    selected_probability: float
    candidates: tuple[CandidateValue, ...]
    policy_actions: dict[int, int]
    next_states: dict[int, PolicyState]
    action_masks: dict[int, np.ndarray]

    @property
    def overridden(self) -> bool:
        return self.action != self.base_action


def clone_search_env(env: SelfPlayBattleEnv) -> SelfPlayBattleEnv:
    """Clone mutable runtime state while sharing immutable environment catalogs."""
    if env.battle is None:
        raise ValueError("cannot clone an environment before reset")
    simulation = copy.copy(env)
    simulation.battle = env.battle.clone()
    simulation.rng = random.Random()
    simulation.rng.setstate(env.rng.getstate())
    simulation.np_rng = np.random.default_rng()
    simulation.np_rng.bit_generator.state = copy.deepcopy(env.np_rng.bit_generator.state)
    simulation.defense_scenario = copy.deepcopy(env.defense_scenario)
    simulation._mask_shadow_checks = 0
    simulation._mask_shadow_mismatches = 0
    return simulation


class RecurrentValueGuidedSearch:
    """Rerank diverse root actions with recurrent policy rollouts and outcome value."""

    def __init__(
        self,
        *,
        policy: LoadedPolicy,
        outcome: LoadedPublicOutcomeHead | None,
        device: torch.device,
        rollout_decisions: int = 8,
        terminal_rollout: bool = False,
        max_candidates: int = 6,
        locations_per_slot: int = 1,
        spatially_diverse_locations: bool = False,
        minimum_value_gain: float = 0.02,
        maximum_override_base_probability: float = 1.0,
    ) -> None:
        if rollout_decisions < 0:
            raise ValueError("rollout_decisions must be non-negative")
        if max_candidates <= 0:
            raise ValueError("max_candidates must be positive")
        if locations_per_slot <= 0:
            raise ValueError("locations_per_slot must be positive")
        if minimum_value_gain < 0.0:
            raise ValueError("minimum_value_gain must be non-negative")
        if not 0.0 <= maximum_override_base_probability <= 1.0:
            raise ValueError(
                "maximum_override_base_probability must be between zero and one"
            )
        self.policy = policy
        self.outcome = outcome
        self.device = device
        self.rollout_decisions = rollout_decisions
        self.terminal_rollout = terminal_rollout
        self.max_candidates = max_candidates
        self.locations_per_slot = locations_per_slot
        self.spatially_diverse_locations = spatially_diverse_locations
        self.minimum_value_gain = minimum_value_gain
        self.maximum_override_base_probability = (
            maximum_override_base_probability
        )

    def _choose_candidate(
        self,
        values: list[CandidateValue],
    ) -> CandidateValue:
        """Apply improvement and risk gates to an evaluated root action set."""
        if not values:
            raise ValueError("value-guided search produced no candidates")
        base = values[0]
        if base.probability > self.maximum_override_base_probability:
            return base
        best = max(values, key=lambda row: (row.probability, -row.action))
        if best.probability < base.probability + self.minimum_value_gain:
            return base
        return best

    def _ordered_slot_tiles(
        self,
        legal_tiles: np.ndarray,
        slot_logits: np.ndarray,
    ) -> list[int]:
        ranked = legal_tiles[
            np.lexsort((legal_tiles, -slot_logits[legal_tiles]))
        ].tolist()
        if not self.spatially_diverse_locations or len(ranked) <= 1:
            return [int(tile) for tile in ranked[: self.locations_per_slot]]

        selected = [int(ranked[0])]
        remaining = {int(tile) for tile in ranked[1:]}
        while remaining and len(selected) < self.locations_per_slot:
            def key(tile: int) -> tuple[int, float, int]:
                x = tile % BOARD_WIDTH
                y = tile // BOARD_WIDTH
                minimum_distance = min(
                    (x - other % BOARD_WIDTH) ** 2
                    + (y - other // BOARD_WIDTH) ** 2
                    for other in selected
                )
                return minimum_distance, float(slot_logits[tile]), -tile

            chosen = max(remaining, key=key)
            selected.append(chosen)
            remaining.remove(chosen)
        return selected

    @torch.no_grad()
    def _observe_policy(
        self,
        env: SelfPlayBattleEnv,
        player_id: int,
        *,
        state: PolicyState,
        previous_action: int,
        previous_reward: float,
        episode_start: bool,
    ) -> tuple[int, PolicyState, PolicyOutput, np.ndarray]:
        if env.battle is None:
            raise ValueError("value-guided search requires a reset environment")
        observation = self.policy.builder.build(env.battle, player_id)
        action_mask = env.get_action_mask(player_id)
        inputs = _stack_step_inputs(
            [observation],
            action_mask[None, :],
            np.asarray([previous_action], dtype=np.int64),
            np.asarray([previous_reward], dtype=np.float32),
            np.asarray([episode_start], dtype=np.bool_),
            self.device,
            public_observation_confidence=(
                self.policy.model.config.public_observation_confidence
            ),
        )
        action, _, _, next_state, output = self.policy.model.act(
            inputs,
            state,
            deterministic=True,
        )
        return int(action[0, 0]), next_state, output, action_mask

    def candidate_actions(
        self,
        *,
        base_action: int,
        output: PolicyOutput,
        action_mask: np.ndarray,
    ) -> tuple[int, ...]:
        """Cover every legal action type, then add alternate spatial candidates."""
        logits = output.joint_logits[0, 0].detach().cpu().numpy()
        primary: list[tuple[float, int]] = []
        alternate: list[tuple[int, float, int]] = []
        for slot in range(NUM_HAND_SLOTS):
            start = slot * NUM_TILES
            legal_tiles = np.flatnonzero(action_mask[start : start + NUM_TILES])
            if not len(legal_tiles):
                continue
            slot_logits = logits[start : start + NUM_TILES]
            ordered = self._ordered_slot_tiles(legal_tiles, slot_logits)
            for rank, tile_value in enumerate(ordered):
                action = start + int(tile_value)
                if rank == 0:
                    primary.append((float(logits[action]), action))
                else:
                    alternate.append((rank, float(logits[action]), action))
        for action in (
            self.policy.model.num_actions - 2,
            self.policy.model.num_actions - 1,
        ):
            if action_mask[action]:
                primary.append((float(logits[action]), action))
        primary.sort(key=lambda row: (-row[0], row[1]))
        alternate.sort(key=lambda row: (row[0], -row[1], row[2]))
        candidates = [base_action]
        candidates.extend(
            action
            for action in (
                [row[1] for row in primary]
                + [row[2] for row in alternate]
            )
            if action != base_action
        )
        return tuple(candidates[: self.max_candidates])

    def _terminal_probability_p0(self, env: SelfPlayBattleEnv) -> float | None:
        assert env.battle is not None
        if not env.battle.game_over and env.battle.tick < env.max_ticks:
            return None
        if env.battle.winner is None:
            return 0.5
        return 1.0 if env.battle.winner == 0 else 0.0

    def _candidate_evaluation(
        self,
        env: SelfPlayBattleEnv,
        probability_p0: float,
    ) -> CandidateEvaluation:
        assert env.battle is not None
        terminal = self._terminal_probability_p0(env) is not None
        if not terminal:
            return CandidateEvaluation(probability_p0, None, None, None)
        battle = env.battle
        crown_difference = battle.get_crown_count(0) - battle.get_crown_count(1)
        tower_damage_difference = (
            battle._tower_damage_dealt_by_player(0)
            - battle._tower_damage_dealt_by_player(1)
        )
        return CandidateEvaluation(
            probability_p0=probability_p0,
            crown_difference_p0=crown_difference,
            tower_damage_difference_p0=float(tower_damage_difference),
            terminal_tick=int(battle.tick),
        )

    @torch.no_grad()
    def _leaf_probability_p0(
        self,
        env: SelfPlayBattleEnv,
        *,
        states: dict[int, PolicyState],
        previous_actions: dict[int, int],
        previous_rewards: dict[int, float],
    ) -> float:
        terminal = self._terminal_probability_p0(env)
        if terminal is not None:
            return terminal
        features: dict[int, Tensor] = {}
        for player_id in (0, 1):
            _, _, output, _ = self._observe_policy(
                env,
                player_id,
                state=states[player_id],
                previous_action=previous_actions[player_id],
                previous_reward=previous_rewards[player_id],
                episode_start=False,
            )
            if output.repair_features is None:
                raise ValueError("policy does not expose public outcome features")
            features[player_id] = output.repair_features[0, 0]
        if self.outcome is None:
            raise ValueError("non-terminal value search requires an outcome head")
        probability = self.outcome.probability_p0(features[0], features[1])
        return float(probability.item())

    @torch.no_grad()
    def _evaluate_candidate(
        self,
        env: SelfPlayBattleEnv,
        *,
        root_actions: dict[int, int],
        root_next_states: dict[int, PolicyState],
        root_masks: dict[int, np.ndarray],
        controlled_player: int,
        opponent_selector: OpponentSelector | None,
    ) -> CandidateEvaluation:
        simulation = clone_search_env(env)
        rewards, done, _ = simulation.step(
            root_actions,
            pre_action_masks=root_masks,
        )
        states: dict[int, PolicyState] = {
            player: (
                root_next_states[player][0].clone(),
                root_next_states[player][1].clone(),
            )
            for player in (0, 1)
        }
        previous_actions = dict(root_actions)
        previous_rewards = {player: float(rewards[player]) for player in (0, 1)}
        if done:
            terminal = self._terminal_probability_p0(simulation)
            assert terminal is not None
            return self._candidate_evaluation(simulation, terminal)
        rollout = 0
        while self.terminal_rollout or rollout < self.rollout_decisions:
            actions: dict[int, int] = {}
            next_states: dict[int, PolicyState] = {}
            masks: dict[int, np.ndarray] = {}
            for player in (0, 1):
                action, next_state, _, mask = self._observe_policy(
                    simulation,
                    player,
                    state=states[player],
                    previous_action=previous_actions[player],
                    previous_reward=previous_rewards[player],
                    episode_start=False,
                )
                actions[player] = action
                next_states[player] = next_state
                masks[player] = mask
            opponent = 1 - controlled_player
            if opponent_selector is not None:
                actions[opponent] = opponent_selector(
                    simulation,
                    opponent,
                    masks[opponent],
                )
            rewards, done, _ = simulation.step(actions, pre_action_masks=masks)
            states = next_states
            previous_actions = actions
            previous_rewards = {player: float(rewards[player]) for player in (0, 1)}
            if done:
                terminal = self._terminal_probability_p0(simulation)
                assert terminal is not None
                return self._candidate_evaluation(simulation, terminal)
            rollout += 1
        probability_p0 = self._leaf_probability_p0(
            simulation,
            states=states,
            previous_actions=previous_actions,
            previous_rewards=previous_rewards,
        )
        return self._candidate_evaluation(simulation, probability_p0)

    @torch.no_grad()
    def observe_policy_pair(
        self,
        env: SelfPlayBattleEnv,
        *,
        states: dict[int, PolicyState],
        previous_actions: dict[int, int],
        previous_rewards: dict[int, float],
        episode_start: bool,
    ) -> tuple[
        dict[int, int],
        dict[int, PolicyState],
        dict[int, PolicyOutput],
        dict[int, np.ndarray],
    ]:
        policy_actions: dict[int, int] = {}
        root_next_states: dict[int, PolicyState] = {}
        outputs: dict[int, PolicyOutput] = {}
        masks: dict[int, np.ndarray] = {}
        for player in (0, 1):
            action, next_state, output, mask = self._observe_policy(
                env,
                player,
                state=states[player],
                previous_action=previous_actions[player],
                previous_reward=previous_rewards[player],
                episode_start=episode_start,
            )
            policy_actions[player] = action
            root_next_states[player] = next_state
            outputs[player] = output
            masks[player] = mask
        return policy_actions, root_next_states, outputs, masks

    @torch.no_grad()
    def select_action(
        self,
        env: SelfPlayBattleEnv,
        player_id: int,
        *,
        states: dict[int, PolicyState],
        previous_actions: dict[int, int],
        previous_rewards: dict[int, float],
        episode_start: bool,
        opponent_selector: OpponentSelector | None = None,
    ) -> ValueGuidedDecision:
        if player_id not in (0, 1):
            raise ValueError("value-guided player_id must be 0 or 1")
        policy_actions, root_next_states, outputs, masks = self.observe_policy_pair(
            env,
            states=states,
            previous_actions=previous_actions,
            previous_rewards=previous_rewards,
            episode_start=episode_start,
        )
        opponent = 1 - player_id
        if opponent_selector is not None:
            policy_actions[opponent] = opponent_selector(
                env,
                opponent,
                masks[opponent],
            )
        base_action = policy_actions[player_id]
        candidate_actions = self.candidate_actions(
            base_action=base_action,
            output=outputs[player_id],
            action_mask=masks[player_id],
        )
        values: list[CandidateValue] = []
        for candidate in candidate_actions:
            root_actions = dict(policy_actions)
            root_actions[player_id] = candidate
            evaluation = self._evaluate_candidate(
                env,
                root_actions=root_actions,
                root_next_states=root_next_states,
                root_masks=masks,
                controlled_player=player_id,
                opponent_selector=opponent_selector,
            )
            probability = (
                evaluation.probability_p0
                if player_id == 0
                else 1.0 - evaluation.probability_p0
            )
            sign = 1 if player_id == 0 else -1
            values.append(
                CandidateValue(
                    candidate,
                    probability,
                    crown_difference=(
                        None
                        if evaluation.crown_difference_p0 is None
                        else sign * evaluation.crown_difference_p0
                    ),
                    tower_damage_difference=(
                        None
                        if evaluation.tower_damage_difference_p0 is None
                        else sign * evaluation.tower_damage_difference_p0
                    ),
                    terminal_tick=evaluation.terminal_tick,
                )
            )
        base_probability = values[0].probability
        best = self._choose_candidate(values)
        return ValueGuidedDecision(
            player_id=player_id,
            action=best.action,
            base_action=base_action,
            base_probability=base_probability,
            selected_probability=best.probability,
            candidates=tuple(values),
            policy_actions=policy_actions,
            next_states=root_next_states,
            action_masks=masks,
        )
