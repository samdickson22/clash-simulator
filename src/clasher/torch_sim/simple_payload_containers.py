"""Fixed-shape delayed payload containers for the practical tensor Gym.

Bombs and falling containers are battle objects, not targetable combatants.
They therefore live in a small dedicated pool rather than occupying an entity
slot.  Setup/runtime code supplies only numeric descriptors; the hot path has
no card-name dispatch, host synchronization, or dynamic event compaction.

Each expiring object can emit an area-effect command, a nested spawn trigger,
or both.  Output slots are ordered by object ``stable_id`` (with physical slot
as the deterministic tie breaker), independently of pool-slot reuse.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import torch

from .simple_effects import FAST_EFFECT_AREA, FastEffectState
from .simple_state import FastGymState


@dataclass
class FastPayloadContainerState:
    """Mutable structure-of-arrays pool with shape ``[batch, containers]``."""

    device: torch.device
    active: torch.Tensor
    stable_id: torch.Tensor
    source_id: torch.Tensor
    owner: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    lifetime_ticks: torch.Tensor
    effect_card_id: torch.Tensor
    effect_damage: torch.Tensor
    effect_radius_units: torch.Tensor
    effect_status_kind: torch.Tensor
    effect_status_duration_ticks: torch.Tensor
    tower_damage_multiplier: torch.Tensor
    building_damage_multiplier: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor
    nested_spawn_blueprint_id: torch.Tensor
    next_stable_id: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.active.shape[0])

    @property
    def max_containers(self) -> int:
        return int(self.active.shape[1])

    @classmethod
    def empty(
        cls,
        batch_size: int,
        *,
        max_containers: int = 32,
        device: str | torch.device = "cpu",
    ) -> FastPayloadContainerState:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if max_containers < 1:
            raise ValueError("max_containers must be positive")
        tensor_device = torch.device(device)
        if tensor_device.type == "cuda" and tensor_device.index is None:
            tensor_device = torch.device("cuda", torch.cuda.current_device())
        shape = (batch_size, max_containers)

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(shape, dtype=dtype, device=tensor_device)

        return cls(
            device=tensor_device,
            active=zeros(torch.bool),
            stable_id=zeros(torch.int64),
            source_id=zeros(torch.int64),
            owner=zeros(torch.int8),
            x_units=zeros(torch.int32),
            y_units=zeros(torch.int32),
            lifetime_ticks=zeros(torch.int32),
            effect_card_id=zeros(torch.int64),
            effect_damage=zeros(torch.float32),
            effect_radius_units=zeros(torch.int32),
            effect_status_kind=zeros(torch.int8),
            effect_status_duration_ticks=zeros(torch.int32),
            tower_damage_multiplier=torch.ones(
                shape, dtype=torch.float32, device=tensor_device
            ),
            building_damage_multiplier=torch.ones(
                shape, dtype=torch.float32, device=tensor_device
            ),
            hits_air=torch.ones(shape, dtype=torch.bool, device=tensor_device),
            hits_ground=torch.ones(shape, dtype=torch.bool, device=tensor_device),
            nested_spawn_blueprint_id=zeros(torch.int64),
            next_stable_id=torch.ones(
                batch_size, dtype=torch.int64, device=tensor_device
            ),
        )

    def clone(self) -> FastPayloadContainerState:
        values: dict[str, object] = {"device": self.device}
        for descriptor in fields(self):
            if descriptor.name != "device":
                values[descriptor.name] = getattr(self, descriptor.name).clone()
        return type(self)(**values)  # type: ignore[arg-type]


@dataclass(frozen=True)
class FastPayloadContainerCommands:
    """Numeric requests to allocate delayed objects, shape ``[batch, commands]``."""

    ready: torch.Tensor
    source_id: torch.Tensor
    owner: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    lifetime_ticks: torch.Tensor
    effect_card_id: torch.Tensor
    effect_damage: torch.Tensor
    effect_radius_units: torch.Tensor
    effect_status_kind: torch.Tensor
    effect_status_duration_ticks: torch.Tensor
    tower_damage_multiplier: torch.Tensor
    building_damage_multiplier: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor
    nested_spawn_blueprint_id: torch.Tensor


@dataclass(frozen=True)
class FastPayloadAllocationResult:
    """Allocation outcome and explicit capacity telemetry."""

    accepted: torch.Tensor
    invalid: torch.Tensor
    capacity_rejected: torch.Tensor
    capacity_rejected_count: torch.Tensor
    allocated_mask: torch.Tensor
    source_command: torch.Tensor


@dataclass(frozen=True)
class FastPayloadEffectCommands:
    """Fixed-shape area-effect commands emitted by expiring containers."""

    ready: torch.Tensor
    payload_stable_id: torch.Tensor
    source_id: torch.Tensor
    owner: torch.Tensor
    effect_card_id: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    damage: torch.Tensor
    radius_units: torch.Tensor
    status_kind: torch.Tensor
    status_duration_ticks: torch.Tensor
    tower_damage_multiplier: torch.Tensor
    building_damage_multiplier: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor


@dataclass(frozen=True)
class FastPayloadSpawnTriggers:
    """Fixed-shape nested-blueprint triggers emitted at expiry."""

    ready: torch.Tensor
    payload_stable_id: torch.Tensor
    source_id: torch.Tensor
    owner: torch.Tensor
    blueprint_id: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor


@dataclass(frozen=True)
class FastPayloadStepResult:
    """Expiry telemetry plus fixed-capacity effect and spawn streams."""

    expired_mask: torch.Tensor
    emitted_count: torch.Tensor
    effect_commands: FastPayloadEffectCommands
    spawn_triggers: FastPayloadSpawnTriggers


@dataclass(frozen=True)
class FastPayloadEffectAllocationResult:
    """Per-command telemetry for terminal effects entering the effect pool."""

    accepted: torch.Tensor
    invalid: torch.Tensor
    capacity_rejected: torch.Tensor
    effect_slot: torch.Tensor


_COMMAND_DTYPES: tuple[tuple[str, torch.dtype], ...] = (
    ("ready", torch.bool),
    ("source_id", torch.int64),
    ("owner", torch.int8),
    ("x_units", torch.int32),
    ("y_units", torch.int32),
    ("lifetime_ticks", torch.int32),
    ("effect_card_id", torch.int64),
    ("effect_damage", torch.float32),
    ("effect_radius_units", torch.int32),
    ("effect_status_kind", torch.int8),
    ("effect_status_duration_ticks", torch.int32),
    ("tower_damage_multiplier", torch.float32),
    ("building_damage_multiplier", torch.float32),
    ("hits_air", torch.bool),
    ("hits_ground", torch.bool),
    ("nested_spawn_blueprint_id", torch.int64),
)

_STATE_DTYPES: tuple[tuple[str, torch.dtype], ...] = (
    ("active", torch.bool),
    ("stable_id", torch.int64),
    ("source_id", torch.int64),
    ("owner", torch.int8),
    ("x_units", torch.int32),
    ("y_units", torch.int32),
    ("lifetime_ticks", torch.int32),
    ("effect_card_id", torch.int64),
    ("effect_damage", torch.float32),
    ("effect_radius_units", torch.int32),
    ("effect_status_kind", torch.int8),
    ("effect_status_duration_ticks", torch.int32),
    ("tower_damage_multiplier", torch.float32),
    ("building_damage_multiplier", torch.float32),
    ("hits_air", torch.bool),
    ("hits_ground", torch.bool),
    ("nested_spawn_blueprint_id", torch.int64),
)


def _validate_state(state: FastPayloadContainerState) -> None:
    shape = tuple(state.active.shape)
    if len(shape) != 2:
        raise ValueError("payload state must have shape [batch, containers]")
    for descriptor in fields(state):
        if descriptor.name in {"device", "next_stable_id"}:
            continue
        value = getattr(state, descriptor.name)
        if tuple(value.shape) != shape:
            raise ValueError(f"{descriptor.name} must have shape [batch, containers]")
        if value.device != state.device:
            raise ValueError(f"{descriptor.name} must use the payload device")
    for name, dtype in _STATE_DTYPES:
        if getattr(state, name).dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")
    if tuple(state.next_stable_id.shape) != (shape[0],):
        raise ValueError("next_stable_id must have shape [batch]")
    if state.next_stable_id.device != state.device:
        raise ValueError("next_stable_id must use the payload device")
    if state.next_stable_id.dtype != torch.int64:
        raise ValueError("next_stable_id must use torch.int64")


def _validate_commands(
    state: FastPayloadContainerState,
    commands: FastPayloadContainerCommands,
) -> tuple[int, int]:
    shape = tuple(commands.ready.shape)
    if len(shape) != 2 or shape[0] != state.batch_size:
        raise ValueError("payload commands must have shape [batch, commands]")
    for name, dtype in _COMMAND_DTYPES:
        value = getattr(commands, name)
        if tuple(value.shape) != shape:
            raise ValueError(f"{name} must match the command shape")
        if value.device != state.device:
            raise ValueError(f"{name} must use the payload device")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")
    return shape


def _clear_slots_(state: FastPayloadContainerState, mask: torch.Tensor) -> None:
    """Clear every slot-owned field while retaining the batch ID counter."""

    zero_fields = (
        "active",
        "stable_id",
        "source_id",
        "owner",
        "x_units",
        "y_units",
        "lifetime_ticks",
        "effect_card_id",
        "effect_damage",
        "effect_radius_units",
        "effect_status_kind",
        "effect_status_duration_ticks",
        "nested_spawn_blueprint_id",
    )
    for name in zero_fields:
        getattr(state, name).masked_fill_(mask, 0)
    state.tower_damage_multiplier.masked_fill_(mask, 1.0)
    state.building_damage_multiplier.masked_fill_(mask, 1.0)
    state.hits_air.masked_fill_(mask, True)
    state.hits_ground.masked_fill_(mask, True)


def allocate_fast_payload_containers_(
    state: FastPayloadContainerState,
    commands: FastPayloadContainerCommands,
) -> FastPayloadAllocationResult:
    """Allocate one pool slot per valid request in command order.

    Capacity is intentionally non-evicting.  Earlier command slots win, every
    rejected live request is surfaced, and accepted objects receive monotonic
    per-battle IDs.  Reused physical slots are completely overwritten.
    """

    _validate_state(state)
    _validate_commands(state, commands)
    stale = ~state.active
    _clear_slots_(state, stale)

    has_payload = (
        (commands.effect_damage != 0)
        | (commands.effect_status_kind != 0)
        | (commands.nested_spawn_blueprint_id > 0)
    )
    valid = (
        commands.ready
        & (commands.source_id >= 0)
        & (commands.owner >= 0)
        & (commands.owner < 2)
        & (commands.lifetime_ticks > 0)
        & (commands.effect_card_id >= 0)
        & torch.isfinite(commands.effect_damage)
        & (commands.effect_radius_units >= 0)
        & (commands.effect_status_kind >= 0)
        & (commands.effect_status_duration_ticks >= 0)
        & torch.isfinite(commands.tower_damage_multiplier)
        & (commands.tower_damage_multiplier >= 0)
        & torch.isfinite(commands.building_damage_multiplier)
        & (commands.building_damage_multiplier >= 0)
        & (commands.nested_spawn_blueprint_id >= 0)
        & has_payload
    )
    command_rank = valid.to(torch.int64).cumsum(dim=1) - 1
    free = ~state.active
    free_rank = free.to(torch.int64).cumsum(dim=1) - 1
    free_count = free.sum(dim=1, dtype=torch.int64)
    accepted = valid & (command_rank < free_count[:, None])
    accepted_count = accepted.sum(dim=1, dtype=torch.int64)
    allocated = free & (free_rank >= 0) & (free_rank < accepted_count[:, None])

    # Accepted requests form a dense prefix in valid-command rank, so the
    # matching command can be selected with a fixed comparison tensor.
    claims = (
        allocated[:, :, None]
        & accepted[:, None, :]
        & (free_rank[:, :, None] == command_rank[:, None, :])
    )
    source_command = claims.to(torch.int64).argmax(dim=2)

    def gather(value: torch.Tensor) -> torch.Tensor:
        return value.gather(1, source_command)

    def write(field: torch.Tensor, value: torch.Tensor) -> None:
        field.copy_(torch.where(allocated, value.to(field.dtype), field))

    write(state.active, torch.ones_like(allocated))
    write(state.stable_id, state.next_stable_id[:, None] + free_rank)
    for name, _dtype in _COMMAND_DTYPES:
        if name == "ready":
            continue
        write(getattr(state, name), gather(getattr(commands, name)))
    state.next_stable_id.add_(accepted_count)

    capacity_rejected = valid & ~accepted
    return FastPayloadAllocationResult(
        accepted=accepted,
        invalid=commands.ready & ~valid,
        capacity_rejected=capacity_rejected,
        capacity_rejected_count=capacity_rejected.sum(dim=1, dtype=torch.int32),
        allocated_mask=allocated,
        source_command=torch.where(allocated, source_command, -1),
    )


def step_fast_payload_containers_(
    state: FastPayloadContainerState,
) -> FastPayloadStepResult:
    """Advance timers, emit stable-ordered terminal commands, and clear slots."""

    _validate_state(state)
    _batch, capacity = state.active.shape
    stale = ~state.active
    _clear_slots_(state, stale)

    state.lifetime_ticks.sub_(state.active.to(torch.int32))
    expired = state.active & (state.lifetime_ticks <= 0)
    emitted_count = expired.sum(dim=1, dtype=torch.int32)

    # Compute each expiring object's order without a dynamic-length index.
    stable_id = state.stable_id
    slots = torch.arange(capacity, dtype=torch.int64, device=state.device)
    id_i = stable_id[:, :, None]
    id_j = stable_id[:, None, :]
    slot_i = slots.view(1, capacity, 1)
    slot_j = slots.view(1, 1, capacity)
    predecessor = expired[:, None, :] & (
        (id_j < id_i) | ((id_j == id_i) & (slot_j < slot_i))
    )
    rank = predecessor.sum(dim=2, dtype=torch.int64)
    output_slot = slots.view(1, capacity)
    emitted = output_slot < emitted_count[:, None]
    claims = (
        emitted[:, :, None]
        & expired[:, None, :]
        & (output_slot[:, :, None] == rank[:, None, :])
    )
    source_slot = claims.to(torch.int64).argmax(dim=2)

    def ordered(value: torch.Tensor) -> torch.Tensor:
        gathered = value.gather(1, source_slot)
        return torch.where(emitted, gathered, torch.zeros_like(gathered))

    payload_stable_id = ordered(state.stable_id)
    source_id = ordered(state.source_id)
    owner = ordered(state.owner)
    x_units = ordered(state.x_units)
    y_units = ordered(state.y_units)
    effect_damage = ordered(state.effect_damage)
    effect_status_kind = ordered(state.effect_status_kind)
    effect_ready = emitted & ((effect_damage != 0) | (effect_status_kind != 0))
    nested_blueprint = ordered(state.nested_spawn_blueprint_id)
    spawn_ready = emitted & (nested_blueprint > 0)

    effect_commands = FastPayloadEffectCommands(
        ready=effect_ready,
        payload_stable_id=payload_stable_id,
        source_id=source_id,
        owner=owner,
        effect_card_id=ordered(state.effect_card_id),
        x_units=x_units,
        y_units=y_units,
        damage=effect_damage,
        radius_units=ordered(state.effect_radius_units),
        status_kind=effect_status_kind,
        status_duration_ticks=ordered(state.effect_status_duration_ticks),
        tower_damage_multiplier=ordered(state.tower_damage_multiplier),
        building_damage_multiplier=ordered(state.building_damage_multiplier),
        hits_air=ordered(state.hits_air),
        hits_ground=ordered(state.hits_ground),
    )
    spawn_triggers = FastPayloadSpawnTriggers(
        ready=spawn_ready,
        payload_stable_id=payload_stable_id,
        source_id=source_id,
        owner=owner,
        blueprint_id=nested_blueprint,
        x_units=x_units,
        y_units=y_units,
    )
    _clear_slots_(state, expired)
    return FastPayloadStepResult(
        expired_mask=expired,
        emitted_count=emitted_count,
        effect_commands=effect_commands,
        spawn_triggers=spawn_triggers,
    )


def allocate_fast_payload_effects_(
    state: FastGymState,
    effects: FastEffectState,
    consume_source_id: torch.Tensor,
    commands: FastPayloadEffectCommands,
) -> FastPayloadEffectAllocationResult:
    """Allocate terminal payloads as ordinary one-tick area effects.

    Payload damage is already scaled at catalog compilation time, so this
    allocator writes the numeric command directly instead of looking up the
    producing card's ordinary attack.  HP mutation remains exclusively owned
    by :func:`simple_effects.step_fast_effects`.
    """

    shape = tuple(commands.ready.shape)
    if len(shape) != 2 or shape[0] != state.batch_size:
        raise ValueError("payload effect commands must have shape [batch, commands]")
    if effects.device != state.device or effects.batch_size != state.batch_size:
        raise ValueError("state and effects must share batch size and device")
    command_dtypes = (
        ("ready", torch.bool),
        ("payload_stable_id", torch.int64),
        ("source_id", torch.int64),
        ("owner", torch.int8),
        ("effect_card_id", torch.int64),
        ("x_units", torch.int32),
        ("y_units", torch.int32),
        ("damage", torch.float32),
        ("radius_units", torch.int32),
        ("status_kind", torch.int8),
        ("status_duration_ticks", torch.int32),
        ("tower_damage_multiplier", torch.float32),
        ("building_damage_multiplier", torch.float32),
        ("hits_air", torch.bool),
        ("hits_ground", torch.bool),
    )
    for name, dtype in command_dtypes:
        value = getattr(commands, name)
        if tuple(value.shape) != shape or value.device != state.device:
            raise ValueError(f"{name} must match command shape and device")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")
    pool_shape = (state.batch_size, effects.max_effects)
    if tuple(consume_source_id.shape) != pool_shape:
        raise ValueError("consume_source_id must have shape [batch, effects]")
    if (
        consume_source_id.device != state.device
        or consume_source_id.dtype != torch.int64
    ):
        raise ValueError("consume_source_id must be int64 on the state device")

    valid = (
        commands.ready
        & (commands.payload_stable_id > 0)
        & (commands.source_id >= 0)
        & (commands.owner >= 0)
        & (commands.owner < 2)
        & (commands.effect_card_id >= 0)
        & torch.isfinite(commands.damage)
        & (commands.damage >= 0)
        & (commands.radius_units >= 0)
        & (commands.status_kind >= 0)
        & (commands.status_duration_ticks >= 0)
        & torch.isfinite(commands.tower_damage_multiplier)
        & (commands.tower_damage_multiplier >= 0)
        & torch.isfinite(commands.building_damage_multiplier)
        & (commands.building_damage_multiplier >= 0)
        & ((commands.damage > 0) | (commands.status_kind > 0))
        & ~state.game_over[:, None]
    )
    free = ~effects.active
    command_rank = valid.to(torch.int64).cumsum(dim=1) - 1
    free_rank = free.to(torch.int64).cumsum(dim=1) - 1
    available = free.sum(dim=1, dtype=torch.int64)
    accepted = valid & (command_rank < available[:, None])
    allocated = free & (free_rank < accepted.sum(dim=1, dtype=torch.int64)[:, None])
    claims = (
        allocated[:, :, None]
        & accepted[:, None, :]
        & (free_rank[:, :, None] == command_rank[:, None, :])
    )
    source_command = claims.to(torch.int64).argmax(dim=2)
    effect_slot = torch.where(
        accepted,
        (accepted[:, :, None] & claims.transpose(1, 2)).to(torch.int64).argmax(dim=2),
        -1,
    )

    def gather(value: torch.Tensor) -> torch.Tensor:
        return value.gather(1, source_command)

    def write(field: torch.Tensor, value: torch.Tensor) -> None:
        field.copy_(torch.where(allocated, value.to(field.dtype), field))

    zeros_i64 = torch.zeros_like(free_rank)
    zeros_i32 = torch.zeros_like(free_rank, dtype=torch.int32)
    zeros_i16 = torch.zeros_like(free_rank, dtype=torch.int16)
    zeros_f32 = torch.zeros_like(free_rank, dtype=torch.float32)
    ones_i32 = torch.ones_like(free_rank, dtype=torch.int32)
    ones_i16 = torch.ones_like(free_rank, dtype=torch.int16)
    write(effects.active, torch.ones_like(allocated))
    write(effects.kind, torch.full_like(free_rank, FAST_EFFECT_AREA))
    write(effects.source_owner, gather(commands.owner))
    write(effects.source_card_id, gather(commands.effect_card_id))
    write(effects.source_x_units, gather(commands.x_units))
    write(effects.source_y_units, gather(commands.y_units))
    write(effects.x_units, gather(commands.x_units))
    write(effects.y_units, gather(commands.y_units))
    write(effects.target_id, zeros_i64)
    write(effects.target_x_units, gather(commands.x_units))
    write(effects.target_y_units, gather(commands.y_units))
    write(effects.tracks_target, torch.zeros_like(allocated))
    write(effects.speed_units_per_tick, zeros_i32)
    write(effects.damage, gather(commands.damage))
    write(effects.tower_damage_multiplier, gather(commands.tower_damage_multiplier))
    write(
        effects.building_damage_multiplier,
        gather(commands.building_damage_multiplier),
    )
    write(effects.radius_units, gather(commands.radius_units))
    write(effects.status_kind, gather(commands.status_kind))
    write(effects.status_duration_ticks, gather(commands.status_duration_ticks))
    write(effects.lifetime_ticks, ones_i32)
    write(effects.damage_interval_ticks, ones_i32)
    write(effects.next_damage_tick, zeros_i32)
    write(effects.damage_on_spawn, torch.ones_like(allocated))
    write(effects.damage_hits_remaining, ones_i32)
    write(effects.status_interval_ticks, ones_i32)
    write(effects.next_status_tick, zeros_i32)
    write(
        effects.status_scans_remaining,
        (gather(commands.status_kind) > 0).to(torch.int32),
    )
    write(effects.hits_air, gather(commands.hits_air))
    write(effects.hits_ground, gather(commands.hits_ground))
    write(effects.multi_target_count, ones_i16)
    write(effects.multi_target_range_units, zeros_i32)
    write(effects.multi_repeat_primary, torch.zeros_like(allocated))
    write(effects.chain_target_count, zeros_i16)
    write(effects.chain_hop_radius_units, zeros_i32)
    write(effects.line_range_units, zeros_i32)
    write(effects.line_half_width_units, zeros_i32)
    write(effects.fan_ray_count, zeros_i16)
    write(effects.fan_range_units, zeros_i32)
    write(effects.fan_radius_units, zeros_i32)
    write(effects.fan_spread_degrees, zeros_f32)
    write(consume_source_id, zeros_i64)
    return FastPayloadEffectAllocationResult(
        accepted=accepted,
        invalid=commands.ready & ~valid,
        capacity_rejected=valid & ~accepted,
        effect_slot=effect_slot,
    )


# Punctuation-free aliases are convenient for consumers and compiled graphs.
allocate_fast_payload_containers = allocate_fast_payload_containers_
allocate_fast_payload_effects = allocate_fast_payload_effects_
step_fast_payload_containers = step_fast_payload_containers_


__all__ = [
    "FastPayloadAllocationResult",
    "FastPayloadContainerCommands",
    "FastPayloadContainerState",
    "FastPayloadEffectAllocationResult",
    "FastPayloadEffectCommands",
    "FastPayloadSpawnTriggers",
    "FastPayloadStepResult",
    "allocate_fast_payload_containers",
    "allocate_fast_payload_containers_",
    "allocate_fast_payload_effects",
    "allocate_fast_payload_effects_",
    "step_fast_payload_containers",
    "step_fast_payload_containers_",
]
