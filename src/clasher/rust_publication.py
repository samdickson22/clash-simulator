from __future__ import annotations

import copy
import hashlib
import json
import random
import struct
from collections import deque
from collections.abc import Iterable
from typing import Any, cast

import numpy as np

from .arena import Position
from .battle import PendingSpellCast
from .differential import _normalize, first_snapshot_difference
from .entities import AreaEffect, Projectile, Troop
from .mechanics.shared.death_area import DeathAreaEffect
from .mechanics.shared.death_effects import DeathDamage, DeathSpawn
from .rust_core import ResidentRustBattle
from .rust_differential import (
    RESIDENT_SEMANTIC_SCHEMA_VERSION,
    python_resident_semantic_snapshot,
    rust_resident_semantic_snapshot,
)


class ResidentPublicationError(RuntimeError):
    """The resident state cannot be published without changing Python identity."""


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
        if not self._record("attrs", owner, dict(owner.__dict__)):
            return
        for value in owner.__dict__.values():
            self.watch_value(value)

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


def _publication_undo_journal(
    battle: Any,
    entity_registry: dict[int, Any],
) -> _UndoJournal:
    journal = _UndoJournal()
    journal.watch_attrs(battle)
    journal.watch_value(battle.entities)
    journal.watch_value(entity_registry)
    journal.watch_attrs(battle.card_loader)
    journal.watch_value(battle.card_loader._cards)
    card_definitions = getattr(battle.card_loader, "_card_definitions", None)
    if isinstance(card_definitions, dict):
        journal.watch_value(card_definitions)
    for player in battle.players:
        journal.watch_attrs(player)
        journal.watch_value(player.hand)
        journal.watch_value(player.cycle_queue)
    for entity in entity_registry.values():
        journal.watch_attrs(entity)
        for mechanic in getattr(entity, "mechanics", ()):
            journal.watch_attrs(mechanic)
    for pending_cast in battle._pending_spell_casts:
        journal.watch_attrs(pending_cast)
        journal.watch_attrs(pending_cast.position)
    return journal


def _scalar(value: Any) -> int | float:
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
        area_state = row["area_effect_state"]
        character_birth = row["character_birth"]
        if (
            sum(
                value is not None
                for value in (point_state, area_state, character_birth)
            )
            != 1
        ):
            raise ResidentPublicationError(
                f"resident publication has unsupported birth recipe for id {entity_id}"
            )
        expected_type = (
            "clasher.entities.Projectile"
            if point_state is not None
            else (
                "clasher.entities.AreaEffect"
                if area_state is not None
                else "clasher.entities.Troop"
            )
        )
        if row["python_type"] != expected_type:
            raise ResidentPublicationError(
                f"resident publication birth type mismatch for id {entity_id}: "
                f"expected={expected_type!r} actual={row['python_type']!r}"
            )
        if character_birth is not None and int(row["entity_kind"]) != 0:
            raise ResidentPublicationError(
                f"resident character birth {entity_id} is not a troop entity"
            )

    character_groups: dict[
        tuple[str, int],
        list[tuple[int, dict[str, Any]]],
    ] = {}
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
        if kind == "death_spawn":
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
            recipe = resident.character_action_birth_recipe(lookup_name)
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
        if len(common) != 1 or group_id != min(entity_id for entity_id, _ in members):
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



def _apply_players(battle: Any, rows: list[dict[str, Any]]) -> None:
    for player, row in zip(battle.players, rows, strict=True):
        player.elixir = _float(row["elixir"])
        player.max_elixir = _float(row["max_elixir"])
        player.next_card_refill_cooldown_ms = int(
            row["next_card_refill_cooldown_ms"]
        )
        player.hand[:] = row["hand"]
        player.cycle_queue.clear()
        player.cycle_queue.extend(row["cycle_queue"])
        player.king_tower_hp = _scalar(row["king_tower_hp"])
        player.left_tower_hp = _scalar(row["left_tower_hp"])
        player.right_tower_hp = _scalar(row["right_tower_hp"])


def _apply_entity_base(
    entity_registry: dict[int, Any], snapshot: dict[str, Any]
) -> None:
    for row in snapshot["entities"]:
        entity = entity_registry[int(row["id"])]
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
        entity.target_id = (
            None if row["target_id"] is None else int(row["target_id"])
        )


def _apply_modifiers(
    entity_registry: dict[int, Any], snapshot: dict[str, Any]
) -> None:
    for row in snapshot["modifiers"]:
        entity = entity_registry[int(row["id"])]
        entity.attack_speed_buff_multiplier = _scalar(
            row["attack_speed_buff_multiplier"]
        )
        entity.attack_speed_debuff_multiplier = _scalar(
            row["attack_speed_debuff_multiplier"]
        )
        entity._haste_effects[:] = [
            tuple(_scalar(value) for value in effect)
            for effect in row["haste_effects"]
        ]
        entity.haste_timer = _scalar(row["haste_timer"])
        entity.movement_mode_multiplier = _scalar(
            row["movement_mode_multiplier"]
        )
        entity.movement_speed_buff_multiplier = _scalar(
            row["movement_speed_buff_multiplier"]
        )
        entity.original_speed = (
            None
            if row["original_speed"] is None
            else _scalar(row["original_speed"])
        )
        entity._slow_effects[:] = [
            tuple(_scalar(value) for value in effect)
            for effect in row["slow_effects"]
        ]
        entity.slow_multiplier = _scalar(row["slow_multiplier"])
        entity.slow_timer = _scalar(row["slow_timer"])
        entity.spawn_speed_buff_multiplier = _scalar(
            row["spawn_speed_buff_multiplier"]
        )
        entity.spawn_speed_debuff_multiplier = _scalar(
            row["spawn_speed_debuff_multiplier"]
        )
        entity.speed = _scalar(row["speed"])
        entity.stun_timer = _scalar(row["stun_timer"])


def _apply_shields(
    entity_registry: dict[int, Any], snapshot: dict[str, Any]
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
        entity._shield_break_count = int(row["shield_break_count"])
        for shield, shield_row in zip(shields, row["shields"], strict=True):
            shield.current_shield = _scalar(shield_row["current_shield"])


def _apply_character_objects(
    entity_registry: dict[int, Any], snapshot: dict[str, Any]
) -> None:
    for row in snapshot["character_objects"]:
        entity = entity_registry[int(row["id"])]
        entity._death_spawn_target_immunity_elapsed_ms = int(
            row["death_spawn_target_immunity_elapsed_ms"]
        )
        entity.deploy_delay_remaining = _scalar(row["deploy_delay_remaining"])
        entity.placement_pending = bool(row["placement_pending"])
        entity._spawn_hook_fired = bool(row["spawn_hook_fired"])
        entity._spawn_hook_pending = bool(row["spawn_hook_pending"])


def _apply_movement(
    entity_registry: dict[int, Any], snapshot: dict[str, Any]
) -> None:
    for row in snapshot["movement"]:
        entity = entity_registry[int(row["id"])]
        _set_position(entity, "_death_spawn_travel_target", row["death_spawn_travel_target"])
        entity._death_spawn_travel_ticks_remaining = int(
            row["death_spawn_travel_ticks"]
        )
        entity._facing_x_units = int(row["facing_x_units"])
        entity._facing_y_units = int(row["facing_y_units"])
        entity._ground_path_backwards = bool(row["ground_path_backwards"])
        entity._ground_path_cache_backwards = bool(row["route_backwards"])
        _set_position(entity, "_knockback_target", row["knockback_target"])
        entity._knockback_interrupts_combat = bool(
            row["knockback_interrupts_combat"]
        )
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
        entity._special_move_consumed_tick = bool(
            row["special_move_consumed_tick"]
        )
        entity._stun_interrupt_deferred_until_landing = bool(
            row["stun_interrupt_deferred_until_landing"]
        )
        entity.forced_movement_active = bool(row["forced_movement_active"])
        entity._movement_vector_bypasses_cap = bool(row["vector_bypasses_cap"])
        entity._movement_vector_count = int(row["vector_count"])
        entity._movement_vector_x_units = int(row["vector_x_units"])
        entity._movement_vector_y_units = int(row["vector_y_units"])


def _apply_combat(
    entity_registry: dict[int, Any], snapshot: dict[str, Any]
) -> None:
    for row in snapshot["locked_combat"]:
        entity = entity_registry[int(row["id"])]
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
    entity_registry: dict[int, Any], snapshot: dict[str, Any]
) -> None:
    for row in snapshot["building_lifetime"]:
        entity = entity_registry[int(row["id"])]
        entity.activation_delay_remaining = _scalar(
            row["activation_delay_remaining"]
        )
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
        tower.is_alive = bool(row["is_alive"])
        tower._tower_active = bool(row["is_active"])
        tower.last_attack_time = _float(row["last_attack_time"])


def _apply_area_effects(
    entity_registry: dict[int, Any], snapshot: dict[str, Any]
) -> None:
    for row in snapshot["area_effects"]:
        entity = entity_registry[int(row["id"])]
        _apply_area_effect_row(entity, row)


def _apply_area_effect_row(entity: Any, row: dict[str, Any]) -> None:
    entity.effect_snapshot_applied = bool(row["effect_snapshot_applied"])
    entity.is_alive = bool(row["is_alive"])
    entity.position.x = _scalar(row["position_x"])
    entity.position.y = _scalar(row["position_y"])
    entity.time_alive = _scalar(row["time_alive"])


def _apply_projectiles(
    entity_registry: dict[int, Any], snapshot: dict[str, Any]
) -> None:
    group_sets: dict[int, set[int]] = {}
    for row in snapshot["point_projectiles"]:
        entity = entity_registry[int(row["id"])]
        _apply_projectile_row(entity, row, entity_registry)
        group_id = row["damage_group_id"]
        if group_id is not None:
            group_sets[int(group_id)] = entity.damage_group_hit_entity_ids

    for row in snapshot["projectile_damage_groups"]:
        hit_ids = group_sets[int(row["group_id"])]
        if hit_ids is None:  # pragma: no cover - structural preflight invariant
            raise AssertionError("validated projectile group disappeared")
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
    entity.crown_tower_damage_multiplier = _scalar(
        row["crown_tower_damage_multiplier"]
    )
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


def _apply_pending_spells(battle: Any, snapshot: dict[str, Any]) -> None:
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


def _apply_rng(battle: Any, snapshot: dict[str, Any]) -> None:
    state = snapshot["rng"]
    inner = tuple(int(word) for word in state["state"]) + (int(state["index"]),)
    gauss = None if state["gauss_next"] is None else _float(state["gauss_next"])
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
        crown_tower_damage_multiplier=_float(
            state["crown_tower_damage_multiplier"]
        ),
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
    shared_card_stats: dict[tuple[str, int], Any],
    attest_live_action_stats: bool,
) -> Troop:
    provenance = row["character_birth"]
    kind = str(provenance["kind"])
    group_key = (kind, int(provenance["group_id"]))
    fingerprint = str(provenance["template_fingerprint"]).lower()
    if kind == "catalog_action":
        lookup_name = str(provenance["lookup_name"])
        recipe = resident.character_action_birth_recipe(lookup_name)
        if recipe is None:  # pragma: no cover - structural preflight invariant
            raise AssertionError("validated action birth recipe disappeared")
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
            stats = battle.card_loader.get_card(lookup_name)
            if stats is None or str(stats.name) != recipe.effective_name:
                raise ResidentPublicationError(
                    f"catalog birth lookup {lookup_name!r} changed during publication"
                )
            shared_card_stats[group_key] = stats
    else:
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

    prototype = recipe.prototype
    memo: dict[int, Any] = {id(prototype.card_stats): stats}
    prototype_battle = getattr(prototype, "battle_state", None)
    if prototype_battle is not None:
        memo[id(prototype_battle)] = battle
    entity = copy.deepcopy(prototype, memo)
    if type(entity) is not Troop:
        raise ResidentPublicationError(
            f"resident character birth recipe produced {type(entity)!r}"
        )
    entity.id = int(row["id"])
    entity.player_id = int(row["player_id"])
    entity.card_stats = stats
    cast(Any, entity).battle_state = battle
    return entity


def _materialize_births(
    battle: Any,
    resident: ResidentRustBattle,
    publication_rows: list[dict[str, Any]],
    entity_registry: dict[int, Any],
    attest_live_action_stats: bool,
) -> None:
    pending: dict[int, Any] = {}
    available = dict(entity_registry)
    shared_card_stats: dict[tuple[str, int], Any] = {}
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
    entity_registry.update(pending)


def _apply_publication_entity_rows(
    battle: Any,
    publication_rows: list[dict[str, Any]],
    entity_registry: dict[int, Any],
) -> None:
    for row in publication_rows:
        entity = entity_registry[int(row["id"])]
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
            _apply_projectile_row(entity, point_state, entity_registry)
        area_state = row["area_effect_state"]
        if area_state is not None:
            _apply_area_effect_row(entity, area_state)
        modifier_state = row["modifier_state"]
        if modifier_state is not None:
            _apply_modifiers(entity_registry, {"modifiers": [modifier_state]})
        shield_state = row["shield_state"]
        if shield_state is not None:
            _apply_shields(entity_registry, {"shields": [shield_state]})
        character_state = row["character_object_state"]
        if character_state is not None:
            _apply_character_objects(
                entity_registry,
                {"character_objects": [character_state]},
            )
        movement_state = row["movement_state"]
        if movement_state is not None:
            _apply_movement(entity_registry, {"movement": [movement_state]})
        combat_state = row["locked_combat_state"]
        if combat_state is not None:
            _apply_combat(
                entity_registry,
                {"locked_combat": [combat_state]},
            )
        building_lifetime_state = row["building_lifetime_state"]
        if building_lifetime_state is not None:
            _apply_buildings(
                entity_registry,
                {
                    "building_lifetime": [building_lifetime_state],
                    "towers": [],
                },
            )

    active_rows = sorted(
        (row for row in publication_rows if bool(row["active"])),
        key=lambda row: int(row["encounter_index"]),
    )
    battle.entities.clear()
    battle.entities.update(
        (int(row["id"]), entity_registry[int(row["id"])])
        for row in active_rows
    )


def _prepare_projectile_groups(
    publication_rows: list[dict[str, Any]],
    entity_registry: dict[int, Any],
) -> None:
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

    chosen_sets: dict[int, set[int]] = {}
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
        shared_hit_ids.clear()
        shared_hit_ids.update(group_hit_ids[group_id])
        chosen_sets[group_id] = shared_hit_ids

    for row in publication_rows:
        state = row["point_projectile_state"]
        if state is None:
            continue
        projectile = entity_registry[int(row["id"])]
        group_id = state["damage_group_id"]
        projectile.damage_group_hit_entity_ids = (
            None if group_id is None else chosen_sets[int(group_id)]
        )


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
) -> None:
    _materialize_births(
        battle,
        resident,
        publication_rows,
        entity_registry,
        attest_live_action_stats,
    )
    _apply_publication_entity_rows(battle, publication_rows, entity_registry)
    _prepare_projectile_groups(publication_rows, entity_registry)
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

    _apply_players(battle, player_rows)
    _apply_entity_base(entity_registry, snapshot)
    _apply_modifiers(entity_registry, snapshot)
    _apply_shields(entity_registry, snapshot)
    _apply_character_objects(entity_registry, snapshot)
    _apply_movement(entity_registry, snapshot)
    _apply_combat(entity_registry, snapshot)
    _apply_buildings(entity_registry, snapshot)
    _apply_area_effects(entity_registry, snapshot)
    _apply_projectiles(entity_registry, snapshot)
    _apply_pending_spells(battle, snapshot)
    _apply_rng(battle, snapshot)
    battle.next_entity_id = int(snapshot["next_entity_id"])
    battle._win_conditions_dirty = bool(snapshot["win_conditions_dirty"])
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


def publish_complete_tick_state(
    battle: Any,
    resident: ResidentRustBattle,
    *,
    prior_resident: ResidentRustBattle,
    entity_registry: dict[int, Any],
) -> None:
    """Atomically stage and publish one resident decision-boundary snapshot.

    The registry is append-only and retains inactive Python tombstones so
    projectile/source references keep their object identities after cleanup.
    Native PointProjectile and DeathArea births are reconstructed off-dict,
    then all state is staged on an isolated clone before live mutation.
    """

    original_snapshot = python_resident_semantic_snapshot(battle)
    undo = _publication_undo_journal(battle, entity_registry)
    snapshot = rust_resident_semantic_snapshot(resident)
    try:
        original_publication_rows = _publication_rows(prior_resident)
        entity_payload = resident.publication_entity_state_bytes()
        battle_presence_payload = (
            resident.publication_battle_attribute_presence_bytes()
        )
        player_payload = resident.publication_player_state_bytes()
        publication_rows = _decode_publication_rows(entity_payload)
        battle_presence = _decode_battle_attribute_presence(
            battle_presence_payload
        )
        player_rows = _decode_publication_player_rows(player_payload)
        _validate_entity_attribute_presence(publication_rows)
        _require_publication_exactness_attestation(
            resident,
            entity_payload,
            battle_presence_payload,
            player_payload,
        )
        if set(entity_registry) != {
            int(row["id"]) for row in original_publication_rows
        }:
            raise ResidentPublicationError(
                "resident publication registry disagrees with the prior resident"
            )
        _validate_structure(
            battle,
            snapshot,
            resident=resident,
            attest_live_action_stats=True,
            publication_rows=publication_rows,
            entity_registry=entity_registry,
        )
    except ResidentPublicationError:
        undo.rollback()
        raise
    except (AttributeError, KeyError, OverflowError, TypeError, ValueError) as error:
        undo.rollback()
        raise ResidentPublicationError(
            "resident publication entity payload is malformed"
        ) from error

    try:
        staged = battle.clone()
        staged_registry = _clone_registry(battle, staged, entity_registry)
        _validate_structure(
            staged,
            snapshot,
            resident=resident,
            attest_live_action_stats=False,
            publication_rows=publication_rows,
            entity_registry=staged_registry,
        )
        _apply_snapshot_unchecked(
            staged,
            resident,
            snapshot,
            publication_rows=publication_rows,
            entity_registry=staged_registry,
            attest_live_action_stats=False,
            battle_presence=battle_presence,
            player_rows=player_rows,
        )
        _require_exact_projection(staged, snapshot, stage="staging")
    except ResidentPublicationError:
        undo.rollback()
        raise
    except Exception as staging_error:
        undo.rollback()
        raise ResidentPublicationError(
            "resident publication staging failed before live Python mutation"
        ) from staging_error

    try:
        _apply_snapshot_unchecked(
            battle,
            resident,
            snapshot,
            publication_rows=publication_rows,
            entity_registry=entity_registry,
            attest_live_action_stats=True,
            battle_presence=battle_presence,
            player_rows=player_rows,
        )
        _require_exact_projection(battle, snapshot, stage="commit")
    except Exception as commit_error:
        try:
            undo.rollback()
            _require_exact_projection(
                battle,
                original_snapshot,
                stage="rollback",
            )
        except Exception as rollback_error:
            raise ResidentPublicationError(
                "resident publication commit and rollback both failed; "
                "the Python battle is poisoned"
            ) from rollback_error
        raise ResidentPublicationError(
            "resident publication commit failed; the Python battle was "
            "rolled back to its exact pre-publication projection"
        ) from commit_error
