from __future__ import annotations

import copy

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Entity, TimedExplosive, Troop
from clasher.rl.deck_pool import load_deck_pool, unique_cards_from_decks
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.objects import ObjectEventOpcode, step_object_phase
from clasher.torch_sim.resident_timed_terminal_payloads import (
    TensorTimedTerminalCatalog,
    TimedTerminalReason,
    materialize_timed_children_,
    materialize_timed_parents_,
    plan_timed_terminal_events,
)
from clasher.torch_sim.runtime_state import TensorBattleRuntime

TIMED_ROOTS = ("Balloon", "BombTower", "SkeletonBarrel")


def _catalog(device: str = "cpu") -> TensorTimedTerminalCatalog:
    loader = BattleState().card_loader
    enabled = tuple(sorted(set(unique_cards_from_decks(load_deck_pool()))))
    cards = TensorCardCatalog.compile(loader, enabled, device=device)
    return TensorTimedTerminalCatalog.compile(loader, cards, list(enabled))


def _battle(name: str) -> tuple[BattleState, Entity]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    parent = battle._spawn_entity(Troop, Position(9.0, 10.0), 0, stats)
    parent.deploy_delay_remaining = 0.0
    parent.placement_pending = False
    parent._spawn_hook_pending = False
    parent._spawn_hook_fired = True
    parent._facing_x_units = 300
    parent._facing_y_units = 400
    parent.freeze_expiry_time = 2.0
    return battle, parent


def _slot(runtime: TensorBattleRuntime, entity_id: int, row: int = 0) -> int:
    match = torch.nonzero(
        runtime.battle.entity_id[row] == entity_id, as_tuple=False
    ).flatten()
    assert match.numel() == 1
    return int(match.item())


def test_timed_terminal_catalog_covers_all_three_enabled_object_roots() -> None:
    catalog = _catalog()

    assert catalog.coverage() == {
        "Balloon": True,
        "BombTower": True,
        "SkeletonBarrel": True,
    }
    spawn = catalog.terminal.spawn
    rows = {
        spawn.root_names[row]: row
        for row in spawn.death_rows().tolist()
        if spawn.depth[row].item() == 0 and spawn.timed_explosive[row].item()
    }
    assert catalog.nested_child_row[rows["Balloon"]].item() == -1
    assert catalog.nested_child_row[rows["BombTower"]].item() == -1
    skeleton_child = int(catalog.nested_child_row[rows["SkeletonBarrel"]].item())
    assert spawn.unit_names[skeleton_child] == "Skeleton"
    assert spawn.count[skeleton_child].item() == 7


@pytest.mark.parametrize("card_name", TIMED_ROOTS)
def test_parent_death_materializes_exact_timed_object_and_terminal_event(
    card_name: str,
) -> None:
    battle, parent = _battle(card_name)
    source = copy.deepcopy(battle)
    oracle = copy.deepcopy(battle)
    oracle_parent = oracle.entities[parent.id]
    oracle_parent.take_damage(oracle_parent.hitpoints)
    oracle._cleanup_dead_entities()
    oracle_objects = [
        entity
        for entity in oracle.entities.values()
        if isinstance(entity, TimedExplosive)
    ]
    assert len(oracle_objects) == 1
    oracle_object = oracle_objects[0]
    catalog = _catalog()
    runtime = TensorBattleRuntime.from_battles(
        [source], max_entities=16, event_capacity=64, catalog=catalog.terminal.cards
    )
    state = catalog.create_state(1, 8)
    catalog.prepare_runtime(runtime)
    parent_slot = _slot(runtime, parent.id)
    dead = torch.zeros_like(runtime.entity_pool.active)
    dead[0, parent_slot] = True
    runtime.battle.entity_active[0, parent_slot] = False
    runtime.battle.entity_hp[0, parent_slot] = 0.0
    facing_x = torch.zeros_like(runtime.battle.entity_x_units)
    facing_y = torch.zeros_like(runtime.battle.entity_y_units)
    facing_x[0, parent_slot] = 300
    facing_y[0, parent_slot] = 400

    materialized = materialize_timed_parents_(
        runtime,
        catalog,
        state,
        dead,
        facing_x_units=facing_x,
        facing_y_units=facing_y,
    )

    assert materialized.committed.tolist() == [True]
    assert materialized.transition.spawned.entity_ids[0, 0].item() == oracle_object.id
    object_slot = int(materialized.object_slots[0, 0].item())
    assert state.objects.object_id[0, object_slot].item() == oracle_object.id
    assert state.objects.x_units[0, object_slot].item() == round(
        oracle_object.position.x * 1_000
    )
    assert state.objects.y_units[0, object_slot].item() == round(
        oracle_object.position.y * 1_000
    )
    assert state.objects.activation_delay_ms[0, object_slot].item() == round(
        oracle_object.explosion_timer * 1_000
    )
    assert state.objects.amount[0, object_slot].item() == oracle_object.explosion_damage
    assert catalog.explosion_radius_units[
        state.operation_row[0, object_slot]
    ].item() == round(oracle_object.explosion_radius * 1_000)
    assert state.facing_x_units[0, object_slot].item() == 300
    assert state.facing_y_units[0, object_slot].item() == 400
    expected_freeze = (
        oracle_object.freeze_expiry_time
        if oracle_object.carries_freeze_to_children
        else 0
    )
    assert state.freeze_expiry_time[0, object_slot].item() == expected_freeze

    result = None
    for _ in range(round(oracle_object.explosion_timer / 0.05)):
        oracle_object.update(0.05, oracle)
        result = step_object_phase(state.objects, event_capacity=32)
    assert result is not None
    terminal = plan_timed_terminal_events(catalog, state, result)
    assert terminal.object_id.tolist() == [oracle_object.id]
    assert terminal.damage.tolist() == [oracle_object.explosion_damage]
    assert terminal.radius_units.tolist() == [
        round(oracle_object.explosion_radius * 1_000)
    ]
    assert terminal.knockback_units.tolist() == [
        round(oracle_object.knockback_distance * 1_000)
    ]
    assert result.events.opcode[0, : result.events.count[0]].tolist()[-1] == int(
        ObjectEventOpcode.DEATH
    )
    if terminal.child_count.item() == 0:
        cleaned = materialize_timed_children_(runtime, catalog, state, terminal)
        assert cleaned.committed.tolist() == [True]
        assert not (runtime.battle.entity_id == oracle_object.id).any().item()


def test_skeleton_barrel_terminal_children_match_python() -> None:
    battle, parent = _battle("SkeletonBarrel")
    source = copy.deepcopy(battle)
    oracle = copy.deepcopy(battle)
    oracle_parent = oracle.entities[parent.id]
    oracle_parent.take_damage(oracle_parent.hitpoints)
    oracle._cleanup_dead_entities()
    oracle_object = next(
        entity
        for entity in oracle.entities.values()
        if isinstance(entity, TimedExplosive)
    )
    catalog = _catalog()
    runtime = TensorBattleRuntime.from_battles(
        [source], max_entities=16, event_capacity=64, catalog=catalog.terminal.cards
    )
    state = catalog.create_state(1, 8)
    catalog.prepare_runtime(runtime)
    parent_slot = _slot(runtime, parent.id)
    dead = torch.zeros_like(runtime.entity_pool.active)
    dead[0, parent_slot] = True
    runtime.battle.entity_active[0, parent_slot] = False
    runtime.battle.entity_hp[0, parent_slot] = 0.0
    facing_x = torch.zeros_like(runtime.battle.entity_x_units)
    facing_y = torch.zeros_like(runtime.battle.entity_y_units)
    facing_x[0, parent_slot] = 300
    facing_y[0, parent_slot] = 400
    materialize_timed_parents_(
        runtime,
        catalog,
        state,
        dead,
        facing_x_units=facing_x,
        facing_y_units=facing_y,
    )

    object_result = None
    for _ in range(12):
        oracle_object.update(0.05, oracle)
        object_result = step_object_phase(state.objects, event_capacity=32)
    assert object_result is not None
    terminal = plan_timed_terminal_events(catalog, state, object_result)
    children = materialize_timed_children_(runtime, catalog, state, terminal)
    oracle._cleanup_dead_entities()
    expected = [
        entity
        for entity in oracle.entities.values()
        if not isinstance(entity, TimedExplosive)
    ]

    assert children.committed.tolist() == [True]
    spawned = children.transition.spawned.entity_ids[0][
        children.transition.spawned.valid[0]
    ].tolist()
    assert spawned == [entity.id for entity in expected]
    for child_id, oracle_child in zip(spawned, expected):
        slot = _slot(runtime, child_id)
        assert runtime.battle.entity_x_units[0, slot].item() == round(
            oracle_child.position.x * 1_000
        )
        assert runtime.battle.entity_y_units[0, slot].item() == round(
            oracle_child.position.y * 1_000
        )
        assert runtime.battle.entity_deploy_delay[0, slot].item() == (
            oracle_child.deploy_delay_remaining
        )
        assert runtime.status.freeze_expiry_time[0, slot].item() == (
            oracle_child.freeze_expiry_time
        )
        assert children.child_target_distance_discount_sq_units[0, slot].item() == (
            getattr(oracle_child, "_native_target_distance_discount_sq_units")  # noqa: B009
        )


def test_timed_parent_object_capacity_failure_is_per_row_atomic() -> None:
    left, left_parent = _battle("Balloon")
    right, right_parent = _battle("Balloon")
    catalog = _catalog()
    runtime = TensorBattleRuntime.from_battles(
        [left, right], max_entities=4, event_capacity=8, catalog=catalog.terminal.cards
    )
    state = catalog.create_state(2, 1)
    # Occupy row zero's only object slot; row one remains available.
    state.objects._load_blueprints(
        torch.tensor([0]), torch.tensor([0]), torch.tensor([1])
    )
    state.objects.object_id[0, 0] = 99
    dead = torch.zeros_like(runtime.entity_pool.active)
    dead[0, _slot(runtime, left_parent.id, 0)] = True
    dead[1, _slot(runtime, right_parent.id, 1)] = True
    ids_before = runtime.battle.entity_id[0].clone()
    object_before = state.objects.object_id[0].clone()

    result = materialize_timed_parents_(
        runtime,
        catalog,
        state,
        dead,
        facing_x_units=torch.zeros_like(runtime.battle.entity_x_units),
        facing_y_units=torch.zeros_like(runtime.battle.entity_y_units),
    )

    assert result.committed.tolist() == [False, True]
    assert result.preflight.reason.tolist() == [
        TimedTerminalReason.OBJECT_CAPACITY,
        TimedTerminalReason.NONE,
    ]
    assert torch.equal(runtime.battle.entity_id[0], ids_before)
    assert torch.equal(state.objects.object_id[0], object_before)


def test_skeleton_child_event_capacity_failure_keeps_object_entity() -> None:
    battle, parent = _battle("SkeletonBarrel")
    catalog = _catalog()
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=16, event_capacity=8, catalog=catalog.terminal.cards
    )
    state = catalog.create_state(1, 8)
    catalog.prepare_runtime(runtime)
    parent_slot = _slot(runtime, parent.id)
    dead = torch.zeros_like(runtime.entity_pool.active)
    dead[0, parent_slot] = True
    facing_x = torch.zeros_like(runtime.battle.entity_x_units)
    facing_y = torch.zeros_like(runtime.battle.entity_y_units)
    parent_result = materialize_timed_parents_(
        runtime,
        catalog,
        state,
        dead,
        facing_x_units=facing_x,
        facing_y_units=facing_y,
    )
    object_id = int(parent_result.transition.spawned.entity_ids[0, 0].item())
    object_result = None
    for _ in range(12):
        object_result = step_object_phase(state.objects, event_capacity=32)
    assert object_result is not None
    terminal = plan_timed_terminal_events(catalog, state, object_result)
    ids_before = runtime.battle.entity_id.clone()
    active_before = runtime.entity_pool.active.clone()

    children = materialize_timed_children_(runtime, catalog, state, terminal)

    assert children.committed.tolist() == [False]
    assert children.reason.tolist() == [TimedTerminalReason.EVENT_CAPACITY]
    assert torch.equal(runtime.battle.entity_id, ids_before)
    assert torch.equal(runtime.entity_pool.active, active_before)
    assert (runtime.battle.entity_id == object_id).any().item()


def test_multiple_timed_parents_preserve_parent_and_child_id_blocks() -> None:
    battle, first = _battle("SkeletonBarrel")
    stats = battle.card_loader.get_card("SkeletonBarrel")
    assert stats is not None
    second = battle._spawn_entity(Troop, Position(12.0, 10.0), 0, stats)
    second.deploy_delay_remaining = 0.0
    catalog = _catalog()
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=20, event_capacity=40, catalog=catalog.terminal.cards
    )
    state = catalog.create_state(1, 4)
    catalog.prepare_runtime(runtime)
    dead = torch.zeros_like(runtime.entity_pool.active)
    dead[0, _slot(runtime, first.id)] = True
    dead[0, _slot(runtime, second.id)] = True
    parents = materialize_timed_parents_(
        runtime,
        catalog,
        state,
        dead,
        facing_x_units=torch.zeros_like(runtime.battle.entity_x_units),
        facing_y_units=torch.ones_like(runtime.battle.entity_y_units),
    )
    parent_valid = parents.transition.spawned.valid[0]
    assert parents.transition.spawned.entity_ids[0][parent_valid].tolist() == [3, 4]
    assert parents.transition.spawn_parent_ids[0][parent_valid].tolist() == [1, 2]
    object_result = None
    for _ in range(12):
        object_result = step_object_phase(state.objects, event_capacity=32)
    assert object_result is not None
    terminal = plan_timed_terminal_events(catalog, state, object_result)

    children = materialize_timed_children_(runtime, catalog, state, terminal)

    valid = children.transition.spawned.valid[0]
    assert children.transition.spawned.entity_ids[0][valid].tolist() == list(
        range(5, 19)
    )
    assert children.transition.spawn_parent_ids[0][valid].tolist() == [3] * 7 + [4] * 7
