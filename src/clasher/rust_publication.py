from __future__ import annotations

import copy
import hashlib
import json
import random
import struct
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, cast

import numpy as np

from .arena import Position
from .battle import PendingSpellCast
from .differential import _normalize, first_snapshot_difference
from .entities import (
    AreaEffect,
    Building,
    Projectile,
    RollingProjectile,
    SpawnProjectile,
    Troop,
)
from .mechanics.shared.death_area import DeathAreaEffect
from .mechanics.shared.death_effects import DeathDamage, DeathSpawn
from .rust_core import (
    _PREPARED_PUBLICATION_BEST_CONSUMER,
    RESIDENT_CARD_CATALOG_SCHEMA_VERSION,
    ResidentRustBattle,
)
from .rust_differential import (
    RESIDENT_SEMANTIC_SCHEMA_VERSION,
    python_resident_semantic_snapshot,
    rust_resident_semantic_snapshot,  # noqa: F401 - legacy-call tripwire in tests
)


class ResidentPublicationError(RuntimeError):
    """The resident state cannot be published without changing Python identity."""


def _catalog_birth_type(entity_kind: int) -> tuple[type[Any], str, str]:
    if entity_kind == 0:
        return Troop, "clasher.entities.Troop", "troop"
    if entity_kind == 1:
        return Building, "clasher.entities.Building", "building"
    raise ResidentPublicationError(
        f"resident catalog birth has unsupported entity kind {entity_kind}"
    )


@dataclass(frozen=True)
class _TypedPublication:
    binding: dict[str, Any]
    snapshot: dict[str, Any]
    publication_rows: list[dict[str, Any]]
    battle_presence: dict[str, bool]
    player_rows: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class _DirectEntityPublication:
    """One validated native entity row retained in its typed PyO3 shape."""

    raw: dict[str, Any]
    entity_id: int
    active: bool
    encounter_index: int
    presence_mask: int


@dataclass(frozen=True, slots=True)
class _DirectPublicationPlan:
    """Private production publication plan with no diagnostic projections."""

    binding: dict[str, Any]
    battle: dict[str, Any]
    players: tuple[dict[str, Any], dict[str, Any]]
    towers: tuple[dict[str, Any], ...]
    entities: tuple[_DirectEntityPublication, ...]
    active_entity_ids: tuple[int, ...]
    rng: dict[str, Any]
    pending_spells: dict[str, Any]
    projectile_groups: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class _DirectDeltaEntityPublication:
    raw: dict[str, Any]
    entity_id: int
    dirty_mask: int
    presence_mask: int
    full: _DirectEntityPublication | None


@dataclass(frozen=True, slots=True)
class _DirectDeltaPublicationPlan:
    binding: dict[str, Any]
    dirty_mask: int
    battle: dict[str, Any] | None
    idle_eligible: bool | None
    players: tuple[dict[str, Any], dict[str, Any]] | None
    towers: tuple[dict[str, Any], ...] | None
    entities: tuple[_DirectDeltaEntityPublication, ...]
    all_entity_ids: tuple[int, ...]
    active_entity_ids: tuple[int, ...]
    next_entity_id: int
    rng: dict[str, Any] | None
    pending_spells: dict[str, Any] | None
    projectile_groups: tuple[dict[str, Any], ...] | None
    battle_presence_mask: int
    cache_dirty: bool
    topology_dirty: bool


_DELTA_BATTLE = 1 << 0
_DELTA_PLAYERS = 1 << 1
_DELTA_TOWERS = 1 << 2
_DELTA_RNG = 1 << 3
_DELTA_PENDING = 1 << 4
_DELTA_GROUPS = 1 << 5
_DELTA_ROOT_MASK = (1 << 6) - 1

_ENTITY_DELTA_PRESENCE = 1 << 0
_ENTITY_DELTA_BASE = 1 << 1
_ENTITY_DELTA_SHIELDS = 1 << 2
_ENTITY_DELTA_MODIFIER = 1 << 3
_ENTITY_DELTA_MOVEMENT = 1 << 4
_ENTITY_DELTA_COMBAT = 1 << 5
_ENTITY_DELTA_BUILDING_LIFETIME = 1 << 6
_ENTITY_DELTA_BUILDING_IMPACT = 1 << 7
_ENTITY_DELTA_POINT = 1 << 8
_ENTITY_DELTA_AREA = 1 << 9
_ENTITY_DELTA_ROLLING = 1 << 10
_ENTITY_DELTA_FULL = 1 << 11
_ENTITY_DELTA_MASK = (1 << 12) - 1


_ENTITY_SPARSE_ATTRIBUTE_NAMES = (
    "_spawn_hook_pending",
    "_spawn_hook_fired",
    "_ground_path_cache_key",
    "_native_ground_route_cells",
    "_ground_path_cache_backwards",
    "movement_phase_elapsed_ms",
    "_native_avoidance",
    "_native_natural_movement_active",
    "_death_spawn_travel_target",
    "_knockback_target",
    "_river_jump_active",
    "_river_jump_origin",
    "_river_jump_target",
    "_river_jump_elapsed",
    "_river_jump_duration",
    "_river_jump_blocked",
    "_special_move_active",
    "_special_move_consumed_tick",
    "_last_combat_target_id",
    "_has_attacked_once",
    "_movement_target_id",
    "initial_position",
    "_permanent_homing_disabled_by_temporary",
    "_temporary_homing_remaining_ms",
    "_temporary_homing_target",
    "_shield_break_count",
)
_ENTITY_SPARSE_ATTRIBUTES = frozenset(_ENTITY_SPARSE_ATTRIBUTE_NAMES)

_BATTLE_SPARSE_ATTRIBUTE_NAMES = (
    "_sudden_death_crowns",
    "_next_spell_cast_sequence",
    "_defer_projectile_impacts",
    "_projectile_lethal_reservations",
    "_coalesce_alive_building_refreshes",
    "_win_conditions_dirty",
    "_building_placement_blocked_masks",
    "_troop_placement_blocked_masks",
)
_BATTLE_SPARSE_ATTRIBUTES = frozenset(_BATTLE_SPARSE_ATTRIBUTE_NAMES)

_DIRECT_KEYS: dict[str, frozenset[str]] = {
    "delta_root": frozenset(
        {
            "version",
            "binding",
            "all_entity_ids",
            "active_entity_ids",
            "next_entity_id",
            "dirty_mask",
            "battle",
            "idle_eligible",
            "players",
            "towers",
            "entities",
            "rng",
            "pending_spells",
            "projectile_groups",
        }
    ),
    "delta_entity": frozenset(
        {
            "id",
            "dirty_mask",
            "sparse_attribute_presence",
            "base",
            "shields",
            "shield_break_count",
            "modifier_state",
            "modifier_present",
            "movement_state",
            "movement_present",
            "locked_combat_state",
            "locked_combat_present",
            "building_lifetime_state",
            "building_lifetime_present",
            "building_impact_state",
            "building_impact_present",
            "point_projectile_state",
            "point_projectile_present",
            "rolling_projectile_state",
            "rolling_projectile_present",
            "area_effect_state",
            "area_effect_present",
            "full",
        }
    ),
    "delta_base": frozenset(
        {
            "active",
            "encounter_index",
            "position_x",
            "position_y",
            "hitpoints",
            "max_hitpoints",
            "damage",
            "is_alive",
            "target_id",
            "deploy_delay_remaining",
            "placement_delay_total",
            "placement_pending",
            "spawn_hook_pending",
            "spawn_hook_fired",
            "freeze_expiry_time",
            "death_spawn_target_immunity_elapsed_ms",
            "pending_projectile_max_duration_ms",
            "status_nova_jump",
        }
    ),
    "root": frozenset(
        {
            "version",
            "binding",
            "battle",
            "players",
            "towers",
            "entities",
            "rng",
            "pending_spells",
            "projectile_groups",
        }
    ),
    "binding": frozenset(
        {
            "semantic_schema_version",
            "lineage_id",
            "prior_node_id",
            "prior_epoch",
            "candidate_node_id",
            "candidate_epoch",
            "parent_node_id",
            "parent_epoch",
            "prior_next_entity_id",
            "prior_entity_ids",
            "checkpoint_schema_version",
            "checkpoint_generation",
            "catalog_schema_version",
            "catalog_fingerprint",
            "catalog_source_fingerprint",
        }
    ),
    "battle": frozenset(
        {
            "sparse_attribute_presence",
            "tick",
            "time",
            "dt",
            "double_elixir",
            "triple_elixir",
            "overtime",
            "game_over",
            "sudden_death",
            "sudden_death_crowns",
            "winner",
            "win_conditions_dirty",
            "next_entity_id",
        }
    ),
    "player": frozenset(
        {
            "cycle_queue",
            "elixir",
            "hand",
            "king_tower_hp",
            "left_tower_hp",
            "max_elixir",
            "next_card_refill_cooldown_ms",
            "player_id",
            "right_tower_hp",
        }
    ),
    "tower": frozenset(
        {
            "active",
            "hp",
            "hp_milli",
            "id",
            "is_active",
            "is_alive",
            "last_attack_time",
            "player_id",
            "slot",
        }
    ),
    "entity": frozenset(
        {
            "sparse_attribute_presence",
            "active",
            "encounter_index",
            "id",
            "player_id",
            "entity_kind",
            "python_type",
            "card_name",
            "position_x",
            "position_y",
            "hitpoints",
            "max_hitpoints",
            "damage",
            "is_alive",
            "target_id",
            "deploy_delay_remaining",
            "placement_delay_total",
            "placement_pending",
            "spawn_hook_pending",
            "spawn_hook_fired",
            "freeze_expiry_time",
            "death_spawn_target_immunity_elapsed_ms",
            "pending_projectile_max_duration_ms",
            "spawn_angle_shift",
            "mechanics",
            "shields",
            "shield_break_count",
            "death_opcodes",
            "modifier_state",
            "movement_state",
            "locked_combat_state",
            "building_lifetime_state",
            "building_impact_state",
            "point_projectile_state",
            "rolling_projectile_state",
            "area_effect_state",
            "character_birth",
            "status_nova_jump",
        }
    ),
    "modifier": frozenset(
        {
            "attack_speed_buff_multiplier",
            "attack_speed_debuff_multiplier",
            "haste_effects",
            "haste_timer",
            "movement_mode_multiplier",
            "movement_speed_buff_multiplier",
            "original_speed",
            "slow_effects",
            "slow_multiplier",
            "slow_timer",
            "spawn_speed_buff_multiplier",
            "spawn_speed_debuff_multiplier",
            "speed",
            "stun_timer",
        }
    ),
    "modifier_effect": frozenset({"remaining", "movement", "attack", "spawn"}),
    "status_nova_jump": frozenset(
        {
            "freeze_radius_units",
            "freeze_duration_ms",
            "hop_duration_ms",
            "jump_speed_units_per_tick",
            "affects_hidden",
            "hits_air",
            "hits_ground",
            "detonated",
            "jump_timer_ms",
            "jump_target_id",
            "jump_destination",
            "jump_origin",
        }
    ),
    "shield": frozenset({"current", "maximum"}),
    "death_opcode": frozenset({"kind", "damage", "spawn", "area"}),
    "death_damage": frozenset(
        {
            "base_damage",
            "hits_air",
            "hits_ground",
            "knockback_distance",
            "knockback_units",
            "radius_tiles",
            "radius_units",
            "scaled_damage",
        }
    ),
    "death_spawn": frozenset(
        {
            "count",
            "deploy_time_ms",
            "min_radius_tiles",
            "radial_pushback",
            "radius_tiles",
            "spawn_const_priority",
            "unit_data_fingerprint",
            "unit_name",
        }
    ),
    "area_spec": frozenset(
        {
            "affects_hidden",
            "area_name",
            "attack_multiplier",
            "cap_buff_time_to_effect",
            "duration",
            "effect_tick_interval",
            "hits_air",
            "hits_ground",
            "movement_multiplier",
            "radius_tiles",
            "radius_units",
            "refresh_duration",
            "spawn_multiplier",
        }
    ),
    "movement": frozenset(
        {
            "building_pathing_radius",
            "charge_range_present",
            "collision_radius",
            "death_spawn_travel_target",
            "death_spawn_travel_ticks",
            "forced_movement_active",
            "is_hover",
            "jump_height_present",
            "jump_speed",
            "kamikaze_primed",
            "knockback_immune",
            "knockback_interrupts_combat",
            "knockback_target",
            "knockback_velocity_work",
            "movement_phase_elapsed_ms",
            "native_avoidance",
            "native_lane_id",
            "native_natural_movement_active",
            "pending_consumed",
            "pending_x",
            "pending_y",
            "river_jump_active",
            "river_jump_blocked",
            "river_jump_duration",
            "river_jump_elapsed",
            "river_jump_origin",
            "river_jump_target",
            "route_backwards",
            "route_cache_kind",
            "route_cache_supported",
            "route_cells",
            "route_goal",
            "route_jump_height",
            "route_lane_id",
            "serialized_speed",
            "special_move_active",
            "special_move_consumed_tick",
            "stop_movement_after_ms",
            "stun_interrupt_deferred_until_landing",
            "unit_mass",
            "vector_bypasses_cap",
            "vector_count",
            "vector_x_units",
            "vector_y_units",
            "wait_ms",
        }
    ),
    "combat": frozenset(
        {
            "allow_area_damage_when_invisible",
            "attack_cooldown",
            "attack_mode_multiplier",
            "attack_preload_blocked",
            "attack_speed_buff_multiplier",
            "attack_speed_debuff_multiplier",
            "attack_windup_active",
            "can_attack_air",
            "can_attack_ground",
            "collision_radius",
            "constructor_range",
            "damage",
            "direct_area",
            "facing_x_units",
            "facing_y_units",
            "first_hit_ms",
            "ground_path_backwards",
            "has_attacked_once",
            "hidden_building",
            "hit_speed_ms",
            "initial_position",
            "is_air_unit",
            "is_airborne_for_projectile",
            "last_attack_time",
            "last_combat_target_id",
            "movement_target_id",
            "native_building_target",
            "native_target_distance_discount_sq_units",
            "point_weapon",
            "range",
            "retarget_ms",
            "sight_clip",
            "sight_clip_side",
            "sight_range",
            "stealth_until_ms",
            "stun_timer",
            "targets_only_buildings",
        }
    ),
    "direct_area": frozenset({"radius_units", "self_centered"}),
    "point_weapon": frozenset(
        {
            "travel_speed",
            "tracks_target",
            "start_radius",
            "y_offset",
            "splash_radius",
            "hit_planes",
            "crown_tower_damage_multiplier",
            "stun_duration",
            "slow_duration",
            "slow_multiplier",
        }
    ),
    "building_lifetime": frozenset(
        {"lifetime_ms", "lifetime_elapsed", "decay_work", "tick_carry_ms"}
    ),
    "building_impact": frozenset(
        {
            "activation_delay_remaining",
            "activation_delay_seconds",
            "activation_first_hit_delay_remaining",
            "activation_first_hit_delay_seconds",
            "allow_area_damage_when_invisible",
            "collision_radius",
            "crown_slot",
            "is_king_tower",
            "requires_activation",
            "stealth_until_ms",
            "tower_active",
        }
    ),
    "point": frozenset(
        {
            "constructor_range",
            "constructor_sight_range",
            "crown_tower_damage",
            "crown_tower_damage_multiplier",
            "damage_group_hit_entity_ids",
            "damage_group_id",
            "damage_wave_interval",
            "hits_air",
            "hits_ground",
            "homing_min_distance",
            "homing_time_ms",
            "ignore_buildings",
            "knockback_distance",
            "knockback_ignores_mass",
            "launch_delay",
            "launch_x",
            "launch_y",
            "permanent_homing_disabled_by_temporary",
            "primary_target_id",
            "slow_duration",
            "slow_multiplier",
            "source_entity_id",
            "source_kind",
            "splash_radius",
            "start_collision_resolved",
            "stun_duration",
            "target_x",
            "target_y",
            "temporary_homing_remaining_ms",
            "temporary_homing_target_id",
            "tracks_target",
            "travel_speed",
            "unsupported",
            "spawn_projectile_state",
        }
    ),
    "spawn_projectile_state": frozenset(
        {
            "activation_delay",
            "spawn_count",
            "spawn_character",
            "spawn_data_fingerprint",
            "spawn_radius",
            "spawn_deploy_delay",
            "spawn_const_priority",
            "time_alive",
        }
    ),
    "rolling": frozenset(
        {
            "crown_tower_damage",
            "crown_tower_damage_multiplier",
            "distance_traveled",
            "has_spawned_character",
            "hit_entity_ids",
            "knockback_distance",
            "knockback_ignores_mass",
            "projectile_range",
            "radius_y",
            "rolling_radius",
            "source_kind",
            "spawn_character",
            "spawn_character_data_fingerprint",
            "spawn_deploy_delay_override",
            "spawn_delay",
            "time_alive",
            "travel_speed",
        }
    ),
    "area": frozenset(
        {
            "birth_source_entity_id",
            "effect_snapshot_applied",
            "spec",
            "supported",
            "time_alive",
        }
    ),
    "character_birth": frozenset(
        {
            "effective_name",
            "group_id",
            "kind",
            "lookup_name",
            "member_count",
            "opcode_index",
            "ordinal",
            "source_entity_id",
            "template_fingerprint",
            "unit_data_fingerprint",
        }
    ),
    "rng": frozenset({"version", "state", "index", "gauss_next"}),
    "pending": frozenset({"next_sequence", "casts"}),
    "pending_cast": frozenset(
        {
            "execute_at",
            "sequence",
            "spell_name",
            "player_id",
            "position_x",
            "position_y",
        }
    ),
    "projectile_group": frozenset({"id", "hit_entity_ids"}),
}


class _UndoJournal:
    def __init__(self) -> None:
        self._seen: set[tuple[str, int]] = set()
        self._entries: list[tuple[str, Any, Any]] = []

    def _record(self, kind: str, owner: Any, state: Any) -> bool:
        key = (kind, id(owner))
        if key in self._seen:
            return False
        self._seen.add(key)
        self._entries.append((kind, owner, state))
        return True

    def watch_attrs(self, owner: Any) -> None:
        if not hasattr(owner, "__dict__"):
            return
        self._record("attrs", owner, dict(owner.__dict__))

    def watch_value(self, value: Any) -> None:
        if isinstance(value, list):
            if self._record("list", value, list(value)):
                for item in value:
                    if isinstance(item, Position):
                        self.watch_attrs(item)
            return
        if isinstance(value, dict):
            self._record("dict", value, list(value.items()))
            return
        if isinstance(value, deque):
            self._record("deque", value, list(value))
            return
        if isinstance(value, set):
            self._record("set", value, set(value))
            return
        if isinstance(value, np.ndarray):
            self._record("ndarray", value, value.copy())
            return
        if isinstance(value, random.Random):
            self._record("rng", value, value.getstate())
            return
        if isinstance(value, Position):
            self.watch_attrs(value)
            return
        if isinstance(value, tuple):
            for item in value:
                self.watch_value(item)

    def rollback(self) -> None:
        for kind, owner, state in reversed(self._entries):
            if kind == "attrs":
                owner.__dict__.clear()
                owner.__dict__.update(state)
            elif kind == "list":
                owner[:] = state
            elif kind == "dict":
                owner.clear()
                owner.update(state)
            elif kind == "deque":
                owner.clear()
                owner.extend(state)
            elif kind == "set":
                owner.clear()
                owner.update(state)
            elif kind == "ndarray":
                np.copyto(owner, state)
            elif kind == "rng":
                owner.setstate(state)
            else:  # pragma: no cover - closed internal record kinds
                raise AssertionError(f"unknown publication undo kind {kind!r}")

    def guard_write_receipt(self) -> tuple[tuple[str, Any, Any], ...]:
        """Return the exact first-write set while the transaction is live."""

        return tuple(self._entries)


def _live_publication_undo_journal(
    battle: Any,
    entity_registry: dict[int, Any],
) -> _UndoJournal:
    del battle, entity_registry
    return _UndoJournal()


def _watch_entity_attrs(
    undo: _UndoJournal | None,
    entity: Any,
    *position_fields: str,
) -> None:
    if undo is None:
        return
    undo.watch_attrs(entity)
    undo.watch_attrs(entity.position)
    for field in position_fields:
        value = getattr(entity, field, None)
        if isinstance(value, Position):
            undo.watch_attrs(value)


def _watch_cache_refresh_mutations(battle: Any, journal: _UndoJournal) -> None:
    """Lazily record mutable cache storage immediately before one refresh."""
    in_place_fast_cache_fields = {
        "_target_pos_x",
        "_target_pos_y",
        "_target_player",
        "_target_is_air",
        "_target_is_building",
        "_target_is_building_target",
        "_target_is_crown",
        "_target_is_targetable",
        "_target_requires_targetability_check",
        "_target_stealth_until",
        "_target_collision_radius",
        "_target_distance_discount_sq",
    }
    for name, value in battle.__dict__.items():
        if (
            "cache" in name
            or "bucket" in name
            or "placement_blocked" in name
            or name == "_pending_projectile_impacts"
            or name in in_place_fast_cache_fields
        ):
            journal.watch_value(value)


def _scalar(value: Any) -> int | float:
    if type(value) is tuple and len(value) == 3:
        tag, integer, bits = value
        if (
            type(tag) is int
            and tag == 0
            and type(integer) is int
            and -(1 << 63) <= integer < 1 << 63
            and type(bits) is int
            and bits == 0
        ):
            return integer
        if (
            type(tag) is int
            and tag == 1
            and type(integer) is int
            and integer == 0
            and type(bits) is int
            and 0 <= bits < 1 << 64
        ):
            try:
                return float(struct.unpack("<d", struct.pack("<Q", bits))[0])
            except struct.error as error:
                raise ResidentPublicationError(
                    f"invalid typed exact scalar payload: {value!r}"
                ) from error
        raise ResidentPublicationError(f"invalid typed exact scalar payload: {value!r}")
    if not isinstance(value, dict):
        raise ResidentPublicationError(f"invalid exact scalar payload: {value!r}")
    kind = value.get("kind")
    if kind == "int":
        return int(value["value"])
    if kind != "float":
        raise ResidentPublicationError(f"invalid exact scalar kind: {kind!r}")
    bits = int(str(value["bits"]), 16)
    return float(struct.unpack("<d", struct.pack("<Q", bits))[0])


def _float(value: Any) -> float:
    return float(_scalar(value))


def _exact(value: Any) -> dict[str, Any]:
    """Convert one typed exact scalar to the semantic-schema representation."""
    if type(value) is not tuple or len(value) != 3:
        raise ResidentPublicationError(f"invalid typed exact scalar payload: {value!r}")
    tag, integer, bits = value
    if (
        type(tag) is int
        and tag == 0
        and type(integer) is int
        and -(1 << 63) <= integer < 1 << 63
        and type(bits) is int
        and bits == 0
    ):
        return {"kind": "int", "value": integer}
    if (
        type(tag) is int
        and tag == 1
        and type(integer) is int
        and integer == 0
        and type(bits) is int
        and 0 <= bits < 1 << 64
    ):
        return {"bits": f"{bits:016x}", "kind": "float"}
    raise ResidentPublicationError(f"invalid typed exact scalar payload: {value!r}")


def _exact_float(value: Any) -> dict[str, Any]:
    if type(value) is not float:
        raise ResidentPublicationError(f"invalid typed binary64 value: {value!r}")
    try:
        bits = struct.unpack("<Q", struct.pack("<d", float(value)))[0]
    except (OverflowError, TypeError, ValueError, struct.error) as error:
        raise ResidentPublicationError(
            f"invalid typed binary64 value: {value!r}"
        ) from error
    return {"bits": f"{bits:016x}", "kind": "float"}


def _optional_exact_position(value: Any, *, exact: bool) -> list[Any] | None:
    if value is None:
        return None
    if type(value) is not tuple or len(value) != 2:
        raise ResidentPublicationError(f"invalid typed position payload: {value!r}")
    convert = _exact if exact else _exact_float
    return [convert(value[0]), convert(value[1])]


def _rows_by_id(
    rows: Iterable[dict[str, Any]],
    *,
    label: str,
) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        entity_id = int(row["id"])
        if entity_id in result:
            raise ResidentPublicationError(
                f"resident publication contains duplicate {label} id {entity_id}"
            )
        result[entity_id] = row
    return result


def _set_position(owner: Any, field: str, value: Any) -> None:
    if value is None:
        setattr(owner, field, None)
        return
    x = _scalar(value[0])
    y = _scalar(value[1])
    current = getattr(owner, field, None)
    if isinstance(current, Position):
        current.x = x
        current.y = y
    else:
        setattr(owner, field, Position(x, y))


def _set_direct_position(
    owner: Any,
    field: str,
    value: Any,
    *,
    exact: bool,
) -> None:
    if value is None:
        setattr(owner, field, None)
        return
    x = _scalar(value[0]) if exact else value[0]
    y = _scalar(value[1]) if exact else value[1]
    current = getattr(owner, field, None)
    if isinstance(current, Position):
        current.x = x
        current.y = y
    else:
        setattr(owner, field, Position(x, y))


def _set_sparse_default(owner: Any, field: str, value: Any, default: Any) -> None:
    del default
    setattr(owner, field, value)


def _validate_transient_boundary(battle: Any) -> None:
    if battle._pending_projectile_impacts:
        raise ResidentPublicationError(
            "resident publication requires an empty pending-projectile queue"
        )
    if battle._defer_projectile_impacts:
        raise ResidentPublicationError(
            "resident publication cannot run while projectile impacts are deferred"
        )
    if getattr(battle, "_projectile_lethal_reservations", None) is not None:
        raise ResidentPublicationError(
            "resident publication requires no phase-local lethal reservations"
        )
    if battle._coalesce_alive_building_refreshes:
        raise ResidentPublicationError(
            "resident publication cannot run inside a coalesced cache phase"
        )
    if battle._step_tick_remainder != 0.0:
        raise ResidentPublicationError(
            "resident publication requires an integer Python tick boundary"
        )


def _presence_from_mask(
    mask: Any,
    names: tuple[str, ...],
    *,
    offset: int,
    label: str,
) -> dict[str, bool]:
    if type(mask) is not int or mask < 0 or mask >= 1 << 64:
        raise ResidentPublicationError(f"invalid typed {label} presence mask")
    known = sum(1 << (offset + index) for index in range(len(names)))
    if mask & ~known:
        raise ResidentPublicationError(f"typed {label} presence has unknown bits")
    return {
        name: bool(mask & (1 << (offset + index))) for index, name in enumerate(names)
    }


def _direct_dict(value: Any, schema: str) -> dict[str, Any]:
    if type(value) is not dict or value.keys() != _DIRECT_KEYS[schema]:
        raise ResidentPublicationError(f"malformed direct {schema} publication")
    return cast(dict[str, Any], value)


def _direct_list(value: Any, label: str) -> list[Any]:
    if type(value) is not list:
        raise ResidentPublicationError(f"malformed direct {label} publication")
    return cast(list[Any], value)


def _direct_int(value: Any, label: str, *, minimum: int | None = None) -> int:
    if type(value) is not int or (minimum is not None and value < minimum):
        raise ResidentPublicationError(f"malformed direct {label} publication")
    return value


def _direct_bool(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise ResidentPublicationError(f"malformed direct {label} publication")
    return value


def _direct_float(value: Any, label: str) -> float:
    if type(value) is not float:
        raise ResidentPublicationError(f"malformed direct {label} publication")
    return value


def _direct_optional_int(value: Any, label: str) -> int | None:
    if value is None:
        return None
    return _direct_int(value, label, minimum=0)


def _direct_exact(value: Any, label: str) -> int | float:
    if type(value) is not tuple or len(value) != 3:
        raise ResidentPublicationError(f"malformed direct {label} exact scalar")
    tag, integer, bits = value
    if (
        type(tag) is int
        and tag == 0
        and type(integer) is int
        and -(1 << 63) <= integer < 1 << 63
        and type(bits) is int
        and bits == 0
    ):
        return integer
    if (
        type(tag) is int
        and tag == 1
        and type(integer) is int
        and integer == 0
        and type(bits) is int
        and 0 <= bits < 1 << 64
    ):
        return float(struct.unpack("<d", struct.pack("<Q", bits))[0])
    raise ResidentPublicationError(f"malformed direct {label} exact scalar")


def _direct_exact_matches(value: Any, actual: Any, label: str) -> bool:
    expected = _direct_exact(value, label)
    if type(expected) is not type(actual):
        return False
    if type(expected) is float:
        return struct.pack("=d", expected) == struct.pack("=d", actual)
    return bool(expected == actual)


def _direct_position(
    value: Any,
    label: str,
    *,
    exact: bool,
) -> tuple[int | float, int | float] | None:
    if value is None:
        return None
    if type(value) is not tuple or len(value) != 2:
        raise ResidentPublicationError(f"malformed direct {label} position")
    if exact:
        return (
            _direct_exact(value[0], f"{label}.x"),
            _direct_exact(value[1], f"{label}.y"),
        )
    return (
        _direct_float(value[0], f"{label}.x"),
        _direct_float(value[1], f"{label}.y"),
    )


def _validate_direct_modifier(state: Any, entity_id: int) -> None:
    if state is None:
        return
    row = _direct_dict(state, "modifier")
    for name in (
        "attack_speed_buff_multiplier",
        "attack_speed_debuff_multiplier",
        "haste_timer",
        "movement_mode_multiplier",
        "movement_speed_buff_multiplier",
        "slow_multiplier",
        "slow_timer",
        "spawn_speed_buff_multiplier",
        "spawn_speed_debuff_multiplier",
        "stun_timer",
    ):
        _direct_float(row[name], f"entity {entity_id} modifier {name}")
    if row["original_speed"] is not None:
        _direct_float(row["original_speed"], f"entity {entity_id} original speed")
    _direct_exact(row["speed"], f"entity {entity_id} speed")
    for name in ("haste_effects", "slow_effects"):
        effects = _direct_list(row[name], f"entity {entity_id} {name}")
        for effect in effects:
            effect_row = _direct_dict(effect, "modifier_effect")
            for field in _DIRECT_KEYS["modifier_effect"]:
                _direct_float(effect_row[field], f"entity {entity_id} {name}.{field}")


def _validate_direct_death_opcodes(opcodes: Any, entity_id: int) -> None:
    for opcode in _direct_list(opcodes, f"entity {entity_id} death opcodes"):
        row = _direct_dict(opcode, "death_opcode")
        kind = _direct_int(row["kind"], f"entity {entity_id} death opcode kind")
        present = [
            row["damage"] is not None,
            row["spawn"] is not None,
            row["area"] is not None,
        ]
        if kind not in (0, 1, 2) or present != [kind == 0, kind == 1, kind == 2]:
            raise ResidentPublicationError(
                f"malformed direct entity {entity_id} death opcode"
            )
        if kind == 0:
            state = _direct_dict(row["damage"], "death_damage")
            for field in ("base_damage", "radius_units", "knockback_units"):
                _direct_int(state[field], f"entity {entity_id} death damage {field}")
            for field in ("hits_air", "hits_ground"):
                _direct_bool(state[field], f"entity {entity_id} death damage {field}")
            for field in ("knockback_distance", "radius_tiles", "scaled_damage"):
                _direct_exact(state[field], f"entity {entity_id} death damage {field}")
        elif kind == 1:
            state = _direct_dict(row["spawn"], "death_spawn")
            for field in ("count", "deploy_time_ms"):
                _direct_int(state[field], f"entity {entity_id} death spawn {field}")
            for field in ("min_radius_tiles", "radius_tiles"):
                _direct_float(state[field], f"entity {entity_id} death spawn {field}")
            for field in ("radial_pushback", "spawn_const_priority"):
                _direct_bool(state[field], f"entity {entity_id} death spawn {field}")
            if type(state["unit_name"]) is not str or not _valid_fingerprint(
                state["unit_data_fingerprint"]
            ):
                raise ResidentPublicationError(
                    f"malformed direct entity {entity_id} death spawn provenance"
                )
        else:
            _validate_direct_area_spec(row["area"], f"entity {entity_id} death area")


def _validate_direct_area_spec(value: Any, label: str) -> None:
    spec = _direct_dict(value, "area_spec")
    if type(spec["area_name"]) is not str:
        raise ResidentPublicationError(f"malformed direct {label} name")
    for field in (
        "attack_multiplier",
        "duration",
        "effect_tick_interval",
        "movement_multiplier",
        "radius_tiles",
        "refresh_duration",
        "spawn_multiplier",
    ):
        _direct_float(spec[field], f"{label}.{field}")
    _direct_int(spec["radius_units"], f"{label}.radius_units")
    for field in (
        "affects_hidden",
        "cap_buff_time_to_effect",
        "hits_air",
        "hits_ground",
    ):
        _direct_bool(spec[field], f"{label}.{field}")


def _valid_fingerprint(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _validate_direct_entity_scalars(row: dict[str, Any], entity_id: int) -> None:
    for field in ("position_x", "position_y", "hitpoints", "max_hitpoints", "damage"):
        _direct_exact(row[field], f"entity {entity_id}.{field}")
    for field in (
        "deploy_delay_remaining",
        "placement_delay_total",
        "freeze_expiry_time",
        "spawn_angle_shift",
    ):
        _direct_float(row[field], f"entity {entity_id}.{field}")
    for field in (
        "active",
        "is_alive",
        "placement_pending",
        "spawn_hook_pending",
        "spawn_hook_fired",
    ):
        _direct_bool(row[field], f"entity {entity_id}.{field}")
    for field in (
        "player_id",
        "entity_kind",
        "death_spawn_target_immunity_elapsed_ms",
        "pending_projectile_max_duration_ms",
        "shield_break_count",
    ):
        _direct_int(row[field], f"entity {entity_id}.{field}")
    _direct_optional_int(row["target_id"], f"entity {entity_id}.target_id")
    if type(row["python_type"]) is not str or type(row["card_name"]) is not str:
        raise ResidentPublicationError(f"malformed direct entity {entity_id} identity")
    mechanics = _direct_list(row["mechanics"], f"entity {entity_id} mechanics")
    if any(type(value) is not str for value in mechanics):
        raise ResidentPublicationError(f"malformed direct entity {entity_id} mechanics")
    for shield in _direct_list(row["shields"], f"entity {entity_id} shields"):
        shield_row = _direct_dict(shield, "shield")
        _direct_exact(shield_row["current"], f"entity {entity_id} shield current")
        _direct_exact(shield_row["maximum"], f"entity {entity_id} shield maximum")
    _validate_direct_modifier(row["modifier_state"], entity_id)
    _validate_direct_death_opcodes(row["death_opcodes"], entity_id)
    _validate_direct_status_nova_jump(row["status_nova_jump"], entity_id)


def _validate_direct_status_nova_jump(value: Any, entity_id: int) -> None:
    if value is None:
        return
    row = _direct_dict(value, "status_nova_jump")
    for field in (
        "freeze_radius_units",
        "freeze_duration_ms",
        "hop_duration_ms",
        "jump_speed_units_per_tick",
    ):
        _direct_int(row[field], f"entity {entity_id} status nova {field}")
    for field in ("affects_hidden", "hits_air", "hits_ground", "detonated"):
        _direct_bool(row[field], f"entity {entity_id} status nova {field}")
    _direct_float(row["jump_timer_ms"], f"entity {entity_id} status nova timer")
    _direct_optional_int(
        row["jump_target_id"], f"entity {entity_id} status nova target"
    )
    _direct_position(
        row["jump_destination"],
        f"entity {entity_id} status nova destination",
        exact=True,
    )
    _direct_position(
        row["jump_origin"], f"entity {entity_id} status nova origin", exact=True
    )
    if (
        row["freeze_radius_units"] <= 0
        or row["freeze_duration_ms"] <= 0
        or row["hop_duration_ms"] < 0
        or row["jump_speed_units_per_tick"] <= 0
        or row["jump_timer_ms"] < 0.0
        or not (row["hits_air"] or row["hits_ground"])
        or ((row["jump_target_id"] is None) != (row["jump_destination"] is None))
        or (row["jump_target_id"] is not None and row["jump_origin"] is None)
    ):
        raise ResidentPublicationError(
            f"malformed direct entity {entity_id} status-nova jump"
        )


def _validate_direct_movement(value: Any, entity_id: int) -> None:
    if value is None:
        return
    row = _direct_dict(value, "movement")
    for field in (
        "building_pathing_radius",
        "jump_speed",
        "pending_x",
        "pending_y",
        "river_jump_duration",
        "river_jump_elapsed",
        "serialized_speed",
        "stop_movement_after_ms",
        "wait_ms",
    ):
        _direct_float(row[field], f"entity {entity_id} movement {field}")
    for field in (
        "death_spawn_travel_ticks",
        "knockback_velocity_work",
        "movement_phase_elapsed_ms",
        "native_avoidance",
        "native_lane_id",
        "route_cache_kind",
        "route_lane_id",
        "vector_count",
        "vector_x_units",
        "vector_y_units",
    ):
        _direct_int(row[field], f"entity {entity_id} movement {field}")
    _direct_float(row["unit_mass"], f"entity {entity_id} movement unit_mass")
    for field in (
        "charge_range_present",
        "forced_movement_active",
        "is_hover",
        "jump_height_present",
        "kamikaze_primed",
        "knockback_immune",
        "knockback_interrupts_combat",
        "native_natural_movement_active",
        "pending_consumed",
        "river_jump_active",
        "river_jump_blocked",
        "route_backwards",
        "route_cache_supported",
        "route_jump_height",
        "special_move_active",
        "special_move_consumed_tick",
        "stun_interrupt_deferred_until_landing",
        "vector_bypasses_cap",
    ):
        _direct_bool(row[field], f"entity {entity_id} movement {field}")
    for field, exact in (
        ("death_spawn_travel_target", False),
        ("knockback_target", False),
        ("river_jump_origin", True),
        ("river_jump_target", False),
    ):
        _direct_position(
            row[field], f"entity {entity_id} movement {field}", exact=exact
        )
    kind = row["route_cache_kind"]
    if kind == 3 or not row["route_cache_supported"]:
        raise ResidentPublicationError(
            f"resident publication rejected unsupported route cache for id {entity_id}"
        )
    if kind not in (0, 1, 2, 3):
        raise ResidentPublicationError(
            f"malformed direct entity {entity_id} route kind"
        )
    goal = row["route_goal"]
    cells = _direct_list(row["route_cells"], f"entity {entity_id} route cells")
    if kind == 0:
        if goal is not None or cells:
            raise ResidentPublicationError(
                f"malformed direct entity {entity_id} absent route"
            )
    elif kind == 2:
        if (
            type(goal) is not tuple
            or len(goal) != 2
            or any(type(v) is not int for v in goal)
        ):
            raise ResidentPublicationError(
                f"malformed direct entity {entity_id} route goal"
            )
        for cell in cells:
            if (
                type(cell) is not tuple
                or len(cell) != 2
                or any(type(v) is not int for v in cell)
            ):
                raise ResidentPublicationError(
                    f"malformed direct entity {entity_id} route cells"
                )


def _validate_direct_combat(value: Any, entity_id: int) -> None:
    if value is None:
        return
    row = _direct_dict(value, "combat")
    for field in (
        "attack_cooldown",
        "attack_mode_multiplier",
        "attack_speed_buff_multiplier",
        "attack_speed_debuff_multiplier",
        "collision_radius",
        "damage",
        "last_attack_time",
        "range",
        "sight_clip",
        "sight_clip_side",
        "sight_range",
        "stun_timer",
    ):
        _direct_float(row[field], f"entity {entity_id} combat {field}")
    _direct_exact(row["constructor_range"], f"entity {entity_id} constructor range")
    _direct_position(
        row["initial_position"], f"entity {entity_id} initial position", exact=True
    )
    for field in (
        "facing_x_units",
        "facing_y_units",
        "first_hit_ms",
        "hit_speed_ms",
        "native_target_distance_discount_sq_units",
        "retarget_ms",
        "stealth_until_ms",
    ):
        _direct_int(row[field], f"entity {entity_id} combat {field}")
    for field in (
        "allow_area_damage_when_invisible",
        "attack_preload_blocked",
        "attack_windup_active",
        "can_attack_air",
        "can_attack_ground",
        "ground_path_backwards",
        "has_attacked_once",
        "hidden_building",
        "is_air_unit",
        "is_airborne_for_projectile",
        "native_building_target",
        "targets_only_buildings",
    ):
        _direct_bool(row[field], f"entity {entity_id} combat {field}")
    direct_area = row["direct_area"]
    if direct_area is not None:
        area = _direct_dict(direct_area, "direct_area")
        _direct_int(area["radius_units"], f"entity {entity_id} direct area radius")
        _direct_bool(area["self_centered"], f"entity {entity_id} direct area center")
    point_weapon = row["point_weapon"]
    if point_weapon is not None:
        point = _direct_dict(point_weapon, "point_weapon")
        for field in (
            "travel_speed",
            "start_radius",
            "y_offset",
            "splash_radius",
            "crown_tower_damage_multiplier",
            "stun_duration",
            "slow_duration",
            "slow_multiplier",
        ):
            _direct_float(point[field], f"entity {entity_id} point weapon {field}")
        _direct_bool(
            point["tracks_target"], f"entity {entity_id} point weapon tracking"
        )
        planes = point["hit_planes"]
        if planes is not None and (
            type(planes) is not tuple
            or len(planes) != 2
            or any(type(value) is not bool for value in planes)
        ):
            raise ResidentPublicationError(
                f"malformed direct entity {entity_id} point weapon planes"
            )
    for field in ("last_combat_target_id", "movement_target_id"):
        _direct_optional_int(row[field], f"entity {entity_id} combat {field}")


def _validate_direct_building(row: dict[str, Any], entity_id: int) -> None:
    lifetime = row["building_lifetime_state"]
    impact = row["building_impact_state"]
    if lifetime is None and impact is None:
        return
    if lifetime is None or impact is None:
        raise ResidentPublicationError(
            f"malformed direct entity {entity_id} building state"
        )
    lifetime_row = _direct_dict(lifetime, "building_lifetime")
    impact_row = _direct_dict(impact, "building_impact")
    if lifetime_row["lifetime_ms"] is not None:
        _direct_int(lifetime_row["lifetime_ms"], f"entity {entity_id} lifetime ms")
    _direct_float(
        lifetime_row["lifetime_elapsed"], f"entity {entity_id} lifetime elapsed"
    )
    _direct_int(lifetime_row["decay_work"], f"entity {entity_id} lifetime work")
    _direct_float(lifetime_row["tick_carry_ms"], f"entity {entity_id} lifetime carry")
    for field in (
        "activation_delay_remaining",
        "activation_delay_seconds",
        "activation_first_hit_delay_remaining",
        "activation_first_hit_delay_seconds",
        "collision_radius",
    ):
        _direct_float(impact_row[field], f"entity {entity_id} building {field}")
    _direct_int(impact_row["stealth_until_ms"], f"entity {entity_id} building stealth")
    for field in (
        "allow_area_damage_when_invisible",
        "is_king_tower",
        "requires_activation",
        "tower_active",
    ):
        _direct_bool(impact_row[field], f"entity {entity_id} building {field}")
    if (
        impact_row["crown_slot"] is not None
        and type(impact_row["crown_slot"]) is not str
    ):
        raise ResidentPublicationError(
            f"malformed direct entity {entity_id} crown slot"
        )


def _validate_direct_point(value: Any, entity_id: int) -> None:
    if value is None:
        return
    row = _direct_dict(value, "point")
    for field in (
        "constructor_range",
        "constructor_sight_range",
        "target_x",
        "target_y",
    ):
        _direct_exact(row[field], f"entity {entity_id} projectile {field}")
    for field in (
        "crown_tower_damage_multiplier",
        "damage_wave_interval",
        "homing_min_distance",
        "knockback_distance",
        "launch_delay",
        "launch_x",
        "launch_y",
        "slow_duration",
        "slow_multiplier",
        "splash_radius",
        "stun_duration",
        "travel_speed",
    ):
        _direct_float(row[field], f"entity {entity_id} projectile {field}")
    if row["crown_tower_damage"] is not None:
        _direct_float(row["crown_tower_damage"], f"entity {entity_id} crown damage")
    for field in (
        "homing_time_ms",
        "temporary_homing_remaining_ms",
    ):
        _direct_int(row[field], f"entity {entity_id} projectile {field}")
    for field in (
        "hits_air",
        "hits_ground",
        "ignore_buildings",
        "knockback_ignores_mass",
        "permanent_homing_disabled_by_temporary",
        "start_collision_resolved",
        "tracks_target",
    ):
        _direct_bool(row[field], f"entity {entity_id} projectile {field}")
    unsupported = _direct_list(
        row["unsupported"], f"entity {entity_id} projectile unsupported"
    )
    if any(type(value) is not str for value in unsupported) or unsupported:
        raise ResidentPublicationError(f"unsupported direct projectile {entity_id}")
    for field in (
        "damage_group_id",
        "primary_target_id",
        "source_entity_id",
        "temporary_homing_target_id",
    ):
        _direct_optional_int(row[field], f"entity {entity_id} projectile {field}")
    if type(row["source_kind"]) is not str:
        raise ResidentPublicationError(
            f"malformed direct projectile {entity_id} source"
        )
    hit_ids = row["damage_group_hit_entity_ids"]
    if hit_ids is not None:
        ids = _direct_list(hit_ids, f"entity {entity_id} projectile hit ids")
        if any(type(value) is not int or value < 0 for value in ids) or len(
            set(ids)
        ) != len(ids):
            raise ResidentPublicationError(
                f"malformed direct projectile {entity_id} hit ids"
            )
    spawn = row["spawn_projectile_state"]
    if spawn is not None:
        spawn_row = _direct_dict(spawn, "spawn_projectile_state")
        for field in ("activation_delay", "time_alive"):
            number = _direct_float(
                spawn_row[field], f"entity {entity_id} spawn projectile {field}"
            )
            if not np.isfinite(number) or number < 0.0:
                raise ResidentPublicationError(
                    f"malformed direct spawn projectile {entity_id} {field}"
                )
        count = _direct_int(
            spawn_row["spawn_count"],
            f"entity {entity_id} spawn projectile count",
        )
        if not 1 <= count <= 90:
            raise ResidentPublicationError(
                f"malformed direct spawn projectile {entity_id} count"
            )
        if (
            type(spawn_row["spawn_character"]) is not str
            or not spawn_row["spawn_character"]
            or not _valid_fingerprint(spawn_row["spawn_data_fingerprint"])
        ):
            raise ResidentPublicationError(
                f"malformed direct spawn projectile {entity_id} child"
            )
        for field in ("spawn_radius", "spawn_deploy_delay"):
            if spawn_row[field] is not None:
                number = _direct_float(
                    spawn_row[field],
                    f"entity {entity_id} spawn projectile {field}",
                )
                if not np.isfinite(number) or number < 0.0:
                    raise ResidentPublicationError(
                        f"malformed direct spawn projectile {entity_id} {field}"
                    )
        _direct_bool(
            spawn_row["spawn_const_priority"],
            f"entity {entity_id} spawn projectile priority",
        )


def _direct_f64_same(left: float, right: float) -> bool:
    return struct.pack("=d", left) == struct.pack("=d", right)


def _validate_direct_spawn_projectile_recipe(
    row: dict[str, Any], resident: ResidentRustBattle, entity_id: int
) -> None:
    point = row["point_projectile_state"]
    if (
        point is not None
        and point["spawn_projectile_state"] is not None
        and (
            row["python_type"] != "clasher.entities.SpawnProjectile"
            or row["entity_kind"] != 2
            or row["card_name"] != ""
            or row["hitpoints"] != (0, 1, 0)
            or row["max_hitpoints"] != (0, 1, 0)
            or row["target_id"] is not None
            or not _direct_f64_same(row["deploy_delay_remaining"], 0.0)
            or not _direct_f64_same(row["placement_delay_total"], 0.0)
            or row["placement_pending"]
            or row["spawn_hook_pending"]
            or row["spawn_hook_fired"]
            or not _direct_f64_same(row["freeze_expiry_time"], 0.0)
            or row["death_spawn_target_immunity_elapsed_ms"] != -1
            or row["pending_projectile_max_duration_ms"] != 0
            or not _direct_f64_same(row["spawn_angle_shift"], 0.0)
            or row["mechanics"]
            or row["shields"]
            or row["shield_break_count"] != 0
            or row["death_opcodes"]
            or row["modifier_state"] is not None
            or row["movement_state"] is not None
            or row["locked_combat_state"] is not None
            or row["building_lifetime_state"] is not None
            or row["building_impact_state"] is not None
            or row["rolling_projectile_state"] is not None
            or row["area_effect_state"] is not None
            or row["status_nova_jump"] is not None
            or point["primary_target_id"] is not None
            or point["source_entity_id"] is not None
            or point["damage_group_id"] is not None
            or point["damage_group_hit_entity_ids"] is not None
            or not _direct_f64_same(point["launch_delay"], 0.0)
            or not point["tracks_target"]
            or point["temporary_homing_remaining_ms"] != 0
            or point["temporary_homing_target_id"] is not None
            or point["permanent_homing_disabled_by_temporary"]
            or point["start_collision_resolved"]
            or point["constructor_range"] != (0, 0, 0)
            or point["constructor_sight_range"] != (0, 0, 0)
            or point["homing_time_ms"] != 0
            or not _direct_f64_same(point["homing_min_distance"], 0.0)
            or not _direct_f64_same(point["stun_duration"], 0.0)
            or not _direct_f64_same(point["slow_duration"], 0.0)
            or not _direct_f64_same(point["slow_multiplier"], 1.0)
            or not _direct_f64_same(point["knockback_distance"], 0.0)
            or point["knockback_ignores_mass"]
            or not _direct_f64_same(point["damage_wave_interval"], 0.0)
        )
    ):
        raise ResidentPublicationError(
            f"spawn projectile {entity_id} has unsupported base shape"
        )
    damage = _direct_exact(row["damage"], f"entity {entity_id} damage")
    _validate_direct_spawn_projectile_state(
        point, damage, row["player_id"], resident, entity_id
    )


def _validate_direct_spawn_projectile_state(
    point: dict[str, Any] | None,
    damage: float,
    player_id: int,
    resident: ResidentRustBattle,
    entity_id: int,
) -> None:
    if point is None or point["spawn_projectile_state"] is None:
        return
    if (
        point["primary_target_id"] is not None
        or point["source_entity_id"] is not None
        or point["damage_group_id"] is not None
        or point["damage_group_hit_entity_ids"] is not None
        or not _direct_f64_same(point["launch_delay"], 0.0)
        or not point["tracks_target"]
        or point["temporary_homing_remaining_ms"] != 0
        or point["temporary_homing_target_id"] is not None
        or point["permanent_homing_disabled_by_temporary"]
        or point["start_collision_resolved"]
        or point["constructor_range"] != (0, 0, 0)
        or point["constructor_sight_range"] != (0, 0, 0)
        or point["homing_time_ms"] != 0
        or not _direct_f64_same(point["homing_min_distance"], 0.0)
        or not _direct_f64_same(point["stun_duration"], 0.0)
        or not _direct_f64_same(point["slow_duration"], 0.0)
        or not _direct_f64_same(point["slow_multiplier"], 1.0)
        or not _direct_f64_same(point["knockback_distance"], 0.0)
        or point["knockback_ignores_mass"]
        or not _direct_f64_same(point["damage_wave_interval"], 0.0)
    ):
        raise ResidentPublicationError(
            f"spawn projectile {entity_id} has unsupported point shape"
        )
    state = point["spawn_projectile_state"]
    recipe = resident.spawn_projectile_recipe(point["source_kind"])
    if recipe is None:
        raise ResidentPublicationError(
            f"spawn projectile {entity_id} has no attested recipe"
        )
    expected_pairs = (
        (float(damage), recipe.damage),
        (point["travel_speed"], recipe.travel_speed),
        (point["splash_radius"], recipe.radius),
        (point["crown_tower_damage_multiplier"], recipe.crown_tower_damage_multiplier),
        (state["activation_delay"], recipe.activation_delay),
    )
    if any(not _direct_f64_same(left, right) for left, right in expected_pairs) or (
        point["crown_tower_damage"] is None
    ) != (recipe.crown_tower_damage is None) or (
        point["crown_tower_damage"] is not None
        and not _direct_f64_same(
            point["crown_tower_damage"], cast(float, recipe.crown_tower_damage)
        )
    ):
        raise ResidentPublicationError(
            f"spawn projectile {entity_id} payload changed from its attested recipe"
        )
    if (
        state["spawn_count"] != recipe.spawn_count
        or state["spawn_character"] != recipe.spawn_character
        or state["spawn_data_fingerprint"] != recipe.spawn_data_fingerprint
        or state["spawn_const_priority"] != recipe.spawn_const_priority
        or point["hits_air"] != recipe.hits_air
        or point["hits_ground"] != recipe.hits_ground
        or point["ignore_buildings"] != recipe.ignore_buildings
    ):
        raise ResidentPublicationError(
            f"spawn projectile {entity_id} constructor provenance changed"
        )
    for field, expected in (
        ("spawn_radius", recipe.spawn_radius),
        ("spawn_deploy_delay", recipe.spawn_deploy_delay),
    ):
        actual = state[field]
        if (actual is None) != (expected is None) or (
            actual is not None
            and not _direct_f64_same(actual, cast(float, expected))
        ):
            raise ResidentPublicationError(
                f"spawn projectile {entity_id} changed {field}"
            )
    expected_launch = (
        (9.0, 2.5 if player_id == 0 else 29.5)
        if recipe.launch_from_king
        else (_scalar(point["target_x"]), _scalar(point["target_y"]))
    )
    if not _direct_f64_same(point["launch_x"], float(expected_launch[0])) or not _direct_f64_same(
        point["launch_y"], float(expected_launch[1])
    ):
        raise ResidentPublicationError(
            f"spawn projectile {entity_id} launch provenance changed"
        )


def _validate_direct_rolling(value: Any, entity_id: int) -> None:
    if value is None:
        return
    row = _direct_dict(value, "rolling")
    if type(row["source_kind"]) is not str or not row["source_kind"]:
        raise ResidentPublicationError(
            f"malformed direct rolling projectile {entity_id} source"
        )
    if row["spawn_character"] is not None and (
        type(row["spawn_character"]) is not str or not row["spawn_character"]
    ):
        raise ResidentPublicationError(
            f"malformed direct rolling projectile {entity_id} child name"
        )
    if not _valid_fingerprint(row["spawn_character_data_fingerprint"]):
        raise ResidentPublicationError(
            f"malformed direct rolling projectile {entity_id} child data fingerprint"
        )
    if row["spawn_deploy_delay_override"] is not None:
        delay = _direct_float(
            row["spawn_deploy_delay_override"],
            f"entity {entity_id} rolling child deploy delay",
        )
        if not np.isfinite(delay) or delay < 0.0:
            raise ResidentPublicationError(
                f"malformed direct rolling projectile {entity_id} child deploy delay"
            )
    travel_speed = _direct_exact(
        row["travel_speed"], f"entity {entity_id} rolling travel speed"
    )
    for field in (
        "rolling_radius",
        "projectile_range",
        "spawn_delay",
        "radius_y",
        "knockback_distance",
        "crown_tower_damage_multiplier",
        "time_alive",
        "distance_traveled",
    ):
        value = _direct_float(row[field], f"entity {entity_id} rolling {field}")
        if not np.isfinite(value):
            raise ResidentPublicationError(
                f"nonfinite direct rolling projectile {entity_id} {field}"
            )
    if row["crown_tower_damage"] is not None:
        _direct_float(
            row["crown_tower_damage"], f"entity {entity_id} rolling crown damage"
        )
    for field in ("knockback_ignores_mass", "has_spawned_character"):
        _direct_bool(row[field], f"entity {entity_id} rolling {field}")
    hit_ids = _direct_list(
        row["hit_entity_ids"], f"entity {entity_id} rolling hit IDs"
    )
    if (
        any(type(value) is not int or value < 0 for value in hit_ids)
        or hit_ids != sorted(hit_ids)
        or len(set(hit_ids)) != len(hit_ids)
    ):
        raise ResidentPublicationError(
            f"malformed direct rolling projectile {entity_id} hit IDs"
        )
    if (
        type(travel_speed) is not int
        or travel_speed <= 0
        or row["rolling_radius"] <= 0.0
        or row["projectile_range"] <= 0.0
        or any(
            row[field] < 0.0
            for field in (
                "spawn_delay",
                "radius_y",
                "knockback_distance",
                "crown_tower_damage_multiplier",
                "time_alive",
                "distance_traveled",
            )
        )
        or row["distance_traveled"] > row["projectile_range"] + 1e-9
        or (
            row["crown_tower_damage"] is not None
            and row["crown_tower_damage"] < 0.0
        )
    ):
        raise ResidentPublicationError(
            f"direct rolling projectile {entity_id} is outside the supported closure"
        )


def _validate_direct_rolling_recipe(
    state: dict[str, Any],
    resident: ResidentRustBattle,
    entity_id: int,
) -> None:
    recipe = resident.rolling_projectile_recipe(state["source_kind"])
    expected_delay = None if recipe is None else recipe.spawn_deploy_delay
    actual_delay = state["spawn_deploy_delay_override"]
    delay_matches = (actual_delay is None) == (expected_delay is None)
    if actual_delay is not None and expected_delay is not None:
        delay_matches = struct.pack(">d", actual_delay) == struct.pack(">d", expected_delay)
    if (
        recipe is None
        or state["spawn_character"] != recipe.spawn_character
        or state["spawn_character_data_fingerprint"]
        != recipe.spawn_data_fingerprint
        or not delay_matches
    ):
        raise ResidentPublicationError(
            f"resident rolling projectile {entity_id} constructor provenance changed"
        )


def _validate_direct_area(value: Any, entity_id: int) -> None:
    if value is None:
        return
    row = _direct_dict(value, "area")
    _direct_optional_int(
        row["birth_source_entity_id"], f"entity {entity_id} area source"
    )
    _direct_bool(row["effect_snapshot_applied"], f"entity {entity_id} area snapshot")
    _direct_bool(row["supported"], f"entity {entity_id} area supported")
    if not row["supported"]:
        raise ResidentPublicationError(f"unsupported direct area effect {entity_id}")
    _direct_float(row["time_alive"], f"entity {entity_id} area time")
    _validate_direct_area_spec(row["spec"], f"entity {entity_id} area")


def _validate_direct_character_birth(value: Any, entity_id: int) -> None:
    if value is None:
        return
    row = _direct_dict(value, "character_birth")
    kind = _direct_int(row["kind"], f"entity {entity_id} birth kind")
    if kind not in (0, 1, 2, 3):
        raise ResidentPublicationError(
            f"unsupported direct character birth {entity_id}"
        )
    for field in ("group_id", "member_count", "ordinal"):
        _direct_int(row[field], f"entity {entity_id} birth {field}", minimum=0)
    if entity_id != row["group_id"] + row["ordinal"] or row["member_count"] <= 0:
        raise ResidentPublicationError(f"malformed direct character birth {entity_id}")
    if type(row["effective_name"]) is not str or not _valid_fingerprint(
        row["template_fingerprint"]
    ):
        raise ResidentPublicationError(
            f"malformed direct character birth {entity_id} identity"
        )
    if kind == 0:
        if type(row["lookup_name"]) is not str or any(
            row[field] is not None
            for field in ("source_entity_id", "opcode_index", "unit_data_fingerprint")
        ):
            raise ResidentPublicationError(
                f"malformed direct catalog birth {entity_id}"
            )
    elif kind == 1:
        if (
            row["lookup_name"] is not None
            or _direct_optional_int(
                row["source_entity_id"], f"entity {entity_id} birth source"
            )
            is None
            or _direct_optional_int(
                row["opcode_index"], f"entity {entity_id} birth opcode"
            )
            is None
            or not _valid_fingerprint(row["unit_data_fingerprint"])
        ):
            raise ResidentPublicationError(f"malformed direct death birth {entity_id}")
    elif kind == 2:
        if (
            type(row["lookup_name"]) is not str
            or _direct_optional_int(
                row["source_entity_id"], f"entity {entity_id} rolling birth source"
            )
            is None
            or row["opcode_index"] is not None
            or not _valid_fingerprint(row["unit_data_fingerprint"])
            or row["member_count"] != 1
            or row["ordinal"] != 0
        ):
            raise ResidentPublicationError(
                f"malformed direct rolling birth {entity_id}"
            )
    else:
        if (
            type(row["lookup_name"]) is not str
            or _direct_optional_int(
                row["source_entity_id"],
                f"entity {entity_id} spawn projectile birth source",
            )
            is None
            or row["opcode_index"] is not None
            or not _valid_fingerprint(row["unit_data_fingerprint"])
        ):
            raise ResidentPublicationError(
                f"malformed direct spawn-projectile birth {entity_id}"
            )


def _direct_death_spawn_source(
    source_id: int,
    group_id: int,
    *,
    battle: Any,
    resident: ResidentRustBattle,
    entity_registry: dict[int, Any],
    same_publication_births: dict[int, dict[str, Any]],
) -> Any | None:
    """Resolve a death-spawn source from the prior or an attested action birth.

    A catalog-action troop can die and execute its compiled DeathSpawn opcode in
    the same resident interval in which it was allocated. Such a source is not
    in the prior Python registry yet, so validate its full suffix row against
    the catalog recipe and inspect the detached attested prototype instead.
    """
    source = entity_registry.get(source_id)
    if source is not None:
        return source
    source_row = same_publication_births.get(source_id)
    if source_row is None or source_id >= group_id or source_row["entity_kind"] != 0:
        return None
    source_birth = source_row["character_birth"]
    if source_birth is None or source_birth["kind"] != 0:
        return None
    recipe = resident.character_action_birth_recipe(
        source_birth["lookup_name"],
        source_birth["template_fingerprint"],
        source_birth["ordinal"],
    )
    if (
        recipe is None
        or recipe.kind != "catalog_action"
        or recipe.action_kind != "troop"
        or recipe.effective_name != source_birth["effective_name"]
        or recipe.template_fingerprint != source_birth["template_fingerprint"]
        or recipe.member_count != source_birth["member_count"]
        or source_row["card_name"] != source_birth["effective_name"]
        or type(recipe.prototype) is not Troop
        or not resident.character_action_card_stats_are_current(
            battle, source_birth["lookup_name"]
        )
    ):
        return None
    return recipe.prototype


def _build_direct_publication_plan(
    raw: Any,
    *,
    battle: Any,
    resident: ResidentRustBattle,
    entity_registry: dict[int, Any],
) -> _DirectPublicationPlan:
    """Validate one native graph and retain only its direct application shape."""
    root = _direct_dict(raw, "root")
    if _direct_int(root["version"], "publication version") != 1:
        raise ResidentPublicationError("unsupported direct publication version")
    binding = _direct_dict(root["binding"], "binding")
    if binding["semantic_schema_version"] != RESIDENT_SEMANTIC_SCHEMA_VERSION:
        raise ResidentPublicationError("direct semantic schema changed")
    for field in (
        "lineage_id",
        "prior_node_id",
        "prior_epoch",
        "candidate_node_id",
        "candidate_epoch",
        "parent_node_id",
        "parent_epoch",
        "prior_next_entity_id",
        "checkpoint_schema_version",
        "checkpoint_generation",
        "catalog_schema_version",
    ):
        _direct_int(binding[field], f"binding {field}", minimum=0)
    prior_ids = _direct_list(binding["prior_entity_ids"], "prior entity IDs")
    if any(type(value) is not int or value < 0 for value in prior_ids):
        raise ResidentPublicationError(
            "typed publication prior entity IDs are malformed"
        )
    if tuple(entity_registry) != tuple(prior_ids):
        raise ResidentPublicationError(
            "typed publication registry disagrees with the authenticated prior"
        )
    if binding["prior_next_entity_id"] != battle.next_entity_id:
        raise ResidentPublicationError(
            "typed publication next-entity ID disagrees with the live prior"
        )
    if (
        binding["parent_node_id"] != binding["prior_node_id"]
        or binding["parent_epoch"] != binding["prior_epoch"]
    ):
        raise ResidentPublicationError("typed publication is not a direct child")
    if binding["checkpoint_schema_version"] != 2:
        raise ResidentPublicationError("typed publication checkpoint schema changed")
    if binding["catalog_schema_version"] != RESIDENT_CARD_CATALOG_SCHEMA_VERSION:
        raise ResidentPublicationError("typed publication catalog schema changed")
    for field in ("catalog_fingerprint", "catalog_source_fingerprint"):
        if not _valid_fingerprint(binding[field]):
            raise ResidentPublicationError(f"typed publication has malformed {field}")

    battle_row = _direct_dict(root["battle"], "battle")
    entity_bits = len(_ENTITY_SPARSE_ATTRIBUTE_NAMES)
    battle_mask = _direct_int(
        battle_row["sparse_attribute_presence"], "battle presence", minimum=0
    )
    known_battle_mask = sum(
        1 << (entity_bits + index)
        for index in range(len(_BATTLE_SPARSE_ATTRIBUTE_NAMES))
    )
    if battle_mask & ~known_battle_mask:
        raise ResidentPublicationError("typed battle presence has unknown bits")
    for field in ("tick", "next_entity_id"):
        _direct_int(battle_row[field], f"battle {field}", minimum=0)
    for field in ("time", "dt"):
        _direct_float(battle_row[field], f"battle {field}")
    for field in (
        "double_elixir",
        "triple_elixir",
        "overtime",
        "game_over",
        "sudden_death",
        "win_conditions_dirty",
    ):
        _direct_bool(battle_row[field], f"battle {field}")
    crowns = battle_row["sudden_death_crowns"]
    if (
        type(crowns) is not tuple
        or len(crowns) != 2
        or any(type(v) is not int for v in crowns)
    ):
        raise ResidentPublicationError("malformed direct sudden-death crowns")
    if battle_row["winner"] is not None and type(battle_row["winner"]) is not int:
        raise ResidentPublicationError("malformed direct winner")

    players_raw = _direct_list(root["players"], "players")
    if len(players_raw) != 2:
        raise ResidentPublicationError("typed publication player count changed")
    players: list[dict[str, Any]] = []
    for index, value in enumerate(players_raw):
        player = _direct_dict(value, "player")
        if _direct_int(player["player_id"], "player id") != index:
            raise ResidentPublicationError("typed publication player order changed")
        for field in ("elixir", "max_elixir"):
            _direct_float(player[field], f"player {index} {field}")
        for field in ("king_tower_hp", "left_tower_hp", "right_tower_hp"):
            _direct_exact(player[field], f"player {index} {field}")
        _direct_int(player["next_card_refill_cooldown_ms"], f"player {index} refill")
        hand = _direct_list(player["hand"], f"player {index} hand")
        if any(card is not None and type(card) is not str for card in hand):
            raise ResidentPublicationError(f"malformed direct player {index} hand")
        cycle = _direct_list(player["cycle_queue"], f"player {index} cycle queue")
        if any(type(card) is not str for card in cycle):
            raise ResidentPublicationError(
                f"malformed direct player {index} cycle queue"
            )
        players.append(player)

    towers: list[dict[str, Any]] = []
    for value in _direct_list(root["towers"], "towers"):
        tower = _direct_dict(value, "tower")
        for field in ("id", "hp_milli", "player_id"):
            _direct_int(tower[field], f"tower {field}")
        _direct_exact(tower["hp"], "tower hp")
        _direct_float(tower["last_attack_time"], "tower last attack")
        for field in ("active", "is_active", "is_alive"):
            _direct_bool(tower[field], f"tower {field}")
        if type(tower["slot"]) is not str:
            raise ResidentPublicationError("malformed direct tower slot")
        towers.append(tower)

    raw_entities = _direct_list(root["entities"], "entities")
    entities: list[_DirectEntityPublication] = []
    active_slots: list[int | None] = []
    all_ids: set[int] = set()
    actual_birth_ids: set[int] = set()
    group_snapshots: dict[int, tuple[int, ...]] = {}
    active_group_snapshots: dict[int, tuple[int, ...]] = {}
    character_groups: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for value in raw_entities:
        row = _direct_dict(value, "entity")
        entity_id = _direct_int(row["id"], "entity id", minimum=0)
        if entity_id in all_ids:
            raise ResidentPublicationError(f"duplicate direct entity id {entity_id}")
        all_ids.add(entity_id)
        encounter_index = _direct_int(
            row["encounter_index"], f"entity {entity_id} encounter"
        )
        active = _direct_bool(row["active"], f"entity {entity_id} active")
        presence_mask = _direct_int(
            row["sparse_attribute_presence"], f"entity {entity_id} presence", minimum=0
        )
        known_entity_mask = (1 << len(_ENTITY_SPARSE_ATTRIBUTE_NAMES)) - 1
        if presence_mask & ~known_entity_mask:
            raise ResidentPublicationError(
                f"typed entity {entity_id} presence has unknown bits"
            )
        _validate_direct_entity_scalars(row, entity_id)
        _validate_direct_movement(row["movement_state"], entity_id)
        _validate_direct_combat(row["locked_combat_state"], entity_id)
        if (row["movement_state"] is None) != (row["locked_combat_state"] is None):
            raise ResidentPublicationError(
                f"resident entity {entity_id} has mismatched movement/combat topology"
            )
        _validate_direct_building(row, entity_id)
        _validate_direct_point(row["point_projectile_state"], entity_id)
        _validate_direct_spawn_projectile_recipe(row, resident, entity_id)
        _validate_direct_rolling(row["rolling_projectile_state"], entity_id)
        if row["rolling_projectile_state"] is not None:
            _validate_direct_rolling_recipe(
                row["rolling_projectile_state"], resident, entity_id
            )
        _validate_direct_area(row["area_effect_state"], entity_id)
        _validate_direct_character_birth(row["character_birth"], entity_id)
        if active:
            if encounter_index < 0:
                raise ResidentPublicationError(
                    "resident publication rejected changed encounter ordering"
                )
            while len(active_slots) <= encounter_index:
                active_slots.append(None)
            if active_slots[encounter_index] is not None:
                raise ResidentPublicationError(
                    "resident publication has duplicate encounter index"
                )
            active_slots[encounter_index] = entity_id
        if entity_id not in entity_registry:
            actual_birth_ids.add(entity_id)
        else:
            entity = entity_registry[entity_id]
            expected_type = f"{type(entity).__module__}.{type(entity).__qualname__}"
            if row["python_type"] != expected_type:
                raise ResidentPublicationError(
                    f"resident publication changed Python type for id {entity_id}"
                )
        point = row["point_projectile_state"]
        if point is not None:
            group_id = point["damage_group_id"]
            hit_ids = point["damage_group_hit_entity_ids"]
            if (group_id is None) != (hit_ids is None):
                raise ResidentPublicationError(
                    f"malformed direct projectile group {entity_id}"
                )
            if group_id is not None:
                snapshot = tuple(cast(list[int], hit_ids))
                previous = group_snapshots.setdefault(group_id, snapshot)
                if previous != snapshot:
                    raise ResidentPublicationError(
                        f"resident projectile group {group_id} members disagree on hit IDs"
                    )
                if active:
                    active_group_snapshots[group_id] = snapshot
        birth = row["character_birth"]
        if birth is not None:
            if row["card_name"] != birth["effective_name"]:
                raise ResidentPublicationError(
                    f"resident character {entity_id} birth name disagrees with entity row"
                )
            character_groups.setdefault((birth["kind"], birth["group_id"]), []).append(
                birth
            )
        entities.append(
            _DirectEntityPublication(
                row, entity_id, active, encounter_index, presence_mask
            )
        )

    expected_birth_ids = set(range(battle.next_entity_id, battle_row["next_entity_id"]))
    if actual_birth_ids != expected_birth_ids:
        raise ResidentPublicationError(
            "resident publication has a non-contiguous allocation range"
        )
    if not set(entity_registry).issubset(all_ids):
        raise ResidentPublicationError(
            "resident publication dropped an allocated entity"
        )
    if any(value is None for value in active_slots):
        raise ResidentPublicationError(
            "resident publication rejected changed encounter ordering"
        )
    active_entity_ids = tuple(cast(int, value) for value in active_slots)
    same_publication_births = {
        entity.entity_id: entity.raw
        for entity in entities
        if entity.entity_id in actual_birth_ids
    }

    for entity in entities:
        row = entity.raw
        if entity.entity_id in actual_birth_ids:
            point = row["point_projectile_state"]
            rolling = row["rolling_projectile_state"]
            area = row["area_effect_state"]
            character = row["character_birth"]
            if sum(
                value is not None for value in (point, rolling, area, character)
            ) != 1:
                raise ResidentPublicationError(
                    f"resident publication has unsupported birth recipe for id {entity.entity_id}"
                )
            expected_type = (
                (
                    "clasher.entities.SpawnProjectile"
                    if point is not None
                    and point["spawn_projectile_state"] is not None
                    else "clasher.entities.Projectile"
                )
                if point is not None
                else "clasher.entities.RollingProjectile"
                if rolling is not None
                else "clasher.entities.AreaEffect"
                if area is not None
                else _catalog_birth_type(row["entity_kind"])[1]
            )
            if row["python_type"] != expected_type:
                raise ResidentPublicationError(
                    f"resident publication birth type mismatch for id {entity.entity_id}"
                )
            if character is not None:
                _catalog_birth_type(row["entity_kind"])
        for reference in (
            row["target_id"],
            None
            if row["locked_combat_state"] is None
            else row["locked_combat_state"]["last_combat_target_id"],
            None
            if row["locked_combat_state"] is None
            else row["locked_combat_state"]["movement_target_id"],
            None
            if row["point_projectile_state"] is None
            else row["point_projectile_state"]["primary_target_id"],
            None
            if row["point_projectile_state"] is None
            else row["point_projectile_state"]["source_entity_id"],
            None
            if row["point_projectile_state"] is None
            else row["point_projectile_state"]["temporary_homing_target_id"],
            None
            if row["area_effect_state"] is None
            else row["area_effect_state"]["birth_source_entity_id"],
            None
            if row["status_nova_jump"] is None
            else row["status_nova_jump"]["jump_target_id"],
        ):
            if reference is not None and reference not in all_ids:
                raise ResidentPublicationError(
                    f"resident entity {entity.entity_id} has unknown reference {reference}"
                )
        rolling = row["rolling_projectile_state"]
        if rolling is not None and any(
            hit_id >= battle_row["next_entity_id"]
            for hit_id in rolling["hit_entity_ids"]
        ):
            raise ResidentPublicationError(
                f"resident rolling projectile {entity.entity_id} has unallocated hit ID"
            )

    for (kind, group_id), members in character_groups.items():
        count = members[0]["member_count"]
        ordinals = sorted(row["ordinal"] for row in members)
        common = {
            (
                row["effective_name"],
                row["template_fingerprint"],
                row["lookup_name"],
                row["source_entity_id"],
                row["opcode_index"],
                row["member_count"],
                row["unit_data_fingerprint"],
            )
            for row in members
        }
        if (
            count <= 0
            or ordinals != list(range(count))
            or kind != 0
            and len(common) != 1
        ):
            raise ResidentPublicationError(
                f"resident character group {group_id} has inconsistent provenance"
            )
        if kind == 0:
            lookup_names = {member["lookup_name"] for member in members}
            recipes = [
                resident.character_action_birth_recipe(
                    member["lookup_name"],
                    member["template_fingerprint"],
                    member["ordinal"],
                )
                for member in members
            ]
            formation_variants = {
                recipe.formation_variant
                for recipe in recipes
                if recipe is not None
            }
            if (
                len(lookup_names) != 1
                or len(formation_variants) != 1
                or any(
                    recipe is None
                    or recipe.kind != "catalog_action"
                    or recipe.effective_name != member["effective_name"]
                    or recipe.template_fingerprint != member["template_fingerprint"]
                    or recipe.member_count != count
                    for recipe, member in zip(recipes, members, strict=True)
                )
                or not resident.character_action_card_stats_are_current(
                    battle, members[0]["lookup_name"]
                )
            ):
                raise ResidentPublicationError(
                    "resident character has unknown catalog birth recipe"
                )
        elif kind == 1:
            source_id = members[0]["source_entity_id"]
            source = _direct_death_spawn_source(
                source_id,
                group_id,
                battle=battle,
                resident=resident,
                entity_registry=entity_registry,
                same_publication_births=same_publication_births,
            )
            recipe = resident.character_death_spawn_birth_recipe(
                members[0]["effective_name"], members[0]["template_fingerprint"]
            )
            if source is None or recipe is None or recipe.kind != "death_spawn":
                raise ResidentPublicationError(
                    "resident character has unknown death-spawn recipe"
                )
            opcodes = [
                mechanic
                for mechanic in source.mechanics
                if isinstance(mechanic, (DeathDamage, DeathSpawn, DeathAreaEffect))
            ]
            opcode_index = members[0]["opcode_index"]
            opcode = opcodes[opcode_index] if 0 <= opcode_index < len(opcodes) else None
            if (
                not isinstance(opcode, DeathSpawn)
                or str(opcode.unit_name) != members[0]["effective_name"]
                or int(opcode.count) != count
            ):
                raise ResidentPublicationError(
                    "resident death-spawn opcode provenance changed"
                )
            fingerprint = hashlib.sha256(
                json.dumps(
                    _normalize(opcode.unit_data), sort_keys=True, separators=(",", ":")
                ).encode("ascii")
            ).hexdigest()
            if (
                recipe.source_fingerprint != fingerprint
                or members[0]["unit_data_fingerprint"] != fingerprint
            ):
                raise ResidentPublicationError(
                    "resident death-spawn data provenance changed"
                )
        elif kind == 2:
            source_id = members[0]["source_entity_id"]
            source = entity_registry.get(source_id)
            recipe = resident.character_rolling_spawn_birth_recipe(
                members[0]["lookup_name"], members[0]["template_fingerprint"]
            )
            if (
                type(source) is not RollingProjectile
                or recipe is None
                or recipe.kind != "rolling_spawn"
                or recipe.effective_name != members[0]["effective_name"]
                or recipe.source_fingerprint
                != members[0]["unit_data_fingerprint"]
                or count != 1
            ):
                raise ResidentPublicationError(
                    "resident character has unknown rolling-spawn recipe"
                )
        else:
            source_id = members[0]["source_entity_id"]
            source = entity_registry.get(source_id)
            source_row = same_publication_births.get(source_id)
            if source is not None:
                source_spell = getattr(source, "spell_name", None)
                source_valid = type(source) is SpawnProjectile
            else:
                source_point = (
                    None if source_row is None else source_row["point_projectile_state"]
                )
                source_spell = None if source_point is None else source_point["source_kind"]
                source_valid = (
                    source_row is not None
                    and source_row["python_type"] == "clasher.entities.SpawnProjectile"
                    and source_point is not None
                    and source_point["spawn_projectile_state"] is not None
                )
            recipes = [
                resident.character_spawn_projectile_birth_recipe(
                    member["lookup_name"],
                    member["template_fingerprint"],
                    member["ordinal"],
                )
                for member in members
            ]
            if (
                not source_valid
                or source_spell != members[0]["lookup_name"]
                or any(
                    recipe is None
                    or recipe.kind != "spawn_projectile_spawn"
                    or recipe.effective_name != member["effective_name"]
                    or recipe.source_fingerprint != member["unit_data_fingerprint"]
                    or recipe.member_count != count
                    for recipe, member in zip(recipes, members, strict=True)
                )
            ):
                raise ResidentPublicationError(
                    "resident character has unknown spawn-projectile recipe"
                )

    rng = _direct_dict(root["rng"], "rng")
    _direct_int(rng["version"], "rng version")
    _direct_int(rng["index"], "rng index", minimum=0)
    words = _direct_list(rng["state"], "rng state")
    if any(type(word) is not int or not 0 <= word < 1 << 32 for word in words):
        raise ResidentPublicationError("malformed direct rng state")
    if rng["gauss_next"] is not None:
        _direct_exact(rng["gauss_next"], "rng gauss")

    pending = _validate_direct_pending(
        root["pending_spells"], battle=battle, resident=resident
    )

    projectile_groups: list[dict[str, Any]] = []
    group_rows: dict[int, tuple[int, ...]] = {}
    for value in _direct_list(root["projectile_groups"], "projectile groups"):
        group = _direct_dict(value, "projectile_group")
        group_id = _direct_int(group["id"], "projectile group id", minimum=0)
        hit_ids = _direct_list(group["hit_entity_ids"], "projectile group hit ids")
        if any(type(item) is not int or item < 0 for item in hit_ids) or len(
            set(hit_ids)
        ) != len(hit_ids):
            raise ResidentPublicationError(
                f"malformed direct projectile group {group_id}"
            )
        if group_id in group_rows:
            raise ResidentPublicationError(
                f"duplicate direct projectile group {group_id}"
            )
        group_rows[group_id] = tuple(hit_ids)
        projectile_groups.append(group)
    if group_rows != active_group_snapshots:
        raise ResidentPublicationError(
            "direct projectile group summary disagrees with entities"
        )

    return _DirectPublicationPlan(
        binding=binding,
        battle=battle_row,
        players=(players[0], players[1]),
        towers=tuple(towers),
        entities=tuple(entities),
        active_entity_ids=active_entity_ids,
        rng=rng,
        pending_spells=pending,
        projectile_groups=tuple(projectile_groups),
    )


def _validate_direct_binding(
    value: Any,
    *,
    battle: Any,
    entity_registry: dict[int, Any],
) -> dict[str, Any]:
    binding = _direct_dict(value, "binding")
    if binding["semantic_schema_version"] != RESIDENT_SEMANTIC_SCHEMA_VERSION:
        raise ResidentPublicationError("direct semantic schema changed")
    for field in (
        "lineage_id",
        "prior_node_id",
        "prior_epoch",
        "candidate_node_id",
        "candidate_epoch",
        "parent_node_id",
        "parent_epoch",
        "prior_next_entity_id",
        "checkpoint_schema_version",
        "checkpoint_generation",
        "catalog_schema_version",
    ):
        _direct_int(binding[field], f"binding {field}", minimum=0)
    prior_ids = _direct_list(binding["prior_entity_ids"], "prior entity IDs")
    if any(type(value) is not int or value < 0 for value in prior_ids):
        raise ResidentPublicationError(
            "typed publication prior entity IDs are malformed"
        )
    if tuple(entity_registry) != tuple(prior_ids):
        raise ResidentPublicationError(
            "typed publication registry disagrees with the authenticated prior"
        )
    if binding["prior_next_entity_id"] != battle.next_entity_id:
        raise ResidentPublicationError(
            "typed publication next-entity ID disagrees with the live prior"
        )
    if (
        binding["parent_node_id"] != binding["prior_node_id"]
        or binding["parent_epoch"] != binding["prior_epoch"]
    ):
        raise ResidentPublicationError("typed publication is not a direct child")
    if binding["checkpoint_schema_version"] != 2:
        raise ResidentPublicationError("typed publication checkpoint schema changed")
    if binding["catalog_schema_version"] != RESIDENT_CARD_CATALOG_SCHEMA_VERSION:
        raise ResidentPublicationError("typed publication catalog schema changed")
    for field in ("catalog_fingerprint", "catalog_source_fingerprint"):
        if not _valid_fingerprint(binding[field]):
            raise ResidentPublicationError(f"typed publication has malformed {field}")
    return binding


def _validate_direct_battle(value: Any) -> dict[str, Any]:
    row = _direct_dict(value, "battle")
    entity_bits = len(_ENTITY_SPARSE_ATTRIBUTE_NAMES)
    presence = _direct_int(
        row["sparse_attribute_presence"], "battle presence", minimum=0
    )
    known = sum(
        1 << (entity_bits + index)
        for index in range(len(_BATTLE_SPARSE_ATTRIBUTE_NAMES))
    )
    if presence & ~known:
        raise ResidentPublicationError("typed battle presence has unknown bits")
    for field in ("tick", "next_entity_id"):
        _direct_int(row[field], f"battle {field}", minimum=0)
    for field in ("time", "dt"):
        _direct_float(row[field], f"battle {field}")
    for field in (
        "double_elixir",
        "triple_elixir",
        "overtime",
        "game_over",
        "sudden_death",
        "win_conditions_dirty",
    ):
        _direct_bool(row[field], f"battle {field}")
    crowns = row["sudden_death_crowns"]
    if (
        type(crowns) is not tuple
        or len(crowns) != 2
        or any(type(item) is not int for item in crowns)
    ):
        raise ResidentPublicationError("malformed direct sudden-death crowns")
    if row["winner"] is not None and type(row["winner"]) is not int:
        raise ResidentPublicationError("malformed direct winner")
    return row


def _validate_direct_players(value: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    values = _direct_list(value, "players")
    if len(values) != 2:
        raise ResidentPublicationError("typed publication player count changed")
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(values):
        row = _direct_dict(item, "player")
        if _direct_int(row["player_id"], "player id") != index:
            raise ResidentPublicationError("typed publication player order changed")
        for field in ("elixir", "max_elixir"):
            _direct_float(row[field], f"player {index} {field}")
        for field in ("king_tower_hp", "left_tower_hp", "right_tower_hp"):
            _direct_exact(row[field], f"player {index} {field}")
        _direct_int(row["next_card_refill_cooldown_ms"], f"player {index} refill")
        hand = _direct_list(row["hand"], f"player {index} hand")
        if any(card is not None and type(card) is not str for card in hand):
            raise ResidentPublicationError(f"malformed direct player {index} hand")
        cycle = _direct_list(row["cycle_queue"], f"player {index} cycle queue")
        if any(type(card) is not str for card in cycle):
            raise ResidentPublicationError(
                f"malformed direct player {index} cycle queue"
            )
        rows.append(row)
    return rows[0], rows[1]


def _validate_direct_towers(value: Any) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for item in _direct_list(value, "towers"):
        row = _direct_dict(item, "tower")
        for field in ("id", "hp_milli", "player_id"):
            _direct_int(row[field], f"tower {field}")
        _direct_exact(row["hp"], "tower hp")
        _direct_float(row["last_attack_time"], "tower last attack")
        for field in ("active", "is_active", "is_alive"):
            _direct_bool(row[field], f"tower {field}")
        if type(row["slot"]) is not str:
            raise ResidentPublicationError("malformed direct tower slot")
        rows.append(row)
    return tuple(rows)


def _validate_direct_rng(value: Any) -> dict[str, Any]:
    row = _direct_dict(value, "rng")
    _direct_int(row["version"], "rng version")
    _direct_int(row["index"], "rng index", minimum=0)
    words = _direct_list(row["state"], "rng state")
    if (
        len(words) != 624
        or any(type(word) is not int or not 0 <= word < 1 << 32 for word in words)
        or row["index"] > 624
    ):
        raise ResidentPublicationError("malformed direct rng state")
    if row["gauss_next"] is not None:
        _direct_exact(row["gauss_next"], "rng gauss")
    return row


def _validate_direct_pending(
    value: Any,
    *,
    battle: Any,
    resident: ResidentRustBattle,
) -> dict[str, Any]:
    row = _direct_dict(value, "pending")
    next_sequence = _direct_int(
        row["next_sequence"], "pending next sequence", minimum=0
    )
    previous_sequence = -1
    for item in _direct_list(row["casts"], "pending casts"):
        cast_row = _direct_dict(item, "pending_cast")
        sequence = _direct_int(cast_row["sequence"], "pending sequence", minimum=0)
        execute_at = _direct_float(cast_row["execute_at"], "pending execute_at")
        position_x = _direct_float(cast_row["position_x"], "pending position_x")
        position_y = _direct_float(cast_row["position_y"], "pending position_y")
        player_id = _direct_int(cast_row["player_id"], "pending player id")
        spell_name = cast_row["spell_name"]
        if type(spell_name) is not str or not spell_name:
            raise ResidentPublicationError("malformed direct pending spell name")
        action_kind = resident.pending_spell_action_kind(spell_name)
        spawn_recipe = (
            resident.spawn_projectile_recipe(spell_name)
            if action_kind == "spawn_projectile_spell"
            else None
        )
        if action_kind not in {
            "projectile_spell",
            "rolling_projectile_spell",
            "spawn_projectile_spell",
            "direct_damage_spell",
        }:
            raise ResidentPublicationError(
                f"unsupported direct pending spell {spell_name!r}"
            )
        in_deploy_zone = any(
            x1 <= position_x < x2 and y1 <= position_y < y2
            for x1, y1, x2, y2 in battle.arena.get_deploy_zones(player_id, battle)
        )
        if (
            sequence <= previous_sequence
            or sequence >= next_sequence
            or not np.isfinite(execute_at)
            or not np.isfinite(position_x)
            or not np.isfinite(position_y)
            or not 0.0 <= position_x < float(battle.arena.width)
            or not 0.0 <= position_y < float(battle.arena.height)
            or (int(position_x), int(position_y)) in battle.arena.BLOCKED_TILES
            or player_id not in (0, 1)
            or action_kind == "rolling_projectile_spell"
            and not in_deploy_zone
            or action_kind == "spawn_projectile_spell"
            and (
                spawn_recipe is None
                or spawn_recipe.requires_territory
                and not in_deploy_zone
            )
        ):
            raise ResidentPublicationError("malformed direct pending spell state")
        previous_sequence = sequence
    return row


def _validate_direct_groups(value: Any) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    for item in _direct_list(value, "projectile groups"):
        row = _direct_dict(item, "projectile_group")
        group_id = _direct_int(row["id"], "projectile group id", minimum=0)
        hit_ids = _direct_list(row["hit_entity_ids"], "projectile group hit ids")
        if (
            group_id in seen
            or any(type(hit_id) is not int or hit_id < 0 for hit_id in hit_ids)
            or len(set(hit_ids)) != len(hit_ids)
        ):
            raise ResidentPublicationError(
                f"malformed direct projectile group {group_id}"
            )
        seen.add(group_id)
        rows.append(row)
    return tuple(rows)


def _validate_direct_full_delta_entity(
    value: Any,
    *,
    all_ids: set[int],
    next_entity_id: int,
    resident: ResidentRustBattle,
) -> _DirectEntityPublication:
    row = _direct_dict(value, "entity")
    entity_id = _direct_int(row["id"], "entity id", minimum=0)
    encounter = _direct_int(row["encounter_index"], f"entity {entity_id} encounter")
    active = _direct_bool(row["active"], f"entity {entity_id} active")
    presence = _direct_int(
        row["sparse_attribute_presence"], f"entity {entity_id} presence", minimum=0
    )
    if presence & ~((1 << len(_ENTITY_SPARSE_ATTRIBUTE_NAMES)) - 1):
        raise ResidentPublicationError(
            f"typed entity {entity_id} presence has unknown bits"
        )
    _validate_direct_entity_scalars(row, entity_id)
    _validate_direct_movement(row["movement_state"], entity_id)
    _validate_direct_combat(row["locked_combat_state"], entity_id)
    if (row["movement_state"] is None) != (row["locked_combat_state"] is None):
        raise ResidentPublicationError(
            f"resident entity {entity_id} has mismatched movement/combat topology"
        )
    _validate_direct_building(row, entity_id)
    _validate_direct_point(row["point_projectile_state"], entity_id)
    _validate_direct_spawn_projectile_recipe(row, resident, entity_id)
    _validate_direct_rolling(row["rolling_projectile_state"], entity_id)
    if row["rolling_projectile_state"] is not None:
        _validate_direct_rolling_recipe(
            row["rolling_projectile_state"], resident, entity_id
        )
    _validate_direct_area(row["area_effect_state"], entity_id)
    _validate_direct_character_birth(row["character_birth"], entity_id)
    point = row["point_projectile_state"]
    rolling = row["rolling_projectile_state"]
    area = row["area_effect_state"]
    character = row["character_birth"]
    if sum(item is not None for item in (point, rolling, area, character)) != 1:
        raise ResidentPublicationError(
            f"resident publication has unsupported birth recipe for id {entity_id}"
        )
    expected_type = (
        (
            "clasher.entities.SpawnProjectile"
            if point is not None and point["spawn_projectile_state"] is not None
            else "clasher.entities.Projectile"
        )
        if point is not None
        else "clasher.entities.RollingProjectile"
        if rolling is not None
        else "clasher.entities.AreaEffect"
        if area is not None
        else _catalog_birth_type(row["entity_kind"])[1]
    )
    if row["python_type"] != expected_type:
        raise ResidentPublicationError(
            f"resident publication birth type mismatch for id {entity_id}"
        )
    if character is not None and row["card_name"] != character["effective_name"]:
        raise ResidentPublicationError(
            f"resident character birth {entity_id} identity changed"
        )
    for reference in (
        row["target_id"],
        None
        if row["locked_combat_state"] is None
        else row["locked_combat_state"]["last_combat_target_id"],
        None
        if row["locked_combat_state"] is None
        else row["locked_combat_state"]["movement_target_id"],
        None if point is None else point["primary_target_id"],
        None if point is None else point["source_entity_id"],
        None if point is None else point["temporary_homing_target_id"],
        None if area is None else area["birth_source_entity_id"],
        None
        if row["status_nova_jump"] is None
        else row["status_nova_jump"]["jump_target_id"],
    ):
        if reference is not None and reference not in all_ids:
            raise ResidentPublicationError(
                f"resident entity {entity_id} has unknown reference {reference}"
            )
    if rolling is not None and any(
        hit_id >= next_entity_id for hit_id in rolling["hit_entity_ids"]
    ):
        raise ResidentPublicationError(
            f"resident rolling projectile {entity_id} has unallocated hit ID"
        )
    return _DirectEntityPublication(row, entity_id, active, encounter, presence)


def _validate_direct_changed_references(
    entity_id: int,
    raw: dict[str, Any],
    mask: int,
    all_ids: set[int],
    next_entity_id: int,
) -> None:
    references: list[int | None] = []
    if mask & _ENTITY_DELTA_BASE:
        references.append(raw["base"]["target_id"])
        status_nova = raw["base"]["status_nova_jump"]
        if status_nova is not None:
            references.append(status_nova["jump_target_id"])
    if mask & _ENTITY_DELTA_COMBAT and raw["locked_combat_state"] is not None:
        state = raw["locked_combat_state"]
        references.extend(
            (state["last_combat_target_id"], state["movement_target_id"])
        )
    if mask & _ENTITY_DELTA_POINT and raw["point_projectile_state"] is not None:
        state = raw["point_projectile_state"]
        references.extend(
            (
                state["primary_target_id"],
                state["source_entity_id"],
                state["temporary_homing_target_id"],
            )
        )
    if mask & _ENTITY_DELTA_ROLLING and raw["rolling_projectile_state"] is not None:
        state = raw["rolling_projectile_state"]
        if any(hit_id >= next_entity_id for hit_id in state["hit_entity_ids"]):
            raise ResidentPublicationError(
                f"resident rolling projectile {entity_id} has unallocated hit ID"
            )
    if mask & _ENTITY_DELTA_AREA and raw["area_effect_state"] is not None:
        references.append(raw["area_effect_state"]["birth_source_entity_id"])
    for reference in references:
        if reference is not None and reference not in all_ids:
            raise ResidentPublicationError(
                f"resident entity {entity_id} has unknown reference {reference}"
            )


def _build_direct_delta_publication_plan(
    raw: Any,
    *,
    battle: Any,
    resident: ResidentRustBattle,
    entity_registry: dict[int, Any],
) -> _DirectDeltaPublicationPlan:
    root = _direct_dict(raw, "delta_root")
    if _direct_int(root["version"], "publication delta version") != 1:
        raise ResidentPublicationError("unsupported direct publication delta version")
    binding = _validate_direct_binding(
        root["binding"], battle=battle, entity_registry=entity_registry
    )
    dirty_mask = _direct_int(root["dirty_mask"], "delta dirty mask", minimum=0)
    if dirty_mask & ~_DELTA_ROOT_MASK:
        raise ResidentPublicationError("direct publication delta has unknown root bits")
    prior_ids = tuple(binding["prior_entity_ids"])
    next_entity_id = _direct_int(
        root["next_entity_id"], "delta next entity id", minimum=0
    )
    if next_entity_id < binding["prior_next_entity_id"]:
        raise ResidentPublicationError("direct publication delta next id regressed")
    all_ids_raw = _direct_list(root["all_entity_ids"], "delta all entity ids")
    if (
        any(type(value) is not int or value < 0 for value in all_ids_raw)
        or len(set(all_ids_raw)) != len(all_ids_raw)
        or tuple(all_ids_raw[: len(prior_ids)]) != prior_ids
        or all_ids_raw[len(prior_ids) :]
        != list(range(binding["prior_next_entity_id"], next_entity_id))
    ):
        raise ResidentPublicationError("direct publication delta allocation is malformed")
    all_entity_ids = tuple(all_ids_raw)
    all_ids = set(all_entity_ids)
    active_raw = _direct_list(root["active_entity_ids"], "delta active entity ids")
    if (
        any(type(value) is not int or value not in all_ids for value in active_raw)
        or len(set(active_raw)) != len(active_raw)
    ):
        raise ResidentPublicationError("direct publication delta active order is malformed")
    active_entity_ids = tuple(active_raw)

    root_sections = (
        (_DELTA_BATTLE, "battle"),
        (_DELTA_PLAYERS, "players"),
        (_DELTA_TOWERS, "towers"),
        (_DELTA_RNG, "rng"),
        (_DELTA_PENDING, "pending_spells"),
        (_DELTA_GROUPS, "projectile_groups"),
    )
    for bit, field in root_sections:
        if bool(dirty_mask & bit) != (root[field] is not None):
            raise ResidentPublicationError(
                f"direct publication delta {field} payload disagrees with mask"
            )
    if bool(dirty_mask & _DELTA_BATTLE) != (type(root["idle_eligible"]) is bool):
        raise ResidentPublicationError(
            "direct publication delta idle eligibility disagrees with mask"
        )
    battle_row = (
        _validate_direct_battle(root["battle"])
        if dirty_mask & _DELTA_BATTLE
        else None
    )
    if (
        next_entity_id != binding["prior_next_entity_id"]
        and not dirty_mask & _DELTA_BATTLE
    ):
        raise ResidentPublicationError(
            "direct publication delta changed next id without battle payload"
        )
    if battle_row is not None and battle_row["next_entity_id"] != next_entity_id:
        raise ResidentPublicationError("direct publication delta next id disagrees")
    players = (
        _validate_direct_players(root["players"])
        if dirty_mask & _DELTA_PLAYERS
        else None
    )
    towers = (
        _validate_direct_towers(root["towers"])
        if dirty_mask & _DELTA_TOWERS
        else None
    )
    if towers is not None and any(
        tower["active"] and tower["id"] not in all_ids for tower in towers
    ):
        raise ResidentPublicationError("direct publication delta has unknown tower")
    rng = _validate_direct_rng(root["rng"]) if dirty_mask & _DELTA_RNG else None
    pending = (
        _validate_direct_pending(
            root["pending_spells"], battle=battle, resident=resident
        )
        if dirty_mask & _DELTA_PENDING
        else None
    )
    groups = (
        _validate_direct_groups(root["projectile_groups"])
        if dirty_mask & _DELTA_GROUPS
        else None
    )

    changes: list[_DirectDeltaEntityPublication] = []
    seen: set[int] = set()
    full_births: list[_DirectEntityPublication] = []
    for item in _direct_list(root["entities"], "delta entities"):
        change = _direct_dict(item, "delta_entity")
        entity_id = _direct_int(change["id"], "delta entity id", minimum=0)
        mask = _direct_int(change["dirty_mask"], f"entity {entity_id} dirty mask")
        if mask <= 0 or mask & ~_ENTITY_DELTA_MASK or entity_id in seen:
            raise ResidentPublicationError(f"malformed direct entity delta {entity_id}")
        seen.add(entity_id)
        if entity_id not in all_ids:
            raise ResidentPublicationError(f"unknown direct entity delta {entity_id}")
        full: _DirectEntityPublication | None = None
        if mask & _ENTITY_DELTA_FULL:
            if mask != _ENTITY_DELTA_FULL or entity_id in entity_registry:
                raise ResidentPublicationError(
                    f"malformed direct full entity delta {entity_id}"
                )
            full = _validate_direct_full_delta_entity(
                change["full"],
                all_ids=all_ids,
                next_entity_id=next_entity_id,
                resident=resident,
            )
            if full.entity_id != entity_id:
                raise ResidentPublicationError(
                    f"direct full entity delta {entity_id} changed identity"
                )
            for field in _DIRECT_KEYS["delta_entity"] - {"id", "dirty_mask", "full"}:
                value = change[field]
                if type(value) is bool:
                    if value:
                        raise ResidentPublicationError(
                            f"direct full entity delta {entity_id} has prefix payload"
                        )
                elif value is not None:
                    raise ResidentPublicationError(
                        f"direct full entity delta {entity_id} has prefix payload"
                    )
            full_births.append(full)
            changes.append(
                _DirectDeltaEntityPublication(
                    change, entity_id, mask, full.presence_mask, full
                )
            )
            continue
        if entity_id not in entity_registry or change["full"] is not None:
            raise ResidentPublicationError(
                f"malformed direct prefix entity delta {entity_id}"
            )
        python_entity = entity_registry[entity_id]
        sparse = change["sparse_attribute_presence"]
        if bool(mask & _ENTITY_DELTA_PRESENCE) != (sparse is not None):
            raise ResidentPublicationError(
                f"direct entity {entity_id} presence disagrees with mask"
            )
        if sparse is not None:
            presence = _direct_int(sparse, f"entity {entity_id} presence", minimum=0)
            if presence & ~((1 << len(_ENTITY_SPARSE_ATTRIBUTE_NAMES)) - 1):
                raise ResidentPublicationError(
                    f"typed entity {entity_id} presence has unknown bits"
                )
        base = change["base"]
        if bool(mask & _ENTITY_DELTA_BASE) != (base is not None):
            raise ResidentPublicationError(
                f"direct entity {entity_id} base disagrees with mask"
            )
        if base is not None:
            base_row = _direct_dict(base, "delta_base")
            for field in ("position_x", "position_y", "hitpoints", "max_hitpoints", "damage"):
                _direct_exact(base_row[field], f"entity {entity_id}.{field}")
            for field in (
                "deploy_delay_remaining",
                "placement_delay_total",
                "freeze_expiry_time",
            ):
                _direct_float(base_row[field], f"entity {entity_id}.{field}")
            for field in (
                "active",
                "is_alive",
                "placement_pending",
                "spawn_hook_pending",
                "spawn_hook_fired",
            ):
                _direct_bool(base_row[field], f"entity {entity_id}.{field}")
            for field in (
                "encounter_index",
                "death_spawn_target_immunity_elapsed_ms",
                "pending_projectile_max_duration_ms",
            ):
                _direct_int(base_row[field], f"entity {entity_id}.{field}")
            _direct_optional_int(base_row["target_id"], f"entity {entity_id}.target_id")
            _validate_direct_status_nova_jump(
                base_row["status_nova_jump"], entity_id
            )
        if bool(mask & _ENTITY_DELTA_SHIELDS) != (
            type(change["shields"]) is list
            and type(change["shield_break_count"]) is int
        ):
            raise ResidentPublicationError(
                f"direct entity {entity_id} shields disagree with mask"
            )
        if mask & _ENTITY_DELTA_SHIELDS:
            shield_mechanics = [
                mechanic
                for mechanic in python_entity.mechanics
                if f"{type(mechanic).__module__}.{type(mechanic).__qualname__}"
                == "clasher.mechanics.shared.shield.Shield"
            ]
            if len(shield_mechanics) != len(change["shields"]):
                raise ResidentPublicationError(
                    f"resident entity {entity_id} shield topology changed"
                )
            for item, mechanic in zip(
                change["shields"], shield_mechanics, strict=True
            ):
                shield = _direct_dict(item, "shield")
                _direct_exact(shield["current"], f"entity {entity_id} shield current")
                if not _direct_exact_matches(
                    shield["maximum"],
                    mechanic.max_shield,
                    f"entity {entity_id} shield maximum",
                ):
                    raise ResidentPublicationError(
                        f"resident entity {entity_id} shield maximum changed"
                    )
        optional = (
            (_ENTITY_DELTA_MODIFIER, "modifier_state", "modifier_present", _validate_direct_modifier),
            (_ENTITY_DELTA_MOVEMENT, "movement_state", "movement_present", _validate_direct_movement),
            (_ENTITY_DELTA_COMBAT, "locked_combat_state", "locked_combat_present", _validate_direct_combat),
            (_ENTITY_DELTA_POINT, "point_projectile_state", "point_projectile_present", _validate_direct_point),
            (_ENTITY_DELTA_ROLLING, "rolling_projectile_state", "rolling_projectile_present", _validate_direct_rolling),
            (_ENTITY_DELTA_AREA, "area_effect_state", "area_effect_present", _validate_direct_area),
        )
        for bit, field, present_field, validator in optional:
            present = _direct_bool(change[present_field], f"entity {entity_id} {present_field}")
            payload = change[field]
            if not mask & bit:
                if present or payload is not None:
                    raise ResidentPublicationError(
                        f"direct entity {entity_id} {field} disagrees with mask"
                    )
            elif present != (payload is not None):
                raise ResidentPublicationError(
                    f"direct entity {entity_id} {field} disagrees with presence"
                )
            elif payload is not None:
                validator(payload, entity_id)
            if bit == _ENTITY_DELTA_ROLLING and payload is not None:
                _validate_direct_rolling_recipe(payload, resident, entity_id)
            expected_present = (
                getattr(python_entity, "entity_kind", -1) in (0, 1)
                if bit
                in (
                    _ENTITY_DELTA_MODIFIER,
                    _ENTITY_DELTA_MOVEMENT,
                    _ENTITY_DELTA_COMBAT,
                )
                else type(python_entity) in (Projectile, SpawnProjectile)
                if bit == _ENTITY_DELTA_POINT
                else type(python_entity) is RollingProjectile
                if bit == _ENTITY_DELTA_ROLLING
                else type(python_entity) is AreaEffect
            )
            if mask & bit and present is not expected_present:
                raise ResidentPublicationError(
                    f"direct entity {entity_id} {field} topology changed"
                )
            if bit == _ENTITY_DELTA_POINT and payload is not None:
                expected_point_type = (
                    SpawnProjectile
                    if payload["spawn_projectile_state"] is not None
                    else Projectile
                )
                if type(python_entity) is not expected_point_type:
                    raise ResidentPublicationError(
                        f"direct entity {entity_id} point projectile type changed"
                    )
        if mask & _ENTITY_DELTA_POINT and change["point_projectile_state"] is not None:
            damage = (
                _direct_exact(base["damage"], f"entity {entity_id} damage")
                if base is not None
                else python_entity.damage
            )
            _validate_direct_spawn_projectile_state(
                change["point_projectile_state"],
                damage,
                int(python_entity.player_id),
                resident,
                entity_id,
            )
        for bit, field, present_field in (
            (_ENTITY_DELTA_BUILDING_LIFETIME, "building_lifetime_state", "building_lifetime_present"),
            (_ENTITY_DELTA_BUILDING_IMPACT, "building_impact_state", "building_impact_present"),
        ):
            present = _direct_bool(change[present_field], f"entity {entity_id} {present_field}")
            payload = change[field]
            if not mask & bit:
                if present or payload is not None:
                    raise ResidentPublicationError(
                        f"direct entity {entity_id} {field} disagrees with mask"
                    )
            elif present != (payload is not None):
                raise ResidentPublicationError(
                    f"direct entity {entity_id} {field} disagrees with presence"
                )
            elif payload is not None:
                schema = "building_lifetime" if bit == _ENTITY_DELTA_BUILDING_LIFETIME else "building_impact"
                parsed = _direct_dict(payload, schema)
                if bit == _ENTITY_DELTA_BUILDING_LIFETIME:
                    _direct_int(parsed["decay_work"], f"entity {entity_id} lifetime work")
                    if parsed["lifetime_ms"] is not None:
                        _direct_int(parsed["lifetime_ms"], f"entity {entity_id} lifetime ms")
                    _direct_float(parsed["lifetime_elapsed"], f"entity {entity_id} lifetime elapsed")
                    _direct_float(parsed["tick_carry_ms"], f"entity {entity_id} lifetime carry")
                else:
                    for name in (
                        "activation_delay_remaining",
                        "activation_delay_seconds",
                        "activation_first_hit_delay_remaining",
                        "activation_first_hit_delay_seconds",
                        "collision_radius",
                    ):
                        _direct_float(parsed[name], f"entity {entity_id} building {name}")
                    _direct_int(parsed["stealth_until_ms"], f"entity {entity_id} building stealth")
                    for name in (
                        "allow_area_damage_when_invisible",
                        "is_king_tower",
                        "requires_activation",
                        "tower_active",
                    ):
                        _direct_bool(parsed[name], f"entity {entity_id} building {name}")
                    if parsed["crown_slot"] is not None and type(parsed["crown_slot"]) is not str:
                        raise ResidentPublicationError(
                            f"malformed direct entity {entity_id} crown slot"
                        )
            expected_present = getattr(python_entity, "entity_kind", -1) == 1
            if mask & bit and present is not expected_present:
                raise ResidentPublicationError(
                    f"direct entity {entity_id} {field} topology changed"
                )
        _validate_direct_changed_references(
            entity_id,
            change,
            mask,
            all_ids,
            next_entity_id,
        )
        if sparse is None:
            entity_fields = vars(entity_registry[entity_id])
            presence = sum(
                1 << index
                for index, field in enumerate(_ENTITY_SPARSE_ATTRIBUTE_NAMES)
                if field in entity_fields
            )
        changes.append(
            _DirectDeltaEntityPublication(change, entity_id, mask, presence, None)
        )

    expected_birth_ids = set(range(binding["prior_next_entity_id"], next_entity_id))
    if {item.entity_id for item in full_births} != expected_birth_ids:
        raise ResidentPublicationError("direct publication delta births are incomplete")
    if set(seen) - set(all_entity_ids):
        raise ResidentPublicationError("direct publication delta has unknown entities")

    active_slots: list[int | None] = [None] * len(active_entity_ids)
    changed_by_id = {item.entity_id: item for item in changes}
    for entity_id in all_entity_ids:
        candidate_change = changed_by_id.get(entity_id)
        if candidate_change is not None and candidate_change.full is not None:
            active = candidate_change.full.active
            encounter = candidate_change.full.encounter_index
        elif (
            candidate_change is not None
            and candidate_change.dirty_mask & _ENTITY_DELTA_BASE
        ):
            active = candidate_change.raw["base"]["active"]
            encounter = candidate_change.raw["base"]["encounter_index"]
        else:
            active = entity_id in battle.entities
            encounter = list(battle.entities).index(entity_id) if active else -1
        if active:
            if encounter < 0 or encounter >= len(active_slots) or active_slots[encounter] is not None:
                raise ResidentPublicationError("direct publication delta encounter order is malformed")
            active_slots[encounter] = entity_id
    if tuple(active_slots) != active_entity_ids:
        raise ResidentPublicationError("direct publication delta active order disagrees")

    same_publication_births = {
        item.entity_id: item.raw for item in full_births
    }

    character_groups: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for item in full_births:
        birth = item.raw["character_birth"]
        if birth is not None:
            character_groups.setdefault((birth["kind"], birth["group_id"]), []).append(birth)
    for (kind, group_id), members in character_groups.items():
        count = members[0]["member_count"]
        if sorted(member["ordinal"] for member in members) != list(range(count)):
            raise ResidentPublicationError(
                f"resident character group {group_id} has inconsistent provenance"
            )
        common = {
            (
                member["effective_name"], member["template_fingerprint"],
                member["lookup_name"], member["source_entity_id"],
                member["opcode_index"], member["member_count"],
                member["unit_data_fingerprint"],
            )
            for member in members
        }
        if kind != 0 and len(common) != 1:
            raise ResidentPublicationError(
                f"resident character group {group_id} has inconsistent provenance"
            )
        if kind == 0:
            lookup_names = {member["lookup_name"] for member in members}
            recipes = [
                resident.character_action_birth_recipe(
                    member["lookup_name"],
                    member["template_fingerprint"],
                    member["ordinal"],
                )
                for member in members
            ]
            formation_variants = {
                recipe.formation_variant
                for recipe in recipes
                if recipe is not None
            }
            if (
                len(lookup_names) != 1
                or len(formation_variants) != 1
                or any(
                    recipe is None
                    or recipe.kind != "catalog_action"
                    or recipe.effective_name != member["effective_name"]
                    or recipe.template_fingerprint != member["template_fingerprint"]
                    or recipe.member_count != count
                    for recipe, member in zip(recipes, members, strict=True)
                )
                or not resident.character_action_card_stats_are_current(
                    battle, members[0]["lookup_name"]
                )
            ):
                raise ResidentPublicationError(
                    "resident character has unknown catalog birth recipe"
                )
        elif kind == 1:
            source = _direct_death_spawn_source(
                members[0]["source_entity_id"],
                group_id,
                battle=battle,
                resident=resident,
                entity_registry=entity_registry,
                same_publication_births=same_publication_births,
            )
            recipe = resident.character_death_spawn_birth_recipe(
                members[0]["effective_name"], members[0]["template_fingerprint"]
            )
            if source is None or recipe is None or recipe.kind != "death_spawn":
                raise ResidentPublicationError(
                    "resident character has unknown death-spawn recipe"
                )
            opcodes = [
                mechanic for mechanic in source.mechanics
                if isinstance(mechanic, (DeathDamage, DeathSpawn, DeathAreaEffect))
            ]
            index = members[0]["opcode_index"]
            opcode = opcodes[index] if 0 <= index < len(opcodes) else None
            if (
                not isinstance(opcode, DeathSpawn)
                or str(opcode.unit_name) != members[0]["effective_name"]
                or int(opcode.count) != count
            ):
                raise ResidentPublicationError(
                    "resident death-spawn opcode provenance changed"
                )
            fingerprint = hashlib.sha256(
                json.dumps(_normalize(opcode.unit_data), sort_keys=True, separators=(",", ":")).encode("ascii")
            ).hexdigest()
            if (
                recipe.source_fingerprint != fingerprint
                or members[0]["unit_data_fingerprint"] != fingerprint
            ):
                raise ResidentPublicationError(
                    "resident death-spawn data provenance changed"
                )
        elif kind == 2:
            source = entity_registry.get(members[0]["source_entity_id"])
            recipe = resident.character_rolling_spawn_birth_recipe(
                members[0]["lookup_name"], members[0]["template_fingerprint"]
            )
            if (
                type(source) is not RollingProjectile
                or recipe is None
                or recipe.kind != "rolling_spawn"
                or recipe.effective_name != members[0]["effective_name"]
                or recipe.source_fingerprint
                != members[0]["unit_data_fingerprint"]
                or count != 1
            ):
                raise ResidentPublicationError(
                    "resident character has unknown rolling-spawn recipe"
                )
        else:
            source_id = members[0]["source_entity_id"]
            source = entity_registry.get(source_id)
            source_row = same_publication_births.get(source_id)
            if source is not None:
                source_spell = getattr(source, "spell_name", None)
                source_valid = type(source) is SpawnProjectile
            else:
                source_point = (
                    None if source_row is None else source_row["point_projectile_state"]
                )
                source_spell = None if source_point is None else source_point["source_kind"]
                source_valid = (
                    source_row is not None
                    and source_row["python_type"] == "clasher.entities.SpawnProjectile"
                    and source_point is not None
                    and source_point["spawn_projectile_state"] is not None
                )
            recipes = [
                resident.character_spawn_projectile_birth_recipe(
                    member["lookup_name"],
                    member["template_fingerprint"],
                    member["ordinal"],
                )
                for member in members
            ]
            if (
                not source_valid
                or source_spell != members[0]["lookup_name"]
                or any(
                    recipe is None
                    or recipe.kind != "spawn_projectile_spawn"
                    or recipe.effective_name != member["effective_name"]
                    or recipe.source_fingerprint != member["unit_data_fingerprint"]
                    or recipe.member_count != count
                    for recipe, member in zip(recipes, members, strict=True)
                )
            ):
                raise ResidentPublicationError(
                    "resident character has unknown spawn-projectile recipe"
                )

    topology_dirty = tuple(battle.entities) != active_entity_ids or bool(full_births)
    cache_dirty = topology_dirty or any(
        item.dirty_mask
        & (
            _ENTITY_DELTA_BASE
            | _ENTITY_DELTA_MOVEMENT
            | _ENTITY_DELTA_COMBAT
            | _ENTITY_DELTA_BUILDING_IMPACT
            | _ENTITY_DELTA_FULL
        )
        for item in changes
    )
    entity_offset = len(_ENTITY_SPARSE_ATTRIBUTE_NAMES)
    battle_presence_mask = (
        battle_row["sparse_attribute_presence"]
        if battle_row is not None
        else sum(
            1 << (entity_offset + index)
            for index, field in enumerate(_BATTLE_SPARSE_ATTRIBUTE_NAMES)
            if field in vars(battle)
        )
    )
    return _DirectDeltaPublicationPlan(
        binding=binding,
        dirty_mask=dirty_mask,
        battle=battle_row,
        idle_eligible=root["idle_eligible"] if dirty_mask & _DELTA_BATTLE else None,
        players=players,
        towers=towers,
        entities=tuple(changes),
        all_entity_ids=all_entity_ids,
        active_entity_ids=active_entity_ids,
        next_entity_id=next_entity_id,
        rng=rng,
        pending_spells=pending,
        projectile_groups=groups,
        battle_presence_mask=battle_presence_mask,
        cache_dirty=cache_dirty,
        topology_dirty=topology_dirty,
    )


def _typed_modifier(row: Any, entity: Any) -> dict[str, Any] | None:
    state = entity["modifier_state"]
    if state is None:
        return None
    effects = lambda values: [
        [
            _exact_float(effect["remaining"]),
            _exact_float(effect["movement"]),
            _exact_float(effect["attack"]),
            _exact_float(effect["spawn"]),
        ]
        for effect in values
    ]
    return {
        "attack_speed_buff_multiplier": _exact_float(
            state["attack_speed_buff_multiplier"]
        ),
        "attack_speed_debuff_multiplier": _exact_float(
            state["attack_speed_debuff_multiplier"]
        ),
        "encounter_index": row["encounter_index"],
        "haste_effects": effects(state["haste_effects"]),
        "haste_timer": _exact_float(state["haste_timer"]),
        "id": row["id"],
        "movement_mode_multiplier": _exact_float(state["movement_mode_multiplier"]),
        "movement_speed_buff_multiplier": _exact_float(
            state["movement_speed_buff_multiplier"]
        ),
        "original_speed": (
            None
            if state["original_speed"] is None
            else _exact_float(state["original_speed"])
        ),
        "slow_effects": effects(state["slow_effects"]),
        "slow_multiplier": _exact_float(state["slow_multiplier"]),
        "slow_timer": _exact_float(state["slow_timer"]),
        "spawn_speed_buff_multiplier": _exact_float(
            state["spawn_speed_buff_multiplier"]
        ),
        "spawn_speed_debuff_multiplier": _exact_float(
            state["spawn_speed_debuff_multiplier"]
        ),
        "speed": _exact(state["speed"]),
        "stun_timer": _exact_float(state["stun_timer"]),
    }


def _typed_shields(row: dict[str, Any], entity: Any) -> dict[str, Any] | None:
    shields = entity["shields"]
    if not shields:
        return None
    return {
        "encounter_index": row["encounter_index"],
        "id": row["id"],
        "shield_break_count": entity["shield_break_count"],
        "shields": [
            {
                "current_shield": _exact(shield["current"]),
                "max_shield": _exact(shield["maximum"]),
            }
            for shield in shields
        ],
    }


def _typed_death_opcodes(row: dict[str, Any], entity: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for opcode_index, opcode in enumerate(entity["death_opcodes"]):
        kind = opcode["kind"]
        common = {
            "encounter_index": row["encounter_index"],
            "id": row["id"],
            "opcode_index": opcode_index,
        }
        if kind == 0:
            state = opcode["damage"]
            if (
                state is None
                or opcode["spawn"] is not None
                or opcode["area"] is not None
            ):
                raise ResidentPublicationError("malformed typed death-damage opcode")
            result.append(
                {
                    **common,
                    "base_damage": state["base_damage"],
                    "hits_air": state["hits_air"],
                    "hits_ground": state["hits_ground"],
                    "knockback_distance": _exact(state["knockback_distance"]),
                    "knockback_units": state["knockback_units"],
                    "opcode_type": "damage",
                    "radius_tiles": _exact(state["radius_tiles"]),
                    "radius_units": state["radius_units"],
                    "scaled_damage": _exact(state["scaled_damage"]),
                }
            )
        elif kind == 1:
            state = opcode["spawn"]
            if (
                state is None
                or opcode["damage"] is not None
                or opcode["area"] is not None
            ):
                raise ResidentPublicationError("malformed typed death-spawn opcode")
            result.append(
                {
                    **common,
                    "count": state["count"],
                    "deploy_time_ms": state["deploy_time_ms"],
                    "min_radius_tiles": _exact_float(state["min_radius_tiles"]),
                    "opcode_type": "spawn",
                    "radial_pushback": state["radial_pushback"],
                    "radius_tiles": _exact_float(state["radius_tiles"]),
                    "spawn_const_priority": state["spawn_const_priority"],
                    "unit_data_sha256": state["unit_data_fingerprint"],
                    "unit_name": state["unit_name"],
                }
            )
        elif kind == 2:
            state = opcode["area"]
            if (
                state is None
                or opcode["damage"] is not None
                or opcode["spawn"] is not None
            ):
                raise ResidentPublicationError("malformed typed death-area opcode")
            result.append(
                {
                    **common,
                    "affects_hidden": state["affects_hidden"],
                    "area_name": state["area_name"],
                    "attack_multiplier": _exact_float(state["attack_multiplier"]),
                    "cap_buff_time_to_effect": state["cap_buff_time_to_effect"],
                    "duration": _exact_float(state["duration"]),
                    "effect_tick_interval": _exact_float(state["effect_tick_interval"]),
                    "hits_air": state["hits_air"],
                    "hits_ground": state["hits_ground"],
                    "movement_multiplier": _exact_float(state["movement_multiplier"]),
                    "opcode_type": "area",
                    "radius_tiles": _exact_float(state["radius_tiles"]),
                    "radius_units": state["radius_units"],
                    "refresh_duration": _exact_float(state["refresh_duration"]),
                    "spawn_multiplier": _exact_float(state["spawn_multiplier"]),
                }
            )
        else:
            raise ResidentPublicationError(f"unknown typed death opcode {kind!r}")
    return result


def _typed_movement(row: dict[str, Any], entity: Any) -> dict[str, Any] | None:
    state = entity["movement_state"]
    combat = entity["locked_combat_state"]
    if state is None:
        return None
    route_names = ("absent", "single", "ground", "unsupported")
    route_kind = state["route_cache_kind"]
    if type(route_kind) is not int or not 0 <= route_kind < len(route_names):
        raise ResidentPublicationError("malformed typed route kind")
    result = {
        "airborne_for_projectile": bool(
            combat is not None and combat["is_airborne_for_projectile"]
        ),
        "building_pathing_radius": _exact_float(state["building_pathing_radius"]),
        "death_spawn_travel_target": _optional_exact_position(
            state["death_spawn_travel_target"], exact=False
        ),
        "death_spawn_travel_ticks": state["death_spawn_travel_ticks"],
        "encounter_index": row["encounter_index"],
        "facing_x_units": 0 if combat is None else combat["facing_x_units"],
        "facing_y_units": 0 if combat is None else combat["facing_y_units"],
        "forced_movement_active": state["forced_movement_active"],
        "ground_path_backwards": bool(
            combat is not None and combat["ground_path_backwards"]
        ),
        "id": row["id"],
        "jump_speed": _exact_float(state["jump_speed"]),
        "knockback_immune": state["knockback_immune"],
        "knockback_interrupts_combat": state["knockback_interrupts_combat"],
        "knockback_target": _optional_exact_position(
            state["knockback_target"], exact=False
        ),
        "knockback_velocity_work": state["knockback_velocity_work"],
        "movement_phase_elapsed_ms": state["movement_phase_elapsed_ms"],
        "native_avoidance": state["native_avoidance"],
        "native_lane_id": state["native_lane_id"],
        "native_natural_movement_active": state["native_natural_movement_active"],
        "pending_consumed": state["pending_consumed"],
        "pending_x": _exact_float(state["pending_x"]),
        "pending_y": _exact_float(state["pending_y"]),
        "position_x": _exact(entity["position_x"]),
        "position_y": _exact(entity["position_y"]),
        "route_backwards": state["route_backwards"],
        "route_cells": [list(cell) for cell in state["route_cells"]],
        "route_goal": None
        if state["route_goal"] is None
        else list(state["route_goal"]),
        "route_jump_height": state["route_jump_height"],
        "route_kind": route_names[route_kind],
        "route_lane_id": state["route_lane_id"],
        "river_jump_active": state["river_jump_active"],
        "river_jump_blocked": state["river_jump_blocked"],
        "river_jump_duration": _exact_float(state["river_jump_duration"]),
        "river_jump_elapsed": _exact_float(state["river_jump_elapsed"]),
        "river_jump_origin": _optional_exact_position(
            state["river_jump_origin"], exact=True
        ),
        "river_jump_target": _optional_exact_position(
            state["river_jump_target"], exact=False
        ),
        "serialized_speed": _exact_float(state["serialized_speed"]),
        "special_move_active": state["special_move_active"],
        "special_move_consumed_tick": state["special_move_consumed_tick"],
        "stop_movement_after_ms": _exact_float(state["stop_movement_after_ms"]),
        "stun_interrupt_deferred_until_landing": state[
            "stun_interrupt_deferred_until_landing"
        ],
        "vector_bypasses_cap": state["vector_bypasses_cap"],
        "vector_count": state["vector_count"],
        "vector_x_units": state["vector_x_units"],
        "vector_y_units": state["vector_y_units"],
        "wait_ms": _exact_float(state["wait_ms"]),
    }
    status_nova = entity["status_nova_jump"]
    if status_nova is not None:
        result.update(
            {
                "status_nova_affects_hidden": status_nova["affects_hidden"],
                "status_nova_detonated": status_nova["detonated"],
                "status_nova_freeze_duration_ms": status_nova[
                    "freeze_duration_ms"
                ],
                "status_nova_freeze_radius_units": status_nova[
                    "freeze_radius_units"
                ],
                "status_nova_hits_air": status_nova["hits_air"],
                "status_nova_hits_ground": status_nova["hits_ground"],
                "status_nova_hop_duration_ms": status_nova["hop_duration_ms"],
                "status_nova_jump_destination": _optional_exact_position(
                    status_nova["jump_destination"], exact=True
                ),
                "status_nova_jump_origin": _optional_exact_position(
                    status_nova["jump_origin"], exact=True
                ),
                "status_nova_jump_speed_units_per_tick": status_nova[
                    "jump_speed_units_per_tick"
                ],
                "status_nova_jump_target_id": status_nova["jump_target_id"],
                "status_nova_jump_timer_ms": _exact_float(
                    status_nova["jump_timer_ms"]
                ),
            }
        )
    return result


def _typed_combat(row: dict[str, Any], entity: Any) -> dict[str, Any] | None:
    state = entity["locked_combat_state"]
    if state is None:
        return None
    return {
        "attack_cooldown": _exact_float(state["attack_cooldown"]),
        "attack_preload_blocked": state["attack_preload_blocked"],
        "attack_windup_active": state["attack_windup_active"],
        "encounter_index": row["encounter_index"],
        "facing_x_units": state["facing_x_units"],
        "facing_y_units": state["facing_y_units"],
        "has_attacked_once": state["has_attacked_once"],
        "hitpoints": _exact(entity["hitpoints"]),
        "id": row["id"],
        "initial_position": _optional_exact_position(
            state["initial_position"], exact=True
        ),
        "is_alive": row["is_alive"],
        "last_attack_time": _exact_float(state["last_attack_time"]),
        "last_combat_target_id": state["last_combat_target_id"],
        "movement_target_id": state["movement_target_id"],
        "native_target_distance_discount_sq_units": state[
            "native_target_distance_discount_sq_units"
        ],
        "target_id": row["target_id"],
    }


def _typed_building(row: dict[str, Any], entity: Any) -> dict[str, Any] | None:
    lifetime = entity["building_lifetime_state"]
    impact = entity["building_impact_state"]
    if lifetime is None:
        return None
    if impact is None:
        raise ResidentPublicationError("typed building lifetime has no impact state")
    return {
        "activation_delay_remaining": _exact_float(
            impact["activation_delay_remaining"]
        ),
        "activation_first_hit_delay_remaining": _exact_float(
            impact["activation_first_hit_delay_remaining"]
        ),
        "crown_slot": impact["crown_slot"],
        "encounter_index": row["encounter_index"],
        "hitpoints": _exact(entity["hitpoints"]),
        "id": row["id"],
        "is_alive": row["is_alive"],
        "lifetime_decay_work": lifetime["decay_work"],
        "lifetime_elapsed": _exact_float(lifetime["lifetime_elapsed"]),
        "lifetime_tick_carry_ms": _exact_float(lifetime["tick_carry_ms"]),
        "tower_active": impact["tower_active"],
    }


def _typed_area(row: dict[str, Any], entity: Any) -> dict[str, Any] | None:
    state = entity["area_effect_state"]
    if state is None:
        return None
    spec = state["spec"]
    return {
        "affects_hidden": spec["affects_hidden"],
        "area_name": spec["area_name"],
        "attack_multiplier": _exact_float(spec["attack_multiplier"]),
        "cap_buff_time_to_effect": spec["cap_buff_time_to_effect"],
        "duration": _exact_float(spec["duration"]),
        "effect_snapshot_applied": state["effect_snapshot_applied"],
        "effect_tick_interval": _exact_float(spec["effect_tick_interval"]),
        "encounter_index": row["encounter_index"],
        "hits_air": spec["hits_air"],
        "hits_ground": spec["hits_ground"],
        "id": row["id"],
        "is_alive": row["is_alive"],
        "movement_multiplier": _exact_float(spec["movement_multiplier"]),
        "player_id": row["player_id"],
        "position_x": _exact(entity["position_x"]),
        "position_y": _exact(entity["position_y"]),
        "radius_tiles": _exact_float(spec["radius_tiles"]),
        "radius_units": spec["radius_units"],
        "refresh_duration": _exact_float(spec["refresh_duration"]),
        "spawn_multiplier": _exact_float(spec["spawn_multiplier"]),
        "time_alive": _exact_float(state["time_alive"]),
    }


def _typed_point(row: dict[str, Any], entity: Any) -> dict[str, Any] | None:
    state = entity["point_projectile_state"]
    if state is None:
        return None
    spawn_state = state["spawn_projectile_state"]
    return {
        "crown_tower_damage": (
            None
            if state["crown_tower_damage"] is None
            else _exact_float(state["crown_tower_damage"])
        ),
        "crown_tower_damage_multiplier": _exact_float(
            state["crown_tower_damage_multiplier"]
        ),
        "damage": _exact(entity["damage"]),
        "damage_group_id": state["damage_group_id"],
        "damage_wave_interval": _exact_float(state["damage_wave_interval"]),
        "encounter_index": row["encounter_index"],
        "hitpoints": _exact(entity["hitpoints"]),
        "hits_air": state["hits_air"],
        "hits_ground": state["hits_ground"],
        "id": row["id"],
        "ignore_buildings": state["ignore_buildings"],
        "is_alive": row["is_alive"],
        "knockback_distance": _exact_float(state["knockback_distance"]),
        "knockback_ignores_mass": state["knockback_ignores_mass"],
        "launch_delay": _exact_float(state["launch_delay"]),
        "permanent_homing_disabled_by_temporary": state[
            "permanent_homing_disabled_by_temporary"
        ],
        "position_x": _exact(entity["position_x"]),
        "position_y": _exact(entity["position_y"]),
        "primary_target_id": state["primary_target_id"],
        "slow_duration": _exact_float(state["slow_duration"]),
        "slow_multiplier": _exact_float(state["slow_multiplier"]),
        "source_entity_id": state["source_entity_id"],
        "source_kind": state["source_kind"],
        "splash_radius": _exact_float(state["splash_radius"]),
        "start_collision_resolved": state["start_collision_resolved"],
        "stun_duration": _exact_float(state["stun_duration"]),
        "target_position_x": _exact(state["target_x"]),
        "target_position_y": _exact(state["target_y"]),
        "temporary_homing_remaining_ms": state["temporary_homing_remaining_ms"],
        "temporary_homing_target_id": state["temporary_homing_target_id"],
        "tracks_target": state["tracks_target"],
        "travel_speed": _exact_float(state["travel_speed"]),
        "spawn_projectile_state": (
            None
            if spawn_state is None
            else {
                "activation_delay": _exact_float(spawn_state["activation_delay"]),
                "spawn_count": spawn_state["spawn_count"],
                "spawn_character": spawn_state["spawn_character"],
                "spawn_data_fingerprint": spawn_state["spawn_data_fingerprint"],
                "spawn_radius": (
                    None
                    if spawn_state["spawn_radius"] is None
                    else _exact_float(spawn_state["spawn_radius"])
                ),
                "spawn_deploy_delay": (
                    None
                    if spawn_state["spawn_deploy_delay"] is None
                    else _exact_float(spawn_state["spawn_deploy_delay"])
                ),
                "spawn_const_priority": spawn_state["spawn_const_priority"],
                "time_alive": _exact_float(spawn_state["time_alive"]),
            }
        ),
    }


def _typed_rolling(row: dict[str, Any], entity: Any) -> dict[str, Any] | None:
    state = entity["rolling_projectile_state"]
    if state is None:
        return None
    return {
        "crown_tower_damage": (
            None
            if state["crown_tower_damage"] is None
            else _exact_float(state["crown_tower_damage"])
        ),
        "crown_tower_damage_multiplier": _exact_float(
            state["crown_tower_damage_multiplier"]
        ),
        "damage": _exact(entity["damage"]),
        "distance_traveled": _exact_float(state["distance_traveled"]),
        "encounter_index": row["encounter_index"],
        "has_spawned_character": state["has_spawned_character"],
        "hit_entity_ids": list(state["hit_entity_ids"]),
        "id": row["id"],
        "is_alive": row["is_alive"],
        "knockback_distance": _exact_float(state["knockback_distance"]),
        "knockback_ignores_mass": state["knockback_ignores_mass"],
        "player_id": row["player_id"],
        "position_x": _exact(entity["position_x"]),
        "position_y": _exact(entity["position_y"]),
        "projectile_range": _exact_float(state["projectile_range"]),
        "radius_y": _exact_float(state["radius_y"]),
        "rolling_radius": _exact_float(state["rolling_radius"]),
        "source_kind": state["source_kind"],
        "spawn_delay": _exact_float(state["spawn_delay"]),
        "time_alive": _exact_float(state["time_alive"]),
        "travel_speed": _exact(state["travel_speed"]),
    }


def _typed_character_birth(state: Any) -> dict[str, Any] | None:
    if state is None:
        return None
    kind = state["kind"]
    base = {
        "effective_name": state["effective_name"],
        "group_id": state["group_id"],
        "lookup_name": state["lookup_name"],
        "member_count": state["member_count"],
        "opcode_index": state["opcode_index"],
        "ordinal": state["ordinal"],
        "source_entity_id": state["source_entity_id"],
        "template_fingerprint": state["template_fingerprint"],
    }
    if kind == 0:
        if state["unit_data_fingerprint"] is not None:
            raise ResidentPublicationError("catalog birth has death-spawn data")
        return {**base, "kind": "catalog_action"}
    if kind == 1:
        return {
            **base,
            "kind": "death_spawn",
            "unit_data_fingerprint": state["unit_data_fingerprint"],
        }
    if kind == 2:
        return {
            **base,
            "kind": "rolling_spawn",
            "unit_data_fingerprint": state["unit_data_fingerprint"],
        }
    raise ResidentPublicationError(f"unknown typed character birth kind {kind!r}")


def _typed_publication_projection(parts: Any) -> _TypedPublication:
    """Decode one owned typed native publication without legacy exporters."""
    try:
        if parts["version"] != 1:
            raise ResidentPublicationError("unsupported typed publication version")
        binding = dict(parts["binding"])
        if binding["semantic_schema_version"] != RESIDENT_SEMANTIC_SCHEMA_VERSION:
            raise ResidentPublicationError("typed semantic schema changed")
        battle = parts["battle"]
        battle_presence = _presence_from_mask(
            battle["sparse_attribute_presence"],
            _BATTLE_SPARSE_ATTRIBUTE_NAMES,
            offset=len(_ENTITY_SPARSE_ATTRIBUTE_NAMES),
            label="battle",
        )
        player_rows = [
            {
                "cycle_queue": list(player["cycle_queue"]),
                "elixir": _exact_float(player["elixir"]),
                "hand": list(player["hand"]),
                "king_tower_hp": _exact(player["king_tower_hp"]),
                "left_tower_hp": _exact(player["left_tower_hp"]),
                "max_elixir": _exact_float(player["max_elixir"]),
                "next_card_refill_cooldown_ms": player["next_card_refill_cooldown_ms"],
                "player_id": player["player_id"],
                "right_tower_hp": _exact(player["right_tower_hp"]),
            }
            for player in parts["players"]
        ]
        semantic_players = [
            {
                **row,
                "king_tower_hp": _exact_float(float(_scalar(row["king_tower_hp"]))),
                "left_tower_hp": _exact_float(float(_scalar(row["left_tower_hp"]))),
                "right_tower_hp": _exact_float(float(_scalar(row["right_tower_hp"]))),
            }
            for row in player_rows
        ]

        publication_rows: list[dict[str, Any]] = []
        sections: dict[str, list[dict[str, Any]]] = {
            name: []
            for name in (
                "entities",
                "modifiers",
                "shields",
                "character_objects",
                "death_opcodes",
                "area_effects",
                "movement",
                "locked_combat",
                "building_lifetime",
                "point_projectiles",
                "rolling_projectiles",
            )
        }
        for entity in parts["entities"]:
            base = {
                "card_name": entity["card_name"],
                "encounter_index": entity["encounter_index"],
                "entity_kind": entity["entity_kind"],
                "freeze_expiry_time": _exact_float(entity["freeze_expiry_time"]),
                "hitpoints": _exact(entity["hitpoints"]),
                "id": entity["id"],
                "is_alive": entity["is_alive"],
                "max_hitpoints": _exact(entity["max_hitpoints"]),
                "mechanics": list(entity["mechanics"]),
                "pending_projectile_max_duration_ms": entity[
                    "pending_projectile_max_duration_ms"
                ],
                "placement_delay_total": _exact_float(entity["placement_delay_total"]),
                "player_id": entity["player_id"],
                "position_x": _exact(entity["position_x"]),
                "position_y": _exact(entity["position_y"]),
                "python_type": entity["python_type"],
                "spawn_angle_shift": _exact_float(entity["spawn_angle_shift"]),
                "target_id": entity["target_id"],
            }
            modifier = _typed_modifier(base, entity)
            shield = _typed_shields(base, entity)
            death_rows = _typed_death_opcodes(base, entity)
            movement = _typed_movement(base, entity)
            combat = _typed_combat(base, entity)
            building = _typed_building(base, entity)
            area = _typed_area(base, entity)
            point = _typed_point(base, entity)
            rolling = _typed_rolling(base, entity)
            character_state = None
            if entity["entity_kind"] in (0, 1):
                character_state = {
                    "death_spawn_target_immunity_elapsed_ms": entity[
                        "death_spawn_target_immunity_elapsed_ms"
                    ],
                    "deploy_delay_remaining": _exact_float(
                        entity["deploy_delay_remaining"]
                    ),
                    "encounter_index": entity["encounter_index"],
                    "id": entity["id"],
                    "placement_pending": entity["placement_pending"],
                    "spawn_hook_fired": entity["spawn_hook_fired"],
                    "spawn_hook_pending": entity["spawn_hook_pending"],
                }
            point_constructor = None
            point_group_ids = None
            if point is not None:
                point_state = entity["point_projectile_state"]
                point_constructor = {
                    "card_stats_source_id": point_state["source_entity_id"],
                    "constructor_range": _exact(point_state["constructor_range"]),
                    "constructor_sight_range": _exact(
                        point_state["constructor_sight_range"]
                    ),
                    "homing_min_distance": _exact_float(
                        point_state["homing_min_distance"]
                    ),
                    "homing_time_ms": point_state["homing_time_ms"],
                    "launch_position_x": _exact_float(point_state["launch_x"]),
                    "launch_position_y": _exact_float(point_state["launch_y"]),
                    "pierces": False,
                    "projectile_range": _exact_float(0.0),
                    "start_extra_radius": _exact_float(0.0),
                }
                point_group_ids = (
                    None
                    if point_state["damage_group_hit_entity_ids"] is None
                    else list(point_state["damage_group_hit_entity_ids"])
                )
            row = {
                **base,
                "active": entity["active"],
                "area_effect_birth_source_id": (
                    None
                    if entity["area_effect_state"] is None
                    else entity["area_effect_state"]["birth_source_entity_id"]
                ),
                "area_effect_state": area,
                "building_lifetime_state": building,
                "character_birth": _typed_character_birth(entity["character_birth"]),
                "character_object_state": character_state,
                "locked_combat_state": combat,
                "modifier_state": modifier,
                "movement_state": movement,
                "point_projectile_constructor": point_constructor,
                "point_projectile_group_hit_entity_ids": point_group_ids,
                "point_projectile_state": point,
                "rolling_projectile_state": rolling,
                "shield_state": shield,
                "sparse_attribute_presence": _presence_from_mask(
                    entity["sparse_attribute_presence"],
                    _ENTITY_SPARSE_ATTRIBUTE_NAMES,
                    offset=0,
                    label=f"entity {entity['id']}",
                ),
            }
            publication_rows.append(row)
            if not entity["active"]:
                continue
            sections["entities"].append(base)
            for name, value in (
                ("modifiers", modifier),
                ("shields", shield),
                ("character_objects", character_state),
                ("area_effects", area),
                ("movement", movement),
                ("locked_combat", combat),
                ("building_lifetime", building),
                ("point_projectiles", point),
                ("rolling_projectiles", rolling),
            ):
                if value is not None:
                    sections[name].append(value)
            sections["death_opcodes"].extend(death_rows)

        towers = [
            {
                "hp": _exact_float(float(_scalar(tower["hp"]))),
                "hp_milli": tower["hp_milli"],
                "id": tower["id"],
                "is_active": tower["is_active"],
                "is_alive": tower["is_alive"],
                "last_attack_time": _exact_float(tower["last_attack_time"]),
                "player_id": tower["player_id"],
                "slot": tower["slot"],
            }
            for tower in parts["towers"]
            if tower["active"]
        ]
        rng = parts["rng"]
        pending = parts["pending_spells"]
        snapshot = {
            "schema_version": binding["semantic_schema_version"],
            "clock": {
                "double_elixir": battle["double_elixir"],
                "dt": _exact_float(battle["dt"]),
                "game_over": battle["game_over"],
                "overtime": battle["overtime"],
                "tick": battle["tick"],
                "time": _exact_float(battle["time"]),
                "triple_elixir": battle["triple_elixir"],
            },
            "players": semantic_players,
            "towers": towers,
            "outcome": {
                "game_over": battle["game_over"],
                "sudden_death": battle["sudden_death"],
                "sudden_death_crowns": list(battle["sudden_death_crowns"]),
                "winner": battle["winner"],
            },
            **sections,
            "rng": {
                "gauss_next": (
                    None if rng["gauss_next"] is None else _exact(rng["gauss_next"])
                ),
                "index": rng["index"],
                "state": list(rng["state"]),
                "version": rng["version"],
            },
            "next_entity_id": battle["next_entity_id"],
            "pending_spells": {
                "casts": [
                    {
                        "execute_at": _exact_float(cast["execute_at"]),
                        "player_id": cast["player_id"],
                        "position_x": _exact_float(cast["position_x"]),
                        "position_y": _exact_float(cast["position_y"]),
                        "sequence": cast["sequence"],
                        "spell_name": cast["spell_name"],
                    }
                    for cast in pending["casts"]
                ],
                "next_sequence": pending["next_sequence"],
            },
            "projectile_damage_groups": [
                {
                    "group_id": group["id"],
                    "hit_entity_ids": sorted(set(group["hit_entity_ids"])),
                }
                for group in parts["projectile_groups"]
            ],
            "win_conditions_dirty": battle["win_conditions_dirty"],
        }
        return _TypedPublication(
            binding=binding,
            snapshot=snapshot,
            publication_rows=publication_rows,
            battle_presence=battle_presence,
            player_rows=player_rows,
        )
    except ResidentPublicationError:
        raise
    except (AttributeError, KeyError, OverflowError, TypeError, ValueError) as error:
        raise ResidentPublicationError(
            "typed resident publication is malformed"
        ) from error


def _validate_entity_attribute_presence(
    publication_rows: list[dict[str, Any]],
) -> None:
    for row in publication_rows:
        presence = row.get("sparse_attribute_presence")
        if (
            type(presence) is not dict
            or set(presence) != _ENTITY_SPARSE_ATTRIBUTES
            or any(type(present) is not bool for present in presence.values())
        ):
            raise ResidentPublicationError(
                f"resident entity {row.get('id')} has malformed attribute presence"
            )


def _validate_structure(
    battle: Any,
    snapshot: dict[str, Any],
    *,
    resident: ResidentRustBattle,
    attest_live_action_stats: bool,
    publication_rows: list[dict[str, Any]],
    entity_registry: dict[int, Any],
) -> None:
    _validate_transient_boundary(battle)
    if snapshot.get("schema_version") != RESIDENT_SEMANTIC_SCHEMA_VERSION:
        raise ResidentPublicationError(
            "resident semantic schema changed before publication"
        )

    publication_by_id = _rows_by_id(publication_rows, label="publication entity")
    _validate_entity_attribute_presence(publication_rows)
    all_ids = set(publication_by_id)
    existing_ids = set(entity_registry)
    if not existing_ids.issubset(all_ids):
        raise ResidentPublicationError(
            "resident publication dropped an allocated entity: "
            f"registry={sorted(existing_ids)!r} resident={sorted(all_ids)!r}"
        )
    next_entity_id = int(snapshot["next_entity_id"])
    expected_birth_ids = set(range(int(battle.next_entity_id), next_entity_id))
    actual_birth_ids = all_ids - existing_ids
    if actual_birth_ids != expected_birth_ids:
        raise ResidentPublicationError(
            "resident publication has a non-contiguous allocation range: "
            f"expected={sorted(expected_birth_ids)!r} "
            f"actual={sorted(actual_birth_ids)!r}"
        )
    active_rows = sorted(
        (row for row in publication_rows if bool(row["active"])),
        key=lambda row: int(row["encounter_index"]),
    )
    active_ids = [int(row["id"]) for row in active_rows]
    resident_ids = [int(row["id"]) for row in snapshot["entities"]]
    if active_ids != resident_ids:
        raise ResidentPublicationError(
            "resident publication active order disagrees with semantic state: "
            f"publication={active_ids!r} semantic={resident_ids!r}"
        )
    for encounter_index, row in enumerate(active_rows):
        if int(row["encounter_index"]) != encounter_index:
            raise ResidentPublicationError(
                "resident publication rejected changed encounter ordering"
            )

    for entity_id in existing_ids:
        entity = entity_registry[entity_id]
        expected_type = f"{type(entity).__module__}.{type(entity).__qualname__}"
        actual_type = str(publication_by_id[entity_id]["python_type"])
        if actual_type != expected_type:
            raise ResidentPublicationError(
                f"resident publication changed Python type for id {entity_id}: "
                f"python={expected_type!r} resident={actual_type!r}"
            )
    for entity_id in actual_birth_ids:
        row = publication_by_id[entity_id]
        point_state = row["point_projectile_state"]
        rolling_state = row["rolling_projectile_state"]
        area_state = row["area_effect_state"]
        character_birth = row["character_birth"]
        if (
            sum(
                value is not None
                for value in (
                    point_state,
                    rolling_state,
                    area_state,
                    character_birth,
                )
            )
            != 1
        ):
            raise ResidentPublicationError(
                f"resident publication has unsupported birth recipe for id {entity_id}"
            )
        expected_type = (
            "clasher.entities.Projectile"
            if point_state is not None
            else "clasher.entities.RollingProjectile"
            if rolling_state is not None
            else (
                "clasher.entities.AreaEffect"
                if area_state is not None
                else _catalog_birth_type(int(row["entity_kind"]))[1]
            )
        )
        if row["python_type"] != expected_type:
            raise ResidentPublicationError(
                f"resident publication birth type mismatch for id {entity_id}: "
                f"expected={expected_type!r} actual={row['python_type']!r}"
            )
        if character_birth is not None:
            _catalog_birth_type(int(row["entity_kind"]))

    character_groups: dict[
        tuple[str, int],
        list[tuple[int, dict[str, Any]]],
    ] = {}
    catalog_group_variants: dict[tuple[str, int], set[int | None]] = {}
    for entity_id in actual_birth_ids:
        provenance = publication_by_id[entity_id]["character_birth"]
        if provenance is None:
            continue
        fingerprint = str(provenance["template_fingerprint"]).lower()
        if len(fingerprint) != 64 or any(
            digit not in "0123456789abcdef" for digit in fingerprint
        ):
            raise ResidentPublicationError(
                f"resident character {entity_id} has invalid template fingerprint"
            )
        kind = str(provenance["kind"])
        expected_fields = {
            "effective_name",
            "group_id",
            "kind",
            "lookup_name",
            "member_count",
            "opcode_index",
            "ordinal",
            "source_entity_id",
            "template_fingerprint",
        }
        if kind in ("death_spawn", "rolling_spawn"):
            expected_fields.add("unit_data_fingerprint")
        if set(provenance) != expected_fields:
            raise ResidentPublicationError(
                f"resident character {entity_id} has malformed {kind!r} provenance"
            )
        group_id = int(provenance["group_id"])
        ordinal = int(provenance["ordinal"])
        if entity_id != group_id + ordinal:
            raise ResidentPublicationError(
                f"resident character {entity_id} disagrees with group/ordinal provenance"
            )
        character_groups.setdefault((kind, group_id), []).append(
            (entity_id, provenance)
        )
        effective_name = str(provenance["effective_name"])
        if publication_by_id[entity_id]["card_name"] != effective_name:
            raise ResidentPublicationError(
                f"resident character {entity_id} birth name disagrees with entity row"
            )
        if kind == "catalog_action":
            lookup_name = str(provenance["lookup_name"])
            recipe = resident.character_action_birth_recipe(
                lookup_name,
                fingerprint,
                int(provenance["ordinal"]),
            )
            if (
                recipe is None
                or recipe.kind != kind
                or recipe.effective_name != effective_name
                or recipe.template_fingerprint != fingerprint
                or recipe.member_count != int(provenance["member_count"])
                or (
                    attest_live_action_stats
                    and not resident.character_action_card_stats_are_current(
                        battle,
                        lookup_name,
                    )
                )
            ):
                raise ResidentPublicationError(
                    f"resident character {entity_id} has unknown catalog birth recipe"
                )
            catalog_group_variants.setdefault((kind, group_id), set()).add(
                recipe.formation_variant
            )
            if (
                provenance["source_entity_id"] is not None
                or provenance["opcode_index"] is not None
            ):
                raise ResidentPublicationError(
                    f"resident catalog character {entity_id} has death provenance"
                )
        elif kind == "death_spawn":
            source_id = int(provenance["source_entity_id"])
            if source_id not in all_ids:
                raise ResidentPublicationError(
                    f"resident death-spawn character {entity_id} has unknown source {source_id}"
                )
            recipe = resident.character_death_spawn_birth_recipe(
                effective_name,
                fingerprint,
            )
            if recipe is None or recipe.kind != kind:
                raise ResidentPublicationError(
                    f"resident character {entity_id} has unknown death-spawn recipe"
                )
            source = entity_registry.get(source_id)
            if source is None:
                raise ResidentPublicationError(
                    f"resident death-spawn source {source_id} was not allocated before its child"
                )
            opcodes = [
                mechanic
                for mechanic in source.mechanics
                if isinstance(mechanic, (DeathDamage, DeathSpawn, DeathAreaEffect))
            ]
            opcode_index = int(provenance["opcode_index"])
            opcode = (
                None
                if opcode_index < 0 or opcode_index >= len(opcodes)
                else opcodes[opcode_index]
            )
            if (
                not isinstance(opcode, DeathSpawn)
                or str(opcode.unit_name) != effective_name
                or int(opcode.count) != int(provenance["member_count"])
            ):
                raise ResidentPublicationError(
                    f"resident character {entity_id} death-spawn opcode provenance changed"
                )
            unit_data_fingerprint = hashlib.sha256(
                json.dumps(
                    _normalize(opcode.unit_data),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("ascii")
            ).hexdigest()
            if (
                recipe.source_fingerprint != unit_data_fingerprint
                or provenance["unit_data_fingerprint"] != unit_data_fingerprint
            ):
                raise ResidentPublicationError(
                    f"resident character {entity_id} death-spawn data provenance changed"
                )
            if provenance["lookup_name"] is not None:
                raise ResidentPublicationError(
                    f"resident death-spawn character {entity_id} has action provenance"
                )
        elif kind == "rolling_spawn":
            source_id = int(provenance["source_entity_id"])
            source = entity_registry.get(source_id)
            recipe = resident.character_rolling_spawn_birth_recipe(
                str(provenance["lookup_name"]), fingerprint
            )
            if (
                type(source) is not RollingProjectile
                or recipe is None
                or recipe.kind != kind
                or recipe.effective_name != effective_name
                or recipe.source_fingerprint
                != provenance["unit_data_fingerprint"]
                or int(provenance["member_count"]) != 1
                or int(provenance["ordinal"]) != 0
                or provenance["opcode_index"] is not None
            ):
                raise ResidentPublicationError(
                    f"resident character {entity_id} has unknown rolling-spawn recipe"
                )
        else:
            raise ResidentPublicationError(
                f"resident character {entity_id} has unsupported birth kind {kind!r}"
            )

    for (kind, group_id), members in character_groups.items():
        member_count = int(members[0][1]["member_count"])
        ordinals = sorted(int(provenance["ordinal"]) for _, provenance in members)
        if member_count <= 0 or ordinals != list(range(member_count)):
            raise ResidentPublicationError(
                f"resident {kind} character group {group_id} has incomplete ordinals"
            )
        common = {
            (
                provenance["effective_name"],
                provenance["template_fingerprint"],
                provenance["lookup_name"],
                provenance["source_entity_id"],
                provenance["opcode_index"],
                provenance["member_count"],
            )
            for _, provenance in members
        }
        if (
            kind != "catalog_action"
            and len(common) != 1
            or kind == "catalog_action"
            and len({provenance["lookup_name"] for _, provenance in members}) != 1
            or kind == "catalog_action"
            and len(catalog_group_variants.get((kind, group_id), ())) != 1
            or group_id != min(entity_id for entity_id, _ in members)
        ):
            raise ResidentPublicationError(
                f"resident {kind} character group {group_id} has inconsistent provenance"
            )

    player_ids = [int(row["player_id"]) for row in snapshot["players"]]
    if player_ids != [int(player.player_id) for player in battle.players]:
        raise ResidentPublicationError(
            "resident publication rejected changed player ordering"
        )

    projectile_group_snapshots: dict[int, tuple[int, ...]] = {}
    for row in publication_rows:
        for field, reference_id in (("target_id", row["target_id"]),):
            if reference_id is not None and int(reference_id) not in all_ids:
                raise ResidentPublicationError(
                    f"resident entity {row['id']} has unknown {field} {reference_id}"
                )
        movement_state = row["movement_state"]
        if movement_state is not None:
            reference_id = movement_state.get("status_nova_jump_target_id")
            if reference_id is not None and int(reference_id) not in all_ids:
                raise ResidentPublicationError(
                    f"resident entity {row['id']} has unknown status-nova jump "
                    f"target {reference_id}"
                )
        rolling_state = row["rolling_projectile_state"]
        if rolling_state is not None and any(
            int(hit_id) >= int(snapshot["next_entity_id"])
            for hit_id in rolling_state["hit_entity_ids"]
        ):
            raise ResidentPublicationError(
                f"resident rolling projectile {row['id']} has an unallocated hit ID"
            )
        combat_state = row["locked_combat_state"]
        if combat_state is not None:
            for field in (
                "last_combat_target_id",
                "movement_target_id",
                "target_id",
            ):
                reference_id = combat_state[field]
                if reference_id is not None and int(reference_id) not in all_ids:
                    raise ResidentPublicationError(
                        f"resident entity {row['id']} has unknown {field} "
                        f"{reference_id}"
                    )
        point_state = row["point_projectile_state"]
        if point_state is None:
            if row["point_projectile_group_hit_entity_ids"] is not None:
                raise ResidentPublicationError(
                    f"resident non-projectile {row['id']} has projectile group state"
                )
            continue
        for field in (
            "primary_target_id",
            "source_entity_id",
            "temporary_homing_target_id",
        ):
            reference_id = point_state[field]
            if reference_id is not None and int(reference_id) not in all_ids:
                raise ResidentPublicationError(
                    "resident publication has an unknown projectile reference: "
                    f"projectile={row['id']} field={field} "
                    f"target={reference_id}"
                )
        constructor = row["point_projectile_constructor"]
        source_id = constructor["card_stats_source_id"]
        if source_id is not None and int(source_id) not in all_ids:
            raise ResidentPublicationError(
                f"resident projectile {row['id']} has unknown card-stats source "
                f"{source_id}"
            )
        group_id = point_state["damage_group_id"]
        hit_ids = row["point_projectile_group_hit_entity_ids"]
        if group_id is None:
            if hit_ids is not None:
                raise ResidentPublicationError(
                    f"resident ungrouped projectile {row['id']} has group hit IDs"
                )
            continue
        if (
            type(hit_ids) is not list
            or any(type(entity_id) is not int or entity_id < 0 for entity_id in hit_ids)
            or len(set(hit_ids)) != len(hit_ids)
        ):
            raise ResidentPublicationError(
                f"resident projectile group {group_id} has malformed hit IDs"
            )
        snapshot_ids = tuple(hit_ids)
        prior_snapshot = projectile_group_snapshots.setdefault(
            int(group_id), snapshot_ids
        )
        if prior_snapshot != snapshot_ids:
            raise ResidentPublicationError(
                f"resident projectile group {group_id} members disagree on hit IDs"
            )
    for row in publication_rows:
        source_id = row["area_effect_birth_source_id"]
        if source_id is not None and int(source_id) not in all_ids:
            raise ResidentPublicationError(
                f"resident area effect {row['id']} has unknown birth source {source_id}"
            )
    for row in snapshot["movement"]:
        if row["route_kind"] == "unsupported":
            raise ResidentPublicationError(
                f"resident publication rejected unsupported route cache for id {row['id']}"
            )


def _apply_players(
    battle: Any,
    rows: list[dict[str, Any]],
    undo: _UndoJournal | None = None,
) -> None:
    for player, row in zip(battle.players, rows, strict=True):
        if undo is not None:
            undo.watch_attrs(player)
            undo.watch_value(player.hand)
            undo.watch_value(player.cycle_queue)
        player.elixir = _float(row["elixir"])
        player.max_elixir = _float(row["max_elixir"])
        player.next_card_refill_cooldown_ms = int(row["next_card_refill_cooldown_ms"])
        player.hand[:] = row["hand"]
        player.cycle_queue.clear()
        player.cycle_queue.extend(row["cycle_queue"])
        player.king_tower_hp = _scalar(row["king_tower_hp"])
        player.left_tower_hp = _scalar(row["left_tower_hp"])
        player.right_tower_hp = _scalar(row["right_tower_hp"])


def _apply_entity_base(
    entity_registry: dict[int, Any],
    snapshot: dict[str, Any],
    undo: _UndoJournal | None = None,
) -> None:
    for row in snapshot["entities"]:
        entity = entity_registry[int(row["id"])]
        _watch_entity_attrs(undo, entity)
        entity.freeze_expiry_time = _scalar(row["freeze_expiry_time"])
        entity.hitpoints = _scalar(row["hitpoints"])
        entity.max_hitpoints = _scalar(row["max_hitpoints"])
        entity.is_alive = bool(row["is_alive"])
        entity._pending_projectile_max_duration_ms = int(
            row["pending_projectile_max_duration_ms"]
        )
        entity.placement_delay_total = _scalar(row["placement_delay_total"])
        entity.position.x = _scalar(row["position_x"])
        entity.position.y = _scalar(row["position_y"])
        entity.target_id = None if row["target_id"] is None else int(row["target_id"])


def _apply_modifiers(
    entity_registry: dict[int, Any],
    snapshot: dict[str, Any],
    undo: _UndoJournal | None = None,
) -> None:
    for row in snapshot["modifiers"]:
        entity = entity_registry[int(row["id"])]
        _watch_entity_attrs(undo, entity)
        if undo is not None:
            undo.watch_value(entity._haste_effects)
            undo.watch_value(entity._slow_effects)
        entity.attack_speed_buff_multiplier = _scalar(
            row["attack_speed_buff_multiplier"]
        )
        entity.attack_speed_debuff_multiplier = _scalar(
            row["attack_speed_debuff_multiplier"]
        )
        entity._haste_effects[:] = [
            tuple(_scalar(value) for value in effect) for effect in row["haste_effects"]
        ]
        entity.haste_timer = _scalar(row["haste_timer"])
        entity.movement_mode_multiplier = _scalar(row["movement_mode_multiplier"])
        entity.movement_speed_buff_multiplier = _scalar(
            row["movement_speed_buff_multiplier"]
        )
        entity.original_speed = (
            None if row["original_speed"] is None else _scalar(row["original_speed"])
        )
        entity._slow_effects[:] = [
            tuple(_scalar(value) for value in effect) for effect in row["slow_effects"]
        ]
        entity.slow_multiplier = _scalar(row["slow_multiplier"])
        entity.slow_timer = _scalar(row["slow_timer"])
        entity.spawn_speed_buff_multiplier = _scalar(row["spawn_speed_buff_multiplier"])
        entity.spawn_speed_debuff_multiplier = _scalar(
            row["spawn_speed_debuff_multiplier"]
        )
        entity.speed = _scalar(row["speed"])
        entity.stun_timer = _scalar(row["stun_timer"])


def _apply_shields(
    entity_registry: dict[int, Any],
    snapshot: dict[str, Any],
    undo: _UndoJournal | None = None,
) -> None:
    for row in snapshot["shields"]:
        entity = entity_registry[int(row["id"])]
        shields = [
            mechanic
            for mechanic in entity.mechanics
            if (
                f"{type(mechanic).__module__}.{type(mechanic).__qualname__}"
                == "clasher.mechanics.shared.shield.Shield"
            )
        ]
        _watch_entity_attrs(undo, entity)
        if undo is not None:
            for shield in shields:
                undo.watch_attrs(shield)
        entity._shield_break_count = int(row["shield_break_count"])
        for shield, shield_row in zip(shields, row["shields"], strict=True):
            shield.current_shield = _scalar(shield_row["current_shield"])


def _apply_character_objects(
    entity_registry: dict[int, Any],
    snapshot: dict[str, Any],
    undo: _UndoJournal | None = None,
) -> None:
    for row in snapshot["character_objects"]:
        entity = entity_registry[int(row["id"])]
        _watch_entity_attrs(undo, entity)
        entity._death_spawn_target_immunity_elapsed_ms = int(
            row["death_spawn_target_immunity_elapsed_ms"]
        )
        entity.deploy_delay_remaining = _scalar(row["deploy_delay_remaining"])
        entity.placement_pending = bool(row["placement_pending"])
        entity._spawn_hook_fired = bool(row["spawn_hook_fired"])
        entity._spawn_hook_pending = bool(row["spawn_hook_pending"])


def _apply_movement(
    entity_registry: dict[int, Any],
    snapshot: dict[str, Any],
    undo: _UndoJournal | None = None,
) -> None:
    for row in snapshot["movement"]:
        entity = entity_registry[int(row["id"])]
        _watch_entity_attrs(
            undo,
            entity,
            "_death_spawn_travel_target",
            "_knockback_target",
            "_river_jump_origin",
            "_river_jump_target",
        )
        _set_position(
            entity, "_death_spawn_travel_target", row["death_spawn_travel_target"]
        )
        entity._death_spawn_travel_ticks_remaining = int(
            row["death_spawn_travel_ticks"]
        )
        entity._facing_x_units = int(row["facing_x_units"])
        entity._facing_y_units = int(row["facing_y_units"])
        entity._ground_path_backwards = bool(row["ground_path_backwards"])
        entity._ground_path_cache_backwards = bool(row["route_backwards"])
        _set_position(entity, "_knockback_target", row["knockback_target"])
        entity._knockback_interrupts_combat = bool(row["knockback_interrupts_combat"])
        entity._knockback_velocity_work = int(row["knockback_velocity_work"])
        entity.movement_phase_elapsed_ms = int(row["movement_phase_elapsed_ms"])
        entity._native_avoidance = int(row["native_avoidance"])
        entity._native_lane_id = int(row["native_lane_id"])
        entity._native_natural_movement_active = bool(
            row["native_natural_movement_active"]
        )
        entity._pending_movement_consumed = bool(row["pending_consumed"])
        entity._pending_movement_x = _scalar(row["pending_x"])
        entity._pending_movement_y = _scalar(row["pending_y"])
        entity.position.x = _scalar(row["position_x"])
        entity.position.y = _scalar(row["position_y"])

        route_kind = row["route_kind"]
        if route_kind == "absent":
            entity.__dict__.pop("_ground_path_cache_key", None)
            entity.__dict__.pop("_native_ground_route_cells", None)
        else:
            goal = tuple(int(value) for value in row["route_goal"])
            if route_kind == "single":
                entity._ground_path_cache_key = ("single", goal)
            elif route_kind == "ground":
                entity._ground_path_cache_key = (
                    goal,
                    int(row["route_lane_id"]),
                    bool(row["route_jump_height"]),
                )
            else:  # validated before staging
                raise AssertionError(f"unreachable route kind {route_kind!r}")
            entity._native_ground_route_cells = [
                tuple(int(value) for value in cell) for cell in row["route_cells"]
            ]

        entity._river_jump_active = bool(row["river_jump_active"])
        entity._river_jump_blocked = bool(row["river_jump_blocked"])
        entity._river_jump_duration = _scalar(row["river_jump_duration"])
        entity._river_jump_elapsed = _scalar(row["river_jump_elapsed"])
        _set_position(entity, "_river_jump_origin", row["river_jump_origin"])
        _set_position(entity, "_river_jump_target", row["river_jump_target"])
        entity._special_move_active = bool(row["special_move_active"])
        entity._special_move_consumed_tick = bool(row["special_move_consumed_tick"])
        entity._stun_interrupt_deferred_until_landing = bool(
            row["stun_interrupt_deferred_until_landing"]
        )
        entity.forced_movement_active = bool(row["forced_movement_active"])
        entity._movement_vector_bypasses_cap = bool(row["vector_bypasses_cap"])
        entity._movement_vector_count = int(row["vector_count"])
        entity._movement_vector_x_units = int(row["vector_x_units"])
        entity._movement_vector_y_units = int(row["vector_y_units"])


def _apply_combat(
    entity_registry: dict[int, Any],
    snapshot: dict[str, Any],
    undo: _UndoJournal | None = None,
) -> None:
    for row in snapshot["locked_combat"]:
        entity = entity_registry[int(row["id"])]
        _watch_entity_attrs(undo, entity, "initial_position")
        entity.attack_cooldown = _scalar(row["attack_cooldown"])
        entity._attack_preload_blocked = bool(row["attack_preload_blocked"])
        entity._attack_windup_active = bool(row["attack_windup_active"])
        entity._facing_x_units = int(row["facing_x_units"])
        entity._facing_y_units = int(row["facing_y_units"])
        entity._has_attacked_once = bool(row["has_attacked_once"])
        entity.hitpoints = _scalar(row["hitpoints"])
        _set_position(entity, "initial_position", row["initial_position"])
        entity.is_alive = bool(row["is_alive"])
        entity.last_attack_time = _scalar(row["last_attack_time"])
        entity._last_combat_target_id = row["last_combat_target_id"]
        entity._movement_target_id = row["movement_target_id"]
        entity._native_target_distance_discount_sq_units = int(
            row["native_target_distance_discount_sq_units"]
        )
        entity.target_id = row["target_id"]


def _apply_buildings(
    entity_registry: dict[int, Any],
    snapshot: dict[str, Any],
    undo: _UndoJournal | None = None,
) -> None:
    for row in snapshot["building_lifetime"]:
        entity = entity_registry[int(row["id"])]
        _watch_entity_attrs(undo, entity)
        entity.activation_delay_remaining = _scalar(row["activation_delay_remaining"])
        entity.activation_first_hit_delay_remaining = _scalar(
            row["activation_first_hit_delay_remaining"]
        )
        entity.hitpoints = _scalar(row["hitpoints"])
        entity.is_alive = bool(row["is_alive"])
        entity.lifetime_decay_work = int(row["lifetime_decay_work"])
        entity.lifetime_elapsed = _scalar(row["lifetime_elapsed"])
        entity.lifetime_tick_carry_ms = _scalar(row["lifetime_tick_carry_ms"])
        entity._tower_active = bool(row["tower_active"])

    for row in snapshot["towers"]:
        tower = entity_registry[int(row["id"])]
        _watch_entity_attrs(undo, tower)
        tower.is_alive = bool(row["is_alive"])
        tower._tower_active = bool(row["is_active"])
        tower.last_attack_time = _float(row["last_attack_time"])


def _apply_area_effects(
    entity_registry: dict[int, Any],
    snapshot: dict[str, Any],
    undo: _UndoJournal | None = None,
) -> None:
    for row in snapshot["area_effects"]:
        entity = entity_registry[int(row["id"])]
        _watch_entity_attrs(undo, entity)
        _apply_area_effect_row(entity, row)


def _apply_area_effect_row(entity: Any, row: dict[str, Any]) -> None:
    entity.effect_snapshot_applied = bool(row["effect_snapshot_applied"])
    entity.is_alive = bool(row["is_alive"])
    entity.position.x = _scalar(row["position_x"])
    entity.position.y = _scalar(row["position_y"])
    entity.time_alive = _scalar(row["time_alive"])


def _apply_projectiles(
    entity_registry: dict[int, Any],
    snapshot: dict[str, Any],
    undo: _UndoJournal | None = None,
) -> None:
    group_sets: dict[int, set[int]] = {}
    for row in snapshot["point_projectiles"]:
        entity = entity_registry[int(row["id"])]
        _watch_entity_attrs(undo, entity, "target_position")
        _apply_projectile_row(entity, row, entity_registry)
        group_id = row["damage_group_id"]
        if group_id is not None:
            group_sets[int(group_id)] = entity.damage_group_hit_entity_ids

    for row in snapshot["projectile_damage_groups"]:
        hit_ids = group_sets[int(row["group_id"])]
        if hit_ids is None:  # pragma: no cover - structural preflight invariant
            raise AssertionError("validated projectile group disappeared")
        if undo is not None:
            undo.watch_value(hit_ids)
        hit_ids.clear()
        hit_ids.update(int(entity_id) for entity_id in row["hit_entity_ids"])


def _apply_projectile_row(
    entity: Any,
    row: dict[str, Any],
    entity_registry: dict[int, Any],
) -> None:
    entity.crown_tower_damage = (
        None
        if row["crown_tower_damage"] is None
        else _scalar(row["crown_tower_damage"])
    )
    entity.crown_tower_damage_multiplier = _scalar(row["crown_tower_damage_multiplier"])
    entity.damage = _scalar(row["damage"])
    entity.damage_wave_interval = _scalar(row["damage_wave_interval"])
    entity.hitpoints = _scalar(row["hitpoints"])
    entity.is_alive = bool(row["is_alive"])
    entity.launch_delay = _scalar(row["launch_delay"])
    entity.knockback_distance = _scalar(row["knockback_distance"])
    _set_sparse_default(
        entity,
        "_permanent_homing_disabled_by_temporary",
        bool(row["permanent_homing_disabled_by_temporary"]),
        False,
    )
    entity.position.x = _scalar(row["position_x"])
    entity.position.y = _scalar(row["position_y"])
    entity.primary_target = (
        None
        if row["primary_target_id"] is None
        else entity_registry[int(row["primary_target_id"])]
    )
    entity.source_entity = (
        None
        if row["source_entity_id"] is None
        else entity_registry[int(row["source_entity_id"])]
    )
    entity.start_collision_resolved = bool(row["start_collision_resolved"])
    entity.target_position.x = _scalar(row["target_position_x"])
    entity.target_position.y = _scalar(row["target_position_y"])
    entity.tracks_target = bool(row["tracks_target"])
    entity.travel_speed = _scalar(row["travel_speed"])
    _set_sparse_default(
        entity,
        "_temporary_homing_remaining_ms",
        int(row["temporary_homing_remaining_ms"]),
        0,
    )
    temporary_homing_target = (
        None
        if row["temporary_homing_target_id"] is None
        else entity_registry[int(row["temporary_homing_target_id"])]
    )
    _set_sparse_default(
        entity,
        "_temporary_homing_target",
        temporary_homing_target,
        None,
    )


def _apply_pending_spells(
    battle: Any,
    snapshot: dict[str, Any],
    undo: _UndoJournal | None = None,
) -> None:
    if undo is not None:
        undo.watch_attrs(battle)
        undo.watch_value(battle._pending_spell_casts)
    spell_state = snapshot["pending_spells"]
    existing_by_sequence = {
        int(cast.sequence): cast for cast in battle._pending_spell_casts
    }
    casts: list[PendingSpellCast] = []
    for row in spell_state["casts"]:
        execute_at = _scalar(row["execute_at"])
        sequence = int(row["sequence"])
        spell_name = str(row["spell_name"])
        player_id = int(row["player_id"])
        position_x = _scalar(row["position_x"])
        position_y = _scalar(row["position_y"])
        existing = existing_by_sequence.get(sequence)
        if (
            existing is not None
            and type(existing.execute_at) is type(execute_at)
            and existing.execute_at == execute_at
            and existing.spell_name == spell_name
            and existing.player_id == player_id
            and type(existing.position.x) is type(position_x)
            and existing.position.x == position_x
            and type(existing.position.y) is type(position_y)
            and existing.position.y == position_y
        ):
            casts.append(existing)
            continue
        casts.append(
            PendingSpellCast(
                execute_at=execute_at,
                sequence=sequence,
                spell_name=spell_name,
                player_id=player_id,
                position=Position(position_x, position_y),
            )
        )
    battle._pending_spell_casts[:] = casts
    _set_sparse_default(
        battle,
        "_next_spell_cast_sequence",
        int(spell_state["next_sequence"]),
        0,
    )


def _apply_rng(
    battle: Any,
    snapshot: dict[str, Any],
    undo: _UndoJournal | None = None,
) -> None:
    state = snapshot["rng"]
    inner = tuple(int(word) for word in state["state"]) + (int(state["index"]),)
    gauss = None if state["gauss_next"] is None else _float(state["gauss_next"])
    if undo is not None:
        undo.watch_value(battle.rng)
    battle.rng.setstate((int(state["version"]), inner, gauss))


def _refresh_python_caches(battle: Any) -> None:
    battle._pending_projectile_impacts.clear()
    battle._defer_projectile_impacts = False
    battle._projectile_lethal_reservations = None
    battle._coalesce_alive_building_refreshes = False
    battle.invalidate_target_cache()
    battle.invalidate_alive_buildings_cache()
    battle._building_placement_blocked_masks.clear()
    battle._troop_placement_blocked_masks.clear()
    if battle.fast_path:
        battle._refresh_fast_path_caches(trust_target_cache_dirty=True)


def _decode_publication_rows(payload: bytes) -> list[dict[str, Any]]:
    try:
        value = json.loads(payload)
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as error:
        raise ResidentPublicationError(
            "resident publication entity payload is not valid JSON"
        ) from error
    if not isinstance(value, list) or any(type(row) is not dict for row in value):
        raise ResidentPublicationError(
            "resident publication entity payload is not a list of rows"
        )
    return value


def _publication_rows(resident: ResidentRustBattle) -> list[dict[str, Any]]:
    return _decode_publication_rows(resident.publication_entity_state_bytes())


def _decode_battle_attribute_presence(payload: bytes) -> dict[str, bool]:
    try:
        value = json.loads(payload)
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as error:
        raise ResidentPublicationError(
            "resident battle attribute-presence payload is not valid JSON"
        ) from error
    if (
        type(value) is not dict
        or set(value) != _BATTLE_SPARSE_ATTRIBUTES
        or any(type(present) is not bool for present in value.values())
    ):
        raise ResidentPublicationError(
            "resident battle attribute-presence payload is malformed"
        )
    return cast(dict[str, bool], value)


def _decode_publication_player_rows(payload: bytes) -> list[dict[str, Any]]:
    try:
        value = json.loads(payload)
    except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as error:
        raise ResidentPublicationError(
            "resident publication player payload is not valid JSON"
        ) from error
    expected_fields = {
        "cycle_queue",
        "elixir",
        "hand",
        "king_tower_hp",
        "left_tower_hp",
        "max_elixir",
        "next_card_refill_cooldown_ms",
        "player_id",
        "right_tower_hp",
    }
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(type(row) is not dict or set(row) != expected_fields for row in value)
        or [row["player_id"] for row in value] != [0, 1]
    ):
        raise ResidentPublicationError(
            "resident publication player payload is malformed"
        )
    return cast(list[dict[str, Any]], value)


def _require_publication_exactness_attestation(
    resident: ResidentRustBattle,
    entity_payload: bytes,
    battle_presence_payload: bytes,
    player_payload: bytes,
) -> None:
    payload = bytearray(b"clasher-publication-exactness-v1")
    for part in (entity_payload, battle_presence_payload, player_payload):
        payload.extend(struct.pack("<Q", len(part)))
        payload.extend(part)
    actual = hashlib.sha256(payload).hexdigest()
    expected = resident.publication_exactness_sha256()
    if actual != expected:
        raise ResidentPublicationError(
            "resident publication exactness attestation mismatch: "
            f"expected={expected} actual={actual}"
        )


def _apply_attribute_presence(
    battle: Any,
    publication_rows: list[dict[str, Any]],
    entity_registry: dict[int, Any],
    battle_presence: dict[str, bool],
) -> None:
    for row in publication_rows:
        entity = entity_registry[int(row["id"])]
        presence = row["sparse_attribute_presence"]
        for field, present in presence.items():
            if present:
                if field not in entity.__dict__:
                    raise ResidentPublicationError(
                        f"resident entity {row['id']} publication omitted present "
                        f"attribute {field!r}"
                    )
            else:
                entity.__dict__.pop(field, None)
    for field, present in battle_presence.items():
        if present:
            if field not in battle.__dict__:
                raise ResidentPublicationError(
                    f"resident battle publication omitted present attribute {field!r}"
                )
        else:
            battle.__dict__.pop(field, None)


def _clone_registry(
    battle: Any,
    staged: Any,
    entity_registry: dict[int, Any],
) -> dict[int, Any]:
    memo: dict[int, Any] = {id(battle): staged}
    for entity_id, entity in battle.entities.items():
        staged_entity = staged.entities[int(entity_id)]
        memo[id(entity)] = staged_entity
        if type(entity) is not Projectile:
            continue
        original_hit_ids = entity.damage_group_hit_entity_ids
        staged_hit_ids = staged_entity.damage_group_hit_entity_ids
        if (original_hit_ids is None) != (staged_hit_ids is None):
            raise ResidentPublicationError(
                "staged projectile group presence disagrees with live state"
            )
        if original_hit_ids is None:
            continue
        prior = memo.get(id(original_hit_ids))
        if prior is not None and prior is not staged_hit_ids:
            raise ResidentPublicationError(
                "staged active projectiles split a shared group set"
            )
        memo[id(original_hit_ids)] = staged_hit_ids
    for original, cloned in zip(battle.players, staged.players, strict=True):
        memo[id(original)] = cloned
        memo[id(original.hand)] = cloned.hand
        memo[id(original.cycle_queue)] = cloned.cycle_queue
    memo[id(battle.rng)] = staged.rng
    return {
        entity_id: memo.get(id(entity)) or copy.deepcopy(entity, memo)
        for entity_id, entity in entity_registry.items()
    }


def _create_projectile_birth(
    battle: Any,
    row: dict[str, Any],
    entity_registry: dict[int, Any],
) -> Projectile:
    state = row["point_projectile_state"]
    constructor = row["point_projectile_constructor"]
    source_id = state["source_entity_id"]
    card_stats_source_id = constructor["card_stats_source_id"]
    if card_stats_source_id != source_id:
        raise ResidentPublicationError(
            f"projectile {row['id']} card-stats provenance disagrees with source"
        )
    source = None if source_id is None else entity_registry[int(source_id)]
    card_stats = None if source is None else source.card_stats
    projectile = Projectile(
        id=int(row["id"]),
        position=Position(
            _scalar(row["position_x"]),
            _scalar(row["position_y"]),
        ),
        player_id=int(row["player_id"]),
        card_stats=cast(Any, card_stats),
        hitpoints=_scalar(row["hitpoints"]),
        max_hitpoints=_scalar(row["max_hitpoints"]),
        damage=_scalar(state["damage"]),
        range=_scalar(constructor["constructor_range"]),
        sight_range=_scalar(constructor["constructor_sight_range"]),
        target_position=Position(
            _scalar(state["target_position_x"]),
            _scalar(state["target_position_y"]),
        ),
        travel_speed=_float(state["travel_speed"]),
        splash_radius=_float(state["splash_radius"]),
        source_name=(str(state["source_kind"]) if source is not None else "Unknown"),
        stun_duration=_float(state["stun_duration"]),
        slow_duration=_float(state["slow_duration"]),
        slow_multiplier=_float(state["slow_multiplier"]),
        knockback_distance=_float(state["knockback_distance"]),
        knockback_ignores_mass=bool(state["knockback_ignores_mass"]),
        hits_air=bool(state["hits_air"]),
        hits_ground=bool(state["hits_ground"]),
        ignore_buildings=bool(state["ignore_buildings"]),
        crown_tower_damage_multiplier=_float(state["crown_tower_damage_multiplier"]),
        crown_tower_damage=(
            None
            if state["crown_tower_damage"] is None
            else _float(state["crown_tower_damage"])
        ),
        damage_waves=1,
        damage_wave_interval=_float(state["damage_wave_interval"]),
        launch_delay=_float(state["launch_delay"]),
        source_entity=None,
        primary_target=None,
        tracks_target=bool(state["tracks_target"]),
        pierces=bool(constructor["pierces"]),
        projectile_range=_float(constructor["projectile_range"]),
        homing_time_ms=int(constructor["homing_time_ms"]),
        homing_min_distance=_float(constructor["homing_min_distance"]),
        launch_position=Position(
            _scalar(constructor["launch_position_x"]),
            _scalar(constructor["launch_position_y"]),
        ),
        start_extra_radius=_float(constructor["start_extra_radius"]),
        start_collision_resolved=bool(state["start_collision_resolved"]),
        spawn_projectile_data=None,
    )
    dynamic_projectile = cast(Any, projectile)
    if source is None:
        dynamic_projectile.spell_name = str(state["source_kind"])
    dynamic_projectile.battle_state = battle
    return projectile


def _create_area_effect_birth(
    battle: Any,
    row: dict[str, Any],
    entity_registry: dict[int, Any],
) -> AreaEffect:
    state = row["area_effect_state"]
    source_id = row["area_effect_birth_source_id"]
    if source_id is None:
        raise ResidentPublicationError(
            f"new area effect {row['id']} has no birth-source provenance"
        )
    source = entity_registry[int(source_id)]
    radius = _float(state["radius_tiles"])
    effect = AreaEffect(
        id=int(row["id"]),
        position=Position(
            _scalar(row["position_x"]),
            _scalar(row["position_y"]),
        ),
        player_id=int(row["player_id"]),
        card_stats=source.card_stats,
        hitpoints=_scalar(row["hitpoints"]),
        max_hitpoints=_scalar(row["max_hitpoints"]),
        damage=0.0,
        range=radius,
        sight_range=radius,
        duration=_float(state["duration"]),
        speed_multiplier=_float(state["movement_multiplier"]),
        attack_speed_multiplier=_float(state["attack_multiplier"]),
        spawn_speed_multiplier=_float(state["spawn_multiplier"]),
        radius=radius,
        hits_air=bool(state["hits_air"]),
        hits_ground=bool(state["hits_ground"]),
        affects_hidden=bool(state["affects_hidden"]),
        slow_refresh_duration=_float(state["refresh_duration"]),
        effect_tick_interval=_float(state["effect_tick_interval"]),
        effect_on_spawn_only=True,
        cap_buff_time_to_effect=bool(state["cap_buff_time_to_effect"]),
    )
    dynamic_effect = cast(Any, effect)
    dynamic_effect.spell_name = str(state["area_name"])
    dynamic_effect.battle_state = battle
    return effect


def _create_character_birth(
    battle: Any,
    row: dict[str, Any],
    resident: ResidentRustBattle,
    shared_card_stats: dict[tuple[Any, ...], Any],
    attest_live_action_stats: bool,
) -> Troop | Building:
    provenance = row["character_birth"]
    kind = str(provenance["kind"])
    group_key: tuple[Any, ...] = (kind, int(provenance["group_id"]))
    fingerprint = str(provenance["template_fingerprint"]).lower()
    if kind == "catalog_action":
        lookup_name = str(provenance["lookup_name"])
        recipe = resident.character_action_birth_recipe(
            lookup_name,
            fingerprint,
            int(provenance["ordinal"]),
        )
        if recipe is None:  # pragma: no cover - structural preflight invariant
            raise AssertionError("validated action birth recipe disappeared")
        group_key = (*group_key, recipe.card_stats_group)
        if (
            attest_live_action_stats
            and not resident.character_action_card_stats_are_current(
                battle,
                lookup_name,
            )
        ):
            raise ResidentPublicationError(
                f"catalog birth lookup {lookup_name!r} changed after resident initialization"
            )
        stats = shared_card_stats.get(group_key)
        if stats is None:
            if recipe.uses_live_action_card_stats:
                stats = battle.card_loader.get_card(lookup_name)
                if stats is None or str(stats.name) != recipe.effective_name:
                    raise ResidentPublicationError(
                        f"catalog birth lookup {lookup_name!r} changed during publication"
                    )
            else:
                stats = copy.deepcopy(recipe.prototype.card_stats)
            shared_card_stats[group_key] = stats
    elif kind == "death_spawn":
        recipe = resident.character_death_spawn_birth_recipe(
            str(provenance["effective_name"]),
            fingerprint,
        )
        if recipe is None:  # pragma: no cover - structural preflight invariant
            raise AssertionError("validated death-spawn recipe disappeared")
        stats = shared_card_stats.get(group_key)
        if stats is None:
            stats = copy.deepcopy(recipe.prototype.card_stats)
            shared_card_stats[group_key] = stats
    elif kind == "rolling_spawn":
        recipe = resident.character_rolling_spawn_birth_recipe(
            provenance["lookup_name"], provenance["template_fingerprint"]
        )
        if recipe is None:
            raise ResidentPublicationError(
                "validated rolling-spawn recipe disappeared"
            )
        stats = shared_card_stats.get(group_key)
        if stats is None:
            stats = copy.deepcopy(recipe.prototype.card_stats)
            shared_card_stats[group_key] = stats
    elif kind == "spawn_projectile_spawn":
        recipe = resident.character_spawn_projectile_birth_recipe(
            provenance["lookup_name"],
            provenance["template_fingerprint"],
            provenance["ordinal"],
        )
        if recipe is None:
            raise ResidentPublicationError(
                "validated spawn-projectile child recipe disappeared"
            )
        stats = shared_card_stats.get(group_key)
        if stats is None:
            stats = copy.deepcopy(recipe.prototype.card_stats)
            shared_card_stats[group_key] = stats
    else:
        raise ResidentPublicationError("unsupported character birth provenance kind")

    prototype = recipe.prototype
    memo: dict[int, Any] = {id(prototype.card_stats): stats}
    prototype_battle = getattr(prototype, "battle_state", None)
    if prototype_battle is not None:
        memo[id(prototype_battle)] = battle
    entity = copy.deepcopy(prototype, memo)
    expected_type, _, expected_action_kind = _catalog_birth_type(int(row["entity_kind"]))
    if recipe.action_kind != expected_action_kind or type(entity) is not expected_type:
        raise ResidentPublicationError(
            "resident catalog birth recipe produced the wrong entity type"
        )
    entity.id = int(row["id"])
    entity.player_id = int(row["player_id"])
    entity.card_stats = stats
    cast(Any, entity).battle_state = battle
    return cast(Troop | Building, entity)


def _prepare_births(
    battle: Any,
    resident: ResidentRustBattle,
    publication_rows: list[dict[str, Any]],
    entity_registry: dict[int, Any],
    attest_live_action_stats: bool,
) -> dict[int, Any]:
    """Construct all births detached from the live registry and entity dict."""
    pending: dict[int, Any] = {}
    available = dict(entity_registry)
    shared_card_stats: dict[tuple[Any, ...], Any] = {}
    for row in publication_rows:
        entity_id = int(row["id"])
        if entity_id in entity_registry:
            continue
        if row["point_projectile_state"] is not None:
            entity: Any = _create_projectile_birth(battle, row, available)
        elif row["area_effect_state"] is not None:
            entity = _create_area_effect_birth(battle, row, available)
        elif row["character_birth"] is not None:
            entity = _create_character_birth(
                battle,
                row,
                resident,
                shared_card_stats,
                attest_live_action_stats,
            )
        else:  # pragma: no cover - structural validation owns this invariant
            raise AssertionError("validated resident birth recipe disappeared")
        pending[entity_id] = entity
        available[entity_id] = entity
    return pending


def _create_projectile_birth_direct(
    battle: Any,
    row: dict[str, Any],
    available: dict[int, Any],
    resident: ResidentRustBattle,
) -> Projectile:
    state = cast(dict[str, Any], row["point_projectile_state"])
    source_id = state["source_entity_id"]
    source = None if source_id is None else available[source_id]
    spawn_state = state["spawn_projectile_state"]
    spawn_recipe = (
        None
        if spawn_state is None
        else resident.spawn_projectile_recipe(state["source_kind"])
    )
    if spawn_state is not None and spawn_recipe is None:
        raise ResidentPublicationError(
            f"spawn projectile {row['id']} recipe disappeared"
        )
    projectile_type: type[Projectile] = (
        SpawnProjectile if spawn_state is not None else Projectile
    )
    spawn_kwargs: dict[str, Any] = (
        {}
        if spawn_state is None
        else {
            "spawn_count": spawn_state["spawn_count"],
            "spawn_character": spawn_state["spawn_character"],
            "spawn_character_data": copy.deepcopy(
                cast(Any, spawn_recipe).spawn_character_data
            ),
            "spawn_radius": spawn_state["spawn_radius"],
            "activation_delay": spawn_state["activation_delay"],
            "spawn_deploy_delay_override": spawn_state["spawn_deploy_delay"],
            "spawn_const_priority": spawn_state["spawn_const_priority"],
            "time_alive": spawn_state["time_alive"],
        }
    )
    projectile = projectile_type(
        id=row["id"],
        position=Position(_scalar(row["position_x"]), _scalar(row["position_y"])),
        player_id=row["player_id"],
        card_stats=cast(Any, None if source is None else source.card_stats),
        hitpoints=_scalar(row["hitpoints"]),
        max_hitpoints=_scalar(row["max_hitpoints"]),
        damage=_scalar(row["damage"]),
        range=_scalar(state["constructor_range"]),
        sight_range=_scalar(state["constructor_sight_range"]),
        target_position=Position(
            _scalar(state["target_x"]), _scalar(state["target_y"])
        ),
        travel_speed=state["travel_speed"],
        splash_radius=state["splash_radius"],
        source_name=state["source_kind"] if source is not None else "Unknown",
        stun_duration=state["stun_duration"],
        slow_duration=state["slow_duration"],
        slow_multiplier=state["slow_multiplier"],
        knockback_distance=state["knockback_distance"],
        knockback_ignores_mass=state["knockback_ignores_mass"],
        hits_air=state["hits_air"],
        hits_ground=state["hits_ground"],
        ignore_buildings=state["ignore_buildings"],
        crown_tower_damage_multiplier=state["crown_tower_damage_multiplier"],
        crown_tower_damage=state["crown_tower_damage"],
        damage_waves=1,
        damage_wave_interval=state["damage_wave_interval"],
        launch_delay=state["launch_delay"],
        source_entity=None,
        primary_target=None,
        tracks_target=state["tracks_target"],
        pierces=False,
        projectile_range=0.0,
        homing_time_ms=state["homing_time_ms"],
        homing_min_distance=state["homing_min_distance"],
        launch_position=Position(state["launch_x"], state["launch_y"]),
        start_extra_radius=0.0,
        start_collision_resolved=state["start_collision_resolved"],
        spawn_projectile_data=None,
        **spawn_kwargs,
    )
    dynamic = cast(Any, projectile)
    if source is None:
        dynamic.spell_name = state["source_kind"]
    dynamic.battle_state = battle
    return projectile


def _create_area_effect_birth_direct(
    battle: Any,
    row: dict[str, Any],
    available: dict[int, Any],
) -> AreaEffect:
    state = cast(dict[str, Any], row["area_effect_state"])
    source_id = state["birth_source_entity_id"]
    if source_id is None:
        raise ResidentPublicationError(
            f"new area effect {row['id']} has no birth source"
        )
    source = available[source_id]
    spec = cast(dict[str, Any], state["spec"])
    radius = spec["radius_tiles"]
    effect = AreaEffect(
        id=row["id"],
        position=Position(_scalar(row["position_x"]), _scalar(row["position_y"])),
        player_id=row["player_id"],
        card_stats=source.card_stats,
        hitpoints=_scalar(row["hitpoints"]),
        max_hitpoints=_scalar(row["max_hitpoints"]),
        damage=0.0,
        range=radius,
        sight_range=radius,
        duration=spec["duration"],
        speed_multiplier=spec["movement_multiplier"],
        attack_speed_multiplier=spec["attack_multiplier"],
        spawn_speed_multiplier=spec["spawn_multiplier"],
        radius=radius,
        hits_air=spec["hits_air"],
        hits_ground=spec["hits_ground"],
        affects_hidden=spec["affects_hidden"],
        slow_refresh_duration=spec["refresh_duration"],
        effect_tick_interval=spec["effect_tick_interval"],
        effect_on_spawn_only=True,
        cap_buff_time_to_effect=spec["cap_buff_time_to_effect"],
    )
    dynamic = cast(Any, effect)
    dynamic.spell_name = spec["area_name"]
    dynamic.battle_state = battle
    return effect


def _create_rolling_birth_direct(
    battle: Any,
    row: dict[str, Any],
    resident: ResidentRustBattle,
) -> RollingProjectile:
    state = cast(dict[str, Any], row["rolling_projectile_state"])
    recipe = resident.rolling_projectile_recipe(state["source_kind"])
    if recipe is None:
        raise ResidentPublicationError(
            "validated rolling projectile recipe disappeared"
        )
    projectile = RollingProjectile(
        id=row["id"],
        position=Position(_scalar(row["position_x"]), _scalar(row["position_y"])),
        player_id=row["player_id"],
        card_stats=None,  # type: ignore[arg-type]
        hitpoints=_scalar(row["hitpoints"]),
        max_hitpoints=_scalar(row["max_hitpoints"]),
        damage=_scalar(row["damage"]),
        range=state["rolling_radius"],
        sight_range=0,
        travel_speed=_scalar(state["travel_speed"]),
        projectile_range=state["projectile_range"],
        spawn_delay=state["spawn_delay"],
        spawn_character=cast(str, recipe.spawn_character),
        spawn_character_data=recipe.spawn_character_data,
        spawn_deploy_delay_override=recipe.spawn_deploy_delay,
        radius_y=state["radius_y"],
        knockback_distance=state["knockback_distance"],
        knockback_ignores_mass=state["knockback_ignores_mass"],
        crown_tower_damage_multiplier=state["crown_tower_damage_multiplier"],
        crown_tower_damage=state["crown_tower_damage"],
    )
    dynamic = cast(Any, projectile)
    dynamic.spell_name = state["source_kind"]
    dynamic.battle_state = battle
    return projectile


def _create_character_birth_direct(
    battle: Any,
    row: dict[str, Any],
    resident: ResidentRustBattle,
    shared_card_stats: dict[tuple[Any, ...], Any],
) -> Troop | Building:
    provenance = cast(dict[str, Any], row["character_birth"])
    kind = provenance["kind"]
    group_key: tuple[Any, ...] = (kind, provenance["group_id"])
    if kind == 0:
        lookup_name = provenance["lookup_name"]
        recipe = resident.character_action_birth_recipe(
            lookup_name,
            provenance["template_fingerprint"],
            provenance["ordinal"],
        )
        if recipe is None or not resident.character_action_card_stats_are_current(
            battle, lookup_name
        ):
            raise ResidentPublicationError(
                f"catalog birth lookup {lookup_name!r} changed during publication"
            )
        group_key = (*group_key, recipe.card_stats_group)
        stats = shared_card_stats.get(group_key)
        if stats is None:
            if recipe.uses_live_action_card_stats:
                stats = battle.card_loader.get_card(lookup_name)
                if stats is None or str(stats.name) != recipe.effective_name:
                    raise ResidentPublicationError(
                        f"catalog birth lookup {lookup_name!r} changed during publication"
                    )
            else:
                stats = copy.deepcopy(recipe.prototype.card_stats)
            shared_card_stats[group_key] = stats
    elif kind == 1:
        recipe = resident.character_death_spawn_birth_recipe(
            provenance["effective_name"], provenance["template_fingerprint"]
        )
        if recipe is None:
            raise ResidentPublicationError("validated death-spawn recipe disappeared")
        stats = shared_card_stats.get(group_key)
        if stats is None:
            stats = copy.deepcopy(recipe.prototype.card_stats)
            shared_card_stats[group_key] = stats
    elif kind == 2:
        recipe = resident.character_rolling_spawn_birth_recipe(
            provenance["lookup_name"], provenance["template_fingerprint"]
        )
        if recipe is None:
            raise ResidentPublicationError(
                "validated rolling-spawn recipe disappeared"
            )
        stats = shared_card_stats.get(group_key)
        if stats is None:
            stats = copy.deepcopy(recipe.prototype.card_stats)
            shared_card_stats[group_key] = stats
    elif kind == 3:
        recipe = resident.character_spawn_projectile_birth_recipe(
            provenance["lookup_name"],
            provenance["template_fingerprint"],
            provenance["ordinal"],
        )
        if recipe is None:
            raise ResidentPublicationError(
                "validated spawn-projectile child recipe disappeared"
            )
        stats = shared_card_stats.get(group_key)
        if stats is None:
            stats = copy.deepcopy(recipe.prototype.card_stats)
            shared_card_stats[group_key] = stats
    else:
        raise ResidentPublicationError("unsupported character birth provenance kind")
    prototype = recipe.prototype
    memo: dict[int, Any] = {id(prototype.card_stats): stats}
    prototype_battle = getattr(prototype, "battle_state", None)
    if prototype_battle is not None:
        memo[id(prototype_battle)] = battle
    entity = copy.deepcopy(prototype, memo)
    expected_type, _, expected_action_kind = _catalog_birth_type(row["entity_kind"])
    if recipe.action_kind != expected_action_kind or type(entity) is not expected_type:
        raise ResidentPublicationError(
            "resident catalog recipe did not produce the expected entity type"
        )
    entity.id = row["id"]
    entity.player_id = row["player_id"]
    entity.card_stats = stats
    cast(Any, entity).battle_state = battle
    return cast(Troop | Building, entity)


def _prepare_direct_births(
    battle: Any,
    resident: ResidentRustBattle,
    plan: _DirectPublicationPlan,
    entity_registry: dict[int, Any],
) -> dict[int, Any]:
    pending: dict[int, Any] = {}
    available = dict(entity_registry)
    shared_card_stats: dict[tuple[Any, ...], Any] = {}
    for entity_plan in plan.entities:
        entity_id = entity_plan.entity_id
        if entity_id in entity_registry:
            continue
        row = entity_plan.raw
        if row["point_projectile_state"] is not None:
            entity: Any = _create_projectile_birth_direct(
                battle, row, available, resident
            )
        elif row["rolling_projectile_state"] is not None:
            entity = _create_rolling_birth_direct(battle, row, resident)
        elif row["area_effect_state"] is not None:
            entity = _create_area_effect_birth_direct(battle, row, available)
        else:
            entity = _create_character_birth_direct(
                battle, row, resident, shared_card_stats
            )
        pending[entity_id] = entity
        available[entity_id] = entity
    return pending


def _validate_direct_bound_entities(
    plan: _DirectPublicationPlan,
    registry: dict[int, Any],
) -> None:
    """Resolve every Python topology dependency before the undoable commit."""
    for entity_plan in plan.entities:
        row = entity_plan.raw
        entity = registry[entity_plan.entity_id]
        shields = [
            mechanic
            for mechanic in entity.mechanics
            if f"{type(mechanic).__module__}.{type(mechanic).__qualname__}"
            == "clasher.mechanics.shared.shield.Shield"
        ]
        if len(shields) != len(row["shields"]):
            raise ResidentPublicationError(
                f"resident entity {entity_plan.entity_id} shield topology changed"
            )
        point = row["point_projectile_state"]
        if point is not None:
            expected_type = (
                SpawnProjectile
                if point["spawn_projectile_state"] is not None
                else Projectile
            )
            if type(entity) is not expected_type or not isinstance(
                entity.target_position, Position
            ):
                raise ResidentPublicationError(
                    f"resident projectile {entity_plan.entity_id} Python topology changed"
                )
            for field in (
                "primary_target_id",
                "source_entity_id",
                "temporary_homing_target_id",
            ):
                reference = point[field]
                if reference is not None and reference not in registry:
                    raise ResidentPublicationError(
                        f"resident projectile {entity_plan.entity_id} has unknown {field}"
                    )
        rolling = row["rolling_projectile_state"]
        if rolling is not None and (
            type(entity) is not RollingProjectile
            or type(entity.hit_entities) is not set
        ):
            raise ResidentPublicationError(
                f"resident rolling projectile {entity_plan.entity_id} Python topology changed"
            )
        area = row["area_effect_state"]
        if area is not None and type(entity) is not AreaEffect:
            raise ResidentPublicationError(
                f"resident area effect {entity_plan.entity_id} Python topology changed"
            )
        movement = row["movement_state"]
        if movement is not None:
            for field in (
                "_death_spawn_travel_target",
                "_knockback_target",
                "_river_jump_origin",
                "_river_jump_target",
            ):
                value = getattr(entity, field, None)
                if value is not None and not isinstance(value, Position):
                    raise ResidentPublicationError(
                        f"resident entity {entity_plan.entity_id} changed {field} topology"
                    )
        combat = row["locked_combat_state"]
        if combat is not None:
            initial = getattr(entity, "initial_position", None)
            if initial is not None and not isinstance(initial, Position):
                raise ResidentPublicationError(
                    f"resident entity {entity_plan.entity_id} changed initial-position topology"
                )
        status_nova = row["status_nova_jump"]
        status_mechanics = [
            mechanic
            for mechanic in entity.mechanics
            if f"{type(mechanic).__module__}.{type(mechanic).__qualname__}"
            == "clasher.cards.ice_spirit.IceSpiritFreeze"
        ]
        if (status_nova is None) != (len(status_mechanics) == 0) or len(
            status_mechanics
        ) > 1:
            raise ResidentPublicationError(
                f"resident entity {entity_plan.entity_id} status-nova topology changed"
            )


def _apply_publication_entity_rows(
    battle: Any,
    publication_rows: list[dict[str, Any]],
    entity_registry: dict[int, Any],
    undo: _UndoJournal | None = None,
) -> None:
    for row in publication_rows:
        entity = entity_registry[int(row["id"])]
        _watch_entity_attrs(undo, entity)
        entity.freeze_expiry_time = _scalar(row["freeze_expiry_time"])
        entity.hitpoints = _scalar(row["hitpoints"])
        entity.max_hitpoints = _scalar(row["max_hitpoints"])
        entity.is_alive = bool(row["is_alive"])
        entity._pending_projectile_max_duration_ms = int(
            row["pending_projectile_max_duration_ms"]
        )
        entity.placement_delay_total = _scalar(row["placement_delay_total"])
        entity.position.x = _scalar(row["position_x"])
        entity.position.y = _scalar(row["position_y"])
        entity.target_id = None if row["target_id"] is None else int(row["target_id"])
        entity.battle_state = battle

    for row in publication_rows:
        if bool(row["active"]):
            continue
        entity = entity_registry[int(row["id"])]
        point_state = row["point_projectile_state"]
        if point_state is not None:
            _watch_entity_attrs(undo, entity, "target_position")
            _apply_projectile_row(entity, point_state, entity_registry)
        area_state = row["area_effect_state"]
        if area_state is not None:
            _apply_area_effect_row(entity, area_state)
        modifier_state = row["modifier_state"]
        if modifier_state is not None:
            _apply_modifiers(entity_registry, {"modifiers": [modifier_state]}, undo)
        shield_state = row["shield_state"]
        if shield_state is not None:
            _apply_shields(entity_registry, {"shields": [shield_state]}, undo)
        character_state = row["character_object_state"]
        if character_state is not None:
            _apply_character_objects(
                entity_registry,
                {"character_objects": [character_state]},
                undo,
            )
        movement_state = row["movement_state"]
        if movement_state is not None:
            _apply_movement(entity_registry, {"movement": [movement_state]}, undo)
        combat_state = row["locked_combat_state"]
        if combat_state is not None:
            _apply_combat(
                entity_registry,
                {"locked_combat": [combat_state]},
                undo,
            )
        building_lifetime_state = row["building_lifetime_state"]
        if building_lifetime_state is not None:
            _apply_buildings(
                entity_registry,
                {
                    "building_lifetime": [building_lifetime_state],
                    "towers": [],
                },
                undo,
            )

    active_rows = sorted(
        (row for row in publication_rows if bool(row["active"])),
        key=lambda row: int(row["encounter_index"]),
    )
    if undo is not None:
        undo.watch_value(battle.entities)
    battle.entities.clear()
    battle.entities.update(
        (int(row["id"]), entity_registry[int(row["id"])]) for row in active_rows
    )


def _plan_projectile_groups(
    publication_rows: list[dict[str, Any]],
    entity_registry: dict[int, Any],
) -> tuple[dict[int, tuple[set[int], tuple[int, ...]]], dict[int, int | None]]:
    group_members: dict[int, list[int]] = {}
    group_hit_ids: dict[int, tuple[int, ...]] = {}
    for row in publication_rows:
        state = row["point_projectile_state"]
        if state is None:
            continue
        group_id = state["damage_group_id"]
        if group_id is not None:
            normalized_group_id = int(group_id)
            group_members.setdefault(normalized_group_id, []).append(int(row["id"]))
            group_hit_ids[normalized_group_id] = tuple(
                int(entity_id)
                for entity_id in row["point_projectile_group_hit_entity_ids"]
            )

    chosen_sets: dict[int, tuple[set[int], tuple[int, ...]]] = {}
    used_set_ids: set[int] = set()
    for group_id, member_ids in group_members.items():
        existing = {
            id(candidate_hit_ids): candidate_hit_ids
            for entity_id in member_ids
            if (
                candidate_hit_ids := entity_registry[
                    entity_id
                ].damage_group_hit_entity_ids
            )
            is not None
        }
        if len(existing) > 1:
            raise ResidentPublicationError(
                f"resident projectile group {group_id} would merge Python set identities"
            )
        shared_hit_ids: set[int] = next(iter(existing.values()), set())
        if id(shared_hit_ids) in used_set_ids:
            raise ResidentPublicationError(
                f"resident projectile group {group_id} would split a Python set identity"
            )
        used_set_ids.add(id(shared_hit_ids))
        chosen_sets[group_id] = (shared_hit_ids, group_hit_ids[group_id])

    assignments: dict[int, int | None] = {}
    for row in publication_rows:
        state = row["point_projectile_state"]
        if state is None:
            continue
        group_id = state["damage_group_id"]
        assignments[int(row["id"])] = None if group_id is None else int(group_id)
    return chosen_sets, assignments


def _apply_projectile_group_plan(
    plan: tuple[dict[int, tuple[set[int], tuple[int, ...]]], dict[int, int | None]],
    entity_registry: dict[int, Any],
    undo: _UndoJournal | None = None,
) -> None:
    chosen_sets, assignments = plan
    for shared_hit_ids, hit_ids in chosen_sets.values():
        if undo is not None:
            undo.watch_value(shared_hit_ids)
        shared_hit_ids.clear()
        shared_hit_ids.update(hit_ids)
    for entity_id, group_id in assignments.items():
        projectile = entity_registry[entity_id]
        if undo is not None:
            undo.watch_attrs(projectile)
        projectile.damage_group_hit_entity_ids = (
            None if group_id is None else chosen_sets[group_id][0]
        )


def _plan_direct_projectile_groups(
    plan: _DirectPublicationPlan,
    entity_registry: dict[int, Any],
) -> tuple[dict[int, tuple[set[int], tuple[int, ...]]], dict[int, int | None]]:
    members: dict[int, list[int]] = {}
    hits: dict[int, tuple[int, ...]] = {}
    assignments: dict[int, int | None] = {}
    for entity_plan in plan.entities:
        state = entity_plan.raw["point_projectile_state"]
        if state is None:
            continue
        group_id = state["damage_group_id"]
        assignments[entity_plan.entity_id] = group_id
        if group_id is None:
            continue
        members.setdefault(group_id, []).append(entity_plan.entity_id)
        hits[group_id] = tuple(state["damage_group_hit_entity_ids"])

    chosen: dict[int, tuple[set[int], tuple[int, ...]]] = {}
    used: set[int] = set()
    for group_id, member_ids in members.items():
        existing = {
            id(value): value
            for entity_id in member_ids
            if (value := entity_registry[entity_id].damage_group_hit_entity_ids)
            is not None
        }
        if len(existing) > 1:
            raise ResidentPublicationError(
                f"resident projectile group {group_id} would merge Python set identities"
            )
        shared: set[int] = next(iter(existing.values()), set())
        if id(shared) in used:
            raise ResidentPublicationError(
                f"resident projectile group {group_id} would split a Python set identity"
            )
        used.add(id(shared))
        chosen[group_id] = (shared, hits[group_id])
    return chosen, assignments


def _apply_direct_status_nova_jump(entity: Any, state: Any) -> None:
    if state is None:
        return
    entity._ice_spirit_detonated = state["detonated"]
    entity._ice_spirit_jump_timer = state["jump_timer_ms"]
    entity._ice_spirit_jump_target = state["jump_target_id"]
    destination = state["jump_destination"]
    entity._ice_spirit_jump_destination = (
        None
        if destination is None
        else (_scalar(destination[0]), _scalar(destination[1]))
    )
    origin = state["jump_origin"]
    if origin is None:
        entity.__dict__.pop("_ice_spirit_jump_origin", None)
    else:
        entity._ice_spirit_jump_origin = (
            _scalar(origin[0]),
            _scalar(origin[1]),
        )


def _apply_direct_entity(
    battle: Any,
    entity: Any,
    row: dict[str, Any],
    registry: dict[int, Any],
    undo: _UndoJournal,
) -> None:
    _watch_entity_attrs(
        undo,
        entity,
        "target_position",
        "_death_spawn_travel_target",
        "_knockback_target",
        "_river_jump_origin",
        "_river_jump_target",
        "initial_position",
    )
    entity.freeze_expiry_time = row["freeze_expiry_time"]
    entity.hitpoints = _scalar(row["hitpoints"])
    entity.max_hitpoints = _scalar(row["max_hitpoints"])
    entity.is_alive = row["is_alive"]
    entity._pending_projectile_max_duration_ms = row[
        "pending_projectile_max_duration_ms"
    ]
    entity.placement_delay_total = row["placement_delay_total"]
    entity.position.x = _scalar(row["position_x"])
    entity.position.y = _scalar(row["position_y"])
    entity.target_id = row["target_id"]
    entity.battle_state = battle
    _apply_direct_status_nova_jump(entity, row["status_nova_jump"])

    modifier = row["modifier_state"]
    if modifier is not None:
        undo.watch_value(entity._haste_effects)
        undo.watch_value(entity._slow_effects)
        entity.attack_speed_buff_multiplier = modifier["attack_speed_buff_multiplier"]
        entity.attack_speed_debuff_multiplier = modifier[
            "attack_speed_debuff_multiplier"
        ]
        entity._haste_effects[:] = [
            (
                effect["remaining"],
                effect["movement"],
                effect["attack"],
                effect["spawn"],
            )
            for effect in modifier["haste_effects"]
        ]
        entity.haste_timer = modifier["haste_timer"]
        entity.movement_mode_multiplier = modifier["movement_mode_multiplier"]
        entity.movement_speed_buff_multiplier = modifier[
            "movement_speed_buff_multiplier"
        ]
        entity.original_speed = modifier["original_speed"]
        entity._slow_effects[:] = [
            (
                effect["remaining"],
                effect["movement"],
                effect["attack"],
                effect["spawn"],
            )
            for effect in modifier["slow_effects"]
        ]
        entity.slow_multiplier = modifier["slow_multiplier"]
        entity.slow_timer = modifier["slow_timer"]
        entity.spawn_speed_buff_multiplier = modifier["spawn_speed_buff_multiplier"]
        entity.spawn_speed_debuff_multiplier = modifier["spawn_speed_debuff_multiplier"]
        entity.speed = _scalar(modifier["speed"])
        entity.stun_timer = modifier["stun_timer"]

    shields = row["shields"]
    if shields:
        mechanics = [
            mechanic
            for mechanic in entity.mechanics
            if f"{type(mechanic).__module__}.{type(mechanic).__qualname__}"
            == "clasher.mechanics.shared.shield.Shield"
        ]
        if len(mechanics) != len(shields):
            raise ResidentPublicationError(
                f"resident entity {row['id']} shield topology changed during commit"
            )
        entity._shield_break_count = row["shield_break_count"]
        for mechanic, state in zip(mechanics, shields, strict=True):
            undo.watch_attrs(mechanic)
            mechanic.current_shield = _scalar(state["current"])

    if row["entity_kind"] in (0, 1):
        entity._death_spawn_target_immunity_elapsed_ms = row[
            "death_spawn_target_immunity_elapsed_ms"
        ]
        entity.deploy_delay_remaining = row["deploy_delay_remaining"]
        entity.placement_pending = row["placement_pending"]
        entity._spawn_hook_fired = row["spawn_hook_fired"]
        entity._spawn_hook_pending = row["spawn_hook_pending"]

    movement = row["movement_state"]
    combat = row["locked_combat_state"]
    if movement is not None:
        _set_direct_position(
            entity,
            "_death_spawn_travel_target",
            movement["death_spawn_travel_target"],
            exact=False,
        )
        entity._death_spawn_travel_ticks_remaining = movement[
            "death_spawn_travel_ticks"
        ]
        entity._ground_path_cache_backwards = movement["route_backwards"]
        _set_direct_position(
            entity, "_knockback_target", movement["knockback_target"], exact=False
        )
        entity._knockback_interrupts_combat = movement["knockback_interrupts_combat"]
        entity._knockback_velocity_work = movement["knockback_velocity_work"]
        entity.movement_phase_elapsed_ms = movement["movement_phase_elapsed_ms"]
        entity._native_avoidance = movement["native_avoidance"]
        entity._native_lane_id = movement["native_lane_id"]
        entity._native_natural_movement_active = movement[
            "native_natural_movement_active"
        ]
        entity._pending_movement_consumed = movement["pending_consumed"]
        entity._pending_movement_x = movement["pending_x"]
        entity._pending_movement_y = movement["pending_y"]
        route_kind = movement["route_cache_kind"]
        if route_kind == 0:
            entity.__dict__.pop("_ground_path_cache_key", None)
            entity.__dict__.pop("_native_ground_route_cells", None)
        else:
            goal = tuple(movement["route_goal"])
            entity._ground_path_cache_key = (
                ("single", goal)
                if route_kind == 1
                else (goal, movement["route_lane_id"], movement["route_jump_height"])
            )
            route_cells = [tuple(cell) for cell in movement["route_cells"]]
            existing_route_cells = entity.__dict__.get(
                "_native_ground_route_cells"
            )
            if type(existing_route_cells) is list:
                undo.watch_value(existing_route_cells)
                existing_route_cells[:] = route_cells
            else:
                entity._native_ground_route_cells = route_cells
        entity._river_jump_active = movement["river_jump_active"]
        entity._river_jump_blocked = movement["river_jump_blocked"]
        entity._river_jump_duration = movement["river_jump_duration"]
        entity._river_jump_elapsed = movement["river_jump_elapsed"]
        _set_direct_position(
            entity, "_river_jump_origin", movement["river_jump_origin"], exact=True
        )
        _set_direct_position(
            entity, "_river_jump_target", movement["river_jump_target"], exact=False
        )
        entity._special_move_active = movement["special_move_active"]
        entity._special_move_consumed_tick = movement["special_move_consumed_tick"]
        entity._stun_interrupt_deferred_until_landing = movement[
            "stun_interrupt_deferred_until_landing"
        ]
        entity.forced_movement_active = movement["forced_movement_active"]
        entity._movement_vector_bypasses_cap = movement["vector_bypasses_cap"]
        entity._movement_vector_count = movement["vector_count"]
        entity._movement_vector_x_units = movement["vector_x_units"]
        entity._movement_vector_y_units = movement["vector_y_units"]
    if combat is not None:
        entity.attack_cooldown = combat["attack_cooldown"]
        entity._attack_preload_blocked = combat["attack_preload_blocked"]
        entity._attack_windup_active = combat["attack_windup_active"]
        entity._facing_x_units = combat["facing_x_units"]
        entity._facing_y_units = combat["facing_y_units"]
        entity._ground_path_backwards = combat["ground_path_backwards"]
        entity._has_attacked_once = combat["has_attacked_once"]
        _set_direct_position(
            entity, "initial_position", combat["initial_position"], exact=True
        )
        entity.last_attack_time = combat["last_attack_time"]
        entity._last_combat_target_id = combat["last_combat_target_id"]
        entity._movement_target_id = combat["movement_target_id"]
        entity._native_target_distance_discount_sq_units = combat[
            "native_target_distance_discount_sq_units"
        ]

    lifetime = row["building_lifetime_state"]
    impact = row["building_impact_state"]
    if lifetime is not None:
        entity.activation_delay_remaining = impact["activation_delay_remaining"]
        entity.activation_first_hit_delay_remaining = impact[
            "activation_first_hit_delay_remaining"
        ]
        entity.lifetime_decay_work = lifetime["decay_work"]
        entity.lifetime_elapsed = lifetime["lifetime_elapsed"]
        entity.lifetime_tick_carry_ms = lifetime["tick_carry_ms"]
        entity._tower_active = impact["tower_active"]

    area = row["area_effect_state"]
    if area is not None:
        entity.effect_snapshot_applied = area["effect_snapshot_applied"]
        entity.time_alive = area["time_alive"]

    point = row["point_projectile_state"]
    if point is not None:
        entity.crown_tower_damage = point["crown_tower_damage"]
        entity.crown_tower_damage_multiplier = point["crown_tower_damage_multiplier"]
        entity.damage = _scalar(row["damage"])
        entity.damage_wave_interval = point["damage_wave_interval"]
        entity.launch_delay = point["launch_delay"]
        entity.knockback_distance = point["knockback_distance"]
        entity._permanent_homing_disabled_by_temporary = point[
            "permanent_homing_disabled_by_temporary"
        ]
        entity.primary_target = (
            None
            if point["primary_target_id"] is None
            else registry[point["primary_target_id"]]
        )
        entity.source_entity = (
            None
            if point["source_entity_id"] is None
            else registry[point["source_entity_id"]]
        )
        entity.start_collision_resolved = point["start_collision_resolved"]
        entity.target_position.x = _scalar(point["target_x"])
        entity.target_position.y = _scalar(point["target_y"])
        entity.tracks_target = point["tracks_target"]
        entity.travel_speed = point["travel_speed"]
        entity._temporary_homing_remaining_ms = point["temporary_homing_remaining_ms"]
        entity._temporary_homing_target = (
            None
            if point["temporary_homing_target_id"] is None
            else registry[point["temporary_homing_target_id"]]
        )
        spawn = point["spawn_projectile_state"]
        if spawn is not None:
            entity.time_alive = spawn["time_alive"]

    rolling = row["rolling_projectile_state"]
    if rolling is not None:
        undo.watch_value(entity.hit_entities)
        entity.damage = _scalar(row["damage"])
        entity.crown_tower_damage = rolling["crown_tower_damage"]
        entity.crown_tower_damage_multiplier = rolling[
            "crown_tower_damage_multiplier"
        ]
        entity.distance_traveled = rolling["distance_traveled"]
        entity.has_spawned_character = rolling["has_spawned_character"]
        entity.hit_entities.clear()
        entity.hit_entities.update(rolling["hit_entity_ids"])
        entity.knockback_distance = rolling["knockback_distance"]
        entity.knockback_ignores_mass = rolling["knockback_ignores_mass"]
        entity.projectile_range = rolling["projectile_range"]
        entity.radius_y = rolling["radius_y"]
        entity.rolling_radius = rolling["rolling_radius"]
        entity.range = rolling["rolling_radius"]
        entity.spell_name = rolling["source_kind"]
        entity.spawn_delay = rolling["spawn_delay"]
        entity.time_alive = rolling["time_alive"]
        entity.travel_speed = _scalar(rolling["travel_speed"])


def _prepare_direct_delta_births(
    battle: Any,
    resident: ResidentRustBattle,
    plan: _DirectDeltaPublicationPlan,
    entity_registry: dict[int, Any],
) -> dict[int, Any]:
    pending: dict[int, Any] = {}
    available = dict(entity_registry)
    shared_card_stats: dict[tuple[Any, ...], Any] = {}
    for change in plan.entities:
        if change.full is None:
            continue
        row = change.full.raw
        if row["point_projectile_state"] is not None:
            entity: Any = _create_projectile_birth_direct(
                battle, row, available, resident
            )
        elif row["rolling_projectile_state"] is not None:
            entity = _create_rolling_birth_direct(battle, row, resident)
        elif row["area_effect_state"] is not None:
            entity = _create_area_effect_birth_direct(battle, row, available)
        else:
            entity = _create_character_birth_direct(
                battle, row, resident, shared_card_stats
            )
        pending[change.entity_id] = entity
        available[change.entity_id] = entity
    return pending


def _validate_direct_delta_bound_entities(
    plan: _DirectDeltaPublicationPlan,
    registry: dict[int, Any],
) -> None:
    for change in plan.entities:
        entity = registry[change.entity_id]
        if change.full is not None or change.dirty_mask & _ENTITY_DELTA_SHIELDS:
            shields = (
                change.full.raw["shields"]
                if change.full is not None
                else change.raw["shields"]
            )
            mechanics = [
                mechanic
                for mechanic in entity.mechanics
                if f"{type(mechanic).__module__}.{type(mechanic).__qualname__}"
                == "clasher.mechanics.shared.shield.Shield"
            ]
            if len(mechanics) != len(shields):
                raise ResidentPublicationError(
                    f"resident entity {change.entity_id} shield topology changed"
                )
        point = (
            change.full.raw["point_projectile_state"]
            if change.full is not None
            else change.raw["point_projectile_state"]
            if change.dirty_mask & _ENTITY_DELTA_POINT
            else None
        )
        if point is not None:
            expected_type = (
                SpawnProjectile
                if point["spawn_projectile_state"] is not None
                else Projectile
            )
            if type(entity) is not expected_type or not isinstance(
                entity.target_position, Position
            ):
                raise ResidentPublicationError(
                    f"resident projectile {change.entity_id} Python topology changed"
                )
            for field in (
                "primary_target_id",
                "source_entity_id",
                "temporary_homing_target_id",
            ):
                reference = point[field]
                if reference is not None and reference not in registry:
                    raise ResidentPublicationError(
                        f"resident projectile {change.entity_id} has unknown {field}"
                    )
        rolling = (
            change.full.raw["rolling_projectile_state"]
            if change.full is not None
            else change.raw["rolling_projectile_state"]
            if change.dirty_mask & _ENTITY_DELTA_ROLLING
            else None
        )
        if rolling is not None and (
            type(entity) is not RollingProjectile
            or type(entity.hit_entities) is not set
        ):
            raise ResidentPublicationError(
                f"resident rolling projectile {change.entity_id} Python topology changed"
            )
        area = (
            change.full.raw["area_effect_state"]
            if change.full is not None
            else change.raw["area_effect_state"]
            if change.dirty_mask & _ENTITY_DELTA_AREA
            else None
        )
        if area is not None and type(entity) is not AreaEffect:
            raise ResidentPublicationError(
                f"resident area effect {change.entity_id} Python topology changed"
            )
        movement = (
            change.full.raw["movement_state"]
            if change.full is not None
            else change.raw["movement_state"]
            if change.dirty_mask & _ENTITY_DELTA_MOVEMENT
            else None
        )
        if movement is not None:
            for field in (
                "_death_spawn_travel_target",
                "_knockback_target",
                "_river_jump_origin",
                "_river_jump_target",
            ):
                value = getattr(entity, field, None)
                if value is not None and not isinstance(value, Position):
                    raise ResidentPublicationError(
                        f"resident entity {change.entity_id} changed {field} topology"
                    )
        combat = (
            change.full.raw["locked_combat_state"]
            if change.full is not None
            else change.raw["locked_combat_state"]
            if change.dirty_mask & _ENTITY_DELTA_COMBAT
            else None
        )
        if combat is not None:
            initial = getattr(entity, "initial_position", None)
            if initial is not None and not isinstance(initial, Position):
                raise ResidentPublicationError(
                    f"resident entity {change.entity_id} changed initial-position topology"
                )


def _plan_direct_delta_projectile_groups(
    plan: _DirectDeltaPublicationPlan,
    registry: dict[int, Any],
) -> tuple[dict[int, tuple[set[int], tuple[int, ...]]], dict[int, int | None]]:
    members: dict[int, list[int]] = {}
    hits: dict[int, tuple[int, ...]] = {}
    active_hits: dict[int, tuple[int, ...]] = {}
    assignments: dict[int, int | None] = {}
    for change in plan.entities:
        state = (
            change.full.raw["point_projectile_state"]
            if change.full is not None
            else change.raw["point_projectile_state"]
            if change.dirty_mask & _ENTITY_DELTA_POINT
            else None
        )
        if state is None:
            continue
        group_id = state["damage_group_id"]
        assignments[change.entity_id] = group_id
        if group_id is None:
            continue
        members.setdefault(group_id, []).append(change.entity_id)
        snapshot = tuple(state["damage_group_hit_entity_ids"])
        previous = hits.setdefault(group_id, snapshot)
        if previous != snapshot:
            raise ResidentPublicationError(
                f"resident projectile group {group_id} members disagree on hit IDs"
            )
        active = (
            change.full.active
            if change.full is not None
            else change.raw["base"]["active"]
            if change.dirty_mask & _ENTITY_DELTA_BASE
            else change.entity_id in plan.active_entity_ids
        )
        if active:
            active_hits[group_id] = snapshot
    if plan.projectile_groups is not None:
        summaries = {
            group["id"]: tuple(group["hit_entity_ids"])
            for group in plan.projectile_groups
        }
        for group_id, snapshot in active_hits.items():
            if summaries.get(group_id) != snapshot:
                raise ResidentPublicationError(
                    "direct projectile group summary disagrees with entities"
                )
        changed_points = {
            change.entity_id: (
                change.full.raw["point_projectile_state"]
                if change.full is not None
                else change.raw["point_projectile_state"]
            )
            for change in plan.entities
            if change.full is not None
            and change.full.raw["point_projectile_state"] is not None
            or change.full is None
            and change.dirty_mask & _ENTITY_DELTA_POINT
            and change.raw["point_projectile_state"] is not None
        }
        expected_summaries: dict[int, tuple[int, ...]] = {}
        unchanged_aliases: dict[int, tuple[set[int], list[int]]] = {}
        for entity_id in plan.active_entity_ids:
            point = changed_points.get(entity_id)
            if point is not None:
                group_id = point["damage_group_id"]
                if group_id is not None:
                    expected_summaries[group_id] = tuple(
                        point["damage_group_hit_entity_ids"]
                    )
                continue
            entity = registry[entity_id]
            if type(entity) is not Projectile:
                continue
            shared = entity.damage_group_hit_entity_ids
            if shared is not None:
                alias = unchanged_aliases.setdefault(id(shared), (shared, []))
                alias[1].append(entity_id)
        for existing_shared, member_ids in unchanged_aliases.values():
            expected_summaries[min(member_ids)] = tuple(sorted(existing_shared))
        if summaries != expected_summaries:
            raise ResidentPublicationError(
                "direct projectile group summary changed unchanged groups"
            )
    chosen: dict[int, tuple[set[int], tuple[int, ...]]] = {}
    used: set[int] = set()
    for group_id, member_ids in members.items():
        existing = {
            id(value): value
            for entity_id in member_ids
            if (value := registry[entity_id].damage_group_hit_entity_ids) is not None
        }
        if len(existing) > 1:
            raise ResidentPublicationError(
                f"resident projectile group {group_id} would merge Python set identities"
            )
        selected_shared = cast(set[int], next(iter(existing.values()), set()))
        if id(selected_shared) in used:
            raise ResidentPublicationError(
                f"resident projectile group {group_id} would split a Python set identity"
            )
        used.add(id(selected_shared))
        chosen[group_id] = (selected_shared, hits[group_id])
    return chosen, assignments


def _apply_direct_delta_entity(
    battle: Any,
    entity: Any,
    change: _DirectDeltaEntityPublication,
    registry: dict[int, Any],
    undo: _UndoJournal,
) -> None:
    if change.full is not None:
        _apply_direct_entity(battle, entity, change.full.raw, registry, undo)
        return
    raw = change.raw
    mask = change.dirty_mask
    if mask & _ENTITY_DELTA_BASE:
        row = raw["base"]
        _watch_entity_attrs(undo, entity)
        entity.freeze_expiry_time = row["freeze_expiry_time"]
        entity.hitpoints = _scalar(row["hitpoints"])
        entity.max_hitpoints = _scalar(row["max_hitpoints"])
        entity.damage = _scalar(row["damage"])
        entity.is_alive = row["is_alive"]
        entity._pending_projectile_max_duration_ms = row[
            "pending_projectile_max_duration_ms"
        ]
        entity.placement_delay_total = row["placement_delay_total"]
        entity.position.x = _scalar(row["position_x"])
        entity.position.y = _scalar(row["position_y"])
        entity.target_id = row["target_id"]
        entity.battle_state = battle
        _apply_direct_status_nova_jump(entity, row["status_nova_jump"])
        if hasattr(entity, "deploy_delay_remaining"):
            entity._death_spawn_target_immunity_elapsed_ms = row[
                "death_spawn_target_immunity_elapsed_ms"
            ]
            entity.deploy_delay_remaining = row["deploy_delay_remaining"]
            entity.placement_pending = row["placement_pending"]
            entity._spawn_hook_fired = row["spawn_hook_fired"]
            entity._spawn_hook_pending = row["spawn_hook_pending"]
    if mask & _ENTITY_DELTA_MODIFIER:
        modifier = raw["modifier_state"]
        if modifier is not None:
            undo.watch_attrs(entity)
            undo.watch_value(entity._haste_effects)
            undo.watch_value(entity._slow_effects)
            entity.attack_speed_buff_multiplier = modifier[
                "attack_speed_buff_multiplier"
            ]
            entity.attack_speed_debuff_multiplier = modifier[
                "attack_speed_debuff_multiplier"
            ]
            entity._haste_effects[:] = [
                (item["remaining"], item["movement"], item["attack"], item["spawn"])
                for item in modifier["haste_effects"]
            ]
            entity.haste_timer = modifier["haste_timer"]
            entity.movement_mode_multiplier = modifier["movement_mode_multiplier"]
            entity.movement_speed_buff_multiplier = modifier[
                "movement_speed_buff_multiplier"
            ]
            entity.original_speed = modifier["original_speed"]
            entity._slow_effects[:] = [
                (item["remaining"], item["movement"], item["attack"], item["spawn"])
                for item in modifier["slow_effects"]
            ]
            entity.slow_multiplier = modifier["slow_multiplier"]
            entity.slow_timer = modifier["slow_timer"]
            entity.spawn_speed_buff_multiplier = modifier[
                "spawn_speed_buff_multiplier"
            ]
            entity.spawn_speed_debuff_multiplier = modifier[
                "spawn_speed_debuff_multiplier"
            ]
            entity.speed = _scalar(modifier["speed"])
            entity.stun_timer = modifier["stun_timer"]
    if mask & _ENTITY_DELTA_SHIELDS:
        undo.watch_attrs(entity)
        mechanics = [
            mechanic
            for mechanic in entity.mechanics
            if f"{type(mechanic).__module__}.{type(mechanic).__qualname__}"
            == "clasher.mechanics.shared.shield.Shield"
        ]
        entity._shield_break_count = raw["shield_break_count"]
        for mechanic, state in zip(mechanics, raw["shields"], strict=True):
            undo.watch_attrs(mechanic)
            mechanic.current_shield = _scalar(state["current"])
    if mask & _ENTITY_DELTA_MOVEMENT:
        movement = raw["movement_state"]
        if movement is not None:
            _watch_entity_attrs(
                undo,
                entity,
                "_death_spawn_travel_target",
                "_knockback_target",
                "_river_jump_origin",
                "_river_jump_target",
            )
            _set_direct_position(entity, "_death_spawn_travel_target", movement["death_spawn_travel_target"], exact=False)
            entity._death_spawn_travel_ticks_remaining = movement["death_spawn_travel_ticks"]
            entity._ground_path_cache_backwards = movement["route_backwards"]
            _set_direct_position(entity, "_knockback_target", movement["knockback_target"], exact=False)
            entity._knockback_interrupts_combat = movement["knockback_interrupts_combat"]
            entity._knockback_velocity_work = movement["knockback_velocity_work"]
            entity.movement_phase_elapsed_ms = movement["movement_phase_elapsed_ms"]
            entity._native_avoidance = movement["native_avoidance"]
            entity._native_lane_id = movement["native_lane_id"]
            entity._native_natural_movement_active = movement["native_natural_movement_active"]
            entity._pending_movement_consumed = movement["pending_consumed"]
            entity._pending_movement_x = movement["pending_x"]
            entity._pending_movement_y = movement["pending_y"]
            route_kind = movement["route_cache_kind"]
            if route_kind == 0:
                entity.__dict__.pop("_ground_path_cache_key", None)
                entity.__dict__.pop("_native_ground_route_cells", None)
            else:
                goal = tuple(movement["route_goal"])
                entity._ground_path_cache_key = (("single", goal) if route_kind == 1 else (goal, movement["route_lane_id"], movement["route_jump_height"]))
                cells = [tuple(cell) for cell in movement["route_cells"]]
                existing = entity.__dict__.get("_native_ground_route_cells")
                if type(existing) is list:
                    undo.watch_value(existing)
                    existing[:] = cells
                else:
                    entity._native_ground_route_cells = cells
            entity._river_jump_active = movement["river_jump_active"]
            entity._river_jump_blocked = movement["river_jump_blocked"]
            entity._river_jump_duration = movement["river_jump_duration"]
            entity._river_jump_elapsed = movement["river_jump_elapsed"]
            _set_direct_position(entity, "_river_jump_origin", movement["river_jump_origin"], exact=True)
            _set_direct_position(entity, "_river_jump_target", movement["river_jump_target"], exact=False)
            entity._special_move_active = movement["special_move_active"]
            entity._special_move_consumed_tick = movement["special_move_consumed_tick"]
            entity._stun_interrupt_deferred_until_landing = movement["stun_interrupt_deferred_until_landing"]
            entity.forced_movement_active = movement["forced_movement_active"]
            entity._movement_vector_bypasses_cap = movement["vector_bypasses_cap"]
            entity._movement_vector_count = movement["vector_count"]
            entity._movement_vector_x_units = movement["vector_x_units"]
            entity._movement_vector_y_units = movement["vector_y_units"]
    if mask & _ENTITY_DELTA_COMBAT:
        combat = raw["locked_combat_state"]
        if combat is not None:
            _watch_entity_attrs(undo, entity, "initial_position")
            entity.attack_cooldown = combat["attack_cooldown"]
            entity._attack_preload_blocked = combat["attack_preload_blocked"]
            entity._attack_windup_active = combat["attack_windup_active"]
            entity._facing_x_units = combat["facing_x_units"]
            entity._facing_y_units = combat["facing_y_units"]
            entity._ground_path_backwards = combat["ground_path_backwards"]
            entity._has_attacked_once = combat["has_attacked_once"]
            _set_direct_position(entity, "initial_position", combat["initial_position"], exact=True)
            entity.last_attack_time = combat["last_attack_time"]
            entity._last_combat_target_id = combat["last_combat_target_id"]
            entity._movement_target_id = combat["movement_target_id"]
            entity._native_target_distance_discount_sq_units = combat["native_target_distance_discount_sq_units"]
    if mask & _ENTITY_DELTA_BUILDING_LIFETIME:
        lifetime = raw["building_lifetime_state"]
        if lifetime is not None:
            undo.watch_attrs(entity)
            entity.lifetime_decay_work = lifetime["decay_work"]
            entity.lifetime_elapsed = lifetime["lifetime_elapsed"]
            entity.lifetime_tick_carry_ms = lifetime["tick_carry_ms"]
    if mask & _ENTITY_DELTA_BUILDING_IMPACT:
        impact = raw["building_impact_state"]
        if impact is not None:
            undo.watch_attrs(entity)
            entity.activation_delay_remaining = impact["activation_delay_remaining"]
            entity.activation_first_hit_delay_remaining = impact["activation_first_hit_delay_remaining"]
            entity._tower_active = impact["tower_active"]
    if mask & _ENTITY_DELTA_AREA:
        area = raw["area_effect_state"]
        if area is not None:
            undo.watch_attrs(entity)
            entity.effect_snapshot_applied = area["effect_snapshot_applied"]
            entity.time_alive = area["time_alive"]
    if mask & _ENTITY_DELTA_POINT:
        point = raw["point_projectile_state"]
        if point is not None:
            _watch_entity_attrs(undo, entity, "target_position")
            entity.crown_tower_damage = point["crown_tower_damage"]
            entity.crown_tower_damage_multiplier = point["crown_tower_damage_multiplier"]
            entity.damage_wave_interval = point["damage_wave_interval"]
            entity.launch_delay = point["launch_delay"]
            entity.knockback_distance = point["knockback_distance"]
            entity._permanent_homing_disabled_by_temporary = point["permanent_homing_disabled_by_temporary"]
            entity.primary_target = None if point["primary_target_id"] is None else registry[point["primary_target_id"]]
            entity.source_entity = None if point["source_entity_id"] is None else registry[point["source_entity_id"]]
            entity.start_collision_resolved = point["start_collision_resolved"]
            entity.target_position.x = _scalar(point["target_x"])
            entity.target_position.y = _scalar(point["target_y"])
            entity.tracks_target = point["tracks_target"]
            entity.travel_speed = point["travel_speed"]
            entity._temporary_homing_remaining_ms = point["temporary_homing_remaining_ms"]
            entity._temporary_homing_target = None if point["temporary_homing_target_id"] is None else registry[point["temporary_homing_target_id"]]
            spawn = point["spawn_projectile_state"]
            if spawn is not None:
                entity.time_alive = spawn["time_alive"]
    if mask & _ENTITY_DELTA_ROLLING:
        rolling = raw["rolling_projectile_state"]
        if rolling is not None:
            undo.watch_attrs(entity)
            undo.watch_value(entity.hit_entities)
            entity.crown_tower_damage = rolling["crown_tower_damage"]
            entity.crown_tower_damage_multiplier = rolling[
                "crown_tower_damage_multiplier"
            ]
            entity.distance_traveled = rolling["distance_traveled"]
            entity.has_spawned_character = rolling["has_spawned_character"]
            entity.hit_entities.clear()
            entity.hit_entities.update(rolling["hit_entity_ids"])
            entity.time_alive = rolling["time_alive"]


def _apply_direct_delta_publication_plan(
    battle: Any,
    plan: _DirectDeltaPublicationPlan,
    *,
    entity_registry: dict[int, Any],
    prepared_births: dict[int, Any],
    projectile_group_plan: tuple[
        dict[int, tuple[set[int], tuple[int, ...]]], dict[int, int | None]
    ],
    undo: _UndoJournal,
) -> None:
    if prepared_births:
        undo.watch_value(entity_registry)
        entity_registry.update(prepared_births)
    for change in plan.entities:
        _apply_direct_delta_entity(
            battle, entity_registry[change.entity_id], change, entity_registry, undo
        )
    if projectile_group_plan[0] or projectile_group_plan[1]:
        _apply_projectile_group_plan(projectile_group_plan, entity_registry, undo)
    if plan.topology_dirty:
        undo.watch_value(battle.entities)
        battle.entities.clear()
        battle.entities.update(
            (entity_id, entity_registry[entity_id])
            for entity_id in plan.active_entity_ids
        )
    root = plan.battle
    if root is not None:
        undo.watch_attrs(battle)
        battle.double_elixir = root["double_elixir"]
        battle.dt = root["dt"]
        battle.game_over = root["game_over"]
        battle.overtime = root["overtime"]
        battle.tick = root["tick"]
        battle.time = root["time"]
        battle.triple_elixir = root["triple_elixir"]
        battle.sudden_death = root["sudden_death"]
        battle.winner = root["winner"]
        battle._sudden_death_crowns = tuple(root["sudden_death_crowns"])
        battle.next_entity_id = root["next_entity_id"]
        battle._win_conditions_dirty = root["win_conditions_dirty"]
        entity_offset = len(_ENTITY_SPARSE_ATTRIBUTE_NAMES)
        battle_presence = root["sparse_attribute_presence"]
        transient_defaults = {
            "_next_spell_cast_sequence": getattr(
                battle, "_next_spell_cast_sequence", 0
            ),
            "_defer_projectile_impacts": False,
            "_projectile_lethal_reservations": None,
            "_coalesce_alive_building_refreshes": False,
        }
        for field, value in transient_defaults.items():
            index = _BATTLE_SPARSE_ATTRIBUTE_NAMES.index(field)
            if battle_presence & (1 << (entity_offset + index)):
                setattr(battle, field, value)
    if plan.players is not None:
        for player, state in zip(battle.players, plan.players, strict=True):
            undo.watch_attrs(player)
            player.elixir = state["elixir"]
            player.max_elixir = state["max_elixir"]
            player.next_card_refill_cooldown_ms = state["next_card_refill_cooldown_ms"]
            if list(player.hand) != state["hand"]:
                undo.watch_value(player.hand)
                player.hand[:] = state["hand"]
            if list(player.cycle_queue) != state["cycle_queue"]:
                undo.watch_value(player.cycle_queue)
                player.cycle_queue.clear()
                player.cycle_queue.extend(state["cycle_queue"])
            player.king_tower_hp = _scalar(state["king_tower_hp"])
            player.left_tower_hp = _scalar(state["left_tower_hp"])
            player.right_tower_hp = _scalar(state["right_tower_hp"])
    if plan.towers is not None:
        for tower in plan.towers:
            if not tower["active"]:
                continue
            entity = entity_registry[tower["id"]]
            _watch_entity_attrs(undo, entity)
            entity.is_alive = tower["is_alive"]
            entity._tower_active = tower["is_active"]
            entity.last_attack_time = tower["last_attack_time"]
    if plan.pending_spells is not None:
        undo.watch_attrs(battle)
        undo.watch_value(battle._pending_spell_casts)
        existing = {cast.sequence: cast for cast in battle._pending_spell_casts}
        casts: list[PendingSpellCast] = []
        for state in plan.pending_spells["casts"]:
            old = existing.get(state["sequence"])
            if (
                old is not None
                and type(old.execute_at) is float
                and struct.pack("=d", old.execute_at) == struct.pack("=d", state["execute_at"])
                and old.spell_name == state["spell_name"]
                and old.player_id == state["player_id"]
                and type(old.position.x) is float
                and struct.pack("=d", old.position.x) == struct.pack("=d", state["position_x"])
                and type(old.position.y) is float
                and struct.pack("=d", old.position.y) == struct.pack("=d", state["position_y"])
            ):
                casts.append(old)
            else:
                casts.append(PendingSpellCast(
                    execute_at=state["execute_at"], sequence=state["sequence"],
                    spell_name=state["spell_name"], player_id=state["player_id"],
                    position=Position(state["position_x"], state["position_y"]),
                ))
        battle._pending_spell_casts[:] = casts
        battle._next_spell_cast_sequence = plan.pending_spells["next_sequence"]
    if plan.rng is not None:
        undo.watch_value(battle.rng)
        gauss = None if plan.rng["gauss_next"] is None else _scalar(plan.rng["gauss_next"])
        battle.rng.setstate((plan.rng["version"], tuple(plan.rng["state"]) + (plan.rng["index"],), gauss))
    if plan.cache_dirty:
        undo.watch_attrs(battle)
        _watch_cache_refresh_mutations(battle, undo)
        _refresh_python_caches(battle)
        if battle.fast_path:
            for change in plan.entities:
                if change.dirty_mask & _ENTITY_DELTA_COMBAT:
                    entity = entity_registry[change.entity_id]
                    if change.entity_id in battle.entities:
                        battle.sync_fast_target_static_entity(entity)
    for change in plan.entities:
        presence = change.presence_mask
        entity = entity_registry[change.entity_id]
        undo.watch_attrs(entity)
        for index, field in enumerate(_ENTITY_SPARSE_ATTRIBUTE_NAMES):
            if presence & (1 << index):
                if field not in entity.__dict__:
                    raise ResidentPublicationError(
                        f"resident entity {change.entity_id} omitted present attribute {field!r}"
                    )
            else:
                entity.__dict__.pop(field, None)
    if root is not None or plan.cache_dirty:
        entity_offset = len(_ENTITY_SPARSE_ATTRIBUTE_NAMES)
        for index, field in enumerate(_BATTLE_SPARSE_ATTRIBUTE_NAMES):
            if plan.battle_presence_mask & (1 << (entity_offset + index)):
                if field not in battle.__dict__:
                    raise ResidentPublicationError(
                        f"resident battle publication omitted present attribute {field!r}"
                    )
            else:
                battle.__dict__.pop(field, None)


def _apply_direct_publication_plan(
    battle: Any,
    plan: _DirectPublicationPlan,
    *,
    entity_registry: dict[int, Any],
    prepared_births: dict[int, Any],
    projectile_group_plan: tuple[
        dict[int, tuple[set[int], tuple[int, ...]]], dict[int, int | None]
    ],
    undo: _UndoJournal,
) -> None:
    undo.watch_value(entity_registry)
    undo.watch_attrs(battle)
    entity_registry.update(prepared_births)
    for entity_plan in plan.entities:
        _apply_direct_entity(
            battle,
            entity_registry[entity_plan.entity_id],
            entity_plan.raw,
            entity_registry,
            undo,
        )
    _apply_projectile_group_plan(projectile_group_plan, entity_registry, undo)

    undo.watch_value(battle.entities)
    battle.entities.clear()
    battle.entities.update(
        (entity_id, entity_registry[entity_id]) for entity_id in plan.active_entity_ids
    )

    root = plan.battle
    battle.double_elixir = root["double_elixir"]
    battle.dt = root["dt"]
    battle.game_over = root["game_over"]
    battle.overtime = root["overtime"]
    battle.tick = root["tick"]
    battle.time = root["time"]
    battle.triple_elixir = root["triple_elixir"]
    battle.sudden_death = root["sudden_death"]
    battle.winner = root["winner"]
    battle._sudden_death_crowns = tuple(root["sudden_death_crowns"])

    for player, state in zip(battle.players, plan.players, strict=True):
        undo.watch_attrs(player)
        undo.watch_value(player.hand)
        undo.watch_value(player.cycle_queue)
        player.elixir = state["elixir"]
        player.max_elixir = state["max_elixir"]
        player.next_card_refill_cooldown_ms = state["next_card_refill_cooldown_ms"]
        player.hand[:] = state["hand"]
        player.cycle_queue.clear()
        player.cycle_queue.extend(state["cycle_queue"])
        player.king_tower_hp = _scalar(state["king_tower_hp"])
        player.left_tower_hp = _scalar(state["left_tower_hp"])
        player.right_tower_hp = _scalar(state["right_tower_hp"])
    for tower in plan.towers:
        if not tower["active"]:
            continue
        entity = entity_registry[tower["id"]]
        _watch_entity_attrs(undo, entity)
        entity.is_alive = tower["is_alive"]
        entity._tower_active = tower["is_active"]
        entity.last_attack_time = tower["last_attack_time"]

    undo.watch_value(battle._pending_spell_casts)
    existing = {cast.sequence: cast for cast in battle._pending_spell_casts}
    casts: list[PendingSpellCast] = []
    for state in plan.pending_spells["casts"]:
        old = existing.get(state["sequence"])
        if (
            old is not None
            and type(old.execute_at) is float
            and old.execute_at == state["execute_at"]
            and old.spell_name == state["spell_name"]
            and old.player_id == state["player_id"]
            and type(old.position.x) is float
            and old.position.x == state["position_x"]
            and type(old.position.y) is float
            and old.position.y == state["position_y"]
        ):
            casts.append(old)
        else:
            casts.append(
                PendingSpellCast(
                    execute_at=state["execute_at"],
                    sequence=state["sequence"],
                    spell_name=state["spell_name"],
                    player_id=state["player_id"],
                    position=Position(state["position_x"], state["position_y"]),
                )
            )
    battle._pending_spell_casts[:] = casts
    battle._next_spell_cast_sequence = plan.pending_spells["next_sequence"]

    rng = plan.rng
    undo.watch_value(battle.rng)
    gauss = None if rng["gauss_next"] is None else _scalar(rng["gauss_next"])
    battle.rng.setstate((rng["version"], tuple(rng["state"]) + (rng["index"],), gauss))
    battle.next_entity_id = root["next_entity_id"]
    battle._win_conditions_dirty = root["win_conditions_dirty"]
    _watch_cache_refresh_mutations(battle, undo)
    _refresh_python_caches(battle)

    for entity_plan in plan.entities:
        entity = entity_registry[entity_plan.entity_id]
        for index, field in enumerate(_ENTITY_SPARSE_ATTRIBUTE_NAMES):
            if entity_plan.presence_mask & (1 << index):
                if field not in entity.__dict__:
                    raise ResidentPublicationError(
                        f"resident entity {entity_plan.entity_id} omitted present attribute {field!r}"
                    )
            else:
                entity.__dict__.pop(field, None)
    entity_offset = len(_ENTITY_SPARSE_ATTRIBUTE_NAMES)
    battle_mask = root["sparse_attribute_presence"]
    for index, field in enumerate(_BATTLE_SPARSE_ATTRIBUTE_NAMES):
        if battle_mask & (1 << (entity_offset + index)):
            if field not in battle.__dict__:
                raise ResidentPublicationError(
                    f"resident battle publication omitted present attribute {field!r}"
                )
        else:
            battle.__dict__.pop(field, None)


def _apply_snapshot_unchecked(
    battle: Any,
    resident: ResidentRustBattle,
    snapshot: dict[str, Any],
    *,
    publication_rows: list[dict[str, Any]],
    entity_registry: dict[int, Any],
    attest_live_action_stats: bool,
    battle_presence: dict[str, bool],
    player_rows: list[dict[str, Any]],
    prepared_births: dict[int, Any] | None = None,
    projectile_group_plan: tuple[
        dict[int, tuple[set[int], tuple[int, ...]]], dict[int, int | None]
    ]
    | None = None,
    undo: _UndoJournal | None = None,
) -> None:
    if prepared_births is None:
        prepared_births = _prepare_births(
            battle,
            resident,
            publication_rows,
            entity_registry,
            attest_live_action_stats,
        )
    if undo is not None:
        undo.watch_value(entity_registry)
        undo.watch_attrs(battle)
    entity_registry.update(prepared_births)
    _apply_publication_entity_rows(battle, publication_rows, entity_registry, undo)
    if projectile_group_plan is None:
        projectile_group_plan = _plan_projectile_groups(
            publication_rows, entity_registry
        )
    _apply_projectile_group_plan(projectile_group_plan, entity_registry, undo)
    clock = snapshot["clock"]
    battle.double_elixir = bool(clock["double_elixir"])
    battle.dt = _float(clock["dt"])
    battle.game_over = bool(clock["game_over"])
    battle.overtime = bool(clock["overtime"])
    battle.tick = int(clock["tick"])
    battle.time = _float(clock["time"])
    battle.triple_elixir = bool(clock["triple_elixir"])

    outcome = snapshot["outcome"]
    battle.sudden_death = bool(outcome["sudden_death"])
    battle.game_over = bool(outcome["game_over"])
    battle.winner = outcome["winner"]
    _set_sparse_default(
        battle,
        "_sudden_death_crowns",
        tuple(int(value) for value in outcome["sudden_death_crowns"]),
        (0, 0),
    )

    _apply_players(battle, player_rows, undo)
    _apply_entity_base(entity_registry, snapshot, undo)
    _apply_modifiers(entity_registry, snapshot, undo)
    _apply_shields(entity_registry, snapshot, undo)
    _apply_character_objects(entity_registry, snapshot, undo)
    _apply_movement(entity_registry, snapshot, undo)
    _apply_combat(entity_registry, snapshot, undo)
    _apply_buildings(entity_registry, snapshot, undo)
    _apply_area_effects(entity_registry, snapshot, undo)
    _apply_projectiles(entity_registry, snapshot, undo)
    _apply_pending_spells(battle, snapshot, undo)
    _apply_rng(battle, snapshot, undo)
    battle.next_entity_id = int(snapshot["next_entity_id"])
    battle._win_conditions_dirty = bool(snapshot["win_conditions_dirty"])
    if undo is not None:
        _watch_cache_refresh_mutations(battle, undo)
    _refresh_python_caches(battle)
    _apply_attribute_presence(
        battle,
        publication_rows,
        entity_registry,
        battle_presence,
    )


def _require_exact_projection(
    battle: Any,
    snapshot: dict[str, Any],
    *,
    stage: str,
) -> None:
    published = python_resident_semantic_snapshot(battle)
    if snapshot == published:
        return
    difference = first_snapshot_difference(snapshot, published)
    if difference is not None:
        raise ResidentPublicationError(
            f"resident publication {stage} mismatch path={difference.path} "
            f"reason={difference.reason} expected={difference.expected!r} "
            f"actual={difference.actual!r}"
        )


def _validate_typed_binding(
    battle: Any,
    publication: _TypedPublication,
    *,
    entity_registry: dict[int, Any],
) -> None:
    binding = publication.binding
    prior_ids = binding.get("prior_entity_ids")
    if type(prior_ids) is list:
        validated_prior_ids = cast(list[Any], prior_ids)
    elif type(prior_ids) is tuple:
        validated_prior_ids = list(cast(tuple[Any, ...], prior_ids))
    else:
        raise ResidentPublicationError(
            "typed publication prior entity IDs are malformed"
        )
    if any(type(value) is not int for value in validated_prior_ids):
        raise ResidentPublicationError(
            "typed publication prior entity IDs are malformed"
        )
    if tuple(entity_registry) != tuple(validated_prior_ids):
        raise ResidentPublicationError(
            "typed publication registry disagrees with the authenticated prior"
        )
    if (
        type(binding.get("prior_next_entity_id")) is not int
        or binding["prior_next_entity_id"] != battle.next_entity_id
    ):
        raise ResidentPublicationError(
            "typed publication next-entity ID disagrees with the live prior"
        )
    if binding.get("parent_node_id") != binding.get("prior_node_id") or binding.get(
        "parent_epoch"
    ) != binding.get("prior_epoch"):
        raise ResidentPublicationError("typed publication is not a direct child")
    if binding.get("checkpoint_schema_version") != 2:
        raise ResidentPublicationError("typed publication checkpoint schema changed")
    if (
        binding.get("catalog_schema_version")
        != RESIDENT_CARD_CATALOG_SCHEMA_VERSION
    ):
        raise ResidentPublicationError("typed publication catalog schema changed")
    for field in ("catalog_fingerprint", "catalog_source_fingerprint"):
        value = binding.get(field)
        if (
            type(value) is not str
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ResidentPublicationError(
                f"typed publication has malformed {field.replace('_', ' ')}"
            )
    if [row["player_id"] for row in publication.player_rows] != [0, 1]:
        raise ResidentPublicationError("typed publication player order changed")


def _require_live_application_shape(
    battle: Any,
    publication: _TypedPublication
    | _DirectPublicationPlan
    | _DirectDeltaPublicationPlan,
    entity_registry: dict[int, Any],
) -> None:
    """Cheap post-commit proof for structural/root fields owned by publication."""
    if isinstance(publication, (_DirectPublicationPlan, _DirectDeltaPublicationPlan)):
        if list(battle.entities) != list(publication.active_entity_ids):
            raise ResidentPublicationError(
                "typed publication active order was not applied"
            )
        expected_registry = (
            tuple(entity.entity_id for entity in publication.entities)
            if isinstance(publication, _DirectPublicationPlan)
            else publication.all_entity_ids
        )
        if tuple(entity_registry) != expected_registry:
            raise ResidentPublicationError(
                "typed publication registry order was not applied"
            )
        root = publication.battle
        rng = publication.rng
        expected_next_entity_id = (
            publication.battle["next_entity_id"]
            if isinstance(publication, _DirectPublicationPlan)
            else publication.next_entity_id
        )
        if (
            battle.next_entity_id != expected_next_entity_id
            or (root is not None and battle.tick != root["tick"])
            or (rng is not None and battle.rng.getstate()[1][-1] != rng["index"])
        ):
            raise ResidentPublicationError(
                "typed publication root state was not applied"
            )
        return
    snapshot = publication.snapshot
    expected_active = [
        int(row["id"])
        for row in sorted(
            (row for row in publication.publication_rows if row["active"]),
            key=lambda row: int(row["encounter_index"]),
        )
    ]
    if list(battle.entities) != expected_active:
        raise ResidentPublicationError("typed publication active order was not applied")
    if tuple(entity_registry) != tuple(
        int(row["id"]) for row in publication.publication_rows
    ):
        raise ResidentPublicationError(
            "typed publication registry order was not applied"
        )
    if (
        battle.tick != snapshot["clock"]["tick"]
        or battle.next_entity_id != snapshot["next_entity_id"]
        or battle.rng.getstate()[1][-1] != snapshot["rng"]["index"]
    ):
        raise ResidentPublicationError("typed publication root state was not applied")


def _after_typed_publication_commit(
    battle: Any,
    publication: _TypedPublication
    | _DirectPublicationPlan
    | _DirectDeltaPublicationPlan,
    entity_registry: dict[int, Any],
) -> None:
    """Final typed commit guard and focused fault-injection seam."""
    _require_live_application_shape(battle, publication, entity_registry)


def publish_complete_tick_state(
    battle: Any,
    resident: ResidentRustBattle,
    *,
    prior_resident: ResidentRustBattle,
    entity_registry: dict[int, Any],
    _prepare_guard: Callable[
        [
            _DirectPublicationPlan | _DirectDeltaPublicationPlan,
            tuple[tuple[str, Any, Any], ...],
        ],
        Any,
    ]
    | None = None,
) -> Any | None:
    """Publish one authenticated typed resident boundary with one live commit."""

    if (
        type(resident) is not ResidentRustBattle
        or type(prior_resident) is not ResidentRustBattle
    ):
        raise ResidentPublicationError(
            "publication authority requires exact resident wrapper types"
        )

    legacy_overrides = {
        "publication_entity_state_bytes",
        "publication_battle_attribute_presence_bytes",
        "publication_player_state_bytes",
        "publication_exactness_sha256",
    }.intersection(resident.__dict__)
    if legacy_overrides:
        raise ResidentPublicationError(
            "legacy publication override rejected before typed publication"
        )
    authority_overrides = {
        "prepare_publication",
        "character_action_birth_recipe",
        "character_death_spawn_birth_recipe",
        "character_action_card_stats_are_current",
        "spawn_projectile_recipe",
        "character_spawn_projectile_birth_recipe",
        "pending_spell_action_kind",
    }.intersection(resident.__dict__)
    if authority_overrides:
        raise ResidentPublicationError(
            "publication authority override rejected before typed publication"
        )

    loader_cards = battle.card_loader._cards
    loader_cards_before = list(loader_cards.items())
    raw_loader_definitions = getattr(battle.card_loader, "_card_definitions", None)
    loader_definitions: dict[Any, Any] | None = (
        cast(dict[Any, Any], raw_loader_definitions)
        if isinstance(raw_loader_definitions, dict)
        else None
    )
    loader_definitions_before = (
        None
        if not isinstance(loader_definitions, dict)
        else list(loader_definitions.items())
    )

    def restore_loader_caches() -> None:
        loader_cards.clear()
        loader_cards.update(loader_cards_before)
        if loader_definitions_before is not None and loader_definitions is not None:
            loader_definitions.clear()
            loader_definitions.update(loader_definitions_before)

    def same_items(mapping: dict[Any, Any], before: list[tuple[Any, Any]]) -> bool:
        return len(mapping) == len(before) and all(
            actual_key == expected_key and actual_value is expected_value
            for (actual_key, actual_value), (expected_key, expected_value) in zip(
                mapping.items(), before, strict=True
            )
        )

    try:
        prepared = resident.prepare_publication(prior_resident)
        envelope = prepared._consume_best_parts(_PREPARED_PUBLICATION_BEST_CONSUMER)
        if envelope["kind"] == 0:
            plan: _DirectPublicationPlan | _DirectDeltaPublicationPlan = (
                _build_direct_publication_plan(
                    envelope["full"],
                    battle=battle,
                    resident=resident,
                    entity_registry=entity_registry,
                )
            )
        else:
            plan = _build_direct_delta_publication_plan(
                envelope["delta"],
                battle=battle,
                resident=resident,
                entity_registry=entity_registry,
            )
        _validate_transient_boundary(battle)
        prepared_births = (
            _prepare_direct_births(battle, resident, plan, entity_registry)
            if isinstance(plan, _DirectPublicationPlan)
            else _prepare_direct_delta_births(battle, resident, plan, entity_registry)
        )
        provisional_registry = dict(entity_registry)
        provisional_registry.update(prepared_births)
        if isinstance(plan, _DirectPublicationPlan):
            _validate_direct_bound_entities(plan, provisional_registry)
            projectile_group_plan = _plan_direct_projectile_groups(
                plan, provisional_registry
            )
        else:
            _validate_direct_delta_bound_entities(plan, provisional_registry)
            projectile_group_plan = _plan_direct_delta_projectile_groups(
                plan, provisional_registry
            )
        if not same_items(loader_cards, loader_cards_before) or (
            loader_definitions_before is not None
            and loader_definitions is not None
            and not same_items(loader_definitions, loader_definitions_before)
        ):
            restore_loader_caches()
            raise ResidentPublicationError(
                "typed publication preflight mutated the card-loader cache"
            )
    except ResidentPublicationError:
        restore_loader_caches()
        raise
    except (AttributeError, KeyError, OverflowError, TypeError, ValueError) as error:
        restore_loader_caches()
        raise ResidentPublicationError(
            "typed resident publication is malformed"
        ) from error

    undo = _live_publication_undo_journal(battle, entity_registry)
    prepared_guard: Any | None = None
    try:
        if isinstance(plan, _DirectPublicationPlan):
            _apply_direct_publication_plan(
                battle,
                plan,
                entity_registry=entity_registry,
                prepared_births=prepared_births,
                projectile_group_plan=projectile_group_plan,
                undo=undo,
            )
        else:
            _apply_direct_delta_publication_plan(
                battle,
                plan,
                entity_registry=entity_registry,
                prepared_births=prepared_births,
                projectile_group_plan=projectile_group_plan,
                undo=undo,
            )
        _after_typed_publication_commit(battle, plan, entity_registry)
        if _prepare_guard is not None:
            prepared_guard = _prepare_guard(plan, undo.guard_write_receipt())
    except Exception as commit_error:
        try:
            undo.rollback()
        except Exception as rollback_error:
            raise ResidentPublicationError(
                "resident publication commit and rollback both failed; "
                "the Python battle is poisoned"
            ) from rollback_error
        raise ResidentPublicationError(
            "resident publication commit failed; the Python battle was "
            "rolled back to its exact pre-publication projection"
        ) from commit_error
    return prepared_guard
