from __future__ import annotations

import random
from dataclasses import fields
from typing import cast

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.torch_sim.movement_adapter import TensorMovementAdapter
from clasher.torch_sim.resident_avoidance import (
    TensorAvoidanceState,
    step_precontact_avoidance_,
)


def _empty_battle() -> BattleState:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    return battle


def _spawn(
    battle: BattleState,
    name: str,
    player: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    troop = cast(Troop, battle._spawn_entity(Troop, position, player, stats))
    troop.deploy_delay_remaining = 0.0
    troop.placement_pending = False
    return troop


def _state(
    battle: BattleState,
    *,
    device: str = "cpu",
) -> tuple[TensorMovementAdapter, TensorAvoidanceState]:
    return _batched_state([battle], device=device)


def _batched_state(
    battles: list[BattleState],
    *,
    device: str = "cpu",
) -> tuple[TensorMovementAdapter, TensorAvoidanceState]:
    adapter = TensorMovementAdapter.from_battles(
        battles,
        device=device,
        max_entities=max(8, max(len(battle.entities) for battle in battles) + 2),
    )
    stopped = torch.zeros_like(adapter.slot_present)
    charging = torch.zeros_like(stopped)
    leap = torch.zeros_like(stopped)
    for row, battle in enumerate(battles):
        by_id = {entity.id: entity for entity in battle.entities.values()}
        for slot, entity_id in enumerate(adapter.entity_id[row].tolist()):
            if not entity_id:
                continue
            entity = by_id[entity_id]
            if isinstance(entity, Troop):
                stopped[row, slot] = entity._native_movement_component_stopped()
                charging[row, slot] = entity.is_charging
                leap[row, slot] = getattr(entity, "_mk_leap_phase", None) in {
                    "airborne",
                    "landing",
                }
    return adapter, TensorAvoidanceState.from_movement_adapter(
        adapter, stopped=stopped, charging=charging, leap_clear=leap
    )


def _oracle_step(
    battle: BattleState,
) -> dict[int, tuple[int, tuple[tuple[int, int], ...]]]:
    for entity in sorted(battle.entities.values(), key=lambda item: item.id):
        if isinstance(entity, Troop):
            entity._update_native_avoidance(battle)
    return {
        entity.id: (
            entity._native_avoidance,
            tuple(getattr(entity, "_native_ground_route_cells", ())),
        )
        for entity in battle.entities.values()
        if isinstance(entity, Troop)
    }


def _assert_matches(
    adapter: TensorMovementAdapter,
    expected: dict[int, tuple[int, tuple[tuple[int, int], ...]]],
    *,
    row: int = 0,
) -> None:
    for slot, entity_id in enumerate(adapter.entity_id[row].tolist()):
        if entity_id not in expected:
            continue
        avoidance, _ = expected[entity_id]
        assert int(adapter.avoidance[row, slot].item()) == avoidance


def test_skeletons_precontact_divergence_fixture_matches_id_order_oracle() -> None:
    battle = _empty_battle()
    lower = [
        _spawn(battle, "Skeletons", 0, Position(8.8 + index * 0.2, 10.0))
        for index in range(3)
    ]
    upper = [
        _spawn(battle, "Skeletons", 1, Position(8.8 + index * 0.2, 11.2))
        for index in range(3)
    ]
    for own, target in zip(lower, reversed(upper)):
        own._movement_target_id = target.id
        own._facing_x_units, own._facing_y_units = (0, 256)
    for own, target in zip(upper, reversed(lower)):
        own._movement_target_id = target.id
        own._facing_x_units, own._facing_y_units = (0, -256)
    expected_battle = battle.clone()
    expected = _oracle_step(expected_battle)
    adapter, state = _state(battle)
    result = step_precontact_avoidance_(state)

    assert result.supported_batch.tolist() == [True]
    _assert_matches(adapter, expected)
    assert result.contacted.sum().item() >= 4


def test_static_building_adjustment_and_route_head_pop_match_oracle() -> None:
    battle = _empty_battle()
    mover = _spawn(battle, "Knight", 0, Position(9.0, 10.0))
    target = _spawn(battle, "Knight", 1, Position(9.0, 14.0))
    stats = battle.card_loader.get_card("Cannon")
    assert stats is not None
    building = cast(
        Building,
        battle._spawn_entity(Building, Position(9.25, 10.75), 1, stats),
    )
    mover._movement_target_id = target.id
    mover._facing_x_units, mover._facing_y_units = (0, 256)
    mover._native_avoidance = 100
    mover.__dict__["_native_ground_route_cells"] = [
        (18, 21),
        (18, 22),
        (18, 23),
    ]
    target._movement_target_id = target.id
    target._facing_x_units, target._facing_y_units = (0, 256)
    expected = _oracle_step(battle.clone())
    adapter, state = _state(battle)
    mover_slot = int(adapter.slots_for_ids(0, [mover.id])[0])
    initial_count = int(adapter.route_count[0, mover_slot].item())
    initial_route = adapter.route_cells[0, mover_slot, :initial_count].clone()
    result = step_precontact_avoidance_(state)

    _assert_matches(adapter, expected)
    assert result.static_contacts[0, mover_slot] >= 1
    assert result.route_nodes_popped[0, mover_slot] == 1
    assert int(adapter.route_count[0, mover_slot].item()) == initial_count - 1
    assert torch.equal(
        adapter.route_cells[0, mover_slot, : initial_count - 1],
        initial_route[1:],
    )
    assert building.id > target.id


def test_randomized_crowded_batches_match_sequential_oracle() -> None:
    rng = random.Random(447_102)
    for case in range(24):
        battle = _empty_battle()
        troops: list[Troop] = []
        names = ("Skeletons", "Knight", "Giant", "Bats", "Prince")
        for index in range(10):
            name = rng.choice(names)
            troop = _spawn(
                battle,
                name,
                index % 2,
                Position(
                    round(8.4 + rng.random() * 1.2, 3),
                    round(9.5 + rng.random() * 2.5, 3),
                ),
            )
            troop._native_avoidance = rng.choice((-170, -50, 0, 50, 170))
            troop.is_charging = name == "Prince" and rng.random() < 0.5
            troops.append(troop)
        if case % 3 == 0:
            stats = battle.card_loader.get_card("Cannon")
            assert stats is not None
            battle._spawn_entity(
                Building,
                Position(9.0, 10.75),
                1,
                stats,
            )
        for index, troop in enumerate(troops):
            target = troops[(index + 5) % len(troops)]
            troop._movement_target_id = target.id if rng.random() > 0.15 else None
            troop._facing_x_units = rng.randint(-400, 400)
            troop._facing_y_units = rng.randint(-400, 400)
        expected = _oracle_step(battle.clone())
        adapter, state = _state(battle)
        result = step_precontact_avoidance_(state)
        assert result.supported_batch.tolist() == [True]
        _assert_matches(adapter, expected)


def test_true_batched_crowded_rows_match_independent_oracles() -> None:
    rng = random.Random(731_905)
    battles: list[BattleState] = []
    expected: list[dict[int, tuple[int, tuple[tuple[int, int], ...]]]] = []
    for row in range(4):
        battle = _empty_battle()
        troops = [
            _spawn(
                battle,
                rng.choice(("Skeletons", "Knight", "Giant", "Bats")),
                index % 2,
                Position(
                    round(8.25 + rng.random() * 1.5, 3),
                    round(9.25 + rng.random() * 3.0, 3),
                ),
            )
            for index in range(14)
        ]
        for index, troop in enumerate(troops):
            troop._movement_target_id = troops[(index + 7) % len(troops)].id
            troop._facing_x_units = rng.randint(-512, 512)
            troop._facing_y_units = rng.randint(-512, 512)
            troop._native_avoidance = rng.choice((-190, -60, 0, 60, 190))
        if row % 2 == 0:
            stats = battle.card_loader.get_card("Cannon")
            assert stats is not None
            battle._spawn_entity(Building, Position(9.0, 10.75), 1, stats)
        expected.append(_oracle_step(battle.clone()))
        battles.append(battle)

    adapter, state = _batched_state(battles)
    result = step_precontact_avoidance_(state)
    assert result.supported_batch.tolist() == [True, True, True, True]
    for row, oracle in enumerate(expected):
        _assert_matches(adapter, oracle, row=row)


def test_low_slot_reuse_and_scramble_still_visit_public_id_order() -> None:
    battle = _empty_battle()
    troops = [
        _spawn(battle, "Skeletons", index % 2, Position(9.0, 10.0 + index * 0.3))
        for index in range(7)
    ]
    for index, troop in enumerate(troops):
        target = troops[-1 - index]
        troop._movement_target_id = target.id
        troop._facing_x_units, troop._facing_y_units = (
            (0, 256) if index < 4 else (0, -256)
        )
    expected = _oracle_step(battle.clone())
    adapter, state = _state(battle)
    permutation = torch.tensor([6, 2, 5, 0, 4, 1, 3, 7, 8])
    entity_shape = adapter.entity_id.shape
    for descriptor in fields(adapter):
        value = getattr(adapter, descriptor.name)
        if (
            isinstance(value, torch.Tensor)
            and value.ndim >= 2
            and value.shape[:2] == entity_shape
        ):
            value.copy_(value[:, permutation].clone())
    # State aliases adapter planes, while stopped/charging/leap are owned by
    # the avoidance state and must follow the same physical-slot permutation.
    for name in ("stopped", "charging", "leap_clear"):
        value = getattr(state, name)
        value.copy_(value[:, permutation].clone())

    result = step_precontact_avoidance_(state)
    assert result.supported_batch.tolist() == [True]
    _assert_matches(adapter, expected)
    assert adapter.entity_id[0, :7].tolist() != sorted(
        adapter.entity_id[0, :7].tolist()
    )


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_cpu_cuda_kernel_matches_head_on_oracle(device: str) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    battle = _empty_battle()
    lower = _spawn(battle, "Knight", 0, Position(9.0, 10.0))
    upper = _spawn(battle, "Knight", 1, Position(9.0, 11.2))
    lower._movement_target_id = upper.id
    upper._movement_target_id = lower.id
    lower._facing_x_units, lower._facing_y_units = (0, 256)
    upper._facing_x_units, upper._facing_y_units = (0, -256)
    expected = _oracle_step(battle.clone())
    adapter, state = _state(battle, device=device)
    result = step_precontact_avoidance_(state)
    assert result.avoidance_after.device.type == device
    _assert_matches(adapter, expected)
