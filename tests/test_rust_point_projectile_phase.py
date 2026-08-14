from __future__ import annotations

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Projectile, Troop
from clasher.rust_core import (
    ResidentRustBattle,
    compare_point_projectile_phase,
    rust_core_available,
)

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _fixture(
    *,
    position: Position | None = None,
    target_position: Position | None = None,
    travel_speed: float = 10.0,
    damage: float = 42.0,
    tracks_target: bool = True,
    launch_delay: float = 0.0,
    homing_time_ms: int = 0,
) -> tuple[BattleState, Troop, Projectile]:
    position = Position(9.0, 10.0) if position is None else position
    target_position = (
        Position(9.0, 12.0) if target_position is None else target_position
    )
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    battle._spawn_unit_at_position(target_position, 1, stats)
    target = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
    )
    target.deploy_delay_remaining = 0.0
    target.mechanics = []
    projectile = Projectile(
        id=battle.next_entity_id,
        position=Position(position.x, position.y),
        player_id=0,
        card_stats=stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=damage,
        range=5.0,
        sight_range=1.0,
        target_position=Position(target_position.x, target_position.y),
        travel_speed=travel_speed,
        source_name="rust-parity-fixture",
        primary_target=target,
        tracks_target=tracks_target,
        launch_delay=launch_delay,
        homing_time_ms=homing_time_ms,
    )
    battle.entities[projectile.id] = projectile
    battle.next_entity_id += 1
    return battle, target, projectile


def _advance_python(battle: BattleState) -> None:
    for entity in sorted(battle.entities.values(), key=lambda value: value.id):
        if type(entity) is not Projectile:
            continue
        entity.update(battle.dt, battle)
        entity.quantize_logic_position()


@pytest.mark.parametrize("target", [Position(10.0, 12.0), Position(8.0, 8.0)])
def test_point_projectile_matches_fixed_point_motion(target: Position) -> None:
    battle, _, projectile = _fixture(target_position=target, tracks_target=False)
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_point_projectile_phase
    for _ in range(3):
        resident.advance_point_projectile_phase()
        _advance_python(battle)
        compare_point_projectile_phase(battle, resident)
        assert projectile.is_alive


@pytest.mark.parametrize("launch_delay", [0.025, 0.05, 0.075])
def test_point_projectile_matches_launch_delay_boundaries(
    launch_delay: float,
) -> None:
    battle, _, _ = _fixture(
        target_position=Position(9.0, 11.0),
        tracks_target=False,
        launch_delay=launch_delay,
    )
    resident = ResidentRustBattle.from_battle(battle)

    for _ in range(3):
        resident.advance_point_projectile_phase()
        _advance_python(battle)
        compare_point_projectile_phase(battle, resident)


def test_delayed_point_projectile_still_quantizes_its_position() -> None:
    battle, _, projectile = _fixture(
        position=Position(9.0006, 10.0),
        launch_delay=0.05,
    )
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_point_projectile_phase()
    _advance_python(battle)
    compare_point_projectile_phase(battle, resident)

    assert projectile.position.x == 9.001


def test_point_projectile_matches_permanent_and_temporary_homing() -> None:
    battle, target, projectile = _fixture(homing_time_ms=100)
    target.position.x += 0.25
    projectile.target_position = Position(9.0, 12.0)
    resident = ResidentRustBattle.from_battle(battle)

    for _ in range(3):
        resident.advance_point_projectile_phase()
        _advance_python(battle)
        compare_point_projectile_phase(battle, resident)


def test_point_projectile_matches_direct_impact_and_integer_death() -> None:
    battle, target, projectile = _fixture(
        target_position=Position(9.0, 10.25),
        damage=10_000.0,
    )
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_point_projectile_phase()
    _advance_python(battle)
    compare_point_projectile_phase(battle, resident)

    assert not target.is_alive
    assert target.hitpoints == 0
    assert not projectile.is_alive


def test_point_projectile_does_not_damage_dead_committed_target() -> None:
    battle, target, projectile = _fixture(
        target_position=Position(9.0, 10.25),
    )
    target.is_alive = False
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_point_projectile_phase()
    _advance_python(battle)
    compare_point_projectile_phase(battle, resident)

    assert not projectile.is_alive


@pytest.mark.parametrize("airborne_field", ["is_air_unit", "_river_jump_active"])
def test_point_projectile_matches_current_air_plane(
    airborne_field: str,
) -> None:
    battle, target, projectile = _fixture(
        target_position=Position(9.0, 10.25),
    )
    setattr(target, airborne_field, True)
    projectile.hits_air = False
    projectile.hits_ground = True
    hitpoints_before = target.hitpoints
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_point_projectile_phase()
    _advance_python(battle)
    compare_point_projectile_phase(battle, resident)

    assert target.hitpoints == hitpoints_before


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("splash_radius", 1.0),
        ("stun_duration", 0.5),
        ("knockback_distance", 1.0),
        ("damage_waves", 2),
        ("pierces", True),
    ],
)
def test_point_projectile_rejects_unsupported_payload_without_mutation(
    field: str,
    value: object,
) -> None:
    battle, _, projectile = _fixture()
    setattr(projectile, field, value)
    resident = ResidentRustBattle.from_battle(battle)
    entity_before = resident.entity_state_bytes()
    projectile_before = resident.point_projectile_state_bytes()
    rng_before = resident.rng_state_bytes()

    assert not resident.supports_point_projectile_phase
    with pytest.raises(RuntimeError, match="unsupported object or payload"):
        resident.advance_point_projectile_phase()

    assert resident.entity_state_bytes() == entity_before
    assert resident.point_projectile_state_bytes() == projectile_before
    assert resident.rng_state_bytes() == rng_before
