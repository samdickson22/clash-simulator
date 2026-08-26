"""Fixed-shape projectile and area effects for the practical tensor Gym.

The production kernel needs only one small effect pool.  Card-specific code
serializes attacks into these primitive fields; this module advances every
active effect together and mutates :class:`FastGymState` directly.  Status
storage remains caller-owned so the combat state can stay backward compatible
while the unified engine is assembled.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import torch

from .simple_state import FastGymState


FAST_EFFECT_PROJECTILE = 0
FAST_EFFECT_AREA = 1

FAST_STATUS_NONE = 0
FAST_STATUS_STUN = 1
FAST_STATUS_SLOW = 2
# Freeze stops the target in the fast Gym and is represented by the same
# primitive as a stun.  The alias keeps serialized card data descriptive.
FAST_STATUS_FREEZE = FAST_STATUS_STUN


@dataclass
class FastEffectState:
    """Mutable structure-of-arrays pool with shape ``[batch, effects]``."""

    device: torch.device
    active: torch.Tensor
    kind: torch.Tensor
    source_owner: torch.Tensor
    source_card_id: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    target_id: torch.Tensor
    speed_units_per_tick: torch.Tensor
    damage: torch.Tensor
    radius_units: torch.Tensor
    status_kind: torch.Tensor
    status_duration_ticks: torch.Tensor
    lifetime_ticks: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.active.shape[0])

    @property
    def max_effects(self) -> int:
        return int(self.active.shape[1])

    @classmethod
    def empty(
        cls,
        batch_size: int,
        *,
        max_effects: int = 64,
        device: str | torch.device = "cpu",
    ) -> FastEffectState:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if max_effects < 1:
            raise ValueError("max_effects must be positive")
        tensor_device = torch.device(device)
        if tensor_device.type == "cuda" and tensor_device.index is None:
            tensor_device = torch.device("cuda", torch.cuda.current_device())
        shape = (batch_size, max_effects)

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(shape, dtype=dtype, device=tensor_device)

        return cls(
            device=tensor_device,
            active=zeros(torch.bool),
            kind=zeros(torch.int8),
            source_owner=zeros(torch.int8),
            source_card_id=zeros(torch.int64),
            x_units=zeros(torch.int32),
            y_units=zeros(torch.int32),
            target_id=zeros(torch.int64),
            speed_units_per_tick=zeros(torch.int32),
            damage=zeros(torch.float32),
            radius_units=zeros(torch.int32),
            status_kind=zeros(torch.int8),
            status_duration_ticks=zeros(torch.int32),
            lifetime_ticks=zeros(torch.int32),
        )

    def clone(self) -> FastEffectState:
        values: dict[str, object] = {"device": self.device}
        for descriptor in fields(self):
            if descriptor.name != "device":
                values[descriptor.name] = getattr(self, descriptor.name).clone()
        return type(self)(**values)  # type: ignore[arg-type]


@dataclass(frozen=True)
class FastEffectStepResult:
    """Fixed-shape effect telemetry; no dynamic event ledger is produced."""

    impacted: torch.Tensor
    targets_hit: torch.Tensor
    sources_consumed: torch.Tensor
    cleaned: torch.Tensor


def _validate_inputs(
    state: FastGymState,
    effects: FastEffectState,
    entity_status_kind: torch.Tensor,
    entity_status_ticks: torch.Tensor,
    consume_source_id: torch.Tensor | None,
) -> None:
    if effects.device != state.device:
        raise ValueError("effects and state must use the same device")
    if effects.batch_size != state.batch_size:
        raise ValueError("effects and state must use the same batch size")
    entity_shape = (state.batch_size, state.max_entities)
    if entity_status_kind.shape != entity_shape:
        raise ValueError("entity_status_kind must have shape [batch, entities]")
    if entity_status_ticks.shape != entity_shape:
        raise ValueError("entity_status_ticks must have shape [batch, entities]")
    if entity_status_kind.device != state.device:
        raise ValueError("entity_status_kind is on a different device")
    if entity_status_ticks.device != state.device:
        raise ValueError("entity_status_ticks is on a different device")
    if entity_status_kind.dtype != torch.int8:
        raise ValueError("entity_status_kind must be int8")
    if entity_status_ticks.dtype != torch.int32:
        raise ValueError("entity_status_ticks must be int32")
    effect_shape = (state.batch_size, effects.max_effects)
    for descriptor in fields(effects):
        if descriptor.name == "device":
            continue
        value = getattr(effects, descriptor.name)
        if value.shape != effect_shape:
            raise ValueError(f"{descriptor.name} must have shape [batch, effects]")
        if value.device != state.device:
            raise ValueError(f"{descriptor.name} is on a different device")
    if consume_source_id is not None:
        if consume_source_id.shape != effect_shape:
            raise ValueError("consume_source_id must have shape [batch, effects]")
        if consume_source_id.device != state.device:
            raise ValueError("consume_source_id is on a different device")
        if consume_source_id.dtype != torch.int64:
            raise ValueError("consume_source_id must be int64")


def step_fast_effects(
    state: FastGymState,
    effects: FastEffectState,
    entity_status_kind: torch.Tensor,
    entity_status_ticks: torch.Tensor,
    *,
    consume_source_id: torch.Tensor | None = None,
) -> FastEffectStepResult:
    """Advance homing effects, resolve splash, install statuses, and clean up.

    ``consume_source_id`` is an optional ``[B, P]`` stable-ID tensor.  A
    nonzero ID removes that source entity when its effect impacts, which covers
    leap-and-burst units such as Ice Spirit without guessing from owner/card.

    Simultaneous AOE damage is grouped before HP mutation.  Stun/freeze has
    precedence over slow when effects overlap; durations of the same kind use
    the longest remaining tick count.  Existing status timers advance before
    newly impacted statuses are installed.
    """

    _validate_inputs(
        state,
        effects,
        entity_status_kind,
        entity_status_ticks,
        consume_source_id,
    )
    batch, max_effects = effects.active.shape
    max_entities = state.max_entities

    status_running = entity_status_ticks > 0
    entity_status_ticks.sub_(status_running.to(torch.int32)).clamp_(min=0)
    entity_status_kind.masked_fill_(entity_status_ticks == 0, FAST_STATUS_NONE)

    alive = effects.active & (effects.lifetime_ticks > 0)
    valid_projectile = alive & (effects.kind == FAST_EFFECT_PROJECTILE)
    valid_area = alive & (effects.kind == FAST_EFFECT_AREA)
    target_match = (
        valid_projectile[:, :, None]
        & state.active[:, None, :]
        & (state.hp[:, None, :] > 0)
        & (effects.target_id[:, :, None] > 0)
        & (effects.target_id[:, :, None] == state.stable_id[:, None, :])
    )
    target_found = target_match.any(dim=2)
    target_slot = target_match.to(torch.int8).argmax(dim=2).to(torch.int64)
    target_x = state.x_units.gather(1, target_slot)
    target_y = state.y_units.gather(1, target_slot)

    delta_x = target_x.to(torch.float32) - effects.x_units.to(torch.float32)
    delta_y = target_y.to(torch.float32) - effects.y_units.to(torch.float32)
    distance = torch.sqrt(delta_x.square() + delta_y.square())
    speed = effects.speed_units_per_tick.to(torch.float32).clamp(min=0.0)
    projectile_impact = valid_projectile & target_found & (distance <= speed)
    travel = torch.minimum(speed, distance)
    moving = valid_projectile & target_found & ~projectile_impact & (travel > 0)
    denominator = distance.clamp(min=1.0)
    move_x = torch.round(delta_x * travel / denominator).to(torch.int32)
    move_y = torch.round(delta_y * travel / denominator).to(torch.int32)
    effects.x_units.add_(torch.where(moving, move_x, 0))
    effects.y_units.add_(torch.where(moving, move_y, 0))
    effects.x_units.copy_(
        torch.where(projectile_impact, target_x, effects.x_units)
    )
    effects.y_units.copy_(
        torch.where(projectile_impact, target_y, effects.y_units)
    )

    impacted = projectile_impact | valid_area
    dx = state.x_units[:, None, :].to(torch.int64) - effects.x_units[
        :, :, None
    ].to(torch.int64)
    dy = state.y_units[:, None, :].to(torch.int64) - effects.y_units[
        :, :, None
    ].to(torch.int64)
    radius_sq = effects.radius_units.to(torch.int64).clamp(min=0).square()
    targets_hit = (
        impacted[:, :, None]
        & state.active[:, None, :]
        & (state.hp[:, None, :] > 0)
        & (state.owner[:, None, :] != effects.source_owner[:, :, None])
        & (dx.square() + dy.square() <= radius_sq[:, :, None])
    )
    grouped_damage = (
        targets_hit.to(torch.float32) * effects.damage.clamp(min=0.0)[:, :, None]
    ).sum(dim=1)
    state.hp.sub_(grouped_damage).clamp_(min=0.0)

    duration = effects.status_duration_ticks.clamp(min=0)[:, :, None]
    stun_duration = torch.where(
        targets_hit
        & (effects.status_kind[:, :, None] == FAST_STATUS_STUN),
        duration,
        0,
    ).amax(dim=1)
    slow_duration = torch.where(
        targets_hit
        & (effects.status_kind[:, :, None] == FAST_STATUS_SLOW),
        duration,
        0,
    ).amax(dim=1)
    incoming_stun = stun_duration > 0
    incoming_slow = (slow_duration > 0) & ~incoming_stun
    same_stun = entity_status_kind == FAST_STATUS_STUN
    same_slow = entity_status_kind == FAST_STATUS_SLOW
    entity_status_ticks.copy_(
        torch.where(
            incoming_stun,
            torch.maximum(
                stun_duration,
                torch.where(same_stun, entity_status_ticks, 0),
            ),
            torch.where(
                incoming_slow,
                torch.maximum(
                    slow_duration,
                    torch.where(same_slow, entity_status_ticks, 0),
                ),
                entity_status_ticks,
            ),
        )
    )
    entity_status_kind.copy_(
        torch.where(
            incoming_stun,
            FAST_STATUS_STUN,
            torch.where(incoming_slow, FAST_STATUS_SLOW, entity_status_kind),
        ).to(torch.int8)
    )

    if consume_source_id is None:
        consume_source_id = torch.zeros(
            (batch, max_effects), dtype=torch.int64, device=state.device
        )
    consume_match = (
        impacted[:, :, None]
        & (consume_source_id[:, :, None] > 0)
        & state.active[:, None, :]
        & (consume_source_id[:, :, None] == state.stable_id[:, None, :])
    )
    sources_consumed = consume_match.any(dim=1)
    state.hp.masked_fill_(sources_consumed, 0.0)

    died = state.active & (state.hp <= 0)
    state.active.logical_and_(~died)
    state.stable_id.masked_fill_(died, 0)
    state.target_id.masked_fill_(died, 0)
    entity_status_kind.masked_fill_(died, FAST_STATUS_NONE)
    entity_status_ticks.masked_fill_(died, 0)

    ticking = alive & ~impacted
    effects.lifetime_ticks.sub_(ticking.to(torch.int32)).clamp_(min=0)
    missing_target = valid_projectile & ~target_found
    invalid_kind = alive & ~(valid_projectile | valid_area)
    cleaned = (
        effects.active
        & (
            impacted
            | missing_target
            | invalid_kind
            | (effects.lifetime_ticks <= 0)
        )
    )
    effects.active.logical_and_(~cleaned)
    effects.target_id.masked_fill_(cleaned, 0)
    effects.status_kind.masked_fill_(cleaned, FAST_STATUS_NONE)
    effects.status_duration_ticks.masked_fill_(cleaned, 0)
    effects.lifetime_ticks.masked_fill_(cleaned, 0)

    return FastEffectStepResult(
        impacted=impacted,
        targets_hit=targets_hit,
        sources_consumed=sources_consumed,
        cleaned=cleaned,
    )
