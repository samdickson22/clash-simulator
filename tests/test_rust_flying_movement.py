from __future__ import annotations

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.rust_core import (
    ResidentRustBattle,
    compare_flying_movement_phase,
    rust_core_available,
)

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _empty_battle() -> BattleState:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    return battle


def _spawn_one(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(position, player_id, stats)
    troop = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )
    troop.deploy_delay_remaining = 0.0
    troop.placement_pending = False
    troop._spawn_hook_pending = False
    troop._spawn_hook_fired = True
    return troop


def _advance_python_movement(battle: BattleState) -> None:
    for entity in list(battle.entities.values()):
        if not isinstance(entity, (Troop, Building)) or not entity.is_alive:
            continue
        if isinstance(entity, Troop):
            battle._accumulate_troop_collision_for(entity)
        entity.begin_movement_tick()
        try:
            entity.update_movement_component(battle.dt, battle)
        finally:
            entity.finish_movement_tick(battle)
            entity.quantize_logic_position()


@pytest.mark.parametrize(
    ("start", "target_position"),
    [
        (Position(9.0, 12.0), Position(9.0, 20.0)),
        (Position(9.0, 20.0), Position(9.0, 12.0)),
        (Position(4.0, 12.0), Position(14.0, 20.0)),
        (Position(14.0, 20.0), Position(4.0, 12.0)),
    ],
)
def test_flying_natural_movement_matches_python_route_goal(
    start: Position,
    target_position: Position,
) -> None:
    battle = _empty_battle()
    flying = _spawn_one(battle, "Bats", 0, start)
    target = _spawn_one(battle, "Knight", 1, target_position)
    flying._movement_target_id = target.id
    resident = ResidentRustBattle.from_battle(battle)
    rng_before = resident.rng_state_bytes()

    assert resident.supports_flying_movement_phase
    for _ in range(4):
        resident.advance_flying_movement_phase()
        _advance_python_movement(battle)
        compare_flying_movement_phase(battle, resident)

    assert resident.rng_state_bytes() == rng_before


def test_flying_movement_matches_air_collision_and_avoidance_order() -> None:
    battle = _empty_battle()
    first = _spawn_one(battle, "Bats", 0, Position(9.0, 12.0))
    second = _spawn_one(battle, "Bats", 1, Position(9.0, 13.0))
    first._movement_target_id = second.id
    second._movement_target_id = first.id
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_flying_movement_phase
    resident.advance_flying_movement_phase()
    _advance_python_movement(battle)

    compare_flying_movement_phase(battle, resident)


def test_flying_route_consumes_goal_then_tracks_live_target_center() -> None:
    battle = _empty_battle()
    flying = _spawn_one(battle, "BabyDragon", 0, Position(2.0, 10.0))
    target = _spawn_one(battle, "Knight", 1, Position(4.0, 14.0))
    flying._movement_target_id = target.id
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_flying_movement_phase()
    _advance_python_movement(battle)

    compare_flying_movement_phase(battle, resident)
    assert flying.position == Position(2.063, 10.063)
    assert flying._native_ground_route_cells == []

    target.position = Position(4.5, 14.5)
    resident = ResidentRustBattle.from_battle(battle)
    resident.advance_flying_movement_phase()
    _advance_python_movement(battle)

    compare_flying_movement_phase(battle, resident)


def test_hovering_natural_movement_uses_single_node_route() -> None:
    battle = _empty_battle()
    hover = _spawn_one(battle, "Knight", 0, Position(4.0, 12.0))
    target = _spawn_one(battle, "Knight", 1, Position(14.0, 20.0))
    hover._is_hover_unit = True
    hover._movement_target_id = target.id
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_flying_movement_phase
    resident.advance_flying_movement_phase()
    _advance_python_movement(battle)

    compare_flying_movement_phase(battle, resident)


def test_flying_movement_composes_status_and_external_vector() -> None:
    battle = _empty_battle()
    flying = _spawn_one(battle, "Bats", 0, Position(9.0, 12.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 20.0))
    flying._movement_target_id = target.id
    flying.apply_slow(1.0, 0.7)
    flying.apply_haste(1.0, 1.3, 1.3)
    flying.accumulate_movement_vector_units(30, -40, bypasses_cap=True)
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_flying_movement_phase
    resident.advance_flying_movement_phase()
    _advance_python_movement(battle)

    compare_flying_movement_phase(battle, resident)


def test_flying_movement_invalid_target_applies_only_external_vector() -> None:
    battle = _empty_battle()
    flying = _spawn_one(battle, "Bats", 0, Position(9.0, 12.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 20.0))
    flying._movement_target_id = target.id
    flying._native_natural_movement_active = True
    flying.accumulate_movement_vector_units(40, -30, bypasses_cap=True)
    target.is_alive = False
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_flying_movement_phase
    resident.advance_flying_movement_phase()
    _advance_python_movement(battle)

    compare_flying_movement_phase(battle, resident)
    assert flying.position == Position(9.04, 11.97)
    assert not flying._native_natural_movement_active


def test_flying_movement_rechecks_targetability_without_plane_filter() -> None:
    battle = _empty_battle()
    flying = _spawn_one(battle, "Bats", 0, Position(9.0, 12.0))
    target = _spawn_one(battle, "Knight", 1, Position(9.0, 20.0))
    flying._can_attack_ground_cached = False
    flying._movement_target_id = target.id
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_flying_movement_phase
    resident.advance_flying_movement_phase()
    _advance_python_movement(battle)

    compare_flying_movement_phase(battle, resident)
    assert flying.position.y > 12.0


def test_flying_movement_rejects_ground_natural_target_before_mutation() -> None:
    battle = _empty_battle()
    ground = _spawn_one(battle, "Knight", 0, Position(9.0, 12.0))
    target = _spawn_one(battle, "Bats", 1, Position(9.0, 20.0))
    ground._movement_target_id = target.id
    resident = ResidentRustBattle.from_battle(battle)
    state_before = resident.flying_movement_state_bytes()
    rng_before = resident.rng_state_bytes()

    assert not resident.supports_flying_movement_phase
    with pytest.raises(RuntimeError, match="flying movement preflight rejected"):
        resident.advance_flying_movement_phase()

    assert resident.flying_movement_state_bytes() == state_before
    assert resident.rng_state_bytes() == rng_before
