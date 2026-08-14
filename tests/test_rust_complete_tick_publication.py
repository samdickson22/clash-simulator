from __future__ import annotations

import copy
import json
import random
import struct
from collections import deque
from dataclasses import fields

import numpy as np
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.differential import _entity_snapshot, canonical_battle_snapshot
from clasher.entities import AreaEffect, Building, Projectile, Troop
from clasher.mechanics.shared.death_area import (
    DeathAreaEffect,
    spawn_death_area_object,
)
from clasher.mechanics.shared.knockback import apply_radial_knockback
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rust_core import ResidentRustBattle, RustBattleMode, rust_core_available
from clasher.rust_differential import (
    python_resident_semantic_snapshot,
    rust_resident_semantic_snapshot,
)
from clasher.rust_publication import (
    ResidentPublicationError,
    publish_complete_tick_state,
)
from clasher.rust_runtime import (
    ResidentCompleteTickRuntime,
    _causal_boundary_snapshot,
)

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _spawn_ready(
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


def _assert_observations_equal(control: BattleState, candidate: BattleState) -> None:
    builder = StructuredObservationBuilder(decks_path="decks.json", max_entities=128)
    for player_id in (0, 1):
        expected = builder.build(control, player_id)
        actual = builder.build(candidate, player_id)
        for field in fields(expected):
            np.testing.assert_array_equal(
                getattr(actual, field.name),
                getattr(expected, field.name),
            )


def _assert_action_masks_equal(control: BattleState, candidate: BattleState) -> None:
    action_space = DiscreteTileActionSpace()
    for player_id in (0, 1):
        for fast_path in (False, True):
            np.testing.assert_array_equal(
                action_space.legal_action_mask(
                    candidate,
                    player_id,
                    fast_path=fast_path,
                ),
                action_space.legal_action_mask(
                    control,
                    player_id,
                    fast_path=fast_path,
                ),
            )


def _mutable_identity_topology(battle: BattleState) -> dict[str, int]:
    result: dict[str, int] = {}
    owners = [
        ("battle", battle),
        ("loader", battle.card_loader),
        *((f"player[{index}]", player) for index, player in enumerate(battle.players)),
        *((f"entity[{entity_id}]", entity) for entity_id, entity in battle.entities.items()),
    ]
    mutable_types = (Position, list, dict, deque, set, np.ndarray, random.Random)
    for owner_name, owner in owners:
        for field_name, value in vars(owner).items():
            if isinstance(value, mutable_types):
                result[f"{owner_name}.{field_name}"] = id(value)
        for index, mechanic in enumerate(getattr(owner, "mechanics", ())):
            result[f"{owner_name}.mechanics[{index}]"] = id(mechanic)
            for field_name, value in vars(mechanic).items():
                if isinstance(value, mutable_types):
                    result[f"{owner_name}.mechanics[{index}].{field_name}"] = id(value)
    return result


def _advance_python_movement_phase(battle: BattleState) -> None:
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


def test_on_publication_preserves_identity_observation_mask_and_future_tick() -> None:
    candidate = BattleState(rng=random.Random(9961), fast_path=True)
    _spawn_ready(candidate, "Knight", 0, Position(8.0, 12.0))
    _spawn_ready(candidate, "Knight", 1, Position(10.0, 20.0))
    control = candidate.clone()

    entities_identity = id(candidate.entities)
    players_identity = id(candidate.players)
    rng_identity = id(candidate.rng)
    player_identities = [id(player) for player in candidate.players]
    hand_identities = [id(player.hand) for player in candidate.players]
    queue_identities = [id(player.cycle_queue) for player in candidate.players]
    entity_identities = {
        entity_id: id(entity) for entity_id, entity in candidate.entities.items()
    }
    position_identities = {
        entity_id: id(entity.position)
        for entity_id, entity in candidate.entities.items()
    }
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)

    assert runtime.advance_ticks(8) == control.step_logic_ticks(8) == 8
    assert python_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )
    assert id(candidate.entities) == entities_identity
    assert id(candidate.players) == players_identity
    assert id(candidate.rng) == rng_identity
    assert [id(player) for player in candidate.players] == player_identities
    assert [id(player.hand) for player in candidate.players] == hand_identities
    assert [id(player.cycle_queue) for player in candidate.players] == queue_identities
    assert {
        entity_id: id(entity) for entity_id, entity in candidate.entities.items()
    } == entity_identities
    assert {
        entity_id: id(entity.position)
        for entity_id, entity in candidate.entities.items()
    } == position_identities
    assert canonical_battle_snapshot(candidate) == canonical_battle_snapshot(control)
    _assert_observations_equal(control, candidate)
    _assert_action_masks_equal(control, candidate)

    assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
    assert python_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )
    _assert_observations_equal(control, candidate)
    _assert_action_masks_equal(control, candidate)
    assert canonical_battle_snapshot(candidate) == canonical_battle_snapshot(control)

    assert candidate.step_logic_ticks(1) == control.step_logic_ticks(1) == 1
    assert python_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )


def test_on_publication_preserves_sparse_deployment_completion_topology() -> None:
    candidate = BattleState(rng=random.Random(9969), fast_path=True)
    stats = candidate.card_loader.get_card("Knight")
    assert stats is not None
    before = set(candidate.entities)
    candidate._spawn_unit_at_position(Position(8, 14), 0, stats)
    troop = next(
        entity
        for entity_id, entity in candidate.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )
    troop.deploy_delay_remaining = candidate.dt
    troop.placement_pending = True
    troop._spawn_hook_pending = True
    troop.__dict__.pop("_spawn_hook_fired", None)
    control = candidate.clone()
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)

    assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
    assert _causal_boundary_snapshot(candidate) == _causal_boundary_snapshot(control)
    assert troop.__dict__["_spawn_hook_pending"] is False
    assert troop.__dict__["_spawn_hook_fired"] is True


def test_on_publication_preserves_integer_initial_position_type() -> None:
    candidate = BattleState(rng=random.Random(9970), fast_path=True)
    first = _spawn_ready(candidate, "Knight", 0, Position(8, 12))
    second = _spawn_ready(candidate, "Knight", 1, Position(10, 20))
    first.position = Position(8, 12)
    second.position = Position(10, 20)
    first.__dict__.pop("initial_position", None)
    second.__dict__.pop("initial_position", None)
    control = candidate.clone()
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)

    assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
    assert _causal_boundary_snapshot(candidate) == _causal_boundary_snapshot(control)
    assert type(first.initial_position.x) is int
    assert type(first.initial_position.y) is int


@pytest.mark.parametrize(
    ("activation_delay", "first_hit_delay"),
    [(0.03, 0.0), (0.0, 0.03)],
)
def test_on_publication_preserves_building_activation_zero_crossing(
    activation_delay: float,
    first_hit_delay: float,
) -> None:
    candidate = BattleState(rng=random.Random(9979), fast_path=True)
    king = candidate.entities[3]
    target = _spawn_ready(candidate, "Knight", 1, Position(9, 7))
    king._tower_active = True
    king.activation_delay_remaining = activation_delay
    king.activation_first_hit_delay_remaining = first_hit_delay
    control = candidate.clone()
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)

    assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
    assert _causal_boundary_snapshot(candidate) == _causal_boundary_snapshot(control)
    assert king.activation_delay_remaining == 0.0
    assert king.activation_first_hit_delay_remaining == 0.0
    assert target.is_alive


def test_lifetime_expired_building_publishes_exact_registry_tombstone() -> None:
    candidate = BattleState(rng=random.Random(9988), fast_path=True)
    stats = candidate.card_loader.get_card("Cannon")
    assert stats is not None
    building = candidate._spawn_entity(
        Building,
        Position(9.0, 12.0),
        0,
        stats,
    )
    building.deploy_delay_remaining = 0.0
    building.placement_pending = False
    building._spawn_hook_pending = False
    building._spawn_hook_fired = True
    building.hitpoints = 1.0
    building.lifetime_decay_work = 99
    building.activation_delay_remaining = 0.03
    building.activation_first_hit_delay_remaining = 0.03
    assert not building.mechanics
    control = candidate.clone()
    control_building = control.entities[building.id]
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)

    assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1

    assert canonical_battle_snapshot(candidate) == canonical_battle_snapshot(control)
    assert building.id not in candidate.entities
    assert building.id not in control.entities
    assert runtime.entity_registry[building.id] is building
    assert not building.is_alive
    assert _entity_snapshot(building) == _entity_snapshot(control_building)


def test_publication_preserves_sparse_forced_movement_finish() -> None:
    candidate = BattleState(rng=random.Random(9980), fast_path=True)
    troop = _spawn_ready(candidate, "Knight", 0, Position(9, 10))
    assert apply_radial_knockback(
        troop,
        candidate,
        Position(6, 6),
        1.0,
        ignores_mass=True,
    )
    troop._knockback_velocity_work = 0
    control = candidate.clone()
    prior = ResidentRustBattle.from_battle(candidate)
    resident = prior.fork()
    assert resident.supports_ground_movement_phase

    resident.advance_ground_movement_phase()
    _advance_python_movement_phase(control)
    registry: dict[int, object] = dict(candidate.entities)
    publish_complete_tick_state(
        candidate,
        resident,
        prior_resident=prior,
        entity_registry=registry,
    )

    assert _causal_boundary_snapshot(candidate) == _causal_boundary_snapshot(control)
    assert troop._knockback_target is None
    assert not troop.forced_movement_active


def test_publication_preserves_sparse_river_landing_and_position_identities() -> None:
    candidate = BattleState(rng=random.Random(9981), fast_path=True)
    jumper = _spawn_ready(candidate, "HogRider", 0, Position(9, 14))
    assert jumper._try_start_river_jump(
        candidate.entities[6].position,
        Position(9, candidate.arena.RIVER_Y1),
        candidate,
    )
    jumper.position.x = jumper._river_jump_target.x - 0.01
    jumper.position.y = jumper._river_jump_target.y
    control = candidate.clone()
    prior = ResidentRustBattle.from_battle(candidate)
    resident = prior.fork()
    assert resident.supports_ground_movement_phase
    position_identity = id(jumper.position)
    origin_identity = id(jumper._river_jump_origin)
    target_identity = id(jumper._river_jump_target)

    resident.advance_ground_movement_phase()
    _advance_python_movement_phase(control)
    registry: dict[int, object] = dict(candidate.entities)
    publish_complete_tick_state(
        candidate,
        resident,
        prior_resident=prior,
        entity_registry=registry,
    )

    assert _causal_boundary_snapshot(candidate) == _causal_boundary_snapshot(control)
    assert not jumper._river_jump_active
    assert not jumper._special_move_active
    assert jumper._special_move_consumed_tick
    assert id(jumper.position) == position_identity
    assert id(jumper._river_jump_origin) == origin_identity
    assert id(jumper._river_jump_target) == target_identity


def test_on_publication_updates_existing_projectile_and_references_in_place() -> None:
    candidate = BattleState(rng=random.Random(9962), fast_path=True)
    target = _spawn_ready(candidate, "Knight", 1, Position(9.0, 20.0))
    stats = candidate.card_loader.get_card("Knight")
    assert stats is not None
    projectile = Projectile(
        id=candidate.next_entity_id,
        position=Position(9.0, 10.0),
        player_id=0,
        card_stats=stats,
        hitpoints=1,
        max_hitpoints=1,
        damage=42,
        range=5.0,
        sight_range=1.0,
        target_position=Position(target.position.x, target.position.y),
        travel_speed=1.0,
        source_name="publication-fixture",
        primary_target=target,
        tracks_target=True,
    )
    candidate.entities[projectile.id] = projectile
    candidate.next_entity_id += 1
    control = candidate.clone()
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)
    projectile_identity = id(projectile)
    target_identity = id(target)

    assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
    assert python_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )
    assert id(candidate.entities[projectile.id]) == projectile_identity
    assert id(candidate.entities[target.id]) == target_identity
    assert projectile.primary_target is target

    assert candidate.step_logic_ticks(1) == control.step_logic_ticks(1) == 1
    assert python_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )


def test_on_publication_updates_supported_area_effect_in_place() -> None:
    candidate = BattleState(rng=random.Random(9965), fast_path=True)
    source = _spawn_ready(candidate, "IceGolem", 0, Position(5.0, 5.0))
    mechanic = next(
        mechanic
        for mechanic in source.mechanics
        if isinstance(mechanic, DeathAreaEffect)
    )
    area = spawn_death_area_object(
        candidate,
        player_id=0,
        position=Position(5.0, 5.0),
        card_stats=source.card_stats,
        area_data=copy.deepcopy(mechanic.area_data),
    )
    assert isinstance(area, AreaEffect)
    candidate.entities.pop(source.id)
    candidate.invalidate_target_cache()
    candidate.invalidate_alive_buildings_cache()
    candidate._refresh_fast_path_caches(trust_target_cache_dirty=True)
    control = candidate.clone()
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)
    area_identity = id(area)

    assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
    assert python_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )
    assert id(candidate.entities[area.id]) == area_identity

    assert candidate.step_logic_ticks(1) == control.step_logic_ticks(1) == 1
    assert python_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )


def test_on_publication_preserves_pending_spell_list_and_survivor_identity() -> None:
    candidate = BattleState(rng=random.Random(9966), fast_path=True)
    candidate._queue_spell_cast("Fireball", 0, Position(9.5, 16.5))
    control = candidate.clone()
    pending_list_identity = id(candidate._pending_spell_casts)
    pending_cast_identity = id(candidate._pending_spell_casts[0])
    pending_position_identity = id(candidate._pending_spell_casts[0].position)
    runtime = ResidentCompleteTickRuntime(candidate, RustBattleMode.ON)

    assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
    assert python_resident_semantic_snapshot(candidate) == (
        python_resident_semantic_snapshot(control)
    )
    assert id(candidate._pending_spell_casts) == pending_list_identity
    assert id(candidate._pending_spell_casts[0]) == pending_cast_identity
    assert id(candidate._pending_spell_casts[0].position) == pending_position_identity


def test_on_publication_publishes_projectile_birth_in_place() -> None:
    battle = BattleState(rng=random.Random(9963), fast_path=True)
    source = _spawn_ready(battle, "Musketeer", 0, Position(9.0, 12.0))
    target = _spawn_ready(battle, "Knight", 1, Position(9.0, 14.0))
    source.target_id = target.id
    source.attack_cooldown = 0.0
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    resident = runtime.resident
    assert resident is not None
    control = battle.clone()
    entity_identities = {
        entity_id: id(entity) for entity_id, entity in battle.entities.items()
    }

    assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )
    _assert_observations_equal(control, battle)
    _assert_action_masks_equal(control, battle)
    assert {
        entity_id: id(battle.entities[entity_id]) for entity_id in entity_identities
    } == entity_identities
    projectile = next(
        entity for entity in battle.entities.values() if type(entity) is Projectile
    )
    assert projectile.source_entity is source
    assert projectile.primary_target is target
    assert projectile.card_stats is source.card_stats
    assert projectile.position is not projectile.target_position
    assert projectile.position is not projectile.launch_position
    assert projectile.target_position is not projectile.launch_position

    assert battle.step_logic_ticks(1) == control.step_logic_ticks(1) == 1
    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )


def test_on_publication_publishes_cleanup_and_retains_tombstone_identity() -> None:
    battle = BattleState(rng=random.Random(9964), fast_path=True)
    source = _spawn_ready(battle, "Knight", 0, Position(9.0, 12.0))
    target = _spawn_ready(battle, "Knight", 1, Position(9.0, 13.0))
    source.target_id = target.id
    source.attack_cooldown = 0.0
    source.damage = target.hitpoints + 1
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    control = battle.clone()

    assert runtime.advance_ticks(1) == control.step_logic_ticks(1) == 1
    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )
    assert target.id not in battle.entities
    assert runtime.entity_registry[target.id] is target
    assert not target.is_alive

    assert battle.step_logic_ticks(1) == control.step_logic_ticks(1) == 1
    assert python_resident_semantic_snapshot(battle) == (
        python_resident_semantic_snapshot(control)
    )


def test_on_boundary_rejects_unpublished_causal_python_mutation() -> None:
    battle = BattleState(rng=random.Random(9967), fast_path=True)
    troop = _spawn_ready(battle, "Knight", 0, Position(9.0, 12.0))
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    resident = runtime.resident
    assert resident is not None
    resident_before = rust_resident_semantic_snapshot(resident)
    troop.damage += 1

    with pytest.raises(RuntimeError, match="external Python state mutation"):
        runtime.advance_ticks(1)

    assert battle.tick == 0
    assert runtime.resident is resident
    assert rust_resident_semantic_snapshot(resident) == resident_before
    assert runtime.poisoned_reason is None


@pytest.mark.parametrize("payload_kind", ["entity", "battle", "player"])
def test_publication_rejects_malformed_sparse_presence_before_mutation(
    payload_kind: str,
) -> None:
    battle = BattleState(rng=random.Random(9982), fast_path=True)
    _spawn_ready(battle, "Knight", 0, Position(8, 12))
    prior = ResidentRustBattle.from_battle(battle)
    resident = prior.fork()
    assert resident.advance_complete_tick()
    if payload_kind == "entity":
        rows = json.loads(resident.publication_entity_state_bytes())
        rows[0]["sparse_attribute_presence"].pop("_has_attacked_once")
        resident.publication_entity_state_bytes = lambda: json.dumps(rows).encode()
        expected_error = "malformed attribute presence"
    elif payload_kind == "battle":
        presence = json.loads(resident.publication_battle_attribute_presence_bytes())
        presence.pop("_win_conditions_dirty")
        resident.publication_battle_attribute_presence_bytes = (
            lambda: json.dumps(presence).encode()
        )
        expected_error = "presence payload is malformed"
    else:
        players = json.loads(resident.publication_player_state_bytes())
        players[0].pop("king_tower_hp")
        resident.publication_player_state_bytes = lambda: json.dumps(players).encode()
        expected_error = "player payload is malformed"
    before = canonical_battle_snapshot(battle)
    registry: dict[int, object] = dict(battle.entities)

    with pytest.raises(ResidentPublicationError, match=expected_error):
        publish_complete_tick_state(
            battle,
            resident,
            prior_resident=prior,
            entity_registry=registry,
        )

    assert canonical_battle_snapshot(battle) == before
    assert tuple(registry.items()) == tuple(battle.entities.items())


@pytest.mark.parametrize("payload_kind", ["entity", "battle"])
def test_publication_authenticates_sparse_presence_boolean_values(
    payload_kind: str,
) -> None:
    battle = BattleState(rng=random.Random(9984), fast_path=True)
    _spawn_ready(battle, "Knight", 0, Position(8, 12))
    prior = ResidentRustBattle.from_battle(battle)
    resident = prior.fork()
    assert resident.advance_complete_tick()
    if payload_kind == "entity":
        rows = json.loads(resident.publication_entity_state_bytes())
        presence = rows[0]["sparse_attribute_presence"]
        presence["_has_attacked_once"] = not presence["_has_attacked_once"]
        resident.publication_entity_state_bytes = lambda: json.dumps(rows).encode()
    else:
        presence = json.loads(resident.publication_battle_attribute_presence_bytes())
        presence["_win_conditions_dirty"] = not presence["_win_conditions_dirty"]
        resident.publication_battle_attribute_presence_bytes = (
            lambda: json.dumps(presence).encode()
        )
    before = canonical_battle_snapshot(battle)
    registry: dict[int, object] = dict(battle.entities)

    with pytest.raises(ResidentPublicationError, match="attestation mismatch"):
        publish_complete_tick_state(
            battle,
            resident,
            prior_resident=prior,
            entity_registry=registry,
        )

    assert canonical_battle_snapshot(battle) == before
    assert tuple(registry.items()) == tuple(battle.entities.items())


def test_publication_authenticates_exact_player_tower_hp_scalar_kind() -> None:
    battle = BattleState(rng=random.Random(9985), fast_path=True)
    prior = ResidentRustBattle.from_battle(battle)
    resident = prior.fork()
    assert resident.advance_complete_tick()
    players = json.loads(resident.publication_player_state_bytes())
    scalar = players[0]["king_tower_hp"]
    assert scalar["kind"] == "int"
    players[0]["king_tower_hp"] = {
        "bits": struct.pack(">d", float(scalar["value"])).hex(),
        "kind": "float",
    }
    resident.publication_player_state_bytes = lambda: json.dumps(players).encode()
    before = canonical_battle_snapshot(battle)
    registry: dict[int, object] = dict(battle.entities)

    with pytest.raises(ResidentPublicationError, match="attestation mismatch"):
        publish_complete_tick_state(
            battle,
            resident,
            prior_resident=prior,
            entity_registry=registry,
        )

    assert canonical_battle_snapshot(battle) == before
    assert tuple(registry.items()) == tuple(battle.entities.items())


def _assert_entity_payload_tamper_rejected(battle, mutate_rows) -> None:
    prior = ResidentRustBattle.from_battle(battle)
    resident = prior.fork()
    assert resident.advance_complete_tick()
    rows = json.loads(resident.publication_entity_state_bytes())
    mutate_rows(rows)
    resident.publication_entity_state_bytes = lambda: json.dumps(rows).encode()
    before = canonical_battle_snapshot(battle)
    registry: dict[int, object] = dict(battle.entities)

    with pytest.raises(ResidentPublicationError, match="attestation mismatch"):
        publish_complete_tick_state(
            battle,
            resident,
            prior_resident=prior,
            entity_registry=registry,
        )

    assert canonical_battle_snapshot(battle) == before
    assert tuple(registry.items()) == tuple(battle.entities.items())


@pytest.mark.parametrize("tamper_kind", ["scalar", "reference"])
def test_publication_authenticates_inactive_entity_rows(tamper_kind: str) -> None:
    battle = BattleState(rng=random.Random(9989), fast_path=True)
    victim = _spawn_ready(battle, "Knight", 0, Position(9.0, 12.0))
    killer = _spawn_ready(battle, "Knight", 1, Position(9.0, 13.0))
    victim.position = Position(9.0, 12.0)
    killer.position = Position(9.0, 13.0)
    killer.target_id = victim.id
    killer.attack_cooldown = 0.0
    killer.damage = victim.hitpoints + 1

    def mutate(rows) -> None:
        row = next(row for row in rows if int(row["id"]) == victim.id)
        assert not row["active"]
        if tamper_kind == "scalar":
            scalar = row["hitpoints"]
            if scalar["kind"] == "int":
                scalar["value"] += 1
            else:
                scalar["bits"] = f"{int(scalar['bits'], 16) ^ 1:016x}"
        else:
            combat = row["locked_combat_state"]
            assert combat is not None
            combat["last_combat_target_id"] = (
                killer.id
                if combat["last_combat_target_id"] is None
                else None
            )

    _assert_entity_payload_tamper_rejected(battle, mutate)


def test_publication_authenticates_active_projectile_constructor() -> None:
    battle = BattleState(rng=random.Random(9990), fast_path=True)
    source = _spawn_ready(battle, "Musketeer", 0, Position(9.0, 12.0))
    target = _spawn_ready(battle, "Knight", 1, Position(9.0, 15.0))
    source.target_id = target.id
    source.attack_cooldown = 0.0

    def mutate(rows) -> None:
        row = next(
            row
            for row in rows
            if row["active"] and row["point_projectile_constructor"] is not None
        )
        row["point_projectile_constructor"]["homing_time_ms"] += 1

    _assert_entity_payload_tamper_rejected(battle, mutate)


def test_publication_authenticates_area_birth_source() -> None:
    battle = BattleState(rng=random.Random(9991), fast_path=True)
    source = _spawn_ready(battle, "IceGolem", 0, Position(9.0, 12.0))
    killer = _spawn_ready(battle, "Knight", 1, Position(9.0, 13.0))
    source.position = Position(9.0, 12.0)
    killer.position = Position(9.0, 13.0)
    killer.target_id = source.id
    killer.attack_cooldown = 0.0
    killer.damage = source.hitpoints + 1

    def mutate(rows) -> None:
        row = next(row for row in rows if row["area_effect_state"] is not None)
        assert row["active"]
        assert row["area_effect_birth_source_id"] == source.id
        row["area_effect_birth_source_id"] = None

    _assert_entity_payload_tamper_rejected(battle, mutate)


def test_explicit_null_route_key_without_cells_is_not_native_publishable() -> None:
    battle = BattleState(rng=random.Random(9986), fast_path=True)
    troop = _spawn_ready(battle, "Knight", 0, Position(8, 12))
    troop._ground_path_cache_key = None
    troop.__dict__.pop("_native_ground_route_cells", None)
    before = canonical_battle_snapshot(battle)

    resident = ResidentRustBattle.from_battle(battle)

    assert not resident.supports_complete_tick
    assert canonical_battle_snapshot(battle) == before


def test_on_commit_failure_rolls_back_and_poisons_runtime(monkeypatch) -> None:
    from clasher import rust_publication

    battle = BattleState(rng=random.Random(9968), fast_path=True)
    _spawn_ready(battle, "Knight", 0, Position(8.0, 12.0))
    _spawn_ready(battle, "Knight", 1, Position(10.0, 20.0))
    runtime = ResidentCompleteTickRuntime(battle, RustBattleMode.ON)
    resident = runtime.resident
    assert resident is not None
    before = python_resident_semantic_snapshot(battle)
    canonical_before = canonical_battle_snapshot(battle)
    topology_before = _mutable_identity_topology(battle)
    control = battle.clone()
    require_exact = rust_publication._require_exact_projection

    def fail_live_commit(*args, stage: str, **kwargs) -> None:
        if stage == "commit":
            raise ResidentPublicationError("injected live commit failure")
        require_exact(*args, stage=stage, **kwargs)

    monkeypatch.setattr(
        rust_publication,
        "_require_exact_projection",
        fail_live_commit,
    )

    with pytest.raises(RuntimeError, match="runtime is now poisoned"):
        runtime.advance_ticks(1)

    assert python_resident_semantic_snapshot(battle) == before
    assert canonical_battle_snapshot(battle) == canonical_before
    assert _mutable_identity_topology(battle) == topology_before
    _assert_observations_equal(control, battle)
    _assert_action_masks_equal(control, battle)
    assert runtime.resident is resident
    assert rust_resident_semantic_snapshot(resident) == before
    assert runtime.poisoned_reason is not None
    with pytest.raises(RuntimeError, match="runtime is poisoned"):
        runtime.advance_ticks(1)
