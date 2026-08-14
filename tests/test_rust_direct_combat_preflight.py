from __future__ import annotations

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.interaction_matrix import enabled_troop_cards
from clasher.rust_core import (
    ResidentRustBattle,
    compare_locked_direct_combat_phase,
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
    player_id: int = 0,
) -> Troop:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(
        Position(8.0 + player_id, 14.0),
        player_id,
        stats,
    )
    return next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )


def _reasons(resident: ResidentRustBattle) -> set[str]:
    return {
        str(reason)
        for row in resident.direct_combat_capability()
        for reason in row["reasons"]
    }


def _locked_pair(*, cooldown: float) -> tuple[BattleState, Troop, Troop]:
    battle = _empty_battle()
    first = _spawn(battle, "Knight", 0)
    second = _spawn(battle, "Knight", 1)
    first.position = Position(9.0, 14.0)
    second.position = Position(9.0, 15.0)
    for actor, target in ((first, second), (second, first)):
        actor.deploy_delay_remaining = 0.0
        actor.placement_pending = False
        actor._spawn_hook_pending = False
        actor._spawn_hook_fired = True
        actor.target_id = target.id
        actor._last_combat_target_id = target.id
        actor.attack_cooldown = cooldown
    return battle, first, second


def _advance_python_combat_phase(battle: BattleState) -> None:
    for entity in list(battle.entities.values()):
        entity.update_combat_component(battle.dt, battle)


def test_direct_combat_preflight_accepts_plain_resolved_melee_state() -> None:
    battle = _empty_battle()
    _spawn(battle, "Knight", 0)
    _spawn(battle, "Knight", 1)
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_direct_combat_phase
    assert _reasons(resident) == set()


@pytest.mark.parametrize("cooldown", [0.0, 0.05, 0.20])
def test_locked_direct_combat_phase_matches_nonlethal_melee_pass(
    cooldown: float,
) -> None:
    battle, _, _ = _locked_pair(cooldown=cooldown)
    resident = ResidentRustBattle.from_battle(battle)
    rng_before = resident.rng_state_bytes()

    assert resident.supports_locked_direct_combat_phase
    resident.advance_locked_direct_combat_phase()
    _advance_python_combat_phase(battle)

    compare_locked_direct_combat_phase(battle, resident)
    assert resident.rng_state_bytes() == rng_before


def test_locked_direct_combat_phase_matches_stunned_target_observation() -> None:
    battle, first, second = _locked_pair(cooldown=0.0)
    first.stun_timer = 1.0
    second.stun_timer = 1.0
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_locked_direct_combat_phase
    resident.advance_locked_direct_combat_phase()
    _advance_python_combat_phase(battle)

    compare_locked_direct_combat_phase(battle, resident)


def test_locked_direct_combat_phase_rejects_lethal_ordering_before_mutation() -> None:
    battle, _, second = _locked_pair(cooldown=0.0)
    second.hitpoints = 1.0
    resident = ResidentRustBattle.from_battle(battle)
    state_before = resident.locked_direct_combat_state_bytes()
    rng_before = resident.rng_state_bytes()

    assert not resident.supports_locked_direct_combat_phase
    with pytest.raises(RuntimeError, match="preflight rejected"):
        resident.advance_locked_direct_combat_phase()

    assert resident.locked_direct_combat_state_bytes() == state_before
    assert resident.rng_state_bytes() == rng_before


def test_direct_troop_combat_acquires_target_and_publishes_movement_lock() -> None:
    battle, first, second = _locked_pair(cooldown=0.20)
    first.position = Position(9.0, 12.0)
    second.position = Position(9.0, 16.0)
    for actor in (first, second):
        actor.target_id = None
        actor._last_combat_target_id = None
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_direct_troop_combat_phase
    resident.advance_direct_troop_combat_phase()
    _advance_python_combat_phase(battle)

    compare_locked_direct_combat_phase(battle, resident)
    assert first.target_id == second.id
    assert second.target_id == first.id
    assert first._movement_target_id == second.id
    assert second._movement_target_id == first.id


def test_direct_troop_combat_handles_targetless_building_targeter() -> None:
    battle = _empty_battle()
    giant = _spawn(battle, "Giant")
    giant.deploy_delay_remaining = 0.0
    giant.placement_pending = False
    giant._spawn_hook_pending = False
    giant._spawn_hook_fired = True
    giant.attack_cooldown = 1.0
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_direct_troop_combat_phase
    resident.advance_direct_troop_combat_phase()
    _advance_python_combat_phase(battle)

    compare_locked_direct_combat_phase(battle, resident)
    assert giant.target_id is None


def test_direct_troop_combat_retargets_to_strictly_closer_enemy() -> None:
    battle = _empty_battle()
    actor = _spawn(battle, "Knight", 0)
    nearer = _spawn(battle, "Knight", 1)
    farther = _spawn(battle, "Knight", 1)
    actor.position = Position(9.0, 12.0)
    nearer.position = Position(9.0, 15.0)
    farther.position = Position(9.0, 17.0)
    for entity in (actor, nearer, farther):
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        entity._spawn_hook_pending = False
        entity._spawn_hook_fired = True
        entity.attack_cooldown = 1.0
    actor.target_id = farther.id
    actor._last_combat_target_id = farther.id
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_direct_troop_combat_phase
    resident.advance_direct_troop_combat_phase()
    _advance_python_combat_phase(battle)

    compare_locked_direct_combat_phase(battle, resident)
    assert actor.target_id == nearer.id


def test_direct_troop_combat_equal_distance_keeps_encounter_order() -> None:
    battle = _empty_battle()
    actor = _spawn(battle, "Knight", 0)
    first = _spawn(battle, "Knight", 1)
    second = _spawn(battle, "Knight", 1)
    actor.position = Position(9.0, 12.0)
    first.position = Position(8.0, 15.0)
    second.position = Position(10.0, 15.0)
    for entity in (actor, first, second):
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        entity._spawn_hook_pending = False
        entity._spawn_hook_fired = True
        entity.attack_cooldown = 1.0
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_direct_troop_combat_phase
    resident.advance_direct_troop_combat_phase()
    _advance_python_combat_phase(battle)

    compare_locked_direct_combat_phase(battle, resident)
    assert actor.target_id == first.id


@pytest.mark.parametrize(
    ("card_name", "expected_reason"),
    [
        ("BabyDragon", "projectile_payload"),
        ("Golem", "executable_mechanics"),
        ("BattleRam", "charge_payload"),
        ("Wallbreakers", "kamikaze_payload"),
    ],
)
def test_direct_combat_preflight_rejects_unsupported_resolved_payloads(
    card_name: str,
    expected_reason: str,
) -> None:
    battle = _empty_battle()
    _spawn(battle, card_name)
    resident = ResidentRustBattle.from_battle(battle)

    assert not resident.supports_direct_combat_phase
    assert expected_reason in _reasons(resident)


@pytest.mark.parametrize(
    ("field", "value", "expected_reason"),
    [
        ("_river_jump_active", True, "active_river_jump"),
        ("_special_move_active", True, "active_special_move"),
        ("_special_move_consumed_tick", True, "consumed_special_move_tick"),
        ("forced_movement_active", True, "interrupting_forced_movement"),
    ],
)
def test_direct_combat_preflight_rejects_active_special_state(
    field: str,
    value: object,
    expected_reason: str,
) -> None:
    battle = _empty_battle()
    troop = _spawn(battle, "Knight")
    setattr(troop, field, value)
    resident = ResidentRustBattle.from_battle(battle)

    assert not resident.supports_direct_combat_phase
    assert expected_reason in _reasons(resident)


@pytest.mark.parametrize("card_name", enabled_troop_cards())
def test_direct_combat_preflight_is_deterministic_for_every_enabled_troop(
    card_name: str,
) -> None:
    battle = _empty_battle()
    _spawn(battle, card_name)

    first = ResidentRustBattle.from_battle(battle)
    second = ResidentRustBattle.from_battle(battle)

    assert first.supports_direct_combat_phase == second.supports_direct_combat_phase
    assert first.direct_combat_capability() == second.direct_combat_capability()
