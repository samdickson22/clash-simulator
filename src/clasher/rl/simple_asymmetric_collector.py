"""Learner-only tensor rollouts against one stationary opponent per row.

The runtime remains a two-seat fixed-shape Gym.  This collector selects one
alternating learner seat from every row, evaluates learner and opponent
policies independently, composes their actions into one joint runtime step,
and exports only learner-controlled transitions for PPO.  Opponent actions and
recurrent state stay device-resident and are returned only as collector state
and audit telemetry.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, fields
from typing import Any, Final

import torch

from clasher.torch_sim.policy_validation import PUBLIC_ACTION_MASK_CONTRACT_V2
from clasher.torch_sim.resident_outputs import (
    TensorPrivilegedCriticObservation,
    TensorPublicStructuredObservation,
)
from clasher.torch_sim.simple_reward_v2 import SIMPLE_REWARD_V2_CONTRACT_ID
from clasher.torch_sim.simple_rollout import (
    SimpleGymRolloutBridge,
    SimpleGymRolloutObservation,
)

from .simple_tensor_collector import (
    SIMPLE_TENSOR_ACTOR_SEMANTICS_ID,
    SIMPLE_TENSOR_BACKEND_ID,
    SIMPLE_TENSOR_COLLECTOR_SCHEMA_VERSION,
    SimplePublicActionMaskV2,
    SimplePublicMaskProvider,
    SimpleResetDeckProvider,
    SimpleTensorCollectorError,
    SimpleTensorCollectorMetadata,
    SimpleTensorDecisionBatch,
    SimpleTensorMaskRequest,
    SimpleTensorPolicy,
    SimpleTensorPolicyBoundary,
    SimpleTensorPolicyDecision,
    _clone_mapping,
    _clone_public,
    _stack_critic,
    _stack_mappings,
    _stack_public,
)

SIMPLE_ASYMMETRIC_COLLECTOR_SCHEMA_VERSION: Final = 1
SIMPLE_ALTERNATING_LEARNER_SEAT_PROFILE: Final = "alternating-row-parity-v1"


def _canonical_digest(value: Mapping[str, Any]) -> str:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise SimpleTensorCollectorError(
            "opponent metadata must be canonical JSON"
        ) from error
    return hashlib.sha256(encoded).hexdigest()


def alternating_learner_seats(
    batch_size: int,
    *,
    device: str | torch.device,
) -> torch.Tensor:
    """Return the one authoritative learner seat for every environment row."""

    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    return torch.arange(batch_size, dtype=torch.int64, device=device).remainder(2)


def _select_seat(value: torch.Tensor, seats: torch.Tensor) -> torch.Tensor:
    if value.ndim < 2 or value.shape[0] != seats.shape[0] or value.shape[1] != 2:
        raise SimpleTensorCollectorError(
            "seat-selected tensors must begin with [batch, 2]"
        )
    index = seats.view(seats.shape[0], 1, *((1,) * (value.ndim - 2))).expand(
        value.shape[0], 1, *value.shape[2:]
    )
    return value.gather(1, index)


def _select_public(
    value: TensorPublicStructuredObservation,
    seats: torch.Tensor,
) -> TensorPublicStructuredObservation:
    return TensorPublicStructuredObservation(
        **{
            descriptor.name: _select_seat(getattr(value, descriptor.name), seats)
            for descriptor in fields(TensorPublicStructuredObservation)
        }
    )


def _select_critic(
    value: TensorPrivilegedCriticObservation | None,
    seats: torch.Tensor,
) -> TensorPrivilegedCriticObservation | None:
    if value is None:
        return None
    return TensorPrivilegedCriticObservation(
        **{
            descriptor.name: _select_seat(getattr(value, descriptor.name), seats)
            for descriptor in fields(TensorPrivilegedCriticObservation)
        }
    )


@dataclass(frozen=True)
class SimpleTensorAsymmetricCollectorMetadata:
    schema_version: int
    learner_seat_profile: str
    learner_seat_digest: str
    opponent_contract_id: str
    opponent_contract_digest: str
    opponent_contract: Mapping[str, Any]


@dataclass(frozen=True)
class SimpleTensorAsymmetricDecisionBatch:
    """Learner PPO batch plus device-resident opponent chronology."""

    learner: SimpleTensorDecisionBatch
    learner_seats: torch.Tensor
    opponent_actions: torch.Tensor
    opponent_recurrent_inputs: Mapping[str, torch.Tensor] | None
    opponent_bootstrap: SimpleTensorPolicyBoundary
    metadata: SimpleTensorAsymmetricCollectorMetadata


class SimpleTensorAsymmetricCollector:
    """Collect one learner seat per row against a stationary tensor policy."""

    def __init__(
        self,
        bridge: SimpleGymRolloutBridge,
        *,
        public_mask_provider: SimplePublicMaskProvider,
        learner_policy: SimpleTensorPolicy,
        opponent_policy: SimpleTensorPolicy,
        learner_seats: torch.Tensor,
        opponent_contract_id: str,
        opponent_contract: Mapping[str, Any],
        reset_deck_provider: SimpleResetDeckProvider | None = None,
        strict_host_validation: bool = False,
    ) -> None:
        if bridge.reward_contract_id != SIMPLE_REWARD_V2_CONTRACT_ID:
            raise SimpleTensorCollectorError(
                "simple tensor training requires objective-v1-gamma-v1"
            )
        if bridge.strict_reset_check:
            raise SimpleTensorCollectorError(
                "production collection requires strict_reset_check=False"
            )
        if (
            learner_seats.shape != (bridge.batch_size,)
            or learner_seats.dtype != torch.int64
            or learner_seats.device != bridge.device
        ):
            raise SimpleTensorCollectorError(
                "learner_seats must be int64 [batch] on the Gym device"
            )
        expected = alternating_learner_seats(
            bridge.batch_size,
            device=bridge.device,
        )
        if not torch.equal(learner_seats, expected):
            raise SimpleTensorCollectorError(
                "learner seats must alternate by environment row"
            )
        if not opponent_contract_id:
            raise SimpleTensorCollectorError("opponent_contract_id is required")
        contract = dict(opponent_contract)
        contract_digest = _canonical_digest(contract)
        seat_spec = {
            "profile": SIMPLE_ALTERNATING_LEARNER_SEAT_PROFILE,
            "batch_size": bridge.batch_size,
            "seats": [index % 2 for index in range(bridge.batch_size)],
        }
        self.bridge = bridge
        self.public_mask_provider = public_mask_provider
        self.learner_policy = learner_policy
        self.opponent_policy = opponent_policy
        self.learner_seats = learner_seats.clone()
        self.opponent_seats = 1 - self.learner_seats
        self.reset_deck_provider = reset_deck_provider
        self.strict_host_validation = bool(strict_host_validation)
        self.device = bridge.device
        self.batch_size = bridge.batch_size
        self.metadata = SimpleTensorAsymmetricCollectorMetadata(
            schema_version=SIMPLE_ASYMMETRIC_COLLECTOR_SCHEMA_VERSION,
            learner_seat_profile=SIMPLE_ALTERNATING_LEARNER_SEAT_PROFILE,
            learner_seat_digest=_canonical_digest(seat_spec),
            opponent_contract_id=opponent_contract_id,
            opponent_contract_digest=contract_digest,
            opponent_contract=contract,
        )

    def _validate_mapping(
        self,
        label: str,
        values: Mapping[str, torch.Tensor] | None,
    ) -> None:
        for name, value in (values or {}).items():
            if not isinstance(value, torch.Tensor):
                raise SimpleTensorCollectorError(f"{label} {name!r} must be a tensor")
            if value.ndim < 2 or tuple(value.shape[:2]) != (self.batch_size, 1):
                raise SimpleTensorCollectorError(
                    f"{label} {name!r} must begin with [batch, 1]"
                )
            if value.device != self.device:
                raise SimpleTensorCollectorError(
                    f"{label} {name!r} must remain on {self.device}"
                )

    def _public_mask(
        self,
        observation: SimpleGymRolloutObservation,
        *,
        decision_index: int,
        bootstrap: bool,
        expected_semantics: tuple[str, str, Mapping[str, Any]] | None,
    ) -> tuple[SimplePublicActionMaskV2, tuple[str, str, Mapping[str, Any]]]:
        packet = self.public_mask_provider(
            SimpleTensorMaskRequest(observation, decision_index, bootstrap)
        )
        if not isinstance(packet, SimplePublicActionMaskV2):
            raise SimpleTensorCollectorError(
                "public_mask_provider must return SimplePublicActionMaskV2"
            )
        if packet.contract_version != PUBLIC_ACTION_MASK_CONTRACT_V2:
            raise SimpleTensorCollectorError("public mask contract v2 is required")
        if packet.masks.shape != observation.legal_mask.shape:
            raise SimpleTensorCollectorError(
                "public action masks must match simulator legal-mask shape"
            )
        if packet.masks.dtype != torch.bool or packet.masks.device != self.device:
            raise SimpleTensorCollectorError(
                "public action masks must be bool on the Gym device"
            )
        semantics = (
            packet.semantics_id,
            packet.semantics_digest,
            packet.semantics,
        )
        if expected_semantics is not None and semantics[:2] != expected_semantics[:2]:
            raise SimpleTensorCollectorError(
                "public mask semantics changed during collection"
            )
        return packet, semantics

    def _boundary(
        self,
        observation: SimpleGymRolloutObservation,
        packet: SimplePublicActionMaskV2,
        recurrent_inputs: Mapping[str, torch.Tensor] | None,
        seats: torch.Tensor,
        decision_index: int,
        *,
        include_critic: bool,
    ) -> SimpleTensorPolicyBoundary:
        return SimpleTensorPolicyBoundary(
            actor=_select_public(observation.actor, seats),
            critic=(
                _select_critic(observation.critic, seats) if include_critic else None
            ),
            legal_mask=_select_seat(observation.legal_mask, seats),
            public_action_masks=_select_seat(packet.masks, seats),
            previous_actions=_select_seat(observation.previous_actions, seats),
            previous_rewards=_select_seat(observation.previous_rewards, seats),
            episode_starts=_select_seat(observation.episode_starts, seats),
            recurrent_inputs=recurrent_inputs,
            decision_index=decision_index,
        )

    def _validate_decision(
        self,
        label: str,
        decision: SimpleTensorPolicyDecision,
        masks: torch.Tensor,
    ) -> None:
        if not isinstance(decision, SimpleTensorPolicyDecision):
            raise SimpleTensorCollectorError(
                f"{label} policy must return SimpleTensorPolicyDecision"
            )
        if (
            decision.actions.shape != (self.batch_size, 1)
            or decision.actions.dtype != torch.int64
            or decision.actions.device != self.device
        ):
            raise SimpleTensorCollectorError(
                f"{label} actions must be int64 [batch, 1] on the Gym device"
            )
        self._validate_mapping(
            f"{label} next recurrent input",
            decision.next_recurrent_inputs,
        )
        self._validate_mapping(f"{label} policy storage", decision.storage)
        if self.strict_host_validation:
            selected = masks.gather(2, decision.actions[..., None]).squeeze(2)
            if not bool(selected.all().item()):
                raise SimpleTensorCollectorError(
                    f"{label} selected a public-masked action"
                )

    def _enforce_admission(
        self,
        *,
        fallback_rows: torch.Tensor,
        admitted: torch.Tensor,
        committed: torch.Tensor,
        native_ticks: torch.Tensor,
        done: torch.Tensor,
    ) -> None:
        invalid = torch.stack(
            (
                fallback_rows.any(),
                (~admitted).any(),
                (~committed).any(),
                (
                    (native_ticks < 1) | (native_ticks > self.bridge.decision_interval)
                ).any(),
                ((~done) & (native_ticks != self.bridge.decision_interval)).any(),
            )
        ).any()
        if self.strict_host_validation or invalid.device.type == "mps":
            if bool(invalid.item()):
                raise SimpleTensorCollectorError(
                    "asymmetric collector native-admission contract failed"
                )
        else:
            torch._assert_async(
                ~invalid,
                "asymmetric collector native-admission contract failed",
            )

    def collect(
        self,
        decision_steps: int,
        *,
        learner_recurrent_inputs: Mapping[str, torch.Tensor] | None = None,
        opponent_recurrent_inputs: Mapping[str, torch.Tensor] | None = None,
    ) -> SimpleTensorAsymmetricDecisionBatch:
        if not isinstance(decision_steps, int) or isinstance(decision_steps, bool):
            raise TypeError("decision_steps must be a positive integer")
        if decision_steps < 1:
            raise ValueError("decision_steps must be a positive integer")
        self._validate_mapping("learner recurrent input", learner_recurrent_inputs)
        self._validate_mapping("opponent recurrent input", opponent_recurrent_inputs)

        actors: list[TensorPublicStructuredObservation] = []
        critics: list[TensorPrivilegedCriticObservation | None] = []
        legal_masks: list[torch.Tensor] = []
        public_masks: list[torch.Tensor] = []
        previous_actions: list[torch.Tensor] = []
        previous_rewards: list[torch.Tensor] = []
        episode_starts: list[torch.Tensor] = []
        actions: list[torch.Tensor] = []
        rewards: list[torch.Tensor] = []
        dones: list[torch.Tensor] = []
        winners: list[torch.Tensor] = []
        action_success: list[torch.Tensor] = []
        native_ticks: list[torch.Tensor] = []
        committed: list[torch.Tensor] = []
        fallback_rows: list[torch.Tensor] = []
        admitted: list[torch.Tensor] = []
        reset_masks: list[torch.Tensor] = []
        learner_recurrent_storage: list[Mapping[str, torch.Tensor] | None] = []
        learner_policy_storage: list[Mapping[str, torch.Tensor] | None] = []
        opponent_actions: list[torch.Tensor] = []
        opponent_recurrent_storage: list[Mapping[str, torch.Tensor] | None] = []
        mask_semantics: tuple[str, str, Mapping[str, Any]] | None = None
        simulator_mask_profile: str | None = None

        current_learner = learner_recurrent_inputs
        current_opponent = opponent_recurrent_inputs
        for decision_index in range(decision_steps):
            observation = self.bridge.observe()
            packet, mask_semantics = self._public_mask(
                observation,
                decision_index=decision_index,
                bootstrap=False,
                expected_semantics=mask_semantics,
            )
            learner_boundary = self._boundary(
                observation,
                packet,
                current_learner,
                self.learner_seats,
                decision_index,
                include_critic=True,
            )
            opponent_boundary = self._boundary(
                observation,
                packet,
                current_opponent,
                self.opponent_seats,
                decision_index,
                include_critic=False,
            )
            learner_decision = self.learner_policy(learner_boundary)
            opponent_decision = self.opponent_policy(opponent_boundary)
            self._validate_decision(
                "learner",
                learner_decision,
                learner_boundary.public_action_masks,
            )
            self._validate_decision(
                "opponent",
                opponent_decision,
                opponent_boundary.public_action_masks,
            )
            joint_actions = torch.empty(
                (self.batch_size, 2),
                dtype=torch.int64,
                device=self.device,
            )
            joint_actions.scatter_(
                1,
                self.learner_seats[:, None],
                learner_decision.actions,
            )
            joint_actions.scatter_(
                1,
                self.opponent_seats[:, None],
                opponent_decision.actions,
            )
            step = self.bridge.step(
                joint_actions,
                public_action_masks=packet.masks,
                public_action_mask_contract_version=packet.contract_version,
                pre_action_boundary=observation,
            )
            if simulator_mask_profile is None:
                simulator_mask_profile = step.simulator_action_mask_profile
            elif simulator_mask_profile != step.simulator_action_mask_profile:
                raise SimpleTensorCollectorError(
                    "simulator action-mask profile changed during collection"
                )

            actors.append(_clone_public(learner_boundary.actor))
            critics.append(_select_critic(step.critic, self.learner_seats))
            legal_masks.append(learner_boundary.legal_mask.clone())
            public_masks.append(learner_boundary.public_action_masks.clone())
            previous_actions.append(learner_boundary.previous_actions.clone())
            previous_rewards.append(learner_boundary.previous_rewards.clone())
            episode_starts.append(learner_boundary.episode_starts.clone())
            actions.append(learner_decision.actions.clone())
            rewards.append(_select_seat(step.rewards, self.learner_seats))
            dones.append(step.done.clone())
            winners.append(step.winner.clone())
            action_success.append(_select_seat(step.action_success, self.learner_seats))
            native_ticks.append(step.native_ticks.clone())
            committed.append(step.committed.clone())
            fallback_rows.append(step.fallback_rows.clone())
            admitted.append(step.all_rows_admitted.clone())
            reset_masks.append(step.done.clone())
            learner_recurrent_storage.append(_clone_mapping(current_learner))
            learner_policy_storage.append(_clone_mapping(learner_decision.storage))
            opponent_actions.append(opponent_decision.actions.clone())
            opponent_recurrent_storage.append(_clone_mapping(current_opponent))
            current_learner = learner_decision.next_recurrent_inputs
            current_opponent = opponent_decision.next_recurrent_inputs

            reset_decks = (
                None
                if self.reset_deck_provider is None
                else self.reset_deck_provider(decision_index, step.done, step)
            )
            self.bridge.reset_done(step.done, deck_ids=reset_decks)

        bootstrap_observation = self.bridge.observe()
        bootstrap_packet, mask_semantics = self._public_mask(
            bootstrap_observation,
            decision_index=decision_steps,
            bootstrap=True,
            expected_semantics=mask_semantics,
        )
        learner_bootstrap = self._boundary(
            bootstrap_observation,
            bootstrap_packet,
            current_learner,
            self.learner_seats,
            decision_steps,
            include_critic=True,
        )
        opponent_bootstrap = self._boundary(
            bootstrap_observation,
            bootstrap_packet,
            current_opponent,
            self.opponent_seats,
            decision_steps,
            include_critic=False,
        )
        assert mask_semantics is not None
        assert simulator_mask_profile is not None
        stacked_done = torch.stack(dones)
        stacked_native_ticks = torch.stack(native_ticks)
        stacked_committed = torch.stack(committed)
        stacked_fallback = torch.stack(fallback_rows)
        stacked_admitted = torch.stack(admitted)
        self._enforce_admission(
            fallback_rows=stacked_fallback,
            admitted=stacked_admitted,
            committed=stacked_committed,
            native_ticks=stacked_native_ticks,
            done=stacked_done,
        )
        collector_metadata = SimpleTensorCollectorMetadata(
            schema_version=SIMPLE_TENSOR_COLLECTOR_SCHEMA_VERSION,
            backend_id=SIMPLE_TENSOR_BACKEND_ID,
            admission_validation=(
                "strict-host-after-rollout"
                if self.strict_host_validation
                else "device-async-after-rollout"
            ),
            actor_semantics_id=SIMPLE_TENSOR_ACTOR_SEMANTICS_ID,
            decision_interval=self.bridge.decision_interval,
            simulator_action_mask_profile=simulator_mask_profile,
            public_action_mask_contract_version=PUBLIC_ACTION_MASK_CONTRACT_V2,
            public_action_mask_semantics_id=mask_semantics[0],
            public_action_mask_semantics_digest=mask_semantics[1],
            public_action_mask_semantics=mask_semantics[2],
            reward_contract_id=self.bridge.reward_contract_id,
            reward_contract_digest=self.bridge.reward_contract_digest,
            reward_contract_metadata=self.bridge.reward_contract_metadata,
        )
        stacked_learner_policy = _stack_mappings(
            learner_policy_storage,
            label="learner policy storage",
        )
        learner_batch = SimpleTensorDecisionBatch(
            actor=_stack_public(actors),
            critic=_stack_critic(critics),
            legal_masks=torch.stack(legal_masks),
            public_action_masks=torch.stack(public_masks),
            previous_actions=torch.stack(previous_actions),
            previous_rewards=torch.stack(previous_rewards),
            episode_starts=torch.stack(episode_starts),
            actions=torch.stack(actions),
            rewards=torch.stack(rewards),
            done=stacked_done,
            winner=torch.stack(winners),
            action_success=torch.stack(action_success),
            native_ticks=stacked_native_ticks,
            committed=stacked_committed,
            fallback_rows=stacked_fallback,
            all_rows_admitted=stacked_admitted,
            reset_masks=torch.stack(reset_masks),
            recurrent_inputs=_stack_mappings(
                learner_recurrent_storage,
                label="learner recurrent input",
            ),
            policy_storage=(
                {} if stacked_learner_policy is None else stacked_learner_policy
            ),
            bootstrap=learner_bootstrap,
            metadata=collector_metadata,
        )
        return SimpleTensorAsymmetricDecisionBatch(
            learner=learner_batch,
            learner_seats=self.learner_seats.clone(),
            opponent_actions=torch.stack(opponent_actions),
            opponent_recurrent_inputs=_stack_mappings(
                opponent_recurrent_storage,
                label="opponent recurrent input",
            ),
            opponent_bootstrap=opponent_bootstrap,
            metadata=self.metadata,
        )


__all__ = [
    "SIMPLE_ALTERNATING_LEARNER_SEAT_PROFILE",
    "SIMPLE_ASYMMETRIC_COLLECTOR_SCHEMA_VERSION",
    "SimpleTensorAsymmetricCollector",
    "SimpleTensorAsymmetricCollectorMetadata",
    "SimpleTensorAsymmetricDecisionBatch",
    "alternating_learner_seats",
]
