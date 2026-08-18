from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.kinematics import tiles_to_logic_units
from clasher.torch_sim.passive_mechanics import PassiveEventOpcode
from clasher.torch_sim.resident_skeleton_king import (
    SkeletonKingReason,
    TensorSkeletonKingState,
    activate_skeleton_king_,
    step_skeleton_king_,
)
from clasher.torch_sim.runtime_state import TensorBattleRuntime


def _battle(*rows: tuple[str, int, float]) -> BattleState:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    battle._champion_ability_owner_ids.clear()
    battle.fast_path = False
    for name, player, x in rows:
        stats = battle.card_loader.get_card(name)
        assert stats is not None
        entity = battle._spawn_entity(Troop, Position(x, 12.0), player, stats)
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        entity._spawn_hook_pending = False
        entity._spawn_hook_fired = True
    return battle


def _mechanic(entity: Troop) -> Any:
    return next(
        mechanic
        for mechanic in entity.mechanics
        if type(mechanic).__name__ == "SkeletonKingSoulCollector"
    )


def _slot(runtime: TensorBattleRuntime, entity_id: int, row: int = 0) -> int:
    matches = torch.nonzero(
        runtime.battle.entity_id[row] == entity_id, as_tuple=False
    ).flatten()
    assert matches.numel() == 1
    return int(matches.item())


def _assert_children_exact(
    oracle: BattleState,
    runtime: TensorBattleRuntime,
    first_child_id: int,
    *,
    positions: bool = True,
) -> None:
    tensor_ids = set(
        runtime.battle.entity_id[0, runtime.entity_pool.active[0]].tolist()
    )
    assert tensor_ids == set(oracle.entities)
    for entity_id, entity in oracle.entities.items():
        if entity_id < first_child_id:
            continue
        slot = _slot(runtime, entity_id)
        if positions:
            assert runtime.battle.entity_x_units[
                0, slot
            ].item() == tiles_to_logic_units(entity.position.x)
            assert runtime.battle.entity_y_units[
                0, slot
            ].item() == tiles_to_logic_units(entity.position.y)
        assert runtime.battle.entity_hp[0, slot].item() == float(entity.hitpoints)
        assert runtime.battle.entity_hp_integer_kind[0, slot].item() == (
            type(entity.hitpoints) is int
        )
        assert runtime.battle.entity_deploy_delay[0, slot].item() == pytest.approx(
            entity.deploy_delay_remaining, abs=1e-12
        )
        assert runtime.battle.entity_placement_pending[0, slot].item() == (
            entity.placement_pending
        )


def test_soul_collection_then_full_ability_spawn_and_multitick_lifecycle() -> None:
    candidate = _battle(("SkeletonKing", 0, 9.0), ("Knight", 1, 10.0))
    candidate.players[0].elixir = 10.0
    oracle = deepcopy(candidate)
    king_id, victim_id = tuple(candidate.entities)
    oracle_king = oracle.entities[king_id]
    oracle_victim = oracle.entities[victim_id]
    assert isinstance(oracle_king, Troop)
    assert isinstance(oracle_victim, Troop)
    oracle_mechanic = _mechanic(oracle_king)
    runtime = TensorBattleRuntime.from_battles(
        [candidate], max_entities=64, event_capacity=512
    )
    state = TensorSkeletonKingState.from_battles(runtime, [candidate])
    king_slot = _slot(runtime, king_id)
    victim_slot = _slot(runtime, victim_id)

    oracle_victim.take_damage(oracle_victim.hitpoints)
    runtime.battle.entity_active[0, victim_slot] = False
    oracle._step_logic_tick()
    collected = step_skeleton_king_(state, runtime)
    assert collected.collected.opcode.tolist() == [
        int(PassiveEventOpcode.SOUL_COLLECTED)
    ]
    assert state.passive.souls_collected[0, king_slot].item() == (
        oracle_mechanic.souls_collected
    )
    assert set(
        runtime.battle.entity_id[0, runtime.entity_pool.active[0]].tolist()
    ) == set(oracle.entities)

    oracle_mechanic.souls_collected = 20
    oracle_mechanic._update_ability_availability(oracle_king)
    state.passive.souls_collected[0, king_slot] = 20
    state.passive.soul_ability_cost[0, king_slot] = 1
    assert oracle.activate_champion_ability(0)
    activation = activate_skeleton_king_(state, runtime, torch.tensor([[True, False]]))
    assert activation.activated[0, king_slot]
    assert activation.spawned.sum().item() == 45
    assert runtime.battle.elixir[0, 0].item() == oracle.players[0].elixir
    assert state.passive.souls_collected[0, king_slot].item() == 0
    _assert_children_exact(oracle, runtime, first_child_id=3)

    for _ in range(20):
        oracle._step_logic_tick()
        runtime.events.clear()
        result = step_skeleton_king_(state, runtime)
        assert result.committed.item()
        _assert_children_exact(oracle, runtime, first_child_id=3, positions=False)
        assert state.ability_active[0, king_slot].item() == (
            oracle_mechanic.ability.is_active
        )


def test_death_drops_nested_child_formation_before_cleanup_exactly() -> None:
    candidate = _battle(("SkeletonKing", 0, 9.0))
    oracle = deepcopy(candidate)
    oracle_king = oracle.entities[1]
    assert isinstance(oracle_king, Troop)
    oracle_mechanic = _mechanic(oracle_king)
    oracle_mechanic.souls_collected = 8
    oracle_king.take_damage(oracle_king.hitpoints)
    oracle._cleanup_dead_entities()
    runtime = TensorBattleRuntime.from_battles(
        [candidate], max_entities=32, event_capacity=256
    )
    state = TensorSkeletonKingState.from_battles(runtime, [candidate])
    state.passive.souls_collected[0, 0] = 8
    runtime.battle.entity_active[0, 0] = False

    result = step_skeleton_king_(state, runtime)

    assert result.dropped.formation_index.tolist() == [0, 1, 2, 3]
    assert result.spawned.sum().item() == 12
    assert not runtime.entity_pool.active[0, 0]
    _assert_children_exact(oracle, runtime, first_child_id=2)


def test_duplicate_owner_death_transfers_and_resets_cooldown() -> None:
    battle = _battle(
        ("SkeletonKing", 0, 8.0),
        ("SkeletonKing", 0, 9.0),
    )
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=16, event_capacity=128
    )
    state = TensorSkeletonKingState.from_battles(runtime, [battle])
    first_slot = _slot(runtime, 1)
    second_slot = _slot(runtime, 2)
    state.last_use_time_ms[0, first_slot] = 500
    state.last_use_time_ms[0, second_slot] = 600
    runtime.battle.entity_active[0, second_slot] = False

    result = step_skeleton_king_(state, runtime)

    assert result.committed.item()
    key = int(state.ability_key[0, first_slot].item())
    assert state.recorded_owner_id[0, 0, key].item() == 1
    assert state.last_use_time_ms[0, first_slot].item() <= -(10**11)
    assert not runtime.entity_pool.active[0, second_slot]


def test_capacity_rejection_is_fail_closed() -> None:
    battle = _battle(("SkeletonKing", 0, 9.0))
    battle.players[0].elixir = 10.0
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=16, event_capacity=128
    )
    state = TensorSkeletonKingState.from_battles(runtime, [battle])
    state.passive.souls_collected[0, 0] = 20
    state.passive.soul_ability_cost[0, 0] = 1
    before_runtime = runtime.clone()
    before_state = state.clone()

    result = activate_skeleton_king_(state, runtime, torch.tensor([[True, False]]))

    assert not result.committed.item()
    assert result.reason.item() == int(SkeletonKingReason.ENTITY_CAPACITY)
    assert torch.equal(runtime.battle.elixir, before_runtime.battle.elixir)
    assert torch.equal(runtime.battle.entity_id, before_runtime.battle.entity_id)
    assert torch.equal(
        state.passive.souls_collected, before_state.passive.souls_collected
    )


def test_clone_fork_reset_and_opcode_boundary() -> None:
    battle = _battle(("SkeletonKing", 0, 9.0))
    runtime = TensorBattleRuntime.from_battles([battle], max_entities=16)
    state = TensorSkeletonKingState.from_battles(runtime, [battle])
    assert state.row_supported.item()
    clone = state.clone()
    clone.passive.souls_collected.fill_(17)
    assert state.passive.souls_collected.max().item() == 0
    fork = clone.fork([0, 0])
    assert fork.batch_size == 2
    assert fork.passive.souls_collected[:, 0].tolist() == [17, 17]
    state.reset_rows_([0], clone, [0])
    assert state.passive.souls_collected[0, 0].item() == 17
    assert clone.catalog is state.catalog


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_cuda_ability_and_multitick_lifecycle() -> None:
    battle = _battle(("SkeletonKing", 0, 9.0))
    battle.players[0].elixir = 10.0
    runtime = TensorBattleRuntime.from_battles(
        [battle], device="cuda", max_entities=64, event_capacity=256
    )
    state = TensorSkeletonKingState.from_battles(runtime, [battle])
    state.passive.souls_collected[0, 0] = 20
    state.passive.soul_ability_cost[0, 0] = 1
    activation = activate_skeleton_king_(
        state,
        runtime,
        torch.tensor([[True, False]], device="cuda"),
    )
    result = step_skeleton_king_(state, runtime)
    assert activation.spawned.device.type == "cuda"
    assert result.committed.device.type == "cuda"
