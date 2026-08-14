from __future__ import annotations

import random

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.factory.dynamic_factory import (
    building_from_values,
    troop_from_character_data,
    troop_from_values,
)
from clasher.mechanics.mechanic_base import BaseMechanic
from clasher.mechanics.shared.shield import Shield
from clasher.rust_core import (
    ResidentRustBattle,
    compare_building_lifetime_phase,
    compare_character_object_phase,
    compare_clock_phase,
    compare_death_opcode_state,
    compare_ground_movement_phase,
    compare_idle_state,
    compare_locked_direct_combat_phase,
    compare_modifier_phase,
    compare_player_phase,
    compare_point_projectile_phase,
    compare_resident_entities,
    compare_resident_rng,
    compare_shield_state,
    rust_core_available,
)

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


class _AreaEffectBlocker(BaseMechanic):
    def allows_effect(
        self,
        entity: Troop,
        source_kind: str | None,
        *,
        affects_hidden: bool = False,
    ) -> bool:
        del entity, source_kind, affects_hidden
        return False


def _empty_battle(seed: int) -> BattleState:
    battle = BattleState(rng=random.Random(seed))
    battle.entities.clear()
    battle.next_entity_id = 1
    return battle


def _activate(*entities: Troop | Building) -> None:
    for entity in entities:
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        entity._spawn_hook_pending = False
        entity._spawn_hook_fired = True


def _spawn_card(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    troop = battle._spawn_entity(Troop, position, player_id, stats)
    _activate(troop)
    return troop


def _spawn_plain(
    battle: BattleState,
    name: str,
    player_id: int,
    position: Position,
    *,
    allow_invisible_area_damage: bool = False,
) -> Troop:
    stats = troop_from_values(
        name,
        hitpoints=1_000,
        damage=40,
        speed_logic_units_per_tick=60,
        range_tiles=1.2,
        sight_range_tiles=5.5,
        hit_speed_ms=1_000,
        collision_radius_tiles=0.5,
        deploy_time_ms=0,
    )
    stats.allow_area_damage_when_invisible = allow_invisible_area_damage
    troop = battle._spawn_entity(Troop, position, player_id, stats)
    _activate(troop)
    troop.attack_cooldown = troop.get_base_attack_interval_seconds()
    return troop


def _spawn_area_attacker(
    battle: BattleState,
    player_id: int,
    position: Position,
    *,
    radius_units: int,
    self_centered: bool,
) -> Troop:
    stats = troop_from_character_data(
        "DataDrivenAreaFixture",
        {
            "hitpoints": 1_200,
            "damage": 100,
            "speed": 60,
            "range": 1_200,
            "sightRange": 5_500,
            "hitSpeed": 1_000,
            "loadTime": 1_000,
            "collisionRadius": 500,
            "deployTime": 0,
            "areaDamageRadius": radius_units,
            "selfAsAoeCenter": self_centered,
            "tidTarget": "TID_TARGETS_GROUND",
            "attacksGround": True,
            "attacksAir": False,
        },
    )
    troop = battle._spawn_entity(Troop, position, player_id, stats)
    _activate(troop)
    troop.attack_cooldown = 0.0
    return troop


def _spawn_building(
    battle: BattleState,
    player_id: int,
    position: Position,
) -> Building:
    stats = building_from_values(
        name="DirectAreaBuildingFixture",
        hitpoints=1_200,
        damage=0,
        range_tiles=0.0,
        sight_range_tiles=0.0,
        hit_speed_ms=1_000,
        deploy_time_ms=0,
        collision_radius_tiles=1.0,
        lifetime_ms=None,
        target_type="TID_TARGETS_AIR_AND_GROUND",
    )
    building = battle._spawn_entity(Building, position, player_id, stats)
    _activate(building)
    building.attack_cooldown = building.get_base_attack_interval_seconds()
    return building


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
    troop = battle._spawn_entity(Troop, position, player_id, stats)
    _activate(troop)
    troop.attack_cooldown = troop.get_base_attack_interval_seconds()
    return troop


def _compare_complete_state(
    battle: BattleState,
    resident: ResidentRustBattle,
) -> None:
    compare_clock_phase(battle, resident)
    compare_player_phase(battle, resident)
    compare_locked_direct_combat_phase(battle, resident)
    compare_ground_movement_phase(battle, resident)
    compare_building_lifetime_phase(battle, resident)
    compare_modifier_phase(battle, resident)
    compare_character_object_phase(battle, resident)
    compare_point_projectile_phase(battle, resident)
    compare_death_opcode_state(battle, resident)
    compare_shield_state(battle, resident)
    compare_resident_entities(battle, resident)
    compare_resident_rng(battle.rng, resident)
    compare_idle_state(battle, resident)
    assert resident.next_entity_id == battle.next_entity_id
    assert resident.win_conditions_dirty is battle._win_conditions_dirty


def _advance_lockstep(
    battle: BattleState,
    resident: ResidentRustBattle,
) -> None:
    assert resident.advance_complete_tick()
    battle._step_logic_tick(refresh_fast_path_end=False)
    _compare_complete_state(battle, resident)


def _all_reasons(resident: ResidentRustBattle) -> set[str]:
    return {
        str(reason)
        for row in resident.direct_combat_capability()
        for reason in row["reasons"]
    }


def test_real_direct_area_is_data_driven_while_charge_remains_fail_closed() -> None:
    battle = _empty_battle(8201)
    _spawn_card(battle, "Valkyrie", 0, Position(9.0, 14.0))
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_complete_tick
    assert _all_reasons(resident) == set()

    charged = _empty_battle(8202)
    _spawn_card(charged, "DarkPrince", 0, Position(9.0, 14.0))
    rejected = ResidentRustBattle.from_battle(charged)
    reasons = _all_reasons(rejected)

    assert not rejected.supports_complete_tick
    assert "charge_payload" in reasons
    assert "area_damage" not in reasons
    assert "self_centered_aoe" not in reasons


def test_direct_area_rejects_uncompiled_recipient_effect_guard_atomically() -> None:
    battle = _empty_battle(8206)
    attacker = _spawn_area_attacker(
        battle,
        0,
        Position(9.0, 14.0),
        radius_units=1_000,
        self_centered=False,
    )
    target = _spawn_plain(battle, "EffectGuardFixture", 1, Position(9.0, 15.0))
    target.mechanics = [_AreaEffectBlocker()]
    attacker.target_id = target.id
    attacker._last_combat_target_id = target.id
    resident = ResidentRustBattle.from_battle(battle)
    entities_before = resident.entity_state_bytes()
    rng_before = resident.rng_state_bytes()

    assert not resident.supports_complete_tick
    assert "executable_mechanics" in _all_reasons(resident)
    with pytest.raises(RuntimeError, match="rejected combat capability"):
        resident.advance_complete_tick()

    assert resident.entity_state_bytes() == entities_before
    assert resident.rng_state_bytes() == rng_before


def test_target_centered_area_uses_exact_plane_effect_and_hitbox_filters() -> None:
    battle = _empty_battle(8203)
    attacker = _spawn_area_attacker(
        battle,
        0,
        Position(9.0, 14.0),
        radius_units=1_000,
        self_centered=False,
    )
    primary = _spawn_plain(battle, "PrimaryFixture", 1, Position(9.0, 15.0))
    inside = _spawn_plain(battle, "InsideFixture", 1, Position(9.0, 16.0))
    tangent = _spawn_plain(battle, "TangentFixture", 1, Position(9.0, 16.5))
    air = _spawn_plain(battle, "AirFixture", 1, Position(9.5, 15.0))
    air.is_air_unit = True
    hidden = _spawn_plain(battle, "HiddenFixture", 1, Position(8.5, 15.0))
    hidden._stealth_until = 10_000
    visible_hidden = _spawn_plain(
        battle,
        "VisibleHiddenFixture",
        1,
        Position(9.0, 14.5),
        allow_invisible_area_damage=True,
    )
    visible_hidden._stealth_until = 10_000
    immune = _spawn_plain(battle, "ImmuneFixture", 1, Position(9.5, 15.5))
    immune._death_spawn_target_immunity_elapsed_ms = 0
    tangent_building = _spawn_building(battle, 1, Position(11.0, 15.0))
    attacker.target_id = primary.id
    attacker._last_combat_target_id = primary.id
    hp_before = {
        entity.id: entity.hitpoints
        for entity in (
            primary,
            inside,
            tangent,
            air,
            hidden,
            visible_hidden,
            immune,
            tangent_building,
        )
    }
    resident = ResidentRustBattle.from_battle(battle)
    rng_before = resident.rng_state_bytes()

    assert resident.supports_complete_tick
    _advance_lockstep(battle, resident)

    assert primary.hitpoints == hp_before[primary.id] - attacker.damage
    assert inside.hitpoints == hp_before[inside.id] - attacker.damage
    assert visible_hidden.hitpoints == hp_before[visible_hidden.id] - attacker.damage
    for excluded in (tangent, air, hidden, immune, tangent_building):
        assert excluded.hitpoints == hp_before[excluded.id]
    assert resident.rng_state_bytes() == rng_before


def test_self_centered_area_snapshots_primary_before_encounter_ordered_deaths() -> None:
    battle = _empty_battle(8204)
    attacker = _spawn_card(battle, "Valkyrie", 0, Position(9.0, 14.0))
    earlier_bystander = _spawn_golemite(battle, 1, Position(10.5, 14.0))
    primary = _spawn_golemite(battle, 1, Position(9.0, 15.0))
    attacker.target_id = primary.id
    attacker._last_combat_target_id = primary.id
    attacker.attack_cooldown = 0.0
    earlier_bystander.hitpoints = 1
    primary.hitpoints = 1
    resident = ResidentRustBattle.from_battle(battle)
    rng_before = resident.rng_state_bytes()

    assert resident.supports_complete_tick
    _advance_lockstep(battle, resident)

    assert primary.id not in battle.entities
    assert earlier_bystander.id not in battle.entities
    assert attacker.position.x == 9.0
    assert attacker.position.y < 14.0
    assert resident.rng_state_bytes() == rng_before


def test_self_centered_area_routes_shield_and_crown_damage_through_shared_path() -> None:
    battle = BattleState(rng=random.Random(8205))
    attacker = _spawn_card(battle, "Valkyrie", 0, Position(3.5, 24.0))
    primary = _spawn_plain(battle, "CrownPrimaryFixture", 1, Position(4.5, 24.0))
    shielded = _spawn_plain(battle, "ShieldFixture", 1, Position(3.5, 23.5))
    shield = Shield(shield_hp=500)
    shielded.mechanics = [shield]
    shield.on_attach(shielded)
    attacker.target_id = primary.id
    attacker._last_combat_target_id = primary.id
    attacker.attack_cooldown = 0.0
    hp_before = shielded.hitpoints
    tower = next(
        entity
        for entity in battle.entities.values()
        if entity.player_id == 1
        and getattr(entity, "_crown_tower_slot", None) == "left"
    )
    tower_hp_before = tower.hitpoints
    resident = ResidentRustBattle.from_battle(battle)
    rng_before = resident.rng_state_bytes()

    assert resident.supports_complete_tick
    _advance_lockstep(battle, resident)

    assert shielded.hitpoints == hp_before
    assert shield.current_shield == shield.max_shield - attacker.damage
    assert tower.hitpoints == tower_hp_before - attacker.damage
    assert battle.players[1].left_tower_hp == tower.hitpoints
    assert not battle._win_conditions_dirty
    assert not resident.win_conditions_dirty
    assert resident.rng_state_bytes() == rng_before
