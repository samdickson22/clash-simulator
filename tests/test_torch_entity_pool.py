from __future__ import annotations

import random

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.torch_sim.entity_pool import INVALID_SLOT, TensorEntityPool


def _valid_rows(values: torch.Tensor, valid: torch.Tensor) -> list[list[int]]:
    return [
        [int(value) for value in row_values[row_valid].tolist()]
        for row_values, row_valid in zip(values, valid)
    ]


def _oracle_ids(battles: list[BattleState]) -> list[list[int]]:
    return [list(battle.entities) for battle in battles]


def _spawn_knights(battle: BattleState, count: int) -> list[int]:
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    spawned: list[int] = []
    for index in range(count):
        entity = battle._spawn_entity(
            Troop,
            Position(2.0 + index, 12.0),
            index % 2,
            stats,
        )
        spawned.append(entity.id)
    return spawned


def test_exact_integer_schema_and_monotonic_ids_with_reused_slots() -> None:
    pool = TensorEntityPool.empty(2, 6)
    first = pool.allocate(torch.tensor([4, 2]))
    assert pool.entity_id.dtype == torch.int64
    assert pool.next_entity_id.dtype == torch.int64
    assert pool.active.dtype == torch.bool
    assert _valid_rows(first.entity_ids, first.valid) == [[1, 2, 3, 4], [1, 2]]

    dead = torch.zeros_like(pool.active)
    dead[0, [0, 2]] = True
    dead[1, 0] = True
    removed = pool.cleanup(dead)
    assert _valid_rows(removed.entity_ids, removed.valid) == [[1, 3], [1]]

    second = pool.allocate(torch.tensor([2, 1]))
    assert _valid_rows(second.slots, second.valid) == [[0, 2], [0]]
    assert _valid_rows(second.entity_ids, second.valid) == [[5, 6], [3]]
    assert _valid_rows(pool.id_order().entity_ids, pool.id_order().valid) == [
        [2, 4, 5, 6],
        [2, 3],
    ]
    pool.assert_invariants()


def test_id_order_masks_and_vectorized_id_lookup_ignore_physical_order() -> None:
    pool = TensorEntityPool.from_id_sequences(
        [[2, 7, 11], [1, 4]], capacity=5, next_entity_ids=[20, 8]
    )
    pool.entity_id[0, [0, 1, 2]] = torch.tensor([11, 2, 7])
    selected = torch.zeros_like(pool.active)
    selected[0, [0, 2]] = True
    selected[1, 1] = True

    order = pool.id_order(selected)
    assert _valid_rows(order.entity_ids, order.valid) == [[7, 11], [4]]
    assert pool.slots_for_ids(torch.tensor([[2, 7, 19], [4, 1, 0]])).tolist() == [
        [1, 2, INVALID_SLOT],
        [1, 0, INVALID_SLOT],
    ]


def test_cleanup_with_spawns_preserves_parent_and_child_id_order() -> None:
    pool = TensorEntityPool.from_id_sequences(
        [[1, 2, 3, 4, 5], [8, 10, 12]],
        capacity=8,
        next_entity_ids=[6, 20],
    )
    # Scramble physical storage to prove parent visitation comes from IDs.
    pool.entity_id[0, :5] = torch.tensor([5, 2, 4, 1, 3])
    pool.entity_id[1, :3] = torch.tensor([12, 8, 10])
    dead = torch.zeros_like(pool.active)
    dead[0, [0, 1, 4]] = True  # IDs 5, 2, 3 -> parent order 2, 3, 5.
    dead[1, [0, 2]] = True  # IDs 12, 10 -> parent order 10, 12.
    spawn_counts = torch.zeros_like(pool.entity_id)
    spawn_counts[0, 1] = 2
    spawn_counts[0, 4] = 1
    spawn_counts[0, 0] = 2
    spawn_counts[1, 2] = 1
    spawn_counts[1, 0] = 2

    transition = pool.cleanup_with_spawns(dead, spawn_counts)
    assert _valid_rows(transition.removed.entity_ids, transition.removed.valid) == [
        [2, 3, 5],
        [10, 12],
    ]
    assert _valid_rows(transition.spawned.entity_ids, transition.spawned.valid) == [
        [6, 7, 8, 9, 10],
        [20, 21, 22],
    ]
    assert _valid_rows(transition.spawn_parent_ids, transition.spawned.valid) == [
        [2, 2, 3, 5, 5],
        [10, 12, 12],
    ]
    assert _valid_rows(pool.id_order().entity_ids, pool.id_order().valid) == [
        [1, 4, 6, 7, 8, 9, 10],
        [8, 20, 21, 22],
    ]
    pool.assert_invariants()


def test_compaction_plan_packs_by_id_and_exposes_payload_gather() -> None:
    pool = TensorEntityPool.empty(1, 6, next_entity_id=20)
    pool.active[0, [0, 2, 5]] = True
    pool.entity_id[0, [0, 2, 5]] = torch.tensor([9, 3, 14])
    payload = torch.tensor([[90, -1, 30, -1, -1, 140]])

    plan = pool.compact_by_id()
    gathered_payload = torch.gather(payload, 1, plan.source_slots.clamp_min(0))
    gathered_payload = torch.where(
        plan.valid, gathered_payload, torch.full_like(payload, -1)
    )
    assert pool.entity_id.tolist() == [[3, 9, 14, 0, 0, 0]]
    assert gathered_payload.tolist() == [[30, 90, 140, -1, -1, -1]]
    pool.assert_invariants()


def test_randomized_batched_allocation_and_cleanup_match_battle_state_oracle() -> None:
    rng = random.Random(147_991)
    battles = [BattleState() for _ in range(3)]
    capacity = 36
    pool = TensorEntityPool.from_id_sequences(
        _oracle_ids(battles),
        capacity=capacity,
        next_entity_ids=[battle.next_entity_id for battle in battles],
    )

    for _ in range(80):
        # Snapshot random non-tower deaths. BattleState cleanup enumerates the
        # insertion-ordered dict, which is ascending because IDs are monotonic.
        dead = torch.zeros_like(pool.active)
        expected_removed: list[list[int]] = []
        for batch_index, battle in enumerate(battles):
            candidates = list(battle.entities)[6:]
            remove_count = rng.randint(0, min(3, len(candidates)))
            remove_ids = sorted(rng.sample(candidates, remove_count))
            expected_removed.append(remove_ids)
            for entity_id in remove_ids:
                battle.entities[entity_id].is_alive = False
            if remove_ids:
                lookup = pool.slots_for_ids(
                    torch.tensor(
                        [[entity_id] for entity_id in remove_ids], dtype=torch.int64
                    ).T.expand(3, -1)
                )[batch_index]
                dead[batch_index, lookup] = True

        removed = pool.cleanup(dead)
        assert _valid_rows(removed.entity_ids, removed.valid) == expected_removed
        for battle in battles:
            battle._cleanup_dead_entities()

        free = capacity - pool.active.sum(dim=1, dtype=torch.int64)
        counts = torch.tensor(
            [rng.randint(0, min(3, int(available))) for available in free.tolist()],
            dtype=torch.int64,
        )
        allocated = pool.allocate(counts)
        expected_allocated = [
            _spawn_knights(battle, int(count))
            for battle, count in zip(battles, counts.tolist())
        ]

        assert _valid_rows(allocated.entity_ids, allocated.valid) == expected_allocated
        order = pool.id_order()
        assert _valid_rows(order.entity_ids, order.valid) == _oracle_ids(battles)
        assert pool.next_entity_id.tolist() == [
            battle.next_entity_id for battle in battles
        ]
        pool.assert_invariants()


def test_rejects_capacity_overflow_without_partial_mutation() -> None:
    pool = TensorEntityPool.empty(2, 3)
    pool.allocate(torch.tensor([2, 3]))
    before = pool.clone()
    with pytest.raises(OverflowError, match="capacity exhausted"):
        pool.allocate(torch.tensor([2, 0]))
    assert torch.equal(pool.active, before.active)
    assert torch.equal(pool.entity_id, before.entity_id)
    assert torch.equal(pool.next_entity_id, before.next_entity_id)
