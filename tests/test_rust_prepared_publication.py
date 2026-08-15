from __future__ import annotations

import json
import random
import struct
from types import MappingProxyType
from typing import Any

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rust_core import (
    ResidentPreparedPublication,
    ResidentRustBattle,
    _decode_prepared_publication_parts,
    rust_core_available,
)
from clasher.rust_differential import rust_resident_semantic_snapshot

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _exact_scalar(value: object) -> dict[str, object]:
    tag, integer, bits = value  # type: ignore[misc]
    if tag == 0:
        return {"kind": "int", "value": integer}
    assert tag == 1
    return {"bits": f"{bits:016x}", "kind": "float"}


def _float_scalar(value: float) -> dict[str, object]:
    bits = struct.unpack(">Q", struct.pack(">d", value))[0]
    return {"bits": f"{bits:016x}", "kind": "float"}


def _optional_float_scalar(value: float | None) -> dict[str, object] | None:
    return None if value is None else _float_scalar(value)


def _semantic_float_scalar(value: object) -> dict[str, object]:
    tag, integer, bits = value  # type: ignore[misc]
    number = float(integer) if tag == 0 else struct.unpack(">d", struct.pack(">Q", bits))[0]
    return _float_scalar(number)


def _typed_basic_semantic(parts: MappingProxyType[str, Any]) -> dict[str, Any]:
    active = [row for row in parts["entities"] if row["active"]]
    players = [
        {
            "cycle_queue": list(row["cycle_queue"]),
            "elixir": _float_scalar(row["elixir"]),
            "hand": list(row["hand"]),
            "king_tower_hp": _semantic_float_scalar(row["king_tower_hp"]),
            "left_tower_hp": _semantic_float_scalar(row["left_tower_hp"]),
            "max_elixir": _float_scalar(row["max_elixir"]),
            "next_card_refill_cooldown_ms": row["next_card_refill_cooldown_ms"],
            "player_id": row["player_id"],
            "right_tower_hp": _semantic_float_scalar(row["right_tower_hp"]),
        }
        for row in parts["players"]
    ]
    towers = [
        {
            "hp": _semantic_float_scalar(row["hp"]),
            "hp_milli": row["hp_milli"],
            "id": row["id"],
            "is_active": row["is_active"],
            "is_alive": row["is_alive"],
            "last_attack_time": _float_scalar(row["last_attack_time"]),
            "player_id": row["player_id"],
            "slot": row["slot"],
        }
        for row in parts["towers"]
        if row["active"]
    ]
    entities = [
        {
            "card_name": row["card_name"],
            "encounter_index": row["encounter_index"],
            "entity_kind": row["entity_kind"],
            "freeze_expiry_time": _float_scalar(row["freeze_expiry_time"]),
            "hitpoints": _exact_scalar(row["hitpoints"]),
            "id": row["id"],
            "is_alive": row["is_alive"],
            "max_hitpoints": _exact_scalar(row["max_hitpoints"]),
            "mechanics": list(row["mechanics"]),
            "pending_projectile_max_duration_ms": row[
                "pending_projectile_max_duration_ms"
            ],
            "placement_delay_total": _float_scalar(row["placement_delay_total"]),
            "player_id": row["player_id"],
            "position_x": _exact_scalar(row["position_x"]),
            "position_y": _exact_scalar(row["position_y"]),
            "python_type": row["python_type"],
            "spawn_angle_shift": _float_scalar(row["spawn_angle_shift"]),
            "target_id": row["target_id"],
        }
        for row in active
    ]
    modifiers = []
    character_objects = []
    movement = []
    locked_combat = []
    building_lifetime = []
    for row in active:
        modifier = row["modifier_state"]
        if modifier is not None:
            modifiers.append(
                {
                    "attack_speed_buff_multiplier": _float_scalar(
                        modifier["attack_speed_buff_multiplier"]
                    ),
                    "attack_speed_debuff_multiplier": _float_scalar(
                        modifier["attack_speed_debuff_multiplier"]
                    ),
                    "encounter_index": row["encounter_index"],
                    "haste_effects": [
                        [
                            _float_scalar(effect["remaining"]),
                            _float_scalar(effect["movement"]),
                            _float_scalar(effect["attack"]),
                            _float_scalar(effect["spawn"]),
                        ]
                        for effect in modifier["haste_effects"]
                    ],
                    "haste_timer": _float_scalar(modifier["haste_timer"]),
                    "id": row["id"],
                    "movement_mode_multiplier": _float_scalar(
                        modifier["movement_mode_multiplier"]
                    ),
                    "movement_speed_buff_multiplier": _float_scalar(
                        modifier["movement_speed_buff_multiplier"]
                    ),
                    "original_speed": _optional_float_scalar(
                        modifier["original_speed"]
                    ),
                    "slow_effects": [
                        [
                            _float_scalar(effect["remaining"]),
                            _float_scalar(effect["movement"]),
                            _float_scalar(effect["attack"]),
                            _float_scalar(effect["spawn"]),
                        ]
                        for effect in modifier["slow_effects"]
                    ],
                    "slow_multiplier": _float_scalar(modifier["slow_multiplier"]),
                    "slow_timer": _float_scalar(modifier["slow_timer"]),
                    "spawn_speed_buff_multiplier": _float_scalar(
                        modifier["spawn_speed_buff_multiplier"]
                    ),
                    "spawn_speed_debuff_multiplier": _float_scalar(
                        modifier["spawn_speed_debuff_multiplier"]
                    ),
                    "speed": _exact_scalar(modifier["speed"]),
                    "stun_timer": _float_scalar(modifier["stun_timer"]),
                }
            )
        if row["entity_kind"] in {0, 1}:
            character_objects.append(
                {
                    "death_spawn_target_immunity_elapsed_ms": row[
                        "death_spawn_target_immunity_elapsed_ms"
                    ],
                    "deploy_delay_remaining": _float_scalar(
                        row["deploy_delay_remaining"]
                    ),
                    "encounter_index": row["encounter_index"],
                    "id": row["id"],
                    "placement_pending": row["placement_pending"],
                    "spawn_hook_fired": row["spawn_hook_fired"],
                    "spawn_hook_pending": row["spawn_hook_pending"],
                }
            )
        move = row["movement_state"]
        combat = row["locked_combat_state"]
        if move is not None and combat is not None:
            route_names = ("absent", "single", "ground", "unsupported")
            movement.append(
                {
                    "airborne_for_projectile": combat["is_airborne_for_projectile"],
                    "building_pathing_radius": _float_scalar(
                        move["building_pathing_radius"]
                    ),
                    "death_spawn_travel_target": None
                    if move["death_spawn_travel_target"] is None
                    else [
                        _float_scalar(move["death_spawn_travel_target"][0]),
                        _float_scalar(move["death_spawn_travel_target"][1]),
                    ],
                    "death_spawn_travel_ticks": move["death_spawn_travel_ticks"],
                    "encounter_index": row["encounter_index"],
                    "facing_x_units": combat["facing_x_units"],
                    "facing_y_units": combat["facing_y_units"],
                    "forced_movement_active": move["forced_movement_active"],
                    "ground_path_backwards": combat["ground_path_backwards"],
                    "id": row["id"],
                    "jump_speed": _float_scalar(move["jump_speed"]),
                    "knockback_immune": move["knockback_immune"],
                    "knockback_interrupts_combat": move["knockback_interrupts_combat"],
                    "knockback_target": None,
                    "knockback_velocity_work": move["knockback_velocity_work"],
                    "movement_phase_elapsed_ms": move["movement_phase_elapsed_ms"],
                    "native_avoidance": move["native_avoidance"],
                    "native_lane_id": move["native_lane_id"],
                    "native_natural_movement_active": move[
                        "native_natural_movement_active"
                    ],
                    "pending_consumed": move["pending_consumed"],
                    "pending_x": _float_scalar(move["pending_x"]),
                    "pending_y": _float_scalar(move["pending_y"]),
                    "position_x": _exact_scalar(row["position_x"]),
                    "position_y": _exact_scalar(row["position_y"]),
                    "route_backwards": move["route_backwards"],
                    "route_cells": [list(cell) for cell in move["route_cells"]],
                    "route_goal": None
                    if move["route_goal"] is None
                    else list(move["route_goal"]),
                    "route_jump_height": move["route_jump_height"],
                    "route_kind": route_names[move["route_cache_kind"]],
                    "route_lane_id": move["route_lane_id"],
                    "river_jump_active": move["river_jump_active"],
                    "river_jump_blocked": move["river_jump_blocked"],
                    "river_jump_duration": _float_scalar(move["river_jump_duration"]),
                    "river_jump_elapsed": _float_scalar(move["river_jump_elapsed"]),
                    "river_jump_origin": None,
                    "river_jump_target": None,
                    "serialized_speed": _float_scalar(move["serialized_speed"]),
                    "special_move_active": move["special_move_active"],
                    "special_move_consumed_tick": move["special_move_consumed_tick"],
                    "stop_movement_after_ms": _float_scalar(
                        move["stop_movement_after_ms"]
                    ),
                    "stun_interrupt_deferred_until_landing": move[
                        "stun_interrupt_deferred_until_landing"
                    ],
                    "vector_bypasses_cap": move["vector_bypasses_cap"],
                    "vector_count": move["vector_count"],
                    "vector_x_units": move["vector_x_units"],
                    "vector_y_units": move["vector_y_units"],
                    "wait_ms": _float_scalar(move["wait_ms"]),
                }
            )
            locked_combat.append(
                {
                    "attack_cooldown": _float_scalar(combat["attack_cooldown"]),
                    "attack_preload_blocked": combat["attack_preload_blocked"],
                    "attack_windup_active": combat["attack_windup_active"],
                    "damage_ramp": (
                        None
                        if combat["damage_ramp"] is None
                        else {
                            "current_target_id": combat["damage_ramp"][
                                "current_target_id"
                            ],
                            "current_target_ms": _float_scalar(
                                combat["damage_ramp"]["current_target_ms"]
                            ),
                            "current_target_ms_present": combat["damage_ramp"][
                                "current_target_ms_present"
                            ],
                            "current_target_present": combat["damage_ramp"][
                                "current_target_present"
                            ],
                            "stages": [
                                [stage["time_ms"], stage["damage"]]
                                for stage in combat["damage_ramp"]["stages"]
                            ],
                            "stored_original_damage": combat["damage_ramp"][
                                "stored_original_damage"
                            ],
                        }
                    ),
                    "encounter_index": row["encounter_index"],
                    "facing_x_units": combat["facing_x_units"],
                    "facing_y_units": combat["facing_y_units"],
                    "has_attacked_once": combat["has_attacked_once"],
                    "hide_when_idle": (
                        None
                        if combat["hide_when_idle"] is None
                        else {
                            "hide_delay_ms": combat["hide_when_idle"][
                                "hide_delay_ms"
                            ],
                            "phase_ms": _float_scalar(
                                combat["hide_when_idle"]["phase_ms"]
                            ),
                            "rise_time_ms": combat["hide_when_idle"][
                                "rise_time_ms"
                            ],
                        }
                    ),
                    "wall_breakers_demolition": (
                        None
                        if combat["wall_breakers_demolition"] is None
                        else {
                            "triggered": combat["wall_breakers_demolition"][
                                "triggered"
                            ]
                        }
                    ),
                    "hidden_building": combat["hidden_building"],
                    "hitpoints": _exact_scalar(row["hitpoints"]),
                    "id": row["id"],
                    "initial_position": None,
                    "is_alive": row["is_alive"],
                    "last_attack_time": _float_scalar(combat["last_attack_time"]),
                    "last_combat_target_id": combat["last_combat_target_id"],
                    "movement_target_id": combat["movement_target_id"],
                    "native_target_distance_discount_sq_units": combat[
                        "native_target_distance_discount_sq_units"
                    ],
                    "target_id": row["target_id"],
                }
            )
        lifetime = row["building_lifetime_state"]
        impact = row["building_impact_state"]
        if lifetime is not None:
            assert impact is not None
            building_lifetime.append(
                {
                    "activation_delay_remaining": _float_scalar(
                        impact["activation_delay_remaining"]
                    ),
                    "activation_first_hit_delay_remaining": _float_scalar(
                        impact["activation_first_hit_delay_remaining"]
                    ),
                    "crown_slot": impact["crown_slot"],
                    "encounter_index": row["encounter_index"],
                    "hitpoints": _exact_scalar(row["hitpoints"]),
                    "id": row["id"],
                    "is_alive": row["is_alive"],
                    "lifetime_decay_work": lifetime["decay_work"],
                    "lifetime_elapsed": _float_scalar(lifetime["lifetime_elapsed"]),
                    "lifetime_tick_carry_ms": _float_scalar(lifetime["tick_carry_ms"]),
                    "tower_active": impact["tower_active"],
                }
            )
    battle = parts["battle"]
    pending = parts["pending_spells"]
    rng = parts["rng"]
    return {
        "schema_version": parts["binding"]["semantic_schema_version"],
        "clock": {
            "double_elixir": battle["double_elixir"],
            "dt": _float_scalar(battle["dt"]),
            "game_over": battle["game_over"],
            "overtime": battle["overtime"],
            "tick": battle["tick"],
            "time": _float_scalar(battle["time"]),
            "triple_elixir": battle["triple_elixir"],
        },
        "players": players,
        "towers": towers,
        "outcome": {
            "game_over": battle["game_over"],
            "sudden_death": battle["sudden_death"],
            "sudden_death_crowns": list(battle["sudden_death_crowns"]),
            "winner": battle["winner"],
        },
        "entities": entities,
        "modifiers": modifiers,
        "shields": [],
        "character_objects": character_objects,
        "death_opcodes": [],
        "area_effects": [],
        "movement": movement,
        "locked_combat": locked_combat,
        "building_lifetime": building_lifetime,
        "point_projectiles": [],
        "rolling_projectiles": [],
        "chain_lightnings": [],
        "rng": {
            "gauss_next": None
            if rng["gauss_next"] is None
            else _exact_scalar(rng["gauss_next"]),
            "index": rng["index"],
            "state": list(rng["state"]),
            "version": rng["version"],
        },
        "next_entity_id": battle["next_entity_id"],
        "pending_spells": {
            "casts": [
                {
                    "execute_at": _float_scalar(cast["execute_at"]),
                    "player_id": cast["player_id"],
                    "position_x": _float_scalar(cast["position_x"]),
                    "position_y": _float_scalar(cast["position_y"]),
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
                "hit_entity_ids": sorted(group["hit_entity_ids"]),
            }
            for group in parts["projectile_groups"]
        ],
        "win_conditions_dirty": battle["win_conditions_dirty"],
    }


def _prepared_pair(*, ticks: int = 1) -> tuple[ResidentRustBattle, ResidentRustBattle]:
    battle = BattleState(rng=random.Random(882_100), fast_path=True)
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()
    assert candidate.advance_complete_ticks(ticks) == ticks
    return prior, candidate


def _spawn_ready(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    troop = battle._spawn_entity(Troop, position, player_id, stats)
    troop.deploy_delay_remaining = 0.0
    troop.placement_pending = False
    troop._spawn_hook_pending = False
    troop._spawn_hook_fired = True
    return troop


def test_prepared_parts_are_owned_frozen_and_match_legacy_root_rows() -> None:
    prior, candidate = _prepared_pair(ticks=1)
    prepared = candidate.prepare_publication(prior)
    prepared_repeat = candidate.prepare_publication(prior)
    legacy_players = json.loads(candidate.publication_player_state_bytes())
    legacy_entities = json.loads(candidate.publication_entity_state_bytes())

    # Mutating the source objects after prepare cannot alter the owned boundary.
    assert candidate.advance_complete_ticks(1) == 1
    assert prior.advance_complete_ticks(1) == 1
    parts = prepared.parts()
    repeated = prepared_repeat.parts()

    assert isinstance(parts, MappingProxyType)
    assert parts["version"] == 1
    assert parts["binding"]["semantic_schema_version"] == 15
    assert parts["binding"]["checkpoint_schema_version"] == 2
    assert parts["binding"]["catalog_schema_version"] == 15
    assert parts["battle"]["tick"] == 1
    assert isinstance(parts["entities"], tuple)
    assert isinstance(parts["entities"][0], MappingProxyType)
    assert repeated == parts
    assert repeated is not parts
    assert repeated["entities"] is not parts["entities"]
    with pytest.raises(RuntimeError, match="already consumed"):
        prepared.parts()
    with pytest.raises(TypeError):
        parts["version"] = 2  # type: ignore[index]

    for typed, legacy in zip(parts["players"], legacy_players, strict=True):
        assert typed["player_id"] == legacy["player_id"]
        assert _float_scalar(typed["elixir"]) == legacy["elixir"]
        assert _exact_scalar(typed["king_tower_hp"]) == legacy["king_tower_hp"]
        assert _exact_scalar(typed["left_tower_hp"]) == legacy["left_tower_hp"]
        assert _exact_scalar(typed["right_tower_hp"]) == legacy["right_tower_hp"]

    for typed, legacy in zip(parts["entities"], legacy_entities, strict=True):
        assert typed["id"] == legacy["id"]
        assert typed["active"] == legacy["active"]
        assert typed["encounter_index"] == legacy["encounter_index"]
        assert _exact_scalar(typed["position_x"]) == legacy["position_x"]
        assert _exact_scalar(typed["position_y"]) == legacy["position_y"]
        assert _exact_scalar(typed["hitpoints"]) == legacy["hitpoints"]
        assert _exact_scalar(typed["max_hitpoints"]) == legacy["max_hitpoints"]
        if "damage" in legacy:
            assert _exact_scalar(typed["damage"]) == legacy["damage"]


def test_typed_parts_match_full_legacy_basic_semantic_and_presence_schema() -> None:
    prior, candidate = _prepared_pair(ticks=1)
    expected = rust_resident_semantic_snapshot(candidate)
    expected_presence = json.loads(
        candidate.publication_battle_attribute_presence_bytes()
    )
    parts = candidate.prepare_publication(prior).parts()

    assert _typed_basic_semantic(parts) == expected
    battle_presence_names = (
        "_sudden_death_crowns",
        "_next_spell_cast_sequence",
        "_defer_projectile_impacts",
        "_projectile_lethal_reservations",
        "_coalesce_alive_building_refreshes",
        "_win_conditions_dirty",
        "_building_placement_blocked_masks",
        "_troop_placement_blocked_masks",
    )
    presence_mask = parts["battle"]["sparse_attribute_presence"]
    actual_presence = {
            name: bool(presence_mask & (1 << (28 + index)))
        for index, name in enumerate(battle_presence_names)
    }
    assert actual_presence == expected_presence


def test_prepare_rejects_wrong_sibling_nested_and_stale_priors() -> None:
    prior, candidate = _prepared_pair(ticks=1)
    sibling = prior.fork()
    nested = candidate.fork()
    unrelated_root = ResidentRustBattle.from_battle(
        BattleState(rng=random.Random(882_100), fast_path=True)
    )
    unrelated = ResidentRustBattle(
        unrelated_root._native,
        prior._birth_catalog,
        prior._action_card_stats,
    )

    with pytest.raises(ValueError, match="different lineage"):
        candidate.prepare_publication(unrelated)
    with pytest.raises(ValueError, match="direct fork"):
        candidate.prepare_publication(sibling)
    with pytest.raises(ValueError, match="direct fork"):
        nested.prepare_publication(prior)

    stale_prior = ResidentRustBattle.from_battle(
        BattleState(rng=random.Random(882_101), fast_path=True)
    )
    stale_candidate = stale_prior.fork()
    assert stale_prior.advance_complete_ticks(1) == 1
    with pytest.raises(ValueError, match="direct fork"):
        stale_candidate.prepare_publication(stale_prior)

    rng_prior = ResidentRustBattle.from_battle(
        BattleState(rng=random.Random(882_106), fast_path=True)
    )
    rng_candidate = rng_prior.fork()
    rng_prior.rng_random()
    with pytest.raises(ValueError, match="direct fork"):
        rng_candidate.prepare_publication(rng_prior)

    wrong_python_owner = ResidentRustBattle(
        candidate._native,
        candidate._birth_catalog,
        dict(candidate._action_card_stats or {}),
    )
    with pytest.raises(ValueError, match="action-card attestations"):
        wrong_python_owner.prepare_publication(prior)


def test_python_prepared_decoder_rejects_wrong_version() -> None:
    with pytest.raises(ValueError, match="unsupported.*version"):
        _decode_prepared_publication_parts({"version": 2})
    with pytest.raises(TypeError, match="runtime-owned"):
        ResidentPreparedPublication(None, None, None, authority=object())


def test_noop_and_rejected_calls_do_not_stale_direct_child_epoch() -> None:
    battle = BattleState(rng=random.Random(882_107), fast_path=True)
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()

    assert prior.advance_complete_ticks(0) == 0
    with pytest.raises(ValueError):
        prior.rng_randrange(0)
    parts = candidate.prepare_publication(prior).parts()
    assert parts["binding"]["prior_epoch"] == 0

    changed_prior = ResidentRustBattle.from_battle(battle)
    stale_candidate = changed_prior.fork()
    assert changed_prior.advance_clock_phase()
    with pytest.raises(ValueError, match="direct fork"):
        stale_candidate.prepare_publication(changed_prior)

    epoch_prior = ResidentRustBattle.from_battle(battle)
    assert epoch_prior.advance_complete_ticks(1) == 1
    epoch_candidate = epoch_prior.fork()
    epoch_parts = epoch_candidate.prepare_publication(epoch_prior).parts()
    assert epoch_parts["binding"]["prior_epoch"] == 1


def test_prepare_rejects_phase_local_lethal_reservations() -> None:
    battle = BattleState(rng=random.Random(882_108), fast_path=True)
    battle.entities.clear()
    battle.next_entity_id = 1
    launcher = _spawn_ready(battle, "Musketeer", 0, Position(9.0, 12.0))
    target = _spawn_ready(battle, "Knight", 1, Position(9.0, 14.0))
    launcher.target_id = target.id
    launcher.attack_cooldown = 0.0
    target.hitpoints = launcher.damage
    prior = ResidentRustBattle.from_battle(battle)
    candidate = prior.fork()

    assert candidate.advance_complete_tick()
    # Complete-tick boundaries clear the phase-local set and remain publishable.
    candidate.prepare_publication(prior).parts()

    dirty_candidate = prior.fork()
    assert dirty_candidate.advance_complete_tick()
    dirty_candidate.advance_direct_troop_combat_phase()
    with pytest.raises(ValueError, match="phase-local lethal reservations"):
        dirty_candidate.prepare_publication(prior)


def test_preview_candidate_has_direct_publication_parent() -> None:
    battle = BattleState(rng=random.Random(882_102), fast_path=True)
    prior = ResidentRustBattle.from_battle(battle)
    no_op = 4 * 18 * 32
    candidate, successes, _order, advanced = prior.preview_resident_joint_action_interval(
        no_op,
        no_op,
        1,
    )

    assert successes == {0: True, 1: True}
    assert advanced == 1
    parts = candidate.prepare_publication(prior).parts()
    assert parts["binding"]["parent_node_id"] == parts["binding"]["prior_node_id"]
    assert parts["binding"]["parent_epoch"] == parts["binding"]["prior_epoch"]


def test_prepared_parts_cover_action_birth_pending_spell_and_grouped_projectiles() -> None:
    troop_battle = BattleState(rng=random.Random(882_103), fast_path=True)
    troop_prior = ResidentRustBattle.from_battle(troop_battle)
    no_op = 4 * 18 * 32
    minions_action = 3 * 18 * 32 + 10 * 18 + 8
    troop_candidate, successes, _order, _advanced = (
        troop_prior.preview_resident_joint_action_interval(
            minions_action,
            no_op,
            0,
        )
    )
    assert successes == {0: True, 1: True}
    troop_parts = troop_candidate.prepare_publication(troop_prior).parts()
    births = troop_parts["entities"][len(troop_parts["binding"]["prior_entity_ids"]) :]
    assert [row["id"] for row in births] == list(
        range(
            troop_parts["binding"]["prior_next_entity_id"],
            troop_parts["battle"]["next_entity_id"],
        )
    )
    assert [row["character_birth"]["kind"] for row in births] == [0, 0, 0]
    assert [row["character_birth"]["ordinal"] for row in births] == [0, 1, 2]
    assert {row["character_birth"]["group_id"] for row in births} == {
        births[0]["id"]
    }

    spell_battle = BattleState(rng=random.Random(882_104), fast_path=True)
    spell_battle.players[0].hand[0] = "Arrows"
    spell_battle.players[0].elixir = 10.0
    spell_prior = ResidentRustBattle.from_battle(spell_battle)
    arrows_action = 10 * 18 + 8
    pending, successes, _order, advanced = (
        spell_prior.preview_resident_joint_action_interval(
            arrows_action,
            no_op,
            0,
        )
    )
    assert successes == {0: True, 1: True}
    assert advanced == 0
    pending_parts = pending.prepare_publication(spell_prior).parts()
    assert pending_parts["pending_spells"]["next_sequence"] == 1
    assert len(pending_parts["pending_spells"]["casts"]) == 1
    assert pending_parts["pending_spells"]["casts"][0]["spell_name"] == "Arrows"

    projectiles, successes, _order, advanced = (
        spell_prior.preview_resident_joint_action_interval(
            arrows_action,
            no_op,
            22,
        )
    )
    assert successes == {0: True, 1: True}
    assert advanced == 22
    projectile_parts = projectiles.prepare_publication(spell_prior).parts()
    projectile_rows = [
        row
        for row in projectile_parts["entities"]
        if row["point_projectile_state"] is not None
    ]
    assert len(projectile_rows) == 30
    assert len(projectile_parts["projectile_groups"]) == 3
    assert all(
        row["point_projectile_state"]["damage_group_id"] is not None
        for row in projectile_rows
    )
    assert all(
        row["point_projectile_state"]["constructor_range"][0] in {0, 1}
        for row in projectile_rows
    )


def test_prepared_parts_do_not_use_legacy_json_exports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prior, candidate = _prepared_pair(ticks=1)
    prepared = candidate.prepare_publication(prior)
    native_type = type(candidate._native)
    prepared_native_type = type(prepared._native)
    native_parts = prepared_native_type.parts
    crossings = 0

    def _counted_parts(native: Any) -> Any:
        nonlocal crossings
        crossings += 1
        return native_parts(native)

    monkeypatch.setattr(prepared_native_type, "parts", _counted_parts)

    for name in (
        "publication_entity_state_bytes",
        "publication_player_state_bytes",
        "publication_battle_attribute_presence_bytes",
        "publication_exactness_sha256",
        "entity_state_bytes",
        "rng_state_bytes",
    ):
        monkeypatch.setattr(
            native_type,
            name,
            lambda *args, _name=name, **kwargs: (_ for _ in ()).throw(
                AssertionError(f"legacy exporter called: {_name}")
            ),
        )

    parts = prepared.parts()
    assert parts["battle"]["tick"] == 1
    assert len(parts["entities"]) >= 6
    assert crossings == 1
    with pytest.raises(RuntimeError, match="already consumed"):
        prepared.parts()
    assert crossings == 1
