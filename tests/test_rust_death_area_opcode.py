from __future__ import annotations

import copy
import json
import random

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import AreaEffect, Building, Entity, Troop
from clasher.mechanics.mechanic_base import BaseMechanic
from clasher.mechanics.shared.death_area import (
    DeathAreaEffect,
    spawn_death_area_object,
)
from clasher.rust_core import (
    ResidentRustBattle,
    compare_area_effect_state,
    compare_death_opcode_state,
    compare_resident_rng,
    rust_core_available,
)
from clasher.rust_differential import (
    python_resident_semantic_snapshot,
    rust_resident_semantic_snapshot,
)

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _empty_battle(seed: int) -> BattleState:
    battle = BattleState(rng=random.Random(seed))
    battle.entities.clear()
    battle.next_entity_id = 1
    return battle


def _spawn(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Entity:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(position, player_id, stats)
    return next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before
    )


def _activate(*entities: Entity) -> None:
    for entity in entities:
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        entity._spawn_hook_pending = False
        entity._spawn_hook_fired = True


def _spawn_building(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Building:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    building = battle._spawn_entity(Building, position, player_id, stats)
    assert isinstance(building, Building)
    _activate(building)
    return building


def _ice_area_data(battle: BattleState) -> tuple[object, dict]:
    stats = battle.card_loader.get_card("IceGolem")
    assert stats is not None
    source = _spawn(battle, "IceGolem", 0, Position(5.0, 5.0))
    mechanic = next(
        mechanic
        for mechanic in source.mechanics
        if isinstance(mechanic, DeathAreaEffect)
    )
    area_data = copy.deepcopy(mechanic.area_data)
    battle.entities.pop(source.id)
    return stats, area_data


def _spawn_area(
    battle: BattleState,
    *,
    position: Position | None = None,
) -> AreaEffect:
    stats, area_data = _ice_area_data(battle)
    if position is None:
        position = Position(5.0, 5.0)
    area = spawn_death_area_object(
        battle,
        player_id=0,
        position=position,
        card_stats=stats,
        area_data=area_data,
    )
    assert isinstance(area, AreaEffect)
    return area


def _advance_lockstep(
    battle: BattleState,
    resident: ResidentRustBattle,
) -> None:
    assert resident.advance_complete_tick()
    battle._step_logic_tick(refresh_fast_path_end=False)
    assert rust_resident_semantic_snapshot(
        resident
    ) == python_resident_semantic_snapshot(battle)
    compare_resident_rng(battle.rng, resident)


def test_ice_golem_death_opcodes_preserve_damage_then_area_order() -> None:
    battle = _empty_battle(8801)
    source = _spawn(battle, "IceGolem", 0, Position(9.0, 14.0))
    assert isinstance(source, Troop)
    resident = ResidentRustBattle.from_battle(battle)

    compare_death_opcode_state(battle, resident)
    rows = json.loads(resident.death_opcode_state_bytes())
    source_rows = [row for row in rows if row["id"] == source.id]
    assert [row["opcode_type"] for row in source_rows] == ["damage", "area"]
    area_row = source_rows[1]
    assert area_row["area_name"] == "FreezeIceGolemite"
    assert area_row["affects_hidden"] is True
    assert area_row["hits_air"] is True
    assert area_row["hits_ground"] is True
    assert area_row["radius_units"] == 2000
    assert area_row["movement_multiplier"] == {
        "bits": "3fe6666666666666",
        "kind": "float",
    }
    assert area_row["attack_multiplier"] == area_row["movement_multiplier"]
    assert area_row["spawn_multiplier"] == area_row["movement_multiplier"]
    assert resident.supports_complete_tick


def test_lethal_hit_spawns_and_updates_ice_area_in_same_object_frame() -> None:
    battle = _empty_battle(8802)
    attacker = _spawn(battle, "Knight", 1, Position(9.0, 13.5))
    source = _spawn(battle, "IceGolem", 0, Position(9.0, 14.0))
    survivor = _spawn(battle, "Knight", 1, Position(10.5, 14.0))
    assert isinstance(attacker, Troop)
    assert isinstance(source, Troop)
    assert isinstance(survivor, Troop)
    _activate(attacker, source, survivor)
    attacker.damage = source.hitpoints + 1
    attacker.attack_cooldown = 0.0
    survivor.attack_cooldown = survivor.get_base_attack_interval_seconds()
    resident = ResidentRustBattle.from_battle(battle)
    rng_before = resident.rng_state_bytes()

    assert resident.supports_complete_tick
    _advance_lockstep(battle, resident)

    areas = [entity for entity in battle.entities.values() if isinstance(entity, AreaEffect)]
    assert len(areas) == 1
    assert areas[0].time_alive == battle.dt
    assert areas[0].effect_snapshot_applied
    assert survivor.slow_timer == 2.0
    assert survivor.slow_multiplier == 0.7
    assert survivor.attack_speed_debuff_multiplier == 0.7
    assert survivor.spawn_speed_debuff_multiplier == 0.7
    assert source.id not in battle.entities
    compare_area_effect_state(battle, resident)
    assert resident.rng_state_bytes() == rng_before

    _advance_lockstep(battle, resident)
    assert survivor.slow_timer == 2.0 - battle.dt


def test_one_shot_area_uses_strict_native_geometry_and_hit_planes() -> None:
    battle = _empty_battle(8803)
    ground_inside = _spawn(battle, "Knight", 1, Position(7.499, 5.0))
    ground_tangent = _spawn(battle, "Knight", 1, Position(2.5, 5.0))
    air_inside = _spawn(battle, "MegaMinion", 1, Position(5.0, 7.0))
    building_inside = _spawn_building(
        battle, "Cannon", 1, Position(5.0, 2.401)
    )
    building_tangent = _spawn_building(
        battle, "Cannon", 1, Position(5.0, 7.6)
    )
    _activate(
        ground_inside,
        ground_tangent,
        air_inside,
        building_inside,
        building_tangent,
    )
    area = _spawn_area(battle)
    area.hits_air = False
    area.hits_ground = True
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_complete_tick
    _advance_lockstep(battle, resident)

    assert ground_inside.slow_multiplier == 0.7
    assert building_inside.slow_multiplier == 0.7
    assert ground_tangent.slow_multiplier == 1.0
    assert building_tangent.slow_multiplier == 1.0
    assert air_inside.slow_multiplier == 1.0


def test_one_shot_area_preserves_distinct_axes_and_capped_refresh() -> None:
    battle = _empty_battle(8807)
    target = _spawn(battle, "Knight", 1, Position(6.0, 5.0))
    _activate(target)
    area = _spawn_area(battle)
    area.duration = 0.075
    area.speed_multiplier = 0.6
    area.attack_speed_multiplier = 0.7
    area.spawn_speed_multiplier = 0.8
    area.slow_refresh_duration = 2.0
    area.cap_buff_time_to_effect = True
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_complete_tick
    _advance_lockstep(battle, resident)

    assert target.slow_multiplier == 0.6
    assert target.attack_speed_debuff_multiplier == 0.7
    assert target.spawn_speed_debuff_multiplier == 0.8
    assert target.slow_timer == pytest.approx(0.025)


def test_active_ice_area_lives_exactly_twenty_logic_frames() -> None:
    battle = _empty_battle(8804)
    area = _spawn_area(battle)
    area_id = area.id
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_complete_tick
    for _ in range(19):
        _advance_lockstep(battle, resident)
        assert area_id in battle.entities
    _advance_lockstep(battle, resident)
    assert area_id not in battle.entities


def test_nested_ice_deaths_allocate_inner_area_before_outer_area() -> None:
    battle = _empty_battle(8805)
    attacker = _spawn(battle, "Knight", 1, Position(9.0, 13.5))
    outer = _spawn(battle, "IceGolem", 0, Position(9.0, 14.0))
    inner = _spawn(battle, "IceGolem", 1, Position(10.0, 14.0))
    assert isinstance(attacker, Troop)
    assert isinstance(outer, Troop)
    assert isinstance(inner, Troop)
    _activate(attacker, outer, inner)
    attacker.damage = outer.hitpoints + 1
    attacker.attack_cooldown = 0.0
    inner.hitpoints = 1
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_complete_tick
    _advance_lockstep(battle, resident)

    areas = sorted(
        (
            entity
            for entity in battle.entities.values()
            if isinstance(entity, AreaEffect)
        ),
        key=lambda entity: entity.id,
    )
    assert [area.player_id for area in areas] == [1, 0]
    assert [area.id for area in areas] == list(range(areas[0].id, areas[0].id + 2))


@pytest.mark.parametrize(
    "failure",
    [
        "container",
        "haste",
        "periodic",
        "freeze",
        "zero_stun",
        "tornado",
        "guard",
    ],
)
def test_uncompiled_area_capabilities_reject_atomically(failure: str) -> None:
    battle = _empty_battle(8806)
    if failure in {"container", "haste"}:
        source = _spawn(battle, "IceGolem", 0, Position(5.0, 5.0))
        mechanic = next(
            mechanic
            for mechanic in source.mechanics
            if isinstance(mechanic, DeathAreaEffect)
        )
        if failure == "container":
            mechanic.area_data["onStartingActionData"] = {
                "spawnDataData": {"deathAreaEffectData": {}}
            }
        else:
            mechanic.area_data["buffData"]["speedMultiplier"] = 130
    else:
        area = _spawn_area(battle)
        if failure == "periodic":
            area.effect_on_spawn_only = False
            area.effect_tick_interval = battle.dt
        elif failure == "freeze":
            area.freeze_effect = True
        elif failure == "zero_stun":
            area.speed_multiplier = 0.0
            area.attack_speed_multiplier = 0.0
            area.spawn_speed_multiplier = 0.0
        elif failure == "tornado":
            area.is_tornado = True
            area.attract_percentage = 1.0
        else:
            target = _spawn(battle, "Knight", 1, Position(6.0, 5.0))
            target.mechanics.append(BaseMechanic())
    resident = ResidentRustBattle.from_battle(battle)
    checkpoint_before = resident.checkpoint_bytes()
    entity_before = resident.entity_state_bytes()
    area_before = resident.area_effect_state_bytes()
    rng_before = resident.rng_state_bytes()

    assert not resident.supports_complete_tick
    with pytest.raises(RuntimeError, match="rejected combat capability"):
        resident.advance_complete_tick()

    assert resident.checkpoint_is_current
    assert resident.checkpoint_bytes() == checkpoint_before
    assert resident.entity_state_bytes() == entity_before
    assert resident.area_effect_state_bytes() == area_before
    assert resident.rng_state_bytes() == rng_before
