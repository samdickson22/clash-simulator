from __future__ import annotations

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Projectile, Troop
from clasher.factory.dynamic_factory import building_from_values
from clasher.interaction_matrix import enabled_troop_cards
from clasher.rust_core import (
    ResidentRustBattle,
    compare_building_lifetime_phase,
    compare_idle_state,
    compare_locked_direct_combat_phase,
    compare_point_projectile_phase,
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


def _spawn_plain_building(
    battle: BattleState,
    *,
    player_id: int,
    position: Position,
) -> Building:
    stats = building_from_values(
        name="TestBuilding",
        hitpoints=1200,
        damage=80,
        range_tiles=6.0,
        sight_range_tiles=6.0,
        hit_speed_ms=1000,
        deploy_time_ms=0,
        collision_radius_tiles=1.0,
        lifetime_ms=None,
        target_type="TID_TARGETS_AIR_AND_GROUND",
    )
    building = Building(
        id=battle.next_entity_id,
        position=position,
        player_id=player_id,
        card_stats=stats,
        hitpoints=1200,
        max_hitpoints=1200,
        damage=80,
        range=6.0,
        sight_range=6.0,
    )
    battle.entities[building.id] = building
    battle.next_entity_id += 1
    building.deploy_delay_remaining = 0.0
    building.placement_pending = False
    building._spawn_hook_pending = False
    building._spawn_hook_fired = True
    building.attack_cooldown = 1.0
    return building


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


def test_direct_troop_combat_lethal_hit_skips_later_actor() -> None:
    battle, first, second = _locked_pair(cooldown=0.0)
    second.hitpoints = 1.0
    resident = ResidentRustBattle.from_battle(battle)
    first_hp_before = first.hitpoints
    rng_before = resident.rng_state_bytes()

    assert resident.supports_direct_troop_combat_phase
    resident.advance_direct_troop_combat_phase()
    _advance_python_combat_phase(battle)

    compare_locked_direct_combat_phase(battle, resident)
    assert not second.is_alive
    assert first.hitpoints == first_hp_before
    assert resident.rng_state_bytes() == rng_before


def test_direct_troop_combat_later_lethal_actor_preserves_earlier_attack() -> None:
    battle, first, second = _locked_pair(cooldown=0.0)
    first.hitpoints = 1.0
    second_hp_before = second.hitpoints
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_direct_troop_combat_phase
    resident.advance_direct_troop_combat_phase()
    _advance_python_combat_phase(battle)

    compare_locked_direct_combat_phase(battle, resident)
    assert not first.is_alive
    assert second.hitpoints == second_hp_before - first.damage


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
    ("building_y", "expected_kind"),
    [(15.0, Troop), (14.5, Building)],
)
def test_direct_combat_preserves_troop_then_building_category_precedence(
    building_y: float,
    expected_kind: type[Troop | Building],
) -> None:
    battle = _empty_battle()
    actor = _spawn(battle, "Knight", 0)
    _spawn_plain_building(
        battle,
        player_id=1,
        position=Position(9.0, building_y),
    )
    troop = _spawn(battle, "Knight", 1)
    actor.position = Position(9.0, 12.0)
    troop.position = Position(9.0, 15.0)
    for entity in (actor, troop):
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        entity._spawn_hook_pending = False
        entity._spawn_hook_fired = True
        entity.attack_cooldown = 1.0
    resident = ResidentRustBattle.from_battle(battle)
    rng_before = resident.rng_state_bytes()

    resident.advance_direct_troop_combat_phase()
    _advance_python_combat_phase(battle)

    compare_locked_direct_combat_phase(battle, resident)
    assert isinstance(battle.entities[actor.target_id], expected_kind)
    assert resident.rng_state_bytes() == rng_before


@pytest.mark.parametrize(("player_id", "expected_x"), [(0, 7.0), (1, 11.0)])
def test_direct_combat_symmetric_building_tie_is_owner_relative(
    player_id: int,
    expected_x: float,
) -> None:
    battle = _empty_battle()
    actor = _spawn(battle, "Giant", player_id)
    actor.position = Position(9.0, 12.0 if player_id == 0 else 20.0)
    actor.deploy_delay_remaining = 0.0
    actor.placement_pending = False
    actor._spawn_hook_pending = False
    actor._spawn_hook_fired = True
    actor.attack_cooldown = 1.0
    target_y = 15.0 if player_id == 0 else 17.0
    xs = (11.0, 7.0) if player_id == 0 else (7.0, 11.0)
    for x in xs:
        _spawn_plain_building(
            battle,
            player_id=1 - player_id,
            position=Position(x, target_y),
        )
    resident = ResidentRustBattle.from_battle(battle)
    rng_before = resident.rng_state_bytes()

    resident.advance_direct_troop_combat_phase()
    _advance_python_combat_phase(battle)

    compare_locked_direct_combat_phase(battle, resident)
    assert battle.entities[actor.target_id].position.x == expected_x
    assert resident.rng_state_bytes() == rng_before


@pytest.mark.parametrize(
    ("card_name", "expected_reason"),
    [
        ("MagicArcher", "projectile_payload"),
        ("Balloon", "executable_mechanics"),
        ("BattleRam", "charge_payload"),
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


def test_direct_combat_building_launch_matches_princess_tower() -> None:
    battle = BattleState()
    tower = battle.entities[1]
    target = _spawn(battle, "Knight", 1)
    target.position = Position(3.5, 11.0)
    target.deploy_delay_remaining = 0.0
    target.placement_pending = False
    target._spawn_hook_pending = False
    target._spawn_hook_fired = True
    tower.attack_cooldown = 0.0
    resident = ResidentRustBattle.from_battle(battle)
    rng_before = resident.rng_state_bytes()

    assert resident.supports_direct_troop_combat_phase
    resident.advance_direct_troop_combat_phase()
    _advance_python_combat_phase(battle)

    compare_locked_direct_combat_phase(battle, resident)
    compare_building_lifetime_phase(battle, resident)
    compare_point_projectile_phase(battle, resident)
    compare_idle_state(battle, resident)
    assert any(type(entity) is Projectile for entity in battle.entities.values())
    assert resident.rng_state_bytes() == rng_before


@pytest.mark.parametrize(
    ("activation_delay", "first_hit_delay"),
    [(0.03, 0.0), (0.0, 0.03), (0.05, 0.0), (0.0, 0.05)],
)
def test_direct_combat_king_activation_clock_matches_partial_tick(
    activation_delay: float,
    first_hit_delay: float,
) -> None:
    battle = BattleState()
    king = battle.entities[3]
    target = _spawn(battle, "Knight", 1)
    target.position = Position(9.0, 7.0)
    target.deploy_delay_remaining = 0.0
    target.placement_pending = False
    target._spawn_hook_pending = False
    target._spawn_hook_fired = True
    king._tower_active = True
    king.activation_delay_remaining = activation_delay
    king.activation_first_hit_delay_remaining = first_hit_delay
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_direct_troop_combat_phase
    resident.advance_direct_troop_combat_phase()
    _advance_python_combat_phase(battle)

    compare_locked_direct_combat_phase(battle, resident)
    compare_building_lifetime_phase(battle, resident)
    compare_point_projectile_phase(battle, resident)
    compare_idle_state(battle, resident)


@pytest.mark.parametrize("card_name", ["Knight", "Giant"])
@pytest.mark.parametrize(("x", "expected_slot"), [(3.5, "left"), (14.5, "right")])
def test_direct_combat_crown_fallback_is_data_driven(
    card_name: str,
    x: float,
    expected_slot: str,
) -> None:
    battle = BattleState()
    actor = _spawn(battle, card_name, 0)
    actor.position = Position(x, 12.0)
    actor.deploy_delay_remaining = 0.0
    actor.placement_pending = False
    actor._spawn_hook_pending = False
    actor._spawn_hook_fired = True
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_direct_troop_combat_phase
    resident.advance_direct_troop_combat_phase()
    _advance_python_combat_phase(battle)

    compare_locked_direct_combat_phase(battle, resident)
    selected = battle.entities[actor.target_id]
    assert selected._crown_tower_slot == expected_slot


def test_direct_combat_backward_route_reacquires_crown_after_target_disappears() -> None:
    battle = BattleState()
    actor = _spawn(battle, "Knight", 0)
    vanished = _spawn(battle, "Knight", 1)
    actor.position = Position(3.5, 12.0)
    for entity in (actor, vanished):
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        entity._spawn_hook_pending = False
        entity._spawn_hook_fired = True
    actor.target_id = vanished.id
    actor._last_combat_target_id = vanished.id
    actor._ground_path_backwards = True
    vanished.is_alive = False
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_direct_troop_combat_phase
    resident.advance_direct_troop_combat_phase()
    _advance_python_combat_phase(battle)

    compare_locked_direct_combat_phase(battle, resident)
    selected = battle.entities[actor.target_id]
    assert selected._crown_tower_slot == "left"


def test_direct_combat_backward_route_keeps_live_current_target_while_stunned() -> None:
    battle = BattleState()
    actor = _spawn(battle, "Knight", 0)
    current = _spawn(battle, "Knight", 1)
    actor.position = Position(3.5, 12.0)
    current.position = Position(9.0, 30.0)
    for entity in (actor, current):
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        entity._spawn_hook_pending = False
        entity._spawn_hook_fired = True
    actor.target_id = current.id
    actor._last_combat_target_id = current.id
    actor._ground_path_backwards = True
    actor.stun_timer = 1.0
    resident = ResidentRustBattle.from_battle(battle)

    assert resident.supports_direct_troop_combat_phase
    resident.advance_direct_troop_combat_phase()
    _advance_python_combat_phase(battle)

    compare_locked_direct_combat_phase(battle, resident)
    assert actor.target_id == current.id


def test_direct_combat_damage_activates_and_syncs_king_tower() -> None:
    battle = BattleState()
    king = battle.entities[3]
    actor = _spawn(battle, "Knight", 1)
    actor.position = Position(9.0, 4.0)
    actor.deploy_delay_remaining = 0.0
    actor.placement_pending = False
    actor._spawn_hook_pending = False
    actor._spawn_hook_fired = True
    actor.attack_cooldown = 0.0
    resident = ResidentRustBattle.from_battle(battle)

    assert not king._tower_active
    resident.advance_direct_troop_combat_phase()
    _advance_python_combat_phase(battle)

    compare_locked_direct_combat_phase(battle, resident)
    compare_building_lifetime_phase(battle, resident)
    compare_idle_state(battle, resident)
    assert king._tower_active
    assert king.activation_delay_remaining == king.activation_delay_seconds
