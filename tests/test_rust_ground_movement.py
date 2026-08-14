from __future__ import annotations

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.pathfinding import ground_path_waypoint
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
    ("player_id", "start", "target_position"),
    [
        (0, Position(9.25, 8.75), Position(9.25, 14.25)),
        (1, Position(9.25, 23.25), Position(9.25, 17.75)),
        (0, Position(4.25, 10.25), Position(13.75, 21.75)),
        (1, Position(13.75, 21.75), Position(4.25, 10.25)),
    ],
)
def test_ground_natural_movement_matches_python_route_and_cache(
    player_id: int,
    start: Position,
    target_position: Position,
) -> None:
    battle = _empty_battle()
    mover = _spawn_troop(battle, "Knight", player_id, start)
    target = _spawn_troop(
        battle,
        "Knight",
        1 - player_id,
        target_position,
    )
    mover._movement_target_id = target.id
    resident = ResidentRustBattle.from_battle(battle)
    rng_before = resident.rng_state_bytes()

    assert resident.supports_ground_movement_phase
    for _ in range(4):
        resident.advance_ground_movement_phase()
        _advance_python_movement(battle)
        compare_ground_movement_phase(battle, resident)

    assert resident.rng_state_bytes() == rng_before


def test_ground_movement_composes_status_collision_and_external_vector() -> None:
    battle = _empty_battle()
    mover = _spawn_troop(battle, "Knight", 0, Position(9.0, 12.0))
    target = _spawn_troop(battle, "Knight", 1, Position(9.0, 20.0))
    blocker = _spawn_troop(battle, "Knight", 1, Position(9.0, 12.8))
    mover._movement_target_id = target.id
    blocker._movement_target_id = mover.id
    mover.apply_slow(1.0, 0.7)
    mover.apply_haste(1.0, 1.3, 1.3)
    mover.accumulate_movement_vector_units(30, -40, bypasses_cap=True)
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_ground_movement_phase
    resident.advance_ground_movement_phase()
    _advance_python_movement(battle)

    compare_ground_movement_phase(battle, resident)


def test_ground_movement_fixed_trace_hash_is_pinned() -> None:
    battle = _empty_battle()
    mover = _spawn_troop(battle, "Knight", 0, Position(9.25, 8.75))
    target = _spawn_troop(battle, "Knight", 1, Position(9.25, 14.25))
    mover._movement_target_id = target.id
    resident = ResidentRustBattle.from_battle(battle)
    rng_before = resident.rng_state_bytes()

    for _ in range(4):
        resident.advance_ground_movement_phase()
        _advance_python_movement(battle)
        compare_ground_movement_phase(battle, resident)

    assert (
        resident.ground_movement_sha256()
        == "32e553e5853842bf9ab805ff4f653cd8807397248f1a68f735b3751016e60b3c"
    )
    assert resident.rng_state_bytes() == rng_before


def test_ground_movement_reuses_empty_route_for_moving_target() -> None:
    battle = _empty_battle()
    mover = _spawn_troop(battle, "Knight", 0, Position(9.25, 12.25))
    target = _spawn_troop(battle, "Knight", 1, Position(9.25, 13.0))
    mover._movement_target_id = target.id
    ground_path_waypoint(
        battle,
        mover,
        target.position,
        target_entity=target,
        backwards_reference=target.position,
    )
    mover._native_ground_route_cells = []
    target.position = Position(9.4, 13.1)
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_ground_movement_phase
    resident.advance_ground_movement_phase()
    _advance_python_movement(battle)

    compare_ground_movement_phase(battle, resident)


def test_ground_start_cell_first_miss_then_empty_hit_tracks_live_target() -> None:
    battle = _empty_battle()
    mover = _spawn_troop(battle, "Knight", 0, Position(9.25, 12.25))
    target = _spawn_troop(battle, "Knight", 1, Position(9.25, 14.25))
    mover.range = 3.0
    mover._movement_target_id = target.id
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_ground_movement_phase()
    _advance_python_movement(battle)
    compare_ground_movement_phase(battle, resident)
    assert mover.position == Position(9.25, 12.25)
    assert mover._native_ground_route_cells == []

    target.position = Position(9.5, 14.5)
    resident = ResidentRustBattle.from_battle(battle)
    resident.advance_ground_movement_phase()
    _advance_python_movement(battle)
    compare_ground_movement_phase(battle, resident)
    assert mover.position != Position(9.25, 12.25)


def test_ground_cache_hit_restores_backwards_without_replanning() -> None:
    battle = _empty_battle()
    mover = _spawn_troop(battle, "Knight", 0, Position(9.25, 12.25))
    target = _spawn_troop(battle, "Knight", 1, Position(9.25, 20.25))
    mover._movement_target_id = target.id
    ground_path_waypoint(
        battle,
        mover,
        target.position,
        target_entity=target,
        backwards_reference=target.position,
    )
    cached_cells = list(mover._native_ground_route_cells)
    mover._ground_path_cache_backwards = True
    mover._ground_path_backwards = False
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_ground_movement_phase()
    _advance_python_movement(battle)

    compare_ground_movement_phase(battle, resident)
    assert mover._ground_path_backwards
    assert mover._native_ground_route_cells == cached_cells[1:]


def test_ground_lane_change_forces_exact_cache_miss() -> None:
    battle = _empty_battle()
    mover = _spawn_troop(battle, "Knight", 0, Position(9.25, 12.25))
    target = _spawn_troop(battle, "Knight", 1, Position(9.25, 20.25))
    mover._movement_target_id = target.id
    ground_path_waypoint(
        battle,
        mover,
        target.position,
        target_entity=target,
        backwards_reference=target.position,
    )
    old_key = mover._ground_path_cache_key
    mover._native_lane_id = 1 if mover._native_lane_id != 1 else 2
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_ground_movement_phase()
    _advance_python_movement(battle)

    compare_ground_movement_phase(battle, resident)
    assert mover._ground_path_cache_key != old_key
    assert mover._ground_path_cache_key[1] == mover._native_lane_id


def test_ground_missing_goal_preserves_stale_cache() -> None:
    battle = _empty_battle()
    mover = _spawn_troop(battle, "Knight", 0, Position(9.25, 12.25))
    target = _spawn_troop(battle, "Knight", 1, Position(9.13, 14.37))
    mover.range = 0.0
    mover._movement_target_id = target.id
    mover._ground_path_cache_key = ((18, 24), mover._native_lane_id, False)
    mover._native_ground_route_cells = [(18, 25), (18, 26)]
    mover._ground_path_cache_backwards = True
    mover._ground_path_backwards = True
    old_key = mover._ground_path_cache_key
    old_cells = list(mover._native_ground_route_cells)
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_ground_movement_phase()
    _advance_python_movement(battle)

    compare_ground_movement_phase(battle, resident)
    assert mover._ground_path_cache_key == old_key
    assert mover._native_ground_route_cells == old_cells
    assert not mover._ground_path_backwards


def test_ground_static_avoidance_pops_retained_node_before_movement() -> None:
    battle = _empty_battle()
    mover = _spawn_troop(battle, "Knight", 0, Position(9.25, 12.25))
    target = _spawn_troop(battle, "Knight", 1, Position(9.25, 20.25))
    mover._movement_target_id = target.id
    ground_path_waypoint(
        battle,
        mover,
        target.position,
        target_entity=target,
        backwards_reference=target.position,
    )
    assert len(mover._native_ground_route_cells) >= 2
    first_cell = mover._native_ground_route_cells[0]
    stats = battle.card_loader.get_card("Cannon")
    assert stats is not None
    building = battle._spawn_entity(
        Building,
        Position(first_cell[0] * 0.5 + 0.25, first_cell[1] * 0.5 + 0.25),
        0,
        stats,
    )
    building.deploy_delay_remaining = 0.0
    original_route = list(mover._native_ground_route_cells)
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_ground_movement_phase
    resident.advance_ground_movement_phase()
    _advance_python_movement(battle)

    compare_ground_movement_phase(battle, resident)
    assert len(mover._native_ground_route_cells) < len(original_route)
    assert mover._native_ground_route_cells[:1] != original_route[:1]


def test_ground_movement_invalid_target_applies_only_external_vector() -> None:
    battle = _empty_battle()
    mover = _spawn_troop(battle, "Knight", 0, Position(9.0, 12.0))
    target = _spawn_troop(battle, "Knight", 1, Position(9.0, 20.0))
    mover._movement_target_id = target.id
    mover._native_natural_movement_active = True
    mover.accumulate_movement_vector_units(40, -30, bypasses_cap=True)
    target.is_alive = False
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_ground_movement_phase
    resident.advance_ground_movement_phase()
    _advance_python_movement(battle)

    compare_ground_movement_phase(battle, resident)
    assert mover.position == Position(9.04, 11.97)
    assert not mover._native_natural_movement_active


def test_ground_movement_rejects_jump_height_before_mutation() -> None:
    battle = _empty_battle()
    mover = _spawn_troop(battle, "Knight", 0, Position(9.0, 12.0))
    target = _spawn_troop(battle, "Knight", 1, Position(9.0, 20.0))
    mover._movement_target_id = target.id
    mover.card_stats.jump_height = 1.0
    resident = ResidentRustBattle.from_battle(battle)
    state_before = resident.ground_movement_state_bytes()
    rng_before = resident.rng_state_bytes()

    assert not resident.supports_ground_movement_phase
    with pytest.raises(RuntimeError, match="ground movement preflight rejected"):
        resident.advance_ground_movement_phase()

    assert resident.ground_movement_state_bytes() == state_before
    assert resident.rng_state_bytes() == rng_before


def test_ground_movement_rejects_lossy_targetless_route_cache() -> None:
    battle = _empty_battle()
    mover = _spawn_troop(battle, "Knight", 0, Position(9.0, 12.0))
    mover._ground_path_cache_key = ("unsupported", (18, 24))
    mover._native_ground_route_cells = []
    resident = ResidentRustBattle.from_battle(battle)
    state_before = resident.ground_movement_state_bytes()
    rng_before = resident.rng_state_bytes()

    assert not resident.supports_ground_movement_phase
    with pytest.raises(RuntimeError, match="ground movement preflight rejected"):
        resident.advance_ground_movement_phase()

    assert resident.ground_movement_state_bytes() == state_before
    assert resident.rng_state_bytes() == rng_before
