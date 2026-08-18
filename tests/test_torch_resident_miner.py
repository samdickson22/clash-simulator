from __future__ import annotations

import random
from dataclasses import fields
from typing import Any, cast

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Troop
from clasher.kinematics import tiles_to_logic_units
from clasher.torch_sim.resident_miner import (
    MinerDeploymentHandoff,
    TensorResidentMiner,
)
from clasher.torch_sim.runtime_state import RuntimeEventOpcode, TensorBattleRuntime


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> str:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return device


def _battle(seed: int = 997_100) -> tuple[BattleState, Troop, Troop]:
    battle = BattleState(fast_path=False, rng=random.Random(seed))
    stats = battle.card_loader.get_card("Miner")
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_troop(Position(9.0, 20.0), 0, stats)
    miner = next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )
    knight_stats = battle.card_loader.get_card("Knight")
    assert knight_stats is not None
    knight = battle._spawn_entity(Troop, Position(9.0, 21.0), 1, knight_stats)
    assert isinstance(knight, Troop)
    knight.deploy_delay_remaining = 0.0
    knight.placement_pending = False
    knight.stun_timer = 100.0
    knight.attack_cooldown = 100.0
    return battle, miner, knight


def _owners(
    battle: BattleState,
    device: str,
    *,
    event_capacity: int = 128,
) -> tuple[TensorBattleRuntime, TensorResidentMiner]:
    runtime = TensorBattleRuntime.from_battles(
        [battle.clone()],
        device=device,
        max_entities=16,
        event_capacity=event_capacity,
    )
    return runtime, TensorResidentMiner.from_battles(runtime, [battle])


def _slot(runtime: TensorBattleRuntime, entity_id: int) -> int:
    return runtime.battle.entity_id[0].tolist().index(entity_id)


def _handoff(
    runtime: TensorBattleRuntime,
    miner: Troop,
) -> MinerDeploymentHandoff:
    shape = runtime.battle.entity_id.shape
    mask = torch.zeros(shape, dtype=torch.bool, device=runtime.device)
    entity_id = torch.zeros(shape, dtype=torch.int64, device=runtime.device)
    destination = torch.zeros((*shape, 2), dtype=torch.int64, device=runtime.device)
    duration = torch.zeros(shape, dtype=torch.float64, device=runtime.device)
    slot = _slot(runtime, miner.id)
    target = cast(Any, miner)._underground_destination
    mask[0, slot] = True
    entity_id[0, slot] = miner.id
    destination[0, slot] = torch.tensor(
        [tiles_to_logic_units(target.x), tiles_to_logic_units(target.y)],
        dtype=torch.int64,
        device=runtime.device,
    )
    duration[0, slot] = cast(Any, miner)._underground_travel_duration
    return MinerDeploymentHandoff(mask, entity_id, destination, duration)


def test_king_origin_transport_immunity_surface_and_ordinary_hit_match_scalar(
    tensor_device: str,
) -> None:
    source, miner, knight = _battle()
    oracle = source.clone()
    scalar_miner = cast(Troop, oracle.entities[miner.id])
    scalar_knight = cast(Troop, oracle.entities[knight.id])
    runtime, owner = _owners(source, tensor_device)
    miner_slot = _slot(runtime, miner.id)
    knight_slot = _slot(runtime, knight.id)
    card = runtime.battle.entity_card[0, miner_slot]
    consumed = owner.consume_handoff_(runtime, _handoff(runtime, miner))

    assert consumed.committed.tolist() == [True]
    assert consumed.accepted.tolist() == [True]
    assert owner.catalog.underground_speed_units[card].item() == 650
    assert owner.catalog.surfaced_speed_units[card].item() == 90
    assert owner.catalog.damage[card].item() == 194
    assert owner.catalog.crown_damage[card].item() == 39
    assert owner.catalog.first_hit_ms[card].item() == 500
    assert runtime.battle.entity_x_units[0, miner_slot].item() == 9_000
    assert runtime.battle.entity_y_units[0, miner_slot].item() == 2_500
    requested = torch.ones_like(owner.underground_active)
    assert not owner.effect_eligible(requested)[0, miner_slot].item()
    hp_before = scalar_miner.hitpoints
    scalar_miner.take_damage(100)
    scalar_miner.apply_stun(1.0)
    scalar_miner.apply_slow(1.0, 0.5)
    assert scalar_miner.hitpoints == hp_before
    assert scalar_miner.stun_timer == scalar_miner.slow_timer == 0.0

    saw_reached = False
    saw_surface = False
    for _ in range(60):
        scalar_miner.update(oracle.dt, oracle)
        result = owner.step_(runtime)
        assert result.committed.tolist() == [True]
        assert runtime.battle.entity_x_units[0, miner_slot].item() == (
            tiles_to_logic_units(scalar_miner.position.x)
        )
        assert runtime.battle.entity_y_units[0, miner_slot].item() == (
            tiles_to_logic_units(scalar_miner.position.y)
        )
        assert runtime.battle.entity_deploy_delay[
            0, miner_slot
        ].item() == pytest.approx(scalar_miner.deploy_delay_remaining)
        saw_reached |= bool(result.reached_destination[0, miner_slot].item())
        saw_surface |= bool(result.surfaced[0, miner_slot].item())
        if saw_surface:
            break

    assert saw_reached and saw_surface
    assert not owner.underground_active[0, miner_slot].item()
    assert result.targetable[0, miner_slot].item()
    assert not result.effect_immune[0, miner_slot].item()
    assert owner.effect_eligible(requested)[0, miner_slot].item()
    assert runtime.battle.entity_x_units[0, miner_slot].item() == 9_000
    assert runtime.battle.entity_y_units[0, miner_slot].item() == 20_000

    hp_before = scalar_knight.hitpoints
    for _ in range(12):
        scalar_miner.update(oracle.dt, oracle)
        result = owner.step_(runtime)
        assert result.committed.tolist() == [True]
        assert (
            result.target_id[0, miner_slot].item()
            == scalar_miner.target_id
            == knight.id
        )
        assert owner.attack_cooldown[0, miner_slot].item() == pytest.approx(
            scalar_miner.attack_cooldown
        )
        assert (
            runtime.battle.entity_hp[0, knight_slot].item() == scalar_knight.hitpoints
        )
        if result.fired[0, miner_slot].item():
            break
    assert result.damage[0, knight_slot].item() == 194
    assert hp_before - scalar_knight.hitpoints == 194
    assert not runtime.battle.entity_hp_integer_kind[0, knight_slot].item()


def test_surfaced_crown_hit_uses_explicit_scaled_damage_and_events(
    tensor_device: str,
) -> None:
    source, miner, knight = _battle(997_110)
    runtime, owner = _owners(source, tensor_device)
    miner_slot = _slot(runtime, miner.id)
    owner.consume_handoff_(runtime, _handoff(runtime, miner))
    owner.underground_active[0, miner_slot] = False
    owner.tracked_entity_id[0, miner_slot] = miner.id
    runtime.battle.entity_deploy_delay[0, miner_slot] = 0.0
    runtime.battle.entity_placement_pending[0, miner_slot] = False
    runtime.battle.entity_active[0, _slot(runtime, knight.id)] = False
    enemy_tower = next(
        entity
        for entity in source.entities.values()
        if isinstance(entity, Building)
        and entity.player_id == 1
        and getattr(entity.card_stats, "name", None) == "Tower"
    )
    tower_slot = _slot(runtime, enemy_tower.id)
    runtime.battle.entity_x_units[0, miner_slot] = runtime.battle.entity_x_units[
        0, tower_slot
    ]
    runtime.battle.entity_y_units[0, miner_slot] = (
        runtime.battle.entity_y_units[0, tower_slot] - 1_000
    )
    owner.attack_cooldown[0, miner_slot] = 0.0
    owner.target_slot[0, miner_slot] = -1
    owner.public_target_id[0, miner_slot] = 0
    hp_before = runtime.battle.entity_hp[0, tower_slot].item()

    result = owner.step_(runtime)

    assert result.committed.tolist() == [True]
    assert result.fired[0, miner_slot].item()
    assert result.target_id[0, miner_slot].item() == enemy_tower.id
    assert result.damage[0, tower_slot].item() == 39
    assert hp_before - runtime.battle.entity_hp[0, tower_slot].item() == 39
    count = int(runtime.events.count.item())
    assert runtime.events.opcode[0, count - 1].item() == RuntimeEventOpcode.DAMAGE
    assert runtime.events.target_id[0, count - 1].item() == enemy_tower.id


def test_clone_fork_reset_and_handoff_event_capacity_rollback(
    tensor_device: str,
) -> None:
    source, miner, _ = _battle(997_120)
    runtime, owner = _owners(source, tensor_device, event_capacity=1)
    runtime.events.count.fill_(1)
    runtime_before = runtime.clone()
    owner_before = owner.clone()

    result = owner.consume_handoff_(runtime, _handoff(runtime, miner))

    assert result.committed.tolist() == [False]
    assert result.capacity_rejected.tolist() == [True]
    assert torch.equal(runtime.battle.entity_hp, runtime_before.battle.entity_hp)
    assert torch.equal(runtime.events.count, runtime_before.events.count)
    for descriptor in fields(owner):
        actual = getattr(owner, descriptor.name)
        expected = getattr(owner_before, descriptor.name)
        if isinstance(actual, torch.Tensor):
            assert torch.equal(actual, expected), descriptor.name

    clone = owner.clone()
    clone.tracked_entity_id[0, 0] = 99
    assert owner.tracked_entity_id[0, 0].item() == 0
    fork = clone.fork([0])
    assert fork.tracked_entity_id[0, 0].item() == 99
    clone.reset_rows_([0], owner, [0])
    assert clone.tracked_entity_id[0, 0].item() == 0


def test_surface_transition_event_capacity_failure_rolls_back_row(
    tensor_device: str,
) -> None:
    source, miner, _ = _battle(997_130)
    runtime, owner = _owners(source, tensor_device, event_capacity=2)
    owner.consume_handoff_(runtime, _handoff(runtime, miner))
    miner_slot = _slot(runtime, miner.id)
    runtime.battle.entity_deploy_delay[0, miner_slot] = 0.0
    runtime.battle.entity_x_units[0, miner_slot] = owner.destination_units[
        0, miner_slot, 0
    ].to(torch.int32)
    runtime.battle.entity_y_units[0, miner_slot] = owner.destination_units[
        0, miner_slot, 1
    ].to(torch.int32)
    runtime.events.count.fill_(runtime.events.capacity)
    runtime_before = runtime.clone()
    owner_before = owner.clone()

    result = owner.step_(runtime)

    assert result.committed.tolist() == [False]
    assert result.capacity_rejected.tolist() == [True]
    assert torch.equal(
        runtime.battle.entity_deploy_delay, runtime_before.battle.entity_deploy_delay
    )
    assert torch.equal(
        runtime.battle.entity_x_units, runtime_before.battle.entity_x_units
    )
    assert torch.equal(owner.underground_active, owner_before.underground_active)
