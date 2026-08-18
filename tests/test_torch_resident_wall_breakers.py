from __future__ import annotations

import random
from dataclasses import fields

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Projectile, Troop
from clasher.torch_sim.resident_wall_breakers import TensorResidentDemolition
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
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity.attack_cooldown = 0.0
    entity.on_spawn()
    return entity


def _battle(seed: int = 995_100) -> BattleState:
    battle = BattleState(fast_path=False, rng=random.Random(seed))
    battle.entities.clear()
    battle.next_entity_id = 1
    first = _spawn_troop(battle, "Wallbreakers", 0, Position(8.7, 14.0))
    second = _spawn_troop(battle, "Wallbreakers", 0, Position(9.3, 14.0))
    cannon_stats = battle.card_loader.get_card("Cannon")
    assert cannon_stats is not None
    cannon = battle._spawn_entity(Building, Position(9.0, 14.8), 1, cannon_stats)
    cannon.deploy_delay_remaining = 0.0
    cannon.placement_pending = False
    cannon.stun_timer = 100.0
    cannon.attack_cooldown = 100.0
    bystander = _spawn_troop(battle, "Knight", 1, Position(9.0, 13.5))
    bystander.stun_timer = 100.0
    bystander.attack_cooldown = 100.0
    first.position = Position(8.7, 14.0)
    second.position = Position(9.3, 14.0)
    return battle


def _owners(
    battle: BattleState,
    device: str,
    *,
    event_capacity: int = 128,
) -> tuple[TensorBattleRuntime, TensorResidentDemolition]:
    runtime = TensorBattleRuntime.from_battles(
        [battle.clone()],
        device=device,
        max_entities=12,
        event_capacity=event_capacity,
    )
    return runtime, TensorResidentDemolition.from_battles(runtime, [battle])


def _slot(runtime: TensorBattleRuntime, entity_id: int) -> int:
    return runtime.battle.entity_id[0].tolist().index(entity_id)


def _scalar_demolish(battle: BattleState) -> list[Projectile]:
    for entity_id in (1, 2):
        source = battle.entities[entity_id]
        assert isinstance(source, Troop)
        source.update_combat_component(battle.dt, battle)
    projectiles = sorted(
        (
            entity
            for entity in battle.entities.values()
            if isinstance(entity, Projectile)
        ),
        key=lambda entity: entity.id,
    )
    for projectile in projectiles:
        projectile.update(battle.dt, battle)
    return projectiles


def test_dual_demolition_ids_snapshot_damage_and_self_death_match_scalar(
    tensor_device: str,
) -> None:
    source = _battle()
    oracle = source.clone()
    scalar_projectiles = _scalar_demolish(oracle)
    runtime, owner = _owners(source, tensor_device)
    result = owner.step_(runtime)
    first_slot = _slot(runtime, 1)
    second_slot = _slot(runtime, 2)
    cannon_slot = _slot(runtime, 3)
    bystander_slot = _slot(runtime, 4)
    card = runtime.battle.entity_card[0, first_slot]

    assert result.committed.tolist() == [True]
    assert owner.catalog.supported[card].item()
    assert owner.catalog.deployment_count[card].item() == 2
    assert owner.catalog.deployment_radius_units[card].item() == 750
    assert owner.catalog.deployment_delay_ms[card].item() == 100
    assert owner.catalog.speed_units[card].item() == 120
    assert owner.catalog.damage[card].item() == 350
    assert owner.catalog.projectile_range_units[card].item() == 1
    assert owner.catalog.projectile_speed_units[card].item() == 1_000
    assert owner.catalog.splash_radius_units[card].item() == 1_500
    assert result.primed[0, first_slot].item()
    assert result.primed[0, second_slot].item()
    assert result.detonated[0, first_slot].item()
    assert result.detonated[0, second_slot].item()
    assert (
        result.projectile_entity_ids[0, [first_slot, second_slot]].tolist()
        == [projectile.id for projectile in scalar_projectiles]
        == [5, 6]
    )
    assert not runtime.battle.entity_active[0, first_slot].item()
    assert not runtime.battle.entity_active[0, second_slot].item()
    assert runtime.phases.death_pending[0, first_slot].item()
    assert runtime.phases.death_pending[0, second_slot].item()
    assert (
        runtime.battle.entity_hp[0, cannon_slot].item() == oracle.entities[3].hitpoints
    )
    assert (
        runtime.battle.entity_hp[0, bystander_slot].item()
        == oracle.entities[4].hitpoints
    )
    assert result.damage[0, cannon_slot].item() == 700
    assert result.damage[0, bystander_slot].item() == 700
    assert not runtime.battle.entity_hp_integer_kind[0, cannon_slot].item()
    assert not runtime.battle.entity_hp_integer_kind[0, bystander_slot].item()
    assert not any(
        entity_id in runtime.battle.entity_id[0].tolist() for entity_id in (5, 6)
    )

    count = int(runtime.events.count.item())
    assert runtime.events.opcode[0, :count].tolist() == [
        RuntimeEventOpcode.SPAWN,
        RuntimeEventOpcode.DEATH,
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.SPAWN,
        RuntimeEventOpcode.DEATH,
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.DAMAGE,
    ]
    assert runtime.events.source_id[0, :count].tolist() == [5, 1, 5, 5, 6, 2, 6, 6]
    assert runtime.events.target_id[0, 2:4].tolist() == [3, 4]
    assert runtime.events.target_id[0, 6:8].tolist() == [3, 4]


def test_waypoint_movement_and_building_only_target_acquisition(
    tensor_device: str,
) -> None:
    battle = _battle(995_110)
    battle.entities[1].position = Position(7.0, 10.0)
    battle.entities[2].position = Position(11.0, 10.0)
    runtime, owner = _owners(battle, tensor_device)
    waypoints = torch.zeros(
        (1, runtime.max_entities, 2), dtype=torch.int64, device=runtime.device
    )
    valid = torch.zeros(
        (1, runtime.max_entities), dtype=torch.bool, device=runtime.device
    )
    waypoints[0, _slot(runtime, 1)] = torch.tensor(
        [9_000, 14_800], dtype=torch.int64, device=runtime.device
    )
    waypoints[0, _slot(runtime, 2)] = torch.tensor(
        [9_000, 14_800], dtype=torch.int64, device=runtime.device
    )
    valid[0, [_slot(runtime, 1), _slot(runtime, 2)]] = True
    before = torch.stack(
        (
            runtime.battle.entity_x_units.clone(),
            runtime.battle.entity_y_units.clone(),
        ),
        dim=-1,
    ).to(torch.int64)

    result = owner.step_(
        runtime,
        waypoint_units=waypoints,
        waypoint_valid=valid,
    )

    for entity_id in (1, 2):
        slot = _slot(runtime, entity_id)
        assert result.moved[0, slot].item()
        assert owner.target_entity_id[0, slot].item() == 3
        delta = (
            torch.stack(
                (
                    runtime.battle.entity_x_units[0, slot],
                    runtime.battle.entity_y_units[0, slot],
                )
            ).to(torch.int64)
            - before[0, slot]
        )
        assert int(torch.linalg.vector_norm(delta.to(torch.float64)).item()) <= 120
    assert not result.detonated.any()


def test_clone_fork_reset_and_capacity_rollback(tensor_device: str) -> None:
    battle = _battle(995_120)
    runtime, owner = _owners(battle, tensor_device, event_capacity=8)
    runtime_before = runtime.clone()
    owner_before = owner.clone()

    result = owner.step_(runtime)

    assert result.committed.tolist() == [False]
    assert result.capacity_rejected.tolist() == [True]
    assert torch.equal(runtime.battle.entity_hp, runtime_before.battle.entity_hp)
    assert torch.equal(runtime.events.count, runtime_before.events.count)
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
    clone.target_entity_id[0, 0] = 99
    assert owner.target_entity_id[0, 0].item() == 0
    fork = clone.fork([0])
    assert fork.target_entity_id[0, 0].item() == 99
    clone.reset_rows_([0], owner, [0])
    assert clone.target_entity_id[0, 0].item() == 0
