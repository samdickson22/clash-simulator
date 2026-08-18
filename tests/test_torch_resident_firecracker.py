from __future__ import annotations

import math
import random
from dataclasses import fields
from typing import Any, cast

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Projectile, Troop
from clasher.kinematics import tiles_to_logic_units
from clasher.torch_sim.resident_firecracker import (
    TensorResidentBurstProjectiles,
)
from clasher.torch_sim.runtime_state import (
    RuntimeEventOpcode,
    TensorBattleRuntime,
    TickPhase,
)


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> str:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return device


def _spawn(
    battle: BattleState,
    name: str,
    player: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    battle._spawn_unit_at_position(
        position,
        player,
        stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    entity = battle.entities[battle.next_entity_id - 1]
    assert isinstance(entity, Troop)
    entity.stun_timer = 100.0
    entity.attack_cooldown = 100.0
    return entity


def _battle(seed: int = 992_100) -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(seed))
    battle.entities.clear()
    battle.next_entity_id = 1
    firecracker = _spawn(battle, "Firecracker", 0, Position(3.5, 10.0))
    primary = _spawn(battle, "DarkPrince", 1, Position(3.5, 15.0))
    center = _spawn(battle, "Knight", 1, Position(3.5, 19.0))
    angle = math.radians(32.0)
    outer = _spawn(
        battle,
        "Knight",
        1,
        Position(3.5 + math.sin(angle) * 4.0, 15.0 + math.cos(angle) * 4.0),
    )
    firecracker.position = Position(3.5, 10.0)
    primary.position = Position(3.5, 15.0)
    center.position = Position(3.5, 19.0)
    outer.position = Position(
        3.5 + math.sin(angle) * 4.0,
        15.0 + math.cos(angle) * 4.0,
    )
    return battle


def _owners(
    battle: BattleState,
    device: str,
    *,
    max_entities: int = 16,
    event_capacity: int = 512,
    parent_capacity: int = 4,
    child_capacity: int = 12,
) -> tuple[TensorBattleRuntime, TensorResidentBurstProjectiles]:
    runtime = TensorBattleRuntime.from_battles(
        [battle.clone()],
        device=device,
        max_entities=max_entities,
        event_capacity=event_capacity,
    )
    owner = TensorResidentBurstProjectiles.from_battles(
        runtime,
        [battle],
        parent_capacity=parent_capacity,
        child_capacity=child_capacity,
    )
    return runtime, owner


def _slot(runtime: TensorBattleRuntime, entity_id: int) -> int:
    return runtime.battle.entity_id[0].tolist().index(entity_id)


def _mechanic(entity: Troop, name: str) -> object:
    return next(item for item in entity.mechanics if type(item).__name__ == name)


def _commit_scalar(battle: BattleState) -> Projectile:
    source = battle.entities[1]
    target = battle.entities[2]
    assert isinstance(source, Troop) and isinstance(target, Troop)
    source._create_projectile(target, battle)
    cast(Any, _mechanic(source, "AttackRecoil")).on_attack_committed(source, target)
    return next(
        entity for entity in battle.entities.values() if isinstance(entity, Projectile)
    )


def _scalar_step(battle: BattleState) -> None:
    source = battle.entities[1]
    assert isinstance(source, Troop)
    source.update_movement_component(battle.dt, battle)
    projectiles = tuple(
        entity
        for entity in battle.entities.values()
        if isinstance(entity, Projectile) and entity.is_alive
    )
    for projectile in projectiles:
        projectile.update(battle.dt, battle)
    battle._cleanup_dead_entities()


def _commit_tensor(
    runtime: TensorBattleRuntime,
    owner: TensorResidentBurstProjectiles,
) -> None:
    result = owner.commit_attacks_(
        runtime,
        source_slots=torch.tensor(
            [[_slot(runtime, 1)]], dtype=torch.int64, device=runtime.device
        ),
        target_slots=torch.tensor(
            [[_slot(runtime, 2)]], dtype=torch.int64, device=runtime.device
        ),
        valid=torch.tensor([[True]], dtype=torch.bool, device=runtime.device),
    )
    assert result.committed.tolist() == [True]
    assert result.accepted.tolist() == [True]
    assert result.recoil_started.tolist() == [[True]]


def test_serialized_commit_recoil_carrier_and_child_fan_match_scalar(
    tensor_device: str,
) -> None:
    source = _battle()
    oracle = source.clone()
    scalar_parent = _commit_scalar(oracle)
    runtime, owner = _owners(source, tensor_device)
    _commit_tensor(runtime, owner)
    card = runtime.battle.card_to_id["Firecracker"]

    assert owner.catalog.supported[card].item()
    assert owner.catalog.recoil_distance_units[card].item() == 1_000
    assert owner.catalog.parent_speed_units[card].item() == 500
    assert owner.catalog.child_count[card].item() == 5
    assert owner.catalog.child_damage[card].item() == 64
    assert not owner.catalog.child_damage_integer_kind[card].item()
    assert owner.catalog.child_speed_units[card].item() == 550
    assert owner.parent_entity_id[0, 0].item() == scalar_parent.id == 5
    assert owner.parent_position_units[0, 0].tolist() == [3_500, 10_200]
    assert owner.parent_target_units[0, 0].tolist() == [3_500, 15_000]
    assert owner.recoil_target_units[0, _slot(runtime, 1)].tolist() == [3_500, 9_000]
    assert owner.recoil_velocity_work[0, _slot(runtime, 1)].item() == 225
    parent_runtime_slot = _slot(runtime, 5)
    assert runtime.phases.target_slot[0, parent_runtime_slot].item() == _slot(
        runtime, 2
    )

    impact = None
    for tick in range(10):
        _scalar_step(oracle)
        impact = owner.step_(runtime)
        assert impact.committed.tolist() == [True]
        assert impact.parent_impacted.tolist() == [tick == 9]
        tensor_source_slot = _slot(runtime, 1)
        assert runtime.battle.entity_x_units[0, tensor_source_slot].item() == 3_500
        assert runtime.battle.entity_y_units[0, tensor_source_slot].item() == (
            tiles_to_logic_units(oracle.entities[1].position.y)
        )
    assert impact is not None
    assert impact.spawned_children.tolist() == [5]
    assert not owner.recoil_active.any()
    assert runtime.battle.entity_y_units[0, _slot(runtime, 1)].item() == 9_100

    scalar_children = sorted(
        (
            entity
            for entity in oracle.entities.values()
            if isinstance(entity, Projectile)
        ),
        key=lambda entity: entity.id,
    )
    tensor_children = owner.child_entity_id[0][owner.child_active[0]].tolist()
    assert (
        tensor_children == [entity.id for entity in scalar_children] == [6, 7, 8, 9, 10]
    )
    assert owner.child_target_units[0, :5].tolist() == [
        [6_151, 19_238],
        [4_876, 19_804],
        [3_500, 20_000],
        [2_123, 19_804],
        [848, 19_238],
    ]
    for index, scalar in enumerate(scalar_children):
        assert owner.child_position_units[0, index].tolist() == [
            tiles_to_logic_units(scalar.position.x),
            tiles_to_logic_units(scalar.position.y),
        ]
        assert owner.child_target_units[0, index].tolist() == [
            tiles_to_logic_units(scalar.target_position.x),
            tiles_to_logic_units(scalar.target_position.y),
        ]
        child_runtime_slot = _slot(runtime, scalar.id)
        assert runtime.phases.target_slot[0, child_runtime_slot].item() == -1

    scalar_shield = cast(
        Any, _mechanic(cast(Troop, oracle.entities[2]), "Shield")
    ).current_shield
    primary_slot = _slot(runtime, 2)
    assert owner.target_shield[0, primary_slot].item() == scalar_shield == 0
    assert not owner.target_shield_integer_kind[0, primary_slot].item()
    assert (
        runtime.battle.entity_hp[0, primary_slot].item() == oracle.entities[2].hitpoints
    )
    assert not runtime.battle.entity_hp_integer_kind[0, primary_slot].item()
    assert impact.damage[0, primary_slot].item() == 64

    center_hp = oracle.entities[3].hitpoints
    outer_hp = oracle.entities[4].hitpoints
    for _ in range(20):
        _scalar_step(oracle)
        step = owner.step_(runtime)
        assert step.committed.tolist() == [True]
        for entity_id in (2, 3, 4):
            tensor_slot = _slot(runtime, entity_id)
            assert (
                runtime.battle.entity_hp[0, tensor_slot].item()
                == oracle.entities[entity_id].hitpoints
            )
    assert center_hp - oracle.entities[3].hitpoints == 64
    assert outer_hp - oracle.entities[4].hitpoints == 64

    count = int(runtime.events.count.item())
    opcodes = runtime.events.opcode[0, :count]
    phases = runtime.events.phase[0, :count]
    assert (opcodes == RuntimeEventOpcode.SPAWN).sum().item() == 6
    assert phases[0].item() == TickPhase.COMBAT
    assert (opcodes == RuntimeEventOpcode.DAMAGE).sum().item() >= 7


def test_clone_fork_reset_and_commit_capacity_rollback(tensor_device: str) -> None:
    battle = _battle(992_110)
    runtime, owner = _owners(battle, tensor_device, max_entities=4)
    runtime_before = {
        descriptor.name: getattr(runtime.battle, descriptor.name).clone()
        for descriptor in fields(runtime.battle)
        if isinstance(getattr(runtime.battle, descriptor.name), torch.Tensor)
    }
    next_id = runtime.entity_pool.next_entity_id.clone()

    result = owner.commit_attacks_(
        runtime,
        source_slots=torch.tensor([[0]], dtype=torch.int64, device=runtime.device),
        target_slots=torch.tensor([[1]], dtype=torch.int64, device=runtime.device),
        valid=torch.tensor([[True]], dtype=torch.bool, device=runtime.device),
    )

    assert result.committed.tolist() == [False]
    assert result.capacity_rejected.tolist() == [True]
    assert torch.equal(runtime.entity_pool.next_entity_id, next_id)
    assert not owner.parent_active.any()
    for name, expected in runtime_before.items():
        assert torch.equal(getattr(runtime.battle, name), expected), name

    clone = owner.clone()
    clone.recoil_entity_id[0, 0] = 99
    assert owner.recoil_entity_id[0, 0].item() == 0
    fork = clone.fork([0])
    assert fork.recoil_entity_id[0, 0].item() == 99
    clone.reset_rows_([0], owner, [0])
    assert clone.recoil_entity_id[0, 0].item() == 0


def test_child_start_collision_matches_serialized_air_target_plane(
    tensor_device: str,
) -> None:
    battle = BattleState(fast_path=False, rng=random.Random(992_115))
    battle.entities.clear()
    battle.next_entity_id = 1
    _spawn(battle, "Firecracker", 0, Position(9.0, 10.0))
    air_target = _spawn(battle, "MegaMinion", 1, Position(9.0, 15.0))
    oracle = battle.clone()
    _commit_scalar(oracle)
    runtime, owner = _owners(
        battle,
        tensor_device,
        max_entities=10,
        event_capacity=256,
    )
    _commit_tensor(runtime, owner)
    air_slot = _slot(runtime, air_target.id)
    assert owner.target_airborne[0, air_slot].item()
    hp_before = air_target.hitpoints

    for _ in range(10):
        _scalar_step(oracle)
        result = owner.step_(runtime)
        assert result.committed.tolist() == [True]

    assert (
        runtime.battle.entity_hp[0, air_slot].item()
        == oracle.entities[air_target.id].hitpoints
    )
    assert hp_before - oracle.entities[air_target.id].hitpoints == 5 * 64


def test_impact_child_capacity_failure_rolls_back_recoil_parent_and_events(
    tensor_device: str,
) -> None:
    battle = _battle(992_120)
    runtime, owner = _owners(
        battle,
        tensor_device,
        max_entities=9,
        child_capacity=4,
    )
    _commit_tensor(runtime, owner)
    owner.parent_position_units[0, 0] = owner.parent_target_units[0, 0]
    runtime_before = runtime.clone()
    owner_before = owner.clone()

    result = owner.step_(runtime)

    assert result.committed.tolist() == [False]
    assert result.capacity_rejected.tolist() == [True]
    assert torch.equal(
        runtime.battle.entity_y_units, runtime_before.battle.entity_y_units
    )
    assert torch.equal(runtime.events.count, runtime_before.events.count)
    assert torch.equal(
        runtime.entity_pool.next_entity_id, runtime_before.entity_pool.next_entity_id
    )
    for descriptor in fields(owner):
        actual = getattr(owner, descriptor.name)
        expected = getattr(owner_before, descriptor.name)
        if isinstance(actual, torch.Tensor):
            assert torch.equal(actual, expected), descriptor.name
