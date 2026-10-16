"""Retained timed explosive/container terminal lifecycle kernels."""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import IntEnum

import torch

from clasher.data import CardDataLoader
from clasher.kinematics import NATIVE_MOVEMENT_SUBSTEP_UNITS
from clasher.native_tilemap import (
    STANDARD_PATH_HEIGHT,
    STANDARD_PATH_ROWS,
    STANDARD_PATH_WIDTH,
)

from .catalog import CardKindOpcode, TensorCardCatalog
from .entity_pool import CleanupSpawnTransition
from .movement import integer_sqrt_tensor, trunc_div_tensor
from .object_adapter import RuntimePayloadOpcode
from .objects import (
    ObjectBlueprint,
    ObjectEventOpcode,
    ObjectPhaseResult,
    TensorObjectCatalog,
    TensorObjectState,
)
from .resident_terminal_payloads import (
    TensorTerminalPayloadCatalog,
    _sin,
    _vector_angle,
)
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase


class TimedTerminalReason(IntEnum):
    NONE = 0
    UNSUPPORTED_PAYLOAD = 1
    ENTITY_CAPACITY = 2
    OBJECT_CAPACITY = 3
    EVENT_CAPACITY = 4


@dataclass(frozen=True)
class TimedTerminalPreflight:
    supported: torch.Tensor
    reason: torch.Tensor
    operation_row_by_slot: torch.Tensor
    object_count_by_slot: torch.Tensor


@dataclass
class TensorTimedTerminalState:
    objects: TensorObjectState
    operation_row: torch.Tensor
    facing_x_units: torch.Tensor
    facing_y_units: torch.Tensor
    freeze_expiry_time: torch.Tensor


@dataclass(frozen=True)
class TensorTimedTerminalEvents:
    batch_index: torch.Tensor
    object_slot: torch.Tensor
    object_id: torch.Tensor
    operation_row: torch.Tensor
    player: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    damage: torch.Tensor
    radius_units: torch.Tensor
    knockback_units: torch.Tensor
    child_row: torch.Tensor
    child_count: torch.Tensor
    facing_x_units: torch.Tensor
    facing_y_units: torch.Tensor
    freeze_expiry_time: torch.Tensor


@dataclass(frozen=True)
class TimedParentMaterialization:
    preflight: TimedTerminalPreflight
    committed: torch.Tensor
    transition: CleanupSpawnTransition
    object_slots: torch.Tensor


@dataclass(frozen=True)
class TimedChildMaterialization:
    committed: torch.Tensor
    reason: torch.Tensor
    transition: CleanupSpawnTransition
    child_travel_target_units: torch.Tensor
    child_travel_ticks: torch.Tensor
    child_target_distance_discount_sq_units: torch.Tensor


@dataclass
class TensorTimedTerminalCatalog:
    terminal: TensorTerminalPayloadCatalog
    objects: TensorObjectCatalog
    blueprint_by_operation: torch.Tensor
    timed_supported: torch.Tensor
    explosion_radius_units: torch.Tensor
    explosion_damage: torch.Tensor
    knockback_units: torch.Tensor
    nested_child_row: torch.Tensor
    nested_child_card: torch.Tensor
    root_angle_shift_degrees: torch.Tensor
    source_row_by_card: torch.Tensor
    _mapping_key: tuple[str, ...] | None = None
    _nested_core_cache: torch.Tensor | None = None

    @property
    def device(self) -> torch.device:
        return self.terminal.device

    @classmethod
    def compile(
        cls,
        loader: CardDataLoader,
        cards: TensorCardCatalog,
        root_names: tuple[str, ...] | list[str],
    ) -> TensorTimedTerminalCatalog:
        terminal = TensorTerminalPayloadCatalog.compile(loader, cards, root_names)
        spawn = terminal.spawn
        count = spawn.operation_count
        blueprint_by_operation = torch.zeros(
            count, dtype=torch.int64, device=terminal.device
        )
        supported = torch.zeros(count, dtype=torch.bool, device=terminal.device)
        radius = torch.zeros(count, dtype=torch.int32, device=terminal.device)
        damage = torch.zeros(count, dtype=torch.float64, device=terminal.device)
        knockback = torch.zeros(count, dtype=torch.int32, device=terminal.device)
        nested_row = torch.full((count,), -1, dtype=torch.int64, device=terminal.device)
        nested_card = torch.full_like(nested_row, -1)
        angle_shift = torch.zeros(count, dtype=torch.int32, device=terminal.device)
        records: list[ObjectBlueprint] = []
        record_rows: list[int] = []
        definitions = loader.load_card_definitions()

        for row in spawn.death_rows().detach().cpu().tolist():
            if int(spawn.depth[row].item()) != 0 or not bool(
                spawn.timed_explosive[row].item()
            ):
                continue
            mechanic = definitions[spawn.root_names[row]].mechanics[
                int(spawn.source_mechanic_slot[row].item())
            ]
            raw = getattr(mechanic, "unit_data", None) or {}
            raw_damage = float(raw.get("deathDamage", 0) or 0)
            stats = loader.get_card(spawn.root_names[row])
            scaler = getattr(stats, "get_scaled_stat", None)
            scaled_damage = (
                float(scaler(raw_damage)) if callable(scaler) else raw_damage
            )
            timer_ms = max(100, int(raw.get("deployTime", 1_000) or 1_000))
            radius[row] = int(
                raw.get("deathDamageRadius") or raw.get("deathRadius") or 2_000
            )
            damage[row] = scaled_damage
            knockback[row] = int(raw.get("deathPushback", 0) or 0)
            angle_shift[row] = round(float(getattr(stats, "spawn_angle_shift", 0) or 0))
            children = (
                (spawn.parent_row == row) & (spawn.depth == 1) & ~spawn.timed_explosive
            ).nonzero(as_tuple=False)[:, 0]
            child_row = int(children[0].item()) if children.numel() == 1 else -1
            if child_row >= 0:
                nested_row[row] = child_row
                nested_card[row] = terminal.cards.name_to_id.get(
                    spawn.unit_names[child_row], -1
                )
            child_count = 0 if child_row < 0 else int(spawn.count[child_row].item())
            supported[row] = bool(
                timer_ms % 50 == 0
                and (children.numel() <= 1)
                and (child_row < 0 or nested_card[row].item() >= 0)
            )
            records.append(
                ObjectBlueprint(
                    opcode=3,
                    activation_delay_ms=timer_ms,
                    amount=scaled_damage,
                    payload_id=int(RuntimePayloadOpcode.EXPLOSION),
                    payload_count=child_count,
                    inherit_terminal_position=True,
                    inherit_player=True,
                )
            )
            record_rows.append(row)

        object_catalog = TensorObjectCatalog.compile(records, device=terminal.device)
        for blueprint_id, row in enumerate(record_rows, start=1):
            blueprint_by_operation[row] = blueprint_id
        return cls(
            terminal=terminal,
            objects=object_catalog,
            blueprint_by_operation=blueprint_by_operation,
            timed_supported=supported,
            explosion_radius_units=radius,
            explosion_damage=damage,
            knockback_units=knockback,
            nested_child_row=nested_row,
            nested_child_card=nested_card,
            root_angle_shift_degrees=angle_shift,
            source_row_by_card=terminal.source_row_by_card,
        )

    def create_state(
        self, batch_size: int, max_objects: int
    ) -> TensorTimedTerminalState:
        objects = TensorObjectState.create(
            self.objects, [[] for _ in range(batch_size)], max_objects=max_objects
        )
        shape = objects.allocated.shape
        return TensorTimedTerminalState(
            objects=objects,
            operation_row=torch.full(shape, -1, dtype=torch.int64, device=self.device),
            facing_x_units=torch.zeros(shape, dtype=torch.int32, device=self.device),
            facing_y_units=torch.zeros(shape, dtype=torch.int32, device=self.device),
            freeze_expiry_time=torch.zeros(
                shape, dtype=torch.float64, device=self.device
            ),
        )

    def prepare_runtime(self, runtime: TensorBattleRuntime) -> None:
        nested_names = {
            self.terminal.spawn.unit_names[int(row.item())]
            for row in self.nested_child_row
            if int(row.item()) >= 0
        }
        current = runtime.battle.card_names
        names = ("", *sorted(set(current[1:]) | nested_names))
        if names != current:
            mapping = {name: index for index, name in enumerate(names)}
            old_to_new = torch.tensor(
                [mapping[name] for name in current],
                dtype=torch.int64,
                device=runtime.device,
            )
            for field in ("hand", "deck", "cycle_queue", "entity_card"):
                value = getattr(runtime.battle, field)
                value.copy_(old_to_new[value])
            runtime.battle.card_names = names
            runtime.battle.card_to_id = mapping
            runtime.card_catalog_index = torch.tensor(
                [
                    self.terminal.cards.name_to_id.get(name, -1) if name else 0
                    for name in names
                ],
                dtype=torch.int64,
                device=runtime.device,
            )
        self._mapping_key = None
        self._nested_core_cache = None

    def nested_core_ids(self, runtime: TensorBattleRuntime) -> torch.Tensor:
        self.prepare_runtime(runtime)
        if (
            self._mapping_key == runtime.battle.card_names
            and self._nested_core_cache is not None
        ):
            return self._nested_core_cache
        values = torch.full_like(self.nested_child_row, -1)
        valid = self.nested_child_row >= 0
        rows = self.nested_child_row[valid]
        names = [self.terminal.spawn.unit_names[int(row.item())] for row in rows]
        values[valid] = torch.tensor(
            [runtime.battle.card_to_id[name] for name in names],
            dtype=torch.int64,
            device=runtime.device,
        )
        self._mapping_key = runtime.battle.card_names
        self._nested_core_cache = values
        return values

    def coverage(self) -> dict[str, bool]:
        spawn = self.terminal.spawn
        return {
            spawn.root_names[row]: bool(self.timed_supported[row].item())
            for row in spawn.death_rows().detach().cpu().tolist()
            if int(spawn.depth[row].item()) == 0
            and bool(spawn.timed_explosive[row].item())
        }


def _empty_transition(runtime: TensorBattleRuntime) -> CleanupSpawnTransition:
    dead = torch.zeros_like(runtime.entity_pool.active)
    counts = torch.zeros_like(runtime.battle.entity_id)
    return runtime.entity_pool.cleanup_with_spawns(dead, counts)


def preflight_timed_parents(
    runtime: TensorBattleRuntime,
    catalog: TensorTimedTerminalCatalog,
    state: TensorTimedTerminalState,
    dead: torch.Tensor,
) -> TimedTerminalPreflight:
    if dead.shape != runtime.entity_pool.active.shape:
        raise ValueError("dead must have shape [batch, entity]")
    if state.objects.batch_size != runtime.batch_size:
        raise ValueError("object state batch differs from runtime")
    catalog.prepare_runtime(runtime)
    dead = dead.to(torch.bool) & runtime.entity_pool.active
    core = runtime.card_catalog_index[runtime.battle.entity_card]
    operation = catalog.source_row_by_card[core.clamp_min(0)]
    safe = operation.clamp_min(0)
    timed = (operation >= 0) & catalog.terminal.spawn.timed_explosive[safe]
    represented = timed & catalog.timed_supported[safe]
    unsupported = (dead & ~represented).any(dim=1)
    counts = torch.where(dead & represented, catalog.terminal.spawn.count[safe], 0).to(
        torch.int64
    )
    total = counts.sum(dim=1, dtype=torch.int64)
    live_after = runtime.entity_pool.active.sum(dim=1) - dead.sum(dim=1)
    entity_overflow = live_after + total > runtime.max_entities
    free_objects = (~state.objects.allocated).sum(dim=1, dtype=torch.int64)
    object_overflow = total > free_objects
    event_overflow = (
        runtime.events.count.to(torch.int64) + total > runtime.events.capacity
    )
    reason = torch.where(
        unsupported,
        int(TimedTerminalReason.UNSUPPORTED_PAYLOAD),
        torch.where(
            entity_overflow,
            int(TimedTerminalReason.ENTITY_CAPACITY),
            torch.where(
                object_overflow,
                int(TimedTerminalReason.OBJECT_CAPACITY),
                torch.where(
                    event_overflow,
                    int(TimedTerminalReason.EVENT_CAPACITY),
                    int(TimedTerminalReason.NONE),
                ),
            ),
        ),
    ).to(torch.int16)
    return TimedTerminalPreflight(
        supported=runtime.supported & (reason == 0),
        reason=reason,
        operation_row_by_slot=operation,
        object_count_by_slot=counts,
    )


def _clear_entity_slots_(
    runtime: TensorBattleRuntime, rows: torch.Tensor, slots: torch.Tensor
) -> None:
    index = (rows, slots)
    for owner in (runtime.battle, runtime.status, runtime.phases):
        for descriptor in fields(owner):
            value = getattr(owner, descriptor.name)
            if (
                isinstance(value, torch.Tensor)
                and value.ndim >= 2
                and value.shape[:2] == runtime.entity_pool.active.shape
                and not (owner is runtime.battle and descriptor.name == "entity_id")
            ):
                value[index] = 0
    runtime.phases.target_slot[index] = -1
    runtime.battle.entity_tower_slot[index] = -1


def materialize_timed_parents_(
    runtime: TensorBattleRuntime,
    catalog: TensorTimedTerminalCatalog,
    state: TensorTimedTerminalState,
    dead: torch.Tensor,
    *,
    facing_x_units: torch.Tensor,
    facing_y_units: torch.Tensor,
) -> TimedParentMaterialization:
    if facing_x_units.shape != dead.shape or facing_y_units.shape != dead.shape:
        raise ValueError("facing planes must match dead")
    preflight = preflight_timed_parents(runtime, catalog, state, dead)
    effective = dead.to(torch.bool) & preflight.supported[:, None]
    counts = torch.where(
        effective,
        preflight.object_count_by_slot,
        torch.zeros_like(preflight.object_count_by_slot),
    )
    ordered = runtime.entity_pool.id_order(effective)
    parent_slots = ordered.slots.clamp_min(0)
    parent_operation = preflight.operation_row_by_slot.gather(1, parent_slots)
    parent_player = runtime.battle.entity_player.gather(1, parent_slots)
    parent_x = runtime.battle.entity_x_units.gather(1, parent_slots)
    parent_y = runtime.battle.entity_y_units.gather(1, parent_slots)
    parent_card = runtime.battle.entity_card.gather(1, parent_slots)
    parent_facing_x = facing_x_units.gather(1, parent_slots)
    parent_facing_y = facing_y_units.gather(1, parent_slots)
    parent_freeze = runtime.status.freeze_expiry_time.gather(1, parent_slots)
    transition = runtime.entity_pool.cleanup_with_spawns(effective, counts)
    valid = transition.spawned.valid
    batch = torch.arange(runtime.batch_size, device=runtime.device)[:, None].expand_as(
        valid
    )
    local = torch.arange(runtime.max_entities, device=runtime.device)[
        None, :
    ].expand_as(valid)
    cumulative = counts.gather(1, parent_slots).cumsum(dim=1)
    belongs = local[:, :, None] < cumulative[:, None, :]
    parent_ordinal = belongs.to(torch.int64).argmax(dim=2)
    operation = parent_operation.gather(1, parent_ordinal)
    player = parent_player.gather(1, parent_ordinal)
    x = parent_x.gather(1, parent_ordinal)
    y = parent_y.gather(1, parent_ordinal)
    card = parent_card.gather(1, parent_ordinal)
    fx = parent_facing_x.gather(1, parent_ordinal)
    fy = parent_facing_y.gather(1, parent_ordinal)
    freeze = parent_freeze.gather(1, parent_ordinal)
    free = ~state.objects.allocated
    sentinel = state.objects.max_objects
    free_order = torch.argsort(
        torch.where(
            free,
            torch.arange(state.objects.max_objects, device=runtime.device)[None, :],
            sentinel,
        ),
        dim=1,
        stable=True,
    )
    object_slot = free_order.gather(1, local.clamp_max(state.objects.max_objects - 1))
    selected = valid
    rows = batch[selected]
    entity_slots = transition.spawned.slots[selected]
    object_slots = object_slot[selected]
    op = operation[selected]
    _clear_entity_slots_(runtime, rows, entity_slots)
    runtime.battle.entity_active[rows, entity_slots] = True
    runtime.battle.entity_kind[rows, entity_slots] = 2
    runtime.battle.entity_player[rows, entity_slots] = player[selected]
    runtime.battle.entity_card[rows, entity_slots] = card[selected]
    runtime.battle.entity_x_units[rows, entity_slots] = x[selected]
    runtime.battle.entity_y_units[rows, entity_slots] = y[selected]
    runtime.battle.entity_hp[rows, entity_slots] = 1.0
    runtime.battle.entity_max_hp[rows, entity_slots] = 1.0
    blueprint = catalog.blueprint_by_operation[op]
    state.objects._load_blueprints(
        rows,
        object_slots,
        blueprint,
        terminal_x=x[selected],
        terminal_y=y[selected],
        terminal_player=player[selected],
    )
    state.objects.object_id[rows, object_slots] = transition.spawned.entity_ids[
        selected
    ]
    state.operation_row[rows, object_slots] = op
    state.facing_x_units[rows, object_slots] = fx[selected].to(torch.int32)
    state.facing_y_units[rows, object_slots] = fy[selected].to(torch.int32)
    carries = catalog.nested_child_row[op] >= 0
    state.freeze_expiry_time[rows, object_slots] = torch.where(
        carries, freeze[selected], 0.0
    )
    state.objects.next_object_id.copy_(runtime.entity_pool.next_entity_id)
    runtime.battle.entity_id.copy_(runtime.entity_pool.entity_id)
    runtime.events.append(
        phase=TickPhase.CLEANUP_AND_SPAWNS,
        opcode=RuntimeEventOpcode.SPAWN,
        valid=valid,
        source_id=transition.spawn_parent_ids,
        target_id=transition.spawned.entity_ids,
        x_units=x,
        y_units=y,
        payload=operation,
    )
    runtime.mark_dirty(effective.any(dim=1), phase=TickPhase.CLEANUP_AND_SPAWNS)
    runtime.assert_invariants()
    return TimedParentMaterialization(
        preflight, preflight.supported, transition, object_slot
    )


def plan_timed_terminal_events(
    catalog: TensorTimedTerminalCatalog,
    state: TensorTimedTerminalState,
    result: ObjectPhaseResult,
) -> TensorTimedTerminalEvents:
    events = result.events
    position = torch.arange(events.opcode.shape[1], device=state.objects.device)[
        None, :
    ]
    terminal = (position < events.count[:, None]) & (
        events.opcode == int(ObjectEventOpcode.DEATH)
    )
    coordinates = torch.nonzero(terminal, as_tuple=False)
    batch = coordinates[:, 0]
    lane = coordinates[:, 1]
    source_id = events.source_id[batch, lane]
    matches = state.objects.allocated[batch] & (
        state.objects.object_id[batch] == source_id[:, None]
    )
    slot = matches.to(torch.int64).argmax(dim=1)
    row = state.operation_row[batch, slot]
    child_row = catalog.nested_child_row[row]
    return TensorTimedTerminalEvents(
        batch_index=batch,
        object_slot=slot,
        object_id=source_id,
        operation_row=row,
        player=events.player[batch, lane],
        x_units=events.x_units[batch, lane],
        y_units=events.y_units[batch, lane],
        damage=events.amount[batch, lane],
        radius_units=catalog.explosion_radius_units[row],
        knockback_units=catalog.knockback_units[row],
        child_row=child_row,
        child_count=torch.where(
            child_row >= 0, catalog.terminal.spawn.count[child_row.clamp_min(0)], 0
        ),
        facing_x_units=state.facing_x_units[batch, slot],
        facing_y_units=state.facing_y_units[batch, slot],
        freeze_expiry_time=state.freeze_expiry_time[batch, slot],
    )


def _lane_id(position: torch.Tensor) -> torch.Tensor:
    x = torch.div(position[:, 0], 500, rounding_mode="trunc")
    y = torch.div(position[:, 1], 500, rounding_mode="trunc")
    cx = torch.arange(STANDARD_PATH_WIDTH, device=position.device).repeat_interleave(
        STANDARD_PATH_HEIGHT
    )
    cy = torch.arange(STANDARD_PATH_HEIGHT, device=position.device).repeat(
        STANDARD_PATH_WIDTH
    )
    lane = torch.tensor(
        [
            ord(STANDARD_PATH_ROWS[j][i]) - ord("0")
            for i in range(STANDARD_PATH_WIDTH)
            for j in range(STANDARD_PATH_HEIGHT)
        ],
        dtype=torch.int64,
        device=position.device,
    )
    distance = (cx - x[:, None]).square() + (cy - y[:, None]).square()
    selected = torch.argmin(
        torch.where(lane > 0, distance, torch.iinfo(torch.int64).max), dim=1
    )
    return lane[selected]


def materialize_timed_children_(
    runtime: TensorBattleRuntime,
    catalog: TensorTimedTerminalCatalog,
    state: TensorTimedTerminalState,
    terminal: TensorTimedTerminalEvents,
) -> TimedChildMaterialization:
    batch_size = runtime.batch_size
    counts = torch.zeros(
        (batch_size, runtime.max_entities), dtype=torch.int64, device=runtime.device
    )
    matches = runtime.entity_pool.active[terminal.batch_index] & (
        runtime.battle.entity_id[terminal.batch_index] == terminal.object_id[:, None]
    )
    source_slot = matches.to(torch.int64).argmax(dim=1)
    counts[terminal.batch_index, source_slot] = terminal.child_count.to(torch.int64)
    dead = torch.zeros_like(runtime.entity_pool.active)
    dead[terminal.batch_index, source_slot] = True
    total = counts.sum(dim=1)
    live_after = runtime.entity_pool.active.sum(dim=1) - dead.sum(dim=1)
    entity_overflow = live_after + total > runtime.max_entities
    event_overflow = (
        runtime.events.count.to(torch.int64) + total + dead.sum(dim=1)
        > runtime.events.capacity
    )
    supported = runtime.supported & ~entity_overflow & ~event_overflow
    reason = torch.where(
        entity_overflow,
        int(TimedTerminalReason.ENTITY_CAPACITY),
        torch.where(event_overflow, int(TimedTerminalReason.EVENT_CAPACITY), 0),
    ).to(torch.int16)
    effective_dead = dead & supported[:, None]
    dead_source_id = torch.where(
        effective_dead,
        runtime.battle.entity_id,
        torch.zeros_like(runtime.battle.entity_id),
    )
    effective_counts = torch.where(effective_dead, counts, 0)
    transition = runtime.entity_pool.cleanup_with_spawns(
        effective_dead, effective_counts
    )
    capacity = runtime.max_entities
    travel_target = torch.zeros(
        (batch_size, capacity, 2), dtype=torch.int64, device=runtime.device
    )
    travel_ticks = torch.zeros(
        (batch_size, capacity), dtype=torch.int64, device=runtime.device
    )
    discount = torch.zeros_like(travel_ticks)
    valid = transition.spawned.valid
    if bool(valid.any().item()):
        rows_grid = torch.arange(batch_size, device=runtime.device)[:, None].expand_as(
            valid
        )
        local = torch.arange(capacity, device=runtime.device)[None, :].expand_as(valid)
        rows = rows_grid[valid]
        slots = transition.spawned.slots[valid]
        parent_id = transition.spawn_parent_ids[valid]
        event_match = (terminal.batch_index[:, None] == rows[None, :]) & (
            terminal.object_id[:, None] == parent_id[None, :]
        )
        event_index = event_match.to(torch.int64).argmax(dim=0)
        child_row = terminal.child_row[event_index]
        child_card = catalog.nested_child_card[terminal.operation_row[event_index]]
        child_core = catalog.nested_core_ids(runtime)[
            terminal.operation_row[event_index]
        ]
        terminal_order = torch.arange(
            terminal.batch_index.numel(), device=runtime.device
        )
        prior = (terminal.batch_index[:, None] == terminal.batch_index[None, :]) & (
            terminal_order[:, None] > terminal_order[None, :]
        )
        event_start = (prior * terminal.child_count[None, :].to(torch.int64)).sum(dim=1)
        formation = local[valid] - event_start[event_index]
        count = terminal.child_count[event_index].clamp_min(1)
        shift = catalog.root_angle_shift_degrees[
            terminal.operation_row[event_index]
        ].to(torch.int64)
        base = torch.where(
            shift != 0,
            _vector_angle(
                terminal.facing_x_units[event_index],
                terminal.facing_y_units[event_index],
            )
            + shift,
            0,
        )
        angle = base + trunc_div_tensor((count - 1 - formation) * 360, count)
        radius = catalog.terminal.spawn.radius_units[child_row].to(torch.int64)
        target_x = terminal.x_units[event_index].to(torch.int64) + _sin(
            angle + 90, radius
        )
        target_y = terminal.y_units[event_index].to(torch.int64) + _sin(angle, radius)
        const = catalog.terminal.spawn.spawn_const_priority[child_row]
        flip_x = const & (
            _lane_id(
                torch.stack(
                    (terminal.x_units[event_index], terminal.y_units[event_index]),
                    dim=1,
                )
            )
            == 1
        )
        flip_y = const & (terminal.player[event_index] == 1)
        target_x = torch.where(
            flip_x, 2 * terminal.x_units[event_index] - target_x, target_x
        )
        target_y = torch.where(
            flip_y, 2 * terminal.y_units[event_index] - target_y, target_y
        )
        radial = catalog.terminal.spawn.radial_pushback[child_row] & (radius > 0)
        x = torch.where(radial, terminal.x_units[event_index].to(torch.int64), target_x)
        y = torch.where(radial, terminal.y_units[event_index].to(torch.int64), target_y)
        _clear_entity_slots_(runtime, rows, slots)
        index = (rows, slots)
        runtime.battle.entity_active[index] = True
        runtime.battle.entity_kind[index] = int(CardKindOpcode.TROOP)
        runtime.battle.entity_player[index] = terminal.player[event_index]
        runtime.battle.entity_card[index] = child_core
        runtime.battle.entity_x_units[index] = x.to(torch.int32)
        runtime.battle.entity_y_units[index] = y.to(torch.int32)
        runtime.battle.entity_hp[index] = catalog.terminal.cards.hitpoints[child_card]
        runtime.battle.entity_hp_integer_kind[index] = (
            catalog.terminal.deployment.hitpoints_integer_kind[child_card]
        )
        runtime.battle.entity_max_hp[index] = catalog.terminal.cards.hitpoints[
            child_card
        ]
        delay_ms = catalog.terminal.spawn.deploy_time_ms[child_row].to(torch.int64)
        runtime.battle.entity_deploy_delay[index] = delay_ms.to(torch.float64) / 1_000.0
        pending = delay_ms > 0
        runtime.battle.entity_placement_pending[index] = pending
        runtime.battle.entity_spawn_hook_pending[index] = pending
        runtime.battle.entity_spawn_hook_fired[index] = ~pending
        runtime.status.freeze_expiry_time[index] = terminal.freeze_expiry_time[
            event_index
        ]
        delta_x = target_x - x
        delta_y = target_y - y
        ticks = torch.div(
            integer_sqrt_tensor(delta_x.square() + delta_y.square()),
            NATIVE_MOVEMENT_SUBSTEP_UNITS,
            rounding_mode="floor",
        )
        travel_target[index] = torch.stack((target_x, target_y), dim=1)
        travel_ticks[index] = torch.where(radial, ticks, 0)
        step = formation * 80
        discount[index] = torch.where(const, step * step, 0)
    runtime.battle.entity_id.copy_(runtime.entity_pool.entity_id)
    runtime.events.append(
        phase=TickPhase.CLEANUP_AND_SPAWNS,
        opcode=RuntimeEventOpcode.DEATH,
        valid=effective_dead,
        source_id=dead_source_id,
    )
    runtime.events.append(
        phase=TickPhase.CLEANUP_AND_SPAWNS,
        opcode=RuntimeEventOpcode.SPAWN,
        valid=transition.spawned.valid,
        source_id=transition.spawn_parent_ids,
        target_id=transition.spawned.entity_ids,
    )
    state.objects.allocated[terminal.batch_index, terminal.object_slot] &= ~supported[
        terminal.batch_index
    ]
    state.objects.next_object_id.copy_(runtime.entity_pool.next_entity_id)
    runtime.assert_invariants()
    return TimedChildMaterialization(
        supported, reason, transition, travel_target, travel_ticks, discount
    )


__all__ = [
    "TensorTimedTerminalCatalog",
    "TensorTimedTerminalEvents",
    "TensorTimedTerminalState",
    "TimedChildMaterialization",
    "TimedParentMaterialization",
    "TimedTerminalPreflight",
    "TimedTerminalReason",
    "materialize_timed_children_",
    "materialize_timed_parents_",
    "plan_timed_terminal_events",
    "preflight_timed_parents",
]
