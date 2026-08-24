from __future__ import annotations

import random
from dataclasses import fields
from typing import Any

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building, Projectile, TimedExplosive, Troop
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.resident_engine import (
    ResidentUnsupportedReason,
    TensorResidentEngine,
)
from clasher.torch_sim.resident_workspace import TensorResidentWorkspace
from clasher.torch_sim.runtime_state import RuntimeEventOpcode, TickPhase


def _spawn_ready(
    battle: BattleState,
    entity_type: type[Building | Troop],
    card_name: str,
    entity_id: int,
    player: int,
    position: Position,
) -> Building | Troop:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    entity = battle._spawn_entity(entity_type, position, player, stats)
    assert isinstance(entity, (Building, Troop))
    assert entity.id == entity_id
    entity.deploy_delay_remaining = 0.0
    entity.placement_pending = False
    entity._spawn_hook_pending = False
    entity._spawn_hook_fired = True
    entity.attack_cooldown = 10.0
    entity.stun_timer = 100.0
    return entity


def _projectile_before_bomb_boundary() -> tuple[BattleState, Building]:
    """Return ID4 projectile live while BombTower ID1 awaits cleanup."""

    battle = BattleState(fast_path=False, rng=random.Random(8_240_501))
    battle.entities.clear()
    battle.next_entity_id = 1
    source = _spawn_ready(battle, Building, "BombTower", 1, 0, Position(9.0, 10.0))
    assert isinstance(source, Building)
    bomb_target = _spawn_ready(battle, Troop, "Knight", 2, 1, Position(9.0, 12.0))
    bomb_target.hitpoints = 100.0
    shooter = _spawn_ready(battle, Troop, "Musketeer", 3, 1, Position(9.0, 17.0))
    shooter._create_projectile(source, battle)
    assert battle.next_entity_id == 5
    projectile = battle.entities[4]
    assert isinstance(projectile, Projectile)
    return battle, source


def _advance_scalar_object_phase(battle: BattleState) -> None:
    ids = set(battle.entities)
    battle._defer_projectile_impacts = True
    battle._run_object_phase(battle.dt, ids, ids)
    battle._defer_projectile_impacts = False
    battle._resolve_pending_projectile_impacts()
    battle._cleanup_dead_entities()


def _kill_source_after_scalar_object_phase(
    battle: BattleState, source: Building
) -> None:
    source.take_damage(source.hitpoints)
    battle._cleanup_dead_entities()
    assert 1 not in battle.entities
    assert battle.next_entity_id == 6
    bomb = battle.entities[5]
    assert isinstance(bomb, TimedExplosive)
    assert bomb.time_alive == 0.0


def _kill_tensor_source(engine: TensorResidentEngine) -> None:
    source_slot = engine.runtime.battle.entity_id[0].tolist().index(1)
    engine.runtime.battle.entity_active[0, source_slot] = False
    engine.runtime.battle.entity_hp[0, source_slot] = 0.0
    engine.combat.alive[0, source_slot] = False
    engine.combat.hp[0, source_slot] = 0.0


def _event_rows(engine: TensorResidentEngine) -> list[tuple[int, int, int, int]]:
    events = engine.runtime.events
    count = int(events.count[0])
    return [
        (
            int(events.phase[0, index]),
            int(events.opcode[0, index]),
            int(events.source_id[0, index]),
            int(events.target_id[0, index]),
        )
        for index in range(count)
    ]


def _assert_object_state_matches_scalar(
    engine: TensorResidentEngine, oracle: BattleState
) -> None:
    generic = engine.objects.objects
    generic_ids = generic.object_id[0, generic.allocated[0]].tolist()
    scalar_generic = sorted(
        entity.id
        for entity in oracle.entities.values()
        if isinstance(entity, Projectile) and entity.is_alive
    )
    assert generic_ids == scalar_generic
    for object_id in scalar_generic:
        tensor_slot = generic.object_id[0].tolist().index(object_id)
        scalar = oracle.entities[object_id]
        assert generic.x_units[0, tensor_slot].item() == round(
            scalar.position.x * 1_000
        )
        assert generic.y_units[0, tensor_slot].item() == round(
            scalar.position.y * 1_000
        )

    timed = engine.terminal_pipeline.state.objects
    timed_ids = timed.object_id[0, timed.allocated[0]].tolist()
    scalar_timed = sorted(
        entity.id
        for entity in oracle.entities.values()
        if type(entity).__name__ == "TimedExplosive" and entity.is_alive
    )
    assert timed_ids == scalar_timed
    for object_id in scalar_timed:
        tensor_slot = timed.object_id[0].tolist().index(object_id)
        scalar = oracle.entities[object_id]
        assert isinstance(scalar, TimedExplosive)
        assert timed.age_ms[0, tensor_slot].item() == round(scalar.time_alive * 1_000)

    tensor_ids = engine.runtime.battle.entity_id[0].tolist()
    tensor_characters = {
        entity_id
        for slot, entity_id in enumerate(tensor_ids)
        if entity_id
        and engine.runtime.entity_pool.active[0, slot]
        and engine.runtime.battle.entity_kind[0, slot].item() in {0, 1}
    }
    scalar_characters = {
        entity.id
        for entity in oracle.entities.values()
        if isinstance(entity, (Building, Troop)) and entity.is_alive
    }
    assert tensor_characters == scalar_characters
    for entity_id in scalar_characters:
        tensor_slot = tensor_ids.index(entity_id)
        assert engine.runtime.battle.entity_hp[0, tensor_slot].item() == (
            oracle.entities[entity_id].hitpoints
        )


@pytest.mark.parametrize("device", ("cpu", "cuda"))
def test_bombtower_older_projectile_and_timed_bomb_full_lifecycle(
    device: str,
) -> None:
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    boundary, _ = _projectile_before_bomb_boundary()
    oracle = boundary.clone()
    oracle_source = oracle.entities[1]
    assert isinstance(oracle_source, Building)
    engine = TensorResidentEngine.from_battles(
        [boundary],
        device=device,
        max_entities=12,
        max_objects=8,
        event_capacity=128,
    )
    _kill_tensor_source(engine)

    # The older generic object owns this object phase. Cleanup creates ID5 only
    # afterward, so its retained timer begins at zero.
    _advance_scalar_object_phase(oracle)
    _kill_source_after_scalar_object_phase(oracle, oracle_source)
    result = engine.step(
        torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=device),
        player_order=torch.tensor([[0, 1]], device=device),
    )

    assert result.committed.tolist() == [True]
    assert engine.runtime.entity_pool.next_entity_id.item() == 6
    assert engine.terminal_pipeline.state.objects.age_ms[
        engine.terminal_pipeline.state.objects.allocated
    ].tolist() == [0]
    assert _event_rows(engine)[-1] == (
        int(TickPhase.CLEANUP_AND_SPAWNS),
        int(RuntimeEventOpcode.SPAWN),
        1,
        5,
    )
    _assert_object_state_matches_scalar(engine, oracle)
    assert engine.runtime.battle.rng.python_state(0) == oracle.rng.getstate()

    projectile_impact_update = None
    bomb_explosion_update = None
    for update_index in range(60):
        engine.runtime.events.clear()
        _advance_scalar_object_phase(oracle)
        result = engine.step(
            torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=device),
            player_order=torch.tensor([[0, 1]], device=device),
        )
        assert result.committed.tolist() == [True], update_index
        rows = _event_rows(engine)
        if any(
            opcode == int(RuntimeEventOpcode.DEATH) and target == 4
            for _, opcode, _, target in rows
        ):
            assert rows == [
                (
                    int(TickPhase.COMBAT),
                    int(RuntimeEventOpcode.DAMAGE),
                    0,
                    4,
                ),
                (
                    int(TickPhase.COMBAT),
                    int(RuntimeEventOpcode.DEATH),
                    0,
                    4,
                ),
            ]
            # ID4 consumed one update in the creation-boundary object phase.
            projectile_impact_update = update_index + 2
        if any(
            opcode == int(RuntimeEventOpcode.DAMAGE) and source == 5
            for _, opcode, source, _ in rows
        ):
            bomb_explosion_update = update_index
        assert not any(
            opcode == int(RuntimeEventOpcode.DAMAGE) and target == 1
            for _, opcode, _, target in rows
        )
        _assert_object_state_matches_scalar(engine, oracle)
        assert engine.runtime.battle.rng.python_state(0) == oracle.rng.getstate()

    assert projectile_impact_update == 7
    assert bomb_explosion_update == 59
    assert 2 not in engine.runtime.battle.entity_id[0].tolist()
    assert 5 not in engine.runtime.battle.entity_id[0].tolist()


def _tensor_snapshot(engine: TensorResidentEngine) -> dict[str, torch.Tensor]:
    snapshot: dict[str, torch.Tensor] = {}
    owners: tuple[tuple[str, Any], ...] = (
        ("battle", engine.runtime.battle),
        ("pool", engine.runtime.entity_pool),
        ("events", engine.runtime.events),
        ("objects", engine.objects.objects),
        ("timed", engine.terminal_pipeline.state.objects),
    )
    for prefix, owner in owners:
        for descriptor in fields(owner):
            value = getattr(owner, descriptor.name)
            if isinstance(value, torch.Tensor):
                snapshot[f"{prefix}.{descriptor.name}"] = value.clone()
    return snapshot


def test_bombtower_new_generic_allocation_while_timed_live_rolls_back() -> None:
    battle, _ = _projectile_before_bomb_boundary()
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=12, max_objects=8, event_capacity=128
    )
    _kill_tensor_source(engine)
    first = engine.step(player_order=torch.tensor([[0, 1]]))
    assert first.committed.item()
    assert engine.terminal_pipeline.state.objects.allocated.any()
    shooter_slot = engine.runtime.battle.entity_id[0].tolist().index(3)
    target_slot = engine.runtime.battle.entity_id[0].tolist().index(2)
    engine.runtime.battle.entity_player[0, target_slot] = 0
    engine.runtime.battle.entity_y_units[0, shooter_slot] = 14_000
    engine.combat.y_units[0, shooter_slot] = 14_000
    engine.movement.position_units[0, shooter_slot, 1] = 14_000
    engine.runtime.status.stun_timer[0, shooter_slot] = 0.0
    engine.combat.stunned[0, shooter_slot] = False
    engine.combat.attack_cooldown[0, shooter_slot] = 0.0
    engine.combat.target_slot[0, shooter_slot] = target_slot
    engine.runtime.phases.target_slot[0, shooter_slot] = target_slot
    engine.combat_target_entity_id[0, shooter_slot] = 2
    before = _tensor_snapshot(engine)

    result = engine.step(player_order=torch.tensor([[0, 1]]))

    assert not result.committed.item()
    assert result.preflight.supported.item()
    after = _tensor_snapshot(engine)
    assert before.keys() == after.keys()
    for name, expected in before.items():
        torch.testing.assert_close(after[name], expected, rtol=0, atol=0, msg=name)


def _replace_generic_id_(
    engine: TensorResidentEngine, *, row: int, replacement: int
) -> None:
    generic = engine.objects.objects
    object_slot = int(torch.where(generic.allocated[row])[0][0])
    old_id = int(generic.object_id[row, object_slot])
    entity_slot = engine.runtime.battle.entity_id[row].tolist().index(old_id)
    generic.object_id[row, object_slot] = replacement
    engine.runtime.entity_pool.entity_id[row, entity_slot] = replacement
    engine.runtime.battle.entity_id[row, entity_slot] = replacement
    engine.runtime.entity_pool.next_entity_id[row] = replacement + 1


def test_bombtower_newer_generic_id_fails_closed_before_mutation() -> None:
    battle, _ = _projectile_before_bomb_boundary()
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=12, max_objects=8, event_capacity=128
    )
    _kill_tensor_source(engine)
    assert engine.step(player_order=torch.tensor([[0, 1]])).committed.item()
    engine.runtime.events.clear()
    _replace_generic_id_(engine, row=0, replacement=6)
    before = _tensor_snapshot(engine)

    preflight = engine.preflight()
    result = engine.step(player_order=torch.tensor([[0, 1]]))

    assert not preflight.supported.item()
    assert preflight.reason_code.item() == int(ResidentUnsupportedReason.OBJECT_PHASE)
    assert not result.committed.item()
    after = _tensor_snapshot(engine)
    for name, expected in before.items():
        torch.testing.assert_close(after[name], expected, rtol=0, atol=0, msg=name)


def test_bombtower_timed_creation_event_capacity_failure_is_atomic() -> None:
    battle, _ = _projectile_before_bomb_boundary()
    engine = TensorResidentEngine.from_battles(
        [battle], max_entities=12, max_objects=8, event_capacity=1
    )
    _kill_tensor_source(engine)
    engine.runtime.events.count.fill_(engine.runtime.events.capacity)
    before = _tensor_snapshot(engine)

    result = engine.step(player_order=torch.tensor([[0, 1]]))

    assert not result.committed.item()
    after = _tensor_snapshot(engine)
    for name, expected in before.items():
        torch.testing.assert_close(after[name], expected, rtol=0, atol=0, msg=name)


def _row_snapshot(engine: TensorResidentEngine, row: int) -> dict[str, torch.Tensor]:
    return {
        name: value[row].clone() for name, value in _tensor_snapshot(engine).items()
    }


def test_bombtower_workspace_mixed_safe_and_unsafe_rows_commit_atomically() -> None:
    first, _ = _projectile_before_bomb_boundary()
    second, _ = _projectile_before_bomb_boundary()
    engine = TensorResidentEngine.from_battles(
        [first, second], max_entities=12, max_objects=8, event_capacity=128
    )
    for row in range(2):
        source_slot = engine.runtime.battle.entity_id[row].tolist().index(1)
        engine.runtime.battle.entity_active[row, source_slot] = False
        engine.runtime.battle.entity_hp[row, source_slot] = 0.0
        engine.combat.alive[row, source_slot] = False
        engine.combat.hp[row, source_slot] = 0.0
    workspace = TensorResidentWorkspace(engine)
    order = torch.tensor([[0, 1], [0, 1]])
    assert workspace.step(player_order=order).committed.tolist() == [True, True]
    engine.runtime.events.clear()
    _replace_generic_id_(engine, row=1, replacement=6)
    unsafe_before = _row_snapshot(engine, 1)
    safe_age_before = int(
        engine.terminal_pipeline.state.objects.age_ms[
            0, engine.terminal_pipeline.state.objects.allocated[0]
        ][0]
    )

    result = workspace.step(player_order=order)

    assert result.committed.tolist() == [True, False]
    assert (
        int(
            engine.terminal_pipeline.state.objects.age_ms[
                0, engine.terminal_pipeline.state.objects.allocated[0]
            ][0]
        )
        == safe_age_before + 50
    )
    unsafe_after = _row_snapshot(engine, 1)
    for name, expected in unsafe_before.items():
        torch.testing.assert_close(
            unsafe_after[name], expected, rtol=0, atol=0, msg=name
        )
