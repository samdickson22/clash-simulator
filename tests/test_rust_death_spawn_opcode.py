from __future__ import annotations

import json
import random

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.mechanics.shared.death_effects import DeathSpawn
from clasher.rust_core import (
    ResidentRustBattle,
    compare_character_object_phase,
    compare_death_opcode_state,
    compare_ground_movement_phase,
    compare_idle_state,
    compare_locked_direct_combat_phase,
    compare_modifier_phase,
    compare_point_projectile_phase,
    compare_resident_entities,
    compare_resident_rng,
    rust_core_available,
)

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _spawn(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(position, player_id, stats)
    return next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )


def _activate(*troops: Troop) -> None:
    for troop in troops:
        troop.deploy_delay_remaining = 0.0
        troop.placement_pending = False
        troop._spawn_hook_pending = False
        troop._spawn_hook_fired = True


def _lethal_golem_battle(seed: int) -> tuple[BattleState, Troop]:
    battle = BattleState(rng=random.Random(seed))
    attacker = _spawn(battle, "Knight", 1, Position(9.0, 13.5))
    golem = _spawn(battle, "Golem", 0, Position(9.0, 14.0))
    _activate(attacker, golem)
    attacker.damage = golem.hitpoints + 1
    attacker.attack_cooldown = 0.0
    return battle, golem


def _compare_complete_state(
    battle: BattleState,
    resident: ResidentRustBattle,
) -> None:
    compare_locked_direct_combat_phase(battle, resident)
    compare_ground_movement_phase(battle, resident)
    compare_modifier_phase(battle, resident)
    compare_character_object_phase(battle, resident)
    compare_point_projectile_phase(battle, resident)
    compare_death_opcode_state(battle, resident)
    compare_resident_entities(battle, resident)
    compare_resident_rng(battle.rng, resident)
    compare_idle_state(battle, resident)
    assert resident.next_entity_id == battle.next_entity_id


def test_golem_death_spawn_is_compiled_in_serialized_mechanic_order() -> None:
    battle, golem = _lethal_golem_battle(9101)
    resident = ResidentRustBattle.from_battle(battle)

    compare_death_opcode_state(battle, resident)
    rows = resident.death_opcode_state_bytes()
    assert rows.index(b'"opcode_type":"damage"') < rows.index(
        b'"opcode_type":"spawn"'
    )
    assert b'"unit_name":"Golemite"' in rows
    assert str(golem.id).encode() in rows
    assert resident.supports_complete_tick


def test_lethal_golem_hit_spawns_exact_birth_frame_golemites() -> None:
    battle, golem = _lethal_golem_battle(9102)
    resident = ResidentRustBattle.from_battle(battle)
    rng_before = resident.rng_state_bytes()

    assert resident.advance_complete_tick()
    battle._step_logic_tick(refresh_fast_path_end=False)

    _compare_complete_state(battle, resident)
    assert golem.id not in battle.entities
    children = [
        entity
        for entity in battle.entities.values()
        if getattr(entity.card_stats, "name", "") == "Golemite"
    ]
    assert [child.id for child in children] == [golem.id + 1, golem.id + 2]
    assert [(child.position.x, child.position.y) for child in children] == [
        (9.0, 14.0),
        (9.0, 14.0),
    ]
    assert [child._death_spawn_travel_ticks_remaining for child in children] == [
        6,
        6,
    ]
    assert [child._death_spawn_target_immunity_elapsed_ms for child in children] == [
        50,
        50,
    ]
    assert resident.rng_state_bytes() == rng_before


def test_death_spawn_deploy_override_preserves_placement_total() -> None:
    battle, golem = _lethal_golem_battle(9108)
    mechanic = next(
        mechanic
        for mechanic in golem.mechanics
        if isinstance(mechanic, DeathSpawn)
    )
    mechanic.deploy_time_ms = 1000
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.advance_complete_tick()
    battle._step_logic_tick(refresh_fast_path_end=False)

    _compare_complete_state(battle, resident)
    children = [
        entity
        for entity in battle.entities.values()
        if getattr(entity.card_stats, "name", "") == "Golemite"
    ]
    assert [child.placement_delay_total for child in children] == [1.0, 1.0]
    assert [child.deploy_delay_remaining for child in children] == [0.95, 0.95]
    resident_children = [
        row
        for row in json.loads(resident.entity_state_bytes())
        if row["card_name"] == "Golemite"
    ]
    assert [row["placement_delay_total"] for row in resident_children] == [
        {"bits": "3ff0000000000000", "kind": "float"},
        {"bits": "3ff0000000000000", "kind": "float"},
    ]


def test_variable_death_spawn_radius_consumes_exactly_matching_rng() -> None:
    battle, golem = _lethal_golem_battle(9103)
    mechanic = next(
        mechanic
        for mechanic in golem.mechanics
        if isinstance(mechanic, DeathSpawn)
    )
    mechanic.min_radius_tiles = 1.0
    mechanic.radius_tiles = 1.5
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.advance_complete_tick()
    battle._step_logic_tick(refresh_fast_path_end=False)

    _compare_complete_state(battle, resident)


def test_constant_priority_spawn_uses_current_parent_path() -> None:
    battle, golem = _lethal_golem_battle(9107)
    attacker = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop) and entity.player_id == 1
    )
    # The parent was initialized on native path 2. Move it to path 1 without
    # rewriting the immutable spawn-lane field: DeathSpawn consults the
    # current arena path at the lethal transition.
    attacker.position = Position(3.0, 13.5)
    golem.position = Position(3.0, 14.0)
    attacker.target_id = golem.id
    attacker._last_combat_target_id = golem.id
    mechanic = next(
        mechanic
        for mechanic in golem.mechanics
        if isinstance(mechanic, DeathSpawn)
    )
    mechanic.spawn_const_priority = True
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.advance_complete_tick()
    battle._step_logic_tick(refresh_fast_path_end=False)

    _compare_complete_state(battle, resident)
    children = [
        entity
        for entity in battle.entities.values()
        if getattr(entity.card_stats, "name", "") == "Golemite"
    ]
    assert [child._native_target_distance_discount_sq_units for child in children] == [
        0,
        80 * 80,
    ]
    assert children[0]._death_spawn_travel_target == Position(4.5, 14.0)


def test_golemite_radial_travel_and_fallback_retarget_remain_exact() -> None:
    battle, _ = _lethal_golem_battle(9105)
    resident = ResidentRustBattle.from_battle(battle)

    for _ in range(7):
        assert resident.supports_complete_tick
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        _compare_complete_state(battle, resident)


def test_immediate_death_spawn_inherits_absolute_freeze_expiry() -> None:
    battle, golem = _lethal_golem_battle(9104)
    golem.inherit_freeze_until(battle.time + 1.0, battle.time)
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.advance_complete_tick()
    battle._step_logic_tick(refresh_fast_path_end=False)

    _compare_complete_state(battle, resident)
    children = [
        entity
        for entity in battle.entities.values()
        if getattr(entity.card_stats, "name", "") == "Golemite"
    ]
    assert [child.freeze_expiry_time for child in children] == [1.0, 1.0]
    assert [child.stun_timer for child in children] == [0.95, 0.95]
    assert [child.slow_timer for child in children] == [0.95, 0.95]
    resident_children = [
        row
        for row in json.loads(resident.entity_state_bytes())
        if row["card_name"] == "Golemite"
    ]
    assert [row["freeze_expiry_time"] for row in resident_children] == [
        {"bits": "3ff0000000000000", "kind": "float"},
        {"bits": "3ff0000000000000", "kind": "float"},
    ]


def test_missing_death_spawn_mechanic_rejects_legacy_card_payload() -> None:
    battle, golem = _lethal_golem_battle(9109)
    golem.mechanics = [
        mechanic
        for mechanic in golem.mechanics
        if not isinstance(mechanic, DeathSpawn)
    ]
    resident = ResidentRustBattle.from_battle(battle)
    entities_before = resident.entity_state_bytes()
    rng_before = resident.rng_state_bytes()

    assert not resident.supports_complete_tick
    with pytest.raises(RuntimeError, match="rejected combat capability"):
        resident.advance_complete_tick()

    assert resident.entity_state_bytes() == entities_before
    assert resident.rng_state_bytes() == rng_before


def test_projectile_child_death_spawn_remains_atomic_and_fail_closed() -> None:
    battle = BattleState(rng=random.Random(9106))
    _spawn(battle, "LavaHound", 0, Position(9.0, 14.0))
    resident = ResidentRustBattle.from_battle(battle)
    entities_before = resident.entity_state_bytes()
    rng_before = resident.rng_state_bytes()

    assert not resident.supports_complete_tick
    with pytest.raises(RuntimeError, match="rejected combat capability"):
        resident.advance_complete_tick()

    assert resident.entity_state_bytes() == entities_before
    assert resident.rng_state_bytes() == rng_before
