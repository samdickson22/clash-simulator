from __future__ import annotations

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Projectile, Troop
from clasher.rust_core import (
    ResidentRustBattle,
    compare_locked_direct_combat_phase,
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


def _advance_python_combat(battle: BattleState) -> None:
    for entity in list(battle.entities.values()):
        if entity.entity_kind in {0, 1}:
            entity.update_combat_component(battle.dt, battle)


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


def test_splash_projectile_snapshots_exact_troop_hitboxes_and_planes() -> None:
    battle, primary, projectile = _fixture(
        target_position=Position(9.0, 10.25),
    )
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None

    def spawn(position: Position, player_id: int) -> Troop:
        troop = battle._spawn_entity(Troop, position, player_id, stats)
        troop.deploy_delay_remaining = 0.0
        troop.mechanics = []
        return troop

    bystander = spawn(Position(9.8, 10.25), 1)
    tangent = spawn(Position(10.5, 10.25), 1)
    ally = spawn(Position(9.4, 10.25), 0)
    airborne = spawn(Position(9.5, 10.25), 1)
    airborne.is_air_unit = True
    invisible = spawn(Position(9.6, 10.25), 1)
    invisible._stealth_until = 1_000
    projectile.splash_radius = 1.0
    projectile.hits_air = False
    projectile.hits_ground = True
    hitpoints_before = {
        entity.id: entity.hitpoints
        for entity in (primary, bystander, tangent, ally, airborne, invisible)
    }
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_point_projectile_phase
    resident.advance_point_projectile_phase()
    _advance_python(battle)
    compare_point_projectile_phase(battle, resident)

    assert primary.hitpoints == hitpoints_before[primary.id] - projectile.damage
    assert bystander.hitpoints == hitpoints_before[bystander.id] - projectile.damage
    for excluded in (tangent, ally, airborne, invisible):
        assert excluded.hitpoints == hitpoints_before[excluded.id]


def test_splash_projectile_rejects_building_geometry_before_mutation() -> None:
    battle, _, projectile = _fixture()
    stats = battle.card_loader.get_card("Cannon")
    assert stats is not None
    battle._spawn_entity(Building, Position(9.0, 11.0), 1, stats)
    projectile.splash_radius = 1.0
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


@pytest.mark.parametrize(
    ("source_position", "target_position"),
    [
        (Position(9.0, 10.0), Position(9.0, 14.0)),
        (Position(8.0, 10.0), Position(10.0, 13.0)),
    ],
)
def test_direct_combat_launches_resident_point_projectile(
    source_position: Position,
    target_position: Position,
) -> None:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    source_stats = battle.card_loader.get_card("Musketeer")
    target_stats = battle.card_loader.get_card("Knight")
    assert source_stats is not None and target_stats is not None
    battle._spawn_unit_at_position(source_position, 0, source_stats)
    battle._spawn_unit_at_position(target_position, 1, target_stats)
    source, target = list(battle.entities.values())
    assert isinstance(source, Troop) and isinstance(target, Troop)
    assert not source.mechanics and not target.mechanics
    source.deploy_delay_remaining = 0.0
    target.deploy_delay_remaining = 0.0
    source.attack_cooldown = 0.0
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_direct_troop_combat_phase
    resident.advance_direct_troop_combat_phase()
    _advance_python_combat(battle)

    compare_locked_direct_combat_phase(battle, resident)
    compare_point_projectile_phase(battle, resident)
    projectile = next(
        entity
        for entity in battle.entities.values()
        if type(entity) is Projectile
    )
    assert projectile.source_entity is source
    assert projectile.primary_target is target
    assert projectile.start_collision_resolved
    assert target._pending_projectile_max_duration_ms > 0

    resident.advance_point_projectile_phase()
    _advance_python(battle)
    compare_point_projectile_phase(battle, resident)


@pytest.mark.parametrize(
    "card_name",
    [
        "Archers",
        "BabyDragon",
        "Bomber",
        "DartGoblin",
        "MegaMinion",
        "Minions",
        "Musketeer",
        "Princess",
        "SpearGoblins",
    ],
)
def test_enabled_simple_point_weapons_launch_without_card_special_cases(
    card_name: str,
) -> None:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    source_stats = battle.card_loader.get_card(card_name)
    target_stats = battle.card_loader.get_card("Knight")
    assert source_stats is not None and target_stats is not None
    source = battle._spawn_entity(
        Troop,
        Position(9.0, 12.0),
        0,
        source_stats,
    )
    target = battle._spawn_entity(
        Troop,
        Position(9.0, 14.0),
        1,
        target_stats,
    )
    assert not source.mechanics and not target.mechanics
    source.deploy_delay_remaining = 0.0
    target.deploy_delay_remaining = 0.0
    source.attack_cooldown = 0.0
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_direct_troop_combat_phase
    resident.advance_direct_troop_combat_phase()
    _advance_python_combat(battle)

    compare_locked_direct_combat_phase(battle, resident)
    compare_point_projectile_phase(battle, resident)
    assert any(type(entity) is Projectile for entity in battle.entities.values())


@pytest.mark.parametrize(
    ("field", "value"),
    [
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
