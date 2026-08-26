"""Device-resident batched rollout boundary for the practical tensor Gym.

This module deliberately stops short of choosing a policy or rollout storage
layout.  It joins :class:`SimpleGymRuntime` and :class:`SimpleGymAdapter` at a
stable training boundary, keeps recurrent history aligned with selective
episode resets, and reports the absence of fallback as fixed-shape tensors.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import torch

from .actions import NO_OP_ACTION
from .resident_outputs import (
    TensorPrivilegedCriticObservation,
    TensorPublicStructuredObservation,
)
from .simple_adapter import (
    SIMPLIFIED_GYM_ACTION_MASK_PROFILE,
    SimpleGymAdapter,
    SimpleGymContractError,
    SimpleGymHistory,
    SimpleGymObservation,
)
from .simple_runtime import SimpleGymRuntime


@dataclass(frozen=True)
class SimpleGymRolloutObservation:
    """Policy inputs at one batched decision boundary."""

    actor: TensorPublicStructuredObservation
    critic: TensorPrivilegedCriticObservation | None
    legal_mask: torch.Tensor
    public_action_masks: torch.Tensor | None
    public_action_mask_contract_version: int | None
    simulator_action_mask_profile: str
    previous_actions: torch.Tensor
    previous_rewards: torch.Tensor
    episode_starts: torch.Tensor


@dataclass(frozen=True)
class SimpleGymRolloutStep(SimpleGymRolloutObservation):
    """One native transition in fixed batch-leading tensors."""

    next_actor: TensorPublicStructuredObservation
    next_critic: TensorPrivilegedCriticObservation | None
    next_legal_mask: torch.Tensor
    rewards: torch.Tensor
    done: torch.Tensor
    winner: torch.Tensor
    action_success: torch.Tensor
    native_ticks: torch.Tensor
    committed: torch.Tensor
    fallback_rows: torch.Tensor
    all_rows_admitted: torch.Tensor
    recurrent_inputs: Mapping[str, torch.Tensor] | None = None


class SimpleGymRolloutBridge:
    """Training-facing owner of a runtime and its recurrent adapter state."""

    def __init__(
        self,
        runtime: SimpleGymRuntime,
        *,
        no_op_action: int = NO_OP_ACTION,
        decision_interval: int = 1,
        adapter: SimpleGymAdapter | None = None,
    ) -> None:
        if (
            not isinstance(decision_interval, int)
            or isinstance(decision_interval, bool)
            or decision_interval < 1
        ):
            raise ValueError("decision_interval must be a positive integer")
        if adapter is not None and adapter.engine is not runtime:
            raise ValueError("adapter must wrap the supplied runtime")
        self.runtime = runtime
        self.adapter = adapter or SimpleGymAdapter(runtime, no_op_action=no_op_action)
        self.device = self.adapter.device
        self.batch_size = self.adapter.batch_size
        self.decision_interval = int(decision_interval)
        self._no_op_actions = torch.full(
            (self.batch_size, 2),
            self.adapter.no_op_action,
            dtype=torch.int64,
            device=self.device,
        )
        self._no_fallback_rows = torch.zeros(
            self.batch_size, dtype=torch.bool, device=self.device
        )
        self._all_rows_admitted = torch.ones_like(self._no_fallback_rows)
        self.needs_reset = torch.zeros_like(self._no_fallback_rows)

    @staticmethod
    def _boundary(
        observation: SimpleGymObservation,
        history: SimpleGymHistory,
        public_action_masks: torch.Tensor | None,
        public_action_mask_contract_version: int | None,
    ) -> SimpleGymRolloutObservation:
        return SimpleGymRolloutObservation(
            actor=observation.actor,
            critic=observation.critic,
            legal_mask=observation.legal_mask,
            public_action_masks=public_action_masks,
            public_action_mask_contract_version=public_action_mask_contract_version,
            simulator_action_mask_profile=SIMPLIFIED_GYM_ACTION_MASK_PROFILE,
            previous_actions=history.previous_actions,
            previous_rewards=history.previous_rewards,
            episode_starts=history.episode_starts,
        )

    def observe(self) -> SimpleGymRolloutObservation:
        """Return current policy inputs without mutating runtime or history."""

        observation = self.adapter.observe()
        return self._boundary(observation, self.adapter.history, None, None)

    @staticmethod
    def _select_rows(
        previous: torch.Tensor, current: torch.Tensor, selected: torch.Tensor
    ) -> torch.Tensor:
        row_mask = selected.view(selected.shape[0], *((1,) * (current.ndim - 1)))
        return torch.where(row_mask, current, previous)

    @classmethod
    def _merge_observation_rows(
        cls,
        previous_actor: TensorPublicStructuredObservation,
        previous_critic: TensorPrivilegedCriticObservation | None,
        previous_legal_mask: torch.Tensor,
        current: SimpleGymObservation,
        selected: torch.Tensor,
    ) -> tuple[
        TensorPublicStructuredObservation,
        TensorPrivilegedCriticObservation | None,
        torch.Tensor,
    ]:
        actor = TensorPublicStructuredObservation(
            entity_ids=cls._select_rows(
                previous_actor.entity_ids, current.actor.entity_ids, selected
            ),
            entity_features=cls._select_rows(
                previous_actor.entity_features,
                current.actor.entity_features,
                selected,
            ),
            entity_mask=cls._select_rows(
                previous_actor.entity_mask, current.actor.entity_mask, selected
            ),
            hand_ids=cls._select_rows(
                previous_actor.hand_ids, current.actor.hand_ids, selected
            ),
            global_features=cls._select_rows(
                previous_actor.global_features,
                current.actor.global_features,
                selected,
            ),
        )
        if previous_critic is None or current.critic is None:
            critic = None
        else:
            critic = TensorPrivilegedCriticObservation(
                entity_ids=cls._select_rows(
                    previous_critic.entity_ids, current.critic.entity_ids, selected
                ),
                entity_features=cls._select_rows(
                    previous_critic.entity_features,
                    current.critic.entity_features,
                    selected,
                ),
                entity_mask=cls._select_rows(
                    previous_critic.entity_mask,
                    current.critic.entity_mask,
                    selected,
                ),
                card_ids=cls._select_rows(
                    previous_critic.card_ids, current.critic.card_ids, selected
                ),
                global_features=cls._select_rows(
                    previous_critic.global_features,
                    current.critic.global_features,
                    selected,
                ),
            )
        legal_mask = cls._select_rows(previous_legal_mask, current.legal_mask, selected)
        return actor, critic, legal_mask

    def step(
        self,
        actions: torch.Tensor,
        *,
        recurrent_inputs: Mapping[str, torch.Tensor] | None = None,
        public_action_masks: torch.Tensor | None = None,
        public_action_mask_contract_version: int | None = None,
    ) -> SimpleGymRolloutStep:
        """Advance one policy decision and return its pre-action boundary.

        External masks are optional, but whenever present must carry public
        action-mask contract v2. Simulator legality remains separately profiled
        and is never relabeled as a public v2 mask. The requested action is
        applied exactly once; remaining native ticks use NO_OP. Terminal rows
        freeze their accounting and bootstrap observation while other rows
        finish the configured interval. Call :meth:`reset_done` for every
        terminal row before requesting another decision; internal terminal-row
        scratch planes are not a supported observation boundary before reset.
        """

        if bool(self.needs_reset.any().item()):
            raise SimpleGymContractError(
                "terminal rows must be passed to reset_done before the next step"
            )
        pre_observation = self.adapter.observe()
        history_before = self.adapter.history
        first = self.adapter.step(
            actions,
            recurrent_inputs=recurrent_inputs,
            public_action_masks=public_action_masks,
            public_action_mask_contract_version=public_action_mask_contract_version,
            update_history=False,
        )
        rewards = first.rewards.clone()
        done = first.dones.clone()
        winner = first.winner.clone()
        native_ticks = first.admission.native_ticks.clone()
        committed = first.admission.committed.clone()
        next_actor = first.observation.actor
        next_critic = first.observation.critic
        next_legal_mask = first.observation.legal_mask
        live = ~done
        for _ in range(1, self.decision_interval):
            native = self.runtime.step_tick(self._no_op_actions)
            active = live
            next_actor, next_critic, next_legal_mask = self._merge_observation_rows(
                next_actor,
                next_critic,
                next_legal_mask,
                native.observation,
                active,
            )
            rewards.add_(torch.where(active[:, None], native.reward, 0.0))
            native_ticks.add_(torch.where(active, native.native_ticks, 0))
            committed &= (~active) | native.committed
            winner = torch.where(active & native.done, native.winner, winner)
            done |= active & native.done
            live &= ~native.done

        terminal = done[:, None]
        self.adapter.history = SimpleGymHistory(
            previous_actions=torch.where(terminal, self._no_op_actions, actions),
            previous_rewards=torch.where(terminal, torch.zeros_like(rewards), rewards),
            episode_starts=terminal.expand(-1, 2),
        )
        self.needs_reset.copy_(done)
        boundary = self._boundary(
            pre_observation,
            history_before,
            public_action_masks,
            public_action_mask_contract_version,
        )
        return SimpleGymRolloutStep(
            actor=boundary.actor,
            critic=boundary.critic,
            legal_mask=boundary.legal_mask,
            public_action_masks=boundary.public_action_masks,
            public_action_mask_contract_version=(
                boundary.public_action_mask_contract_version
            ),
            simulator_action_mask_profile=boundary.simulator_action_mask_profile,
            previous_actions=boundary.previous_actions,
            previous_rewards=boundary.previous_rewards,
            episode_starts=boundary.episode_starts,
            next_actor=next_actor,
            next_critic=next_critic,
            next_legal_mask=next_legal_mask,
            rewards=rewards,
            done=done,
            winner=winner,
            action_success=first.action_success,
            native_ticks=native_ticks,
            committed=committed,
            fallback_rows=self._no_fallback_rows,
            all_rows_admitted=self._all_rows_admitted,
            recurrent_inputs=recurrent_inputs,
        )

    def reset_done(
        self,
        reset_mask: torch.Tensor,
        *,
        deck_ids: torch.Tensor | None = None,
    ) -> SimpleGymRolloutObservation:
        """Reset selected runtime episodes and their recurrent history."""

        observation = self.runtime.reset_rows(reset_mask, deck_ids=deck_ids)
        history = self.adapter.reset_history_rows(reset_mask)
        self.needs_reset &= ~reset_mask
        return self._boundary(observation, history, None, None)


__all__ = [
    "SimpleGymRolloutBridge",
    "SimpleGymRolloutObservation",
    "SimpleGymRolloutStep",
]
