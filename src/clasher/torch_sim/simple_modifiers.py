"""Dense shield and charge primitives for the practical tensor Gym.

The fast Gym keeps mechanics numeric and data-driven.  This module therefore
contains no card dispatch, target acquisition, ownership, or event recording:
callers pass fixed-shape parameter planes and compose the returned values into
movement and combat.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import torch
from torch.nn import functional


@dataclass
class FastModifierState:
    """Mutable modifier planes with shape ``[batch, entities]``."""

    device: torch.device
    shield: torch.Tensor
    max_shield: torch.Tensor
    charge_progress_ticks: torch.Tensor
    charge_progress_distance_units: torch.Tensor
    charge_ready: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.shield.shape[0])

    @property
    def max_entities(self) -> int:
        return int(self.shield.shape[1])

    @classmethod
    def empty(
        cls,
        batch_size: int,
        *,
        max_entities: int = 64,
        device: str | torch.device = "cpu",
    ) -> FastModifierState:
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
            shield=torch.zeros(shape, dtype=torch.float32, device=tensor_device),
            max_shield=torch.zeros(shape, dtype=torch.float32, device=tensor_device),
            charge_progress_ticks=torch.zeros(
                shape, dtype=torch.int32, device=tensor_device
            ),
            charge_progress_distance_units=torch.zeros(
                shape, dtype=torch.int32, device=tensor_device
            ),
            charge_ready=torch.zeros(shape, dtype=torch.bool, device=tensor_device),
        )

    def clone(self) -> FastModifierState:
        values: dict[str, object] = {"device": self.device}
        for descriptor in fields(self):
            if descriptor.name != "device":
                values[descriptor.name] = getattr(self, descriptor.name).clone()
        return type(self)(**values)  # type: ignore[arg-type]


@dataclass(frozen=True)
class FastChargeParameters:
    """Per-entity numeric charge configuration with shape ``[B, E]``.

    A zero threshold disables that threshold lane.  When both lanes are
    positive, both must be reached.  An enabled entity with two zero thresholds
    never becomes ready, which keeps incomplete serialized data fail-closed.
    """

    enabled: torch.Tensor
    threshold_ticks: torch.Tensor
    threshold_distance_units: torch.Tensor
    ready_speed_multiplier: torch.Tensor
    ready_damage_multiplier: torch.Tensor


@dataclass(frozen=True)
class FastChargeMultipliers:
    """Pre-move charge view consumed by movement and attack calculation."""

    ready: torch.Tensor
    speed: torch.Tensor
    damage: torch.Tensor


@dataclass(frozen=True)
class FastChargeStepResult:
    """Post-move charge telemetry retained entirely on the tensor device."""

    progressed: torch.Tensor
    became_ready: torch.Tensor
    reset: torch.Tensor


@dataclass(frozen=True)
class FastShieldInterceptionResult:
    """Ordered hit decisions and grouped damage remaining for entity HP."""

    absorbed: torch.Tensor
    broken: torch.Tensor
    hp_damage: torch.Tensor
    shield_damage: torch.Tensor


def _validate_modifier_state(state: FastModifierState) -> tuple[int, int]:
    shape = tuple(state.shield.shape)
    if len(shape) != 2:
        raise ValueError("modifier tensors must have shape [batch, entities]")
    expected_dtypes = {
        "shield": torch.float32,
        "max_shield": torch.float32,
        "charge_progress_ticks": torch.int32,
        "charge_progress_distance_units": torch.int32,
        "charge_ready": torch.bool,
    }
    for name, dtype in expected_dtypes.items():
        value = getattr(state, name)
        if tuple(value.shape) != shape:
            raise ValueError(f"{name} must have shape [batch, entities]")
        if value.device != state.device:
            raise ValueError(f"{name} is on a different device")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")
    return shape


def _validate_charge_parameters(
    state: FastModifierState,
    parameters: FastChargeParameters,
) -> tuple[int, int]:
    shape = _validate_modifier_state(state)
    expected_dtypes = {
        "enabled": torch.bool,
        "threshold_ticks": torch.int32,
        "threshold_distance_units": torch.int32,
        "ready_speed_multiplier": torch.float32,
        "ready_damage_multiplier": torch.float32,
    }
    for name, dtype in expected_dtypes.items():
        value = getattr(parameters, name)
        if tuple(value.shape) != shape:
            raise ValueError(f"{name} must have shape [batch, entities]")
        if value.device != state.device:
            raise ValueError(f"{name} is on a different device")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")
    return shape


def pre_move_charge_multipliers(
    state: FastModifierState,
    parameters: FastChargeParameters,
) -> FastChargeMultipliers:
    """Return effective pre-move speed and damage multiplier planes.

    Multipliers are clamped at zero so malformed serialized values cannot
    reverse movement or heal through negative attack damage.
    """

    _validate_charge_parameters(state, parameters)
    ready = parameters.enabled & state.charge_ready
    one = torch.ones_like(parameters.ready_speed_multiplier)
    speed = torch.where(
        ready,
        parameters.ready_speed_multiplier.clamp(min=0.0),
        one,
    )
    damage = torch.where(
        ready,
        parameters.ready_damage_multiplier.clamp(min=0.0),
        one,
    )
    return FastChargeMultipliers(ready=ready, speed=speed, damage=damage)


def advance_fast_charge_(
    state: FastModifierState,
    parameters: FastChargeParameters,
    *,
    active: torch.Tensor,
    moved_distance_units: torch.Tensor,
    attacked: torch.Tensor,
) -> FastChargeStepResult:
    """Advance continuous movement progress, then reset entities that attacked.

    A movement tick is counted only when its nonnegative travelled distance is
    positive.  Crossing a configured threshold updates ``charge_ready`` for the
    next pre-move view.  Every attack by a charge-enabled entity resets both
    progress lanes, matching the simple reusable charge lifecycle rather than
    encoding a particular card's attack path.
    """

    shape = _validate_charge_parameters(state, parameters)
    for name, value, dtype in (
        ("active", active, torch.bool),
        ("moved_distance_units", moved_distance_units, torch.int32),
        ("attacked", attacked, torch.bool),
    ):
        if tuple(value.shape) != shape:
            raise ValueError(f"{name} must have shape [batch, entities]")
        if value.device != state.device:
            raise ValueError(f"{name} is on a different device")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")

    enabled = active & parameters.enabled
    distance = moved_distance_units.clamp(min=0)
    progressed = enabled & (distance > 0) & ~attacked
    reset = parameters.enabled & attacked

    next_ticks = state.charge_progress_ticks + progressed.to(torch.int32)
    next_distance = state.charge_progress_distance_units + torch.where(
        progressed,
        distance,
        0,
    )
    tick_configured = parameters.threshold_ticks > 0
    distance_configured = parameters.threshold_distance_units > 0
    configured = tick_configured | distance_configured
    tick_ready = ~tick_configured | (
        next_ticks >= parameters.threshold_ticks.clamp(min=0)
    )
    distance_ready = ~distance_configured | (
        next_distance >= parameters.threshold_distance_units.clamp(min=0)
    )
    next_ready = enabled & configured & tick_ready & distance_ready
    became_ready = next_ready & ~state.charge_ready & ~reset

    state.charge_progress_ticks.copy_(torch.where(reset, 0, next_ticks))
    state.charge_progress_distance_units.copy_(torch.where(reset, 0, next_distance))
    state.charge_ready.copy_(torch.where(reset, False, next_ready))
    return FastChargeStepResult(
        progressed=progressed,
        became_ready=became_ready,
        reset=reset,
    )


def intercept_fast_shield_hits_(
    state: FastModifierState,
    *,
    valid: torch.Tensor,
    target_slot: torch.Tensor,
    damage: torch.Tensor,
) -> FastShieldInterceptionResult:
    """Intercept ordered whole hits and return grouped HP damage.

    Inputs have shape ``[B, H]`` and are ordered along ``H``.  If a target has
    positive shield before a hit, that entire hit is absorbed even when its
    damage exceeds the remaining shield.  Later hits in the same call pass to
    HP after the shield breaks.  The returned ``hp_damage`` is grouped to
    ``[B, E]`` so the caller can perform one HP mutation.
    """

    batch, max_entities = _validate_modifier_state(state)
    if valid.ndim != 2 or valid.shape[0] != batch:
        raise ValueError("hit tensors must have shape [batch, hits]")
    hit_shape = tuple(valid.shape)
    for name, value, dtype in (
        ("valid", valid, torch.bool),
        ("target_slot", target_slot, torch.int64),
        ("damage", damage, torch.float32),
    ):
        if tuple(value.shape) != hit_shape:
            raise ValueError(f"{name} must have shape [batch, hits]")
        if value.device != state.device:
            raise ValueError(f"{name} is on a different device")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")

    in_bounds = (target_slot >= 0) & (target_slot < max_entities)
    accepted = valid & in_bounds & (damage > 0)
    safe_target = target_slot.clamp(0, max_entities - 1)
    target = functional.one_hot(safe_target, num_classes=max_entities).to(torch.bool)
    target &= accepted[:, :, None]
    positive_damage = damage.clamp(min=0.0)
    per_target_damage = target.to(torch.float32) * positive_damage[:, :, None]
    prior_damage = per_target_damage.cumsum(dim=1) - per_target_damage
    initial_shield = state.shield.clamp(min=0.0)
    absorbed_by_target = (
        target
        & (initial_shield[:, None, :] > 0)
        & (prior_damage < initial_shield[:, None, :])
    )
    absorbed = absorbed_by_target.any(dim=2)
    shield_damage = (
        absorbed_by_target.to(torch.float32) * positive_damage[:, :, None]
    ).sum(dim=1)
    previous_shield = initial_shield
    next_shield = (previous_shield - shield_damage).clamp(min=0.0)
    state.shield.copy_(torch.minimum(next_shield, state.max_shield.clamp(min=0.0)))
    broken = (
        absorbed_by_target
        & (prior_damage + per_target_damage >= initial_shield[:, None, :])
    ).any(dim=2)
    hp_damage = (
        target.to(torch.float32)
        * torch.where(absorbed, 0.0, positive_damage)[:, :, None]
    ).sum(dim=1)
    return FastShieldInterceptionResult(
        absorbed=absorbed,
        broken=broken,
        hp_damage=hp_damage,
        shield_damage=shield_damage,
    )
