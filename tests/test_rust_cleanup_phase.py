from __future__ import annotations

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Projectile, Troop
from clasher.rust_core import (
    ResidentRustBattle,
    compare_idle_state,
    compare_locked_direct_combat_phase,
    compare_point_projectile_phase,
    compare_resident_entities,
    rust_core_available,
)

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _projectile(
    battle: BattleState,
    target: Troop,
    *,
    position: Position,
    speed: float,
    damage: float,
) -> Projectile:
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    projectile = Projectile(
        id=battle.next_entity_id,
        position=position,
        player_id=0,
        card_stats=stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=damage,
        range=5.0,
        sight_range=1.0,
        target_position=Position(target.position.x, target.position.y),
        travel_speed=speed,
        source_name="rust-cleanup-fixture",
        primary_target=target,
        tracks_target=True,
    )
    battle.entities[projectile.id] = projectile
    battle.next_entity_id += 1
    return projectile


def _advance_python_projectiles(battle: BattleState) -> None:
    for entity in sorted(battle.entities.values(), key=lambda value: value.id):
        if type(entity) is Projectile:
            entity.update(battle.dt, battle)
            entity.quantize_logic_position()


def test_cleanup_keeps_removed_homing_target_as_resident_tombstone() -> None:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    target = battle._spawn_entity(
        Troop,
        Position(9.0, 12.0),
        1,
        stats,
    )
    target.deploy_delay_remaining = 0.0
    killer = _projectile(
        battle,
        target,
        position=Position(9.0, 11.9),
        speed=10.0,
        damage=target.hitpoints,
    )
    follower = _projectile(
        battle,
        target,
        position=Position(9.0, 8.0),
        speed=1.0,
        damage=1.0,
    )
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_point_projectile_phase()
    _advance_python_projectiles(battle)
    assert not target.is_alive and not killer.is_alive and follower.is_alive

    assert resident.supports_cleanup_phase
    resident.advance_cleanup_phase()
    battle._cleanup_dead_entities()

    compare_resident_entities(battle, resident)
    compare_point_projectile_phase(battle, resident)
    compare_locked_direct_combat_phase(battle, resident)
    assert list(battle.entities) == [follower.id]

    resident.advance_point_projectile_phase()
    _advance_python_projectiles(battle)
    compare_resident_entities(battle, resident)
    compare_point_projectile_phase(battle, resident)


def test_cleanup_removes_princess_and_activates_king_exactly() -> None:
    battle = BattleState()
    princess = battle.entities[1]
    king = battle.entities[3]
    princess.hitpoints = 0
    princess.is_alive = False
    resident = ResidentRustBattle.from_battle(battle)
    rng_before = resident.rng_state_bytes()

    assert not king._tower_active
    assert resident.supports_cleanup_phase
    resident.advance_cleanup_phase()
    battle._cleanup_dead_entities()

    compare_resident_entities(battle, resident)
    compare_locked_direct_combat_phase(battle, resident)
    compare_idle_state(battle, resident)
    assert king._tower_active
    assert king.activation_delay_remaining == king.activation_delay_seconds
    assert battle.players[0].left_tower_hp == 0
    assert resident.rng_state_bytes() == rng_before


def test_cleanup_rejects_death_payload_before_mutation() -> None:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card("Balloon")
    assert stats is not None
    troop = battle._spawn_entity(
        Troop,
        Position(9.0, 12.0),
        0,
        stats,
    )
    troop.hitpoints = 0
    troop.is_alive = False
    resident = ResidentRustBattle.from_battle(battle)
    state_before = resident.entity_state_bytes()
    rng_before = resident.rng_state_bytes()

    assert not resident.supports_cleanup_phase
    with pytest.raises(RuntimeError, match="cleanup preflight rejected"):
        resident.advance_cleanup_phase()

    assert resident.entity_state_bytes() == state_before
    assert resident.rng_state_bytes() == rng_before
