from __future__ import annotations

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.rust_core import (
    ResidentRustBattle,
    compare_stationary_movement_phase,
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


def _spawn_troop(
    battle: BattleState,
    *,
    player_id: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    troop = battle._spawn_entity(Troop, position, player_id, stats)
    troop.deploy_delay_remaining = 0.0
    troop.placement_pending = False
    troop._spawn_hook_pending = False
    troop._spawn_hook_fired = True
    troop.target_id = None
    troop._movement_target_id = None
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


@pytest.mark.parametrize("first_player", [0, 1])
def test_stationary_collision_preserves_sequential_owner_relative_order(
    first_player: int,
) -> None:
    battle = _empty_battle()
    first = _spawn_troop(
        battle,
        player_id=first_player,
        position=Position(9.0, 12.0),
    )
    second = _spawn_troop(
        battle,
        player_id=1 - first_player,
        position=Position(9.0, 12.0),
    )
    resident = ResidentRustBattle.from_battle(battle)
    rng_before = resident.rng_state_bytes()

    assert resident.supports_stationary_movement_phase
    resident.advance_stationary_movement_phase()
    _advance_python_movement(battle)

    compare_stationary_movement_phase(battle, resident)
    assert first.position != second.position
    assert resident.rng_state_bytes() == rng_before


def test_stationary_collision_uses_static_building_mass() -> None:
    battle = _empty_battle()
    troop = _spawn_troop(
        battle,
        player_id=0,
        position=Position(9.0, 12.0),
    )
    stats = battle.card_loader.get_card("Cannon")
    assert stats is not None
    building = battle._spawn_entity(
        Building,
        Position(9.0, 12.0),
        0,
        stats,
    )
    building.deploy_delay_remaining = 0.0
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_stationary_movement_phase
    resident.advance_stationary_movement_phase()
    _advance_python_movement(battle)

    compare_stationary_movement_phase(battle, resident)
    assert troop.position != building.position


@pytest.mark.parametrize("bypasses_cap", [False, True])
def test_stationary_external_vector_cap_matches_python(
    bypasses_cap: bool,
) -> None:
    battle = _empty_battle()
    troop = _spawn_troop(
        battle,
        player_id=0,
        position=Position(9.0, 12.0),
    )
    troop.accumulate_movement_vector_units(
        300,
        400,
        bypasses_cap=bypasses_cap,
    )
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_stationary_movement_phase()
    _advance_python_movement(battle)

    compare_stationary_movement_phase(battle, resident)
    expected = Position(9.3, 12.4) if bypasses_cap else Position(9.09, 12.12)
    assert troop.position == expected


def test_stationary_external_vector_clamps_native_arena_boundary() -> None:
    battle = _empty_battle()
    troop = _spawn_troop(
        battle,
        player_id=0,
        position=Position(0.25, 0.25),
    )
    troop.accumulate_movement_vector_units(
        -500,
        -500,
        bypasses_cap=True,
    )
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_stationary_movement_phase()
    _advance_python_movement(battle)

    compare_stationary_movement_phase(battle, resident)
    assert troop.position == Position(0.25, 0.25)


def test_stationary_movement_rejects_natural_target_before_mutation() -> None:
    battle = _empty_battle()
    troop = _spawn_troop(
        battle,
        player_id=0,
        position=Position(9.0, 12.0),
    )
    target = _spawn_troop(
        battle,
        player_id=1,
        position=Position(9.0, 16.0),
    )
    troop._movement_target_id = target.id
    resident = ResidentRustBattle.from_battle(battle)
    state_before = resident.stationary_movement_state_bytes()
    rng_before = resident.rng_state_bytes()

    assert not resident.supports_stationary_movement_phase
    with pytest.raises(RuntimeError, match="stationary movement preflight rejected"):
        resident.advance_stationary_movement_phase()

    assert resident.stationary_movement_state_bytes() == state_before
    assert resident.rng_state_bytes() == rng_before
