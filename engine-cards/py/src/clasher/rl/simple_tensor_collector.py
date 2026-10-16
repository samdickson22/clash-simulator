"""Generic device-resident collector for the practical tensor Gym.

The collector owns rollout chronology, not policy architecture. A caller
supplies label-independent public-mask-v2 tensors and a structural policy
callback. Actor/critic views, recurrent inputs, policy outputs, transitions,
and the post-reset bootstrap boundary remain on the Gym device until a later
training-stack adapter deliberately serializes them.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from typing import Any, Final, Protocol

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
    SimpleGymRolloutStep,
)

SIMPLE_TENSOR_COLLECTOR_SCHEMA_VERSION: Final = 1
SIMPLE_TENSOR_BACKEND_ID: Final = "simple-pytorch-gym-v1"
SIMPLE_TENSOR_ACTOR_SEMANTICS_ID: Final = "typed-public-structured-canonical-v1"


class SimpleTensorCollectorError(RuntimeError):
    """Raised before returning a semantically incomplete decision batch."""


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
            "semantics metadata must be canonical JSON"
        ) from error
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class SimplePublicActionMaskV2:
    """One caller-built, label-independent public action mask boundary."""

    masks: torch.Tensor
    semantics_id: str
    semantics: Mapping[str, Any]
    contract_version: int = PUBLIC_ACTION_MASK_CONTRACT_V2

    @property
    def semantics_digest(self) -> str:
        return _canonical_digest(self.semantics)


@dataclass(frozen=True)
class SimpleTensorMaskRequest:
    observation: SimpleGymRolloutObservation
    decision_index: int
    bootstrap: bool


@dataclass(frozen=True)
class SimpleTensorPolicyBoundary:
    """Model-neutral inputs for one pre-action policy decision."""

    actor: TensorPublicStructuredObservation
    critic: TensorPrivilegedCriticObservation | None
    legal_mask: torch.Tensor
    public_action_masks: torch.Tensor
    previous_actions: torch.Tensor
    previous_rewards: torch.Tensor
    episode_starts: torch.Tensor
    recurrent_inputs: Mapping[str, torch.Tensor] | None
    decision_index: int


@dataclass(frozen=True)
class SimpleTensorPolicyDecision:
    """Structural policy result; optional tensors are stored without interpretation."""

    actions: torch.Tensor
    next_recurrent_inputs: Mapping[str, torch.Tensor] | None = None
    storage: Mapping[str, torch.Tensor] = field(default_factory=dict)


class SimplePublicMaskProvider(Protocol):
    def __call__(self, request: SimpleTensorMaskRequest) -> SimplePublicActionMaskV2: ...


class SimpleTensorPolicy(Protocol):
    def __call__(
        self, boundary: SimpleTensorPolicyBoundary
    ) -> SimpleTensorPolicyDecision: ...


class SimpleResetDeckProvider(Protocol):
    def __call__(
        self,
        decision_index: int,
        reset_mask: torch.Tensor,
        step: SimpleGymRolloutStep,
    ) -> torch.Tensor | None: ...


@dataclass(frozen=True)
class SimpleTensorCollectorMetadata:
    schema_version: int
    backend_id: str
    admission_validation: str
    actor_semantics_id: str
    decision_interval: int
    simulator_action_mask_profile: str
    public_action_mask_contract_version: int
    public_action_mask_semantics_id: str
    public_action_mask_semantics_digest: str
    public_action_mask_semantics: Mapping[str, Any]
    reward_contract_id: str
    reward_contract_digest: str
    reward_contract_metadata: Mapping[str, Any]


@dataclass(frozen=True)
class SimpleTensorDecisionBatch:
    """Fixed-length decisions with leading shape ``[steps, batch, seats]``."""

    actor: TensorPublicStructuredObservation
    next_global_features: torch.Tensor
    critic: TensorPrivilegedCriticObservation | None
    legal_masks: torch.Tensor
    public_action_masks: torch.Tensor
    previous_actions: torch.Tensor
    previous_rewards: torch.Tensor
    episode_starts: torch.Tensor
    actions: torch.Tensor
    rewards: torch.Tensor
    done: torch.Tensor
    winner: torch.Tensor
    action_success: torch.Tensor
    native_ticks: torch.Tensor
    committed: torch.Tensor
    fallback_rows: torch.Tensor
    all_rows_admitted: torch.Tensor
    reset_masks: torch.Tensor
    recurrent_inputs: Mapping[str, torch.Tensor] | None
    policy_storage: Mapping[str, torch.Tensor]
    bootstrap: SimpleTensorPolicyBoundary
    metadata: SimpleTensorCollectorMetadata

    @property
    def decision_steps(self) -> int:
        return int(self.actions.shape[0])

    @property
    def batch_size(self) -> int:
        return int(self.actions.shape[1])


def _stack_public(
    values: list[TensorPublicStructuredObservation],
) -> TensorPublicStructuredObservation:
    return TensorPublicStructuredObservation(
        **{
            descriptor.name: torch.stack(
                [getattr(value, descriptor.name) for value in values]
            )
            for descriptor in fields(TensorPublicStructuredObservation)
        }
    )


def _clone_public(
    value: TensorPublicStructuredObservation,
) -> TensorPublicStructuredObservation:
    """Detach one decision from reusable CUDA Graph output addresses."""

    return TensorPublicStructuredObservation(
        **{
            descriptor.name: getattr(value, descriptor.name).clone()
            for descriptor in fields(TensorPublicStructuredObservation)
        }
    )


def _clone_critic(
    value: TensorPrivilegedCriticObservation | None,
) -> TensorPrivilegedCriticObservation | None:
    if value is None:
        return None
    return TensorPrivilegedCriticObservation(
        **{
            descriptor.name: getattr(value, descriptor.name).clone()
            for descriptor in fields(TensorPrivilegedCriticObservation)
        }
    )


def _stack_critic(
    values: list[TensorPrivilegedCriticObservation | None],
) -> TensorPrivilegedCriticObservation | None:
    if all(value is None for value in values):
        return None
    if any(value is None for value in values):
        raise SimpleTensorCollectorError("critic presence changed during collection")
    concrete = [value for value in values if value is not None]
    return TensorPrivilegedCriticObservation(
        **{
            descriptor.name: torch.stack(
                [getattr(value, descriptor.name) for value in concrete]
            )
            for descriptor in fields(TensorPrivilegedCriticObservation)
        }
    )


def _clone_mapping(
    values: Mapping[str, torch.Tensor] | None,
) -> dict[str, torch.Tensor] | None:
    if values is None:
        return None
    return {name: value.clone() for name, value in values.items()}


def _stack_mappings(
    values: list[Mapping[str, torch.Tensor] | None],
    *,
    label: str,
) -> Mapping[str, torch.Tensor] | None:
    if all(value is None for value in values):
        return None
    if any(value is None for value in values):
        raise SimpleTensorCollectorError(f"{label} presence changed during collection")
    concrete = [value for value in values if value is not None]
    keys = tuple(concrete[0])
    if any(tuple(value) != keys for value in concrete[1:]):
        raise SimpleTensorCollectorError(f"{label} keys changed during collection")
    return {
        name: torch.stack([value[name] for value in concrete]) for name in keys
    }


class SimpleTensorCollector:
    """Collect fixed-length native Gym decisions through structural callbacks."""

    def __init__(
        self,
        bridge: SimpleGymRolloutBridge,
        *,
        public_mask_provider: SimplePublicMaskProvider,
        policy: SimpleTensorPolicy,
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
        self.bridge = bridge
        self.public_mask_provider = public_mask_provider
        self.policy = policy
        self.reset_deck_provider = reset_deck_provider
        self.strict_host_validation = bool(strict_host_validation)
        self.device = bridge.device
        self.batch_size = bridge.batch_size

    def _validate_mapping(
        self,
        label: str,
        values: Mapping[str, torch.Tensor] | None,
    ) -> None:
        for name, value in (values or {}).items():
            if not isinstance(value, torch.Tensor):
                raise SimpleTensorCollectorError(f"{label} {name!r} must be a tensor")
            if value.ndim < 2 or tuple(value.shape[:2]) != (self.batch_size, 2):
                raise SimpleTensorCollectorError(
                    f"{label} {name!r} must begin with [batch, 2]"
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
        if not packet.semantics_id:
            raise SimpleTensorCollectorError("public mask semantics_id is required")
        mask = packet.masks
        if mask.shape != observation.legal_mask.shape:
            raise SimpleTensorCollectorError(
                "public action masks must match simulator legal-mask shape"
            )
        if mask.dtype != torch.bool or mask.device != self.device:
            raise SimpleTensorCollectorError(
                "public action masks must be bool on the Gym device"
            )
        semantics = (packet.semantics_id, packet.semantics_digest, packet.semantics)
        if expected_semantics is not None and (
            semantics[0] != expected_semantics[0]
            or semantics[1] != expected_semantics[1]
        ):
            raise SimpleTensorCollectorError(
                "public mask semantics changed during collection"
            )
        return packet, semantics

    def _policy_boundary(
        self,
        observation: SimpleGymRolloutObservation,
        packet: SimplePublicActionMaskV2,
        recurrent_inputs: Mapping[str, torch.Tensor] | None,
        decision_index: int,
    ) -> SimpleTensorPolicyBoundary:
        return SimpleTensorPolicyBoundary(
            actor=observation.actor,
            critic=observation.critic,
            legal_mask=observation.legal_mask,
            public_action_masks=packet.masks,
            previous_actions=observation.previous_actions,
            previous_rewards=observation.previous_rewards,
            episode_starts=observation.episode_starts,
            recurrent_inputs=recurrent_inputs,
            decision_index=decision_index,
        )

    def _validate_decision(
        self,
        decision: SimpleTensorPolicyDecision,
        public_masks: torch.Tensor,
    ) -> None:
        if not isinstance(decision, SimpleTensorPolicyDecision):
            raise SimpleTensorCollectorError(
                "policy must return SimpleTensorPolicyDecision"
            )
        actions = decision.actions
        if actions.shape != (self.batch_size, 2):
            raise SimpleTensorCollectorError("policy actions must have shape [batch, 2]")
        if actions.dtype != torch.int64 or actions.device != self.device:
            raise SimpleTensorCollectorError(
                "policy actions must be int64 on the Gym device"
            )
        self._validate_mapping("next recurrent input", decision.next_recurrent_inputs)
        self._validate_mapping("policy storage", decision.storage)
        if self.strict_host_validation:
            self._validate_masked_action_host(actions, public_masks)

    @staticmethod
    def _validate_masked_action_host(
        actions: torch.Tensor,
        public_masks: torch.Tensor,
    ) -> None:
        """Strict debug validation allowed to synchronize before mutation."""

        if bool(((actions < 0) | (actions >= public_masks.shape[2])).any().item()):
            raise SimpleTensorCollectorError("policy action is outside mask bounds")
        selected = public_masks.gather(2, actions[..., None]).squeeze(2)
        if not bool(selected.all().item()):
            raise SimpleTensorCollectorError("policy selected a public-masked action")

    def _enforce_native_admission(
        self,
        *,
        fallback_rows: torch.Tensor,
        all_rows_admitted: torch.Tensor,
        committed: torch.Tensor,
        native_ticks: torch.Tensor,
        done: torch.Tensor,
    ) -> None:
        """Assert the complete rollout at one boundary, without a production sync."""

        invalid = torch.stack(
            (
                fallback_rows.any(),
                (~all_rows_admitted).any(),
                (~committed).any(),
                ((native_ticks < 1) | (native_ticks > self.bridge.decision_interval)).any(),
                ((~done) & (native_ticks != self.bridge.decision_interval)).any(),
            )
        ).any()
        if self.strict_host_validation or invalid.device.type == "mps":
            # PyTorch MPS does not implement aten::_assert_async. MPS already
            # uses an exact CPU public-mask boundary, so validate the scalar at
            # that host boundary while CUDA retains the asynchronous assertion.
            self._enforce_native_admission_host(invalid)
        else:
            torch._assert_async(
                ~invalid,
                "simple tensor collector native-admission contract failed",
            )

    @staticmethod
    def _enforce_native_admission_host(invalid: torch.Tensor) -> None:
        """One strict-debug host synchronization after collection."""

        if bool(invalid.item()):
            raise SimpleTensorCollectorError(
                "simple tensor collector native-admission contract failed"
            )

    def collect(
        self,
        decision_steps: int,
        *,
        recurrent_inputs: Mapping[str, torch.Tensor] | None = None,
    ) -> SimpleTensorDecisionBatch:
        if not isinstance(decision_steps, int) or isinstance(decision_steps, bool):
            raise TypeError("decision_steps must be a positive integer")
        if decision_steps < 1:
            raise ValueError("decision_steps must be a positive integer")
        self._validate_mapping("recurrent input", recurrent_inputs)

        actors: list[TensorPublicStructuredObservation] = []
        next_global_features: list[torch.Tensor] = []
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
        recurrent_storage: list[Mapping[str, torch.Tensor] | None] = []
        policy_storage: list[Mapping[str, torch.Tensor] | None] = []
        mask_semantics: tuple[str, str, Mapping[str, Any]] | None = None
        simulator_mask_profile: str | None = None

        current_recurrent = recurrent_inputs
        for decision_index in range(decision_steps):
            observation = self.bridge.observe()
            packet, mask_semantics = self._public_mask(
                observation,
                decision_index=decision_index,
                bootstrap=False,
                expected_semantics=mask_semantics,
            )
            boundary = self._policy_boundary(
                observation, packet, current_recurrent, decision_index
            )
            decision = self.policy(boundary)
            self._validate_decision(decision, packet.masks)
            step = self.bridge.step(
                decision.actions,
                recurrent_inputs=current_recurrent,
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

            # A graph-backed bridge reuses output addresses on its next
            # replay. Snapshot every policy input before collection advances.
            actors.append(_clone_public(step.actor))
            next_global_features.append(step.next_actor.global_features.clone())
            critics.append(_clone_critic(step.critic))
            legal_masks.append(step.legal_mask.clone())
            assert step.public_action_masks is not None
            public_masks.append(step.public_action_masks.clone())
            previous_actions.append(step.previous_actions.clone())
            previous_rewards.append(step.previous_rewards.clone())
            episode_starts.append(step.episode_starts.clone())
            actions.append(decision.actions.clone())
            rewards.append(step.rewards.clone())
            dones.append(step.done.clone())
            winners.append(step.winner.clone())
            action_success.append(step.action_success.clone())
            native_ticks.append(step.native_ticks.clone())
            committed.append(step.committed.clone())
            fallback_rows.append(step.fallback_rows.clone())
            admitted.append(step.all_rows_admitted.clone())
            reset_masks.append(step.done.clone())
            recurrent_storage.append(_clone_mapping(current_recurrent))
            policy_storage.append(_clone_mapping(decision.storage))
            current_recurrent = decision.next_recurrent_inputs

            reset_decks = (
                None
                if self.reset_deck_provider is None
                else self.reset_deck_provider(decision_index, step.done, step)
            )
            # Avoid a device-to-host terminal branch. Row selection is entirely
            # tensorized, so an all-false mask is a semantic no-op.
            self.bridge.reset_done(step.done, deck_ids=reset_decks)

        bootstrap_observation = self.bridge.observe()
        bootstrap_packet, mask_semantics = self._public_mask(
            bootstrap_observation,
            decision_index=decision_steps,
            bootstrap=True,
            expected_semantics=mask_semantics,
        )
        bootstrap = self._policy_boundary(
            bootstrap_observation,
            bootstrap_packet,
            current_recurrent,
            decision_steps,
        )
        assert mask_semantics is not None
        assert simulator_mask_profile is not None
        stacked_done = torch.stack(dones)
        stacked_native_ticks = torch.stack(native_ticks)
        stacked_committed = torch.stack(committed)
        stacked_fallback_rows = torch.stack(fallback_rows)
        stacked_admitted = torch.stack(admitted)
        self._enforce_native_admission(
            fallback_rows=stacked_fallback_rows,
            all_rows_admitted=stacked_admitted,
            committed=stacked_committed,
            native_ticks=stacked_native_ticks,
            done=stacked_done,
        )
        metadata = SimpleTensorCollectorMetadata(
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
        stacked_policy = _stack_mappings(policy_storage, label="policy storage")
        return SimpleTensorDecisionBatch(
            actor=_stack_public(actors),
            next_global_features=torch.stack(next_global_features),
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
            fallback_rows=stacked_fallback_rows,
            all_rows_admitted=stacked_admitted,
            reset_masks=torch.stack(reset_masks),
            recurrent_inputs=_stack_mappings(
                recurrent_storage, label="recurrent input"
            ),
            policy_storage={} if stacked_policy is None else stacked_policy,
            bootstrap=bootstrap,
            metadata=metadata,
        )


__all__ = [
    "SIMPLE_TENSOR_ACTOR_SEMANTICS_ID",
    "SIMPLE_TENSOR_BACKEND_ID",
    "SIMPLE_TENSOR_COLLECTOR_SCHEMA_VERSION",
    "SimplePublicActionMaskV2",
    "SimplePublicMaskProvider",
    "SimpleResetDeckProvider",
    "SimpleTensorCollector",
    "SimpleTensorCollectorError",
    "SimpleTensorCollectorMetadata",
    "SimpleTensorDecisionBatch",
    "SimpleTensorMaskRequest",
    "SimpleTensorPolicy",
    "SimpleTensorPolicyBoundary",
    "SimpleTensorPolicyDecision",
]
