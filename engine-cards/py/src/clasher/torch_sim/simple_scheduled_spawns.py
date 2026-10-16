"""Fixed-shape delayed and repeated cast scheduling for the practical Gym.

The pool retains only numeric setup-time payloads.  Each accepted request gets
a monotonic per-battle cast ID, an absolute first deadline, and an optional
initial area payload followed by one or more spawn waves.  A step emits at
most one wave per live cast, padded to pool capacity and ordered by cast ID.

This module deliberately does not materialize effects or entities.  Its output
feeds the ordinary fixed-capacity allocators, which remain the authority for
effect/entity capacity rejection.  There is no runtime name dispatch, host
read, or dynamic event compaction.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import torch


FAST_SCHEDULED_UNLIMITED = -1
_ORDER_SENTINEL = torch.iinfo(torch.int64).max


@dataclass(frozen=True)
class FastScheduledCastCommands:
    """Numeric cast requests with shape ``[batch, commands]``."""

    ready: torch.Tensor
    owner: torch.Tensor
    source_card_id: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    first_delay_ticks: torch.Tensor
    interval_ticks: torch.Tensor
    waves: torch.Tensor
    child_card_id: torch.Tensor
    count: torch.Tensor
    radius_units: torch.Tensor
    deploy_ticks: torch.Tensor
    initial_damage: torch.Tensor
    initial_radius_units: torch.Tensor
    initial_status_kind: torch.Tensor
    initial_status_duration_ticks: torch.Tensor
    tower_damage_multiplier: torch.Tensor
    building_damage_multiplier: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor


@dataclass
class FastScheduledCastState:
    """Fixed cast pool with absolute deadlines and monotonic identities."""

    device: torch.device
    active: torch.Tensor
    stable_id: torch.Tensor
    owner: torch.Tensor
    source_card_id: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    next_tick: torch.Tensor
    interval_ticks: torch.Tensor
    waves_remaining: torch.Tensor
    child_card_id: torch.Tensor
    count: torch.Tensor
    radius_units: torch.Tensor
    deploy_ticks: torch.Tensor
    initial_effect_pending: torch.Tensor
    initial_damage: torch.Tensor
    initial_radius_units: torch.Tensor
    initial_status_kind: torch.Tensor
    initial_status_duration_ticks: torch.Tensor
    tower_damage_multiplier: torch.Tensor
    building_damage_multiplier: torch.Tensor
    hits_air: torch.Tensor
    hits_ground: torch.Tensor
    next_stable_id: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.active.shape[0])

    @property
    def capacity(self) -> int:
        return int(self.active.shape[1])

    @classmethod
    def empty(
        cls,
        batch_size: int,
        *,
        max_casts: int = 16,
        device: str | torch.device = "cpu",
    ) -> FastScheduledCastState:
        if batch_size < 1 or max_casts < 1:
            raise ValueError("batch_size and max_casts must be positive")
        tensor_device = torch.device(device)
        if tensor_device.type == "cuda" and tensor_device.index is None:
            tensor_device = torch.device("cuda", torch.cuda.current_device())
        shape = (batch_size, max_casts)

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(shape, dtype=dtype, device=tensor_device)

        return cls(
            device=tensor_device,
            active=zeros(torch.bool),
            stable_id=zeros(torch.int64),
            owner=zeros(torch.int8),
            source_card_id=zeros(torch.int64),
            x_units=zeros(torch.int32),
            y_units=zeros(torch.int32),
            next_tick=zeros(torch.int64),
            interval_ticks=zeros(torch.int32),
            waves_remaining=zeros(torch.int32),
            child_card_id=zeros(torch.int64),
            count=zeros(torch.int32),
            radius_units=zeros(torch.int32),
            deploy_ticks=zeros(torch.int32),
            initial_effect_pending=zeros(torch.bool),
            initial_damage=zeros(torch.float32),
            initial_radius_units=zeros(torch.int32),
            initial_status_kind=zeros(torch.int8),
            initial_status_duration_ticks=zeros(torch.int32),
            tower_damage_multiplier=torch.ones(
                shape, dtype=torch.float32, device=tensor_device
            ),
            building_damage_multiplier=torch.ones(
                shape, dtype=torch.float32, device=tensor_device
            ),
            hits_air=torch.ones(shape, dtype=torch.bool, device=tensor_device),
            hits_ground=torch.ones(shape, dtype=torch.bool, device=tensor_device),
            next_stable_id=torch.ones(
                (batch_size,), dtype=torch.int64, device=tensor_device
            ),
        )

    def clone(self) -> FastScheduledCastState:
        values: dict[str, object] = {"device": self.device}
        for descriptor in fields(self):
            if descriptor.name != "device":
                values[descriptor.name] = getattr(self, descriptor.name).clone()
        return type(self)(**values)  # type: ignore[arg-type]


@dataclass(frozen=True)
class FastScheduledCastAllocationResult:
    """Cast-pool admission and explicit bounded-capacity telemetry."""

    accepted: torch.Tensor
    invalid: torch.Tensor
    capacity_rejected: torch.Tensor
    capacity_rejected_count: torch.Tensor
    allocated_mask: torch.Tensor
    source_command: torch.Tensor


@dataclass(frozen=True)
class FastScheduledAreaEffectCommands:
    """Initial one-tick area payloads ordered by cast stable ID."""

    ready: torch.Tensor
    cast_stable_id: torch.Tensor
    owner: torch.Tensor
    source_card_id: torch.Tensor
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
class FastScheduledSpawnCommands:
    """Whole-wave entity commands ordered by cast stable ID."""

    ready: torch.Tensor
    cast_stable_id: torch.Tensor
    owner: torch.Tensor
    child_card_id: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    count: torch.Tensor
    radius_units: torch.Tensor
    deploy_ticks: torch.Tensor


@dataclass(frozen=True)
class FastScheduledCastStepResult:
    """Padded due streams and lifecycle telemetry for one native tick."""

    due_mask: torch.Tensor
    expired_mask: torch.Tensor
    emitted_count: torch.Tensor
    effect_commands: FastScheduledAreaEffectCommands
    spawn_commands: FastScheduledSpawnCommands


_COMMAND_DTYPES: tuple[tuple[str, torch.dtype], ...] = (
    ("ready", torch.bool),
    ("owner", torch.int8),
    ("source_card_id", torch.int64),
    ("x_units", torch.int32),
    ("y_units", torch.int32),
    ("first_delay_ticks", torch.int32),
    ("interval_ticks", torch.int32),
    ("waves", torch.int32),
    ("child_card_id", torch.int64),
    ("count", torch.int32),
    ("radius_units", torch.int32),
    ("deploy_ticks", torch.int32),
    ("initial_damage", torch.float32),
    ("initial_radius_units", torch.int32),
    ("initial_status_kind", torch.int8),
    ("initial_status_duration_ticks", torch.int32),
    ("tower_damage_multiplier", torch.float32),
    ("building_damage_multiplier", torch.float32),
    ("hits_air", torch.bool),
    ("hits_ground", torch.bool),
)


def _validate_state(state: FastScheduledCastState) -> None:
    shape = tuple(state.active.shape)
    if len(shape) != 2:
        raise ValueError("scheduled cast state must have shape [batch, casts]")
    for descriptor in fields(state):
        if descriptor.name in {"device", "next_stable_id"}:
            continue
        value = getattr(state, descriptor.name)
        if tuple(value.shape) != shape or value.device != state.device:
            raise ValueError(
                f"{descriptor.name} must match scheduled cast shape and device"
            )
    if tuple(state.next_stable_id.shape) != (shape[0],):
        raise ValueError("next_stable_id must have shape [batch]")
    if (
        state.next_stable_id.device != state.device
        or state.next_stable_id.dtype != torch.int64
    ):
        raise ValueError("next_stable_id must be int64 on the cast device")


def _validate_commands(
    state: FastScheduledCastState,
    commands: FastScheduledCastCommands,
) -> tuple[int, int]:
    shape = tuple(commands.ready.shape)
    if len(shape) != 2 or shape[0] != state.batch_size:
        raise ValueError("scheduled commands must have shape [batch, commands]")
    for name, dtype in _COMMAND_DTYPES:
        value = getattr(commands, name)
        if tuple(value.shape) != shape or value.device != state.device:
            raise ValueError(f"{name} must match command shape and device")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")
    return shape


def _tick_plane(
    tick: int | torch.Tensor,
    *,
    state: FastScheduledCastState,
) -> torch.Tensor:
    value = torch.as_tensor(tick, dtype=torch.int64, device=state.device)
    if value.ndim == 0:
        return value.expand(state.batch_size, state.capacity)
    if tuple(value.shape) == (state.batch_size,):
        return value[:, None].expand(-1, state.capacity)
    if tuple(value.shape) == (state.batch_size, 1):
        return value.expand(-1, state.capacity)
    raise ValueError("tick must be scalar, [batch], or [batch, 1]")


def _clear_slots_(state: FastScheduledCastState, mask: torch.Tensor) -> None:
    zero_fields = (
        "active",
        "stable_id",
        "owner",
        "source_card_id",
        "x_units",
        "y_units",
        "next_tick",
        "interval_ticks",
        "waves_remaining",
        "child_card_id",
        "count",
        "radius_units",
        "deploy_ticks",
        "initial_effect_pending",
        "initial_damage",
        "initial_radius_units",
        "initial_status_kind",
        "initial_status_duration_ticks",
    )
    for name in zero_fields:
        getattr(state, name).masked_fill_(mask, 0)
    state.tower_damage_multiplier.masked_fill_(mask, 1.0)
    state.building_damage_multiplier.masked_fill_(mask, 1.0)
    state.hits_air.masked_fill_(mask, True)
    state.hits_ground.masked_fill_(mask, True)


def allocate_fast_scheduled_casts_(
    state: FastScheduledCastState,
    commands: FastScheduledCastCommands,
    *,
    tick: int | torch.Tensor,
) -> FastScheduledCastAllocationResult:
    """Admit casts in command order without eviction or partial mutation."""

    _validate_state(state)
    command_shape = _validate_commands(state, commands)
    _clear_slots_(state, ~state.active)

    has_spawn = (commands.child_card_id > 0) & (commands.count > 0)
    has_effect = (commands.initial_damage != 0) | (
        commands.initial_status_kind > 0
    )
    valid_waves = (commands.waves == FAST_SCHEDULED_UNLIMITED) | (
        commands.waves > 0
    )
    repeated = (commands.waves == FAST_SCHEDULED_UNLIMITED) | (
        commands.waves > 1
    )
    valid = (
        commands.ready
        & (commands.owner >= 0)
        & (commands.owner < 2)
        & (commands.source_card_id >= 0)
        & (commands.first_delay_ticks >= 0)
        & valid_waves
        & (~repeated | (commands.interval_ticks > 0))
        & (commands.interval_ticks >= 0)
        & (commands.child_card_id >= 0)
        & (commands.count >= 0)
        & (commands.radius_units >= 0)
        & (commands.deploy_ticks >= 0)
        & torch.isfinite(commands.initial_damage)
        & (commands.initial_radius_units >= 0)
        & (commands.initial_status_kind >= 0)
        & (commands.initial_status_duration_ticks >= 0)
        & torch.isfinite(commands.tower_damage_multiplier)
        & (commands.tower_damage_multiplier >= 0)
        & torch.isfinite(commands.building_damage_multiplier)
        & (commands.building_damage_multiplier >= 0)
        & (has_spawn | has_effect)
        & (has_spawn | ~repeated)
    )
    command_rank = valid.to(torch.int64).cumsum(dim=1) - 1
    free = ~state.active
    free_rank = free.to(torch.int64).cumsum(dim=1) - 1
    free_count = free.sum(dim=1, dtype=torch.int64)
    accepted = valid & (command_rank < free_count[:, None])
    accepted_count = accepted.sum(dim=1, dtype=torch.int64)
    allocated = free & (free_rank >= 0) & (free_rank < accepted_count[:, None])
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

    tick_value = torch.as_tensor(tick, dtype=torch.int64, device=state.device)
    if tick_value.ndim == 0:
        command_tick = tick_value.expand(command_shape)
    elif tuple(tick_value.shape) == (state.batch_size,):
        command_tick = tick_value[:, None].expand(command_shape)
    elif tuple(tick_value.shape) == (state.batch_size, 1):
        command_tick = tick_value.expand(command_shape)
    else:
        raise ValueError("tick must be scalar, [batch], or [batch, 1]")

    write(state.active, torch.ones_like(allocated))
    write(state.stable_id, state.next_stable_id[:, None] + free_rank)
    write(state.owner, gather(commands.owner))
    write(state.source_card_id, gather(commands.source_card_id))
    write(state.x_units, gather(commands.x_units))
    write(state.y_units, gather(commands.y_units))
    write(
        state.next_tick,
        gather(command_tick + commands.first_delay_ticks.to(torch.int64)),
    )
    write(state.interval_ticks, gather(commands.interval_ticks))
    write(state.waves_remaining, gather(commands.waves))
    write(state.child_card_id, gather(commands.child_card_id))
    write(state.count, gather(commands.count))
    write(state.radius_units, gather(commands.radius_units))
    write(state.deploy_ticks, gather(commands.deploy_ticks))
    write(state.initial_effect_pending, gather(has_effect))
    write(state.initial_damage, gather(commands.initial_damage))
    write(state.initial_radius_units, gather(commands.initial_radius_units))
    write(state.initial_status_kind, gather(commands.initial_status_kind))
    write(
        state.initial_status_duration_ticks,
        gather(commands.initial_status_duration_ticks),
    )
    write(
        state.tower_damage_multiplier,
        gather(commands.tower_damage_multiplier),
    )
    write(
        state.building_damage_multiplier,
        gather(commands.building_damage_multiplier),
    )
    write(state.hits_air, gather(commands.hits_air))
    write(state.hits_ground, gather(commands.hits_ground))
    state.next_stable_id.add_(accepted_count)

    capacity_rejected = valid & ~accepted
    return FastScheduledCastAllocationResult(
        accepted=accepted,
        invalid=commands.ready & ~valid,
        capacity_rejected=capacity_rejected,
        capacity_rejected_count=capacity_rejected.sum(dim=1, dtype=torch.int32),
        allocated_mask=allocated,
        source_command=torch.where(allocated, source_command, -1),
    )


def step_fast_scheduled_casts_(
    state: FastScheduledCastState,
    *,
    tick: int | torch.Tensor,
) -> FastScheduledCastStepResult:
    """Emit one stable-ordered due wave per cast and clear completed slots."""

    _validate_state(state)
    _clear_slots_(state, ~state.active)
    now = _tick_plane(tick, state=state)
    due = state.active & (state.waves_remaining != 0) & (now >= state.next_tick)
    finite_due = due & (state.waves_remaining > 0)
    state.waves_remaining.sub_(finite_due.to(torch.int32))
    state.next_tick.add_(due.to(torch.int64) * state.interval_ticks.to(torch.int64))

    capacity = state.capacity
    slots = torch.arange(capacity, dtype=torch.int64, device=state.device)
    id_i = state.stable_id[:, :, None]
    id_j = state.stable_id[:, None, :]
    slot_i = slots.view(1, capacity, 1)
    slot_j = slots.view(1, 1, capacity)
    predecessor = due[:, None, :] & (
        (id_j < id_i) | ((id_j == id_i) & (slot_j < slot_i))
    )
    rank = predecessor.sum(dim=2, dtype=torch.int64)
    output_slot = slots.view(1, capacity)
    emitted_count = due.sum(dim=1, dtype=torch.int32)
    emitted = output_slot < emitted_count[:, None]
    claims = (
        emitted[:, :, None]
        & due[:, None, :]
        & (output_slot[:, :, None] == rank[:, None, :])
    )
    source_slot = claims.to(torch.int64).argmax(dim=2)

    def ordered(value: torch.Tensor) -> torch.Tensor:
        gathered = value.gather(1, source_slot)
        return torch.where(emitted, gathered, torch.zeros_like(gathered))

    cast_stable_id = ordered(state.stable_id)
    owner = ordered(state.owner)
    x_units = ordered(state.x_units)
    y_units = ordered(state.y_units)
    effect_pending = ordered(state.initial_effect_pending)
    effect_ready = emitted & effect_pending
    child_card_id = ordered(state.child_card_id)
    count = ordered(state.count)
    spawn_ready = emitted & (child_card_id > 0) & (count > 0)

    effect_commands = FastScheduledAreaEffectCommands(
        ready=effect_ready,
        cast_stable_id=cast_stable_id,
        owner=owner,
        source_card_id=ordered(state.source_card_id),
        x_units=x_units,
        y_units=y_units,
        damage=ordered(state.initial_damage),
        radius_units=ordered(state.initial_radius_units),
        status_kind=ordered(state.initial_status_kind),
        status_duration_ticks=ordered(state.initial_status_duration_ticks),
        tower_damage_multiplier=ordered(state.tower_damage_multiplier),
        building_damage_multiplier=ordered(state.building_damage_multiplier),
        hits_air=ordered(state.hits_air),
        hits_ground=ordered(state.hits_ground),
    )
    spawn_commands = FastScheduledSpawnCommands(
        ready=spawn_ready,
        cast_stable_id=cast_stable_id,
        owner=owner,
        child_card_id=child_card_id,
        x_units=x_units,
        y_units=y_units,
        count=count,
        radius_units=ordered(state.radius_units),
        deploy_ticks=ordered(state.deploy_ticks),
    )

    state.initial_effect_pending.masked_fill_(due, False)
    expired = due & (state.waves_remaining == 0)
    expired_snapshot = expired.clone()
    _clear_slots_(state, expired)
    return FastScheduledCastStepResult(
        due_mask=due,
        expired_mask=expired_snapshot,
        emitted_count=emitted_count,
        effect_commands=effect_commands,
        spawn_commands=spawn_commands,
    )


__all__ = [
    "FAST_SCHEDULED_UNLIMITED",
    "FastScheduledAreaEffectCommands",
    "FastScheduledCastAllocationResult",
    "FastScheduledCastCommands",
    "FastScheduledCastState",
    "FastScheduledCastStepResult",
    "FastScheduledSpawnCommands",
    "allocate_fast_scheduled_casts_",
    "step_fast_scheduled_casts_",
]
