from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .battle import BattleState
from .differential import BattleAdapter, DifferentialResult, run_differential
from .rust_core import (
    ResidentOutcomeState,
    ResidentPlayerState,
    ResidentRustBattle,
    ResidentTowerState,
    _exact_scalar,
    area_effect_state_rows,
    building_lifetime_state_rows,
    chain_lightning_state_rows,
    character_object_state_rows,
    death_opcode_state_rows,
    flying_movement_state_rows,
    locked_direct_combat_state_rows,
    modifier_state_rows,
    point_projectile_state_rows,
    python_outcome_state,
    python_player_states,
    python_tower_states,
    resident_entity_rows,
    resident_rng_state,
    rolling_projectile_state_rows,
    shield_state_rows,
)

RESIDENT_SEMANTIC_SCHEMA_VERSION = 16


def _python_pending_spell_state(battle: BattleState) -> dict[str, Any]:
    return {
        "casts": [
            {
                "execute_at": _exact_scalar(cast.execute_at),
                "player_id": int(cast.player_id),
                "position_x": _exact_scalar(cast.position.x),
                "position_y": _exact_scalar(cast.position.y),
                "sequence": int(cast.sequence),
                "spell_name": str(cast.spell_name),
            }
            for cast in battle._pending_spell_casts
        ],
        "next_sequence": int(battle._next_spell_cast_sequence),
    }


def _python_projectile_damage_groups(battle: BattleState) -> list[dict[str, Any]]:
    from .entities import Projectile

    groups: dict[int, tuple[set[int], list[int]]] = {}
    for entity in battle.entities.values():
        if type(entity) is not Projectile or entity.damage_group_hit_entity_ids is None:
            continue
        hit_ids = entity.damage_group_hit_entity_ids
        _, projectile_ids = groups.setdefault(id(hit_ids), (hit_ids, []))
        projectile_ids.append(int(entity.id))
    return [
        {
            "group_id": min(projectile_ids),
            "hit_entity_ids": sorted(hit_ids),
        }
        for hit_ids, projectile_ids in groups.values()
    ]


def _player_row(state: ResidentPlayerState) -> dict[str, Any]:
    return {
        "cycle_queue": list(state.cycle_queue),
        "elixir": _exact_scalar(state.elixir),
        "hand": list(state.hand),
        "king_tower_hp": _exact_scalar(state.king_tower_hp),
        "left_tower_hp": _exact_scalar(state.left_tower_hp),
        "max_elixir": _exact_scalar(state.max_elixir),
        "next_card_refill_cooldown_ms": state.next_card_refill_cooldown_ms,
        "player_id": state.player_id,
        "right_tower_hp": _exact_scalar(state.right_tower_hp),
    }


def _tower_row(state: ResidentTowerState) -> dict[str, Any]:
    return {
        "hp": _exact_scalar(state.hp),
        "hp_milli": state.hp_milli,
        "id": state.id,
        "is_active": state.is_active,
        "is_alive": state.is_alive,
        "last_attack_time": _exact_scalar(state.last_attack_time),
        "player_id": state.player_id,
        "slot": state.slot,
    }


def _outcome_row(state: ResidentOutcomeState) -> dict[str, Any]:
    return {
        "game_over": state.game_over,
        "sudden_death": state.sudden_death,
        "sudden_death_crowns": list(state.sudden_death_crowns),
        "winner": state.winner,
    }


def python_resident_semantic_snapshot(battle: BattleState) -> dict[str, Any]:
    """Return the exact state projection currently owned by resident Rust.

    This projection deliberately excludes Python fast-path cache layout. It is
    narrower than the canonical Python snapshot, but every included field is
    compared without tolerance and is sufficient to diagnose the currently
    declared complete-tick capability.
    """

    return {
        "schema_version": RESIDENT_SEMANTIC_SCHEMA_VERSION,
        "clock": {
            "double_elixir": bool(battle.double_elixir),
            "dt": _exact_scalar(battle.dt),
            "game_over": bool(battle.game_over),
            "overtime": bool(battle.overtime),
            "tick": int(battle.tick),
            "time": _exact_scalar(battle.time),
            "triple_elixir": bool(battle.triple_elixir),
        },
        "players": [_player_row(state) for state in python_player_states(battle)],
        "towers": [_tower_row(state) for state in python_tower_states(battle)],
        "outcome": _outcome_row(python_outcome_state(battle)),
        "entities": resident_entity_rows(battle),
        "modifiers": modifier_state_rows(battle),
        "shields": shield_state_rows(battle),
        "character_objects": character_object_state_rows(battle),
        "death_opcodes": death_opcode_state_rows(battle),
        "area_effects": area_effect_state_rows(battle),
        "movement": flying_movement_state_rows(battle),
        "locked_combat": locked_direct_combat_state_rows(battle),
        "building_lifetime": building_lifetime_state_rows(battle),
        "point_projectiles": point_projectile_state_rows(battle),
        "rolling_projectiles": rolling_projectile_state_rows(battle),
        "chain_lightnings": chain_lightning_state_rows(battle),
        "rng": resident_rng_state(battle.rng),
        "next_entity_id": int(battle.next_entity_id),
        "pending_spells": _python_pending_spell_state(battle),
        "projectile_damage_groups": _python_projectile_damage_groups(battle),
        "win_conditions_dirty": bool(battle._win_conditions_dirty),
    }


def rust_resident_semantic_snapshot(
    resident: ResidentRustBattle,
) -> dict[str, Any]:
    clock = resident.clock_state()
    return {
        "schema_version": RESIDENT_SEMANTIC_SCHEMA_VERSION,
        "clock": {
            "double_elixir": clock.double_elixir,
            "dt": _exact_scalar(clock.dt),
            "game_over": clock.game_over,
            "overtime": clock.overtime,
            "tick": clock.tick,
            "time": _exact_scalar(clock.time),
            "triple_elixir": clock.triple_elixir,
        },
        "players": [_player_row(state) for state in resident.player_states()],
        "towers": [_tower_row(state) for state in resident.tower_states()],
        "outcome": _outcome_row(resident.outcome_state()),
        "entities": json.loads(resident.entity_state_bytes()),
        "modifiers": json.loads(resident.modifier_state_bytes()),
        "shields": json.loads(resident.shield_state_bytes()),
        "character_objects": json.loads(resident.character_object_state_bytes()),
        "death_opcodes": json.loads(resident.death_opcode_state_bytes()),
        "area_effects": json.loads(resident.area_effect_state_bytes()),
        "movement": json.loads(resident.ground_movement_state_bytes()),
        "locked_combat": json.loads(resident.locked_direct_combat_state_bytes()),
        "building_lifetime": json.loads(resident.building_lifetime_state_bytes()),
        "point_projectiles": json.loads(resident.point_projectile_state_bytes()),
        "rolling_projectiles": json.loads(
            resident.rolling_projectile_state_bytes()
        ),
        "chain_lightnings": json.loads(resident.chain_lightning_state_bytes()),
        "rng": json.loads(resident.rng_state_bytes()),
        "next_entity_id": resident.next_entity_id,
        "pending_spells": json.loads(resident.pending_spell_state_bytes()),
        "projectile_damage_groups": json.loads(
            resident.projectile_damage_group_state_bytes()
        ),
        "win_conditions_dirty": resident.win_conditions_dirty,
    }


@dataclass
class PythonResidentBattleAdapter(BattleAdapter):
    battle: BattleState

    def advance_one_tick(self) -> None:
        self.battle._step_logic_tick(refresh_fast_path_end=False)

    def snapshot(self) -> dict[str, Any]:
        return python_resident_semantic_snapshot(self.battle)


@dataclass
class RustResidentBattleAdapter(BattleAdapter):
    resident: ResidentRustBattle

    def advance_one_tick(self) -> None:
        self.resident.advance_complete_tick()

    def snapshot(self) -> dict[str, Any]:
        return rust_resident_semantic_snapshot(self.resident)


def rust_shadow_lockstep(
    battle: BattleState,
    *,
    ticks: int,
    scenario: str,
    dump_directory: str | None = None,
) -> DifferentialResult:
    python_battle = battle.clone()
    resident = ResidentRustBattle.from_battle(battle)
    resident.require_complete_tick("shadow")
    return run_differential(
        PythonResidentBattleAdapter(python_battle),
        RustResidentBattleAdapter(resident),
        ticks=ticks,
        scenario=scenario,
        dump_directory=dump_directory,
    )
