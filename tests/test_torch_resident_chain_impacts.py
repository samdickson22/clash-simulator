from __future__ import annotations

import copy
from collections.abc import Iterator
from typing import Any, cast

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import ChainLightning, Troop
from clasher.torch_sim.resident_chain_impacts import (
    ChainImpactInputs,
    ChainImpactReason,
    TensorChainImpactState,
    step_chain_impacts_,
)
from clasher.torch_sim.runtime_state import (
    RuntimeEventOpcode,
    TensorBattleRuntime,
    TickPhase,
)


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> Iterator[str]:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    yield device


def _spawn(battle: BattleState, name: str, player: int, position: Position) -> Troop:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    battle._spawn_unit_at_position(
        position, player, stats, deploy_delay_override=0.0, snap_to_valid=False
    )
    entity = battle.entities[battle.next_entity_id - 1]
    assert isinstance(entity, Troop)
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    entity.speed = 0.0
    entity.attack_cooldown = 10.0
    return entity


def _mechanic(entity: Troop, name: str) -> Any:
    return cast(
        Any, next(item for item in entity.mechanics if type(item).__name__ == name)
    )


def _battle(source_name: str) -> tuple[BattleState, Troop, list[Troop]]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    source = _spawn(battle, source_name, 0, Position(9.0, 10.0))
    targets = [
        _spawn(battle, "Knight", 1, Position(9.0, 11.0)),
        _spawn(battle, "Knight", 1, Position(9.0, 13.0)),
        _spawn(battle, "Knight", 1, Position(9.0, 15.0)),
    ]
    for target in targets:
        target.damage = 0.0
    return battle, source, targets


def _slot(runtime: TensorBattleRuntime, entity_id: int, row: int = 0) -> int:
    found = torch.where(runtime.battle.entity_id[row] == entity_id)[0]
    assert found.numel() == 1
    return int(found[0].item())


def _inputs(
    runtime: TensorBattleRuntime, source: Troop, primary: Troop, *, applied: bool
) -> ChainImpactInputs:
    result = ChainImpactInputs.empty(runtime.batch_size, 1, device=runtime.device)
    result.valid[:, 0] = True
    result.source_slot[:, 0] = _slot(runtime, source.id)
    result.primary_slot[:, 0] = _slot(runtime, primary.id)
    result.primary_damage_applied[:, 0] = applied
    return result


def _chain(oracle: BattleState) -> ChainLightning | None:
    return next(
        (item for item in oracle.entities.values() if isinstance(item, ChainLightning)),
        None,
    )


def test_electro_dragon_chain_full_multi_tick_matches_scalar(
    tensor_device: str,
) -> None:
    source, attacker, targets = _battle("ElectroDragon")
    targets[0].take_damage(attacker.damage)
    runtime = TensorBattleRuntime.from_battles(
        [source], device=tensor_device, max_entities=8, event_capacity=32
    )
    state = TensorChainImpactState.from_battles(runtime, [source], max_chains=4)
    oracle = copy.deepcopy(source)
    oracle_attacker = oracle.entities[attacker.id]
    oracle_primary = oracle.entities[targets[0].id]
    assert isinstance(oracle_attacker, Troop)
    _mechanic(oracle_attacker, "ElectroDragonChainLightning").on_attack_hit(
        oracle_attacker, oracle_primary
    )
    inputs = _inputs(runtime, attacker, targets[0], applied=True)

    for tick in range(2):
        oracle_chain = _chain(oracle)
        assert oracle_chain is not None
        oracle_chain.update(oracle.dt, oracle)
        result = step_chain_impacts_(runtime, state, inputs if tick == 0 else None)
        assert result.committed.tolist() == [True]
        tensor_chain = torch.where(state.object_id[0] == oracle_chain.id)[0]
        assert tensor_chain.numel() == 1
        chain_slot = int(tensor_chain[0].item())
        assert state.position_units[0, chain_slot].tolist() == [
            round(oracle_chain.position.x * 1_000),
            round(oracle_chain.position.y * 1_000),
        ]
        assert state.active[0, chain_slot].item() is oracle_chain.is_alive
        for target in targets:
            slot = _slot(runtime, target.id)
            assert (
                runtime.battle.entity_hp[0, slot].item()
                == oracle.entities[target.id].hitpoints
            )
            assert (
                runtime.status.stun_timer[0, slot].item()
                == oracle.entities[target.id].stun_timer
            )
    assert not runtime.battle.entity_hp_integer_kind[
        0, _slot(runtime, targets[1].id)
    ].item()


def test_electro_spirit_primary_self_death_and_fixed_hops_match_scalar() -> None:
    source, spirit, targets = _battle("ElectroSpirit")
    spirit.attack_cooldown = 0.0
    runtime = TensorBattleRuntime.from_battles(
        [source], max_entities=8, event_capacity=64
    )
    state = TensorChainImpactState.from_battles(runtime, [source], max_chains=4)
    oracle = copy.deepcopy(source)
    oracle_spirit = oracle.entities[spirit.id]
    oracle_primary = oracle.entities[targets[0].id]
    assert isinstance(oracle_spirit, Troop)
    oracle_primary.take_damage(oracle_spirit.damage)
    _mechanic(oracle_spirit, "ElectroSpiritChain")._land(oracle_spirit, oracle_primary)
    oracle_spirit.take_damage(oracle_spirit.hitpoints)
    inputs = _inputs(runtime, spirit, targets[0], applied=False)

    for tick in range(6):
        oracle_chain = _chain(oracle)
        assert oracle_chain is not None
        oracle_chain.update(oracle.dt, oracle)
        result = step_chain_impacts_(runtime, state, inputs if tick == 0 else None)
        assert result.committed.tolist() == [True]
        if tick == 0:
            assert result.self_died[0, _slot(runtime, spirit.id)].item()
            assert not runtime.battle.entity_active[0, _slot(runtime, spirit.id)].item()
            assert (
                runtime.battle.entity_hp[0, _slot(runtime, targets[0].id)].item()
                == oracle_primary.hitpoints
            )
        for target in targets:
            slot = _slot(runtime, target.id)
            assert (
                runtime.battle.entity_hp[0, slot].item()
                == oracle.entities[target.id].hitpoints
            )
            assert (
                runtime.status.stun_timer[0, slot].item()
                == oracle.entities[target.id].stun_timer
            )
        tensor_slot = int(
            torch.where(state.object_id[0] == oracle_chain.id)[0][0].item()
        )
        assert state.position_units[0, tensor_slot].tolist() == [
            round(oracle_chain.position.x * 1_000),
            round(oracle_chain.position.y * 1_000),
        ]
        if not oracle_chain.is_alive:
            break


def test_stable_event_order_and_capacity_rollback_are_row_local() -> None:
    first, source_a, targets_a = _battle("ElectroDragon")
    second = copy.deepcopy(first)
    target_b = second.entities[targets_a[0].id]
    runtime = TensorBattleRuntime.from_battles(
        [first, second], max_entities=8, event_capacity=3
    )
    state = TensorChainImpactState.from_battles(runtime, [first, second], max_chains=2)
    inputs = ChainImpactInputs.empty(2, 1)
    inputs.valid[:, 0] = True
    inputs.source_slot[:, 0] = _slot(runtime, source_a.id)
    inputs.primary_slot[:, 0] = _slot(runtime, targets_a[0].id)
    inputs.primary_damage_applied[:, 0] = True
    runtime.events.append(
        phase=TickPhase.COMMANDS,
        opcode=RuntimeEventOpcode.COMMAND,
        valid=torch.tensor([[True], [False]]),
    )
    before = runtime.battle.entity_hp.clone()

    result = step_chain_impacts_(runtime, state, inputs)

    assert result.committed.tolist() == [False, True]
    assert result.reason.tolist() == [ChainImpactReason.EVENT_CAPACITY, 0]
    assert torch.equal(runtime.battle.entity_hp[0], before[0])
    assert (
        runtime.battle.entity_hp[1, _slot(runtime, target_b.id, 1)]
        == before[1, _slot(runtime, target_b.id, 1)]
    )
    count = int(runtime.events.count[1].item())
    assert runtime.events.opcode[1, :count].tolist() == [
        RuntimeEventOpcode.PROJECTILE,
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.STATUS,
    ]


def test_clone_fork_reset_and_object_capacity_are_atomic() -> None:
    battle, source, targets = _battle("ElectroDragon")
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=8, event_capacity=16
    )
    state = TensorChainImpactState.from_battles(runtime, [battle], max_chains=1)
    cloned = state.clone()
    forked = state.fork([0, 0])
    assert forked.active.shape == (2, 1)
    cloned.active[0, 0] = True
    state.reset_rows_([0], cloned, [0])
    assert state.active[0, 0].item()
    before_id = runtime.entity_pool.next_entity_id.clone()

    result = step_chain_impacts_(
        runtime, state, _inputs(runtime, source, targets[0], applied=True)
    )

    assert result.committed.tolist() == [False]
    assert result.reason.tolist() == [ChainImpactReason.OBJECT_CAPACITY]
    assert torch.equal(runtime.entity_pool.next_entity_id, before_id)


def test_lethal_serialized_chain_victim_payload_fails_closed() -> None:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    source = _spawn(battle, "ElectroDragon", 0, Position(9.0, 10.0))
    primary = _spawn(battle, "Knight", 1, Position(9.0, 11.0))
    victim = _spawn(battle, "Golem", 1, Position(9.0, 13.0))
    victim.hitpoints = 1
    primary.take_damage(source.damage)
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=8, event_capacity=16
    )
    state = TensorChainImpactState.from_battles(runtime, [battle], max_chains=2)
    before = runtime.battle.entity_hp.clone()

    result = step_chain_impacts_(
        runtime,
        state,
        _inputs(runtime, source, primary, applied=True),
    )

    assert result.committed.tolist() == [False]
    assert result.reason.tolist() == [ChainImpactReason.UNSUPPORTED_DEATH_PAYLOAD]
    assert torch.equal(runtime.battle.entity_hp, before)
    assert runtime.events.count.tolist() == [0]
