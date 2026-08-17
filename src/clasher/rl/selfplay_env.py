from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import numpy as np

from clasher.battle import STANDARD_MATCH_TICKS, BattleState
from clasher.torch_sim import SimulatorBackend, TorchBattleExecutor

from .action_space import DiscreteTileActionSpace
from .deck_pool import apply_deck_to_player, load_deck_pool, sample_decks
from .obs_cv import CvObservation, CvObservationBuilder
from .reward_model import objective_potential_p0
from .structured_obs import StructuredObservation, StructuredObservationBuilder

# Reference/benchmark switch. The env has just performed the same exact idle
# eligibility check before dispatching the bounded fast-forward operation.
_USE_TRUSTED_IDLE_ELIGIBILITY = True

@dataclass
class StepInfo:
    action_success: Dict[int, bool]
    ticks_advanced: int


@dataclass
class _PreparedStep:
    actions: Dict[int, int]
    pre_elixir: Dict[int, float]
    pre_can_spend: Dict[int, bool]
    action_success: Dict[int, bool]
    remaining_ticks: int
    ticks_advanced: int = 0


_BACKEND_METRIC_NAMES = (
    "tensor_ticks",
    "python_ticks",
    "shadow_checks",
    "shadow_mismatches",
    "unsupported_fallbacks",
)


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
        simulation_backend: str = "python",
        idle_fast_forward: bool = True,
    ) -> None:
        self.decision_interval_ticks = decision_interval_ticks
        self.max_ticks = max_ticks
        self.mirror_match = mirror_match
        if engine_fast_path not in {"off", "shadow", "on"}:
            raise ValueError("engine_fast_path must be one of: off, shadow, on")
        self.engine_fast_path = engine_fast_path
        try:
            self.simulation_backend = SimulatorBackend(simulation_backend)
        except ValueError as exc:
            choices = ", ".join(value.value for value in SimulatorBackend)
            raise ValueError(f"simulation_backend must be one of: {choices}") from exc
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
        self._simulator = TorchBattleExecutor(self.simulation_backend)

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
        self._simulator = TorchBattleExecutor(self.simulation_backend)
        self._sample_and_apply_decks()
        self._reset_reward_trackers()

    def get_observation(self, player_id: int) -> CvObservation:
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

    def get_structured_observation(self, player_id: int) -> StructuredObservation:
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

    def simulator_backend_metrics(self) -> Dict[str, float]:
        return self._simulator.metrics_dict()

    def pop_simulator_backend_metrics(self) -> Dict[str, float]:
        return self._simulator.pop_metrics()

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

    def _prepare_step(
        self,
        actions: Mapping[int, int],
        *,
        pre_action_masks: Optional[Mapping[int, np.ndarray]],
    ) -> _PreparedStep:
        """Apply one environment's actions without advancing its clock."""

        assert self.battle is not None
        action_values = dict(actions)
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
            action_id = action_values.get(
                player_id, self.action_space.no_op_action
            )
            action_success[player_id] = self.action_space.apply_action(
                self.battle, player_id, action_id
            )

        remaining_ticks = min(
            self.decision_interval_ticks,
            max(0, self.max_ticks - self.battle.tick),
        )
        return _PreparedStep(
            actions=action_values,
            pre_elixir=pre_elixir,
            pre_can_spend=pre_can_spend,
            action_success=action_success,
            remaining_ticks=remaining_ticks,
        )

    def _can_fast_forward_prepared_idle(self, prepared: _PreparedStep) -> bool:
        assert self.battle is not None
        no_op = self.action_space.no_op_action
        return bool(
            self.simulation_backend is SimulatorBackend.PYTHON
            and self.idle_fast_forward
            and prepared.actions.get(0, no_op) == no_op
            and prepared.actions.get(1, no_op) == no_op
            and hasattr(self.battle, "can_fast_forward_idle")
            and self.battle.can_fast_forward_idle()
        )

    def _finish_step(
        self,
        prepared: _PreparedStep,
    ) -> tuple[Dict[int, float], bool, StepInfo]:
        """Compute the legacy post-tick reward and terminal result exactly."""

        assert self.battle is not None
        done = self.battle.game_over or self.battle.tick >= self.max_ticks
        rewards = self._compute_dense_rewards()

        # Tiny invalid-action penalty (no-op is always valid).
        for player_id in (0, 1):
            attempted = prepared.actions.get(
                player_id, self.action_space.no_op_action
            )
            if (
                attempted != self.action_space.no_op_action
                and not prepared.action_success.get(player_id, True)
            ):
                rewards[player_id] -= 0.01

        leak_penalty = self._compute_elixir_leak_penalty(
            actions=prepared.actions,
            pre_elixir=prepared.pre_elixir,
            pre_can_spend=prepared.pre_can_spend,
            done=done,
        )
        # Keep reward strictly zero-sum.
        leak_edge = leak_penalty[1] - leak_penalty[0]
        rewards[0] += leak_edge
        rewards[1] -= leak_edge

        if done and self.battle.winner is not None:
            rewards[self.battle.winner] += 1.0
            rewards[1 - self.battle.winner] -= 1.0

        return rewards, done, StepInfo(
            action_success=prepared.action_success,
            ticks_advanced=prepared.ticks_advanced,
        )

    def step(
        self,
        actions: Dict[int, int],
        *,
        pre_action_masks: Optional[Dict[int, np.ndarray]] = None,
    ) -> tuple[Dict[int, float], bool, StepInfo]:
        return step_selfplay_envs(
            [self],
            [actions],
            pre_action_masks=(
                None if pre_action_masks is None else [pre_action_masks]
            ),
        )[0]


def step_selfplay_envs(
    envs: Sequence[SelfPlayBattleEnv],
    actions: Sequence[Mapping[int, int]],
    *,
    pre_action_masks: Optional[Sequence[Mapping[int, np.ndarray]]] = None,
) -> list[tuple[Dict[int, float], bool, StepInfo]]:
    """One-shot batched adapter that preserves legacy per-environment metrics."""

    stepper = BatchedSelfPlayStepper()
    results = stepper.step(
        envs,
        actions,
        pre_action_masks=pre_action_masks,
    )
    metrics = stepper.pop_metrics()
    if envs:
        leader_metrics = envs[0]._simulator.metrics
        for name in _BACKEND_METRIC_NAMES:
            setattr(
                leader_metrics,
                name,
                getattr(leader_metrics, name) + int(metrics[name]),
            )
    return results


class BatchedSelfPlayStepper:
    """Stateful exact tick batching boundary for one CPU actor rollout.

    Each environment still applies its two actions using its own RNG and
    computes rewards independently. Only the clock advance is batched. Backend
    executors and counters live here so environment resets cannot discard
    telemetry or retained tensor batches.
    """

    def __init__(self) -> None:
        self._executors: dict[
            tuple[SimulatorBackend, str, int], TorchBattleExecutor
        ] = {}
        self._metrics = {name: 0 for name in _BACKEND_METRIC_NAMES}

    def _drain_executor(
        self,
        key: tuple[SimulatorBackend, str, int],
    ) -> None:
        executor = self._executors.pop(key, None)
        if executor is None:
            return
        for name, value in executor.pop_metrics().items():
            self._metrics[name] += int(value)

    def step(
        self,
        envs: Sequence[SelfPlayBattleEnv],
        actions: Sequence[Mapping[int, int]],
        *,
        pre_action_masks: Optional[
            Sequence[Mapping[int, np.ndarray]]
        ] = None,
    ) -> list[tuple[Dict[int, float], bool, StepInfo]]:
        if len(envs) != len(actions):
            raise ValueError("actions must have one mapping per environment")
        if pre_action_masks is not None and len(envs) != len(pre_action_masks):
            raise ValueError(
                "pre_action_masks must have one mapping per environment"
            )
        if len({id(env) for env in envs}) != len(envs):
            raise ValueError("an environment may appear only once per batch")
        if not envs:
            return []

        prepared_steps: list[_PreparedStep] = []
        advance_groups: dict[
            tuple[SimulatorBackend, str, int], list[int]
        ] = defaultdict(list)
        for index, (env, env_actions) in enumerate(zip(envs, actions)):
            masks = None if pre_action_masks is None else pre_action_masks[index]
            prepared = env._prepare_step(
                env_actions,
                pre_action_masks=masks,
            )
            prepared_steps.append(prepared)
            if env._can_fast_forward_prepared_idle(prepared):
                assert env.battle is not None
                if prepared.remaining_ticks > 0:
                    prepared.ticks_advanced = env.battle.fast_forward_idle_ticks(
                        prepared.remaining_ticks,
                        eligibility_checked=_USE_TRUSTED_IDLE_ELIGIBILITY,
                    )
                continue
            device = str(env._simulator.device)
            advance_groups[
                (env.simulation_backend, device, prepared.remaining_ticks)
            ].append(index)

        for key, indices in advance_groups.items():
            # Successful non-noop actions can mutate tensor-backed scalar fields
            # without necessarily changing clocks. Re-encode such a group so a
            # retained tensor state can never overwrite the fresh action.
            action_mutated = any(
                any(
                    success
                    and prepared_steps[index].actions.get(
                        player_id, envs[index].action_space.no_op_action
                    )
                    != envs[index].action_space.no_op_action
                    for player_id, success in prepared_steps[
                        index
                    ].action_success.items()
                )
                for index in indices
            )
            if action_mutated:
                self._drain_executor(key)
            executor = self._executors.get(key)
            if executor is None:
                backend, device, _ = key
                executor = TorchBattleExecutor(backend, device=device)
                self._executors[key] = executor
            battles = []
            for index in indices:
                battle = envs[index].battle
                assert battle is not None
                battles.append(battle)
            advanced = executor.step_battles(
                battles,
                prepared_steps[indices[0]].remaining_ticks,
            )
            for index, ticks_advanced in zip(indices, advanced):
                prepared_steps[index].ticks_advanced = ticks_advanced

        return [
            env._finish_step(prepared)
            for env, prepared in zip(envs, prepared_steps)
        ]

    def pop_metrics(self) -> dict[str, float]:
        for key in list(self._executors):
            self._drain_executor(key)
        result = {name: float(value) for name, value in self._metrics.items()}
        self._metrics = {name: 0 for name in _BACKEND_METRIC_NAMES}
        return result
