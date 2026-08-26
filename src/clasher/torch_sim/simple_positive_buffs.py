"""Fixed-shape friendly haste buffs for the practical tensor Gym.

The kernel consumes numeric area scans rather than card identities.  An area
owner is responsible for its own lifetime and scan cadence; each command only
refreshes the recipient duration carried in ``duration_ticks``.  This keeps a
long-lived field separate from the shorter buff falloff on entities that leave
it.

Overlapping scans compose deterministically by retaining the strongest
movement and attack-clock multipliers and the longest recipient duration.  A
single compact state is an intentional practical-Gym approximation: it does
not retain a dynamic stack of contributing area objects.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import torch

from .simple_state import FastGymState


@dataclass
class FastPositiveBuffState:
    """Mutable per-entity haste state with shape ``[batch, entities]``."""

    device: torch.device
    bound_stable_id: torch.Tensor
    remaining_ticks: torch.Tensor
    movement_speed_multiplier: torch.Tensor
    attack_cooldown_multiplier: torch.Tensor
    attack_clock_fraction: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.bound_stable_id.shape[0])

    @property
    def max_entities(self) -> int:
        return int(self.bound_stable_id.shape[1])

    @classmethod
    def empty(
        cls,
        batch_size: int,
        *,
        max_entities: int = 64,
        device: str | torch.device = "cpu",
    ) -> FastPositiveBuffState:
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
            bound_stable_id=torch.zeros(
                shape, dtype=torch.int64, device=tensor_device
            ),
            remaining_ticks=torch.zeros(
                shape, dtype=torch.int32, device=tensor_device
            ),
            movement_speed_multiplier=torch.ones(
                shape, dtype=torch.float32, device=tensor_device
            ),
            attack_cooldown_multiplier=torch.ones(
                shape, dtype=torch.float32, device=tensor_device
            ),
            attack_clock_fraction=torch.zeros(
                shape, dtype=torch.float32, device=tensor_device
            ),
        )

    def clone(self) -> FastPositiveBuffState:
        values: dict[str, object] = {"device": self.device}
        for descriptor in fields(self):
            if descriptor.name != "device":
                values[descriptor.name] = getattr(self, descriptor.name).clone()
        return type(self)(**values)  # type: ignore[arg-type]

    def reset_rows_(self, reset_mask: torch.Tensor) -> None:
        """Clear selected batch rows without moving state off device."""

        if tuple(reset_mask.shape) != (self.batch_size,):
            raise ValueError("reset_mask must have shape [batch]")
        if reset_mask.device != self.device or reset_mask.dtype != torch.bool:
            raise ValueError("reset_mask must be bool on the buff device")
        selected = reset_mask[:, None]
        self.bound_stable_id.masked_fill_(selected, 0)
        self.remaining_ticks.masked_fill_(selected, 0)
        self.movement_speed_multiplier.copy_(
            torch.where(selected, 1.0, self.movement_speed_multiplier)
        )
        self.attack_cooldown_multiplier.copy_(
            torch.where(selected, 1.0, self.attack_cooldown_multiplier)
        )
        self.attack_clock_fraction.masked_fill_(selected, 0.0)


@dataclass
class FastPositiveBuffAreaState:
    """Fixed-capacity persistent friendly-area pool."""

    device: torch.device
    active: torch.Tensor
    stable_id: torch.Tensor
    owner: torch.Tensor
    center_x_units: torch.Tensor
    center_y_units: torch.Tensor
    radius_units: torch.Tensor
    remaining_ticks: torch.Tensor
    scan_interval_ticks: torch.Tensor
    next_scan_ticks: torch.Tensor
    recipient_duration_ticks: torch.Tensor
    movement_speed_multiplier: torch.Tensor
    attack_cooldown_multiplier: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.active.shape[0])

    @property
    def max_areas(self) -> int:
        return int(self.active.shape[1])

    @classmethod
    def empty(
        cls,
        batch_size: int,
        *,
        max_areas: int = 32,
        device: str | torch.device = "cpu",
    ) -> FastPositiveBuffAreaState:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if max_areas < 1:
            raise ValueError("max_areas must be positive")
        tensor_device = torch.device(device)
        if tensor_device.type == "cuda" and tensor_device.index is None:
            tensor_device = torch.device("cuda", torch.cuda.current_device())
        shape = (batch_size, max_areas)

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(shape, dtype=dtype, device=tensor_device)

        return cls(
            device=tensor_device,
            active=zeros(torch.bool),
            stable_id=zeros(torch.int64),
            owner=zeros(torch.int8),
            center_x_units=zeros(torch.int32),
            center_y_units=zeros(torch.int32),
            radius_units=zeros(torch.int32),
            remaining_ticks=zeros(torch.int32),
            scan_interval_ticks=zeros(torch.int32),
            next_scan_ticks=zeros(torch.int32),
            recipient_duration_ticks=zeros(torch.int32),
            movement_speed_multiplier=torch.ones(
                shape, dtype=torch.float32, device=tensor_device
            ),
            attack_cooldown_multiplier=torch.ones(
                shape, dtype=torch.float32, device=tensor_device
            ),
        )

    def reset_rows_(self, reset_mask: torch.Tensor) -> None:
        if tuple(reset_mask.shape) != (self.batch_size,):
            raise ValueError("reset_mask must have shape [batch]")
        if reset_mask.device != self.device or reset_mask.dtype != torch.bool:
            raise ValueError("reset_mask must be bool on the area device")
        selected = reset_mask[:, None]
        for descriptor in fields(self):
            if descriptor.name == "device":
                continue
            value = getattr(self, descriptor.name)
            if value.dtype == torch.bool:
                value.masked_fill_(selected, False)
            elif descriptor.name in {
                "movement_speed_multiplier",
                "attack_cooldown_multiplier",
            }:
                value.masked_fill_(selected, 1.0)
            else:
                value.masked_fill_(selected, 0)


@dataclass(frozen=True)
class FastPositiveBuffAreaAllocationCommands:
    """Persistent-area creation requests with shape ``[batch, commands]``."""

    ready: torch.Tensor
    stable_id: torch.Tensor
    owner: torch.Tensor
    center_x_units: torch.Tensor
    center_y_units: torch.Tensor
    radius_units: torch.Tensor
    lifetime_ticks: torch.Tensor
    scan_interval_ticks: torch.Tensor
    recipient_duration_ticks: torch.Tensor
    movement_speed_multiplier: torch.Tensor
    attack_cooldown_multiplier: torch.Tensor


@dataclass(frozen=True)
class FastPositiveBuffAreaAllocationResult:
    accepted: torch.Tensor
    invalid: torch.Tensor
    capacity_rejected: torch.Tensor
    capacity_rejected_count: torch.Tensor
    allocated_mask: torch.Tensor


@dataclass(frozen=True)
class FastPositiveBuffAreaStepResult:
    scans: FastPositiveBuffAreaCommands
    expired: torch.Tensor


@dataclass(frozen=True)
class FastPositiveBuffAreaCommands:
    """Numeric friendly-area scans with shape ``[batch, areas]``.

    Multipliers use direct ratios: ``1.3`` is a thirty-percent movement or
    attack-clock increase.  Values below one are not positive buffs and fail
    closed.  The area producer owns source lifetime and scan cadence.
    """

    active: torch.Tensor
    owner: torch.Tensor
    center_x_units: torch.Tensor
    center_y_units: torch.Tensor
    radius_units: torch.Tensor
    duration_ticks: torch.Tensor
    movement_speed_multiplier: torch.Tensor
    attack_cooldown_multiplier: torch.Tensor


@dataclass(frozen=True)
class FastPositiveBuffView:
    """Identity-safe multipliers consumed by movement and attack clocks."""

    active: torch.Tensor
    movement_speed_multiplier: torch.Tensor
    cooldown_decrement_multiplier: torch.Tensor


@dataclass(frozen=True)
class FastPositiveBuffApplyResult:
    """Fixed-shape application facts for diagnostics and tests."""

    touched: torch.Tensor
    newly_applied: torch.Tensor
    refreshed: torch.Tensor


@dataclass(frozen=True)
class FastPositiveBuffAdvanceResult:
    """Fixed-shape expiration and stale-identity cleanup facts."""

    decremented: torch.Tensor
    expired: torch.Tensor
    stale_cleared: torch.Tensor


def _validate_buff_state(
    state: FastGymState,
    buffs: FastPositiveBuffState,
) -> tuple[int, int]:
    shape = (state.batch_size, state.max_entities)
    if buffs.device != state.device:
        raise ValueError("buffs and state must use the same device")
    expected = {
        "bound_stable_id": torch.int64,
        "remaining_ticks": torch.int32,
        "movement_speed_multiplier": torch.float32,
        "attack_cooldown_multiplier": torch.float32,
        "attack_clock_fraction": torch.float32,
    }
    for name, dtype in expected.items():
        value = getattr(buffs, name)
        if tuple(value.shape) != shape:
            raise ValueError(f"{name} must have shape [batch, entities]")
        if value.device != state.device:
            raise ValueError(f"{name} is on a different device")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")
    return shape


def _validate_commands(
    state: FastGymState,
    commands: FastPositiveBuffAreaCommands,
) -> tuple[int, int]:
    shape = tuple(commands.active.shape)
    if len(shape) != 2 or shape[0] != state.batch_size:
        raise ValueError("area tensors must have shape [batch, areas]")
    expected = {
        "active": torch.bool,
        "owner": torch.int8,
        "center_x_units": torch.int32,
        "center_y_units": torch.int32,
        "radius_units": torch.int32,
        "duration_ticks": torch.int32,
        "movement_speed_multiplier": torch.float32,
        "attack_cooldown_multiplier": torch.float32,
    }
    for name, dtype in expected.items():
        value = getattr(commands, name)
        if tuple(value.shape) != shape:
            raise ValueError(f"{name} must have shape [batch, areas]")
        if value.device != state.device:
            raise ValueError(f"{name} is on a different device")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")
    return shape


def _identity_current(
    state: FastGymState,
    buffs: FastPositiveBuffState,
) -> torch.Tensor:
    return (
        state.active
        & (state.hp > 0)
        & (state.stable_id > 0)
        & (buffs.remaining_ticks > 0)
        & (buffs.bound_stable_id == state.stable_id)
    )


def clear_stale_fast_positive_buffs_(
    state: FastGymState,
    buffs: FastPositiveBuffState,
) -> torch.Tensor:
    """Clear expired, dead, or slot-reused recipients and return their mask."""

    _validate_buff_state(state, buffs)
    occupied = buffs.bound_stable_id > 0
    current = _identity_current(state, buffs)
    stale = occupied & ~current
    buffs.bound_stable_id.masked_fill_(stale, 0)
    buffs.remaining_ticks.masked_fill_(stale, 0)
    buffs.movement_speed_multiplier.copy_(
        torch.where(stale, 1.0, buffs.movement_speed_multiplier)
    )
    buffs.attack_cooldown_multiplier.copy_(
        torch.where(stale, 1.0, buffs.attack_cooldown_multiplier)
    )
    buffs.attack_clock_fraction.masked_fill_(stale, 0.0)
    return stale


def fast_positive_buff_view(
    state: FastGymState,
    buffs: FastPositiveBuffState,
) -> FastPositiveBuffView:
    """Return ordinary-one tensor views for stale or unbuffed entities."""

    _validate_buff_state(state, buffs)
    current = _identity_current(state, buffs)
    one = torch.ones_like(buffs.movement_speed_multiplier)
    return FastPositiveBuffView(
        active=current,
        movement_speed_multiplier=torch.where(
            current, buffs.movement_speed_multiplier.clamp(min=1.0), one
        ),
        cooldown_decrement_multiplier=torch.where(
            current, buffs.attack_cooldown_multiplier.clamp(min=1.0), one
        ),
    )


def apply_fast_positive_area_buffs_(
    state: FastGymState,
    buffs: FastPositiveBuffState,
    commands: FastPositiveBuffAreaCommands,
) -> FastPositiveBuffApplyResult:
    """Apply simultaneous friendly-area scans to live recipients.

    All reductions are order-independent.  Malformed owners, radii, durations,
    NaNs, infinities, and non-positive-buff multiplier pairs are ignored.
    """

    entity_shape = _validate_buff_state(state, buffs)
    _, areas = _validate_commands(state, commands)
    clear_stale_fast_positive_buffs_(state, buffs)

    existing = _identity_current(state, buffs)
    dx = (
        state.x_units[:, None, :].to(torch.int64)
        - commands.center_x_units[:, :, None].to(torch.int64)
    )
    dy = (
        state.y_units[:, None, :].to(torch.int64)
        - commands.center_y_units[:, :, None].to(torch.int64)
    )
    radius = commands.radius_units.to(torch.int64)
    distance_inside = dx.square() + dy.square() <= radius[:, :, None].square()
    movement = commands.movement_speed_multiplier
    attack = commands.attack_cooldown_multiplier
    finite = torch.isfinite(movement) & torch.isfinite(attack)
    has_boost = (movement > 1.0) | (attack > 1.0)
    valid_area = (
        commands.active
        & (commands.owner >= 0)
        & (commands.owner < 2)
        & (commands.radius_units >= 0)
        & (commands.duration_ticks > 0)
        & finite
        & has_boost
    )
    eligible_entity = state.active & (state.hp > 0) & (state.stable_id > 0)
    eligible = (
        valid_area[:, :, None]
        & eligible_entity[:, None, :]
        & (commands.owner[:, :, None] == state.owner[:, None, :])
        & distance_inside
    )

    # Reducing empty area axes is undefined, so the zero-capacity case returns
    # the same fixed entity-shaped telemetry without touching recipient state.
    if areas == 0:
        untouched = torch.zeros(entity_shape, dtype=torch.bool, device=state.device)
        return FastPositiveBuffApplyResult(
            touched=untouched,
            newly_applied=untouched,
            refreshed=untouched,
        )

    one_movement = torch.ones_like(movement)[:, :, None]
    one_attack = torch.ones_like(attack)[:, :, None]
    candidate_movement = torch.where(
        eligible,
        movement.clamp(min=1.0)[:, :, None],
        one_movement,
    ).amax(dim=1)
    candidate_attack = torch.where(
        eligible,
        attack.clamp(min=1.0)[:, :, None],
        one_attack,
    ).amax(dim=1)
    candidate_duration = torch.where(
        eligible,
        commands.duration_ticks[:, :, None],
        0,
    ).amax(dim=1)
    touched = candidate_duration > 0
    newly_applied = touched & ~existing
    refreshed = touched & existing

    buffs.bound_stable_id.copy_(
        torch.where(touched, state.stable_id, buffs.bound_stable_id)
    )
    buffs.remaining_ticks.copy_(
        torch.where(
            touched,
            torch.maximum(buffs.remaining_ticks, candidate_duration),
            buffs.remaining_ticks,
        )
    )
    buffs.movement_speed_multiplier.copy_(
        torch.where(
            touched,
            torch.maximum(
                buffs.movement_speed_multiplier,
                candidate_movement,
            ),
            buffs.movement_speed_multiplier,
        )
    )
    buffs.attack_cooldown_multiplier.copy_(
        torch.where(
            touched,
            torch.maximum(
                buffs.attack_cooldown_multiplier,
                candidate_attack,
            ),
            buffs.attack_cooldown_multiplier,
        )
    )
    return FastPositiveBuffApplyResult(
        touched=touched,
        newly_applied=newly_applied,
        refreshed=refreshed,
    )


def advance_fast_positive_buffs_(
    state: FastGymState,
    buffs: FastPositiveBuffState,
) -> FastPositiveBuffAdvanceResult:
    """Consume one recipient tick, then clear buffs that just expired."""

    _validate_buff_state(state, buffs)
    stale = clear_stale_fast_positive_buffs_(state, buffs)
    decremented = _identity_current(state, buffs)
    buffs.remaining_ticks.sub_(decremented.to(torch.int32)).clamp_(min=0)
    expired = decremented & (buffs.remaining_ticks == 0)
    buffs.bound_stable_id.masked_fill_(expired, 0)
    buffs.movement_speed_multiplier.copy_(
        torch.where(expired, 1.0, buffs.movement_speed_multiplier)
    )
    buffs.attack_cooldown_multiplier.copy_(
        torch.where(expired, 1.0, buffs.attack_cooldown_multiplier)
    )
    buffs.attack_clock_fraction.masked_fill_(expired, 0.0)
    return FastPositiveBuffAdvanceResult(
        decremented=decremented,
        expired=expired,
        stale_cleared=stale,
    )


def fast_positive_attack_clock_decrement_(
    state: FastGymState,
    buffs: FastPositiveBuffState,
    *,
    cooling: torch.Tensor,
) -> torch.Tensor:
    """Return integer cooldown progress and retain fractional haste credit.

    The caller supplies the exact slots whose attack clock advances this tick.
    This makes a 1.3 multiplier produce three extra cooldown ticks per ten
    native ticks without rounding it away or decrementing the same clock in a
    second subsystem.
    """

    _validate_buff_state(state, buffs)
    if cooling.shape != state.active.shape:
        raise ValueError("cooling must have shape [batch, entities]")
    if cooling.device != state.device or cooling.dtype != torch.bool:
        raise ValueError("cooling must be bool on the state device")
    view = fast_positive_buff_view(state, buffs)
    total = buffs.attack_clock_fraction + view.cooldown_decrement_multiplier
    decrement = torch.floor(total).to(torch.int32)
    buffs.attack_clock_fraction.copy_(
        torch.where(cooling, total - decrement.to(torch.float32), 0.0)
    )
    return torch.where(cooling, decrement.clamp(min=1), 0)


def _validate_area_state(areas: FastPositiveBuffAreaState) -> None:
    shape = tuple(areas.active.shape)
    if len(shape) != 2:
        raise ValueError("positive area state must have shape [batch, areas]")
    expected = {
        "active": torch.bool,
        "stable_id": torch.int64,
        "owner": torch.int8,
        "center_x_units": torch.int32,
        "center_y_units": torch.int32,
        "radius_units": torch.int32,
        "remaining_ticks": torch.int32,
        "scan_interval_ticks": torch.int32,
        "next_scan_ticks": torch.int32,
        "recipient_duration_ticks": torch.int32,
        "movement_speed_multiplier": torch.float32,
        "attack_cooldown_multiplier": torch.float32,
    }
    for name, dtype in expected.items():
        value = getattr(areas, name)
        if tuple(value.shape) != shape or value.device != areas.device:
            raise ValueError(f"{name} must match the area shape and device")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")


def allocate_fast_positive_buff_areas_(
    areas: FastPositiveBuffAreaState,
    commands: FastPositiveBuffAreaAllocationCommands,
) -> FastPositiveBuffAreaAllocationResult:
    """Allocate persistent friendly fields in command order without eviction."""

    _validate_area_state(areas)
    shape = tuple(commands.ready.shape)
    if len(shape) != 2 or shape[0] != areas.batch_size:
        raise ValueError("positive area commands must have shape [batch, commands]")
    expected = {
        "ready": torch.bool,
        "stable_id": torch.int64,
        "owner": torch.int8,
        "center_x_units": torch.int32,
        "center_y_units": torch.int32,
        "radius_units": torch.int32,
        "lifetime_ticks": torch.int32,
        "scan_interval_ticks": torch.int32,
        "recipient_duration_ticks": torch.int32,
        "movement_speed_multiplier": torch.float32,
        "attack_cooldown_multiplier": torch.float32,
    }
    for name, dtype in expected.items():
        value = getattr(commands, name)
        if tuple(value.shape) != shape or value.device != areas.device:
            raise ValueError(f"{name} must match command shape and device")
        if value.dtype != dtype:
            raise ValueError(f"{name} must use {dtype}")
    finite = torch.isfinite(commands.movement_speed_multiplier) & torch.isfinite(
        commands.attack_cooldown_multiplier
    )
    valid = (
        commands.ready
        & (commands.stable_id > 0)
        & (commands.owner >= 0)
        & (commands.owner < 2)
        & (commands.radius_units >= 0)
        & (commands.lifetime_ticks > 0)
        & (commands.scan_interval_ticks > 0)
        & (commands.recipient_duration_ticks > 0)
        & finite
        & (
            (commands.movement_speed_multiplier > 1.0)
            | (commands.attack_cooldown_multiplier > 1.0)
        )
    )
    command_rank = valid.to(torch.int64).cumsum(dim=1) - 1
    free = ~areas.active
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
    source = claims.to(torch.int64).argmax(dim=2)

    def gather(value: torch.Tensor) -> torch.Tensor:
        return value.gather(1, source)

    def write(field: torch.Tensor, value: torch.Tensor) -> None:
        field.copy_(torch.where(allocated, value.to(field.dtype), field))

    write(areas.active, torch.ones_like(allocated))
    for name in (
        "stable_id",
        "owner",
        "center_x_units",
        "center_y_units",
        "radius_units",
        "recipient_duration_ticks",
        "movement_speed_multiplier",
        "attack_cooldown_multiplier",
    ):
        write(getattr(areas, name), gather(getattr(commands, name)))
    write(areas.remaining_ticks, gather(commands.lifetime_ticks))
    write(areas.scan_interval_ticks, gather(commands.scan_interval_ticks))
    write(areas.next_scan_ticks, gather(commands.scan_interval_ticks))
    rejected = valid & ~accepted
    return FastPositiveBuffAreaAllocationResult(
        accepted=accepted,
        invalid=commands.ready & ~valid,
        capacity_rejected=rejected,
        capacity_rejected_count=rejected.sum(dim=1, dtype=torch.int32),
        allocated_mask=allocated,
    )


def step_fast_positive_buff_areas_(
    areas: FastPositiveBuffAreaState,
) -> FastPositiveBuffAreaStepResult:
    """Advance fields once and emit their serialized-cadence friendly scans."""

    _validate_area_state(areas)
    active = areas.active
    areas.remaining_ticks.sub_(active.to(torch.int32)).clamp_(min=0)
    areas.next_scan_ticks.sub_(active.to(torch.int32))
    expired = active & (areas.remaining_ticks == 0)
    scan = active & ~expired & (areas.next_scan_ticks <= 0)
    areas.next_scan_ticks.copy_(
        torch.where(
            scan,
            areas.next_scan_ticks + areas.scan_interval_ticks,
            areas.next_scan_ticks,
        )
    )
    commands = FastPositiveBuffAreaCommands(
        active=scan,
        owner=areas.owner,
        center_x_units=areas.center_x_units,
        center_y_units=areas.center_y_units,
        radius_units=areas.radius_units,
        duration_ticks=areas.recipient_duration_ticks,
        movement_speed_multiplier=areas.movement_speed_multiplier,
        attack_cooldown_multiplier=areas.attack_cooldown_multiplier,
    )
    areas.active.masked_fill_(expired, False)
    areas.stable_id.masked_fill_(expired, 0)
    areas.remaining_ticks.masked_fill_(expired, 0)
    areas.next_scan_ticks.masked_fill_(expired, 0)
    return FastPositiveBuffAreaStepResult(scans=commands, expired=expired)
