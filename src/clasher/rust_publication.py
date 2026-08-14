from __future__ import annotations

import struct
from collections.abc import Iterable
from typing import Any

from .arena import Position
from .battle import PendingSpellCast
from .differential import first_snapshot_difference
from .entities import Projectile
from .rust_core import ResidentRustBattle
from .rust_differential import (
    RESIDENT_SEMANTIC_SCHEMA_VERSION,
    python_resident_semantic_snapshot,
    rust_resident_semantic_snapshot,
)


class ResidentPublicationError(RuntimeError):
    """The resident state cannot be published without changing Python identity."""


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


def _validate_row_topology(
    current: dict[str, Any],
    resident: dict[str, Any],
) -> None:
    sections = (
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
        "towers",
    )
    for section in sections:
        current_keys = [
            (
                row.get("id"),
                row.get("encounter_index"),
                row.get("opcode_index"),
            )
            for row in current[section]
        ]
        resident_keys = [
            (
                row.get("id"),
                row.get("encounter_index"),
                row.get("opcode_index"),
            )
            for row in resident[section]
        ]
        if current_keys != resident_keys:
            raise ResidentPublicationError(
                f"resident publication changed {section} row topology: "
                f"python={current_keys!r} resident={resident_keys!r}"
            )
    current_shield_widths = [
        len(row["shields"]) for row in current["shields"]
    ]
    resident_shield_widths = [
        len(row["shields"]) for row in resident["shields"]
    ]
    if current_shield_widths != resident_shield_widths:
        raise ResidentPublicationError(
            "resident publication changed shield row topology"
        )


def _validate_structure(
    battle: Any,
    snapshot: dict[str, Any],
    *,
    current_snapshot: dict[str, Any] | None = None,
) -> None:
    _validate_transient_boundary(battle)
    if snapshot.get("schema_version") != RESIDENT_SEMANTIC_SCHEMA_VERSION:
        raise ResidentPublicationError(
            "resident semantic schema changed before publication"
        )

    entity_rows = snapshot["entities"]
    resident_ids = [int(row["id"]) for row in entity_rows]
    python_ids = [int(entity_id) for entity_id in battle.entities]
    if resident_ids != python_ids:
        raise ResidentPublicationError(
            "resident publication rejected an entity birth, death, cleanup, "
            f"or order change: python={python_ids!r} resident={resident_ids!r}"
        )
    if int(snapshot["next_entity_id"]) != int(battle.next_entity_id):
        raise ResidentPublicationError(
            "resident publication rejected entity allocation within the native interval"
        )
    for encounter_index, row in enumerate(entity_rows):
        if int(row["encounter_index"]) != encounter_index:
            raise ResidentPublicationError(
                "resident publication rejected changed encounter ordering"
            )
    if current_snapshot is not None:
        _validate_row_topology(current_snapshot, snapshot)

    player_ids = [int(row["player_id"]) for row in snapshot["players"]]
    if player_ids != [int(player.player_id) for player in battle.players]:
        raise ResidentPublicationError(
            "resident publication rejected changed player ordering"
        )

    active_ids = set(resident_ids)
    for row in snapshot["point_projectiles"]:
        for field in (
            "primary_target_id",
            "source_entity_id",
            "temporary_homing_target_id",
        ):
            reference_id = row[field]
            if reference_id is not None and int(reference_id) not in active_ids:
                raise ResidentPublicationError(
                    "resident publication rejected an inactive projectile "
                    f"reference: projectile={row['id']} field={field} "
                    f"target={reference_id}"
                )
    for row in snapshot["movement"]:
        if row["route_kind"] == "unsupported":
            raise ResidentPublicationError(
                f"resident publication rejected unsupported route cache for id {row['id']}"
            )

    projectile_rows = _rows_by_id(
        snapshot["point_projectiles"], label="point projectile"
    )
    group_sets: dict[int, set[int]] = {}
    for entity_id, row in projectile_rows.items():
        projectile = battle.entities[entity_id]
        if type(projectile) is not Projectile:
            raise ResidentPublicationError(
                f"resident point projectile id {entity_id} has incompatible Python type"
            )
        group_id = row["damage_group_id"]
        current = projectile.damage_group_hit_entity_ids
        if group_id is None:
            if current is not None:
                raise ResidentPublicationError(
                    f"resident publication changed projectile group topology for id {entity_id}"
                )
            continue
        if current is None:
            raise ResidentPublicationError(
                f"resident publication changed projectile group topology for id {entity_id}"
            )
        group_key = int(group_id)
        previous = group_sets.setdefault(group_key, current)
        if previous is not current:
            raise ResidentPublicationError(
                f"resident publication changed projectile group aliasing for group {group_key}"
            )
    resident_group_ids = {
        int(row["group_id"]) for row in snapshot["projectile_damage_groups"]
    }
    if resident_group_ids != set(group_sets):
        raise ResidentPublicationError(
            "resident publication changed projectile damage-group membership"
        )


def _apply_players(battle: Any, snapshot: dict[str, Any]) -> None:
    for player, row in zip(battle.players, snapshot["players"], strict=True):
        player.elixir = _float(row["elixir"])
        player.max_elixir = _float(row["max_elixir"])
        player.next_card_refill_cooldown_ms = int(
            row["next_card_refill_cooldown_ms"]
        )
        player.hand[:] = row["hand"]
        player.cycle_queue.clear()
        player.cycle_queue.extend(row["cycle_queue"])
        player.king_tower_hp = _float(row["king_tower_hp"])
        player.left_tower_hp = _float(row["left_tower_hp"])
        player.right_tower_hp = _float(row["right_tower_hp"])


def _apply_entity_base(battle: Any, snapshot: dict[str, Any]) -> None:
    for row in snapshot["entities"]:
        entity = battle.entities[int(row["id"])]
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


def _apply_modifiers(battle: Any, snapshot: dict[str, Any]) -> None:
    for row in snapshot["modifiers"]:
        entity = battle.entities[int(row["id"])]
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


def _apply_shields(battle: Any, snapshot: dict[str, Any]) -> None:
    for row in snapshot["shields"]:
        entity = battle.entities[int(row["id"])]
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


def _apply_character_objects(battle: Any, snapshot: dict[str, Any]) -> None:
    for row in snapshot["character_objects"]:
        entity = battle.entities[int(row["id"])]
        entity._death_spawn_target_immunity_elapsed_ms = int(
            row["death_spawn_target_immunity_elapsed_ms"]
        )
        entity.deploy_delay_remaining = _scalar(row["deploy_delay_remaining"])
        entity.placement_pending = bool(row["placement_pending"])
        entity._spawn_hook_fired = bool(row["spawn_hook_fired"])
        entity._spawn_hook_pending = bool(row["spawn_hook_pending"])


def _apply_movement(battle: Any, snapshot: dict[str, Any]) -> None:
    for row in snapshot["movement"]:
        entity = battle.entities[int(row["id"])]
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


def _apply_combat(battle: Any, snapshot: dict[str, Any]) -> None:
    for row in snapshot["locked_combat"]:
        entity = battle.entities[int(row["id"])]
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
        entity.target_id = row["target_id"]


def _apply_buildings(battle: Any, snapshot: dict[str, Any]) -> None:
    for row in snapshot["building_lifetime"]:
        entity = battle.entities[int(row["id"])]
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
        tower = battle.entities[int(row["id"])]
        tower.is_alive = bool(row["is_alive"])
        tower._tower_active = bool(row["is_active"])
        tower.last_attack_time = _float(row["last_attack_time"])


def _apply_area_effects(battle: Any, snapshot: dict[str, Any]) -> None:
    for row in snapshot["area_effects"]:
        entity = battle.entities[int(row["id"])]
        entity.effect_snapshot_applied = bool(row["effect_snapshot_applied"])
        entity.is_alive = bool(row["is_alive"])
        entity.position.x = _scalar(row["position_x"])
        entity.position.y = _scalar(row["position_y"])
        entity.time_alive = _scalar(row["time_alive"])


def _apply_projectiles(battle: Any, snapshot: dict[str, Any]) -> None:
    group_sets: dict[int, set[int]] = {}
    for row in snapshot["point_projectiles"]:
        entity = battle.entities[int(row["id"])]
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
        entity._permanent_homing_disabled_by_temporary = bool(
            row["permanent_homing_disabled_by_temporary"]
        )
        entity.position.x = _scalar(row["position_x"])
        entity.position.y = _scalar(row["position_y"])
        entity.primary_target = (
            None
            if row["primary_target_id"] is None
            else battle.entities[int(row["primary_target_id"])]
        )
        entity.source_entity = (
            None
            if row["source_entity_id"] is None
            else battle.entities[int(row["source_entity_id"])]
        )
        entity.start_collision_resolved = bool(row["start_collision_resolved"])
        entity.target_position.x = _scalar(row["target_position_x"])
        entity.target_position.y = _scalar(row["target_position_y"])
        entity.tracks_target = bool(row["tracks_target"])
        entity.travel_speed = _scalar(row["travel_speed"])
        entity._temporary_homing_remaining_ms = int(
            row["temporary_homing_remaining_ms"]
        )
        entity._temporary_homing_target = (
            None
            if row["temporary_homing_target_id"] is None
            else battle.entities[int(row["temporary_homing_target_id"])]
        )
        group_id = row["damage_group_id"]
        if group_id is not None:
            group_sets[int(group_id)] = entity.damage_group_hit_entity_ids

    for row in snapshot["projectile_damage_groups"]:
        hit_ids = group_sets[int(row["group_id"])]
        if hit_ids is None:  # pragma: no cover - structural preflight invariant
            raise AssertionError("validated projectile group disappeared")
        hit_ids.clear()
        hit_ids.update(int(entity_id) for entity_id in row["hit_entity_ids"])


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
    battle._next_spell_cast_sequence = int(spell_state["next_sequence"])


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


def _apply_snapshot_unchecked(battle: Any, snapshot: dict[str, Any]) -> None:
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
    battle._sudden_death_crowns = tuple(
        int(value) for value in outcome["sudden_death_crowns"]
    )

    _apply_players(battle, snapshot)
    _apply_entity_base(battle, snapshot)
    _apply_modifiers(battle, snapshot)
    _apply_shields(battle, snapshot)
    _apply_character_objects(battle, snapshot)
    _apply_movement(battle, snapshot)
    _apply_combat(battle, snapshot)
    _apply_buildings(battle, snapshot)
    _apply_area_effects(battle, snapshot)
    _apply_projectiles(battle, snapshot)
    _apply_pending_spells(battle, snapshot)
    _apply_rng(battle, snapshot)
    battle.next_entity_id = int(snapshot["next_entity_id"])
    battle._win_conditions_dirty = bool(snapshot["win_conditions_dirty"])
    _refresh_python_caches(battle)


def _require_exact_projection(
    battle: Any,
    snapshot: dict[str, Any],
    *,
    stage: str,
) -> None:
    published = python_resident_semantic_snapshot(battle)
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
) -> None:
    """Atomically stage and publish one resident decision-boundary snapshot.

    This first milestone intentionally rejects any interval that allocates,
    removes, reorders, or tombstones an entity. Existing characters, point
    projectiles, area effects, players, references, and shared projectile
    damage-group sets are updated in place. The original battle is untouched
    unless an isolated clone reproduces the resident semantic projection
    exactly.
    """

    original_snapshot = python_resident_semantic_snapshot(battle)
    snapshot = rust_resident_semantic_snapshot(resident)
    _validate_structure(
        battle,
        snapshot,
        current_snapshot=original_snapshot,
    )

    try:
        staged = battle.clone()
        _validate_structure(staged, snapshot)
        _apply_snapshot_unchecked(staged, snapshot)
        _require_exact_projection(staged, snapshot, stage="staging")
    except ResidentPublicationError:
        raise
    except Exception as staging_error:
        raise ResidentPublicationError(
            "resident publication staging failed before live Python mutation"
        ) from staging_error

    try:
        _apply_snapshot_unchecked(battle, snapshot)
        _require_exact_projection(battle, snapshot, stage="commit")
    except Exception as commit_error:
        try:
            _validate_structure(battle, original_snapshot)
            _apply_snapshot_unchecked(battle, original_snapshot)
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
