"""Retained runtime composition for the native object-manager phase.

Boundary compilation is allowed to inspect Python objects.  The retained step
path below operates exclusively on tensors: it previews the dynamically grown
object worklist, resolves represented payloads against canonical runtime
planes, allocates terminal objects, emits stable events, and commits only rows
which pass every preflight.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, fields

import torch

from clasher.battle import BattleState
from clasher.entities import (
    AreaEffect,
    Building,
    DeathAreaEffectContainer,
    Projectile,
    TimedExplosive,
    Troop,
)
from clasher.kinematics import tiles_to_logic_units
from clasher.unit_traits import is_airborne_target

from .entity_pool import EntitySelection
from .object_adapter import RuntimeObjectKind, runtime_objects_to_tensor
from .objects import (
    ObjectEventOpcode,
    ObjectPhaseResult,
    TensorObjectState,
    step_object_phase,
)
from .runtime_state import (
    RuntimeEventOpcode,
    TensorBattleRuntime,
    TickPhase,
)


@dataclass
class TensorRuntimeObjectPhase:
    """Object state plus immutable payload/target traits for retained ticks."""

    objects: TensorObjectState
    blueprint_kind: torch.Tensor
    blueprint_payload_known: torch.Tensor
    blueprint_primary_target_id: torch.Tensor
    blueprint_radius_units: torch.Tensor
    blueprint_hits_air: torch.Tensor
    blueprint_hits_ground: torch.Tensor
    blueprint_ignore_buildings: torch.Tensor
    blueprint_crown_multiplier: torch.Tensor
    blueprint_crown_damage: torch.Tensor
    blueprint_crown_damage_valid: torch.Tensor
    blueprint_building_multiplier: torch.Tensor
    blueprint_building_damage: torch.Tensor
    blueprint_building_damage_valid: torch.Tensor
    target_collision_radius_units: torch.Tensor
    target_airborne: torch.Tensor
    target_building: torch.Tensor
    target_crown: torch.Tensor
    target_payload_supported: torch.Tensor
    static_supported: torch.Tensor
    unsupported_reasons: tuple[str | None, ...]

    @property
    def device(self) -> torch.device:
        return self.objects.device

    @property
    def batch_size(self) -> int:
        return self.objects.batch_size

    @classmethod
    def from_battles(
        cls,
        runtime: TensorBattleRuntime,
        battles: Sequence[BattleState],
        *,
        max_objects: int = 128,
    ) -> TensorRuntimeObjectPhase:
        """Compile runtime objects and generalized immutable payload traits."""

        if len(battles) != runtime.batch_size:
            raise ValueError("battle count does not match runtime batch")
        adapted = runtime_objects_to_tensor(
            battles,
            device=runtime.device,
            max_objects=max_objects,
        )
        catalog_size = adapted.catalog.size

        def catalog_zeros(dtype: torch.dtype) -> torch.Tensor:
            return torch.zeros(catalog_size, dtype=dtype, device=runtime.device)

        blueprint_kind = catalog_zeros(torch.int8)
        payload_known = torch.zeros(
            catalog_size, dtype=torch.bool, device=runtime.device
        )
        primary_target = catalog_zeros(torch.int64)
        radius = catalog_zeros(torch.int32)
        hits_air = torch.ones(catalog_size, dtype=torch.bool, device=runtime.device)
        hits_ground = torch.ones(catalog_size, dtype=torch.bool, device=runtime.device)
        ignore_buildings = torch.zeros(
            catalog_size, dtype=torch.bool, device=runtime.device
        )
        crown_multiplier = torch.ones(
            catalog_size, dtype=torch.float64, device=runtime.device
        )
        crown_damage = catalog_zeros(torch.float64)
        crown_damage_valid = torch.zeros(
            catalog_size, dtype=torch.bool, device=runtime.device
        )
        building_multiplier = torch.ones(
            catalog_size, dtype=torch.float64, device=runtime.device
        )
        building_damage = catalog_zeros(torch.float64)
        building_damage_valid = torch.zeros(
            catalog_size, dtype=torch.bool, device=runtime.device
        )

        target_shape = (runtime.batch_size, runtime.max_entities)
        collision_radius = torch.zeros(
            target_shape, dtype=torch.int32, device=runtime.device
        )
        airborne = torch.zeros(target_shape, dtype=torch.bool, device=runtime.device)
        building = torch.zeros(target_shape, dtype=torch.bool, device=runtime.device)
        crown = torch.zeros(target_shape, dtype=torch.bool, device=runtime.device)
        target_supported = torch.ones(
            target_shape, dtype=torch.bool, device=runtime.device
        )
        static_supported = adapted.supported_batches.clone()
        reasons: list[str | None] = [None] * runtime.batch_size

        failure_by_batch: dict[int, list[str]] = {}
        for failure in adapted.failures:
            failure_by_batch.setdefault(failure.batch_index, []).extend(failure.reasons)
        for batch_index, values in failure_by_batch.items():
            reasons[batch_index] = "; ".join(dict.fromkeys(values))

        for batch_index, battle in enumerate(battles):
            runtime_ids = {
                int(entity_id): slot
                for slot, entity_id in enumerate(
                    runtime.battle.entity_id[batch_index].tolist()
                )
                if entity_id
            }
            if set(runtime_ids) != set(battle.entities):
                raise ValueError("runtime/oracle entity identity sets differ")
            if int(adapted.state.next_object_id[batch_index].item()) != int(
                runtime.entity_pool.next_entity_id[batch_index].item()
            ):
                raise ValueError("object/runtime next entity IDs differ")

            for entity_id, entity in battle.entities.items():
                slot = runtime_ids[entity_id]
                collision_radius[batch_index, slot] = tiles_to_logic_units(
                    entity.get_collision_radius()
                )
                airborne[batch_index, slot] = is_airborne_target(entity)
                building[batch_index, slot] = isinstance(entity, Building)
                crown[batch_index, slot] = bool(
                    isinstance(entity, Building)
                    and getattr(entity.card_stats, "name", None)
                    in {"Tower", "KingTower"}
                )
                # Runtime payload kernels do not execute recipient mechanics.
                target_supported[batch_index, slot] = not bool(entity.mechanics)

            objects = sorted(
                (
                    entity
                    for entity in battle.entities.values()
                    if not isinstance(entity, (Troop, Building))
                ),
                key=lambda entity: entity.id,
            )
            for object_slot, obj in enumerate(objects):
                blueprint_id = int(
                    adapted.state.blueprint_id[batch_index, object_slot].item()
                )
                kind = RuntimeObjectKind(int(adapted.metadata[blueprint_id].kind))
                blueprint_kind[blueprint_id] = int(kind)
                payload_known[blueprint_id] = True
                if isinstance(obj, Projectile):
                    primary_target[blueprint_id] = (
                        0 if obj.primary_target is None else obj.primary_target.id
                    )
                    radius[blueprint_id] = tiles_to_logic_units(obj.splash_radius)
                    hits_air[blueprint_id] = obj.hits_air
                    hits_ground[blueprint_id] = obj.hits_ground
                    ignore_buildings[blueprint_id] = obj.ignore_buildings
                    crown_multiplier[blueprint_id] = obj.crown_tower_damage_multiplier
                    if obj.crown_tower_damage is not None:
                        crown_damage[blueprint_id] = obj.crown_tower_damage
                        crown_damage_valid[blueprint_id] = True
                    source_mechanics = getattr(obj.source_entity, "mechanics", ())
                    if obj.damage_group_hit_entity_ids is not None or source_mechanics:
                        static_supported[batch_index] = False
                        reasons[batch_index] = (
                            "projectile damage-group/source hit callbacks lack retained state"
                        )
                elif type(obj) is AreaEffect:
                    radius[blueprint_id] = tiles_to_logic_units(obj.radius)
                    hits_air[blueprint_id] = obj.hits_air
                    hits_ground[blueprint_id] = obj.hits_ground
                    crown_multiplier[blueprint_id] = obj.crown_tower_damage_multiplier
                    building_multiplier[blueprint_id] = obj.building_damage_multiplier
                    if obj.crown_tower_damage is not None:
                        crown_damage[blueprint_id] = obj.crown_tower_damage
                        crown_damage_valid[blueprint_id] = True
                    if obj.building_damage is not None:
                        building_damage[blueprint_id] = obj.building_damage
                        building_damage_valid[blueprint_id] = True
                elif type(obj) is TimedExplosive:
                    radius[blueprint_id] = tiles_to_logic_units(obj.explosion_radius)
                    hits_air[blueprint_id] = True
                    hits_ground[blueprint_id] = True
                elif type(obj) is DeathAreaEffectContainer:
                    # The parent has no damage payload. Its terminal child has
                    # a separate blueprint and is admitted below only when its
                    # emitted amount is zero or boundary metadata is complete.
                    pass

        for blueprint_id, metadata in enumerate(adapted.metadata):
            blueprint_kind[blueprint_id] = int(metadata.kind)

        # A terminal blueprint materialized from serialized nested data has no
        # live Python object to inspect. Zero-amount payloads are complete;
        # damaging ones fail closed until their payload catalog is widened.
        unknown_damage = (~payload_known) & (adapted.catalog.amount != 0)
        if bool(unknown_damage.any().item()):
            for batch_index in range(runtime.batch_size):
                reachable = _reachable_blueprints(adapted.state, batch_index)
                if any(bool(unknown_damage[index].item()) for index in reachable):
                    static_supported[batch_index] = False
                    reasons[batch_index] = (
                        "terminal object damage payload lacks retained target metadata"
                    )

        return cls(
            objects=adapted.state,
            blueprint_kind=blueprint_kind,
            blueprint_payload_known=payload_known,
            blueprint_primary_target_id=primary_target,
            blueprint_radius_units=radius,
            blueprint_hits_air=hits_air,
            blueprint_hits_ground=hits_ground,
            blueprint_ignore_buildings=ignore_buildings,
            blueprint_crown_multiplier=crown_multiplier,
            blueprint_crown_damage=crown_damage,
            blueprint_crown_damage_valid=crown_damage_valid,
            blueprint_building_multiplier=building_multiplier,
            blueprint_building_damage=building_damage,
            blueprint_building_damage_valid=building_damage_valid,
            target_collision_radius_units=collision_radius,
            target_airborne=airborne,
            target_building=building,
            target_crown=crown,
            target_payload_supported=target_supported,
            static_supported=static_supported,
            unsupported_reasons=tuple(reasons),
        )


@dataclass(frozen=True)
class RuntimeObjectPhaseResult:
    supported_batch: torch.Tensor
    object_result: ObjectPhaseResult
    damage: torch.Tensor
    died: torch.Tensor
    spawned: torch.Tensor
    removed: EntitySelection
    event_count: torch.Tensor
    unsupported_reasons: tuple[str | None, ...]


def _reachable_blueprints(state: TensorObjectState, batch_index: int) -> set[int]:
    pending = [
        int(value)
        for value in state.blueprint_id[batch_index][
            state.allocated[batch_index]
        ].tolist()
    ]
    reachable: set[int] = set()
    while pending:
        blueprint_id = pending.pop()
        if blueprint_id in reachable or blueprint_id <= 0:
            continue
        reachable.add(blueprint_id)
        child = int(state.catalog.terminal_blueprint[blueprint_id].item())
        if child > 0:
            pending.append(child)
    return reachable


def _clone_objects(state: TensorObjectState) -> TensorObjectState:
    values: dict[str, object] = {"catalog": state.catalog}
    for descriptor in fields(state):
        if descriptor.name == "catalog":
            continue
        values[descriptor.name] = getattr(state, descriptor.name).clone()
    return TensorObjectState(**values)  # type: ignore[arg-type]


def _scatter_objects(
    destination: TensorObjectState,
    source: TensorObjectState,
    rows: torch.Tensor,
) -> None:
    for descriptor in fields(destination):
        if descriptor.name == "catalog":
            continue
        getattr(destination, descriptor.name)[rows] = getattr(source, descriptor.name)[
            rows
        ]


def _scatter_runtime(
    destination: TensorBattleRuntime,
    source: TensorBattleRuntime,
    rows: torch.Tensor,
) -> None:
    for owner_name in ("battle", "status", "phases", "events"):
        destination_owner = getattr(destination, owner_name)
        source_owner = getattr(source, owner_name)
        for descriptor in fields(destination_owner):
            destination_value = getattr(destination_owner, descriptor.name)
            source_value = getattr(source_owner, descriptor.name)
            if (
                isinstance(destination_value, torch.Tensor)
                and destination_value.ndim > 0
                and destination_value.shape[0] == destination.batch_size
            ):
                destination_value[rows] = source_value[rows]
    destination.entity_pool.active[rows] = source.entity_pool.active[rows]
    destination.entity_pool.next_entity_id[rows] = source.entity_pool.next_entity_id[
        rows
    ]
    destination.dirty[rows] = source.dirty[rows]


def _copy_tensor_fields_(destination: object, source: object) -> None:
    for descriptor in fields(destination):  # type: ignore[arg-type]
        left = getattr(destination, descriptor.name)
        right = getattr(source, descriptor.name)
        if isinstance(left, torch.Tensor) and isinstance(right, torch.Tensor):
            if left.shape != right.shape or left.dtype != right.dtype:
                raise ValueError(
                    f"object-phase plane {descriptor.name!r} changed layout"
                )
            left.copy_(right)


def _working_runtime(
    runtime: TensorBattleRuntime,
    phase: TensorRuntimeObjectPhase,
) -> TensorBattleRuntime:
    """Refresh a retained atomic object-phase buffer when its layout is stable."""

    working = getattr(phase, "_working_runtime", None)
    compatible = (
        isinstance(working, TensorBattleRuntime)
        and working.device == runtime.device
        and working.catalog is runtime.catalog
        and working.batch_size == runtime.batch_size
        and working.max_entities == runtime.max_entities
        and working.events.capacity == runtime.events.capacity
        and working.card_catalog_index.shape == runtime.card_catalog_index.shape
    )
    if not compatible:
        working = runtime.clone()
        phase._working_runtime = working  # type: ignore[attr-defined]
        return working

    assert isinstance(working, TensorBattleRuntime)
    _copy_tensor_fields_(working.battle, runtime.battle)
    _copy_tensor_fields_(working.battle.rng, runtime.battle.rng)
    working.battle.card_names = runtime.battle.card_names
    working.battle.card_to_id = runtime.battle.card_to_id
    working.card_catalog_index.copy_(runtime.card_catalog_index)
    working.entity_pool.active.copy_(runtime.entity_pool.active)
    working.entity_pool.next_entity_id.copy_(runtime.entity_pool.next_entity_id)
    _copy_tensor_fields_(working.status, runtime.status)
    _copy_tensor_fields_(working.phases, runtime.phases)
    _copy_tensor_fields_(working.events, runtime.events)
    working.supported.copy_(runtime.supported)
    working.dirty.copy_(runtime.dirty)
    return working


def _object_source(
    state: TensorObjectState,
    source_id: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    matches = (
        state.allocated
        & (state.object_id == source_id[:, None])
        & (source_id[:, None] > 0)
    )
    found = matches.any(dim=1)
    slot = matches.to(torch.int64).argmax(dim=1)
    blueprint = torch.gather(state.blueprint_id.to(torch.int64), 1, slot[:, None])[:, 0]
    return found, slot, blueprint


def _native_overlap(
    phase: TensorRuntimeObjectPhase,
    runtime: TensorBattleRuntime,
    center_x: torch.Tensor,
    center_y: torch.Tensor,
    radius: torch.Tensor,
) -> torch.Tensor:
    x = runtime.battle.entity_x_units.to(torch.int64)
    y = runtime.battle.entity_y_units.to(torch.int64)
    center_x = center_x.to(torch.int64)[:, None]
    center_y = center_y.to(torch.int64)[:, None]
    radius = radius.to(torch.int64)[:, None].clamp_min(0)
    object_radius = phase.target_collision_radius_units.to(torch.int64).clamp_min(0)
    dx = x - center_x
    dy = y - center_y
    circular_radius = radius + object_radius
    circular = dx * dx + dy * dy < circular_radius * circular_radius
    closest_x = torch.minimum(
        x + object_radius, torch.maximum(x - object_radius, center_x)
    )
    closest_y = torch.minimum(
        y + object_radius, torch.maximum(y - object_radius, center_y)
    )
    square_dx = closest_x - center_x
    square_dy = closest_y - center_y
    square = square_dx * square_dx + square_dy * square_dy < radius * radius
    return torch.where(phase.target_building, square, circular)


def _target_mask(
    phase: TensorRuntimeObjectPhase,
    runtime: TensorBattleRuntime,
    blueprint: torch.Tensor,
    source_player: torch.Tensor,
    center_x: torch.Tensor,
    center_y: torch.Tensor,
    event_opcode: torch.Tensor,
) -> torch.Tensor:
    safe = blueprint.clamp_min(0)
    radius = phase.blueprint_radius_units[safe]
    primary = phase.blueprint_primary_target_id[safe]
    projectile = event_opcode == int(ObjectEventOpcode.PROJECTILE_IMPACT)
    direct = projectile & (radius <= 0) & (primary > 0)
    direct_mask = runtime.battle.entity_id == primary[:, None]
    area_mask = _native_overlap(phase, runtime, center_x, center_y, radius)
    mask = torch.where(direct[:, None], direct_mask, area_mask)
    alive = runtime.entity_pool.active & runtime.battle.entity_active
    mask &= alive
    mask &= runtime.battle.entity_player != source_player[:, None]
    mask &= (runtime.battle.entity_kind != 2) & (runtime.battle.entity_kind != 3)
    mask &= torch.where(
        phase.target_airborne,
        phase.blueprint_hits_air[safe][:, None],
        phase.blueprint_hits_ground[safe][:, None],
    )
    mask &= ~(phase.blueprint_ignore_buildings[safe][:, None] & phase.target_building)
    return mask


def _native_percent_tensor(
    amount: torch.Tensor, multiplier: torch.Tensor
) -> torch.Tensor:
    base = torch.round(amount).to(torch.int64).clamp_min(0)
    percentage = torch.round(multiplier * 100.0).to(torch.int64).clamp_min(0)
    result = torch.where(
        (base > 0) & (percentage > 0),
        torch.div(base * percentage + 99, 100, rounding_mode="floor"),
        torch.zeros_like(base),
    )
    return result.to(torch.float64)


def _damage_by_target(
    phase: TensorRuntimeObjectPhase,
    blueprint: torch.Tensor,
    amount: torch.Tensor,
) -> torch.Tensor:
    safe = blueprint.clamp_min(0)
    base = amount[:, None].expand_as(phase.target_building)
    crown_amount = torch.where(
        phase.blueprint_crown_damage_valid[safe],
        phase.blueprint_crown_damage[safe],
        _native_percent_tensor(amount, phase.blueprint_crown_multiplier[safe]),
    )
    building_amount = torch.where(
        phase.blueprint_building_damage_valid[safe],
        phase.blueprint_building_damage[safe],
        _native_percent_tensor(amount, phase.blueprint_building_multiplier[safe]),
    )
    return torch.where(
        phase.target_crown,
        crown_amount[:, None],
        torch.where(phase.target_building, building_amount[:, None], base),
    )


def _append_events(
    runtime: TensorBattleRuntime,
    supported: torch.Tensor,
    *,
    opcode: int | torch.Tensor,
    valid: torch.Tensor,
    source_id: int | torch.Tensor = 0,
    target_id: int | torch.Tensor = 0,
    x_units: int | torch.Tensor = 0,
    y_units: int | torch.Tensor = 0,
    amount: float | torch.Tensor = 0.0,
    payload: int | torch.Tensor = 0,
) -> torch.Tensor:
    admitted = valid & supported[:, None]
    additions = admitted.sum(dim=1, dtype=torch.int64)
    overflow = supported & (
        runtime.events.count.to(torch.int64) + additions > runtime.events.capacity
    )
    supported &= ~overflow
    admitted &= supported[:, None]
    # Capacity is proven above, so write the padded lanes directly instead of
    # repeating TensorRuntimeEvents.append's host-side defensive preflight.
    events = runtime.events
    width = admitted.shape[1]

    def lanes(value: float | torch.Tensor, dtype: torch.dtype) -> torch.Tensor:
        return torch.broadcast_to(
            torch.as_tensor(value, dtype=dtype, device=runtime.device),
            (runtime.batch_size, width),
        )

    local = torch.cumsum(admitted.to(torch.int64), dim=1) - 1
    destinations = events.count.to(torch.int64)[:, None] + local
    row_lanes = torch.arange(runtime.batch_size, device=runtime.device)[
        :, None
    ].expand_as(admitted)
    row_index = row_lanes[admitted]
    event_index = destinations[admitted]
    for destination, value in (
        (events.phase, lanes(int(TickPhase.OBJECTS), torch.int8)),
        (events.opcode, lanes(opcode, torch.int16)),
        (events.source_id, lanes(source_id, torch.int64)),
        (events.target_id, lanes(target_id, torch.int64)),
        (events.x_units, lanes(x_units, torch.int32)),
        (events.y_units, lanes(y_units, torch.int32)),
        (events.amount, lanes(amount, torch.float64)),
        (events.payload, lanes(payload, torch.int64)),
    ):
        destination[row_index, event_index] = value[admitted]
    events.count.add_(admitted.sum(dim=1, dtype=events.count.dtype))
    return overflow


def _apply_damage(
    runtime: TensorBattleRuntime,
    phase: TensorRuntimeObjectPhase,
    supported: torch.Tensor,
    source_id: torch.Tensor,
    blueprint: torch.Tensor,
    target_mask: torch.Tensor,
    amount: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    unsupported_target = target_mask & ~phase.target_payload_supported
    unsupported_rows = supported & unsupported_target.any(dim=1)
    supported &= ~unsupported_rows
    committed = target_mask & supported[:, None]
    damage = _damage_by_target(phase, blueprint, amount)
    before_hp = runtime.battle.entity_hp.clone()
    before_alive = runtime.battle.entity_active.clone()
    runtime.battle.entity_hp.copy_(
        torch.where(
            committed,
            (runtime.battle.entity_hp - damage).clamp_min(0.0),
            runtime.battle.entity_hp,
        )
    )
    died = committed & before_alive & (runtime.battle.entity_hp <= 0)
    runtime.battle.entity_active &= ~died
    runtime.phases.death_pending |= died

    selection = runtime.entity_pool.id_order(committed)
    slots = selection.slots.clamp_min(0)
    ordered_damage = torch.gather(damage, 1, slots)
    ordered_x = torch.gather(runtime.battle.entity_x_units, 1, slots)
    ordered_y = torch.gather(runtime.battle.entity_y_units, 1, slots)
    ordered_died = torch.gather(died, 1, slots) & selection.valid
    pair_valid = torch.stack((selection.valid, ordered_died), dim=2).flatten(1)
    damage_opcode = torch.full_like(selection.entity_ids, RuntimeEventOpcode.DAMAGE)
    death_opcode = torch.full_like(selection.entity_ids, RuntimeEventOpcode.DEATH)
    pair_opcode = torch.stack((damage_opcode, death_opcode), dim=2).flatten(1)
    pair_target = torch.stack(
        (selection.entity_ids, selection.entity_ids), dim=2
    ).flatten(1)
    pair_source = source_id[:, None].expand_as(selection.entity_ids)
    pair_source = torch.stack((pair_source, pair_source), dim=2).flatten(1)
    pair_x = torch.stack((ordered_x, ordered_x), dim=2).flatten(1)
    pair_y = torch.stack((ordered_y, ordered_y), dim=2).flatten(1)
    pair_amount = torch.stack(
        (ordered_damage, torch.zeros_like(ordered_damage)), dim=2
    ).flatten(1)
    pair_payload = blueprint[:, None].expand_as(selection.entity_ids)
    pair_payload = torch.stack((pair_payload, pair_payload), dim=2).flatten(1)
    overflow = _append_events(
        runtime,
        supported,
        opcode=pair_opcode,
        valid=pair_valid,
        source_id=pair_source,
        target_id=pair_target,
        x_units=pair_x,
        y_units=pair_y,
        amount=pair_amount,
        payload=pair_payload,
    )
    unsupported_rows |= overflow
    # Rows rejected during event preflight live only in the working clone and
    # are discarded by the caller, so no rollback is needed here.
    return unsupported_rows, before_hp - runtime.battle.entity_hp, died


def _clear_entity_slots(runtime: TensorBattleRuntime, mask: torch.Tensor) -> None:
    for descriptor in fields(runtime.battle):
        value = getattr(runtime.battle, descriptor.name)
        if (
            descriptor.name.startswith("entity_")
            and descriptor.name != "entity_id"
            and isinstance(value, torch.Tensor)
            and value.ndim >= 2
            and value.shape[:2] == mask.shape
        ):
            if descriptor.name == "entity_tower_slot":
                value.masked_fill_(mask, -1)
            else:
                value.masked_fill_(mask, 0)
    for owner in (runtime.status, runtime.phases):
        for descriptor in fields(owner):
            if owner is runtime.phases and descriptor.name in {
                "phase_cursor",
                "supported",
                "dirty",
            }:
                continue
            value = getattr(owner, descriptor.name)
            if (
                isinstance(value, torch.Tensor)
                and value.ndim >= 2
                and value.shape[:2] == mask.shape
            ):
                expanded = mask.reshape(*mask.shape, *((1,) * (value.ndim - 2)))
                value.masked_fill_(expanded, 0)


def _initialize_spawned_objects(
    runtime: TensorBattleRuntime,
    phase: TensorRuntimeObjectPhase,
    object_state: TensorObjectState,
    supported: torch.Tensor,
    spawn_rows: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    missing = object_state.allocated & ~(
        (object_state.object_id[:, :, None] == runtime.battle.entity_id[:, None, :])
        & runtime.entity_pool.active[:, None, :]
    ).any(dim=2)
    candidate_id = torch.where(
        missing,
        object_state.object_id,
        torch.full_like(object_state.object_id, torch.iinfo(torch.int64).max),
    )
    expected_id, object_slot = candidate_id.min(dim=1)
    valid = spawn_rows & supported & (expected_id != torch.iinfo(torch.int64).max)
    available = (~runtime.entity_pool.active).sum(dim=1)
    overflow = valid & (available < 1)
    mismatch = valid & (expected_id != runtime.entity_pool.next_entity_id)
    supported &= ~(overflow | mismatch)
    valid &= supported
    # One object event can materialize at most one canonical entity per row.
    # Allocate its monotonic ID into the lowest free slot directly, avoiding
    # EntityPool.allocate's defensive host-side capacity synchronization.
    free = ~runtime.entity_pool.active
    slot_numbers = getattr(phase, "_entity_slot_numbers", None)
    if not isinstance(slot_numbers, torch.Tensor) or slot_numbers.shape != (
        runtime.entity_pool.capacity,
    ):
        slot_numbers = torch.arange(
            runtime.entity_pool.capacity,
            dtype=torch.int64,
            device=runtime.device,
        )
        phase._entity_slot_numbers = slot_numbers  # type: ignore[attr-defined]
    free_keys = torch.where(
        free,
        slot_numbers[None, :],
        torch.full_like(runtime.entity_pool.entity_id, runtime.entity_pool.capacity),
    )
    allocated_slot = free_keys.min(dim=1).values.clamp_max(
        runtime.entity_pool.capacity - 1
    )
    rows = torch.where(valid)[0]
    entity_slots = allocated_slot[rows]
    runtime.entity_pool.active[rows, entity_slots] = True
    runtime.entity_pool.entity_id[rows, entity_slots] = expected_id[rows]
    runtime.entity_pool.next_entity_id.add_(valid.to(torch.int64))
    source_object_slots = object_slot[rows]
    blueprint = object_state.blueprint_id[rows, source_object_slots].to(torch.int64)
    kind = phase.blueprint_kind[blueprint]

    # Reset every canonical entity-aligned plane before installing the child.
    reset_mask = torch.zeros_like(runtime.entity_pool.active)
    reset_mask[rows, entity_slots] = True
    _clear_entity_slots(runtime, reset_mask)
    runtime.battle.entity_id[rows, entity_slots] = expected_id[rows]
    runtime.entity_pool.active[rows, entity_slots] = True
    runtime.battle.entity_active[rows, entity_slots] = True
    runtime.battle.entity_kind[rows, entity_slots] = torch.where(
        (kind == int(RuntimeObjectKind.PROJECTILE))
        | (kind == int(RuntimeObjectKind.SPAWN_PROJECTILE)),
        torch.full_like(kind, 2),
        torch.full_like(kind, 3),
    )
    runtime.battle.entity_player[rows, entity_slots] = object_state.player[
        rows, source_object_slots
    ]
    runtime.battle.entity_x_units[rows, entity_slots] = object_state.x_units[
        rows, source_object_slots
    ]
    runtime.battle.entity_y_units[rows, entity_slots] = object_state.y_units[
        rows, source_object_slots
    ]
    runtime.battle.entity_hp[rows, entity_slots] = 1.0
    runtime.battle.entity_max_hp[rows, entity_slots] = 1.0
    runtime.battle.entity_tower_slot[rows, entity_slots] = -1
    spawned = torch.zeros_like(runtime.entity_pool.active)
    spawned[rows, entity_slots] = True
    return overflow | mismatch, spawned


def step_runtime_object_phase_(
    runtime: TensorBattleRuntime,
    phase: TensorRuntimeObjectPhase,
    *,
    battle_mask: torch.Tensor | None = None,
) -> RuntimeObjectPhaseResult:
    """Advance one retained object phase without Python object stepping."""

    if phase.batch_size != runtime.batch_size or phase.device != runtime.device:
        raise ValueError("runtime object phase has incompatible batch/device")
    selected = (
        torch.ones(runtime.batch_size, dtype=torch.bool, device=runtime.device)
        if battle_mask is None
        else torch.as_tensor(battle_mask, dtype=torch.bool, device=runtime.device)
    )
    if selected.shape != (runtime.batch_size,):
        raise ValueError("battle_mask must have shape [batch_size]")
    attempted = (
        selected & runtime.supported & runtime.phases.supported[:, TickPhase.OBJECTS]
    )
    supported = attempted & phase.static_supported
    if runtime.device.type not in {"cpu", "cuda"}:
        supported &= False

    event_count_before = runtime.events.count.clone()
    working = _working_runtime(runtime, phase)
    object_preview = _clone_objects(phase.objects)
    object_result = step_object_phase(object_preview)
    supported &= ~object_result.unsupported_batch
    initial_supported = attempted.clone()
    reasons = list(phase.unsupported_reasons)
    damage_total = torch.zeros_like(runtime.battle.entity_hp)
    died_total = torch.zeros_like(runtime.battle.entity_active)
    spawned_total = torch.zeros_like(runtime.entity_pool.active)
    pending: list[tuple[torch.Tensor, ...]] = []
    event_limit = int(object_result.events.count.max().item())

    for event_index in range(event_limit):
        event_valid = event_index < object_result.events.count
        event_opcode = object_result.events.opcode[:, event_index].to(torch.int64)
        source_id = object_result.events.source_id[:, event_index]
        source_player = object_result.events.player[:, event_index]
        center_x = object_result.events.x_units[:, event_index]
        center_y = object_result.events.y_units[:, event_index]
        amount = object_result.events.amount[:, event_index]
        found, _, blueprint = _object_source(object_preview, source_id)
        missing_source = supported & event_valid & ~found
        supported &= ~missing_source

        projectile = (
            event_valid
            & (event_opcode == int(ObjectEventOpcode.PROJECTILE_IMPACT))
            & supported
        )
        area = (
            event_valid & (event_opcode == int(ObjectEventOpcode.AREA_TICK)) & supported
        )
        spawn = event_valid & (event_opcode == int(ObjectEventOpcode.SPAWN)) & supported
        death = event_valid & (event_opcode == int(ObjectEventOpcode.DEATH)) & supported
        kind = phase.blueprint_kind[blueprint.clamp_min(0)]
        timed_death = death & (kind == int(RuntimeObjectKind.TIMED_EXPLOSIVE))

        marker_valid = projectile[:, None]
        overflow = _append_events(
            working,
            supported,
            opcode=RuntimeEventOpcode.PROJECTILE,
            valid=marker_valid,
            source_id=source_id[:, None],
            x_units=center_x[:, None],
            y_units=center_y[:, None],
            amount=amount[:, None],
            payload=blueprint[:, None],
        )
        supported &= ~overflow
        projectile_targets = _target_mask(
            phase,
            working,
            blueprint,
            source_player,
            center_x,
            center_y,
            event_opcode,
        )
        pending.append(
            (
                projectile & supported,
                source_id.clone(),
                blueprint.clone(),
                projectile_targets,
                amount.clone(),
            )
        )

        overflow = _append_events(
            working,
            supported,
            opcode=RuntimeEventOpcode.AREA,
            valid=area[:, None],
            source_id=source_id[:, None],
            x_units=center_x[:, None],
            y_units=center_y[:, None],
            amount=amount[:, None],
            payload=blueprint[:, None],
        )
        supported &= ~overflow
        damage_event = area | timed_death
        area_targets = _target_mask(
            phase,
            working,
            blueprint,
            source_player,
            center_x,
            center_y,
            torch.full_like(event_opcode, ObjectEventOpcode.AREA_TICK),
        )
        unsupported, damage, died = _apply_damage(
            working,
            phase,
            supported,
            source_id,
            blueprint,
            area_targets & damage_event[:, None],
            amount,
        )
        supported &= ~unsupported
        damage_total += damage
        died_total |= died

        unsupported, spawned = _initialize_spawned_objects(
            working, phase, object_preview, supported, spawn
        )
        supported &= ~unsupported
        spawned_total |= spawned
        child_id = (
            torch.where(
                spawned,
                working.battle.entity_id,
                torch.zeros_like(working.battle.entity_id),
            )
            .max(dim=1)
            .values
        )
        overflow = _append_events(
            working,
            supported,
            opcode=RuntimeEventOpcode.SPAWN,
            valid=(spawn & supported)[:, None],
            source_id=source_id[:, None],
            target_id=child_id[:, None],
            x_units=center_x[:, None],
            y_units=center_y[:, None],
            payload=object_result.events.payload_id[:, event_index, None],
        )
        supported &= ~overflow

        projectile_source = (kind == int(RuntimeObjectKind.PROJECTILE)) | (
            kind == int(RuntimeObjectKind.SPAWN_PROJECTILE)
        )
        immediate_death = death & ~projectile_source
        slots = working.entity_pool.slots_for_ids(source_id[:, None])[:, 0]
        exists = slots >= 0
        unsupported = immediate_death & ~exists
        supported &= ~unsupported
        rows = torch.where(immediate_death & supported)[0]
        entity_slots = slots[rows]
        working.battle.entity_active[rows, entity_slots] = False
        working.phases.death_pending[rows, entity_slots] = True
        died_total[rows, entity_slots] = True
        overflow = _append_events(
            working,
            supported,
            opcode=RuntimeEventOpcode.DEATH,
            valid=(immediate_death & supported)[:, None],
            source_id=source_id[:, None],
            x_units=center_x[:, None],
            y_units=center_y[:, None],
            payload=blueprint[:, None],
        )
        supported &= ~overflow

    # Native projectiles commit target snapshots during the object worklist
    # and resolve them afterward in impact order.
    for projectile, source_id, blueprint, targets, amount in pending:
        unsupported, damage, died = _apply_damage(
            working,
            phase,
            supported,
            source_id,
            blueprint,
            targets & projectile[:, None],
            amount,
        )
        supported &= ~unsupported
        damage_total += damage
        died_total |= died
        slots = working.entity_pool.slots_for_ids(source_id[:, None])[:, 0]
        rows = torch.where(projectile & supported & (slots >= 0))[0]
        entity_slots = slots[rows]
        working.battle.entity_active[rows, entity_slots] = False
        working.phases.death_pending[rows, entity_slots] = True
        died_total[rows, entity_slots] = True
        overflow = _append_events(
            working,
            supported,
            opcode=RuntimeEventOpcode.DEATH,
            valid=(projectile & supported)[:, None],
            source_id=source_id[:, None],
            payload=blueprint[:, None],
        )
        supported &= ~overflow

    # Publish every still-canonical coordinate in one object/entity join.
    object_ids = object_preview.object_id
    matches = (
        object_preview.allocated[:, :, None]
        & working.entity_pool.active[:, None, :]
        & (object_ids[:, :, None] == working.battle.entity_id[:, None, :])
        & (object_ids[:, :, None] > 0)
    )
    found = matches.any(dim=2) & supported[:, None]
    entity_slots = matches.to(torch.int64).argmax(dim=2)
    publish_rows, object_slots = torch.where(found)
    publish_entities = entity_slots[publish_rows, object_slots]
    working.battle.entity_x_units[publish_rows, publish_entities] = (
        object_preview.x_units[publish_rows, object_slots]
    )
    working.battle.entity_y_units[publish_rows, publish_entities] = (
        object_preview.y_units[publish_rows, object_slots]
    )

    dead = (
        supported[:, None] & working.entity_pool.active & ~working.battle.entity_active
    )
    removed = working.entity_pool.cleanup(dead)
    _clear_entity_slots(working, dead)
    working.phases.death_pending &= ~dead
    object_dead = object_preview.allocated & ~object_preview.active & supported[:, None]
    for descriptor in fields(object_preview):
        if descriptor.name == "catalog":
            continue
        value = getattr(object_preview, descriptor.name)
        if value.ndim == 2 and value.shape == object_dead.shape:
            value.masked_fill_(object_dead, 0)
    object_preview.allocated &= ~object_dead

    failed = initial_supported & ~supported
    for batch_index in torch.where(failed)[0].tolist():
        reasons[batch_index] = reasons[batch_index] or (
            "object event payload, allocation, or event capacity is unsupported"
        )
    runtime.mark_unsupported(failed, phase=TickPhase.OBJECTS)
    rows = torch.where(supported)[0]
    if rows.numel():
        working.mark_dirty(supported, phase=TickPhase.OBJECTS)
        _scatter_runtime(runtime, working, rows)
        _scatter_objects(phase.objects, object_preview, rows)

    event_count = torch.where(
        supported,
        runtime.events.count - event_count_before,
        torch.zeros_like(runtime.events.count),
    )
    return RuntimeObjectPhaseResult(
        supported_batch=supported,
        object_result=object_result,
        damage=torch.where(supported[:, None], damage_total, 0.0),
        died=died_total & supported[:, None],
        spawned=spawned_total & supported[:, None],
        removed=removed,
        event_count=event_count,
        unsupported_reasons=tuple(reasons),
    )
