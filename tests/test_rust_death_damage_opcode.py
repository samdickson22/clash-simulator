from __future__ import annotations

import random

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.factory.dynamic_factory import (
    building_from_values,
    troop_from_character_data,
)
from clasher.mechanics.shared.death_effects import DeathDamage
from clasher.mechanics.shared.shield import Shield
from clasher.rust_core import (
    ResidentRustBattle,
    compare_building_lifetime_phase,
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


def _spawn_golemite(
    battle: BattleState,
    player_id: int,
    position: Position,
) -> Troop:
    golem = battle.card_loader.get_card("Golem")
    assert golem is not None
    assert golem.death_spawn_character_data is not None
    stats = troop_from_character_data(
        "Golemite",
        golem.death_spawn_character_data,
        elixir=0,
        rarity="Common",
    )
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


def _lifetime_building(
    battle: BattleState,
    *,
    player_id: int,
    position: Position,
    lifetime_ms: int,
) -> Building:
    stats = building_from_values(
        name="LifetimeFixture",
        hitpoints=100,
        damage=0,
        range_tiles=0.0,
        sight_range_tiles=0.0,
        hit_speed_ms=1000,
        deploy_time_ms=0,
        collision_radius_tiles=0.5,
        lifetime_ms=lifetime_ms,
        target_type="TID_TARGETS_AIR_AND_GROUND",
    )
    building = Building(
        id=battle.next_entity_id,
        position=position,
        player_id=player_id,
        card_stats=stats,
        hitpoints=100,
        max_hitpoints=100,
        damage=0,
        range=0.0,
        sight_range=0.0,
    )
    battle.next_entity_id += 1
    battle.entities[building.id] = building
    setattr(building, "battle_state", battle)  # noqa: B010 - dynamic runtime field
    building.deploy_delay_remaining = 0.0
    building.placement_pending = False
    building._spawn_hook_pending = False
    building._spawn_hook_fired = True
    return building


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


def test_golemite_death_damage_opcode_is_exact_and_complete_tick_capable() -> None:
    battle = BattleState(rng=random.Random(8101))
    golemite = _spawn_golemite(battle, 0, Position(9.0, 14.0))
    resident = ResidentRustBattle.from_battle(battle)

    compare_death_opcode_state(battle, resident)
    rows = resident.death_opcode_state_bytes()
    assert b'"base_damage":39' in rows
    assert b'"knockback_units":900' in rows
    assert b'"radius_units":2000' in rows
    assert str(golemite.id).encode() in rows
    assert resident.supports_complete_tick


def test_death_damage_parser_uses_serialized_mechanic_fields() -> None:
    battle = BattleState(rng=random.Random(8105))
    golemite = _spawn_golemite(battle, 0, Position(9.0, 14.0))
    mechanic = golemite.mechanics[0]
    assert isinstance(mechanic, DeathDamage)
    mechanic.radius_tiles = 1.375
    mechanic.damage = 17
    mechanic.scaled_damage = 23.5
    mechanic.knockback_distance = 0.625
    mechanic.hits_air = False
    mechanic.hits_ground = True
    resident = ResidentRustBattle.from_battle(battle)

    compare_death_opcode_state(battle, resident)
    rows = resident.death_opcode_state_bytes()
    assert b'"base_damage":17' in rows
    assert b'"radius_units":1375' in rows
    assert b'"knockback_units":625' in rows
    assert b'"hits_air":false' in rows


def test_timed_explosive_death_spawn_payload_remains_fail_closed() -> None:
    battle = BattleState(rng=random.Random(8102))
    _spawn(battle, "Balloon", 0, Position(9.0, 14.0))
    resident = ResidentRustBattle.from_battle(battle)
    entity_before = resident.entity_state_bytes()
    rng_before = resident.rng_state_bytes()

    assert not resident.supports_complete_tick
    with pytest.raises(RuntimeError, match="rejected combat capability"):
        resident.advance_complete_tick()

    assert resident.entity_state_bytes() == entity_before
    assert resident.rng_state_bytes() == rng_before


def test_lethal_direct_hit_dispatches_damage_and_knockback_in_same_tick() -> None:
    battle = BattleState(rng=random.Random(8103))
    attacker = _spawn(battle, "Knight", 1, Position(9.0, 13.5))
    source = _spawn_golemite(battle, 0, Position(9.0, 14.0))
    survivor = _spawn(battle, "Knight", 1, Position(10.5, 14.0))
    _activate(attacker, source, survivor)
    attacker.damage = source.hitpoints + 1
    attacker.attack_cooldown = 0.0
    survivor.attack_cooldown = survivor.get_base_attack_interval_seconds()
    resident = ResidentRustBattle.from_battle(battle)
    rng_before = resident.rng_state_bytes()

    assert resident.supports_complete_tick
    assert resident.advance_complete_tick()
    battle._step_logic_tick(refresh_fast_path_end=False)

    _compare_complete_state(battle, resident)
    assert source.id not in battle.entities
    assert survivor.hitpoints < survivor.max_hitpoints
    assert survivor.position.x > 10.5
    assert resident.rng_state_bytes() == rng_before


def test_nested_death_damage_uses_committed_outer_target_order() -> None:
    battle = BattleState(rng=random.Random(8104))
    attacker = _spawn(battle, "Knight", 1, Position(9.0, 13.5))
    first = _spawn_golemite(battle, 0, Position(9.0, 14.0))
    second = _spawn_golemite(battle, 1, Position(10.0, 14.0))
    trailing = _spawn(battle, "Knight", 1, Position(10.75, 14.0))
    _activate(attacker, first, second, trailing)
    attacker.damage = first.hitpoints + 1
    attacker.attack_cooldown = 0.0
    second.hitpoints = 1
    trailing.attack_cooldown = trailing.get_base_attack_interval_seconds()
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_complete_tick
    assert resident.advance_complete_tick()
    battle._step_logic_tick(refresh_fast_path_end=False)

    _compare_complete_state(battle, resident)
    assert first.id not in battle.entities
    assert second.id not in battle.entities
    assert trailing.hitpoints < trailing.max_hitpoints


def test_projectile_lethal_hit_dispatches_death_damage_in_object_phase() -> None:
    battle = BattleState(rng=random.Random(8106))
    attacker = _spawn(battle, "Musketeer", 1, Position(9.0, 13.5))
    source = _spawn_golemite(battle, 0, Position(9.0, 14.0))
    _activate(attacker, source)
    attacker.damage = source.hitpoints + 1
    attacker.attack_cooldown = 0.0
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_complete_tick
    assert resident.advance_complete_tick()
    battle._step_logic_tick(refresh_fast_path_end=False)

    _compare_complete_state(battle, resident)
    assert source.id not in battle.entities
    assert attacker.hitpoints < attacker.max_hitpoints
    assert attacker._knockback_target is not None


def test_death_damage_shield_consumes_hit_but_survivor_is_knocked_back() -> None:
    battle = BattleState(rng=random.Random(8107))
    attacker = _spawn(battle, "Knight", 1, Position(9.0, 13.5))
    source = _spawn_golemite(battle, 0, Position(9.0, 14.0))
    shielded = _spawn(battle, "Knight", 1, Position(10.5, 14.0))
    shield = Shield(shield_hp=500)
    shielded.mechanics = [shield]
    shield.on_attach(shielded)
    _activate(attacker, source, shielded)
    attacker.damage = source.hitpoints + 1
    attacker.attack_cooldown = 0.0
    shielded.attack_cooldown = shielded.get_base_attack_interval_seconds()
    hp_before = shielded.hitpoints
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_complete_tick
    assert resident.advance_complete_tick()
    battle._step_logic_tick(refresh_fast_path_end=False)

    _compare_complete_state(battle, resident)
    assert shielded.hitpoints == hp_before
    assert shield.current_shield < shield.max_shield
    assert shielded.position.x > 10.5


def test_lifetime_death_dispatches_before_later_building_component() -> None:
    battle = BattleState(rng=random.Random(8108))
    source = _lifetime_building(
        battle,
        player_id=0,
        position=Position(9.0, 14.0),
        lifetime_ms=50,
    )
    target = _lifetime_building(
        battle,
        player_id=1,
        position=Position(9.5, 14.0),
        lifetime_ms=1_000,
    )
    nova = DeathDamage(radius_tiles=2.0, damage=200)
    source.mechanics = [nova]
    nova.on_attach(source)
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_building_lifetime_phase()
    for entity in list(battle.entities.values()):
        if isinstance(entity, Building) and entity.is_alive:
            entity.update_hitpoint_component(battle.dt)

    compare_building_lifetime_phase(battle, resident)
    compare_death_opcode_state(battle, resident)
    compare_resident_entities(battle, resident)
    compare_resident_rng(battle.rng, resident)
    assert not source.is_alive
    assert not target.is_alive
    assert target.lifetime_elapsed == 0.0
