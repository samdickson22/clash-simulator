from __future__ import annotations

import math

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.rust_core import (
    ResidentRustBattle,
    compare_ground_movement_phase,
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
    player_id: int,
    position: Position,
    card_name: str = "Knight",
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
    ("player_id", "origin", "endpoint"),
    [
        (0, Position(9.0, 14.0), Position(10.25, 11.835)),
        (1, Position(9.0, 18.0), Position(7.75, 20.165)),
        (0, Position(5.0, 14.0), Position(3.5, 14.0)),
    ],
)
def test_resident_death_spawn_travel_matches_complete_trace(
    player_id: int,
    origin: Position,
    endpoint: Position,
) -> None:
    battle = _empty_battle()
    child = _spawn_troop(battle, player_id, endpoint)
    child.begin_death_spawn_travel(origin)
    child.stun_timer = 99.0
    expected_ticks = child._death_spawn_travel_ticks_remaining
    assert expected_ticks > 0
    resident = ResidentRustBattle.from_battle(battle)
    rng_before = resident.rng_state_bytes()
    assert resident.supports_direct_combat_phase

    for _ in range(expected_ticks):
        assert resident.supports_ground_movement_phase
        resident.advance_ground_movement_phase()
        _advance_python_movement(battle)
        compare_ground_movement_phase(battle, resident)

    assert child._death_spawn_travel_target is None
    assert child._death_spawn_travel_ticks_remaining == 0
    if player_id == 0 and origin == Position(9.0, 14.0):
        # The movement digest includes the data-driven knockback-immunity
        # trait even though this transport does not exercise knockback.
        assert (
            resident.ground_movement_sha256()
                == "c2b64045fbbeaed5cd7691bc4f883c8741dd664639b8d7be9de752b37c6e852b"
        )
    assert resident.rng_state_bytes() == rng_before


def test_death_spawn_travel_composes_collision_avoidance_and_external_vector() -> None:
    battle = _empty_battle()
    child = _spawn_troop(battle, 0, Position(10.25, 11.835))
    child.begin_death_spawn_travel(Position(9.0, 14.0))
    blocker = _spawn_troop(battle, 1, Position(9.4, 14.0))
    blocker.stun_timer = 1.0
    child._native_avoidance = 90
    child.accumulate_movement_vector_units(30, -40, bypasses_cap=True)
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_ground_movement_phase()
    _advance_python_movement(battle)

    compare_ground_movement_phase(battle, resident)
    assert child._death_spawn_travel_ticks_remaining == 8


def test_resident_lava_hound_children_match_data_driven_radial_traces() -> None:
    battle = _empty_battle()
    hound = _spawn_troop(
        battle,
        0,
        Position(9.0, 14.0),
        "LavaHound",
    )
    hound.take_damage(hound.hitpoints)
    children = [
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop) and entity is not hound
    ]
    assert len(children) == 6
    assert sorted(
        child._death_spawn_travel_ticks_remaining for child in children
    ) == [9, 9, 9, 9, 10, 10]
    resident = ResidentRustBattle.from_battle(battle)
    rng_before = resident.rng_state_bytes()

    for _ in range(10):
        assert resident.supports_ground_movement_phase
        resident.advance_ground_movement_phase()
        _advance_python_movement(battle)
        compare_ground_movement_phase(battle, resident)

    assert all(
        child._death_spawn_travel_target is None for child in children
    )
    assert resident.rng_state_bytes() == rng_before


def test_final_travel_frame_precedes_deployment_and_natural_movement() -> None:
    battle = _empty_battle()
    child = _spawn_troop(battle, 0, Position(9.25, 14.0))
    child.begin_death_spawn_travel(Position(9.0, 14.0))
    child.deploy_delay_remaining = 0.5
    child._movement_target_id = 999
    assert child._death_spawn_travel_ticks_remaining == 1
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_ground_movement_phase
    resident.advance_ground_movement_phase()
    _advance_python_movement(battle)

    compare_ground_movement_phase(battle, resident)
    assert child.position == Position(9.25, 14.0)
    assert child.deploy_delay_remaining == 0.5
    assert child._death_spawn_travel_target is None
    assert child._death_spawn_travel_ticks_remaining == 0


@pytest.mark.parametrize(
    "failure",
    [
        "missing_target",
        "zero_ticks",
        "negative_ticks",
        "excessive_ticks",
        "nonfinite",
        "non_grid",
        "out_of_bounds",
        "knockback",
    ],
)
def test_invalid_death_spawn_travel_rejects_before_mutation(failure: str) -> None:
    battle = _empty_battle()
    child = _spawn_troop(battle, 0, Position(10.25, 11.835))
    child.begin_death_spawn_travel(Position(9.0, 14.0))
    if failure == "missing_target":
        child._death_spawn_travel_target = None
    elif failure == "zero_ticks":
        child._death_spawn_travel_ticks_remaining = 0
    elif failure == "negative_ticks":
        child._death_spawn_travel_ticks_remaining = -1
    elif failure == "excessive_ticks":
        child._death_spawn_travel_ticks_remaining = 145
    elif failure == "nonfinite":
        child._death_spawn_travel_target = Position(math.inf, 11.0)
    elif failure == "non_grid":
        child._death_spawn_travel_target = Position(10.2505, 11.835)
    elif failure == "out_of_bounds":
        child._death_spawn_travel_target = Position(0.0, 11.835)
    else:
        child._knockback_target = Position(10.0, 14.0)
        child._knockback_velocity_work = 200
        child.forced_movement_active = True
    resident = ResidentRustBattle.from_battle(battle)
    state_before = resident.ground_movement_state_bytes()
    rng_before = resident.rng_state_bytes()

    assert not resident.supports_ground_movement_phase
    with pytest.raises(RuntimeError, match="ground movement preflight rejected"):
        resident.advance_ground_movement_phase()

    assert resident.ground_movement_state_bytes() == state_before
    assert resident.rng_state_bytes() == rng_before


def test_building_death_spawn_travel_is_rejected_before_mutation() -> None:
    battle = BattleState()
    building = battle.entities[1]
    assert isinstance(building, Building)
    building._death_spawn_travel_target = Position(9.0, 4.0)
    building._death_spawn_travel_ticks_remaining = 1
    resident = ResidentRustBattle.from_battle(battle)
    state_before = resident.ground_movement_state_bytes()
    rng_before = resident.rng_state_bytes()

    assert not resident.supports_ground_movement_phase
    with pytest.raises(RuntimeError, match="ground movement preflight rejected"):
        resident.advance_ground_movement_phase()

    assert resident.ground_movement_state_bytes() == state_before
    assert resident.rng_state_bytes() == rng_before
