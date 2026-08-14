from __future__ import annotations

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Projectile, Troop
from clasher.rust_core import (
    ResidentRustBattle,
    compare_locked_direct_combat_phase,
    compare_point_projectile_phase,
    compare_shield_state,
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


def _spawn(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    troop = battle._spawn_entity(Troop, position, player_id, stats)
    troop.deploy_delay_remaining = 0.0
    troop.placement_pending = False
    troop._spawn_hook_pending = False
    troop._spawn_hook_fired = True
    return troop


def _advance_python_combat(battle: BattleState) -> None:
    for entity in list(battle.entities.values()):
        if entity.entity_kind in {0, 1}:
            entity.update_combat_component(battle.dt, battle)


def _shield(entity: Troop) -> object:
    assert len(entity.mechanics) == 1
    return entity.mechanics[0]


def test_direct_hit_breaks_shield_without_spilling_into_hitpoints() -> None:
    battle = _empty_battle()
    attacker = _spawn(battle, "Knight", 0, Position(9.0, 12.0))
    target = _spawn(battle, "Guards", 1, Position(9.0, 13.0))
    shield = _shield(target)
    attacker.damage = shield.current_shield + 10
    attacker.attack_cooldown = 0.0
    hp_before = target.hitpoints
    assert target._shield_break_count == 0
    resident = ResidentRustBattle.from_battle(battle)
    rng_before = resident.rng_state_bytes()

    assert resident.supports_direct_troop_combat_phase
    resident.advance_direct_troop_combat_phase()
    _advance_python_combat(battle)

    compare_locked_direct_combat_phase(battle, resident)
    compare_shield_state(battle, resident)
    assert shield.current_shield == 0.0
    assert target._shield_break_count == 1
    assert target.hitpoints == hp_before
    assert resident.rng_state_bytes() == rng_before


def test_point_projectile_breaks_shield_without_spilling() -> None:
    battle = _empty_battle()
    target = _spawn(battle, "Guards", 1, Position(9.0, 12.0))
    shield = _shield(target)
    stats = battle.card_loader.get_card("Musketeer")
    assert stats is not None
    projectile = Projectile(
        id=battle.next_entity_id,
        position=Position(9.0, 11.9),
        player_id=0,
        card_stats=stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=shield.current_shield + 10,
        range=5.0,
        sight_range=1.0,
        target_position=Position(target.position.x, target.position.y),
        travel_speed=10.0,
        source_name="rust-shield-fixture",
        primary_target=target,
        tracks_target=True,
    )
    battle.entities[projectile.id] = projectile
    battle.next_entity_id += 1
    hp_before = target.hitpoints
    assert target._shield_break_count == 0
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_point_projectile_phase
    resident.advance_point_projectile_phase()
    projectile.update(battle.dt, battle)
    projectile.quantize_logic_position()

    compare_point_projectile_phase(battle, resident)
    compare_shield_state(battle, resident)
    assert shield.current_shield == 0.0
    assert target._shield_break_count == 1
    assert target.hitpoints == hp_before


def test_partial_shield_hit_does_not_increment_break_count() -> None:
    battle = _empty_battle()
    attacker = _spawn(battle, "Knight", 0, Position(9.0, 12.0))
    target = _spawn(battle, "Guards", 1, Position(9.0, 13.0))
    shield = _shield(target)
    attacker.damage = shield.current_shield / 2
    attacker.attack_cooldown = 0.0
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_direct_troop_combat_phase()
    _advance_python_combat(battle)

    compare_shield_state(battle, resident)
    assert shield.current_shield > 0.0
    assert target._shield_break_count == 0


def test_hit_after_broken_shield_damages_hitpoints_without_recounting() -> None:
    battle = _empty_battle()
    attacker = _spawn(battle, "Knight", 0, Position(9.0, 12.0))
    target = _spawn(battle, "Guards", 1, Position(9.0, 13.0))
    shield = _shield(target)
    shield.current_shield = 0.0
    target._shield_break_count = 1
    attacker.attack_cooldown = 0.0
    hp_before = target.hitpoints
    resident = ResidentRustBattle.from_battle(battle)

    resident.advance_direct_troop_combat_phase()
    _advance_python_combat(battle)

    compare_shield_state(battle, resident)
    assert target.hitpoints < hp_before
    assert target._shield_break_count == 1


def test_live_shield_prevents_lethal_projectile_target_reservation() -> None:
    battle = _empty_battle()
    attacker = _spawn(battle, "Musketeer", 0, Position(9.0, 10.0))
    guarded = _spawn(battle, "Guards", 1, Position(9.0, 14.0))
    fallback = _spawn(battle, "Knight", 1, Position(10.0, 14.0))
    guarded.hitpoints = 1
    attacker.attack_cooldown = 1.0
    projectile = Projectile(
        id=battle.next_entity_id,
        position=Position(9.0, 13.0),
        player_id=0,
        card_stats=attacker.card_stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=1000,
        range=5.0,
        sight_range=1.0,
        target_position=Position(guarded.position.x, guarded.position.y),
        travel_speed=10.0,
        source_name="rust-shield-reservation-fixture",
        primary_target=guarded,
        source_entity=attacker,
        tracks_target=True,
    )
    battle.entities[projectile.id] = projectile
    battle.next_entity_id += 1
    battle._projectile_lethal_reservations = frozenset()
    resident = ResidentRustBattle.from_battle(battle)

    assert fallback.is_alive
    resident.advance_direct_troop_combat_phase()
    _advance_python_combat(battle)

    compare_locked_direct_combat_phase(battle, resident)
    compare_shield_state(battle, resident)
    assert attacker.target_id == guarded.id
