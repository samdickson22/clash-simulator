from __future__ import annotations

import random

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.rust_core import (
    ResidentRustBattle,
    compare_building_lifetime_phase,
    compare_character_object_phase,
    compare_clock_phase,
    compare_ground_movement_phase,
    compare_idle_state,
    compare_locked_direct_combat_phase,
    compare_modifier_phase,
    compare_player_phase,
    compare_point_projectile_phase,
    compare_resident_entities,
    compare_resident_rng,
    compare_shield_state,
    rust_core_available,
)
from clasher.rust_differential import rust_resident_semantic_snapshot

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _spawn(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(position, player_id, stats)
    return next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )


def _compare_complete_tick(battle: BattleState, resident: ResidentRustBattle) -> None:
    compare_clock_phase(battle, resident)
    compare_player_phase(battle, resident)
    compare_locked_direct_combat_phase(battle, resident)
    compare_ground_movement_phase(battle, resident)
    compare_building_lifetime_phase(battle, resident)
    compare_modifier_phase(battle, resident)
    compare_character_object_phase(battle, resident)
    compare_point_projectile_phase(battle, resident)
    compare_shield_state(battle, resident)
    compare_resident_entities(battle, resident)
    compare_resident_rng(battle.rng, resident)
    compare_idle_state(battle, resident)
    assert resident.next_entity_id == battle.next_entity_id
    assert resident.win_conditions_dirty is battle._win_conditions_dirty


def _advance_lockstep(battle: BattleState, resident: ResidentRustBattle) -> None:
    assert resident.advance_complete_tick()
    battle._step_logic_tick(refresh_fast_path_end=False)
    _compare_complete_tick(battle, resident)


def test_restricted_complete_tick_matches_default_battle_for_many_ticks() -> None:
    battle = BattleState(rng=random.Random(9411))
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_complete_tick
    for _ in range(12):
        _advance_lockstep(battle, resident)


@pytest.mark.parametrize("remaining", [0.15, 0.10, 0.05, 1e-10])
def test_restricted_complete_tick_matches_deployment_zero_crossing(
    remaining: float,
) -> None:
    battle = BattleState(rng=random.Random(9412))
    troop = _spawn(battle, "Knight", 0, Position(8.0, 14.0))
    troop.deploy_delay_remaining = remaining
    troop.placement_pending = remaining > 1e-9
    troop._spawn_hook_pending = remaining > 1e-9
    troop._spawn_hook_fired = remaining <= 1e-9
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_complete_tick
    for _ in range(4):
        _advance_lockstep(battle, resident)


def test_restricted_complete_tick_synchronizes_expired_status_into_combat() -> None:
    battle = BattleState(rng=random.Random(9413))
    first = _spawn(battle, "Knight", 0, Position(9.0, 14.0))
    second = _spawn(battle, "Knight", 1, Position(9.0, 16.0))
    for troop in (first, second):
        troop.deploy_delay_remaining = 0.0
        troop.placement_pending = False
        troop._spawn_hook_pending = False
        troop._spawn_hook_fired = True
    first.apply_stun(battle.dt, source_kind="complete-tick-test")
    first.apply_slow(
        battle.dt,
        0.7,
        attack_speed_multiplier=0.8,
        spawn_speed_multiplier=0.9,
    )
    first.apply_haste(battle.dt, 1.2, 1.3, 1.4)
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_complete_tick
    _advance_lockstep(battle, resident)
    assert first.stun_timer == 0.0
    _advance_lockstep(battle, resident)


def test_restricted_complete_tick_launches_and_updates_projectile_same_frame() -> None:
    battle = BattleState(rng=random.Random(9414))
    source = _spawn(battle, "Musketeer", 0, Position(9.0, 12.0))
    target = _spawn(battle, "Knight", 1, Position(9.0, 14.0))
    for troop in (source, target):
        troop.deploy_delay_remaining = 0.0
        troop.placement_pending = False
        troop._spawn_hook_pending = False
        troop._spawn_hook_fired = True
    source.attack_cooldown = 0.0
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_complete_tick
    _advance_lockstep(battle, resident)
    assert resident.next_entity_id == battle.next_entity_id == 10


def test_restricted_complete_tick_tracks_shield_break_count() -> None:
    battle = BattleState(rng=random.Random(9421))
    attacker = _spawn(battle, "Knight", 0, Position(9.0, 12.0))
    target = _spawn(battle, "Guards", 1, Position(9.0, 13.0))
    for troop in (attacker, target):
        troop.deploy_delay_remaining = 0.0
        troop.placement_pending = False
        troop._spawn_hook_pending = False
        troop._spawn_hook_fired = True
    shield = target.mechanics[0]
    attacker.damage = shield.current_shield + 1
    attacker.attack_cooldown = 0.0
    resident = ResidentRustBattle.from_battle(battle)

    _advance_lockstep(battle, resident)

    assert target._shield_break_count == 1


def test_restricted_complete_tick_refreshes_nonlethal_crown_damage() -> None:
    battle = BattleState(rng=random.Random(9416))
    attacker = _spawn(battle, "Knight", 0, Position(3.5, 24.0))
    attacker.deploy_delay_remaining = 0.0
    attacker.placement_pending = False
    attacker._spawn_hook_pending = False
    attacker._spawn_hook_fired = True
    attacker.attack_cooldown = 0.0
    resident = ResidentRustBattle.from_battle(battle)

    _advance_lockstep(battle, resident)

    target = next(
        entity
        for entity in battle.entities.values()
        if getattr(entity, "_crown_tower_slot", None) == "left"
        and entity.player_id == 1
    )
    assert target.hitpoints < target.max_hitpoints
    assert battle.players[1].left_tower_hp == target.hitpoints
    assert not battle._win_conditions_dirty
    assert not resident.win_conditions_dirty


def test_restricted_complete_tick_resolves_simultaneous_king_death_as_draw() -> None:
    battle = BattleState(rng=random.Random(9417))
    for player_id, position in (
        (0, Position(9.0, 28.0)),
        (1, Position(9.0, 4.0)),
    ):
        attacker = _spawn(battle, "Knight", player_id, position)
        attacker.deploy_delay_remaining = 0.0
        attacker.placement_pending = False
        attacker._spawn_hook_pending = False
        attacker._spawn_hook_fired = True
        attacker.attack_cooldown = 0.0
        attacker.damage = 10_000
    resident = ResidentRustBattle.from_battle(battle)

    _advance_lockstep(battle, resident)

    assert battle.game_over
    assert battle.winner is None
    assert [player.king_tower_hp for player in battle.players] == [0, 0]


def test_restricted_complete_tick_rejection_is_atomic() -> None:
    battle = BattleState(rng=random.Random(9415))
    _spawn(battle, "Golem", 0, Position(9.0, 14.0))
    resident = ResidentRustBattle.from_battle(battle)
    checkpoint = resident.checkpoint_bytes()
    entity_state = resident.entity_state_bytes()
    rng_state = resident.rng_getstate()

    assert not resident.supports_complete_tick
    with pytest.raises(RuntimeError, match="rejected combat capability"):
        resident.advance_complete_tick()

    assert resident.checkpoint_is_current
    assert resident.checkpoint_bytes() == checkpoint
    assert resident.entity_state_bytes() == entity_state
    assert resident.rng_getstate() == rng_state


def test_advance_complete_ticks_matches_repeated_python_ticks() -> None:
    battle = BattleState(rng=random.Random(9418))
    _spawn(battle, "Knight", 0, Position(8.0, 13.0))
    _spawn(battle, "Musketeer", 1, Position(10.0, 19.0))
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.advance_complete_ticks(8) == 8
    assert battle.step_logic_ticks(8) == 8
    _compare_complete_tick(battle, resident)


def test_advance_complete_ticks_stops_at_game_over() -> None:
    battle = BattleState(rng=random.Random(9419))
    for player_id, position in (
        (0, Position(9.0, 28.0)),
        (1, Position(9.0, 4.0)),
    ):
        attacker = _spawn(battle, "Knight", player_id, position)
        attacker.deploy_delay_remaining = 0.0
        attacker.placement_pending = False
        attacker._spawn_hook_pending = False
        attacker._spawn_hook_fired = True
        attacker.attack_cooldown = 0.0
        attacker.damage = 10_000
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.advance_complete_ticks(8) == 1
    assert battle.step_logic_ticks(8) == 1
    _compare_complete_tick(battle, resident)
    assert battle.game_over
    before = rust_resident_semantic_snapshot(resident)

    assert resident.advance_complete_ticks(8) == 0
    assert rust_resident_semantic_snapshot(resident) == before


@pytest.mark.parametrize("ticks", [0, -1])
def test_advance_complete_ticks_nonpositive_is_noop(ticks: int) -> None:
    resident = ResidentRustBattle.from_battle(BattleState(rng=random.Random(9420)))
    before = rust_resident_semantic_snapshot(resident)
    generation = resident.checkpoint_generation

    assert resident.advance_complete_ticks(ticks) == 0
    assert rust_resident_semantic_snapshot(resident) == before
    assert resident.checkpoint_generation == generation
    assert resident.checkpoint_is_current
