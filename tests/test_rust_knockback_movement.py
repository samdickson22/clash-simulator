from __future__ import annotations

import math

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.mechanics.shared.knockback import apply_radial_knockback
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
) -> Troop:
    stats = battle.card_loader.get_card("Knight")
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
        if isinstance(entity, Troop) and not (
            entity._knockback_target is not None
            and entity._knockback_velocity_work < 1
        ):
            battle._accumulate_troop_collision_for(entity)
        entity.begin_movement_tick()
        try:
            entity.update_movement_component(battle.dt, battle)
        finally:
            entity.finish_movement_tick(battle)
            entity.quantize_logic_position()


@pytest.mark.parametrize(
    ("player_id", "start", "origin"),
    [
        (0, Position(9.0, 10.0), Position(6.0, 6.0)),
        (1, Position(9.0, 22.0), Position(12.0, 26.0)),
        (0, Position(9.0, 14.4), Position(9.0, 13.4)),
    ],
)
def test_resident_knockback_matches_complete_velocity_trace(
    player_id: int,
    start: Position,
    origin: Position,
) -> None:
    battle = _empty_battle()
    target = _spawn_troop(battle, player_id, start)
    assert apply_radial_knockback(
        target,
        battle,
        origin,
        1.0,
        ignores_mass=True,
    )
    resident = ResidentRustBattle.from_battle(battle)
    rng_before = resident.rng_state_bytes()

    for tick in range(10):
        assert resident.supports_ground_movement_phase
        resident.advance_ground_movement_phase()
        _advance_python_movement(battle)
        compare_ground_movement_phase(battle, resident)
        if tick < 9:
            assert target._knockback_target is not None
            assert target.forced_movement_active

    assert target._knockback_target is None
    assert target._knockback_velocity_work == 0
    assert not target.forced_movement_active
    if player_id == 0 and start == Position(9.0, 10.0):
        assert (
            resident.ground_movement_sha256()
            == "8d86b6d1facae984eda11e64856b54f7dc64a6235d1b554042fc8a3abd0e0cf8"
        )
    assert resident.rng_state_bytes() == rng_before


def test_resident_knockback_combines_pending_vector_before_boundary_clamp() -> None:
    battle = _empty_battle()
    target = _spawn_troop(battle, 0, Position(0.6, 10.0))
    assert apply_radial_knockback(
        target,
        battle,
        Position(1.6, 10.0),
        1.0,
        ignores_mass=True,
    )
    target.accumulate_movement_vector(0.15, 0.0)
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_ground_movement_phase()
    _advance_python_movement(battle)

    compare_ground_movement_phase(battle, resident)
    assert target.position == Position(0.55, 10.0)


def test_resident_knockback_preserves_then_clears_final_zero_work_frame() -> None:
    battle = _empty_battle()
    target = _spawn_troop(battle, 0, Position(9.0, 10.0))
    blocker = _spawn_troop(battle, 1, Position(9.4, 10.0))
    blocker.stun_timer = 1.0
    target._knockback_target = Position(10.0, 10.0)
    target._knockback_velocity_work = 25
    target._knockback_interrupts_combat = True
    target.forced_movement_active = True
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_ground_movement_phase()
    _advance_python_movement(battle)
    compare_ground_movement_phase(battle, resident)
    first_position = Position(target.position.x, target.position.y)
    assert target._knockback_velocity_work == 0
    assert target.forced_movement_active

    resident.advance_ground_movement_phase()
    _advance_python_movement(battle)
    compare_ground_movement_phase(battle, resident)
    assert target.position == first_position
    assert target._knockback_target is None
    assert not target.forced_movement_active


def test_resident_knockback_keeps_support_after_opposing_controlled_motion() -> None:
    battle = _empty_battle()
    target = _spawn_troop(battle, 0, Position(9.0, 10.0))
    assert apply_radial_knockback(
        target,
        battle,
        Position(8.0, 10.0),
        20.0,
        ignores_mass=True,
    )

    for _ in range(4):
        target.accumulate_movement_vector_units(
            -432,
            0,
            bypasses_cap=True,
        )
        resident = ResidentRustBattle.from_battle(battle)
        assert resident.supports_ground_movement_phase
        resident.advance_ground_movement_phase()
        _advance_python_movement(battle)
        compare_ground_movement_phase(battle, resident)

    assert target._knockback_target is not None
    assert target._knockback_target.x - target.position.x > 10.0


def test_zero_work_clear_frame_consumes_prequeued_controlled_vector() -> None:
    battle = _empty_battle()
    target = _spawn_troop(battle, 0, Position(9.0, 10.0))
    target._knockback_target = Position(10.0, 10.0)
    target._knockback_velocity_work = 0
    target._knockback_interrupts_combat = True
    target.forced_movement_active = True
    target.accumulate_movement_vector_units(75, -50, bypasses_cap=True)
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_ground_movement_phase()
    _advance_python_movement(battle)

    compare_ground_movement_phase(battle, resident)
    assert target.position == Position(9.075, 9.95)
    assert target._knockback_target is None
    assert not target.forced_movement_active


def test_knockback_combat_capability_respects_interrupt_flag() -> None:
    interrupting_battle = _empty_battle()
    interrupting = _spawn_troop(
        interrupting_battle,
        0,
        Position(9.0, 10.0),
    )
    assert interrupting.begin_knockback(
        Position(10.0, 10.0),
        1000,
        source_kind="test",
    )
    interrupting_resident = ResidentRustBattle.from_battle(
        interrupting_battle
    )
    assert not interrupting_resident.supports_direct_combat_phase

    noninterrupting_battle = _empty_battle()
    noninterrupting = _spawn_troop(
        noninterrupting_battle,
        0,
        Position(9.0, 10.0),
    )
    assert noninterrupting.begin_knockback(
        Position(10.0, 10.0),
        1000,
        source_kind="test",
        interrupts_combat=False,
    )
    noninterrupting_resident = ResidentRustBattle.from_battle(
        noninterrupting_battle
    )
    assert noninterrupting_resident.supports_direct_combat_phase


@pytest.mark.parametrize(
    "failure",
    [
        "target",
        "velocity",
        "velocity_stride",
        "velocity_cap",
        "forced",
        "river",
    ],
)
def test_invalid_knockback_state_rejects_before_mutation(failure: str) -> None:
    battle = _empty_battle()
    target = _spawn_troop(battle, 0, Position(9.0, 10.0))
    assert apply_radial_knockback(
        target,
        battle,
        Position(8.0, 10.0),
        1.0,
        ignores_mass=True,
    )
    if failure == "target":
        target._knockback_target = Position(math.nan, 10.0)
    elif failure == "velocity":
        target._knockback_velocity_work = -1
    elif failure == "velocity_stride":
        target._knockback_velocity_work = 26
    elif failure == "velocity_cap":
        target._knockback_velocity_work = 725
    elif failure == "forced":
        target.forced_movement_active = False
    else:
        target._river_jump_active = True
        target._river_jump_origin = Position(9.0, 10.0)
        target._river_jump_target = Position(9.0, 17.25)
        target._river_jump_elapsed = 0.0
        target._river_jump_duration = 1.0
        target._special_move_active = True
    resident = ResidentRustBattle.from_battle(battle)
    state_before = resident.ground_movement_state_bytes()
    rng_before = resident.rng_state_bytes()

    assert not resident.supports_ground_movement_phase
    with pytest.raises(RuntimeError, match="ground movement preflight rejected"):
        resident.advance_ground_movement_phase()

    assert resident.ground_movement_state_bytes() == state_before
    assert resident.rng_state_bytes() == rng_before


def test_building_knockback_state_is_rejected_before_mutation() -> None:
    battle = BattleState()
    building = battle.entities[1]
    assert isinstance(building, Building)
    building._knockback_target = Position(9.0, 3.0)
    building._knockback_velocity_work = 200
    building.forced_movement_active = True
    resident = ResidentRustBattle.from_battle(battle)
    state_before = resident.ground_movement_state_bytes()
    rng_before = resident.rng_state_bytes()

    assert not resident.supports_ground_movement_phase
    with pytest.raises(RuntimeError, match="ground movement preflight rejected"):
        resident.advance_ground_movement_phase()

    assert resident.ground_movement_state_bytes() == state_before
    assert resident.rng_state_bytes() == rng_before
