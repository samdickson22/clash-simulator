from __future__ import annotations

import random
from typing import cast

import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.torch_sim.diagnostics import battle_snapshot, first_divergence
from clasher.torch_sim.runtime_state import (
    RuntimeEventOpcode,
    TensorBattleRuntime,
    TensorRuntimeEvents,
    TickPhase,
)


def _spawn_randomized_battles() -> list[BattleState]:
    rng = random.Random(619_441)
    battles = [BattleState() for _ in range(3)]
    for battle_index, battle in enumerate(battles):
        stats = battle.card_loader.get_card("Knight")
        assert stats is not None
        spawned: list[Troop] = []
        for entity_index in range(7):
            entity = cast(
                Troop,
                battle._spawn_entity(
                    Troop,
                    Position(
                        round(rng.uniform(1.0, 17.0), 3),
                        round(rng.uniform(2.0, 30.0), 3),
                    ),
                    entity_index % 2,
                    stats,
                ),
            )
            entity.hitpoints = float(rng.randint(1, int(entity.max_hitpoints)))
            entity.apply_stun(rng.choice((0.05, 0.2, 0.75)))
            entity.apply_slow(
                rng.choice((0.1, 0.4)),
                0.7,
                attack_speed_multiplier=0.8,
                spawn_speed_multiplier=0.9,
            )
            entity.apply_haste(rng.choice((0.2, 0.5)), 1.2, 1.3, 1.1)
            entity.accumulate_movement_vector_units(
                rng.randint(-120, 120), rng.randint(-120, 120)
            )
            spawned.append(entity)
        for entity_index, entity in enumerate(spawned):
            entity.target_id = spawned[(entity_index + 1) % len(spawned)].id
        battle.time = battle_index * 0.05
        battle.tick = battle_index
    return battles


def test_composed_state_owns_one_identity_tensor_and_exact_boundary_roundtrip() -> None:
    battles = _spawn_randomized_battles()
    expected = [battle_snapshot(battle) for battle in battles]
    runtime = TensorBattleRuntime.from_battles(
        battles, max_entities=32, event_capacity=64
    )
    runtime.assert_invariants()

    assert runtime.entity_pool.entity_id is runtime.battle.entity_id
    assert runtime.entity_pool.active is not runtime.battle.entity_active
    assert runtime.catalog.names[0] == ""
    assert runtime.card_catalog_index.shape == (len(runtime.battle.card_names),)

    candidates = [battle.clone() for battle in battles]
    runtime.sync_to_battles(candidates)
    for snapshot, candidate in zip(expected, candidates):
        assert first_divergence(snapshot, battle_snapshot(candidate)) is None


def test_clone_and_multi_fork_are_independent_but_share_immutable_catalog() -> None:
    runtime = TensorBattleRuntime.from_battles(
        _spawn_randomized_battles(), max_entities=32
    )
    cloned = runtime.clone()
    forked = runtime.fork([2, 0], copies=2)

    assert cloned.catalog is runtime.catalog
    assert forked.catalog is runtime.catalog
    assert forked.batch_size == 4
    assert forked.battle.tick.tolist() == [2, 2, 0, 0]
    assert forked.entity_pool.entity_id is forked.battle.entity_id

    cloned.battle.tick.add_(100)
    cloned.status.stun_timer.add_(2.0)
    cloned.phases.target_slot.fill_(-1)
    cloned.entity_pool.next_entity_id.add_(50)
    cloned.events.count.add_(1)
    assert not torch.equal(cloned.battle.tick, runtime.battle.tick)
    assert not torch.equal(cloned.status.stun_timer, runtime.status.stun_timer)
    assert not torch.equal(cloned.phases.target_slot, runtime.phases.target_slot)
    assert not torch.equal(
        cloned.entity_pool.next_entity_id, runtime.entity_pool.next_entity_id
    )
    assert not torch.equal(cloned.events.count, runtime.events.count)


def test_support_and_dirty_masks_are_per_battle_and_per_phase() -> None:
    runtime = TensorBattleRuntime.from_battles(
        _spawn_randomized_battles(), max_entities=32
    )
    combat_rows = torch.tensor([False, True, False])
    runtime.mark_unsupported(combat_rows, phase=TickPhase.COMBAT)
    runtime.mark_dirty(combat_rows, phase=TickPhase.COMBAT)

    assert runtime.supported.tolist() == [True, False, True]
    assert runtime.dirty.tolist() == [False, True, False]
    assert runtime.phases.supported[:, TickPhase.COMBAT].tolist() == [
        True,
        False,
        True,
    ]
    assert runtime.phases.dirty[:, TickPhase.COMBAT].tolist() == [
        False,
        True,
        False,
    ]
    runtime.clear_dirty(combat_rows)
    assert not runtime.dirty.any()
    assert not runtime.phases.dirty.any()


def test_event_buffers_preserve_left_to_right_order_and_row_local_sequences() -> None:
    events = TensorRuntimeEvents.empty(3, 8)
    first_valid = torch.tensor(
        [[True, False, True], [False, True, False], [True, True, True]]
    )
    sources = torch.tensor([[10, 11, 12], [20, 21, 22], [30, 31, 32]])
    events.append(
        phase=TickPhase.COMBAT,
        opcode=RuntimeEventOpcode.DAMAGE,
        valid=first_valid,
        source_id=sources,
        amount=torch.tensor([[1.0, 2.0, 3.0]]),
    )
    events.append(
        phase=TickPhase.CLEANUP_AND_SPAWNS,
        opcode=RuntimeEventOpcode.SPAWN,
        valid=torch.tensor([[True], [True], [False]]),
        source_id=torch.tensor([[99], [98], [97]]),
    )

    assert events.count.tolist() == [3, 2, 3]
    assert events.source_id[0, :3].tolist() == [10, 12, 99]
    assert events.source_id[1, :2].tolist() == [21, 98]
    assert events.source_id[2, :3].tolist() == [30, 31, 32]
    assert events.sequence[0, :3].tolist() == [0, 1, 2]
    assert events.sequence[1, :2].tolist() == [0, 1]
    assert events.sequence[2, :3].tolist() == [0, 1, 2]


def test_event_append_overflow_is_fail_closed_before_mutation() -> None:
    events = TensorRuntimeEvents.empty(2, 2)
    events.append(
        phase=TickPhase.COMMANDS,
        opcode=RuntimeEventOpcode.COMMAND,
        valid=torch.tensor([[True], [False]]),
        source_id=7,
    )
    before = events.count.clone(), events.source_id.clone()
    try:
        events.append(
            phase=TickPhase.OBJECTS,
            opcode=RuntimeEventOpcode.AREA,
            valid=torch.ones((2, 2), dtype=torch.bool),
        )
    except OverflowError:
        pass
    else:
        raise AssertionError("expected event capacity failure")
    assert torch.equal(events.count, before[0])
    assert torch.equal(events.source_id, before[1])
