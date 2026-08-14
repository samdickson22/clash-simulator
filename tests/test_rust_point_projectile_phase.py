from __future__ import annotations

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Projectile, Troop
from clasher.rust_core import (
    ResidentRustBattle,
    compare_building_lifetime_phase,
    compare_character_object_phase,
    compare_idle_state,
    compare_locked_direct_combat_phase,
    compare_modifier_phase,
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


def _advance_python_object_phase(battle: BattleState) -> None:
    ids = set(battle.entities)
    battle._run_object_phase(battle.dt, ids, ids)


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


def test_resident_object_phase_quantizes_supported_character_position() -> None:
    battle, target, projectile = _fixture(launch_delay=0.05)
    projectile.is_alive = False
    target.position.x = 9.0006
    target.deploy_delay_remaining = 0.0
    target.placement_pending = False
    target._spawn_hook_pending = False
    target._spawn_hook_fired = True
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_resident_object_phase
    resident.advance_resident_object_phase()
    _advance_python_object_phase(battle)
    compare_point_projectile_phase(battle, resident)
    compare_character_object_phase(battle, resident)

    assert target.position.x == 9.001


def test_resident_object_phase_rejects_noncharacter_base_movement_atomically() -> None:
    battle, _, projectile = _fixture(launch_delay=0.05)
    projectile.accumulate_movement_vector_units(100, 0)
    resident = ResidentRustBattle.from_battle(battle)
    checkpoint = resident.checkpoint_bytes()
    rng_state = resident.rng_getstate()

    assert not resident.supports_resident_object_phase
    with pytest.raises(RuntimeError, match="unsupported object"):
        resident.advance_resident_object_phase()

    assert resident.checkpoint_is_current
    assert resident.checkpoint_bytes() == checkpoint
    assert resident.rng_getstate() == rng_state


@pytest.mark.parametrize("projectile_first", [False, True])
def test_resident_object_phase_uses_global_id_order(
    projectile_first: bool,
) -> None:
    battle, target, projectile = _fixture(
        position=Position(9.0, 12.0),
        target_position=Position(9.0, 12.0),
        damage=10_000.0,
    )
    target.deploy_delay_remaining = 0.10
    target.placement_pending = True
    target._spawn_hook_pending = True
    target._spawn_hook_fired = False
    target.id, projectile.id = ((2, 1) if projectile_first else (1, 2))
    battle.entities = {target.id: target, projectile.id: projectile}
    battle.next_entity_id = 3
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_resident_object_phase
    resident.advance_resident_object_phase()
    _advance_python_object_phase(battle)
    compare_point_projectile_phase(battle, resident)
    compare_character_object_phase(battle, resident)

    expected_remaining = 0.10 if projectile_first else 0.05
    assert target.deploy_delay_remaining == pytest.approx(expected_remaining)


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


def test_splash_projectile_matches_square_building_geometry() -> None:
    battle, _, projectile = _fixture(
        target_position=Position(9.0, 10.25),
    )
    stats = battle.card_loader.get_card("Cannon")
    assert stats is not None
    collision_radius = float(stats.collision_radius or 0.5)
    overlapping = battle._spawn_entity(
        Building,
        Position(9.0 + collision_radius + 0.9, 10.25),
        1,
        stats,
    )
    tangent = battle._spawn_entity(
        Building,
        Position(9.0 + collision_radius + 1.0, 10.25),
        1,
        stats,
    )
    projectile.splash_radius = 1.0
    overlapping_hp = overlapping.hitpoints
    tangent_hp = tangent.hitpoints
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_point_projectile_phase
    resident.advance_point_projectile_phase()
    _advance_python(battle)
    compare_point_projectile_phase(battle, resident)

    assert overlapping.hitpoints == overlapping_hp - projectile.damage
    assert tangent.hitpoints == tangent_hp


def test_point_projectile_matches_crown_damage_and_king_activation() -> None:
    battle = BattleState()
    king = next(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Building)
        and entity._crown_tower_slot == "king"
        and entity.player_id == 1
    )
    stats = battle.card_loader.get_card("Musketeer")
    assert stats is not None
    projectile = Projectile(
        id=battle.next_entity_id,
        position=Position(king.position.x, king.position.y - 0.25),
        player_id=0,
        card_stats=stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=101,
        range=5.0,
        sight_range=1.0,
        target_position=Position(king.position.x, king.position.y),
        travel_speed=10.0,
        source_name="rust-crown-fixture",
        primary_target=king,
        tracks_target=True,
        crown_tower_damage_multiplier=0.3,
    )
    battle.entities[projectile.id] = projectile
    battle.next_entity_id += 1
    hitpoints_before = king.hitpoints
    assert king.requires_activation and not king._tower_active
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_point_projectile_phase
    resident.advance_point_projectile_phase()
    _advance_python(battle)
    compare_point_projectile_phase(battle, resident)
    compare_building_lifetime_phase(battle, resident)
    compare_idle_state(battle, resident)

    assert king.hitpoints == hitpoints_before - 31
    assert king._tower_active


@pytest.mark.parametrize("status_kind", ["stun", "slow"])
def test_point_projectile_matches_troop_status_state(status_kind: str) -> None:
    battle, target, projectile = _fixture(
        target_position=Position(9.0, 10.25),
    )
    target.attack_cooldown = 0.2
    target._last_combat_target_id = 99
    if status_kind == "stun":
        projectile.stun_duration = 0.5
    else:
        projectile.slow_duration = 1.0
        projectile.slow_multiplier = 0.7
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_point_projectile_phase
    resident.advance_point_projectile_phase()
    _advance_python(battle)
    compare_point_projectile_phase(battle, resident)
    compare_modifier_phase(battle, resident)
    compare_locked_direct_combat_phase(battle, resident)

    if status_kind == "stun":
        assert target.stun_timer == 0.5
        assert target.attack_cooldown == target.get_base_attack_interval_seconds()
        assert target._last_combat_target_id is None
    else:
        assert target.slow_timer == 1.0
        assert target.slow_multiplier == 0.7


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


def test_resident_combat_repeats_with_point_projectile_in_flight() -> None:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    source_stats = battle.card_loader.get_card("Musketeer")
    target_stats = battle.card_loader.get_card("Knight")
    assert source_stats is not None and target_stats is not None
    source = battle._spawn_entity(
        Troop,
        Position(9.0, 10.0),
        0,
        source_stats,
    )
    target = battle._spawn_entity(
        Troop,
        Position(9.0, 14.0),
        1,
        target_stats,
    )
    for entity in (source, target):
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        entity._spawn_hook_pending = False
        entity._spawn_hook_fired = True
    source.attack_cooldown = 0.0
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_direct_troop_combat_phase()
    _advance_python_combat(battle)
    resident.advance_point_projectile_phase()
    _advance_python(battle)
    assert resident.supports_direct_troop_combat_phase

    resident.advance_direct_troop_combat_phase()
    _advance_python_combat(battle)

    compare_locked_direct_combat_phase(battle, resident)
    compare_point_projectile_phase(battle, resident)


def test_resident_combat_uses_frozen_lethal_projectile_reservation() -> None:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    source_stats = battle.card_loader.get_card("Musketeer")
    target_stats = battle.card_loader.get_card("Knight")
    assert source_stats is not None and target_stats is not None
    source = battle._spawn_entity(
        Troop,
        Position(9.0, 10.0),
        0,
        source_stats,
    )
    reserved = battle._spawn_entity(
        Troop,
        Position(9.0, 14.0),
        1,
        target_stats,
    )
    fallback = battle._spawn_entity(
        Troop,
        Position(10.0, 14.0),
        1,
        target_stats,
    )
    for entity in (source, reserved, fallback):
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        entity._spawn_hook_pending = False
        entity._spawn_hook_fired = True
        entity.attack_cooldown = 1.0
    reserved.hitpoints = source.damage
    projectile = Projectile(
        id=battle.next_entity_id,
        position=Position(9.0, 13.0),
        player_id=0,
        card_stats=source_stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=source.damage,
        range=5.0,
        sight_range=1.0,
        target_position=Position(reserved.position.x, reserved.position.y),
        travel_speed=10.0,
        source_name="rust-reservation-fixture",
        primary_target=reserved,
        source_entity=source,
        tracks_target=True,
    )
    battle.entities[projectile.id] = projectile
    battle.next_entity_id += 1
    battle._projectile_lethal_reservations = frozenset({reserved.id})
    resident = ResidentRustBattle.from_battle(battle)
    rng_before = resident.rng_state_bytes()

    assert reserved._pending_projectile_max_duration_ms <= 600
    assert resident.supports_direct_troop_combat_phase
    resident.advance_direct_troop_combat_phase()
    _advance_python_combat(battle)

    compare_locked_direct_combat_phase(battle, resident)
    compare_point_projectile_phase(battle, resident)
    assert source.target_id == fallback.id
    assert resident.rng_state_bytes() == rng_before


def test_same_pass_projectile_launch_does_not_change_frozen_reservations() -> None:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    source_stats = battle.card_loader.get_card("Musketeer")
    target_stats = battle.card_loader.get_card("Knight")
    assert source_stats is not None and target_stats is not None
    sources = [
        battle._spawn_entity(
            Troop,
            Position(x, 10.0),
            0,
            source_stats,
        )
        for x in (8.5, 9.5)
    ]
    reserved = battle._spawn_entity(
        Troop,
        Position(9.0, 14.0),
        1,
        target_stats,
    )
    fallback = battle._spawn_entity(
        Troop,
        Position(11.0, 14.0),
        1,
        target_stats,
    )
    for entity in (*sources, reserved, fallback):
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        entity._spawn_hook_pending = False
        entity._spawn_hook_fired = True
        entity.attack_cooldown = 1.0
    reserved.hitpoints = sources[0].damage
    for source in sources:
        source.attack_cooldown = 0.0
    battle._projectile_lethal_reservations = frozenset()
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_direct_troop_combat_phase()
    _advance_python_combat(battle)

    compare_locked_direct_combat_phase(battle, resident)
    compare_point_projectile_phase(battle, resident)
    assert [source.target_id for source in sources] == [reserved.id, reserved.id]
    assert len(
        [entity for entity in battle.entities.values() if type(entity) is Projectile]
    ) == 2


@pytest.mark.parametrize(
    ("field", "value"),
    [
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
