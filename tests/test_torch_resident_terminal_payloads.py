from __future__ import annotations

import copy
from dataclasses import fields

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Entity, Troop
from clasher.rl.deck_pool import load_deck_pool, unique_cards_from_decks
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.resident_terminal_payloads import (
    TensorTerminalPayloadCatalog,
    TerminalPayloadReason,
    materialize_terminal_payloads_,
)
from clasher.torch_sim.runtime_state import TensorBattleRuntime

DIRECT_SUPPORTED = ("BattleRam", "Golem", "LavaHound", "NightWitch", "Tombstone")
DIRECT_OBJECT_BLOCKED = ("Balloon", "BombTower", "SkeletonBarrel")


def _terminal_catalog(device: str = "cpu") -> TensorTerminalPayloadCatalog:
    loader = BattleState().card_loader
    enabled = tuple(sorted(set(unique_cards_from_decks(load_deck_pool()))))
    cards = TensorCardCatalog.compile(loader, enabled, device=device)
    return TensorTerminalPayloadCatalog.compile(loader, cards, list(enabled))


def _parent_battle(name: str) -> tuple[BattleState, Entity]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    entity_type = Building if str(stats.card_type).casefold() == "building" else Troop
    parent = battle._spawn_entity(entity_type, Position(9.0, 10.0), 0, stats)
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


def _child_entities(battle: BattleState, parent_id: int) -> list[Entity]:
    return [
        entity
        for entity_id, entity in sorted(battle.entities.items())
        if entity_id != parent_id
    ]


def test_enabled_death_spawn_terminal_coverage_is_explicit() -> None:
    catalog = _terminal_catalog()

    assert catalog.direct_coverage() == {
        "Balloon": False,
        "BattleRam": True,
        "BombTower": False,
        "Golem": True,
        "LavaHound": True,
        "NightWitch": True,
        "SkeletonBarrel": False,
        "Tombstone": True,
    }
    rows = {
        catalog.spawn.root_names[row]: row
        for row in catalog.spawn.death_rows().tolist()
        if catalog.spawn.depth[row].item() == 0
    }
    assert catalog.has_death_damage[rows["Golem"]].item()
    assert not catalog.has_death_area[list(rows.values())].any().item()
    assert all(
        catalog.spawn.timed_explosive[rows[name]].item()
        for name in DIRECT_OBJECT_BLOCKED
    )


@pytest.mark.parametrize("card_name", DIRECT_OBJECT_BLOCKED)
def test_timed_explosive_terminal_payloads_fail_closed(card_name: str) -> None:
    battle, parent = _parent_battle(card_name)
    catalog = _terminal_catalog()
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=8, event_capacity=16, catalog=catalog.cards
    )
    catalog.prepare_runtime(runtime)
    dead = torch.zeros_like(runtime.entity_pool.active)
    dead[0, _slot(runtime, parent.id)] = True
    ids_before = runtime.battle.entity_id.clone()
    active_before = runtime.entity_pool.active.clone()

    result = materialize_terminal_payloads_(
        runtime,
        catalog,
        dead,
        facing_x_units=torch.zeros_like(runtime.battle.entity_x_units),
        facing_y_units=torch.zeros_like(runtime.battle.entity_y_units),
    )

    assert result.committed.tolist() == [False]
    assert result.preflight.reason.tolist() == [
        TerminalPayloadReason.UNSUPPORTED_PAYLOAD
    ]
    assert torch.equal(runtime.battle.entity_id, ids_before)
    assert torch.equal(runtime.entity_pool.active, active_before)
    assert runtime.events.count.tolist() == [0]


@pytest.mark.parametrize("card_name", DIRECT_SUPPORTED)
def test_direct_terminal_children_match_python_geometry_identity_and_status(
    card_name: str,
) -> None:
    battle, parent = _parent_battle(card_name)
    source = copy.deepcopy(battle)
    oracle = copy.deepcopy(battle)
    oracle_parent = oracle.entities[parent.id]
    oracle_parent.take_damage(oracle_parent.hitpoints)
    oracle._cleanup_dead_entities()
    expected = _child_entities(oracle, parent.id)
    catalog = _terminal_catalog()
    runtime = TensorBattleRuntime.from_battles(
        [source], max_entities=16, event_capacity=64, catalog=catalog.cards
    )
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

    result = materialize_terminal_payloads_(
        runtime,
        catalog,
        dead,
        facing_x_units=facing_x,
        facing_y_units=facing_y,
    )

    assert result.committed.tolist() == [True]
    assert not (runtime.battle.entity_id == parent.id).any().item()
    spawned_ids = result.transition.spawned.entity_ids[0][
        result.transition.spawned.valid[0]
    ].tolist()
    assert spawned_ids == [entity.id for entity in expected]
    for ordinal, oracle_child in enumerate(expected):
        child_id = spawned_ids[ordinal]
        child_slot = _slot(runtime, child_id)
        assert runtime.battle.card_names[
            int(runtime.battle.entity_card[0, child_slot].item())
        ] == getattr(oracle_child.card_stats, "name", None)
        assert (
            runtime.battle.entity_player[0, child_slot].item() == oracle_child.player_id
        )
        assert runtime.battle.entity_x_units[0, child_slot].item() == round(
            oracle_child.position.x * 1_000
        )
        assert runtime.battle.entity_y_units[0, child_slot].item() == round(
            oracle_child.position.y * 1_000
        )
        assert runtime.battle.entity_hp[0, child_slot].item() == oracle_child.hitpoints
        assert runtime.battle.entity_deploy_delay[0, child_slot].item() == (
            oracle_child.deploy_delay_remaining
        )
        assert runtime.status.freeze_expiry_time[0, child_slot].item() == (
            oracle_child.freeze_expiry_time
        )
        assert result.child_facing_x_units[0, child_slot].item() == 300
        assert result.child_facing_y_units[0, child_slot].item() == 400
        travel_target = getattr(oracle_child, "_death_spawn_travel_target", None)
        if travel_target is None:
            assert result.child_travel_ticks[0, child_slot].item() == 0
        else:
            assert result.child_travel_target_units[0, child_slot].tolist() == [
                round(travel_target.x * 1_000),
                round(travel_target.y * 1_000),
            ]
            assert result.child_travel_ticks[0, child_slot].item() == getattr(  # noqa: B009
                oracle_child, "_death_spawn_travel_ticks_remaining"
            )


def test_mixed_capacity_failure_leaves_failed_row_untouched() -> None:
    crowded, crowded_parent = _parent_battle("Golem")
    knight = crowded.card_loader.get_card("Knight")
    assert knight is not None
    for x in (3.0, 5.0):
        filler = crowded._spawn_entity(Troop, Position(x, 4.0), 1, knight)
        filler.deploy_delay_remaining = 0.0
    sparse, sparse_parent = _parent_battle("Golem")
    catalog = _terminal_catalog()
    runtime = TensorBattleRuntime.from_battles(
        [crowded, sparse], max_entities=3, event_capacity=16, catalog=catalog.cards
    )
    catalog.prepare_runtime(runtime)
    dead = torch.zeros_like(runtime.entity_pool.active)
    dead[0, _slot(runtime, crowded_parent.id, 0)] = True
    dead[1, _slot(runtime, sparse_parent.id, 1)] = True
    ids_before = runtime.battle.entity_id[0].clone()
    active_before = runtime.entity_pool.active[0].clone()
    next_before = runtime.entity_pool.next_entity_id[0].clone()
    events_before = runtime.events.count[0].clone()

    result = materialize_terminal_payloads_(
        runtime,
        catalog,
        dead,
        facing_x_units=torch.zeros_like(runtime.battle.entity_x_units),
        facing_y_units=torch.zeros_like(runtime.battle.entity_y_units),
    )

    assert result.committed.tolist() == [False, True]
    assert result.preflight.reason.tolist() == [
        TerminalPayloadReason.ENTITY_CAPACITY,
        TerminalPayloadReason.NONE,
    ]
    assert torch.equal(runtime.battle.entity_id[0], ids_before)
    assert torch.equal(runtime.entity_pool.active[0], active_before)
    assert torch.equal(runtime.entity_pool.next_entity_id[0], next_before)
    assert torch.equal(runtime.events.count[0], events_before)
    assert result.transition.spawned.valid[1].sum().item() == 2


def test_event_capacity_failure_is_atomic() -> None:
    battle, parent = _parent_battle("Golem")
    catalog = _terminal_catalog()
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=4, event_capacity=1, catalog=catalog.cards
    )
    catalog.prepare_runtime(runtime)
    dead = torch.zeros_like(runtime.entity_pool.active)
    dead[0, _slot(runtime, parent.id)] = True
    snapshot = runtime.battle.entity_id.clone()

    result = materialize_terminal_payloads_(
        runtime,
        catalog,
        dead,
        facing_x_units=torch.zeros_like(runtime.battle.entity_x_units),
        facing_y_units=torch.zeros_like(runtime.battle.entity_y_units),
    )

    assert result.committed.tolist() == [False]
    assert result.preflight.reason.tolist() == [TerminalPayloadReason.EVENT_CAPACITY]
    assert torch.equal(runtime.battle.entity_id, snapshot)
    assert runtime.events.count.tolist() == [0]


def test_parent_id_order_controls_child_allocation_after_physical_permutation() -> None:
    battle, first = _parent_battle("Golem")
    stats = battle.card_loader.get_card("Golem")
    assert stats is not None
    second = battle._spawn_entity(Troop, Position(12.0, 10.0), 0, stats)
    second.deploy_delay_remaining = 0.0
    catalog = _terminal_catalog()
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=8, event_capacity=16, catalog=catalog.cards
    )
    catalog.prepare_runtime(runtime)
    permutation = torch.tensor([1, 0, 2, 3, 4, 5, 6, 7])
    for owner in (runtime.battle, runtime.status, runtime.phases):
        for descriptor in fields(owner):
            value = getattr(owner, descriptor.name)
            if (
                isinstance(value, torch.Tensor)
                and value.ndim >= 2
                and value.shape[:2] == runtime.entity_pool.active.shape
            ):
                value.copy_(value[:, permutation])
    runtime.entity_pool.active.copy_(runtime.entity_pool.active[:, permutation])
    dead = torch.zeros_like(runtime.entity_pool.active)
    dead[0, _slot(runtime, first.id)] = True
    dead[0, _slot(runtime, second.id)] = True

    result = materialize_terminal_payloads_(
        runtime,
        catalog,
        dead,
        facing_x_units=torch.zeros_like(runtime.battle.entity_x_units),
        facing_y_units=torch.ones_like(runtime.battle.entity_y_units),
    )

    valid = result.transition.spawned.valid[0]
    assert result.transition.spawned.entity_ids[0][valid].tolist() == [3, 4, 5, 6]
    assert result.transition.spawn_parent_ids[0][valid].tolist() == [1, 1, 2, 2]
    assert result.child_parent_id[0][valid].tolist() == [1, 1, 2, 2]
