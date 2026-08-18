from __future__ import annotations

import copy
from contextlib import AbstractContextManager
from dataclasses import fields
from typing import Any, cast

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import (
    AreaEffect,
    BuffAreaEffect,
    Building,
    DeathAreaEffectContainer,
    Troop,
)
from clasher.torch_sim.oracle_event_capture import (
    OracleEventRecord,
    PythonOracleEventCapture,
)
from clasher.torch_sim.resident_death_areas import TensorResidentDeathAreas
from clasher.torch_sim.resident_death_payloads import (
    TensorDeathPayloadState,
    step_death_payloads_,
)
from clasher.torch_sim.runtime_state import TensorBattleRuntime, TickPhase


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
    entity.position = Position(position.x, position.y)
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity.stun_timer = 100.0
    entity.attack_cooldown = 100.0
    return entity


def _battle(source_name: str) -> tuple[BattleState, Troop, dict[str, Troop]]:
    battle = BattleState(fast_path=False)
    battle.entities.clear()
    battle.next_entity_id = 1
    source = _spawn(battle, source_name, 0, Position(9.0, 14.0))
    targets = {
        "enemy": _spawn(battle, "Knight", 1, Position(9.5, 14.0)),
        "ally": _spawn(battle, "Knight", 0, Position(8.5, 14.0)),
        "outside": _spawn(battle, "Knight", 1, Position(16.0, 14.0)),
    }
    source.hitpoints = 0.0
    source.is_alive = False
    return battle, source, targets


def _slot(runtime: TensorBattleRuntime, entity_id: int, row: int = 0) -> int:
    found = torch.where(runtime.battle.entity_id[row] == entity_id)[0]
    assert found.numel() == 1
    return int(found[0].item())


def _phase_scope(
    capture: PythonOracleEventCapture,
    phase: TickPhase,
    source_id: int,
) -> AbstractContextManager[None]:
    return cast(
        AbstractContextManager[None],
        cast(Any, capture)._scope(phase=phase, source_id=source_id),
    )


def _run_scalar_death_payloads(battle: BattleState, source_id: int) -> None:
    source = battle.entities[source_id]
    for mechanic in source.mechanics:
        if type(mechanic).__name__ in {"DeathDamage", "DeathAreaEffect"}:
            mechanic.on_death(source)


def _scalar_object_tick(battle: BattleState) -> None:
    for entity in tuple(battle.entities.values()):
        if entity.is_alive:
            entity.update_status_effects(battle.dt)
    processed: set[int] = set()
    while True:
        objects = sorted(
            (
                entity
                for entity_id, entity in battle.entities.items()
                if entity_id not in processed
                and entity.is_alive
                and not isinstance(entity, (Troop, Building))
            ),
            key=lambda entity: entity.id,
        )
        if not objects:
            break
        for entity in objects:
            processed.add(entity.id)
            entity.update(battle.dt, battle)
    battle._cleanup_dead_entities()
    battle.time += battle.dt
    battle.tick += 1


def _event_tuples(
    runtime: TensorBattleRuntime,
    start: int,
) -> list[tuple[int, int, int, int, int, int, float]]:
    end = int(runtime.events.count[0].item())
    return [
        (
            int(runtime.events.phase[0, index].item()),
            int(runtime.events.opcode[0, index].item()),
            int(runtime.events.source_id[0, index].item()),
            int(runtime.events.target_id[0, index].item()),
            int(runtime.events.x_units[0, index].item()),
            int(runtime.events.y_units[0, index].item()),
            float(runtime.events.amount[0, index].item()),
        )
        for index in range(start, end)
    ]


def _oracle_tuples(
    events: list[OracleEventRecord] | tuple[OracleEventRecord, ...],
) -> list[tuple[int, int, int, int, int, int, float]]:
    return [
        (
            event.phase,
            event.opcode,
            event.source_id,
            event.target_id,
            event.x_units,
            event.y_units,
            float(cast(Any, event.amount)),
        )
        for event in events
    ]


def _stack(
    boundary: BattleState,
    device: str,
    *,
    event_capacity: int = 2_048,
    area_capacity: int = 4,
) -> tuple[
    TensorBattleRuntime,
    TensorDeathPayloadState,
    TensorResidentDeathAreas,
]:
    runtime = TensorBattleRuntime.from_battles(
        [copy.deepcopy(boundary)],
        device=device,
        max_entities=16,
        event_capacity=event_capacity,
    )
    death_state = TensorDeathPayloadState.from_battles(runtime, [boundary])
    consumer = TensorResidentDeathAreas.from_battles(
        runtime, [boundary], capacity=area_capacity
    )
    return runtime, death_state, consumer


@pytest.mark.parametrize("source_name", ("IceGolem", "Lumberjack"))
def test_full_post_death_area_lifecycle_matches_scalar(
    source_name: str,
    tensor_device: str,
) -> None:
    boundary, source, targets = _battle(source_name)
    oracle = copy.deepcopy(boundary)
    runtime, death_state, consumer = _stack(boundary, tensor_device)
    capture = PythonOracleEventCapture(oracle)
    with capture:
        with _phase_scope(capture, TickPhase.CLEANUP_AND_SPAWNS, source.id):
            _run_scalar_death_payloads(oracle, source.id)
        oracle.entities.pop(source.id)
        dead = torch.zeros_like(runtime.entity_pool.active)
        dead[0, _slot(runtime, source.id)] = True
        emitted = step_death_payloads_(runtime, death_state, dead)
        consumed = consumer.consume_descriptors_(runtime, emitted.areas)

        assert emitted.committed.tolist() == [True]
        assert consumed.committed.tolist() == [True]
        assert consumed.accepted.sum().item() == 1
        tensor_initial = _event_tuples(runtime, 0)
        oracle_initial = _oracle_tuples(capture.events)
        assert [
            (phase, source_id, target_id, amount)
            for phase, _, source_id, target_id, _, _, amount in tensor_initial
        ] == [
            (phase, source_id, target_id, amount)
            for phase, _, source_id, target_id, _, _, amount in oracle_initial
        ]
        descriptor_slot = int(torch.where(emitted.areas.valid[0])[0][0].item())
        initial_object = next(
            entity
            for entity in oracle.entities.values()
            if isinstance(
                entity,
                (AreaEffect, BuffAreaEffect, DeathAreaEffectContainer),
            )
        )
        assert consumer.object_id[0, 0].item() == initial_object.id
        assert (
            consumer.duration_ms[0, 0].item()
            == emitted.areas.duration_ms[0, descriptor_slot].item()
        )

        total_ticks = 70 if source_name == "IceGolem" else 145
        enemy_hp_before = targets["enemy"].hitpoints
        ally_hp_before = targets["ally"].hitpoints
        for _ in range(total_ticks):
            before_oracle = len(capture.events)
            before_tensor = int(runtime.events.count[0].item())
            with _phase_scope(capture, TickPhase.OBJECTS, 0):
                _scalar_object_tick(oracle)
            runtime.status.tick(
                runtime.battle.dt,
                component_mask=(
                    runtime.entity_pool.active & runtime.battle.entity_active
                ),
            )
            runtime.battle.time += runtime.battle.dt
            runtime.battle.tick += 1
            result = consumer.step_(runtime)
            assert result.committed.tolist() == [True]
            assert runtime.battle.rng.python_state(0) == oracle.rng.getstate()
            assert _event_tuples(runtime, before_tensor) == _oracle_tuples(
                capture.events[before_oracle:]
            )
            for target in targets.values():
                scalar_target = oracle.entities[target.id]
                slot = _slot(runtime, target.id)
                assert runtime.battle.entity_hp[0, slot].item() == (
                    scalar_target.hitpoints
                )
                assert runtime.battle.entity_hp_integer_kind[0, slot].item() == (
                    type(scalar_target.hitpoints) is int
                )
                assert runtime.status.slow_timer[0, slot].item() == pytest.approx(
                    scalar_target.slow_timer
                )
                assert runtime.status.slow_multiplier[0, slot].item() == (
                    scalar_target.slow_multiplier
                )
                assert runtime.status.haste_timer[0, slot].item() == pytest.approx(
                    scalar_target.haste_timer
                )
                assert (
                    runtime.status.movement_speed_buff_multiplier[0, slot].item()
                    == scalar_target.movement_speed_buff_multiplier
                )

        assert not consumer.active.any()
        assert oracle.entities[targets["outside"].id].hitpoints == (
            targets["outside"].max_hitpoints
        )
        if source_name == "IceGolem":
            assert oracle.entities[targets["enemy"].id].hitpoints == (
                enemy_hp_before - 84
            )
            assert oracle.entities[targets["ally"].id].hitpoints == ally_hp_before
            assert (
                runtime.status.slow_timer[0, _slot(runtime, targets["enemy"].id)] == 0
            )
        else:
            assert oracle.entities[targets["enemy"].id].hitpoints == (
                enemy_hp_before - 179
            )
            assert oracle.entities[targets["ally"].id].hitpoints == ally_hp_before
            assert (
                runtime.status.haste_timer[0, _slot(runtime, targets["ally"].id)] == 0
            )


def test_lumberjack_container_and_rage_scan_boundaries_are_exact(
    tensor_device: str,
) -> None:
    boundary, source, targets = _battle("Lumberjack")
    oracle = copy.deepcopy(boundary)
    _run_scalar_death_payloads(oracle, source.id)
    oracle.entities.pop(source.id)
    runtime, death_state, consumer = _stack(boundary, tensor_device)
    dead = torch.zeros_like(runtime.entity_pool.active)
    dead[0, _slot(runtime, source.id)] = True
    emitted = step_death_payloads_(runtime, death_state, dead)
    assert consumer.consume_descriptors_(runtime, emitted.areas).committed.tolist() == [
        True
    ]
    ally_slot = _slot(runtime, targets["ally"].id)
    enemy_slot = _slot(runtime, targets["enemy"].id)
    enemy_hp = runtime.battle.entity_hp[0, enemy_slot].item()

    for tick in range(15):
        _scalar_object_tick(oracle)
        runtime.status.tick(
            runtime.battle.dt,
            component_mask=runtime.entity_pool.active & runtime.battle.entity_active,
        )
        result = consumer.step_(runtime)
        assert result.committed.tolist() == [True]
        if tick < 9:
            assert consumer.container.any()
            assert runtime.battle.entity_hp[0, enemy_slot].item() == enemy_hp
        if tick == 9:
            assert result.container_activated.any()
            assert not consumer.container.any()
            assert runtime.battle.entity_hp[0, enemy_slot].item() == enemy_hp - 179
            assert runtime.status.haste_timer[0, ally_slot].item() == 0.0
        if tick == 14:
            assert runtime.status.haste_timer[0, ally_slot].item() == 1.0


def test_clone_fork_reset_and_consume_capacity_rollback_are_atomic() -> None:
    boundary, source, _ = _battle("IceGolem")
    runtime, death_state, consumer = _stack(boundary, "cpu", area_capacity=1)
    dead = torch.zeros_like(runtime.entity_pool.active)
    dead[0, _slot(runtime, source.id)] = True
    emitted = step_death_payloads_(runtime, death_state, dead)
    consumer.active[0, 0] = True
    before_runtime = {
        descriptor.name: getattr(runtime.battle, descriptor.name).clone()
        for descriptor in fields(runtime.battle)
        if isinstance(getattr(runtime.battle, descriptor.name), torch.Tensor)
    }
    before_next = runtime.entity_pool.next_entity_id.clone()
    before_events = runtime.events.count.clone()

    rejected = consumer.consume_descriptors_(runtime, emitted.areas)

    assert rejected.committed.tolist() == [False]
    assert rejected.capacity_rejected.tolist() == [True]
    assert torch.equal(runtime.entity_pool.next_entity_id, before_next)
    assert torch.equal(runtime.events.count, before_events)
    for name, expected in before_runtime.items():
        assert torch.equal(getattr(runtime.battle, name), expected), name

    clone = consumer.clone()
    clone.object_id[0, 0] = 77
    assert consumer.object_id[0, 0].item() == 0
    fork = clone.fork([0])
    assert fork.object_id[0, 0].item() == 77
    clone.reset_rows_([0], consumer, [0])
    assert clone.object_id[0, 0].item() == 0


def test_step_event_capacity_failure_rolls_back_runtime_and_owner() -> None:
    boundary, source, _ = _battle("Lumberjack")
    runtime, death_state, consumer = _stack(
        boundary, "cpu", event_capacity=2, area_capacity=2
    )
    dead = torch.zeros_like(runtime.entity_pool.active)
    dead[0, _slot(runtime, source.id)] = True
    emitted = step_death_payloads_(runtime, death_state, dead)
    assert consumer.consume_descriptors_(runtime, emitted.areas).committed.tolist() == [
        True
    ]
    for _ in range(9):
        assert consumer.step_(runtime).committed.tolist() == [True]
    before = consumer.clone()
    before_ids = runtime.battle.entity_id.clone()
    before_next = runtime.entity_pool.next_entity_id.clone()

    failed = consumer.step_(runtime)

    assert failed.committed.tolist() == [False]
    assert failed.capacity_rejected.tolist() == [True]
    assert torch.equal(consumer.age_ms, before.age_ms)
    assert torch.equal(runtime.battle.entity_id, before_ids)
    assert torch.equal(runtime.entity_pool.next_entity_id, before_next)
