"""Dense continuous-target damage ramp for the practical tensor Gym.

This module owns only the small, reusable state machine shared by continuous
damage attackers.  Target acquisition, range checks, attack cooldowns, and
damage application stay with the caller.  A positive ``current_target_id``
means that the channel is connected for this tick; zero means that it is not.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import torch


@dataclass
class FastDamageRampState:
    """Fixed-shape ramp state aligned with the entity pool."""

    device: torch.device
    observed_target_stable_id: torch.Tensor
    connected_ticks: torch.Tensor
    stage: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.connected_ticks.shape[0])

    @property
    def max_entities(self) -> int:
        return int(self.connected_ticks.shape[1])

    @classmethod
    def empty(
        cls,
        batch_size: int,
        *,
        max_entities: int = 64,
        device: str | torch.device = "cpu",
    ) -> FastDamageRampState:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if max_entities < 1:
            raise ValueError("max_entities must be positive")
        tensor_device = torch.device(device)
        if tensor_device.type == "cuda" and tensor_device.index is None:
            tensor_device = torch.device("cuda", torch.cuda.current_device())
        shape = (batch_size, max_entities)
        return cls(
            device=tensor_device,
            observed_target_stable_id=torch.zeros(
                shape, dtype=torch.int64, device=tensor_device
            ),
            connected_ticks=torch.zeros(
                shape, dtype=torch.int32, device=tensor_device
            ),
            stage=torch.zeros(shape, dtype=torch.int8, device=tensor_device),
        )

    def clone(self) -> FastDamageRampState:
        values: dict[str, object] = {"device": self.device}
        for descriptor in fields(self):
            if descriptor.name != "device":
                values[descriptor.name] = getattr(self, descriptor.name).clone()
        return type(self)(**values)  # type: ignore[arg-type]


@dataclass(frozen=True)
class FastDamageRampParameters:
    """Numeric ramp configuration, with every plane shaped ``[B, E]``.

    ``retarget_grace_ticks`` is returned when an already-observed target is
    lost or replaced.  The attack-clock owner may use it to clamp its cooldown;
    keeping that clock out of this state avoids duplicate timing authority.
    """

    enabled: torch.Tensor
    stage_1_ticks: torch.Tensor
    stage_2_ticks: torch.Tensor
    stage_0_damage_multiplier: torch.Tensor
    stage_1_damage_multiplier: torch.Tensor
    stage_2_damage_multiplier: torch.Tensor
    retarget_grace_ticks: torch.Tensor


@dataclass(frozen=True)
class FastDamageRampStepResult:
    """Pre-attack multiplier and tensor-only transition facts."""

    damage_multiplier: torch.Tensor
    observed_target_stable_id: torch.Tensor
    connected_ticks: torch.Tensor
    stage: torch.Tensor
    connected: torch.Tensor
    reset: torch.Tensor
    target_changed: torch.Tensor
    retarget_delay_ticks: torch.Tensor


def _validate_damage_ramp(
    state: FastDamageRampState,
    parameters: FastDamageRampParameters,
) -> tuple[int, int]:
    shape = tuple(state.connected_ticks.shape)
    if len(shape) != 2:
        raise ValueError("damage-ramp tensors must have shape [batch, entities]")
    state_dtypes = {
        "observed_target_stable_id": torch.int64,
        "connected_ticks": torch.int32,
        "stage": torch.int8,
    }
    for name, dtype in state_dtypes.items():
        value = getattr(state, name)
        if tuple(value.shape) != shape:
            raise ValueError(f"{name} must have shape [batch, entities]")
        if value.device != state.device:
            raise ValueError(f"{name} is on a different device")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")

    parameter_dtypes = {
        "enabled": torch.bool,
        "stage_1_ticks": torch.int32,
        "stage_2_ticks": torch.int32,
        "stage_0_damage_multiplier": torch.float32,
        "stage_1_damage_multiplier": torch.float32,
        "stage_2_damage_multiplier": torch.float32,
        "retarget_grace_ticks": torch.int32,
    }
    for name, dtype in parameter_dtypes.items():
        value = getattr(parameters, name)
        if tuple(value.shape) != shape:
            raise ValueError(f"{name} must have shape [batch, entities]")
        if value.device != state.device:
            raise ValueError(f"{name} is on a different device")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")
    return shape


def pre_attack_damage_ramp_(
    state: FastDamageRampState,
    parameters: FastDamageRampParameters,
    *,
    current_target_stable_id: torch.Tensor,
    stunned: torch.Tensor,
) -> FastDamageRampStepResult:
    """Advance connected channels and return their pre-attack multipliers.

    The acquisition tick counts as the first connected tick.  A target change
    starts a fresh channel at tick one; loss or stun clears it to tick zero.
    Disabled slots remain cleared and return an ordinary multiplier of one.
    Stage thresholds are numeric and inclusive, so thresholds 40 and 80 enter
    stages one and two exactly on connected ticks 40 and 80.
    """

    shape = _validate_damage_ramp(state, parameters)
    for name, value, dtype in (
        ("current_target_stable_id", current_target_stable_id, torch.int64),
        ("stunned", stunned, torch.bool),
    ):
        if tuple(value.shape) != shape:
            raise ValueError(f"{name} must have shape [batch, entities]")
        if value.device != state.device:
            raise ValueError(f"{name} is on a different device")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")

    enabled = parameters.enabled
    target = current_target_stable_id.clamp(min=0)
    previous_target = state.observed_target_stable_id
    target_present = target > 0
    connected = enabled & target_present & ~stunned
    same_target = connected & (target == previous_target) & (previous_target > 0)
    target_changed = (
        enabled
        & target_present
        & (previous_target > 0)
        & (target != previous_target)
    )
    target_lost = enabled & ~target_present & (previous_target > 0)
    reset = enabled & (stunned | target_lost | target_changed)

    next_ticks = torch.where(
        same_target,
        state.connected_ticks.clamp(min=0) + 1,
        torch.where(connected, torch.ones_like(state.connected_ticks), 0),
    )
    # Invalid or unordered serialized thresholds degrade to monotonic numeric
    # thresholds instead of creating a card-specific exception path.
    stage_1_ticks = parameters.stage_1_ticks.clamp(min=0)
    stage_2_ticks = torch.maximum(
        parameters.stage_2_ticks.clamp(min=0), stage_1_ticks
    )
    next_stage = torch.where(
        connected & (next_ticks >= stage_2_ticks),
        torch.full_like(state.stage, 2),
        torch.where(
            connected & (next_ticks >= stage_1_ticks),
            torch.full_like(state.stage, 1),
            torch.zeros_like(state.stage),
        ),
    )
    next_target = torch.where(connected, target, torch.zeros_like(target))

    state.observed_target_stable_id.copy_(next_target)
    state.connected_ticks.copy_(next_ticks)
    state.stage.copy_(next_stage)

    one = torch.ones_like(parameters.stage_0_damage_multiplier)
    ramp_multiplier = torch.where(
        next_stage == 2,
        parameters.stage_2_damage_multiplier.clamp(min=0.0),
        torch.where(
            next_stage == 1,
            parameters.stage_1_damage_multiplier.clamp(min=0.0),
            parameters.stage_0_damage_multiplier.clamp(min=0.0),
        ),
    )
    damage_multiplier = torch.where(enabled, ramp_multiplier, one)
    retargeted = (target_changed | target_lost) & ~stunned
    retarget_delay_ticks = torch.where(
        retargeted,
        parameters.retarget_grace_ticks.clamp(min=0),
        torch.zeros_like(parameters.retarget_grace_ticks),
    )
    return FastDamageRampStepResult(
        damage_multiplier=damage_multiplier,
        observed_target_stable_id=state.observed_target_stable_id,
        connected_ticks=state.connected_ticks,
        stage=state.stage,
        connected=connected,
        reset=reset,
        target_changed=target_changed,
        retarget_delay_ticks=retarget_delay_ticks,
    )


# Readable alias for callers that use the generic "advance" naming convention.
advance_fast_damage_ramp_ = pre_attack_damage_ramp_
