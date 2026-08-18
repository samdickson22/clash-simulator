from __future__ import annotations

import random
from dataclasses import fields

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, TimedExplosive, Troop
from clasher.torch_sim.resident_charge_carrier import (
    TensorResidentChargeCarriers,
)
from clasher.torch_sim.runtime_state import RuntimeEventOpcode, TensorBattleRuntime


@pytest.fixture(params=("cpu", "cuda"))
def tensor_device(request: pytest.FixtureRequest) -> str:
    device = str(request.param)
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return device


def _battle(
    card_name: str,
    *,
    source_y: float,
    target_y: float,
    seed: int,
) -> tuple[BattleState, Troop, Building]:
    battle = BattleState(fast_path=False, rng=random.Random(seed))
    battle.entities.clear()
    battle.next_entity_id = 1
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    battle._spawn_unit_at_position(
        Position(9.0, source_y),
        0,
        stats,
        deploy_delay_override=0.0,
        snap_to_valid=False,
    )
    source = next(
        entity for entity in battle.entities.values() if isinstance(entity, Troop)
    )
    source.deploy_delay_remaining = 0.0
    source.placement_pending = False
    source.attack_cooldown = 0.0
    source.on_spawn()
    cannon_stats = battle.card_loader.get_card("Cannon")
    assert cannon_stats is not None
    target = battle._spawn_entity(
        Building,
        Position(9.0, target_y),
        1,
        cannon_stats,
    )
    assert isinstance(target, Building)
    target.deploy_delay_remaining = 0.0
    target.placement_pending = False
    target.stun_timer = 100.0
    target.attack_cooldown = 100.0
    return battle, source, target


def _owners(
    battle: BattleState,
    device: str,
    *,
    event_capacity: int = 64,
) -> tuple[TensorBattleRuntime, TensorResidentChargeCarriers]:
    runtime = TensorBattleRuntime.from_battles(
        [battle.clone()],
        device=device,
        max_entities=12,
        event_capacity=event_capacity,
    )
    return runtime, TensorResidentChargeCarriers.from_battles(runtime, [battle])


def _slot(runtime: TensorBattleRuntime, entity_id: int) -> int:
    return runtime.battle.entity_id[0].tolist().index(entity_id)


def _scalar_tick(source: Troop, battle: BattleState) -> None:
    source.update_components(battle.dt, battle)
    source.tick_character_object_phase(battle.dt)


def test_battle_ram_charge_speed_damage_demolition_and_handoff_match_scalar(
    tensor_device: str,
) -> None:
    source_battle, _, _ = _battle(
        "BattleRam", source_y=9.0, target_y=14.0, seed=994_100
    )
    oracle = source_battle.clone()
    scalar_source = oracle.entities[1]
    scalar_target = oracle.entities[2]
    assert isinstance(scalar_source, Troop) and isinstance(scalar_target, Building)
    runtime, owner = _owners(source_battle, tensor_device)
    source_slot = _slot(runtime, 1)
    target_slot = _slot(runtime, 2)
    card = runtime.battle.entity_card[0, source_slot]

    assert owner.catalog.supported[card].item()
    assert owner.catalog.base_speed_units[card].item() == 60
    assert owner.catalog.charged_speed_units[card].item() == 120
    assert owner.catalog.charge_range_units[card].item() == 300
    assert owner.catalog.damage[card].item() == 286
    assert owner.catalog.charged_damage[card].item() == 573
    assert owner.catalog.child_name[int(card.item())] == "Barbarian"
    assert owner.catalog.child_count[card].item() == 2
    assert owner.catalog.child_deploy_ms[card].item() == 1_000

    final = None
    for _ in range(51):
        _scalar_tick(scalar_source, oracle)
        final = owner.step_(runtime)
        assert final.committed.tolist() == [True]
        assert owner.charge_progress[0, source_slot].item() == (
            scalar_source._native_charge_progress
        )
        assert owner.charging[0, source_slot].item() == scalar_source.is_charging
        assert owner.target_entity_id[0, source_slot].item() == 2

    assert scalar_source.is_charging
    assert owner.charge_progress[0, source_slot].item() == 10_000
    scalar_source.position = Position(9.0, 13.5)
    runtime.battle.entity_x_units[0, source_slot] = 9_000
    runtime.battle.entity_y_units[0, source_slot] = 13_500
    _scalar_tick(scalar_source, oracle)
    final = owner.step_(runtime)

    assert final is not None
    assert not scalar_source.is_alive
    assert final.impacted[0, source_slot].item()
    assert final.carrier_death[0, source_slot].item()
    assert final.damage[0, target_slot].item() == 573
    assert runtime.battle.entity_hp[0, target_slot].item() == scalar_target.hitpoints
    assert not runtime.battle.entity_hp_integer_kind[0, target_slot].item()
    assert final.handoff.valid[0, source_slot].item()
    assert final.handoff.parent_entity_id[0, source_slot].item() == 1
    assert final.handoff.child_count[0, source_slot].item() == 2
    assert final.handoff.child_deploy_ms[0, source_slot].item() == 1_000
    assert not final.handoff.child_is_timed[0, source_slot].item()
    barbarians = [
        entity
        for entity in oracle.entities.values()
        if isinstance(entity, Troop)
        and getattr(entity.card_stats, "name", None) == "Barbarian"
    ]
    assert len(barbarians) == 2
    count = int(runtime.events.count.item())
    assert runtime.events.opcode[0, :count].tolist() == [
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.DEATH,
    ]
    assert runtime.events.target_id[0, :count].tolist() == [2, 1]


def test_skeleton_barrel_delayed_demolition_and_timed_child_handoff_match_scalar(
    tensor_device: str,
) -> None:
    source_battle, _, target = _battle(
        "SkeletonBarrel", source_y=13.5, target_y=14.0, seed=994_110
    )
    oracle = source_battle.clone()
    scalar_source = oracle.entities[1]
    assert isinstance(scalar_source, Troop)
    runtime, owner = _owners(source_battle, tensor_device)
    source_slot = _slot(runtime, 1)
    target_slot = _slot(runtime, target.id)
    target_hp = target.hitpoints
    card = runtime.battle.entity_card[0, source_slot]

    assert owner.catalog.base_speed_units[card].item() == 90
    assert owner.catalog.charge_range_units[card].item() == 0
    assert owner.catalog.kamikaze_delay_ms[card].item() == 500
    assert owner.catalog.child_name[int(card.item())] == "SkeletonContainerNew"
    assert owner.catalog.child_is_timed[card].item()
    assert owner.catalog.child_terminal_knockback_units[card].item() == 1_000

    final = None
    for tick in range(12):
        _scalar_tick(scalar_source, oracle)
        final = owner.step_(runtime)
        assert final.committed.tolist() == [True]
        if tick == 0:
            assert scalar_source.kamikaze_primed
            assert owner.kamikaze_primed[0, source_slot].item()
            assert owner.kamikaze_remaining_ms[0, source_slot].item() == 500
        if not scalar_source.is_alive:
            break

    assert final is not None
    assert not scalar_source.is_alive
    assert final.carrier_death[0, source_slot].item()
    assert final.damage[0, target_slot].item() == 0
    assert runtime.battle.entity_hp[0, target_slot].item() == target_hp
    assert final.handoff.valid[0, source_slot].item()
    assert final.handoff.child_count[0, source_slot].item() == 1
    assert final.handoff.child_terminal_knockback_units[0, source_slot].item() == 1_000
    assert final.handoff.child_is_timed[0, source_slot].item()
    containers = [
        entity
        for entity in oracle.entities.values()
        if isinstance(entity, TimedExplosive)
    ]
    assert len(containers) == 1
    assert containers[0].explosion_timer == pytest.approx(0.6)


def test_deploy_clock_blocks_acquisition_and_travel_until_next_frame(
    tensor_device: str,
) -> None:
    battle, source, _ = _battle("BattleRam", source_y=9.0, target_y=14.0, seed=994_115)
    source.deploy_delay_remaining = 0.1
    source.placement_pending = True
    oracle = battle.clone()
    scalar = oracle.entities[1]
    assert isinstance(scalar, Troop)
    runtime, owner = _owners(battle, tensor_device)
    source_slot = _slot(runtime, 1)

    for expected in (0.05, 0.0):
        _scalar_tick(scalar, oracle)
        result = owner.step_(runtime)
        assert result.committed.tolist() == [True]
        assert not result.moved[0, source_slot].item()
        assert owner.target_entity_id[0, source_slot].item() == 0
        assert runtime.battle.entity_deploy_delay[
            0, source_slot
        ].item() == pytest.approx(expected)
        assert runtime.battle.entity_deploy_delay[
            0, source_slot
        ].item() == pytest.approx(scalar.deploy_delay_remaining)

    _scalar_tick(scalar, oracle)
    result = owner.step_(runtime)
    assert result.moved[0, source_slot].item()
    assert owner.target_entity_id[0, source_slot].item() == 2


def test_clone_fork_reset_and_event_capacity_rollback(tensor_device: str) -> None:
    battle, _, _ = _battle("BattleRam", source_y=12.8, target_y=14.0, seed=994_120)
    runtime, owner = _owners(battle, tensor_device, event_capacity=1)
    runtime.battle.entity_deploy_delay[0, 0] = 0.0
    runtime.battle.entity_placement_pending[0, 0] = False
    runtime_before = runtime.clone()
    owner_before = owner.clone()

    result = owner.step_(runtime)

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
    clone.charge_progress[0, 0] = 123
    assert owner.charge_progress[0, 0].item() == 0
    fork = clone.fork([0])
    assert fork.charge_progress[0, 0].item() == 123
    clone.reset_rows_([0], owner, [0])
    assert clone.charge_progress[0, 0].item() == 0
