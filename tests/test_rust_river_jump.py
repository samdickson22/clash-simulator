from __future__ import annotations

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.pathfinding import native_route_goal_cell
from clasher.rust_core import (
    ResidentRustBattle,
    compare_ground_movement_phase,
    rust_core_available,
)

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _spawn_troop(
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
    ("player_id", "start", "target_id"),
    [
        (0, Position(9.0, 14.0), 6),
        (1, Position(9.0, 18.0), 3),
    ],
)
def test_resident_river_jump_matches_full_initiation_and_landing_trace(
    player_id: int,
    start: Position,
    target_id: int,
) -> None:
    battle = BattleState()
    jumper = _spawn_troop(battle, "HogRider", player_id, start)
    jumper._movement_target_id = target_id
    resident = ResidentRustBattle.from_battle(battle)
    rng_before = resident.rng_state_bytes()
    saw_airborne = False
    landing_tick: int | None = None

    for tick in range(80):
        assert resident.supports_ground_movement_phase
        resident.advance_ground_movement_phase()
        _advance_python_movement(battle)
        compare_ground_movement_phase(battle, resident)
        if getattr(jumper, "_river_jump_active", False):
            saw_airborne = True
            assert not resident.supports_direct_combat_phase
            assert jumper.position != jumper._river_jump_target
            assert jumper._native_ground_route_cells == [
                (
                    int(jumper._river_jump_target.x * 2 - 0.5),
                    int(jumper._river_jump_target.y * 2 - 0.5),
                )
            ]
        elif saw_airborne:
            landing_tick = tick
            assert jumper._special_move_consumed_tick
            break

    assert saw_airborne
    assert landing_tick is not None
    assert jumper.position == jumper._river_jump_target
    assert not resident.supports_direct_combat_phase

    resident.advance_ground_movement_phase()
    _advance_python_movement(battle)
    compare_ground_movement_phase(battle, resident)
    assert not jumper._special_move_consumed_tick
    if player_id == 0:
        assert (
            resident.ground_movement_sha256()
            == "3f3ab32635d2f5ed3ddc28d524e018354875d5a7903ca93c185f45aaa29162c1"
        )
    assert resident.rng_state_bytes() == rng_before


def test_resident_active_jumper_uses_air_collision_plane() -> None:
    battle = BattleState()
    jumper = _spawn_troop(battle, "HogRider", 0, Position(9.0, 14.9))
    flying = _spawn_troop(battle, "MegaMinion", 0, Position(9.4, 14.9))
    ground = _spawn_troop(battle, "Knight", 0, Position(9.0, 14.9))
    assert jumper._try_start_river_jump(
        battle.entities[6].position,
        Position(9.0, battle.arena.RIVER_Y1),
        battle,
    )
    ground_start = Position(ground.position.x, ground.position.y)
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_ground_movement_phase
    resident.advance_ground_movement_phase()
    _advance_python_movement(battle)

    compare_ground_movement_phase(battle, resident)
    assert jumper.position.x < 9.0
    assert flying.position.x > 9.4
    assert ground.position == ground_start


def test_external_vector_crosses_river_without_starting_jump() -> None:
    battle = BattleState()
    jumper = _spawn_troop(battle, "HogRider", 0, Position(9.0, 14.99))
    jumper._movement_target_id = 6
    jumper.accumulate_movement_vector_units(1, 1, bypasses_cap=True)
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_ground_movement_phase()
    _advance_python_movement(battle)

    compare_ground_movement_phase(battle, resident)
    assert not getattr(jumper, "_river_jump_active", False)
    assert jumper.position.y > 15.0


@pytest.mark.parametrize("position_x", [0.5, 17.5])
def test_blocked_edge_origin_does_not_start_river_jump(
    position_x: float,
) -> None:
    battle = BattleState()
    jumper = _spawn_troop(
        battle,
        "HogRider",
        0,
        Position(position_x, 14.99),
    )
    jumper.position = Position(position_x, 14.99)
    jumper._movement_target_id = 6
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_ground_movement_phase()
    _advance_python_movement(battle)

    compare_ground_movement_phase(battle, resident)
    assert not getattr(jumper, "_river_jump_active", False)


def test_missing_water_run_sets_blocked_and_preserves_route() -> None:
    battle = BattleState()
    jumper = _spawn_troop(battle, "HogRider", 0, Position(9.0, 14.99))
    target = battle.entities[6]
    jumper._movement_target_id = target.id
    goal = native_route_goal_cell(jumper, target)
    assert goal is not None
    jumper._ground_path_cache_key = (
        goal,
        jumper._native_lane_id,
        True,
    )
    jumper._native_ground_route_cells = [(18, 34)]
    old_route = list(jumper._native_ground_route_cells)
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_ground_movement_phase()
    _advance_python_movement(battle)

    compare_ground_movement_phase(battle, resident)
    assert not getattr(jumper, "_river_jump_active", False)
    assert jumper._river_jump_blocked
    assert jumper._native_ground_route_cells == old_route


@pytest.mark.parametrize("failure", ["speed", "charge", "deferred_stun"])
def test_invalid_river_state_rejects_before_mutation(failure: str) -> None:
    battle = BattleState()
    jumper = _spawn_troop(battle, "HogRider", 0, Position(9.0, 14.9))
    jumper._movement_target_id = 6
    if failure == "speed":
        jumper.card_stats.jump_speed = 0
    elif failure == "charge":
        jumper.card_stats.charge_range = 250
    else:
        assert jumper._try_start_river_jump(
            battle.entities[6].position,
            Position(9.0, battle.arena.RIVER_Y1),
            battle,
        )
        jumper.apply_stun(0.5, source_kind="test")
    resident = ResidentRustBattle.from_battle(battle)
    state_before = resident.ground_movement_state_bytes()
    rng_before = resident.rng_state_bytes()

    assert not resident.supports_ground_movement_phase
    with pytest.raises(RuntimeError, match="ground movement preflight rejected"):
        resident.advance_ground_movement_phase()

    assert resident.ground_movement_state_bytes() == state_before
    assert resident.rng_state_bytes() == rng_before
