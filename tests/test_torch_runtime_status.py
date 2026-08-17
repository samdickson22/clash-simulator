from __future__ import annotations

from typing import cast

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Entity, Troop
from clasher.torch_sim.runtime_state import RuntimeEventOpcode, TensorBattleRuntime
from clasher.torch_sim.runtime_status import (
    TensorRuntimeStatusPhase,
    step_runtime_status_phase_,
)


def _empty_battle() -> BattleState:
    battle = BattleState()
    battle.entities.clear()
    battle.next_entity_id = 1
    return battle


def _spawn_building(battle: BattleState, name: str, x: float) -> Building:
    stats = battle.card_loader.get_card(name)
    assert stats is not None and stats.lifetime_ms
    return cast(
        Building,
        battle._spawn_entity(Building, Position(x, 12.0), 0, stats),
    )


def _spawn_troop(battle: BattleState, x: float) -> Troop:
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    return cast(
        Troop,
        battle._spawn_entity(Troop, Position(x, 12.0), 0, stats),
    )


def test_standard_building_lifetime_and_status_match_oracle_phase_order() -> None:
    battle = _empty_battle()
    buildings = [
        _spawn_building(battle, name, 2.0 + 3.0 * index)
        for index, name in enumerate(("Cannon", "Tesla", "BombTower", "Tombstone"))
    ]
    for index, building in enumerate(buildings):
        building.apply_stun(0.1 + index * 0.05)
        building.apply_slow(0.2, 0.7)
    expected = battle.clone()
    runtime = TensorBattleRuntime.from_battles([battle], max_entities=16)
    phase = TensorRuntimeStatusPhase.from_battles(runtime, [battle])

    for _ in range(25):
        for entity in expected.entities.values():
            if isinstance(entity, Building):
                entity.update_hitpoint_component(0.05)
        for entity in expected.entities.values():
            if isinstance(entity, (Troop, Building)) and entity.is_alive:
                entity.update_buff_component(0.05)
        runtime.events.clear()
        result = step_runtime_status_phase_(runtime, phase)
        assert result.supported_batch.tolist() == [True]

    candidate = battle.clone()
    phase.sync_to_battles(runtime, [candidate])
    for entity_id, oracle in expected.entities.items():
        expected_building = cast(Building, oracle)
        actual = cast(Building, candidate.entities[entity_id])
        assert actual.hitpoints == expected_building.hitpoints
        assert actual.is_alive is expected_building.is_alive
        assert actual.stun_timer == expected_building.stun_timer
        assert actual.slow_timer == expected_building.slow_timer
        assert actual.slow_multiplier == expected_building.slow_multiplier
        assert actual.speed == expected_building.speed
        assert actual.lifetime_elapsed == expected_building.lifetime_elapsed
        assert actual.lifetime_decay_work == expected_building.lifetime_decay_work
        assert actual.lifetime_tick_carry_ms == expected_building.lifetime_tick_carry_ms


def test_periodic_hits_and_death_events_follow_entity_then_source_order() -> None:
    battle = _empty_battle()
    first = _spawn_troop(battle, 4.0)
    second = _spawn_troop(battle, 8.0)
    first.hitpoints = 9.0
    second.hitpoints = 30.0
    first.apply_periodic_damage(
        source_id=20,
        source_kind=None,
        duration=1.0,
        hit_interval=0.05,
        damage=5.0,
    )
    first.apply_periodic_damage(
        source_id=10,
        source_kind=None,
        duration=1.0,
        hit_interval=0.05,
        damage=5.0,
    )
    second.apply_periodic_damage(
        source_id=30,
        source_kind=None,
        duration=1.0,
        hit_interval=0.05,
        damage=7.0,
    )
    expected = battle.clone()
    for entity in expected.entities.values():
        cast(Troop, entity).update_buff_component(0.05)

    runtime = TensorBattleRuntime.from_battles([battle], max_entities=8)
    phase = TensorRuntimeStatusPhase.from_battles(runtime, [battle])
    result = step_runtime_status_phase_(runtime, phase)
    assert result.supported_batch.tolist() == [True]

    valid = slice(0, int(runtime.events.count[0].item()))
    assert runtime.events.opcode[0, valid].tolist() == [
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.DEATH,
        RuntimeEventOpcode.DAMAGE,
    ]
    assert runtime.events.source_id[0, valid].tolist() == [20, 10, 10, 30]
    assert runtime.events.target_id[0, valid].tolist() == [
        first.id,
        first.id,
        first.id,
        second.id,
    ]
    candidate = battle.clone()
    phase.sync_to_battles(runtime, [candidate])
    for entity_id, oracle in expected.entities.items():
        actual = candidate.entities[entity_id]
        assert actual.hitpoints == oracle.hitpoints
        assert actual.is_alive is oracle.is_alive
        assert actual._periodic_damage_effects == oracle._periodic_damage_effects


def test_lifetime_damage_and_death_events_are_interleaved_in_id_order() -> None:
    battle = _empty_battle()
    first = _spawn_building(battle, "Cannon", 4.0)
    second = _spawn_building(battle, "Tesla", 8.0)
    first.hitpoints = second.hitpoints = 1.0
    expected = battle.clone()
    for entity in expected.entities.values():
        cast(Building, entity).update_hitpoint_component(0.05)

    runtime = TensorBattleRuntime.from_battles([battle], max_entities=8)
    phase = TensorRuntimeStatusPhase.from_battles(runtime, [battle])
    result = step_runtime_status_phase_(runtime, phase)
    assert result.died[0, :2].tolist() == [True, True]
    valid = slice(0, int(runtime.events.count[0].item()))
    assert runtime.events.opcode[0, valid].tolist() == [
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.DEATH,
        RuntimeEventOpcode.DAMAGE,
        RuntimeEventOpcode.DEATH,
    ]
    assert runtime.events.target_id[0, valid].tolist() == [
        first.id,
        first.id,
        second.id,
        second.id,
    ]


def test_mechanic_bearing_periodic_target_fails_closed_before_mutation() -> None:
    battle = _empty_battle()
    stats = battle.card_loader.get_card("DarkPrince")
    assert stats is not None
    target = cast(
        Troop,
        battle._spawn_entity(Troop, Position(5.0, 12.0), 0, stats),
    )
    target.apply_periodic_damage(
        source_id=7,
        source_kind=None,
        duration=1.0,
        hit_interval=0.05,
        damage=10.0,
    )
    runtime = TensorBattleRuntime.from_battles([battle], max_entities=8)
    phase = TensorRuntimeStatusPhase.from_battles(runtime, [battle])
    before_hp = runtime.battle.entity_hp.clone()
    before_status = runtime.status.periodic_remaining.clone()

    result = step_runtime_status_phase_(runtime, phase)
    assert result.supported_batch.tolist() == [False]
    assert torch.equal(runtime.battle.entity_hp, before_hp)
    assert torch.equal(runtime.status.periodic_remaining, before_status)
    assert runtime.events.count.tolist() == [0]


def test_event_overflow_fails_closed_before_any_phase_mutation() -> None:
    battle = _empty_battle()
    target = _spawn_troop(battle, 5.0)
    target.hitpoints = 5.0
    target.apply_periodic_damage(
        source_id=9,
        source_kind=None,
        duration=1.0,
        hit_interval=0.05,
        damage=5.0,
    )
    runtime = TensorBattleRuntime.from_battles(
        [battle], max_entities=4, event_capacity=1
    )
    phase = TensorRuntimeStatusPhase.from_battles(runtime, [battle])
    before_hp = runtime.battle.entity_hp.clone()
    before_status = runtime.status.periodic_remaining.clone()

    result = step_runtime_status_phase_(runtime, phase)
    assert result.supported_batch.tolist() == [False]
    assert torch.equal(runtime.battle.entity_hp, before_hp)
    assert torch.equal(runtime.status.periodic_remaining, before_status)
    assert runtime.events.count.tolist() == [0]


def test_supported_path_never_calls_python_entity_phase_methods(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = _empty_battle()
    building = _spawn_building(battle, "Cannon", 4.0)
    building.apply_stun(0.2)
    runtime = TensorBattleRuntime.from_battles([battle], max_entities=4)
    phase = TensorRuntimeStatusPhase.from_battles(runtime, [battle])

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("supported tensor phase called a Python entity method")

    monkeypatch.setattr(Building, "update_hitpoint_component", forbidden)
    monkeypatch.setattr(Entity, "update_status_effects", forbidden)
    result = step_runtime_status_phase_(runtime, phase)
    assert result.supported_batch.tolist() == [True]
