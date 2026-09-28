"""Exact scalar-state adapter for the batched movement kernels.

The movement kernels operate on native integer coordinates and deliberately do
not know about Python ``Entity`` objects.  This module is the narrow boundary
between those representations.  It compiles the scalar pathfinder's current
route head on a clone (so merely inspecting support cannot mutate the oracle),
publishes every body-pressure input in stable entity-ID order, and can restore
the hidden movement-component state after a tensor phase.

Support is intentionally split between ordinary target-directed movement and
an already-active river jump.  A false mask is a fail-closed request for the
Python oracle; it is never interpreted as "the entity does not move".
"""

from __future__ import annotations

import struct
from collections.abc import Sequence
from dataclasses import dataclass
from enum import IntFlag

import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Entity, Troop
from clasher.kinematics import logic_units_to_tiles, tiles_to_logic_units
from clasher.native_tilemap import STANDARD_PATH_HEIGHT, STANDARD_PATH_WIDTH
from clasher.pathfinding import ground_path_waypoint, native_single_node_waypoint
from clasher.unit_traits import is_in_transit, uses_air_collision_plane

from .movement import (
    CollisionBatch,
    NaturalMovementResult,
    RiverJumpResult,
    advance_route_node_mask,
    natural_movement_support_mask,
)


class MovementUnsupported(IntFlag):
    """Bitwise reason codes shared by the explicit support masks."""

    NONE = 0
    INACTIVE = 1 << 0
    NOT_TROOP = 1 << 1
    MECHANIC_HOOK = 1 << 2
    NOT_DEPLOYED = 1 << 3
    NO_TARGET = 1 << 4
    INVALID_TARGET = 1 << 5
    NO_WAYPOINT = 1 << 6
    STUNNED = 1 << 7
    FORCED_MOVEMENT = 1 << 8
    SPECIAL_MOVEMENT = 1 << 9
    DEATH_SPAWN_TRAVEL = 1 << 10
    KNOCKBACK = 1 << 11
    KAMIKAZE = 1 << 12
    RIVER_JUMP_ACTIVE = 1 << 13
    RIVER_JUMP_INACTIVE = 1 << 14
    MISSING_RIVER_STATE = 1 << 15
    INVALID_JUMP_SPEED = 1 << 16
    UNKNOWN_ROUTE_CACHE = 1 << 17
    CHARGE_COMPONENT = 1 << 18
    MOVEMENT_CYCLE = 1 << 19
    AVOIDANCE_PREPASS = 1 << 20


_CACHE_NONE = 0
_CACHE_GROUND = 1
_CACHE_SINGLE = 2
_MAX_ROUTE_NODES = STANDARD_PATH_WIDTH * STANDARD_PATH_HEIGHT


def _float_to_int64_bits(value: float) -> int:
    """Store a Python binary64 value losslessly in an integer tensor lane."""

    unsigned = struct.unpack("!Q", struct.pack("!d", float(value)))[0]
    return int(unsigned if unsigned < 1 << 63 else unsigned - (1 << 64))


def _int64_bits_to_float(value: int) -> float:
    unsigned = int(value) & ((1 << 64) - 1)
    return float(struct.unpack("!d", struct.pack("!Q", unsigned))[0])


def _optional_position_units(entity: Entity, name: str) -> tuple[int, int] | None:
    value = getattr(entity, name, None)
    if not isinstance(value, Position):
        return None
    return tiles_to_logic_units(value.x), tiles_to_logic_units(value.y)


def _parse_route_cache_key(
    key: object,
) -> tuple[int, tuple[int, int], int, bool] | None:
    if key is None:
        return (_CACHE_NONE, (-1, -1), 0, False)
    if (
        isinstance(key, tuple)
        and len(key) == 2
        and key[0] == "single"
        and isinstance(key[1], tuple)
        and len(key[1]) == 2
    ):
        return (_CACHE_SINGLE, (int(key[1][0]), int(key[1][1])), 0, False)
    if (
        isinstance(key, tuple)
        and len(key) == 3
        and isinstance(key[0], tuple)
        and len(key[0]) == 2
    ):
        return (
            _CACHE_GROUND,
            (int(key[0][0]), int(key[0][1])),
            int(key[1]),
            bool(key[2]),
        )
    return None


def _route_cells(entity: Entity) -> tuple[tuple[int, int], ...]:
    raw = getattr(entity, "_native_ground_route_cells", None)
    if not isinstance(raw, list):
        return ()
    result: list[tuple[int, int]] = []
    for cell in raw:
        if not isinstance(cell, tuple) or len(cell) != 2:
            return ()
        result.append((int(cell[0]), int(cell[1])))
    return tuple(result)


@dataclass
class TensorMovementAdapter:
    """Dense movement boundary for a batch of scalar battles.

    Every tensor except the final coordinate axis uses ``[battle, entity]``.
    Active slots are packed in increasing entity-ID order.  Route cells use a
    third variable-capacity axis and remain integer half-tile indices.
    """

    device: torch.device
    entity_id: torch.Tensor
    slot_present: torch.Tensor
    entity_active: torch.Tensor
    entity_kind: torch.Tensor
    player_id: torch.Tensor
    position_units: torch.Tensor
    target_id: torch.Tensor
    target_slot: torch.Tensor
    target_position_units: torch.Tensor
    target_valid: torch.Tensor
    waypoint_units: torch.Tensor
    waypoint_valid: torch.Tensor
    route_cells: torch.Tensor
    route_count: torch.Tensor
    route_cache_kind: torch.Tensor
    route_cache_goal: torch.Tensor
    route_cache_lane: torch.Tensor
    route_cache_jump: torch.Tensor
    route_cache_backwards: torch.Tensor
    ground_path_backwards: torch.Tensor
    is_troop: torch.Tensor
    is_air: torch.Tensor
    is_hover: torch.Tensor
    lane_id: torch.Tensor
    jump_height: torch.Tensor
    jump_speed_units: torch.Tensor
    effective_speed_units: torch.Tensor
    collision_radius_units: torch.Tensor
    mass_milliunits: torch.Tensor
    air_collision: torch.Tensor
    in_transit: torch.Tensor
    mega_knight_airborne: torch.Tensor
    stunned: torch.Tensor
    forced_movement: torch.Tensor
    special_movement: torch.Tensor
    death_spawn_travel: torch.Tensor
    knockback_active: torch.Tensor
    kamikaze_primed: torch.Tensor
    mechanic_free: torch.Tensor
    charge_component: torch.Tensor
    movement_cycle: torch.Tensor
    avoidance_prepass_required: torch.Tensor
    facing_units: torch.Tensor
    avoidance: torch.Tensor
    accumulated_vector_units: torch.Tensor
    accumulated_vector_count: torch.Tensor
    accumulated_vector_bypasses_cap: torch.Tensor
    pending_vector_units: torch.Tensor
    pending_vector_consumed: torch.Tensor
    natural_movement_active: torch.Tensor
    movement_phase_elapsed_ms: torch.Tensor
    native_charge_progress: torch.Tensor
    distance_traveled_bits: torch.Tensor
    river_jump_active: torch.Tensor
    river_jump_blocked: torch.Tensor
    river_origin_units: torch.Tensor
    river_origin_valid: torch.Tensor
    river_target_units: torch.Tensor
    river_target_valid: torch.Tensor
    river_elapsed_bits: torch.Tensor
    river_duration_bits: torch.Tensor
    special_move_consumed_tick: torch.Tensor
    stun_interrupt_deferred: torch.Tensor
    ordinary_unsupported: torch.Tensor
    river_unsupported: torch.Tensor
    ordinary_supported: torch.Tensor
    river_jump_supported: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.entity_id.shape[0])

    @property
    def max_entities(self) -> int:
        return int(self.entity_id.shape[1])

    @property
    def route_capacity(self) -> int:
        return int(self.route_cells.shape[2])

    def collision_batch(self) -> CollisionBatch:
        """Return the exact inputs consumed by the body-pressure kernel."""

        return CollisionBatch(
            position_units=self.position_units,
            active=self.entity_active & self.slot_present,
            entity_id=self.entity_id,
            entity_kind=self.entity_kind,
            player_id=self.player_id,
            collision_radius_units=self.collision_radius_units,
            mass_milliunits=self.mass_milliunits,
            air_collision=self.air_collision,
            stunned=self.stunned,
            in_transit=self.in_transit,
            river_jump_active=self.river_jump_active,
            death_spawn_travel=self.death_spawn_travel,
            mega_knight_airborne=self.mega_knight_airborne,
        )

    def slots_for_ids(self, battle_index: int, entity_ids: Sequence[int]) -> list[int]:
        """Resolve IDs without exposing Python object identity to tensor code."""

        if not 0 <= battle_index < self.batch_size:
            raise IndexError("battle index is out of range")
        slot_by_id = {
            int(entity_id): slot
            for slot, entity_id in enumerate(self.entity_id[battle_index].tolist())
            if int(entity_id) != 0
        }
        try:
            return [slot_by_id[int(entity_id)] for entity_id in entity_ids]
        except KeyError as exc:
            raise KeyError(
                f"entity ID {exc.args[0]} is absent from movement batch"
            ) from exc

    @classmethod
    def from_battles(
        cls,
        battles: Sequence[BattleState],
        *,
        device: str | torch.device = "cpu",
        max_entities: int | None = None,
    ) -> TensorMovementAdapter:
        """Compile path heads and movement traits without mutating ``battles``."""

        if not battles:
            raise ValueError("at least one battle is required")
        entity_capacity = max_entities or max(
            len(battle.entities) for battle in battles
        )
        if entity_capacity < max(len(battle.entities) for battle in battles):
            raise ValueError("max_entities is smaller than the battle object count")

        # Route selection mutates retained path state. Run it on one exact
        # battle clone per lane and later publish the compiled cache tensors.
        clones = [battle.clone() for battle in battles]
        compiled_waypoints: list[dict[int, Position]] = []
        cache_is_known: list[dict[int, bool]] = []
        avoidance_prepass_by_id: list[dict[int, bool]] = []
        maximum_route = 1
        for clone in clones:
            waypoints: dict[int, Position] = {}
            known: dict[int, bool] = {}
            avoidance_needed: dict[int, bool] = {}
            for entity in sorted(clone.entities.values(), key=lambda item: item.id):
                target_id = getattr(entity, "_movement_target_id", None)
                target = (
                    clone.entities.get(target_id) if target_id is not None else None
                )
                target_is_valid = bool(
                    target is not None
                    and target.is_alive
                    and isinstance(entity, Troop)
                    and entity._is_valid_target(target, is_current_target=True)
                )
                ordinary_candidate = bool(
                    isinstance(entity, Troop)
                    and entity.is_alive
                    and target_is_valid
                    and entity.deploy_delay_remaining <= 1e-9
                    and not entity.mechanics
                    and not entity.is_stunned()
                    and not entity.forced_movement_active
                    and entity._death_spawn_travel_ticks_remaining <= 0
                    and entity._knockback_target is None
                    and not entity.kamikaze_primed
                    and not getattr(entity, "_river_jump_active", False)
                    and not getattr(entity, "_special_move_active", False)
                    and not getattr(entity, "_special_move_consumed_tick", False)
                )
                if (
                    isinstance(entity, Troop)
                    and ordinary_candidate
                    and target is not None
                ):
                    previous_avoidance = entity._native_avoidance
                    previous_route = list(
                        getattr(entity, "_native_ground_route_cells", [])
                    )
                    entity._update_native_avoidance(clone)
                    avoidance_needed[entity.id] = bool(
                        entity._native_avoidance != previous_avoidance
                        or list(getattr(entity, "_native_ground_route_cells", []))
                        != previous_route
                    )
                    entity._native_avoidance = previous_avoidance
                    setattr(entity, "_native_ground_route_cells", previous_route)
                    if entity.is_air_unit:
                        waypoint = native_single_node_waypoint(entity, target)
                    else:
                        waypoint = ground_path_waypoint(
                            clone,
                            entity,
                            target.position,
                            target_entity=target,
                            backwards_reference=target.position,
                        )
                    waypoints[entity.id] = Position(waypoint.x, waypoint.y)
                parsed = _parse_route_cache_key(
                    getattr(entity, "_ground_path_cache_key", None)
                )
                known[entity.id] = parsed is not None
                avoidance_needed.setdefault(entity.id, False)
                maximum_route = max(maximum_route, len(_route_cells(entity)))
            compiled_waypoints.append(waypoints)
            cache_is_known.append(known)
            avoidance_prepass_by_id.append(avoidance_needed)
        if maximum_route > _MAX_ROUTE_NODES:
            raise ValueError("retained route exceeds the serialized arena capacity")

        torch_device = torch.device(device)
        batch_size = len(battles)

        def zeros(*shape: int, dtype: torch.dtype = torch.int64) -> torch.Tensor:
            return torch.zeros(shape, dtype=dtype, device=torch_device)

        entity_id = zeros(batch_size, entity_capacity)
        slot_present = zeros(batch_size, entity_capacity, dtype=torch.bool)
        entity_active = zeros(batch_size, entity_capacity, dtype=torch.bool)
        entity_kind = zeros(batch_size, entity_capacity)
        player_id = zeros(batch_size, entity_capacity)
        position_units = zeros(batch_size, entity_capacity, 2)
        target_id = torch.full_like(entity_id, -1)
        target_slot = torch.full_like(entity_id, -1)
        target_position_units = zeros(batch_size, entity_capacity, 2)
        target_valid = zeros(batch_size, entity_capacity, dtype=torch.bool)
        waypoint_units = zeros(batch_size, entity_capacity, 2)
        waypoint_valid = zeros(batch_size, entity_capacity, dtype=torch.bool)
        route_cells = zeros(batch_size, entity_capacity, maximum_route, 2)
        route_count = zeros(batch_size, entity_capacity)
        route_cache_kind = zeros(batch_size, entity_capacity)
        route_cache_goal = torch.full(
            (batch_size, entity_capacity, 2),
            -1,
            dtype=torch.int64,
            device=torch_device,
        )
        route_cache_lane = zeros(batch_size, entity_capacity)
        route_cache_jump = zeros(batch_size, entity_capacity, dtype=torch.bool)
        route_cache_backwards = zeros(batch_size, entity_capacity, dtype=torch.bool)
        ground_path_backwards = zeros(batch_size, entity_capacity, dtype=torch.bool)
        is_troop = zeros(batch_size, entity_capacity, dtype=torch.bool)
        is_air = zeros(batch_size, entity_capacity, dtype=torch.bool)
        is_hover = zeros(batch_size, entity_capacity, dtype=torch.bool)
        lane_id = zeros(batch_size, entity_capacity)
        jump_height = zeros(batch_size, entity_capacity, dtype=torch.bool)
        jump_speed_units = zeros(batch_size, entity_capacity)
        effective_speed_units = zeros(batch_size, entity_capacity)
        collision_radius_units = zeros(batch_size, entity_capacity)
        mass_milliunits = zeros(batch_size, entity_capacity)
        air_collision = zeros(batch_size, entity_capacity, dtype=torch.bool)
        in_transit_tensor = zeros(batch_size, entity_capacity, dtype=torch.bool)
        mega_knight_airborne = zeros(batch_size, entity_capacity, dtype=torch.bool)
        stunned = zeros(batch_size, entity_capacity, dtype=torch.bool)
        forced_movement = zeros(batch_size, entity_capacity, dtype=torch.bool)
        special_movement = zeros(batch_size, entity_capacity, dtype=torch.bool)
        death_spawn_travel = zeros(batch_size, entity_capacity, dtype=torch.bool)
        knockback_active = zeros(batch_size, entity_capacity, dtype=torch.bool)
        kamikaze_primed = zeros(batch_size, entity_capacity, dtype=torch.bool)
        mechanic_free = zeros(batch_size, entity_capacity, dtype=torch.bool)
        charge_component = zeros(batch_size, entity_capacity, dtype=torch.bool)
        movement_cycle = zeros(batch_size, entity_capacity, dtype=torch.bool)
        avoidance_prepass_required = zeros(
            batch_size, entity_capacity, dtype=torch.bool
        )
        facing_units = zeros(batch_size, entity_capacity, 2)
        avoidance = zeros(batch_size, entity_capacity)
        accumulated_vector_units = zeros(batch_size, entity_capacity, 2)
        accumulated_vector_count = zeros(batch_size, entity_capacity)
        accumulated_vector_bypasses_cap = zeros(
            batch_size, entity_capacity, dtype=torch.bool
        )
        pending_vector_units = zeros(batch_size, entity_capacity, 2)
        pending_vector_consumed = zeros(batch_size, entity_capacity, dtype=torch.bool)
        natural_movement_active = zeros(batch_size, entity_capacity, dtype=torch.bool)
        movement_phase_elapsed_ms = zeros(batch_size, entity_capacity)
        native_charge_progress = zeros(batch_size, entity_capacity)
        distance_traveled_bits = zeros(batch_size, entity_capacity)
        river_jump_active = zeros(batch_size, entity_capacity, dtype=torch.bool)
        river_jump_blocked = zeros(batch_size, entity_capacity, dtype=torch.bool)
        river_origin_units = zeros(batch_size, entity_capacity, 2)
        river_origin_valid = zeros(batch_size, entity_capacity, dtype=torch.bool)
        river_target_units = zeros(batch_size, entity_capacity, 2)
        river_target_valid = zeros(batch_size, entity_capacity, dtype=torch.bool)
        river_elapsed_bits = zeros(batch_size, entity_capacity)
        river_duration_bits = zeros(batch_size, entity_capacity)
        special_move_consumed_tick = zeros(
            batch_size, entity_capacity, dtype=torch.bool
        )
        stun_interrupt_deferred = zeros(batch_size, entity_capacity, dtype=torch.bool)

        for batch_index, (battle, clone) in enumerate(
            zip(battles, clones, strict=True)
        ):
            original_entities = sorted(
                battle.entities.values(), key=lambda item: item.id
            )
            clone_by_id = clone.entities
            slot_by_id = {
                entity.id: slot for slot, entity in enumerate(original_entities)
            }
            for slot, original in enumerate(original_entities):
                entity = clone_by_id[original.id]
                stats = getattr(entity, "card_stats", None)
                entity_id[batch_index, slot] = entity.id
                slot_present[batch_index, slot] = True
                entity_active[batch_index, slot] = bool(entity.is_alive)
                entity_kind[batch_index, slot] = int(entity.entity_kind)
                player_id[batch_index, slot] = int(entity.player_id)
                position_units[batch_index, slot] = torch.tensor(
                    (
                        tiles_to_logic_units(entity.position.x),
                        tiles_to_logic_units(entity.position.y),
                    ),
                    dtype=torch.int64,
                    device=torch_device,
                )
                movement_target_id = getattr(entity, "_movement_target_id", None)
                target = (
                    clone_by_id.get(movement_target_id)
                    if movement_target_id is not None
                    else None
                )
                if movement_target_id is not None:
                    target_id[batch_index, slot] = int(movement_target_id)
                if target is not None:
                    target_slot[batch_index, slot] = slot_by_id[target.id]
                    target_position_units[batch_index, slot] = torch.tensor(
                        (
                            tiles_to_logic_units(target.position.x),
                            tiles_to_logic_units(target.position.y),
                        ),
                        dtype=torch.int64,
                        device=torch_device,
                    )
                    target_valid[batch_index, slot] = bool(
                        target.is_alive
                        and isinstance(entity, Troop)
                        and entity._is_valid_target(target, is_current_target=True)
                    )

                compiled_waypoint = compiled_waypoints[batch_index].get(entity.id)
                if compiled_waypoint is not None:
                    waypoint_units[batch_index, slot] = torch.tensor(
                        (
                            tiles_to_logic_units(compiled_waypoint.x),
                            tiles_to_logic_units(compiled_waypoint.y),
                        ),
                        dtype=torch.int64,
                        device=torch_device,
                    )
                    waypoint_valid[batch_index, slot] = True

                retained = _route_cells(entity)
                route_count[batch_index, slot] = len(retained)
                for route_index, cell in enumerate(retained):
                    route_cells[batch_index, slot, route_index] = torch.tensor(
                        cell, dtype=torch.int64, device=torch_device
                    )
                parsed_cache = _parse_route_cache_key(
                    getattr(entity, "_ground_path_cache_key", None)
                )
                if parsed_cache is not None:
                    cache_kind, cache_goal, cache_lane, cache_jump = parsed_cache
                    route_cache_kind[batch_index, slot] = cache_kind
                    route_cache_goal[batch_index, slot] = torch.tensor(
                        cache_goal, dtype=torch.int64, device=torch_device
                    )
                    route_cache_lane[batch_index, slot] = cache_lane
                    route_cache_jump[batch_index, slot] = cache_jump
                route_cache_backwards[batch_index, slot] = bool(
                    getattr(entity, "_ground_path_cache_backwards", False)
                )
                ground_path_backwards[batch_index, slot] = bool(
                    getattr(entity, "_ground_path_backwards", False)
                )

                troop = isinstance(entity, Troop)
                is_troop[batch_index, slot] = troop
                is_air[batch_index, slot] = bool(getattr(entity, "is_air_unit", False))
                is_hover[batch_index, slot] = bool(
                    getattr(entity, "_is_hover_unit", False)
                )
                lane_id[batch_index, slot] = int(
                    getattr(entity, "_native_lane_id", 0) or 0
                )
                jump_height[batch_index, slot] = bool(
                    getattr(stats, "jump_height", None)
                )
                jump_speed_units[batch_index, slot] = round(
                    float(getattr(stats, "jump_speed", 0) or 0)
                )
                if troop:
                    effective_speed_units[batch_index, slot] = (
                        entity._native_scaled_speed(
                            entity._unslowed_movement_speed(),
                            entity._movement_debuff_multiplier(),
                            entity.movement_speed_buff_multiplier,
                        )
                    )
                collision_radius_units[batch_index, slot] = max(
                    0, tiles_to_logic_units(entity.get_collision_radius())
                )
                mass_milliunits[batch_index, slot] = max(
                    1, round(entity.get_unit_mass() * 1000.0)
                )
                air_collision[batch_index, slot] = uses_air_collision_plane(entity)
                in_transit_tensor[batch_index, slot] = is_in_transit(entity)
                mega_knight_airborne[batch_index, slot] = bool(
                    getattr(entity, "_mk_leap_phase", None) == "airborne"
                )
                stunned[batch_index, slot] = bool(entity.is_stunned())
                forced_movement[batch_index, slot] = bool(entity.forced_movement_active)
                special_movement[batch_index, slot] = bool(
                    getattr(entity, "_special_move_active", False)
                )
                death_spawn_travel[batch_index, slot] = bool(
                    entity._death_spawn_travel_ticks_remaining > 0
                )
                knockback_active[batch_index, slot] = bool(
                    entity._knockback_target is not None
                )
                kamikaze_primed[batch_index, slot] = bool(
                    getattr(entity, "kamikaze_primed", False)
                )
                mechanic_free[batch_index, slot] = not bool(entity.mechanics)
                charge_component[batch_index, slot] = bool(
                    getattr(stats, "charge_range", None)
                )
                movement_cycle[batch_index, slot] = bool(
                    float(getattr(stats, "stop_movement_after_ms", 0) or 0) > 0
                    and float(getattr(stats, "wait_ms", 0) or 0) > 0
                )
                avoidance_prepass_required[batch_index, slot] = bool(
                    avoidance_prepass_by_id[batch_index][entity.id]
                )
                facing_units[batch_index, slot] = torch.tensor(
                    (entity._facing_x_units, entity._facing_y_units),
                    dtype=torch.int64,
                    device=torch_device,
                )
                avoidance[batch_index, slot] = int(
                    getattr(entity, "_native_avoidance", 0)
                )
                accumulated_vector_units[batch_index, slot] = torch.tensor(
                    (entity._movement_vector_x_units, entity._movement_vector_y_units),
                    dtype=torch.int64,
                    device=torch_device,
                )
                accumulated_vector_count[batch_index, slot] = int(
                    entity._movement_vector_count
                )
                accumulated_vector_bypasses_cap[batch_index, slot] = bool(
                    entity._movement_vector_bypasses_cap
                )
                pending_vector_units[batch_index, slot] = torch.tensor(
                    (
                        tiles_to_logic_units(entity._pending_movement_x),
                        tiles_to_logic_units(entity._pending_movement_y),
                    ),
                    dtype=torch.int64,
                    device=torch_device,
                )
                pending_vector_consumed[batch_index, slot] = bool(
                    entity._pending_movement_consumed
                )
                natural_movement_active[batch_index, slot] = bool(
                    getattr(entity, "_native_natural_movement_active", False)
                )
                movement_phase_elapsed_ms[batch_index, slot] = int(
                    getattr(entity, "movement_phase_elapsed_ms", 0)
                )
                native_charge_progress[batch_index, slot] = int(
                    getattr(entity, "_native_charge_progress", 0)
                )
                distance_traveled_bits[batch_index, slot] = _float_to_int64_bits(
                    float(getattr(entity, "distance_traveled", 0.0))
                )
                river_jump_active[batch_index, slot] = bool(
                    getattr(entity, "_river_jump_active", False)
                )
                river_jump_blocked[batch_index, slot] = bool(
                    getattr(entity, "_river_jump_blocked", False)
                )
                river_origin = _optional_position_units(entity, "_river_jump_origin")
                if river_origin is not None:
                    river_origin_units[batch_index, slot] = torch.tensor(
                        river_origin, dtype=torch.int64, device=torch_device
                    )
                    river_origin_valid[batch_index, slot] = True
                river_target = _optional_position_units(entity, "_river_jump_target")
                if river_target is not None:
                    river_target_units[batch_index, slot] = torch.tensor(
                        river_target, dtype=torch.int64, device=torch_device
                    )
                    river_target_valid[batch_index, slot] = True
                river_elapsed_bits[batch_index, slot] = _float_to_int64_bits(
                    float(getattr(entity, "_river_jump_elapsed", 0.0))
                )
                river_duration_bits[batch_index, slot] = _float_to_int64_bits(
                    float(getattr(entity, "_river_jump_duration", 0.0))
                )
                special_move_consumed_tick[batch_index, slot] = bool(
                    getattr(entity, "_special_move_consumed_tick", False)
                )
                stun_interrupt_deferred[batch_index, slot] = bool(
                    entity._stun_interrupt_deferred_until_landing
                )

        ordinary_unsupported = zeros(batch_size, entity_capacity)
        river_unsupported = zeros(batch_size, entity_capacity)

        def add_reason(
            destination: torch.Tensor,
            mask: torch.Tensor,
            reason: MovementUnsupported,
        ) -> None:
            destination.bitwise_or_(mask.to(torch.int64) * int(reason))

        active = slot_present & entity_active
        for destination in (ordinary_unsupported, river_unsupported):
            add_reason(destination, ~active, MovementUnsupported.INACTIVE)
            add_reason(destination, ~is_troop, MovementUnsupported.NOT_TROOP)
            add_reason(destination, ~mechanic_free, MovementUnsupported.MECHANIC_HOOK)

        # Deployment state is compiled separately because it is a float scalar,
        # not a movement-kernel input after the support decision.
        deployed = zeros(batch_size, entity_capacity, dtype=torch.bool)
        for batch_index, clone in enumerate(clones):
            for slot, entity in enumerate(
                sorted(clone.entities.values(), key=lambda item: item.id)
            ):
                deployed[batch_index, slot] = entity.deploy_delay_remaining <= 1e-9
        add_reason(ordinary_unsupported, ~deployed, MovementUnsupported.NOT_DEPLOYED)
        add_reason(river_unsupported, ~deployed, MovementUnsupported.NOT_DEPLOYED)

        add_reason(ordinary_unsupported, target_slot < 0, MovementUnsupported.NO_TARGET)
        add_reason(
            ordinary_unsupported, ~target_valid, MovementUnsupported.INVALID_TARGET
        )
        add_reason(
            ordinary_unsupported, ~waypoint_valid, MovementUnsupported.NO_WAYPOINT
        )
        add_reason(ordinary_unsupported, stunned, MovementUnsupported.STUNNED)
        add_reason(
            ordinary_unsupported, forced_movement, MovementUnsupported.FORCED_MOVEMENT
        )
        add_reason(
            ordinary_unsupported, special_movement, MovementUnsupported.SPECIAL_MOVEMENT
        )
        add_reason(
            ordinary_unsupported,
            special_move_consumed_tick,
            MovementUnsupported.SPECIAL_MOVEMENT,
        )
        add_reason(
            ordinary_unsupported,
            death_spawn_travel,
            MovementUnsupported.DEATH_SPAWN_TRAVEL,
        )
        add_reason(
            ordinary_unsupported, knockback_active, MovementUnsupported.KNOCKBACK
        )
        add_reason(ordinary_unsupported, kamikaze_primed, MovementUnsupported.KAMIKAZE)
        add_reason(
            ordinary_unsupported,
            river_jump_active,
            MovementUnsupported.RIVER_JUMP_ACTIVE,
        )

        unknown_cache = zeros(batch_size, entity_capacity, dtype=torch.bool)
        for batch_index, known in enumerate(cache_is_known):
            for entity_id_value, is_known in known.items():
                if not is_known:
                    unknown_cache[
                        batch_index,
                        int((entity_id[batch_index] == entity_id_value).nonzero()[0]),
                    ] = True
        add_reason(
            ordinary_unsupported,
            unknown_cache,
            MovementUnsupported.UNKNOWN_ROUTE_CACHE,
        )
        add_reason(
            ordinary_unsupported,
            charge_component,
            MovementUnsupported.CHARGE_COMPONENT,
        )
        add_reason(
            ordinary_unsupported,
            movement_cycle,
            MovementUnsupported.MOVEMENT_CYCLE,
        )
        add_reason(
            ordinary_unsupported,
            avoidance_prepass_required,
            MovementUnsupported.AVOIDANCE_PREPASS,
        )

        add_reason(
            river_unsupported,
            ~river_jump_active,
            MovementUnsupported.RIVER_JUMP_INACTIVE,
        )
        add_reason(
            river_unsupported,
            ~(river_origin_valid & river_target_valid),
            MovementUnsupported.MISSING_RIVER_STATE,
        )
        add_reason(
            river_unsupported,
            jump_speed_units <= 0,
            MovementUnsupported.INVALID_JUMP_SPEED,
        )
        add_reason(
            river_unsupported,
            charge_component,
            MovementUnsupported.CHARGE_COMPONENT,
        )
        add_reason(
            river_unsupported,
            death_spawn_travel,
            MovementUnsupported.DEATH_SPAWN_TRAVEL,
        )
        add_reason(river_unsupported, knockback_active, MovementUnsupported.KNOCKBACK)

        base_ordinary = natural_movement_support_mask(
            active=active,
            target_valid=target_valid,
            waypoint_valid=waypoint_valid,
            deployed=deployed,
            stunned=stunned,
            forced_movement=forced_movement,
            special_movement=special_movement,
            death_spawn_travel=death_spawn_travel,
            river_jump_active=river_jump_active,
        )
        ordinary_supported = base_ordinary & (ordinary_unsupported == 0)
        river_jump_supported = river_unsupported == 0

        return cls(
            device=torch_device,
            entity_id=entity_id,
            slot_present=slot_present,
            entity_active=entity_active,
            entity_kind=entity_kind,
            player_id=player_id,
            position_units=position_units,
            target_id=target_id,
            target_slot=target_slot,
            target_position_units=target_position_units,
            target_valid=target_valid,
            waypoint_units=waypoint_units,
            waypoint_valid=waypoint_valid,
            route_cells=route_cells,
            route_count=route_count,
            route_cache_kind=route_cache_kind,
            route_cache_goal=route_cache_goal,
            route_cache_lane=route_cache_lane,
            route_cache_jump=route_cache_jump,
            route_cache_backwards=route_cache_backwards,
            ground_path_backwards=ground_path_backwards,
            is_troop=is_troop,
            is_air=is_air,
            is_hover=is_hover,
            lane_id=lane_id,
            jump_height=jump_height,
            jump_speed_units=jump_speed_units,
            effective_speed_units=effective_speed_units,
            collision_radius_units=collision_radius_units,
            mass_milliunits=mass_milliunits,
            air_collision=air_collision,
            in_transit=in_transit_tensor,
            mega_knight_airborne=mega_knight_airborne,
            stunned=stunned,
            forced_movement=forced_movement,
            special_movement=special_movement,
            death_spawn_travel=death_spawn_travel,
            knockback_active=knockback_active,
            kamikaze_primed=kamikaze_primed,
            mechanic_free=mechanic_free,
            charge_component=charge_component,
            movement_cycle=movement_cycle,
            avoidance_prepass_required=avoidance_prepass_required,
            facing_units=facing_units,
            avoidance=avoidance,
            accumulated_vector_units=accumulated_vector_units,
            accumulated_vector_count=accumulated_vector_count,
            accumulated_vector_bypasses_cap=accumulated_vector_bypasses_cap,
            pending_vector_units=pending_vector_units,
            pending_vector_consumed=pending_vector_consumed,
            natural_movement_active=natural_movement_active,
            movement_phase_elapsed_ms=movement_phase_elapsed_ms,
            native_charge_progress=native_charge_progress,
            distance_traveled_bits=distance_traveled_bits,
            river_jump_active=river_jump_active,
            river_jump_blocked=river_jump_blocked,
            river_origin_units=river_origin_units,
            river_origin_valid=river_origin_valid,
            river_target_units=river_target_units,
            river_target_valid=river_target_valid,
            river_elapsed_bits=river_elapsed_bits,
            river_duration_bits=river_duration_bits,
            special_move_consumed_tick=special_move_consumed_tick,
            stun_interrupt_deferred=stun_interrupt_deferred,
            ordinary_unsupported=ordinary_unsupported,
            river_unsupported=river_unsupported,
            ordinary_supported=ordinary_supported,
            river_jump_supported=river_jump_supported,
        )

    def apply_natural_result(self, result: NaturalMovementResult) -> None:
        """Commit an ordinary kernel result and its retained-route pop."""

        if result.position_units.shape != self.position_units.shape:
            raise ValueError("natural movement result shape does not match adapter")
        support = result.supported & self.ordinary_supported
        previous = self.position_units.clone()
        delta = self.waypoint_units - previous
        nonzero_facing = torch.any(delta != 0, dim=-1) & support
        self.facing_units.copy_(
            torch.where(nonzero_facing.unsqueeze(-1), delta, self.facing_units)
        )
        self.position_units.copy_(
            torch.where(support.unsqueeze(-1), result.position_units, previous)
        )
        if self.route_capacity:
            head_center = self.route_cells[:, :, 0] * 500 + 250
            head_matches = (
                support
                & (self.route_count > 0)
                & torch.all(head_center == self.waypoint_units, dim=-1)
            )
            pop = advance_route_node_mask(
                self.position_units,
                previous,
                self.waypoint_units,
                route_head_matches=head_matches,
            )
            indices = torch.arange(self.route_capacity, device=self.device)
            gather_indices = torch.clamp(
                indices.view(1, 1, -1) + pop.unsqueeze(-1).to(torch.int64),
                max=self.route_capacity - 1,
            )
            shifted = torch.gather(
                self.route_cells,
                2,
                gather_indices.unsqueeze(-1).expand(-1, -1, -1, 2),
            )
            self.route_cells.copy_(
                torch.where(pop.unsqueeze(-1).unsqueeze(-1), shifted, self.route_cells)
            )
            self.route_count.sub_(pop.to(torch.int64)).clamp_(min=0)
            new_head = self.route_cells[:, :, 0] * 500 + 250
            next_waypoint = torch.where(
                (self.route_count > 0).unsqueeze(-1),
                new_head,
                self.target_position_units,
            )
            self.waypoint_units.copy_(
                torch.where(pop.unsqueeze(-1), next_waypoint, self.waypoint_units)
            )
        self.pending_vector_units.copy_(
            torch.where(
                support.unsqueeze(-1),
                torch.zeros_like(self.pending_vector_units),
                self.pending_vector_units,
            )
        )
        self.pending_vector_consumed |= support
        self.natural_movement_active |= support

    def apply_river_result(self, result: RiverJumpResult, *, dt: float = 0.05) -> None:
        """Commit an active river-jump kernel result and state-six flags."""

        if result.position_units.shape != self.position_units.shape:
            raise ValueError("river movement result shape does not match adapter")
        support = result.supported & self.river_jump_supported
        previous = self.position_units.clone()
        delta = self.river_target_units - previous
        nonzero_facing = torch.any(delta != 0, dim=-1) & support
        self.facing_units.copy_(
            torch.where(nonzero_facing.unsqueeze(-1), delta, self.facing_units)
        )
        self.position_units.copy_(
            torch.where(support.unsqueeze(-1), result.position_units, previous)
        )
        # MPS has no float64 arithmetic. Reinterpret the complete hidden-clock
        # batch on CPU, add once vectorially with Python's binary64 kind, then
        # return only the integer bit pattern to the production device.
        elapsed_bits_cpu = self.river_elapsed_bits.detach().to("cpu").contiguous()
        elapsed_float_cpu = elapsed_bits_cpu.view(torch.float64)
        advanced_bits = (elapsed_float_cpu + float(dt)).view(torch.int64)
        self.river_elapsed_bits.copy_(
            torch.where(
                support,
                advanced_bits.to(self.device),
                self.river_elapsed_bits,
            )
        )
        self.river_jump_active.copy_(
            torch.where(support, result.active, self.river_jump_active)
        )
        finished = support & result.finished
        self.special_movement.copy_(
            torch.where(
                finished, torch.zeros_like(self.special_movement), self.special_movement
            )
        )
        self.special_move_consumed_tick |= finished
        self.river_jump_blocked.copy_(
            torch.where(
                finished,
                torch.zeros_like(self.river_jump_blocked),
                self.river_jump_blocked,
            )
        )

    def sync_to_battles(self, battles: Sequence[BattleState]) -> None:
        """Restore positions and all represented hidden movement state by ID."""

        if len(battles) != self.batch_size:
            raise ValueError("battle count does not match movement batch")
        for batch_index, battle in enumerate(battles):
            expected_ids = [
                int(value)
                for value in self.entity_id[batch_index][
                    self.slot_present[batch_index]
                ].tolist()
            ]
            if expected_ids != sorted(battle.entities):
                raise ValueError(
                    "battle entity identity/order changed after movement compile"
                )
            for slot, entity_id in enumerate(expected_ids):
                entity = battle.entities[entity_id]
                x_units, y_units = (
                    int(value)
                    for value in self.position_units[batch_index, slot].tolist()
                )
                entity.position = Position(
                    logic_units_to_tiles(x_units), logic_units_to_tiles(y_units)
                )
                movement_target_id = int(self.target_id[batch_index, slot].item())
                if isinstance(entity, Troop):
                    entity._movement_target_id = (
                        None if movement_target_id < 0 else movement_target_id
                    )
                entity._facing_x_units = int(
                    self.facing_units[batch_index, slot, 0].item()
                )
                entity._facing_y_units = int(
                    self.facing_units[batch_index, slot, 1].item()
                )
                entity._movement_vector_x_units = int(
                    self.accumulated_vector_units[batch_index, slot, 0].item()
                )
                entity._movement_vector_y_units = int(
                    self.accumulated_vector_units[batch_index, slot, 1].item()
                )
                entity._movement_vector_count = int(
                    self.accumulated_vector_count[batch_index, slot].item()
                )
                entity._movement_vector_bypasses_cap = bool(
                    self.accumulated_vector_bypasses_cap[batch_index, slot].item()
                )
                entity._pending_movement_x = logic_units_to_tiles(
                    int(self.pending_vector_units[batch_index, slot, 0].item())
                )
                entity._pending_movement_y = logic_units_to_tiles(
                    int(self.pending_vector_units[batch_index, slot, 1].item())
                )
                entity._pending_movement_consumed = bool(
                    self.pending_vector_consumed[batch_index, slot].item()
                )
                entity._ground_path_backwards = bool(
                    self.ground_path_backwards[batch_index, slot].item()
                )
                count = int(self.route_count[batch_index, slot].item())
                setattr(
                    entity,
                    "_native_ground_route_cells",
                    [
                        (int(cell[0]), int(cell[1]))
                        for cell in self.route_cells[batch_index, slot, :count].tolist()
                    ],
                )
                cache_kind = int(self.route_cache_kind[batch_index, slot].item())
                goal = tuple(
                    int(value)
                    for value in self.route_cache_goal[batch_index, slot].tolist()
                )
                if cache_kind == _CACHE_NONE:
                    setattr(entity, "_ground_path_cache_key", None)
                elif cache_kind == _CACHE_SINGLE:
                    setattr(entity, "_ground_path_cache_key", ("single", goal))
                elif cache_kind == _CACHE_GROUND:
                    setattr(
                        entity,
                        "_ground_path_cache_key",
                        (
                            goal,
                            int(self.route_cache_lane[batch_index, slot].item()),
                            bool(self.route_cache_jump[batch_index, slot].item()),
                        ),
                    )
                else:
                    raise ValueError("unknown tensor route-cache kind")
                setattr(
                    entity,
                    "_ground_path_cache_backwards",
                    bool(self.route_cache_backwards[batch_index, slot].item()),
                )
                if isinstance(entity, Troop):
                    entity._native_avoidance = int(
                        self.avoidance[batch_index, slot].item()
                    )
                    entity._native_natural_movement_active = bool(
                        self.natural_movement_active[batch_index, slot].item()
                    )
                    entity.movement_phase_elapsed_ms = int(
                        self.movement_phase_elapsed_ms[batch_index, slot].item()
                    )
                    entity._native_charge_progress = int(
                        self.native_charge_progress[batch_index, slot].item()
                    )
                    entity.distance_traveled = _int64_bits_to_float(
                        int(self.distance_traveled_bits[batch_index, slot].item())
                    )
                    entity._river_jump_active = bool(
                        self.river_jump_active[batch_index, slot].item()
                    )
                    entity._river_jump_blocked = bool(
                        self.river_jump_blocked[batch_index, slot].item()
                    )
                    setattr(
                        entity,
                        "_river_jump_origin",
                        (
                            Position(
                                logic_units_to_tiles(
                                    int(
                                        self.river_origin_units[
                                            batch_index, slot, 0
                                        ].item()
                                    )
                                ),
                                logic_units_to_tiles(
                                    int(
                                        self.river_origin_units[
                                            batch_index, slot, 1
                                        ].item()
                                    )
                                ),
                            )
                            if bool(self.river_origin_valid[batch_index, slot].item())
                            else None
                        ),
                    )
                    setattr(
                        entity,
                        "_river_jump_target",
                        (
                            Position(
                                logic_units_to_tiles(
                                    int(
                                        self.river_target_units[
                                            batch_index, slot, 0
                                        ].item()
                                    )
                                ),
                                logic_units_to_tiles(
                                    int(
                                        self.river_target_units[
                                            batch_index, slot, 1
                                        ].item()
                                    )
                                ),
                            )
                            if bool(self.river_target_valid[batch_index, slot].item())
                            else None
                        ),
                    )
                    entity._river_jump_elapsed = _int64_bits_to_float(
                        int(self.river_elapsed_bits[batch_index, slot].item())
                    )
                    entity._river_jump_duration = _int64_bits_to_float(
                        int(self.river_duration_bits[batch_index, slot].item())
                    )
                    entity._special_move_active = bool(
                        self.special_movement[batch_index, slot].item()
                    )
                    entity._special_move_consumed_tick = bool(
                        self.special_move_consumed_tick[batch_index, slot].item()
                    )
                    entity._stun_interrupt_deferred_until_landing = bool(
                        self.stun_interrupt_deferred[batch_index, slot].item()
                    )
                if battle.fast_path:
                    battle.sync_fast_target_entity(entity)
