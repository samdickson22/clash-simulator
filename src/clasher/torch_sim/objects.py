"""Batched fixed-point runtime for non-character battle objects.

This module deliberately owns only the object-manager part of a battle tick:
projectile travel/arrival, periodic-area clocks, delayed payload containers,
and the ID-ordered dynamically growing worklist.  Target selection, hitbox
queries, damage/status application, formations, and entity allocation remain
consumers of the emitted events.  A caller must fall back to the Python oracle
when :meth:`TensorObjectState.unsupported_batches` marks a battle unsupported.

The two public effect opcodes match the serialized factory's ``PeriodicArea``
and ``ProjectileLaunch`` operations.  No opcode or branch is card-named.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import IntEnum, IntFlag

import torch

from clasher.effects.area import PeriodicArea
from clasher.effects.projectile import ProjectileLaunch
from clasher.kinematics import (
    LOGIC_TICK_MILLISECONDS,
    tiles_per_second_to_logic_speed,
    tiles_to_logic_units,
)


class ObjectOpcode(IntEnum):
    """Stable generalized operations used by the serialized effect factory."""

    PERIODIC_AREA = 1
    PROJECTILE_LAUNCH = 2
    TIMED_PAYLOAD = 3


class ObjectEventOpcode(IntEnum):
    PROJECTILE_IMPACT = 1
    AREA_TICK = 2
    SPAWN = 3
    DEATH = 4


class UnsupportedObjectFeature(IntFlag):
    """Features which force a whole battle to the Python oracle."""

    NONE = 0
    HOMING = 1 << 0
    PIERCING = 1 << 1
    TARGET_QUERY = 1 << 2
    STATUS_APPLICATION = 1 << 3
    KNOCKBACK = 1 << 4
    CONTINUOUS_AREA = 1 << 5
    SUB_TICK_INTERVAL = 1 << 6
    FRACTIONAL_DELAY = 1 << 7
    UNKNOWN_OPERATION = 1 << 8


@dataclass(frozen=True)
class ObjectBlueprint:
    """Immutable object parameters compiled before production tick execution.

    Coordinates, durations, and speeds are native integer units.  A terminal
    blueprint appends another object at the terminal position and reserves its
    ID before that child is considered by the same-frame worklist.
    """

    opcode: int
    player_id: int = 0
    x_units: int = 0
    y_units: int = 0
    target_x_units: int = 0
    target_y_units: int = 0
    speed_units_per_tick: int = 0
    launch_delay_ms: int = 0
    activation_delay_ms: int = 0
    duration_ms: int = 0
    tick_interval_ms: int = 0
    initial_tick_ms: int = 0
    max_ticks: int = 0
    amount: float = 0.0
    payload_id: int = 0
    payload_count: int = 0
    terminal_blueprint: int = 0
    inherit_terminal_position: bool = False
    inherit_player: bool = False
    feature_mask: int = 0

    @classmethod
    def from_serialized_effect(
        cls,
        effect: object,
        *,
        player_id: int,
        position: tuple[float, float],
        target_position: tuple[float, float] | None = None,
        payload_id: int = 0,
        payload_count: int = 0,
    ) -> ObjectBlueprint:
        """Compile one factory effect without inspecting a producing card name."""

        x_units = tiles_to_logic_units(position[0])
        y_units = tiles_to_logic_units(position[1])
        target = target_position if target_position is not None else position
        if isinstance(effect, ProjectileLaunch):
            return cls(
                opcode=ObjectOpcode.PROJECTILE_LAUNCH,
                player_id=player_id,
                x_units=x_units,
                y_units=y_units,
                target_x_units=tiles_to_logic_units(target[0]),
                target_y_units=tiles_to_logic_units(target[1]),
                speed_units_per_tick=tiles_per_second_to_logic_speed(
                    effect.travel_speed
                ),
                amount=float(effect.damage),
                payload_id=payload_id,
                payload_count=payload_count,
            )
        if isinstance(effect, PeriodicArea):
            duration_ms = round(float(effect.duration_seconds) * 1000.0)
            # BaseEffect represents a continuously integrated aura.  The
            # object kernel exposes one deterministic 50 ms integration event
            # per native frame; target resolution consumes ``amount``.
            ticks = max(0, (duration_ms + LOGIC_TICK_MILLISECONDS - 1) // 50)
            feature_mask = UnsupportedObjectFeature.NONE
            if effect.freeze_effect or effect.attract_percentage > 0:
                feature_mask |= UnsupportedObjectFeature.CONTINUOUS_AREA
            return cls(
                opcode=ObjectOpcode.PERIODIC_AREA,
                player_id=player_id,
                x_units=x_units,
                y_units=y_units,
                duration_ms=duration_ms,
                tick_interval_ms=LOGIC_TICK_MILLISECONDS,
                initial_tick_ms=LOGIC_TICK_MILLISECONDS,
                max_ticks=ticks,
                amount=float(effect.damage_per_second) * 0.05,
                feature_mask=int(feature_mask),
            )
        return cls(
            opcode=0,
            player_id=player_id,
            x_units=x_units,
            y_units=y_units,
            feature_mask=int(UnsupportedObjectFeature.UNKNOWN_OPERATION),
        )


@dataclass(frozen=True)
class TensorObjectCatalog:
    """Dense immutable blueprint table; index zero is reserved for no child."""

    device: torch.device
    opcode: torch.Tensor
    player: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    target_x_units: torch.Tensor
    target_y_units: torch.Tensor
    speed_units_per_tick: torch.Tensor
    launch_delay_ms: torch.Tensor
    activation_delay_ms: torch.Tensor
    duration_ms: torch.Tensor
    tick_interval_ms: torch.Tensor
    initial_tick_ms: torch.Tensor
    max_ticks: torch.Tensor
    amount: torch.Tensor
    payload_id: torch.Tensor
    payload_count: torch.Tensor
    terminal_blueprint: torch.Tensor
    inherit_terminal_position: torch.Tensor
    inherit_player: torch.Tensor
    feature_mask: torch.Tensor

    @property
    def size(self) -> int:
        return int(self.opcode.shape[0])

    @classmethod
    def compile(
        cls,
        blueprints: Sequence[ObjectBlueprint],
        *,
        device: str | torch.device = "cpu",
    ) -> TensorObjectCatalog:
        torch_device = torch.device(device)
        records = (ObjectBlueprint(opcode=0), *blueprints)

        def tensor(name: str, dtype: torch.dtype) -> torch.Tensor:
            return torch.tensor(
                [getattr(record, name) for record in records],
                dtype=dtype,
                device=torch_device,
            )

        catalog = cls(
            device=torch_device,
            opcode=tensor("opcode", torch.int16),
            player=tensor("player_id", torch.int8),
            x_units=tensor("x_units", torch.int32),
            y_units=tensor("y_units", torch.int32),
            target_x_units=tensor("target_x_units", torch.int32),
            target_y_units=tensor("target_y_units", torch.int32),
            speed_units_per_tick=tensor("speed_units_per_tick", torch.int32),
            launch_delay_ms=tensor("launch_delay_ms", torch.int32),
            activation_delay_ms=tensor("activation_delay_ms", torch.int32),
            duration_ms=tensor("duration_ms", torch.int32),
            tick_interval_ms=tensor("tick_interval_ms", torch.int32),
            initial_tick_ms=tensor("initial_tick_ms", torch.int32),
            max_ticks=tensor("max_ticks", torch.int32),
            amount=tensor("amount", torch.float64),
            payload_id=tensor("payload_id", torch.int32),
            payload_count=tensor("payload_count", torch.int16),
            terminal_blueprint=tensor("terminal_blueprint", torch.int32),
            inherit_terminal_position=tensor("inherit_terminal_position", torch.bool),
            inherit_player=tensor("inherit_player", torch.bool),
            feature_mask=tensor("feature_mask", torch.int32),
        )
        invalid_children = (catalog.terminal_blueprint < 0) | (
            catalog.terminal_blueprint >= catalog.size
        )
        if bool(invalid_children.any().item()):
            raise ValueError("terminal blueprint index is outside the catalog")
        return catalog


@dataclass
class TensorObjectEvents:
    """Fixed-capacity per-battle output stream in exact emission order."""

    count: torch.Tensor
    opcode: torch.Tensor
    sequence: torch.Tensor
    source_id: torch.Tensor
    player: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    amount: torch.Tensor
    payload_id: torch.Tensor
    payload_count: torch.Tensor

    @classmethod
    def empty(
        cls,
        batch_size: int,
        capacity: int,
        device: torch.device,
    ) -> TensorObjectEvents:
        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros((batch_size, capacity), dtype=dtype, device=device)

        return cls(
            count=torch.zeros(batch_size, dtype=torch.int32, device=device),
            opcode=zeros(torch.int16),
            sequence=zeros(torch.int32),
            source_id=zeros(torch.int64),
            player=zeros(torch.int8),
            x_units=zeros(torch.int32),
            y_units=zeros(torch.int32),
            amount=zeros(torch.float64),
            payload_id=zeros(torch.int32),
            payload_count=zeros(torch.int16),
        )


@dataclass
class ObjectPhaseResult:
    events: TensorObjectEvents
    unsupported_batch: torch.Tensor
    processed_count: torch.Tensor


@dataclass
class TensorObjectState:
    """Mutable batched object state retained across ordinary battle ticks."""

    catalog: TensorObjectCatalog
    allocated: torch.Tensor
    active: torch.Tensor
    object_id: torch.Tensor
    blueprint_id: torch.Tensor
    opcode: torch.Tensor
    player: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    target_x_units: torch.Tensor
    target_y_units: torch.Tensor
    speed_units_per_tick: torch.Tensor
    launch_delay_ms: torch.Tensor
    activation_delay_ms: torch.Tensor
    age_ms: torch.Tensor
    duration_ms: torch.Tensor
    tick_interval_ms: torch.Tensor
    next_tick_ms: torch.Tensor
    ticks_remaining: torch.Tensor
    amount: torch.Tensor
    payload_id: torch.Tensor
    payload_count: torch.Tensor
    terminal_blueprint: torch.Tensor
    feature_mask: torch.Tensor
    next_object_id: torch.Tensor

    @property
    def device(self) -> torch.device:
        return self.allocated.device

    @property
    def batch_size(self) -> int:
        return int(self.allocated.shape[0])

    @property
    def max_objects(self) -> int:
        return int(self.allocated.shape[1])

    @classmethod
    def create(
        cls,
        catalog: TensorObjectCatalog,
        batch_blueprint_ids: Sequence[Sequence[int]],
        *,
        max_objects: int = 128,
    ) -> TensorObjectState:
        if not batch_blueprint_ids:
            raise ValueError("at least one object batch is required")
        if max((len(items) for items in batch_blueprint_ids), default=0) > max_objects:
            raise ValueError("max_objects is smaller than the initial object count")
        for items in batch_blueprint_ids:
            if any(index <= 0 or index >= catalog.size for index in items):
                raise ValueError("initial blueprint index is outside the catalog")

        batch = len(batch_blueprint_ids)
        shape = (batch, max_objects)

        def zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(shape, dtype=dtype, device=catalog.device)

        state = cls(
            catalog=catalog,
            allocated=zeros(torch.bool),
            active=zeros(torch.bool),
            object_id=zeros(torch.int64),
            blueprint_id=zeros(torch.int32),
            opcode=zeros(torch.int16),
            player=zeros(torch.int8),
            x_units=zeros(torch.int32),
            y_units=zeros(torch.int32),
            target_x_units=zeros(torch.int32),
            target_y_units=zeros(torch.int32),
            speed_units_per_tick=zeros(torch.int32),
            launch_delay_ms=zeros(torch.int32),
            activation_delay_ms=zeros(torch.int32),
            age_ms=zeros(torch.int32),
            duration_ms=zeros(torch.int32),
            tick_interval_ms=zeros(torch.int32),
            next_tick_ms=zeros(torch.int32),
            ticks_remaining=zeros(torch.int32),
            amount=zeros(torch.float64),
            payload_id=zeros(torch.int32),
            payload_count=zeros(torch.int16),
            terminal_blueprint=zeros(torch.int32),
            feature_mask=zeros(torch.int32),
            next_object_id=torch.ones(batch, dtype=torch.int64, device=catalog.device),
        )
        for batch_index, blueprint_ids in enumerate(batch_blueprint_ids):
            count = len(blueprint_ids)
            if count == 0:
                continue
            slots = torch.arange(count, device=catalog.device)
            ids = torch.tensor(blueprint_ids, dtype=torch.int64, device=catalog.device)
            state._load_blueprints(
                torch.full(
                    (count,), batch_index, dtype=torch.int64, device=catalog.device
                ),
                slots,
                ids,
            )
            state.object_id[batch_index, :count] = torch.arange(
                1, count + 1, dtype=torch.int64, device=catalog.device
            )
            state.next_object_id[batch_index] = count + 1
        return state

    def _load_blueprints(
        self,
        batch_indices: torch.Tensor,
        slots: torch.Tensor,
        blueprint_ids: torch.Tensor,
        *,
        terminal_x: torch.Tensor | None = None,
        terminal_y: torch.Tensor | None = None,
        terminal_player: torch.Tensor | None = None,
    ) -> None:
        catalog = self.catalog
        self.allocated[batch_indices, slots] = True
        self.active[batch_indices, slots] = True
        self.blueprint_id[batch_indices, slots] = blueprint_ids.to(torch.int32)
        self.opcode[batch_indices, slots] = catalog.opcode[blueprint_ids]
        player = catalog.player[blueprint_ids]
        x_units = catalog.x_units[blueprint_ids]
        y_units = catalog.y_units[blueprint_ids]
        if terminal_player is not None:
            player = torch.where(
                catalog.inherit_player[blueprint_ids], terminal_player, player
            )
        if terminal_x is not None and terminal_y is not None:
            inherit = catalog.inherit_terminal_position[blueprint_ids]
            x_units = torch.where(inherit, terminal_x, x_units)
            y_units = torch.where(inherit, terminal_y, y_units)
        self.player[batch_indices, slots] = player
        self.x_units[batch_indices, slots] = x_units
        self.y_units[batch_indices, slots] = y_units
        self.target_x_units[batch_indices, slots] = catalog.target_x_units[
            blueprint_ids
        ]
        self.target_y_units[batch_indices, slots] = catalog.target_y_units[
            blueprint_ids
        ]
        self.speed_units_per_tick[batch_indices, slots] = catalog.speed_units_per_tick[
            blueprint_ids
        ]
        self.launch_delay_ms[batch_indices, slots] = catalog.launch_delay_ms[
            blueprint_ids
        ]
        self.activation_delay_ms[batch_indices, slots] = catalog.activation_delay_ms[
            blueprint_ids
        ]
        self.age_ms[batch_indices, slots] = 0
        self.duration_ms[batch_indices, slots] = catalog.duration_ms[blueprint_ids]
        self.tick_interval_ms[batch_indices, slots] = catalog.tick_interval_ms[
            blueprint_ids
        ]
        self.next_tick_ms[batch_indices, slots] = catalog.initial_tick_ms[blueprint_ids]
        self.ticks_remaining[batch_indices, slots] = catalog.max_ticks[blueprint_ids]
        self.amount[batch_indices, slots] = catalog.amount[blueprint_ids]
        self.payload_id[batch_indices, slots] = catalog.payload_id[blueprint_ids]
        self.payload_count[batch_indices, slots] = catalog.payload_count[blueprint_ids]
        self.terminal_blueprint[batch_indices, slots] = catalog.terminal_blueprint[
            blueprint_ids
        ]
        self.feature_mask[batch_indices, slots] = catalog.feature_mask[blueprint_ids]

    def unsupported_batches(self) -> torch.Tensor:
        valid_opcode = (
            (self.opcode == ObjectOpcode.PERIODIC_AREA)
            | (self.opcode == ObjectOpcode.PROJECTILE_LAUNCH)
            | (self.opcode == ObjectOpcode.TIMED_PAYLOAD)
        )
        active = self.allocated & self.active
        unsupported = active & ((self.feature_mask != 0) | ~valid_opcode)
        unsupported |= active & (
            (self.tick_interval_ms > 0)
            & (self.tick_interval_ms < LOGIC_TICK_MILLISECONDS)
        )
        unsupported |= active & ((self.launch_delay_ms % LOGIC_TICK_MILLISECONDS) != 0)
        return unsupported.any(dim=1)


def _integer_sqrt(values: torch.Tensor) -> torch.Tensor:
    """Vectorized exact floor sqrt for arena-sized nonnegative int64 values."""

    floating_dtype = torch.float32 if values.device.type == "mps" else torch.float64
    root = torch.sqrt(values.to(floating_dtype)).to(torch.int64)
    # Float estimates are already within one at arena scale; two corrections
    # make the integer result exact even at a perfect-square rounding edge.
    for _ in range(2):
        root = torch.where(root * root > values, root - 1, root)
        next_root = root + 1
        root = torch.where(next_root * next_root <= values, next_root, root)
    return root


def _trunc_div(numerator: torch.Tensor, denominator: torch.Tensor) -> torch.Tensor:
    denominator = torch.clamp(denominator, min=1)
    return torch.sign(numerator) * torch.div(
        torch.abs(numerator), denominator, rounding_mode="floor"
    )


def _emit(
    events: TensorObjectEvents,
    mask: torch.Tensor,
    opcode: ObjectEventOpcode,
    source_id: torch.Tensor,
    player: torch.Tensor,
    x_units: torch.Tensor,
    y_units: torch.Tensor,
    amount: torch.Tensor,
    payload_id: torch.Tensor,
    payload_count: torch.Tensor,
) -> None:
    batch_indices = torch.nonzero(mask, as_tuple=False).flatten()
    if batch_indices.numel() == 0:
        return
    slots = events.count[batch_indices].to(torch.int64)
    if bool((slots >= events.opcode.shape[1]).any().item()):
        raise RuntimeError("tensor object event capacity exhausted")
    events.opcode[batch_indices, slots] = int(opcode)
    events.sequence[batch_indices, slots] = slots.to(torch.int32)
    events.source_id[batch_indices, slots] = source_id[batch_indices]
    events.player[batch_indices, slots] = player[batch_indices]
    events.x_units[batch_indices, slots] = x_units[batch_indices]
    events.y_units[batch_indices, slots] = y_units[batch_indices]
    events.amount[batch_indices, slots] = amount[batch_indices]
    events.payload_id[batch_indices, slots] = payload_id[batch_indices]
    events.payload_count[batch_indices, slots] = payload_count[batch_indices]
    events.count[batch_indices] += 1


def step_object_phase(
    state: TensorObjectState,
    *,
    dt_ms: int = LOGIC_TICK_MILLISECONDS,
    event_capacity: int | None = None,
) -> ObjectPhaseResult:
    """Advance one complete, dynamically growing native object phase.

    Batches containing any unsupported live object are left byte-for-byte
    untouched and marked for Python fallback.  Supported batches are processed
    in stable object-ID order.  A terminal child receives an ID immediately and
    participates later in this same call, matching ``BattleState._run_object_phase``.
    """

    if dt_ms != LOGIC_TICK_MILLISECONDS:
        raise ValueError("object runtime currently accepts one exact 50 ms frame")
    capacity = event_capacity or max(8, state.max_objects * 4)
    if capacity < state.max_objects * 4:
        raise ValueError("event_capacity must be at least four times max_objects")

    unsupported = state.unsupported_batches()
    runnable = ~unsupported
    processed = torch.zeros_like(state.allocated)
    processed_count = torch.zeros(
        state.batch_size, dtype=torch.int32, device=state.device
    )
    events = TensorObjectEvents.empty(state.batch_size, capacity, state.device)
    max_id = torch.iinfo(torch.int64).max
    batch_range = torch.arange(state.batch_size, device=state.device)

    for _ in range(state.max_objects):
        candidates = state.allocated & state.active & ~processed & runnable[:, None]
        candidate_ids = torch.where(candidates, state.object_id, max_id)
        selected_id, selected_slot = candidate_ids.min(dim=1)
        selected = selected_id != max_id
        if not bool(selected.any().item()):
            break
        selected_batches = batch_range[selected]
        selected_slots = selected_slot[selected]
        processed[selected_batches, selected_slots] = True
        processed_count[selected] += 1

        # Gather the selected row for every batch. Non-selected rows are
        # masked throughout, so their arbitrary argmin slot is never mutated.
        slot = selected_slot
        source_id = state.object_id[batch_range, slot]
        opcode = state.opcode[batch_range, slot]
        player = state.player[batch_range, slot]
        x_units = state.x_units[batch_range, slot]
        y_units = state.y_units[batch_range, slot]
        target_x = state.target_x_units[batch_range, slot]
        target_y = state.target_y_units[batch_range, slot]
        amount = state.amount[batch_range, slot]
        payload_id = state.payload_id[batch_range, slot]
        payload_count = state.payload_count[batch_range, slot]

        projectile = selected & (opcode == ObjectOpcode.PROJECTILE_LAUNCH)
        area = selected & (opcode == ObjectOpcode.PERIODIC_AREA)
        timer = selected & (opcode == ObjectOpcode.TIMED_PAYLOAD)

        # Every object owns an integer age clock. Projectile launch-delay is a
        # separate pre-motion countdown, mirroring Projectile.update exactly.
        state.age_ms[selected_batches, selected_slots] += dt_ms
        age = state.age_ms[batch_range, slot]

        launch_delay = state.launch_delay_ms[batch_range, slot]
        projectile_waiting = projectile & (launch_delay > 0)
        if bool(projectile_waiting.any().item()):
            wait_batches = batch_range[projectile_waiting]
            wait_slots = slot[projectile_waiting]
            state.launch_delay_ms[wait_batches, wait_slots] = torch.clamp(
                launch_delay[projectile_waiting] - dt_ms, min=0
            )
        projectile_moving = (
            projectile
            & ~projectile_waiting
            & (age >= state.activation_delay_ms[batch_range, slot])
        )
        dx = (target_x - x_units).to(torch.int64)
        dy = (target_y - y_units).to(torch.int64)
        distance = _integer_sqrt(dx * dx + dy * dy)
        travel = state.speed_units_per_tick[batch_range, slot].to(torch.int64)
        impact = projectile_moving & (distance <= travel)
        moving = projectile_moving & ~impact
        if bool(moving.any().item()):
            denom = torch.clamp(distance, min=1)
            move_x = _trunc_div(dx * travel, denom).to(torch.int32)
            move_y = _trunc_div(dy * travel, denom).to(torch.int32)
            moving_batches = batch_range[moving]
            moving_slots = slot[moving]
            state.x_units[moving_batches, moving_slots] += move_x[moving]
            state.y_units[moving_batches, moving_slots] += move_y[moving]

        _emit(
            events,
            impact,
            ObjectEventOpcode.PROJECTILE_IMPACT,
            source_id,
            player,
            target_x,
            target_y,
            amount,
            payload_id,
            payload_count,
        )
        terminal = impact.clone()

        # At most two >=50 ms area deadlines can be visible during a single
        # frame (an initial zero deadline and the 50 ms deadline).
        for _ in range(2):
            next_tick = state.next_tick_ms[batch_range, slot]
            remaining_ticks = state.ticks_remaining[batch_range, slot]
            deadline = torch.minimum(age, state.duration_ms[batch_range, slot])
            tick_due = area & (remaining_ticks > 0) & (next_tick <= deadline)
            _emit(
                events,
                tick_due,
                ObjectEventOpcode.AREA_TICK,
                source_id,
                player,
                x_units,
                y_units,
                amount,
                payload_id,
                payload_count,
            )
            if bool(tick_due.any().item()):
                due_batches = batch_range[tick_due]
                due_slots = slot[tick_due]
                state.ticks_remaining[due_batches, due_slots] -= 1
                state.next_tick_ms[due_batches, due_slots] += state.tick_interval_ms[
                    due_batches, due_slots
                ]

        area_expired = area & (age >= state.duration_ms[batch_range, slot])
        terminal |= area_expired
        timer_triggered = timer & (age >= state.activation_delay_ms[batch_range, slot])
        terminal |= timer_triggered

        spawn_output = terminal & (payload_count > 0)
        _emit(
            events,
            spawn_output,
            ObjectEventOpcode.SPAWN,
            source_id,
            player,
            torch.where(projectile, target_x, x_units),
            torch.where(projectile, target_y, y_units),
            amount,
            payload_id,
            payload_count,
        )
        _emit(
            events,
            terminal,
            ObjectEventOpcode.DEATH,
            source_id,
            player,
            torch.where(projectile, target_x, x_units),
            torch.where(projectile, target_y, y_units),
            amount,
            payload_id,
            payload_count,
        )

        child_blueprint = state.terminal_blueprint[batch_range, slot]
        append = terminal & (child_blueprint > 0)
        if bool(append.any().item()):
            append_batches = batch_range[append]
            free = ~state.allocated[append_batches]
            has_capacity = free.any(dim=1)
            if not bool(has_capacity.all().item()):
                raise RuntimeError("tensor object capacity exhausted")
            append_slots = free.to(torch.int8).argmax(dim=1).to(torch.int64)
            append_blueprints = child_blueprint[append].to(torch.int64)
            terminal_position_x = torch.where(projectile, target_x, x_units)[append]
            terminal_position_y = torch.where(projectile, target_y, y_units)[append]
            state._load_blueprints(
                append_batches,
                append_slots,
                append_blueprints,
                terminal_x=terminal_position_x,
                terminal_y=terminal_position_y,
                terminal_player=player[append],
            )
            state.object_id[append_batches, append_slots] = state.next_object_id[
                append_batches
            ]
            state.next_object_id[append_batches] += 1

        if bool(terminal.any().item()):
            terminal_batches = batch_range[terminal]
            terminal_slots = slot[terminal]
            state.active[terminal_batches, terminal_slots] = False

    return ObjectPhaseResult(
        events=events,
        unsupported_batch=unsupported,
        processed_count=processed_count,
    )
