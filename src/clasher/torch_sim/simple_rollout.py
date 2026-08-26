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
        adapter: SimpleGymAdapter | None = None,
    ) -> None:
        if adapter is not None and adapter.engine is not runtime:
            raise ValueError("adapter must wrap the supplied runtime")
        self.runtime = runtime
        self.adapter = adapter or SimpleGymAdapter(runtime, no_op_action=no_op_action)
        self.device = self.adapter.device
        self.batch_size = self.adapter.batch_size
        self._no_fallback_rows = torch.zeros(
            self.batch_size, dtype=torch.bool, device=self.device
        )
        self._all_rows_admitted = torch.ones_like(self._no_fallback_rows)

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

    def step(
        self,
        actions: torch.Tensor,
        *,
        recurrent_inputs: Mapping[str, torch.Tensor] | None = None,
        public_action_masks: torch.Tensor | None = None,
        public_action_mask_contract_version: int | None = None,
    ) -> SimpleGymRolloutStep:
        """Advance one native tick and return a storage-ready tensor boundary.

        External masks are optional, but whenever present must carry public
        action-mask contract v2. Simulator legality remains separately profiled
        and is never relabeled as a public v2 mask.
        """

        result = self.adapter.step(
            actions,
            recurrent_inputs=recurrent_inputs,
            public_action_masks=public_action_masks,
            public_action_mask_contract_version=public_action_mask_contract_version,
        )
        boundary = self._boundary(
            result.observation,
            result.history_before,
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
            rewards=result.rewards,
            done=result.dones,
            winner=result.winner,
            action_success=result.action_success,
            native_ticks=result.admission.native_ticks,
            committed=result.admission.committed,
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
        return self._boundary(observation, history, None, None)


__all__ = [
    "SimpleGymRolloutBridge",
    "SimpleGymRolloutObservation",
    "SimpleGymRolloutStep",
]
