"""Retained materialization for serialized ``PeriodicSpawner`` mechanics."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, fields
from enum import IntEnum

import torch

from clasher.data import CardDataLoader
from clasher.factory.dynamic_factory import troop_from_character_data

from .catalog import CardKindOpcode, TensorCardCatalog
from .deployment import TensorDeploymentCatalog
from .entity_pool import EntityAllocation
from .resident_terminal_payloads import _SPAWN_BLOCKED, _sin, _vector_angle
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase
from .spawn import (
    TensorPeriodicSpawnerState,
    TensorSpawnCatalog,
    TensorSpawnEvents,
    step_periodic_spawners,
)


class PeriodicSpawnerReason(IntEnum):
    NONE = 0
    ENTITY_CAPACITY = 1
    EVENT_CAPACITY = 2
    UNKNOWN_CHILD = 3


class _PeriodicCatalogLoader(CardDataLoader):
    def __init__(self, source: CardDataLoader) -> None:
        self.data_file = source.data_file
        self._card_definitions = dict(source.load_card_definitions())
        self._cards = {}

    def add_character(self, name: str, data: dict[str, object]) -> None:
        if name in self._card_definitions:
            return
        rarity = str(data.get("rarity", "Common"))
        stats = troop_from_character_data(name, data, elixir=0, rarity=rarity)
        self._cards[name] = stats
        self._card_definitions[name] = stats.card_definition


@dataclass
class TensorPeriodicSpawnerCatalog:
    cards: TensorCardCatalog
    deployment: TensorDeploymentCatalog
    spawn: TensorSpawnCatalog
    source_row_by_card: torch.Tensor
    child_card_id: torch.Tensor
    _mapping_key: tuple[str, ...] | None = None
    _child_core_cache: torch.Tensor | None = None

    @property
    def device(self) -> torch.device:
        return self.cards.device

    @classmethod
    def compile(
        cls,
        loader: CardDataLoader,
        cards: TensorCardCatalog,
        root_names: Sequence[str],
    ) -> TensorPeriodicSpawnerCatalog:
        spawn = TensorSpawnCatalog.compile(loader, root_names, device=cards.device)
        definitions = loader.load_card_definitions()
        overlay = _PeriodicCatalogLoader(loader)
        required = set(cards.names[1:])
        periodic_rows = spawn.periodic_rows().detach().cpu().tolist()
        source_aliases: dict[int, set[str]] = {}
        for row in periodic_rows:
            stats = loader.get_card(spawn.root_names[row])
            aliases = {
                spawn.source_names[row],
                spawn.root_names[row],
                str(getattr(stats, "name", "") or ""),
            }
            aliases.discard("")
            source_aliases[row] = aliases
            required.update(aliases)
            required.add(spawn.unit_names[row])
            mechanic = definitions[spawn.source_names[row]].mechanics[
                int(spawn.source_mechanic_slot[row].item())
            ]
            unit_data = getattr(mechanic, "unit_data", None)
            if isinstance(unit_data, dict):
                overlay.add_character(spawn.unit_names[row], unit_data)
        if not required.issubset(cards.name_to_id):
            cards = TensorCardCatalog.compile(
                overlay, tuple(sorted(required)), device=cards.device
            )
        deployment = TensorDeploymentCatalog.compile(overlay, cards)
        source_row = torch.full(
            (len(cards.names),), -1, dtype=torch.int64, device=cards.device
        )
        child_card = torch.full(
            (spawn.operation_count,), -1, dtype=torch.int64, device=cards.device
        )
        for row in periodic_rows:
            child_id = cards.name_to_id.get(spawn.unit_names[row], -1)
            for source_name in source_aliases[row]:
                source_id = cards.name_to_id.get(source_name, -1)
                if source_id >= 0:
                    source_row[source_id] = row
            child_card[row] = child_id
        return cls(cards, deployment, spawn, source_row, child_card)

    def prepare_runtime(self, runtime: TensorBattleRuntime) -> None:
        required = {
            self.spawn.unit_names[row]
            for row in self.spawn.periodic_rows().detach().cpu().tolist()
        }
        current = runtime.battle.card_names
        names = ("", *sorted(set(current[1:]) | required))
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
                [self.cards.name_to_id.get(name, -1) if name else 0 for name in names],
                dtype=torch.int64,
                device=runtime.device,
            )
        self._mapping_key = None
        self._child_core_cache = None

    def child_core_ids(self, runtime: TensorBattleRuntime) -> torch.Tensor:
        self.prepare_runtime(runtime)
        if (
            self._mapping_key == runtime.battle.card_names
            and self._child_core_cache is not None
        ):
            return self._child_core_cache
        values = torch.full(
            (self.spawn.operation_count,), -1, dtype=torch.int64, device=runtime.device
        )
        for row in self.spawn.periodic_rows().detach().cpu().tolist():
            values[row] = runtime.battle.card_to_id.get(self.spawn.unit_names[row], -1)
        self._mapping_key = runtime.battle.card_names
        self._child_core_cache = values
        return values


@dataclass
class TensorPeriodicSpawnerRuntimeState:
    source_entity_id: torch.Tensor
    operation_row: torch.Tensor
    time_since_spawn_ms: torch.Tensor
    spawns_created: torch.Tensor
    pending_units: torch.Tensor
    time_since_unit_spawn_ms: torch.Tensor
    current_wave_spawned: torch.Tensor

    @classmethod
    def zeros(
        cls,
        runtime: TensorBattleRuntime,
    ) -> TensorPeriodicSpawnerRuntimeState:
        shape = runtime.battle.entity_id.shape
        zeros_i64 = torch.zeros(shape, dtype=torch.int64, device=runtime.device)
        zeros_f64 = torch.zeros(shape, dtype=torch.float64, device=runtime.device)
        return cls(
            source_entity_id=zeros_i64.clone(),
            operation_row=torch.full_like(zeros_i64, -1),
            time_since_spawn_ms=zeros_f64.clone(),
            spawns_created=zeros_i64.clone(),
            pending_units=zeros_i64.clone(),
            time_since_unit_spawn_ms=zeros_f64.clone(),
            current_wave_spawned=zeros_i64.clone(),
        )

    def clone(self) -> TensorPeriodicSpawnerRuntimeState:
        return type(self)(
            **{
                descriptor.name: getattr(self, descriptor.name).clone()
                for descriptor in fields(self)
            }
        )

    def fork(
        self, rows: Sequence[int] | torch.Tensor
    ) -> TensorPeriodicSpawnerRuntimeState:
        index = torch.as_tensor(
            rows, dtype=torch.int64, device=self.source_entity_id.device
        )
        return type(self)(
            **{
                descriptor.name: getattr(self, descriptor.name)
                .index_select(0, index)
                .clone()
                for descriptor in fields(self)
            }
        )

    def reset_(self, mask: torch.Tensor) -> None:
        selected = torch.as_tensor(
            mask, dtype=torch.bool, device=self.source_entity_id.device
        )
        if selected.shape != self.source_entity_id.shape:
            raise ValueError("reset mask must have shape [batch, entity]")
        for descriptor in fields(self):
            value = getattr(self, descriptor.name)
            value.masked_fill_(
                selected, -1 if descriptor.name == "operation_row" else 0
            )


@dataclass(frozen=True)
class TensorPeriodicSpawnerResult:
    committed: torch.Tensor
    reason: torch.Tensor
    schedule: TensorSpawnEvents
    allocation: EntityAllocation
    child_source_id: torch.Tensor
    child_formation_index: torch.Tensor
    child_wave_size: torch.Tensor
    child_target_distance_discount_sq_units: torch.Tensor


def _clear_slots_(
    runtime: TensorBattleRuntime,
    rows: torch.Tensor,
    slots: torch.Tensor,
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


def _copy_rows_(destination: object, source: object, rows: torch.Tensor) -> None:
    batch = int(rows.shape[0])
    for descriptor in fields(destination):  # type: ignore[arg-type]
        left = getattr(destination, descriptor.name)
        right = getattr(source, descriptor.name)
        if (
            isinstance(left, torch.Tensor)
            and left.ndim > 0
            and left.shape[0] == batch
            and isinstance(right, torch.Tensor)
        ):
            left[rows] = right[rows]


def _refresh_sources_(
    runtime: TensorBattleRuntime,
    catalog: TensorPeriodicSpawnerCatalog,
    state: TensorPeriodicSpawnerRuntimeState,
) -> torch.Tensor:
    core = runtime.card_catalog_index[runtime.battle.entity_card]
    operation = catalog.source_row_by_card[core.clamp_min(0)]
    active = (
        runtime.entity_pool.active
        & runtime.battle.entity_active
        & (operation >= 0)
        & ((runtime.battle.entity_kind == 0) | (runtime.battle.entity_kind == 1))
        & ~runtime.battle.entity_placement_pending
        & (runtime.battle.entity_deploy_delay <= 1e-9)
    )
    identity_changed = state.source_entity_id != runtime.battle.entity_id
    state.reset_(identity_changed | ~active)
    state.source_entity_id.copy_(
        torch.where(active, runtime.battle.entity_id, state.source_entity_id)
    )
    state.operation_row.copy_(torch.where(active, operation, state.operation_row))
    return active


def _positions(
    runtime: TensorBattleRuntime,
    catalog: TensorPeriodicSpawnerCatalog,
    events: TensorSpawnEvents,
    source_slots: torch.Tensor,
    facing_x: torch.Tensor,
    facing_y: torch.Tensor,
) -> torch.Tensor:
    rows = events.batch_index
    operation = events.catalog_row
    source_x = runtime.battle.entity_x_units[rows, source_slots].to(torch.int64)
    source_y = runtime.battle.entity_y_units[rows, source_slots].to(torch.int64)
    radius = catalog.spawn.radius_units[operation].to(torch.int64)
    wave = events.wave_size.clamp_min(1)
    shift = catalog.spawn.spawn_angle_shift_degrees[operation].round().to(torch.int64)
    base = torch.where(
        shift != 0,
        _vector_angle(facing_x.to(torch.int64), facing_y.to(torch.int64)) + shift,
        0,
    )
    angle = base + torch.div(
        (wave - 1 - events.formation_index) * 360,
        wave,
        rounding_mode="trunc",
    )
    radial_x = source_x + _sin(angle + 90, radius)
    radial_y = source_y + _sin(angle, radius)

    child = catalog.child_card_id[operation]
    parent_core = runtime.card_catalog_index[
        runtime.battle.entity_card[rows, source_slots]
    ].clamp_min(0)
    parent_radius = catalog.cards.collision_radius_units[parent_core].to(torch.int64)
    child_radius = catalog.cards.collision_radius_units[child.clamp_min(0)].to(
        torch.int64
    )
    distance = parent_radius + child_radius
    zero = torch.zeros_like(distance)
    offset_x = torch.stack((zero, -distance, zero, distance), dim=1)
    offset_y = torch.stack((distance, zero, -distance, zero), dim=1)
    offset_x = torch.where((source_x > 9_000)[:, None], -offset_x, offset_x)
    player = runtime.battle.entity_player[rows, source_slots]
    offset_y = torch.where((player == 1)[:, None], -offset_y, offset_y)
    candidates = torch.stack(
        (source_x[:, None] + offset_x, source_y[:, None] + offset_y), dim=2
    )
    candidate_x = candidates[:, :, 0]
    candidate_y = candidates[:, :, 1]
    bounds = (
        (candidate_x - child_radius[:, None] >= 0)
        & (candidate_y - child_radius[:, None] >= 0)
        & (candidate_x + child_radius[:, None] < 18_000)
        & (candidate_y + child_radius[:, None] < 32_000)
    )
    min_x = torch.div(candidate_x - child_radius[:, None], 500, rounding_mode="floor")
    max_x = torch.div(
        candidate_x + child_radius[:, None] - 1, 500, rounding_mode="floor"
    )
    min_y = torch.div(candidate_y - child_radius[:, None], 500, rounding_mode="floor")
    max_y = torch.div(
        candidate_y + child_radius[:, None] - 1, 500, rounding_mode="floor"
    )
    tile_x = torch.arange(36, device=runtime.device).view(1, 1, 36, 1)
    tile_y = torch.arange(64, device=runtime.device).view(1, 1, 1, 64)
    covered = (
        (tile_x >= min_x[:, :, None, None])
        & (tile_x <= max_x[:, :, None, None])
        & (tile_y >= min_y[:, :, None, None])
        & (tile_y <= max_y[:, :, None, None])
    )
    blocked = torch.tensor(_SPAWN_BLOCKED, dtype=torch.bool, device=runtime.device)
    valid = bounds & ~(covered & blocked[None, None, :, :]).any(dim=(2, 3))
    selected = valid.to(torch.int64).argmax(dim=1)
    exists = valid.any(dim=1)
    event_index = torch.arange(rows.numel(), device=runtime.device)
    terrain_x = candidate_x[event_index, selected]
    terrain_y = candidate_y[event_index, selected]
    terrain = torch.stack(
        (
            torch.where(exists, terrain_x, source_x + 1),
            torch.where(exists, terrain_y, source_y),
        ),
        dim=1,
    )
    return torch.where(
        (radius > 0)[:, None],
        torch.stack((radial_x, radial_y), dim=1),
        terrain,
    )


def step_runtime_periodic_spawners_(
    runtime: TensorBattleRuntime,
    catalog: TensorPeriodicSpawnerCatalog,
    state: TensorPeriodicSpawnerRuntimeState,
    *,
    dt_ms: float | torch.Tensor = 50.0,
    stunned: torch.Tensor | None = None,
    spawn_rate: torch.Tensor | None = None,
    facing_x_units: torch.Tensor | None = None,
    facing_y_units: torch.Tensor | None = None,
) -> TensorPeriodicSpawnerResult:
    """Advance and materialize all live sources transactionally by battle row."""

    catalog.prepare_runtime(runtime)
    working = runtime.clone()
    working.battle.rng = runtime.battle.rng.clone()
    preview = state.clone()
    active = _refresh_sources_(working, catalog, preview)
    frozen = (
        torch.zeros_like(active)
        if stunned is None
        else torch.as_tensor(stunned, dtype=torch.bool, device=runtime.device)
    )
    rate = (
        torch.ones_like(preview.time_since_spawn_ms)
        if spawn_rate is None
        else torch.as_tensor(spawn_rate, dtype=torch.float64, device=runtime.device)
    )
    if frozen.shape != active.shape or rate.shape != active.shape:
        raise ValueError("stunned and spawn_rate must have shape [batch, entity]")
    order = working.entity_pool.id_order(active)
    slots = order.slots.clamp_min(0)
    fallback = catalog.spawn.periodic_rows()[0]
    operation = preview.operation_row.gather(1, slots)
    operation = torch.where(order.valid, operation, fallback)
    compact = TensorPeriodicSpawnerState(
        preview.time_since_spawn_ms.gather(1, slots).clone(),
        preview.spawns_created.gather(1, slots).clone(),
        preview.pending_units.gather(1, slots).clone(),
        preview.time_since_unit_spawn_ms.gather(1, slots).clone(),
        preview.current_wave_spawned.gather(1, slots).clone(),
    )
    schedule = step_periodic_spawners(
        catalog.spawn,
        compact,
        dt_ms,
        operation_rows=operation,
        active=order.valid & ~frozen.gather(1, slots),
        spawn_rate=rate.gather(1, slots),
    )
    for destination, source in (
        (preview.time_since_spawn_ms, compact.time_since_spawn_ms),
        (preview.spawns_created, compact.spawns_created),
        (preview.pending_units, compact.pending_units),
        (preview.time_since_unit_spawn_ms, compact.time_since_unit_spawn_ms),
        (preview.current_wave_spawned, compact.current_wave_spawned),
    ):
        batch_index, ordered_index = torch.where(order.valid)
        destination[batch_index, slots[batch_index, ordered_index]] = source[
            batch_index, ordered_index
        ]

    counts = torch.bincount(schedule.batch_index, minlength=runtime.batch_size)
    available = (~working.entity_pool.active).sum(dim=1)
    entity_overflow = counts > available
    event_overflow = (
        working.events.count.to(torch.int64) + counts > working.events.capacity
    )
    unknown = torch.zeros(runtime.batch_size, dtype=torch.bool, device=runtime.device)
    if schedule.catalog_row.numel():
        invalid = catalog.child_card_id[schedule.catalog_row] < 0
        unknown.scatter_reduce_(
            0,
            schedule.batch_index,
            invalid,
            reduce="amax",
            include_self=True,
        )
    committed = runtime.supported & ~entity_overflow & ~event_overflow & ~unknown
    reason = torch.where(
        entity_overflow,
        int(PeriodicSpawnerReason.ENTITY_CAPACITY),
        torch.where(
            event_overflow,
            int(PeriodicSpawnerReason.EVENT_CAPACITY),
            torch.where(unknown, int(PeriodicSpawnerReason.UNKNOWN_CHILD), 0),
        ),
    ).to(torch.int16)
    effective_counts = torch.where(committed, counts, 0)
    allocation = working.entity_pool.allocate(effective_counts)
    event_keep = committed[schedule.batch_index]
    event_batch = schedule.batch_index[event_keep]
    event_source_column = schedule.source_column[event_keep]
    event_operation = schedule.catalog_row[event_keep]
    source_slots = slots[event_batch, event_source_column]
    source_ids = working.battle.entity_id[event_batch, source_slots]
    event_ordinal = torch.arange(schedule.batch_index.numel(), device=runtime.device)
    prior = (schedule.batch_index[:, None] == schedule.batch_index[None, :]) & (
        event_ordinal[:, None] > event_ordinal[None, :]
    )
    local = prior.sum(dim=1)[event_keep]
    child_slots = allocation.slots[event_batch, local]
    fx_plane = (
        torch.zeros_like(working.battle.entity_x_units)
        if facing_x_units is None
        else facing_x_units
    )
    fy_plane = (
        torch.zeros_like(working.battle.entity_y_units)
        if facing_y_units is None
        else facing_y_units
    )
    position = _positions(
        working,
        catalog,
        TensorSpawnEvents(
            event_batch,
            event_source_column,
            event_operation,
            schedule.formation_index[event_keep],
            schedule.wave_size[event_keep],
        ),
        source_slots,
        fx_plane[event_batch, source_slots],
        fy_plane[event_batch, source_slots],
    )
    _clear_slots_(working, event_batch, child_slots)
    index = (event_batch, child_slots)
    child_card = catalog.child_card_id[event_operation]
    child_core = catalog.child_core_ids(working)[event_operation]
    working.battle.entity_active[index] = True
    working.battle.entity_kind[index] = int(CardKindOpcode.TROOP)
    working.battle.entity_player[index] = working.battle.entity_player[
        event_batch, source_slots
    ]
    working.battle.entity_card[index] = child_core
    working.battle.entity_x_units[index] = position[:, 0].to(torch.int32)
    working.battle.entity_y_units[index] = position[:, 1].to(torch.int32)
    working.battle.entity_hp[index] = catalog.cards.hitpoints[child_card]
    working.battle.entity_hp_integer_kind[index] = (
        catalog.deployment.hitpoints_integer_kind[child_card]
    )
    working.battle.entity_max_hp[index] = catalog.cards.hitpoints[child_card]
    with_deploy = catalog.spawn.spawn_with_deploy[event_operation]
    deploy = torch.where(
        with_deploy,
        catalog.deployment.deploy_delay_seconds[child_card, 0],
        0.0,
    )
    working.battle.entity_deploy_delay[index] = deploy
    pending = deploy > 1e-9
    working.battle.entity_placement_pending[index] = pending
    working.battle.entity_spawn_hook_pending[index] = pending
    working.battle.entity_spawn_hook_fired[index] = ~pending
    working.battle.entity_id.copy_(working.entity_pool.entity_id)
    event_x = torch.zeros_like(allocation.slots, dtype=torch.int32)
    event_y = torch.zeros_like(allocation.slots, dtype=torch.int32)
    event_payload = torch.zeros_like(allocation.entity_ids)
    if event_batch.numel():
        event_x[event_batch, local] = position[:, 0].to(torch.int32)
        event_y[event_batch, local] = position[:, 1].to(torch.int32)
        event_payload[event_batch, local] = child_core
    working.events.append(
        phase=TickPhase.OBJECTS,
        opcode=RuntimeEventOpcode.SPAWN,
        valid=allocation.valid,
        target_id=allocation.entity_ids,
        x_units=event_x,
        y_units=event_y,
        payload=event_payload,
    )
    working.mark_dirty(committed & (counts > 0), phase=TickPhase.OBJECTS)

    _copy_rows_(runtime.battle, working.battle, committed)
    _copy_rows_(runtime.status, working.status, committed)
    _copy_rows_(runtime.phases, working.phases, committed)
    _copy_rows_(runtime.events, working.events, committed)
    runtime.entity_pool.active[committed] = working.entity_pool.active[committed]
    runtime.entity_pool.next_entity_id[committed] = working.entity_pool.next_entity_id[
        committed
    ]
    runtime.dirty[committed] = working.dirty[committed]
    _copy_rows_(state, preview, committed)
    child_source = torch.zeros_like(allocation.entity_ids)
    formation = torch.zeros_like(allocation.entity_ids)
    wave = torch.zeros_like(allocation.entity_ids)
    if event_batch.numel():
        child_source[event_batch, local] = source_ids
        formation[event_batch, local] = schedule.formation_index[event_keep]
        wave[event_batch, local] = schedule.wave_size[event_keep]
    return TensorPeriodicSpawnerResult(
        committed,
        reason,
        schedule,
        allocation,
        child_source,
        formation,
        wave,
        torch.zeros_like(allocation.entity_ids),
    )


__all__ = [
    "PeriodicSpawnerReason",
    "TensorPeriodicSpawnerCatalog",
    "TensorPeriodicSpawnerResult",
    "TensorPeriodicSpawnerRuntimeState",
    "step_runtime_periodic_spawners_",
]
