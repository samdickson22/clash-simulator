"""Transactional resident planning/materialization for terminal character payloads.

The kernel composes the serialized :class:`DeathSpawn` schedule with the
entity pool's spawn-before-remove transaction. Runtime behavior is selected by
catalog rows only. Timed explosives and DeathArea containers remain explicit
preflight failures because they require retained object materialization.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import IntEnum

import torch

from clasher.data import CardDataLoader
from clasher.factory.dynamic_factory import troop_from_character_data
from clasher.kinematics import NATIVE_MOVEMENT_SUBSTEP_UNITS
from clasher.logic_math import logic_sin, logic_vector_angle
from clasher.native_tilemap import native_spawn_tile_blocked

from .catalog import MECHANIC_OPCODE, CardKindOpcode, TensorCardCatalog
from .deployment import TensorDeploymentCatalog
from .entity_pool import CleanupSpawnTransition
from .movement import integer_sqrt_tensor, trunc_div_tensor
from .runtime_state import RuntimeEventOpcode, TensorBattleRuntime, TickPhase
from .spawn import (
    TensorDeathSpawnEvents,
    TensorDeathSpawnSources,
    TensorSpawnCatalog,
    plan_death_spawns,
)

_SIN_1024 = tuple(logic_sin(angle, 1_024) for angle in range(360))
_ATAN = tuple(logic_vector_angle(128, value) for value in range(129))
_SPAWN_BLOCKED = tuple(
    tuple(native_spawn_tile_blocked(x, y) for y in range(64)) for x in range(36)
)


class _TerminalCatalogLoader(CardDataLoader):
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


class TerminalPayloadReason(IntEnum):
    NONE = 0
    UNSUPPORTED_PAYLOAD = 1
    ENTITY_CAPACITY = 2
    EVENT_CAPACITY = 3


@dataclass(frozen=True)
class TerminalPayloadPreflight:
    supported: torch.Tensor
    reason: torch.Tensor
    operation_row_by_slot: torch.Tensor
    spawn_count_by_slot: torch.Tensor


@dataclass(frozen=True)
class TensorTerminalPayloadResult:
    preflight: TerminalPayloadPreflight
    committed: torch.Tensor
    transition: CleanupSpawnTransition
    schedule: TensorDeathSpawnEvents
    child_catalog_row: torch.Tensor
    child_parent_id: torch.Tensor
    child_formation_index: torch.Tensor
    child_facing_x_units: torch.Tensor
    child_facing_y_units: torch.Tensor
    child_freeze_expiry_time: torch.Tensor
    child_travel_target_units: torch.Tensor
    child_travel_ticks: torch.Tensor
    child_target_distance_discount_sq_units: torch.Tensor


@dataclass
class TensorTerminalPayloadCatalog:
    """Dense direct-DeathSpawn metadata indexed without card-name dispatch."""

    cards: TensorCardCatalog
    deployment: TensorDeploymentCatalog
    spawn: TensorSpawnCatalog
    source_row_by_card: torch.Tensor
    child_card_id: torch.Tensor
    direct_supported: torch.Tensor
    parent_angle_shift_degrees: torch.Tensor
    has_death_damage: torch.Tensor
    has_death_area: torch.Tensor
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
        root_names: tuple[str, ...] | list[str],
    ) -> TensorTerminalPayloadCatalog:
        spawn = TensorSpawnCatalog.compile(loader, root_names, device=cards.device)
        direct_rows = [
            row
            for row in spawn.death_rows().detach().cpu().tolist()
            if int(spawn.depth[row].item()) == 0
        ]
        required_children = {spawn.unit_names[row] for row in direct_rows}
        required_sources = {
            str(getattr(loader.get_card(spawn.root_names[row]), "name", "") or "")
            for row in direct_rows
        }
        required_names = required_children | required_sources
        effective_loader: CardDataLoader = loader
        if not required_names.issubset(cards.name_to_id):
            overlay = _TerminalCatalogLoader(loader)
            definitions = loader.load_card_definitions()
            for row in direct_rows:
                mechanic = definitions[spawn.root_names[row]].mechanics[
                    int(spawn.source_mechanic_slot[row].item())
                ]
                unit_data = getattr(mechanic, "unit_data", None)
                if isinstance(unit_data, dict):
                    overlay.add_character(spawn.unit_names[row], unit_data)
            effective_loader = overlay
            cards = TensorCardCatalog.compile(
                overlay,
                tuple(sorted(set(cards.names[1:]) | required_names)),
                device=cards.device,
            )
        deployment = TensorDeploymentCatalog.compile(effective_loader, cards)
        operation_count = spawn.operation_count
        child_card = torch.full(
            (operation_count,), -1, dtype=torch.int64, device=cards.device
        )
        source_row = torch.full(
            (len(cards.names),), -1, dtype=torch.int64, device=cards.device
        )
        direct_supported = torch.zeros(
            operation_count, dtype=torch.bool, device=cards.device
        )
        angle_shift = torch.zeros(
            operation_count, dtype=torch.int32, device=cards.device
        )
        has_damage = torch.zeros(operation_count, dtype=torch.bool, device=cards.device)
        has_area = torch.zeros_like(has_damage)
        direct_rows_by_card: dict[int, list[int]] = {}

        for row in spawn.death_rows().detach().cpu().tolist():
            if int(spawn.depth[row].item()) != 0:
                continue
            child_id = cards.name_to_id.get(spawn.unit_names[row], -1)
            child_card[row] = child_id
            stats = effective_loader.get_card(spawn.root_names[row])
            source_names = {
                spawn.root_names[row],
                str(getattr(stats, "name", "") or ""),
            }
            root_ids = {
                cards.name_to_id[name]
                for name in source_names
                if name in cards.name_to_id
            }
            if not root_ids:
                continue
            for root_id in root_ids:
                direct_rows_by_card.setdefault(root_id, []).append(row)
            angle_shift[row] = round(float(getattr(stats, "spawn_angle_shift", 0) or 0))
            operations = cards.mechanic_opcode[min(root_ids)]
            has_damage[row] = bool(
                (operations == MECHANIC_OPCODE["DeathDamage"]).any().item()
            )
            has_area[row] = bool(
                (operations == MECHANIC_OPCODE["DeathAreaEffect"]).any().item()
            )
            direct_supported[row] = bool(
                child_id >= 0
                and not spawn.timed_explosive[row].item()
                and spawn.min_radius_units[row].item() == 0
                and cards.kind[child_id].item() == int(CardKindOpcode.TROOP)
            )

        for card_id, rows in direct_rows_by_card.items():
            if len(rows) == 1:
                source_row[card_id] = rows[0]
            else:
                direct_supported[rows] = False
                source_row[card_id] = rows[0]

        return cls(
            cards=cards,
            deployment=deployment,
            spawn=spawn,
            source_row_by_card=source_row,
            child_card_id=child_card,
            direct_supported=direct_supported,
            parent_angle_shift_degrees=angle_shift,
            has_death_damage=has_damage,
            has_death_area=has_area,
        )

    def prepare_runtime(self, runtime: TensorBattleRuntime) -> None:
        """Install direct child names before any terminal transaction."""

        required = {
            self.spawn.unit_names[row]
            for row in self.spawn.death_rows().detach().cpu().tolist()
            if int(self.spawn.depth[row].item()) == 0
            and bool(self.direct_supported[row].item())
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
        mapping = torch.tensor(
            [
                runtime.battle.card_to_id.get(name, -1) if name else -1
                for name in self.spawn.unit_names
            ],
            dtype=torch.int64,
            device=runtime.device,
        )
        self._mapping_key = runtime.battle.card_names
        self._child_core_cache = mapping
        return mapping

    def direct_coverage(self) -> dict[str, bool]:
        """Boundary report for direct root payloads."""

        return {
            self.spawn.root_names[row]: bool(self.direct_supported[row].item())
            for row in self.spawn.death_rows().detach().cpu().tolist()
            if int(self.spawn.depth[row].item()) == 0
        }


def _vector_angle(x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    table = torch.tensor(_ATAN, dtype=torch.int64, device=x.device)
    x = x.to(torch.int64)
    y = y.to(torch.int64)
    ax = x.abs()
    ay = y.abs()
    x_safe = ax.clamp_min(1)
    y_safe = ay.clamp_min(1)
    y_over_x = trunc_div_tensor(ay * 128, x_safe).clamp(0, 128)
    x_over_y = trunc_div_tensor(ax * 128, y_safe).clamp(0, 128)
    q1 = torch.where(ay < ax, table[y_over_x], 90 - table[x_over_y])
    q2 = torch.where(ax < ay, 90 + table[x_over_y], 180 - table[y_over_x])
    q3 = torch.where(ay < ax, 180 + table[y_over_x], 270 - table[x_over_y])
    q4 = torch.where(ax < ay, 270 + table[x_over_y], 360 - table[y_over_x])
    angle = torch.where(
        (x > 0) & (y >= 0),
        q1,
        torch.where((x <= 0) & (y > 0), q2, torch.where((x < 0), q3, q4)),
    )
    return torch.where((x == 0) & (y == 0), 0, angle % 360)


def _sin(angle: torch.Tensor, magnitude: torch.Tensor) -> torch.Tensor:
    table = torch.tensor(_SIN_1024, dtype=torch.int64, device=angle.device)
    return trunc_div_tensor(table[angle.to(torch.int64) % 360] * magnitude, 1_024)


def _radial_target(
    events: TensorDeathSpawnEvents,
    catalog: TensorTerminalPayloadCatalog,
) -> torch.Tensor:
    row = events.catalog_row
    count = events.wave_size.clamp_min(1)
    shift = catalog.parent_angle_shift_degrees[row].to(torch.int64)
    base = torch.where(
        shift != 0,
        _vector_angle(events.source_facing_x_units, events.source_facing_y_units)
        + shift,
        0,
    )
    angle = base + trunc_div_tensor(
        (count - 1 - events.formation_index) * 360,
        count,
    )
    radius = catalog.spawn.radius_units[row].to(torch.int64)
    x = events.source_x_units.to(torch.int64) + _sin(angle + 90, radius)
    y = events.source_y_units.to(torch.int64) + _sin(angle, radius)
    return torch.stack((x, y), dim=1)


def _terrain_child_target(
    events: TensorDeathSpawnEvents,
    catalog: TensorTerminalPayloadCatalog,
) -> torch.Tensor:
    row = events.catalog_row
    source_card = torch.tensor(
        [catalog.cards.name_to_id[name] for name in catalog.spawn.root_names],
        dtype=torch.int64,
        device=catalog.device,
    )[row]
    child_card = catalog.child_card_id[row]
    parent_radius = catalog.cards.collision_radius_units[source_card].to(torch.int64)
    child_radius = catalog.cards.collision_radius_units[child_card].to(torch.int64)
    direct = events.wave_size == 1
    distance = torch.where(direct, 0, parent_radius + child_radius)
    zero = torch.zeros_like(distance)
    offset_x = torch.stack((zero, -distance, zero, distance), dim=1)
    offset_y = torch.stack((distance, zero, -distance, zero), dim=1)
    offset_x = torch.where(
        (events.source_x_units > 9_000)[:, None], -offset_x, offset_x
    )
    offset_y = torch.where((events.source_player == 1)[:, None], -offset_y, offset_y)
    candidate_x = events.source_x_units[:, None].to(torch.int64) + offset_x
    candidate_y = events.source_y_units[:, None].to(torch.int64) + offset_y
    radius = child_radius[:, None]
    bounds = (
        (candidate_x - radius >= 0)
        & (candidate_y - radius >= 0)
        & (candidate_x + radius < 18_000)
        & (candidate_y + radius < 32_000)
    )
    min_x = torch.div(candidate_x - radius, 500, rounding_mode="floor")
    max_x = torch.div(candidate_x + radius - 1, 500, rounding_mode="floor")
    min_y = torch.div(candidate_y - radius, 500, rounding_mode="floor")
    max_y = torch.div(candidate_y + radius - 1, 500, rounding_mode="floor")
    tile_x = torch.arange(36, device=catalog.device).view(1, 1, 36, 1)
    tile_y = torch.arange(64, device=catalog.device).view(1, 1, 1, 64)
    covered = (
        (tile_x >= min_x[:, :, None, None])
        & (tile_x <= max_x[:, :, None, None])
        & (tile_y >= min_y[:, :, None, None])
        & (tile_y <= max_y[:, :, None, None])
    )
    blocked = torch.tensor(_SPAWN_BLOCKED, dtype=torch.bool, device=catalog.device)
    valid = bounds & ~(covered & blocked[None, None, :, :]).any(dim=(2, 3))
    selected = valid.to(torch.int64).argmax(dim=1)
    exists = valid.any(dim=1)
    rows = torch.arange(events.batch_index.numel(), device=catalog.device)
    x = candidate_x[rows, selected]
    y = candidate_y[rows, selected]
    x = torch.where(exists, x, events.source_x_units.to(torch.int64) + 1)
    y = torch.where(exists, y, events.source_y_units.to(torch.int64))
    return torch.stack((x, y), dim=1)


def preflight_terminal_payloads(
    runtime: TensorBattleRuntime,
    catalog: TensorTerminalPayloadCatalog,
    dead: torch.Tensor,
) -> TerminalPayloadPreflight:
    if dead.shape != runtime.entity_pool.active.shape:
        raise ValueError("dead must have shape [batch, entity]")
    if dead.device != runtime.device or catalog.device != runtime.device:
        raise ValueError("runtime, catalog, and dead mask must share a device")
    catalog.prepare_runtime(runtime)
    dead = dead.to(torch.bool) & runtime.entity_pool.active
    core_card = runtime.card_catalog_index[runtime.battle.entity_card]
    safe_card = core_card.clamp_min(0)
    operation = catalog.source_row_by_card[safe_card]
    has_payload = operation >= 0
    safe_operation = operation.clamp_min(0)
    supported_payload = ~has_payload | catalog.direct_supported[safe_operation]
    unsupported = (dead & ~supported_payload).any(dim=1)
    counts = torch.where(
        dead & has_payload & supported_payload,
        catalog.spawn.count[safe_operation].to(torch.int64),
        0,
    )
    live_after = runtime.entity_pool.active.sum(dim=1, dtype=torch.int64) - dead.sum(
        dim=1, dtype=torch.int64
    )
    total = counts.sum(dim=1, dtype=torch.int64)
    entity_overflow = live_after + total > runtime.max_entities
    event_overflow = (
        runtime.events.count.to(torch.int64) + total > runtime.events.capacity
    )
    reason = torch.where(
        unsupported,
        int(TerminalPayloadReason.UNSUPPORTED_PAYLOAD),
        torch.where(
            entity_overflow,
            int(TerminalPayloadReason.ENTITY_CAPACITY),
            torch.where(
                event_overflow,
                int(TerminalPayloadReason.EVENT_CAPACITY),
                int(TerminalPayloadReason.NONE),
            ),
        ),
    ).to(torch.int16)
    return TerminalPayloadPreflight(
        supported=runtime.supported & (reason == int(TerminalPayloadReason.NONE)),
        reason=reason,
        operation_row_by_slot=operation,
        spawn_count_by_slot=counts,
    )


def _clear_child_slots_(
    runtime: TensorBattleRuntime,
    rows: torch.Tensor,
    slots: torch.Tensor,
) -> None:
    index = (rows, slots)
    for owner in (runtime.battle, runtime.status, runtime.phases):
        for descriptor in fields(owner):
            value = getattr(owner, descriptor.name)
            if (
                not isinstance(value, torch.Tensor)
                or value.ndim < 2
                or value.shape[:2] != runtime.entity_pool.active.shape
            ):
                continue
            if owner is runtime.battle and descriptor.name == "entity_id":
                continue
            value[index] = 0
    runtime.phases.target_slot[index] = -1
    runtime.battle.entity_tower_slot[index] = -1


def materialize_terminal_payloads_(
    runtime: TensorBattleRuntime,
    catalog: TensorTerminalPayloadCatalog,
    dead: torch.Tensor,
    *,
    facing_x_units: torch.Tensor,
    facing_y_units: torch.Tensor,
) -> TensorTerminalPayloadResult:
    """Materialize supported rows and leave every failed row bit-for-bit intact."""

    if facing_x_units.shape != dead.shape or facing_y_units.shape != dead.shape:
        raise ValueError("facing planes must match dead")
    preflight = preflight_terminal_payloads(runtime, catalog, dead)
    effective_dead = dead.to(torch.bool) & preflight.supported[:, None]
    ordered = runtime.entity_pool.id_order(effective_dead)
    source_slot = ordered.slots.clamp_min(0)
    operation = preflight.operation_row_by_slot.gather(1, source_slot)
    fallback_rows = catalog.spawn.death_rows()
    if fallback_rows.numel() == 0:
        raise ValueError("terminal catalog has no DeathSpawn operation")
    operation = torch.where(
        ordered.valid & (operation >= 0), operation, fallback_rows[0]
    )
    source = TensorDeathSpawnSources(
        entity_id=runtime.battle.entity_id.gather(1, source_slot),
        player=runtime.battle.entity_player.gather(1, source_slot),
        x_units=runtime.battle.entity_x_units.gather(1, source_slot),
        y_units=runtime.battle.entity_y_units.gather(1, source_slot),
        facing_x_units=facing_x_units.gather(1, source_slot).to(torch.int32),
        facing_y_units=facing_y_units.gather(1, source_slot).to(torch.int32),
        freeze_expiry_time=runtime.status.freeze_expiry_time.gather(1, source_slot),
    )
    scheduled_dead = ordered.valid & (
        preflight.spawn_count_by_slot.gather(1, source_slot) > 0
    )
    schedule = plan_death_spawns(
        catalog.spawn,
        scheduled_dead,
        operation_rows=operation,
        sources=source,
    )
    counts = torch.where(
        effective_dead,
        preflight.spawn_count_by_slot,
        torch.zeros_like(preflight.spawn_count_by_slot),
    )
    transition = runtime.entity_pool.cleanup_with_spawns(effective_dead, counts)
    capacity = runtime.max_entities
    zeros_i64 = torch.zeros(
        (runtime.batch_size, capacity), dtype=torch.int64, device=runtime.device
    )
    zeros_i32 = torch.zeros_like(zeros_i64, dtype=torch.int32)
    zeros_f64 = torch.zeros_like(zeros_i64, dtype=torch.float64)
    travel_target = torch.zeros(
        (runtime.batch_size, capacity, 2), dtype=torch.int64, device=runtime.device
    )
    child_row = torch.full_like(zeros_i64, -1)
    parent_id = transition.spawn_parent_ids.clone()
    formation = zeros_i64.clone()
    facing_x = zeros_i32.clone()
    facing_y = zeros_i32.clone()
    freeze = zeros_f64.clone()
    travel_ticks = zeros_i64.clone()
    discount = zeros_i64.clone()

    if schedule.batch_index.numel():
        batch_counts = torch.bincount(
            schedule.batch_index, minlength=runtime.batch_size
        )
        starts = torch.cumsum(batch_counts, dim=0) - batch_counts
        event_index = torch.arange(schedule.batch_index.numel(), device=runtime.device)
        local = event_index - starts[schedule.batch_index]
        child_slot = transition.spawned.slots[schedule.batch_index, local]
        rows = schedule.batch_index
        index = (rows, child_slot)
        _clear_child_slots_(runtime, rows, child_slot)
        row = schedule.catalog_row
        child_catalog = catalog.child_card_id[row]
        child_core = catalog.child_core_ids(runtime)[row]
        radius = catalog.spawn.radius_units[row]
        radial_target = _radial_target(schedule, catalog)
        terrain_target = _terrain_child_target(schedule, catalog)
        target = torch.where((radius > 0)[:, None], radial_target, terrain_target)
        radial_travel = catalog.spawn.radial_pushback[row] & (radius > 0)
        position = torch.where(
            radial_travel[:, None],
            torch.stack(
                (
                    schedule.source_x_units.to(torch.int64),
                    schedule.source_y_units.to(torch.int64),
                ),
                dim=1,
            ),
            target,
        )
        delta = target - position
        ticks = torch.div(
            integer_sqrt_tensor((delta * delta).sum(dim=1)),
            NATIVE_MOVEMENT_SUBSTEP_UNITS,
            rounding_mode="floor",
        )
        delay_ms = catalog.spawn.deploy_time_ms[row].to(torch.int64)
        inherited = (delay_ms <= 0) & (
            schedule.source_freeze_expiry_time > runtime.battle.time[rows] + 1e-9
        )
        inherited_freeze = torch.where(
            inherited, schedule.source_freeze_expiry_time, 0.0
        )

        runtime.battle.entity_active[index] = True
        runtime.battle.entity_kind[index] = catalog.cards.kind[child_catalog].to(
            torch.int8
        )
        runtime.battle.entity_player[index] = schedule.source_player
        runtime.battle.entity_card[index] = child_core
        runtime.battle.entity_x_units[index] = position[:, 0].to(torch.int32)
        runtime.battle.entity_y_units[index] = position[:, 1].to(torch.int32)
        runtime.battle.entity_hp[index] = catalog.cards.hitpoints[child_catalog]
        runtime.battle.entity_hp_integer_kind[index] = (
            catalog.deployment.hitpoints_integer_kind[child_catalog]
        )
        runtime.battle.entity_max_hp[index] = catalog.cards.hitpoints[child_catalog]
        delay_seconds = delay_ms.to(torch.float64) / 1_000.0
        runtime.battle.entity_deploy_delay[index] = delay_seconds
        pending = delay_ms > 0
        runtime.battle.entity_placement_pending[index] = pending
        runtime.battle.entity_spawn_hook_pending[index] = pending
        runtime.battle.entity_spawn_hook_fired[index] = ~pending
        runtime.status.freeze_expiry_time[index] = inherited_freeze

        child_row[index] = row
        formation[index] = schedule.formation_index
        facing_x[index] = schedule.source_facing_x_units
        facing_y[index] = schedule.source_facing_y_units
        freeze[index] = inherited_freeze
        travel_target[index] = target
        travel_ticks[index] = torch.where(radial_travel, ticks, 0)
        step = schedule.formation_index * 80
        discount[index] = torch.where(
            catalog.spawn.spawn_const_priority[row], step * step, 0
        )

    runtime.battle.entity_id.copy_(runtime.entity_pool.entity_id)
    runtime.events.append(
        phase=TickPhase.CLEANUP_AND_SPAWNS,
        opcode=RuntimeEventOpcode.SPAWN,
        valid=transition.spawned.valid,
        source_id=transition.spawn_parent_ids,
        target_id=transition.spawned.entity_ids,
        x_units=runtime.battle.entity_x_units.gather(
            1, transition.spawned.slots.clamp_min(0)
        ),
        y_units=runtime.battle.entity_y_units.gather(
            1, transition.spawned.slots.clamp_min(0)
        ),
        payload=runtime.battle.entity_card.gather(
            1, transition.spawned.slots.clamp_min(0)
        ),
    )
    runtime.phases.death_pending &= ~effective_dead
    runtime.mark_dirty(effective_dead.any(dim=1), phase=TickPhase.CLEANUP_AND_SPAWNS)
    runtime.assert_invariants()
    return TensorTerminalPayloadResult(
        preflight=preflight,
        committed=preflight.supported,
        transition=transition,
        schedule=schedule,
        child_catalog_row=child_row,
        child_parent_id=parent_id,
        child_formation_index=formation,
        child_facing_x_units=facing_x,
        child_facing_y_units=facing_y,
        child_freeze_expiry_time=freeze,
        child_travel_target_units=travel_target,
        child_travel_ticks=travel_ticks,
        child_target_distance_discount_sq_units=discount,
    )


__all__ = [
    "TensorTerminalPayloadCatalog",
    "TensorTerminalPayloadResult",
    "TerminalPayloadPreflight",
    "TerminalPayloadReason",
    "materialize_terminal_payloads_",
    "preflight_terminal_payloads",
]
