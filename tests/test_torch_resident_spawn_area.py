from __future__ import annotations

import random
from dataclasses import fields
from typing import Any, cast

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import AreaEffect, Building, Troop
from clasher.torch_sim.resident_spawn_area import TensorResidentSpawnAreas
from clasher.torch_sim.runtime_state import RuntimeEventOpcode, TensorBattleRuntime


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> str:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return device


def _spawn_troop(
    battle: BattleState,
    name: str,
    player: int,
    position: Position,
    *,
    fire_spawn: bool = False,
) -> Troop:
    stats = battle.card_loader.get_card(name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(
        position,
        player,
        stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    entity = next(
        candidate
        for entity_id, candidate in battle.entities.items()
        if entity_id not in before and isinstance(candidate, Troop)
    )
    assert isinstance(entity, Troop)
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    if fire_spawn:
        entity.on_spawn()
    return entity


def _battle(source_name: str, seed: int) -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(seed))
    battle.entities.clear()
    battle.next_entity_id = 1
    _spawn_troop(battle, "Knight", 1, Position(10.0, 14.0))
    _spawn_troop(battle, "MegaMinion", 1, Position(8.0, 14.0))
    cannon_stats = battle.card_loader.get_card("Cannon")
    assert cannon_stats is not None
    cannon = battle._spawn_entity(Building, Position(11.5, 14.0), 1, cannon_stats)
    cannon.deploy_delay_remaining = 0.0
    cannon.placement_pending = False
    source = _spawn_troop(battle, source_name, 0, Position(9.0, 14.0))
    for entity_id, entity in tuple(battle.entities.items()):
        if isinstance(entity, AreaEffect):
            battle.entities.pop(entity_id)
    battle.next_entity_id = max(battle.entities) + 1
    source._spawn_hook_fired = False
    source._spawn_hook_pending = True
    for mechanic in source.mechanics:
        if type(mechanic).__name__ == "SpawnAreaEffect":
            cast(Any, mechanic)._applied = False
    return battle


def _owners(
    battle: BattleState,
    device: str,
    *,
    event_capacity: int = 128,
    capacity: int = 2,
    max_entities: int = 12,
) -> tuple[TensorBattleRuntime, TensorResidentSpawnAreas]:
    runtime = TensorBattleRuntime.from_battles(
        [battle.clone()],
        device=device,
        max_entities=max_entities,
        event_capacity=event_capacity,
    )
    owner = TensorResidentSpawnAreas.from_battles(runtime, [battle], capacity=capacity)
    return runtime, owner


def _slot(runtime: TensorBattleRuntime, entity_id: int) -> int:
    return runtime.battle.entity_id[0].tolist().index(entity_id)


def _scalar_resolve(battle: BattleState) -> AreaEffect:
    source = cast(Troop, battle.entities[4])
    source.on_spawn()
    area = next(
        entity for entity in battle.entities.values() if isinstance(entity, AreaEffect)
    )
    area.update(battle.dt, battle)
    return area


def _tensor_resolve(
    runtime: TensorBattleRuntime,
    owner: TensorResidentSpawnAreas,
) -> tuple[int, Any]:
    source_slot = _slot(runtime, 4)
    materialized = owner.materialize_spawns_(
        runtime,
        source_slots=torch.tensor(
            [[source_slot]], dtype=torch.int64, device=runtime.device
        ),
        valid=torch.tensor([[True]], dtype=torch.bool, device=runtime.device),
    )
    assert materialized.committed.tolist() == [True]
    assert materialized.accepted.tolist() == [True]
    area_id = int(materialized.area_entity_ids[0, 0].item())
    result = owner.step_(runtime)
    assert result.committed.tolist() == [True]
    return area_id, result


@pytest.mark.parametrize(
    ("source_name", "expected_damage", "stun", "slow"),
    [
        ("IceWizard", 84.0, 0.0, 0.7),
        ("ElectroWizard", 192.0, 0.5, 1.0),
    ],
)
def test_spawn_area_full_snapshot_damage_status_planes_match_scalar(
    tensor_device: str,
    source_name: str,
    expected_damage: float,
    stun: float,
    slow: float,
) -> None:
    source = _battle(source_name, 993_100)
    oracle = source.clone()
    scalar_area = _scalar_resolve(oracle)
    runtime, owner = _owners(source, tensor_device)
    area_id, result = _tensor_resolve(runtime, owner)
    card = runtime.battle.card_to_id[source_name]

    assert area_id == scalar_area.id == 5
    assert owner.catalog.supported[card].item()
    assert owner.catalog.radius_units[card].item() == 3_000
    assert owner.catalog.damage[card].item() == expected_damage
    assert not owner.catalog.damage_integer_kind[card].item()
    assert owner.catalog.status_duration[card].item() == pytest.approx(
        2.5 if source_name == "IceWizard" else 0.5
    )
    assert owner.catalog.knockback_units[card].item() == 0
    assert result.damage_targets[0, :4].tolist() == [True, True, True, False]
    assert result.status_targets[0, :4].tolist() == [True, True, True, False]
    assert not result.knockback_started.any()

    for entity_id in (1, 2, 3):
        slot = _slot(runtime, entity_id)
        scalar = oracle.entities[entity_id]
        assert runtime.battle.entity_hp[0, slot].item() == scalar.hitpoints
        assert result.damage[0, slot].item() == expected_damage
        assert not runtime.battle.entity_hp_integer_kind[0, slot].item()
        assert runtime.status.stun_timer[0, slot].item() == pytest.approx(stun)
        assert runtime.status.slow_multiplier[0, slot].item() == pytest.approx(slow)
        if source_name == "IceWizard":
            assert runtime.status.attack_speed_debuff_multiplier[
                0, slot
            ].item() == pytest.approx(0.7)
            assert runtime.status.spawn_speed_debuff_multiplier[
                0, slot
            ].item() == pytest.approx(0.7)

    source_slot = _slot(runtime, 4)
    assert (
        runtime.battle.entity_hp[0, source_slot].item() == oracle.entities[4].hitpoints
    )
    assert not owner.active.any()
    assert area_id not in runtime.battle.entity_id[0].tolist()
    assert owner.applied_source_entity_id[0, source_slot].item() == 4
    next_id = runtime.entity_pool.next_entity_id.clone()
    repeated = owner.materialize_spawns_(
        runtime,
        source_slots=torch.tensor(
            [[source_slot]], dtype=torch.int64, device=runtime.device
        ),
        valid=torch.tensor([[True]], dtype=torch.bool, device=runtime.device),
    )
    assert repeated.committed.tolist() == [True]
    assert repeated.accepted.tolist() == [False]
    assert torch.equal(runtime.entity_pool.next_entity_id, next_id)
    count = int(runtime.events.count.item())
    assert runtime.events.opcode[0, :count].tolist() == [
        RuntimeEventOpcode.SPAWN,
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.DAMAGE,
    ]
    assert runtime.events.target_id[0, 1:4].tolist() == [1, 2, 3]


def test_snapshot_retains_later_target_after_geometry_changes(
    tensor_device: str,
) -> None:
    source = _battle("IceWizard", 993_110)
    oracle = source.clone()
    cast(Troop, oracle.entities[4]).on_spawn()
    scalar_area = next(
        entity for entity in oracle.entities.values() if isinstance(entity, AreaEffect)
    )
    runtime, owner = _owners(source, tensor_device)
    source_slot = _slot(runtime, 4)
    materialized = owner.materialize_spawns_(
        runtime,
        source_slots=torch.tensor(
            [[source_slot]], dtype=torch.int64, device=runtime.device
        ),
        valid=torch.tensor([[True]], dtype=torch.bool, device=runtime.device),
    )
    assert materialized.committed.tolist() == [True]

    # Damage uses the committed footprint even if a target is displaced before
    # target iteration; the later status query uses current geometry.
    oracle.entities[3].position = Position(17.0, 14.0)
    runtime.battle.entity_x_units[0, _slot(runtime, 3)] = 17_000
    hp_before = oracle.entities[3].hitpoints
    scalar_area._apply_damage_tick(oracle, scalar_area.damage)
    scalar_area._apply_continuous_effects(
        0.001,
        oracle,
        effect_time_remaining=0.0,
    )
    result = owner.step_(runtime)

    target_slot = _slot(runtime, 3)
    assert hp_before - oracle.entities[3].hitpoints == 0
    # The scalar helper took its snapshot after displacement. The retained
    # owner proves the earlier committed snapshot independently.
    assert result.damage[0, target_slot].item() == 84
    assert not result.status_targets[0, target_slot].item()
    assert runtime.status.slow_multiplier[0, target_slot].item() == 1.0


def test_clone_fork_reset_and_event_capacity_rollback(tensor_device: str) -> None:
    source = _battle("ElectroWizard", 993_120)
    runtime, owner = _owners(source, tensor_device, event_capacity=1)
    source_slot = _slot(runtime, 4)
    materialized = owner.materialize_spawns_(
        runtime,
        source_slots=torch.tensor(
            [[source_slot]], dtype=torch.int64, device=runtime.device
        ),
        valid=torch.tensor([[True]], dtype=torch.bool, device=runtime.device),
    )
    assert materialized.committed.tolist() == [True]
    runtime_before = runtime.clone()
    owner_before = owner.clone()

    result = owner.step_(runtime)

    assert result.committed.tolist() == [False]
    assert result.capacity_rejected.tolist() == [True]
    assert torch.equal(runtime.events.count, runtime_before.events.count)
    assert torch.equal(runtime.battle.entity_hp, runtime_before.battle.entity_hp)
    assert torch.equal(
        runtime.entity_pool.next_entity_id,
        runtime_before.entity_pool.next_entity_id,
    )
    for descriptor in fields(owner):
        actual = getattr(owner, descriptor.name)
        expected = getattr(owner_before, descriptor.name)
        if isinstance(actual, torch.Tensor):
            assert torch.equal(actual, expected), descriptor.name

    clone = owner.clone()
    clone.applied_source_entity_id[0, source_slot] = 99
    assert owner.applied_source_entity_id[0, source_slot].item() == 4
    fork = clone.fork([0])
    assert fork.applied_source_entity_id[0, source_slot].item() == 99
    clone.reset_rows_([0], owner, [0])
    assert clone.applied_source_entity_id[0, source_slot].item() == 4


def test_materialize_entity_capacity_failure_is_atomic(tensor_device: str) -> None:
    source = _battle("IceWizard", 993_130)
    runtime, owner = _owners(source, tensor_device, max_entities=4)
    next_id = runtime.entity_pool.next_entity_id.clone()
    events = runtime.events.count.clone()
    hp = runtime.battle.entity_hp.clone()

    result = owner.materialize_spawns_(
        runtime,
        source_slots=torch.tensor([[3]], dtype=torch.int64, device=runtime.device),
        valid=torch.tensor([[True]], dtype=torch.bool, device=runtime.device),
    )

    assert result.committed.tolist() == [False]
    assert result.capacity_rejected.tolist() == [True]
    assert torch.equal(runtime.entity_pool.next_entity_id, next_id)
    assert torch.equal(runtime.events.count, events)
    assert torch.equal(runtime.battle.entity_hp, hp)
    assert not owner.active.any()
