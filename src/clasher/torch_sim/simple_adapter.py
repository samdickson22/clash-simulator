"""Training-facing contract for a small, unified tensor Gym engine.

The adapter is deliberately structural: a fast engine does not inherit from or
import the retained resident engine.  It only returns already-projected public
actor tensors, an optional separate critic view, and transition tensors.  Shape
and device checks inspect tensor metadata only; the hot path never calls
``item()``, ``tolist()``, or copies tensors to the host.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

import torch

from .policy_validation import (
    PUBLIC_ACTION_MASK_CONTRACT_V2,
    ProjectedGymTransition,
)
from .resident_outputs import (
    TensorPrivilegedCriticObservation,
    TensorPublicStructuredObservation,
)

SIMPLIFIED_GYM_ACTION_MASK_PROFILE = "simulator_exact_legal_v1"


class SimpleGymContractError(ValueError):
    """Raised before engine mutation when a policy boundary is malformed."""


class SimpleGymObservation(Protocol):
    """Already-projected observation returned by a unified tensor engine."""

    @property
    def actor(self) -> TensorPublicStructuredObservation: ...

    @property
    def critic(self) -> TensorPrivilegedCriticObservation | None: ...

    @property
    def legal_mask(self) -> torch.Tensor: ...


class SimpleGymStepResult(Protocol):
    """Minimal result of one native engine tick.

    ``committed`` is evidence, not fallback routing.  Implementations must
    raise instead of returning a partially scalar or partially mutated batch.
    """

    @property
    def observation(self) -> SimpleGymObservation: ...

    @property
    def action_success(self) -> torch.Tensor: ...

    @property
    def reward(self) -> torch.Tensor: ...

    @property
    def done(self) -> torch.Tensor: ...

    @property
    def winner(self) -> torch.Tensor: ...

    @property
    def native_ticks(self) -> torch.Tensor: ...

    @property
    def committed(self) -> torch.Tensor: ...


class SimpleGymEngine(Protocol):
    """Structural interface implemented by the simplified Gym kernel."""

    @property
    def device(self) -> torch.device: ...

    @property
    def batch_size(self) -> int: ...

    def observe(self) -> SimpleGymObservation: ...

    def step_tick(self, action_ids: torch.Tensor) -> SimpleGymStepResult: ...


@dataclass(frozen=True)
class SimpleGymHistory:
    """Rollout-owned recurrent scalars for both actor seats."""

    previous_actions: torch.Tensor
    previous_rewards: torch.Tensor
    episode_starts: torch.Tensor

    @classmethod
    def initial(
        cls,
        batch_size: int,
        *,
        device: torch.device,
        no_op_action: int,
        reward_dtype: torch.dtype = torch.float32,
    ) -> SimpleGymHistory:
        shape = (batch_size, 2)
        return cls(
            previous_actions=torch.full(
                shape, no_op_action, dtype=torch.int64, device=device
            ),
            previous_rewards=torch.zeros(
                shape, dtype=reward_dtype, device=device
            ),
            episode_starts=torch.ones(shape, dtype=torch.bool, device=device),
        )


@dataclass(frozen=True)
class SimpleGymAdmission:
    """Zero-fallback evidence accompanying a simplified Gym transition."""

    simulator_action_mask_profile: str
    native_ticks: torch.Tensor
    committed: torch.Tensor
    fallback_rows: tuple[int, ...] = ()
    all_rows_admitted: bool = True


@dataclass(frozen=True)
class SimpleGymAdapterStep:
    """One policy boundary plus the history used before and after it."""

    observation: SimpleGymObservation
    legal_mask: torch.Tensor
    rewards: torch.Tensor
    dones: torch.Tensor
    winner: torch.Tensor
    action_success: torch.Tensor
    history_before: SimpleGymHistory
    history_after: SimpleGymHistory
    transition: ProjectedGymTransition
    admission: SimpleGymAdmission


def _same_device(actual: torch.device, expected: torch.device) -> bool:
    if actual.type != expected.type:
        return False
    return expected.index is None or actual.index == expected.index


def _require_tensor(
    name: str,
    value: torch.Tensor,
    *,
    shape: tuple[int, ...],
    device: torch.device,
    dtypes: tuple[torch.dtype, ...],
) -> None:
    if not isinstance(value, torch.Tensor):
        raise SimpleGymContractError(f"{name} must be a torch.Tensor")
    if tuple(value.shape) != shape:
        raise SimpleGymContractError(f"{name} must have shape {shape}")
    if value.dtype not in dtypes:
        allowed = ", ".join(str(dtype) for dtype in dtypes)
        raise SimpleGymContractError(f"{name} must use one of: {allowed}")
    if not _same_device(value.device, device):
        raise SimpleGymContractError(f"{name} must be on {device}")


def _validate_observation(
    observation: SimpleGymObservation,
    *,
    batch_size: int,
    device: torch.device,
) -> None:
    actor = observation.actor
    entity_shape = tuple(actor.entity_ids.shape)
    if len(entity_shape) != 3 or entity_shape[:2] != (batch_size, 2):
        raise SimpleGymContractError(
            "actor.entity_ids must have shape [batch, 2, entities]"
        )
    entities = entity_shape[2]
    _require_tensor(
        "actor.entity_ids",
        actor.entity_ids,
        shape=(batch_size, 2, entities),
        device=device,
        dtypes=(torch.int64,),
    )
    features = tuple(actor.entity_features.shape)
    if len(features) != 4 or features[:3] != (batch_size, 2, entities):
        raise SimpleGymContractError(
            "actor.entity_features must align with [batch, 2, entities]"
        )
    _require_tensor(
        "actor.entity_features",
        actor.entity_features,
        shape=features,
        device=device,
        dtypes=(torch.float32,),
    )
    _require_tensor(
        "actor.entity_mask",
        actor.entity_mask,
        shape=(batch_size, 2, entities),
        device=device,
        dtypes=(torch.bool,),
    )
    for name, value, dtypes in (
        ("hand_ids", actor.hand_ids, (torch.int64,)),
        ("global_features", actor.global_features, (torch.float32,)),
    ):
        shape = tuple(value.shape)
        if len(shape) != 3 or shape[:2] != (batch_size, 2):
            raise SimpleGymContractError(
                f"actor.{name} must have shape [batch, 2, features]"
            )
        _require_tensor(
            f"actor.{name}", value, shape=shape, device=device, dtypes=dtypes
        )

    actions = tuple(observation.legal_mask.shape)
    if len(actions) != 3 or actions[:2] != (batch_size, 2):
        raise SimpleGymContractError(
            "legal_mask must have shape [batch, 2, actions]"
        )
    _require_tensor(
        "legal_mask",
        observation.legal_mask,
        shape=actions,
        device=device,
        dtypes=(torch.bool,),
    )

    critic = observation.critic
    if critic is None:
        return
    for name in (
        "entity_ids",
        "entity_features",
        "entity_mask",
        "card_ids",
        "global_features",
    ):
        value = getattr(critic, name)
        shape = tuple(value.shape)
        if len(shape) < 3 or shape[:2] != (batch_size, 2):
            raise SimpleGymContractError(
                f"critic.{name} must begin with [batch, 2]"
            )
        dtype = (
            (torch.bool,)
            if name == "entity_mask"
            else (torch.int64,)
            if name in {"entity_ids", "card_ids"}
            else (torch.float32,)
        )
        _require_tensor(
            f"critic.{name}", value, shape=shape, device=device, dtypes=dtype
        )


class SimpleGymAdapter:
    """Map a unified engine result onto the established policy transition."""

    def __init__(
        self,
        engine: SimpleGymEngine,
        *,
        no_op_action: int,
        history: SimpleGymHistory | None = None,
    ) -> None:
        self.engine = engine
        self.device = torch.device(engine.device)
        self.batch_size = int(engine.batch_size)
        self.no_op_action = int(no_op_action)
        self.history = history or SimpleGymHistory.initial(
            self.batch_size,
            device=self.device,
            no_op_action=self.no_op_action,
        )
        self._validate_history(self.history)

    def _validate_history(self, history: SimpleGymHistory) -> None:
        shape = (self.batch_size, 2)
        _require_tensor(
            "previous_actions",
            history.previous_actions,
            shape=shape,
            device=self.device,
            dtypes=(torch.int64,),
        )
        _require_tensor(
            "previous_rewards",
            history.previous_rewards,
            shape=shape,
            device=self.device,
            dtypes=(torch.float32, torch.float64),
        )
        _require_tensor(
            "episode_starts",
            history.episode_starts,
            shape=shape,
            device=self.device,
            dtypes=(torch.bool,),
        )

    def observe(self) -> SimpleGymObservation:
        observation = self.engine.observe()
        _validate_observation(
            observation, batch_size=self.batch_size, device=self.device
        )
        return observation

    def reset_history_rows(self, reset_mask: torch.Tensor) -> SimpleGymHistory:
        """Reset recurrent history for selected episode rows in-place logically.

        The adapter owns history independently from the simulator so a batched
        collector can reset completed rows without rebuilding either object.
        All selection remains device-resident and unselected values are copied
        exactly into the replacement immutable history record.
        """

        _require_tensor(
            "reset_mask",
            reset_mask,
            shape=(self.batch_size,),
            device=self.device,
            dtypes=(torch.bool,),
        )
        selected = reset_mask[:, None]
        self.history = SimpleGymHistory(
            previous_actions=torch.where(
                selected,
                torch.full_like(self.history.previous_actions, self.no_op_action),
                self.history.previous_actions,
            ),
            previous_rewards=torch.where(
                selected,
                torch.zeros_like(self.history.previous_rewards),
                self.history.previous_rewards,
            ),
            episode_starts=torch.where(
                selected,
                torch.ones_like(self.history.episode_starts),
                self.history.episode_starts,
            ),
        )
        return self.history

    def step(
        self,
        action_ids: torch.Tensor,
        *,
        recurrent_inputs: Mapping[str, torch.Tensor] | None = None,
        public_action_masks: torch.Tensor | None = None,
        public_action_mask_contract_version: int | None = None,
        update_history: bool = True,
    ) -> SimpleGymAdapterStep:
        shape = (self.batch_size, 2)
        _require_tensor(
            "action_ids",
            action_ids,
            shape=shape,
            device=self.device,
            dtypes=(torch.int64,),
        )
        if public_action_masks is None:
            if public_action_mask_contract_version is not None:
                raise SimpleGymContractError(
                    "public mask version requires public_action_masks"
                )
        else:
            if public_action_mask_contract_version != PUBLIC_ACTION_MASK_CONTRACT_V2:
                raise SimpleGymContractError(
                    "simplified Gym accepts public-mask contract v2 only"
                )
            mask_shape = tuple(public_action_masks.shape)
            if len(mask_shape) != 3 or mask_shape[:2] != shape:
                raise SimpleGymContractError(
                    "public_action_masks must have shape [batch, 2, actions]"
                )
            _require_tensor(
                "public_action_masks",
                public_action_masks,
                shape=mask_shape,
                device=self.device,
                dtypes=(torch.bool,),
            )
        for name, value in (recurrent_inputs or {}).items():
            recurrent_shape = tuple(value.shape)
            if len(recurrent_shape) < 2 or recurrent_shape[:2] != shape:
                raise SimpleGymContractError(
                    f"recurrent input {name!r} must begin with [batch, 2]"
                )
            if not _same_device(value.device, self.device):
                raise SimpleGymContractError(
                    f"recurrent input {name!r} must be on {self.device}"
                )

        history_before = self.history
        result = self.engine.step_tick(action_ids)
        _validate_observation(
            result.observation, batch_size=self.batch_size, device=self.device
        )
        _require_tensor(
            "action_success",
            result.action_success,
            shape=shape,
            device=self.device,
            dtypes=(torch.bool,),
        )
        _require_tensor(
            "reward",
            result.reward,
            shape=shape,
            device=self.device,
            dtypes=(torch.float32, torch.float64),
        )
        for name, value, dtypes in (
            ("done", result.done, (torch.bool,)),
            ("winner", result.winner, (torch.int8, torch.int64)),
            ("native_ticks", result.native_ticks, (torch.int64,)),
            ("committed", result.committed, (torch.bool,)),
        ):
            _require_tensor(
                name,
                value,
                shape=(self.batch_size,),
                device=self.device,
                dtypes=dtypes,
            )

        transition = ProjectedGymTransition(
            actor=result.observation.actor,
            critic=result.observation.critic,
            public_action_masks=public_action_masks,
            public_action_mask_contract_version=public_action_mask_contract_version,
            action_success=result.action_success,
            rewards=result.reward,
            done=result.done,
            winner=result.winner,
            previous_actions=history_before.previous_actions,
            previous_rewards=history_before.previous_rewards,
            episode_starts=history_before.episode_starts,
            recurrent_inputs=recurrent_inputs,
        )
        terminal = result.done[:, None]
        history_after = SimpleGymHistory(
            previous_actions=torch.where(
                terminal,
                torch.full_like(action_ids, self.no_op_action),
                action_ids,
            ),
            previous_rewards=torch.where(
                terminal, torch.zeros_like(result.reward), result.reward
            ),
            episode_starts=terminal.expand(-1, 2),
        )
        if update_history:
            self.history = history_after
        return SimpleGymAdapterStep(
            observation=result.observation,
            legal_mask=result.observation.legal_mask,
            rewards=result.reward,
            dones=result.done,
            winner=result.winner,
            action_success=result.action_success,
            history_before=history_before,
            history_after=history_after,
            transition=transition,
            admission=SimpleGymAdmission(
                simulator_action_mask_profile=SIMPLIFIED_GYM_ACTION_MASK_PROFILE,
                native_ticks=result.native_ticks,
                committed=result.committed,
            ),
        )


__all__ = [
    "SIMPLIFIED_GYM_ACTION_MASK_PROFILE",
    "SimpleGymAdapter",
    "SimpleGymAdapterStep",
    "SimpleGymAdmission",
    "SimpleGymContractError",
    "SimpleGymEngine",
    "SimpleGymHistory",
    "SimpleGymObservation",
    "SimpleGymStepResult",
]
