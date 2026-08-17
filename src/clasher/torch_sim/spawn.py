"""Serialized spawn-operation tables and exact batched scheduling kernels."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

import torch

from clasher.card_aliases import resolve_card_name
from clasher.data import CardDataLoader
from clasher.factory.dynamic_factory import troop_from_character_data
from clasher.kinematics import tiles_to_logic_units
from clasher.mechanics.shared.death_effects import DeathSpawn
from clasher.mechanics.shared.spawner import PeriodicSpawner

from .catalog import MECHANIC_OPCODE


@dataclass(frozen=True)
class _ReachableSpawnOperation:
    root_name: str
    source_name: str
    source_mechanic_slot: int
    parent_row: int
    depth: int
    mechanic: DeathSpawn | PeriodicSpawner


def _reachable_spawn_operations(
    loader: CardDataLoader,
    card_names: Iterable[str],
) -> Iterator[_ReachableSpawnOperation]:
    """Yield spawn operations, including mechanics on serialized child payloads."""

    definitions = loader.load_card_definitions()
    resolved_names = tuple(
        sorted({resolve_card_name(name, definitions) for name in card_names})
    )
    missing = [name for name in resolved_names if name not in definitions]
    if missing:
        raise ValueError(f"missing card definitions: {missing}")

    rows_emitted = 0

    def walk(
        root_name: str,
        source_name: str,
        mechanics: Iterable[object],
        *,
        parent_row: int,
        depth: int,
        ancestry: frozenset[int],
    ) -> Iterator[_ReachableSpawnOperation]:
        nonlocal rows_emitted
        for mechanic_slot, mechanic in enumerate(mechanics):
            if not isinstance(mechanic, (DeathSpawn, PeriodicSpawner)):
                continue
            row = rows_emitted
            rows_emitted += 1
            yield _ReachableSpawnOperation(
                root_name=root_name,
                source_name=source_name,
                source_mechanic_slot=mechanic_slot,
                parent_row=parent_row,
                depth=depth,
                mechanic=mechanic,
            )

            unit_data = mechanic.unit_data
            if not unit_data or id(unit_data) in ancestry:
                continue
            child = troop_from_character_data(
                mechanic.unit_name,
                unit_data,
                elixir=0,
                rarity=unit_data.get("rarity", "Common"),
            )
            yield from walk(
                root_name,
                mechanic.unit_name,
                child._card_def.mechanics,
                parent_row=row,
                depth=depth + 1,
                ancestry=ancestry | {id(unit_data)},
            )

    for root_name in resolved_names:
        yield from walk(
            root_name,
            root_name,
            definitions[root_name].mechanics,
            parent_row=-1,
            depth=0,
            ancestry=frozenset(),
        )


@dataclass(frozen=True)
class TensorSpawnCatalog:
    """Dense data-driven inventory for reachable spawn-producing mechanics.

    Rows retain their enabled root and parent row so nested payloads such as a
    container that later releases troops remain distinguishable even when the
    child name is shared by multiple cards. Runtime dispatch is by serialized
    mechanic opcode and row, never by a card-name switch.
    """

    device: torch.device
    root_names: tuple[str, ...]
    source_names: tuple[str, ...]
    unit_names: tuple[str, ...]
    mechanic_opcode: torch.Tensor
    source_mechanic_slot: torch.Tensor
    parent_row: torch.Tensor
    depth: torch.Tensor
    count: torch.Tensor
    radius_units: torch.Tensor
    min_radius_units: torch.Tensor
    radial_pushback: torch.Tensor
    spawn_const_priority: torch.Tensor
    deploy_time_ms: torch.Tensor
    timed_explosive: torch.Tensor
    spawn_interval_ms: torch.Tensor
    first_spawn_delay_ms: torch.Tensor
    intra_spawn_interval_ms: torch.Tensor
    spawn_with_deploy: torch.Tensor
    spawn_angle_shift_degrees: torch.Tensor
    max_spawns: torch.Tensor

    @property
    def operation_count(self) -> int:
        return len(self.root_names)

    @classmethod
    def compile(
        cls,
        loader: CardDataLoader,
        card_names: Iterable[str],
        *,
        device: str | torch.device = "cpu",
    ) -> TensorSpawnCatalog:
        operations = tuple(_reachable_spawn_operations(loader, card_names))
        torch_device = torch.device(device)

        def tensor(values: Iterable[object], dtype: torch.dtype) -> torch.Tensor:
            return torch.tensor(tuple(values), dtype=dtype, device=torch_device)

        periodic_opcode = MECHANIC_OPCODE["PeriodicSpawner"]
        death_opcode = MECHANIC_OPCODE["DeathSpawn"]
        opcodes: list[int] = []
        counts: list[int] = []
        radii: list[int] = []
        min_radii: list[int] = []
        radial_pushback: list[bool] = []
        spawn_const_priority: list[bool] = []
        deploy_time_ms: list[int] = []
        timed_explosive: list[bool] = []
        spawn_interval_ms: list[int] = []
        first_spawn_delay_ms: list[int] = []
        intra_spawn_interval_ms: list[int] = []
        spawn_with_deploy: list[bool] = []
        spawn_angle_shift_degrees: list[float] = []
        max_spawns: list[int] = []

        for operation in operations:
            mechanic = operation.mechanic
            if isinstance(mechanic, DeathSpawn):
                counts.append(max(0, int(mechanic.count)))
                opcodes.append(death_opcode)
                radii.append(tiles_to_logic_units(mechanic.radius_tiles))
                min_radii.append(tiles_to_logic_units(mechanic.min_radius_tiles))
                radial_pushback.append(bool(mechanic.radial_pushback))
                spawn_const_priority.append(bool(mechanic.spawn_const_priority))
                deploy_time_ms.append(max(0, int(mechanic.deploy_time_ms)))
                unit_data = mechanic.unit_data or {}
                timed_explosive.append(
                    unit_data.get("deathDamage") is not None
                    and not bool(unit_data.get("hitpoints"))
                )
                spawn_interval_ms.append(0)
                first_spawn_delay_ms.append(0)
                intra_spawn_interval_ms.append(0)
                spawn_with_deploy.append(False)
                spawn_angle_shift_degrees.append(0.0)
                max_spawns.append(0)
            else:
                # The Python PeriodicSpawner explicitly treats a non-positive
                # serialized count as a one-member wave. DeathSpawn does not.
                counts.append(max(1, int(mechanic.count)))
                opcodes.append(periodic_opcode)
                radii.append(tiles_to_logic_units(mechanic.spawn_radius_tiles))
                min_radii.append(0)
                radial_pushback.append(False)
                spawn_const_priority.append(False)
                deploy_time_ms.append(0)
                timed_explosive.append(False)
                spawn_interval_ms.append(max(0, int(mechanic.spawn_interval_ms)))
                first_spawn_delay_ms.append(
                    int(
                        mechanic.spawn_interval_ms
                        if mechanic.first_spawn_delay_ms is None
                        else mechanic.first_spawn_delay_ms
                    )
                )
                intra_spawn_interval_ms.append(
                    max(0, int(mechanic.intra_spawn_interval_ms))
                )
                spawn_with_deploy.append(bool(mechanic.spawn_with_deploy))
                spawn_angle_shift_degrees.append(
                    float(mechanic.spawn_angle_shift_degrees)
                )
                max_spawns.append(int(mechanic.max_spawns))

        return cls(
            device=torch_device,
            root_names=tuple(operation.root_name for operation in operations),
            source_names=tuple(operation.source_name for operation in operations),
            unit_names=tuple(operation.mechanic.unit_name for operation in operations),
            mechanic_opcode=tensor(opcodes, torch.int16),
            source_mechanic_slot=tensor(
                (operation.source_mechanic_slot for operation in operations),
                torch.int16,
            ),
            parent_row=tensor(
                (operation.parent_row for operation in operations), torch.int32
            ),
            depth=tensor((operation.depth for operation in operations), torch.int16),
            count=tensor(counts, torch.int16),
            radius_units=tensor(radii, torch.int32),
            min_radius_units=tensor(min_radii, torch.int32),
            radial_pushback=tensor(radial_pushback, torch.bool),
            spawn_const_priority=tensor(spawn_const_priority, torch.bool),
            deploy_time_ms=tensor(deploy_time_ms, torch.int32),
            timed_explosive=tensor(timed_explosive, torch.bool),
            spawn_interval_ms=tensor(spawn_interval_ms, torch.float64),
            first_spawn_delay_ms=tensor(first_spawn_delay_ms, torch.float64),
            intra_spawn_interval_ms=tensor(intra_spawn_interval_ms, torch.float64),
            spawn_with_deploy=tensor(spawn_with_deploy, torch.bool),
            spawn_angle_shift_degrees=tensor(spawn_angle_shift_degrees, torch.float64),
            max_spawns=tensor(max_spawns, torch.int32),
        )

    def periodic_rows(self) -> torch.Tensor:
        return (self.mechanic_opcode == MECHANIC_OPCODE["PeriodicSpawner"]).nonzero(
            as_tuple=False
        )[:, 0]

    def death_rows(self) -> torch.Tensor:
        return (self.mechanic_opcode == MECHANIC_OPCODE["DeathSpawn"]).nonzero(
            as_tuple=False
        )[:, 0]


@dataclass
class TensorPeriodicSpawnerState:
    """Mutable oracle-equivalent clocks for a batch of periodic spawners."""

    time_since_spawn_ms: torch.Tensor
    spawns_created: torch.Tensor
    pending_units: torch.Tensor
    time_since_unit_spawn_ms: torch.Tensor
    current_wave_spawned: torch.Tensor

    @classmethod
    def zeros(
        cls,
        batch_size: int,
        spawner_count: int,
        *,
        device: str | torch.device = "cpu",
    ) -> TensorPeriodicSpawnerState:
        torch_device = torch.device(device)
        shape = (batch_size, spawner_count)
        return cls(
            time_since_spawn_ms=torch.zeros(
                shape, dtype=torch.float64, device=torch_device
            ),
            spawns_created=torch.zeros(shape, dtype=torch.int64, device=torch_device),
            pending_units=torch.zeros(shape, dtype=torch.int64, device=torch_device),
            time_since_unit_spawn_ms=torch.zeros(
                shape, dtype=torch.float64, device=torch_device
            ),
            current_wave_spawned=torch.zeros(
                shape, dtype=torch.int64, device=torch_device
            ),
        )


@dataclass(frozen=True)
class TensorSpawnEvents:
    """Flat stable-order spawn events emitted by a tensor scheduling step."""

    batch_index: torch.Tensor
    source_column: torch.Tensor
    catalog_row: torch.Tensor
    formation_index: torch.Tensor
    wave_size: torch.Tensor

    @property
    def operation_index(self) -> torch.Tensor:
        """Compatibility alias for the source column in the scheduling state."""

        return self.source_column

    @classmethod
    def empty(cls, device: torch.device) -> TensorSpawnEvents:
        empty = torch.empty((0,), dtype=torch.int64, device=device)
        return cls(
            empty,
            empty.clone(),
            empty.clone(),
            empty.clone(),
            empty.clone(),
        )


@dataclass(frozen=True)
class TensorDeathSpawnSources:
    """Authoritative source planes aligned to death-planning columns."""

    entity_id: torch.Tensor
    player: torch.Tensor
    x_units: torch.Tensor
    y_units: torch.Tensor
    facing_x_units: torch.Tensor
    facing_y_units: torch.Tensor
    freeze_expiry_time: torch.Tensor


@dataclass(frozen=True)
class TensorDeathSpawnEvents:
    """Death-child schedule with exact source context, not materialized children."""

    batch_index: torch.Tensor
    source_column: torch.Tensor
    catalog_row: torch.Tensor
    source_entity_id: torch.Tensor
    source_player: torch.Tensor
    source_x_units: torch.Tensor
    source_y_units: torch.Tensor
    source_facing_x_units: torch.Tensor
    source_facing_y_units: torch.Tensor
    source_freeze_expiry_time: torch.Tensor
    formation_index: torch.Tensor
    wave_size: torch.Tensor

    @classmethod
    def empty(cls, device: torch.device) -> TensorDeathSpawnEvents:
        integer64 = torch.empty((0,), dtype=torch.int64, device=device)
        integer32 = torch.empty((0,), dtype=torch.int32, device=device)
        integer8 = torch.empty((0,), dtype=torch.int8, device=device)
        floating = torch.empty((0,), dtype=torch.float64, device=device)
        return cls(
            integer64,
            integer64.clone(),
            integer64.clone(),
            integer64.clone(),
            integer8,
            integer32,
            integer32.clone(),
            integer32.clone(),
            integer32.clone(),
            floating,
            integer64.clone(),
            integer64.clone(),
        )


def _append_spawn_events(
    event_parts: list[
        tuple[
            torch.Tensor,
            torch.Tensor,
            torch.Tensor,
            torch.Tensor,
            torch.Tensor,
        ]
    ],
    mask: torch.Tensor,
    *,
    catalog_rows: torch.Tensor,
    start_index: torch.Tensor,
    event_count: torch.Tensor,
    wave_size: torch.Tensor,
) -> None:
    coordinates = mask.nonzero(as_tuple=False)
    if coordinates.numel() == 0:
        return
    selected_counts = event_count[mask].to(torch.int64)
    repeated = coordinates.repeat_interleave(selected_counts, dim=0)
    starts = start_index[mask].to(torch.int64).repeat_interleave(selected_counts)
    local = torch.cat(
        [
            torch.arange(int(count), device=mask.device)
            for count in selected_counts.tolist()
        ]
    )
    waves = wave_size[mask].to(torch.int64).repeat_interleave(selected_counts)
    rows = catalog_rows[mask].to(torch.int64).repeat_interleave(selected_counts)
    event_parts.append((repeated[:, 0], repeated[:, 1], rows, starts + local, waves))


def step_periodic_spawners(
    catalog: TensorSpawnCatalog,
    state: TensorPeriodicSpawnerState,
    dt_ms: float | torch.Tensor,
    *,
    operation_rows: torch.Tensor | None = None,
    active: torch.Tensor | None = None,
    spawn_rate: torch.Tensor | None = None,
) -> TensorSpawnEvents:
    """Advance periodic clocks with the Python oracle's budget semantics.

    ``operation_rows`` maps each state column to a periodic catalog row. A 1-D
    mapping broadcasts across battles; a 2-D mapping supports heterogeneous
    per-battle layouts. The caller keeps columns in source-entity ID order;
    duplicate rows are valid when multiple entities share one blueprint.
    """

    batch_size, spawner_count = state.spawns_created.shape
    rows = catalog.periodic_rows() if operation_rows is None else operation_rows
    rows = rows.to(device=catalog.device, dtype=torch.int64)
    if rows.ndim == 1:
        if rows.shape[0] != spawner_count:
            raise ValueError("operation_rows width must match the spawner state")
        rows = rows[None, :].expand(batch_size, -1)
    elif rows.shape != (batch_size, spawner_count):
        raise ValueError("operation_rows must be one-dimensional or match the state")
    if bool(((rows < 0) | (rows >= catalog.operation_count)).any().item()):
        raise ValueError("operation_rows contains an invalid catalog row")
    if bool(
        (catalog.mechanic_opcode[rows] != MECHANIC_OPCODE["PeriodicSpawner"])
        .any()
        .item()
    ):
        raise ValueError("operation_rows may contain only PeriodicSpawner rows")
    shape = (batch_size, spawner_count)
    device = state.spawns_created.device
    if catalog.device != device:
        raise ValueError("catalog and spawner state must use the same device")
    if active is None:
        active = torch.ones(shape, dtype=torch.bool, device=device)
    else:
        active = active.to(device=device, dtype=torch.bool)
    if spawn_rate is None:
        spawn_rate = torch.ones(shape, dtype=torch.float64, device=device)
    else:
        spawn_rate = spawn_rate.to(device=device, dtype=torch.float64)
    if active.shape != shape or spawn_rate.shape != shape:
        raise ValueError("active and spawn_rate must match the spawner state shape")

    dt = torch.as_tensor(dt_ms, dtype=torch.float64, device=device)
    budget = torch.clamp(spawn_rate.to(torch.float64), min=0.0) * dt
    eligible = active & (budget > 0)
    counts = catalog.count[rows].to(torch.int64)
    interval = catalog.spawn_interval_ms[rows]
    first_delay = catalog.first_spawn_delay_ms[rows]
    intra = catalog.intra_spawn_interval_ms[rows]
    max_spawns = catalog.max_spawns[rows].to(torch.int64)
    catalog_rows = rows
    if bool(((interval <= 0) & (max_spawns < 0)).any().item()):
        raise ValueError("an unlimited periodic spawner requires a positive interval")

    event_parts: list[
        tuple[
            torch.Tensor,
            torch.Tensor,
            torch.Tensor,
            torch.Tensor,
            torch.Tensor,
        ]
    ] = []
    # State columns are supplied in source-entity ID order. Drain one source's
    # complete budget before moving to the next, matching Python's component
    # pass; advancing all columns round-robin would reorder coarse-step waves.
    for operation_index in range(spawner_count):
        source_column = torch.zeros(shape, dtype=torch.bool, device=device)
        source_column[:, operation_index] = True
        running = eligible & source_column
        while bool(running.any().item()):
            pending = running & (state.pending_units > 0)
            pending_needed = torch.clamp(
                intra - state.time_since_unit_spawn_ms, min=0.0
            )
            pending_wait = pending & (budget < pending_needed)
            state.time_since_unit_spawn_ms.add_(
                torch.where(pending_wait, budget, torch.zeros_like(budget))
            )
            running &= ~pending_wait

            pending_ready = pending & ~pending_wait
            budget.sub_(
                torch.where(pending_ready, pending_needed, torch.zeros_like(budget))
            )
            _append_spawn_events(
                event_parts,
                pending_ready,
                catalog_rows=catalog_rows,
                start_index=state.current_wave_spawned,
                event_count=torch.ones_like(state.pending_units),
                wave_size=counts,
            )
            state.time_since_unit_spawn_ms.masked_fill_(pending_ready, 0.0)
            state.current_wave_spawned.add_(pending_ready.to(torch.int64))
            state.pending_units.sub_(pending_ready.to(torch.int64))
            wave_finished = pending_ready & (state.pending_units == 0)
            state.spawns_created.add_(wave_finished.to(torch.int64))
            state.current_wave_spawned.masked_fill_(wave_finished, 0)
            state.time_since_spawn_ms.masked_fill_(wave_finished, 0.0)
            running &= ~(pending_ready & (budget == 0))

            idle = running & (state.pending_units == 0)
            exhausted = idle & (max_spawns >= 0) & (state.spawns_created >= max_spawns)
            running &= ~exhausted
            idle &= ~exhausted
            threshold = torch.where(state.spawns_created == 0, first_delay, interval)
            wave_needed = torch.clamp(threshold - state.time_since_spawn_ms, min=0.0)
            wave_wait = idle & (budget < wave_needed)
            state.time_since_spawn_ms.add_(
                torch.where(wave_wait, budget, torch.zeros_like(budget))
            )
            running &= ~wave_wait

            wave_ready = idle & ~wave_wait
            budget.sub_(torch.where(wave_ready, wave_needed, torch.zeros_like(budget)))
            state.time_since_spawn_ms.masked_fill_(wave_ready, 0.0)
            staggered = wave_ready & (intra > 0) & (counts > 1)
            immediate = wave_ready & ~staggered
            _append_spawn_events(
                event_parts,
                staggered,
                catalog_rows=catalog_rows,
                start_index=torch.zeros_like(state.current_wave_spawned),
                event_count=torch.ones_like(state.pending_units),
                wave_size=counts,
            )
            state.current_wave_spawned.copy_(
                torch.where(
                    staggered,
                    torch.ones_like(state.current_wave_spawned),
                    state.current_wave_spawned,
                )
            )
            state.pending_units.copy_(
                torch.where(staggered, counts - 1, state.pending_units)
            )
            state.time_since_unit_spawn_ms.masked_fill_(staggered, 0.0)
            _append_spawn_events(
                event_parts,
                immediate,
                catalog_rows=catalog_rows,
                start_index=torch.zeros_like(state.current_wave_spawned),
                event_count=counts,
                wave_size=counts,
            )
            state.spawns_created.add_(immediate.to(torch.int64))
            running &= ~(wave_ready & (budget == 0))

    if not event_parts:
        return TensorSpawnEvents.empty(device)
    columns = tuple(torch.cat(parts) for parts in zip(*event_parts))
    return TensorSpawnEvents(*columns)


def plan_death_spawns(
    catalog: TensorSpawnCatalog,
    dead: torch.Tensor,
    *,
    operation_rows: torch.Tensor,
    sources: TensorDeathSpawnSources,
) -> TensorDeathSpawnEvents:
    """Schedule death children in source-ID order without materializing them.

    Source columns may map to duplicate serialized rows when multiple live
    entities share a blueprint. The caller supplies columns in entity-ID order
    and the authoritative context needed by later geometry/materialization.
    """

    if dead.ndim != 2:
        raise ValueError("dead must have shape [batch, source-columns]")
    if catalog.device != dead.device:
        raise ValueError("catalog and dead mask must use the same device")
    dead = dead.to(dtype=torch.bool)
    rows = operation_rows.to(device=dead.device, dtype=torch.int64)
    if rows.ndim == 1:
        if rows.shape[0] != dead.shape[1]:
            raise ValueError("operation_rows width must match the source columns")
        rows = rows[None, :].expand_as(dead)
    elif rows.shape != dead.shape:
        raise ValueError("operation_rows must be one-dimensional or match dead")
    if bool(((rows < 0) | (rows >= catalog.operation_count)).any().item()):
        raise ValueError("operation_rows contains an invalid catalog row")
    if bool(
        (catalog.mechanic_opcode[rows] != MECHANIC_OPCODE["DeathSpawn"]).any().item()
    ):
        raise ValueError("operation_rows may contain only DeathSpawn rows")

    source_planes = (
        sources.entity_id,
        sources.player,
        sources.x_units,
        sources.y_units,
        sources.facing_x_units,
        sources.facing_y_units,
        sources.freeze_expiry_time,
    )
    if any(plane.shape != dead.shape for plane in source_planes):
        raise ValueError("every death-source plane must match the dead mask")
    if any(plane.device != dead.device for plane in source_planes):
        raise ValueError("every death-source plane must use the catalog device")
    expected_dtypes = (
        torch.int64,
        torch.int8,
        torch.int32,
        torch.int32,
        torch.int32,
        torch.int32,
        torch.float64,
    )
    if any(
        plane.dtype != expected
        for plane, expected in zip(source_planes, expected_dtypes)
    ):
        raise TypeError("death-source planes use an unexpected dtype")
    if bool((dead & (sources.entity_id <= 0)).any().item()):
        raise ValueError("dead source columns must contain positive entity IDs")
    if bool((dead & ~((sources.player == 0) | (sources.player == 1))).any().item()):
        raise ValueError("dead source columns must belong to player zero or one")

    counts = catalog.count[rows].to(torch.int64)
    parts: list[
        tuple[
            torch.Tensor,
            torch.Tensor,
            torch.Tensor,
            torch.Tensor,
            torch.Tensor,
        ]
    ] = []
    _append_spawn_events(
        parts,
        dead,
        catalog_rows=rows,
        start_index=torch.zeros_like(counts),
        event_count=counts,
        wave_size=counts,
    )
    if not parts:
        return TensorDeathSpawnEvents.empty(dead.device)
    scheduled = TensorSpawnEvents(*(torch.cat(column) for column in zip(*parts)))
    batch = scheduled.batch_index
    column = scheduled.source_column
    return TensorDeathSpawnEvents(
        batch_index=batch,
        source_column=column,
        catalog_row=scheduled.catalog_row,
        source_entity_id=sources.entity_id[batch, column],
        source_player=sources.player[batch, column],
        source_x_units=sources.x_units[batch, column],
        source_y_units=sources.y_units[batch, column],
        source_facing_x_units=sources.facing_x_units[batch, column],
        source_facing_y_units=sources.facing_y_units[batch, column],
        source_freeze_expiry_time=sources.freeze_expiry_time[batch, column],
        formation_index=scheduled.formation_index,
        wave_size=scheduled.wave_size,
    )
