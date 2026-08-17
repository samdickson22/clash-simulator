"""Stable entity identity and slot allocation for batched tensor battles.

The Python oracle stores entities in insertion-ordered dictionaries and gives
every entity a monotonically increasing integer ID.  IDs are never recycled;
all component and cleanup passes consequently observe ascending ID order.

This module separates that public identity from bounded tensor storage.  A
freed physical slot may be reused immediately, but iteration is always derived
from ``entity_id`` rather than slot position.  All mutation kernels operate on
whole tensors; Python iteration is only needed by optional boundary adapters.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import torch

EMPTY_ENTITY_ID = 0
INVALID_SLOT = -1
_SORT_SENTINEL = torch.iinfo(torch.int64).max


@dataclass(frozen=True)
class EntitySelection:
    """Padded, ID-ordered entity selection for every battle in a batch."""

    slots: torch.Tensor
    entity_ids: torch.Tensor
    valid: torch.Tensor

    @property
    def counts(self) -> torch.Tensor:
        return self.valid.sum(dim=1, dtype=torch.int64)


@dataclass(frozen=True)
class EntityAllocation(EntitySelection):
    """New identities in allocation order, padded to pool capacity."""


@dataclass(frozen=True)
class CleanupSpawnTransition:
    """Result of the oracle's spawn-before-remove death cleanup transaction."""

    removed: EntitySelection
    spawned: EntityAllocation
    spawn_parent_ids: torch.Tensor
    spawn_parent_slots: torch.Tensor


@dataclass(frozen=True)
class CompactionPlan:
    """ID-order gather plan for compacting every entity SoA field.

    ``source_slots`` is indexed by destination slot.  Callers owning more
    entity fields must gather them with this plan before or together with
    :meth:`TensorEntityPool.compact_by_id`.
    """

    source_slots: torch.Tensor
    destination_slots: torch.Tensor
    valid: torch.Tensor


@dataclass
class TensorEntityPool:
    """Bounded batched pool with oracle-compatible stable entity identities."""

    next_entity_id: torch.Tensor
    active: torch.Tensor
    entity_id: torch.Tensor

    @property
    def device(self) -> torch.device:
        return self.entity_id.device

    @property
    def batch_size(self) -> int:
        return int(self.entity_id.shape[0])

    @property
    def capacity(self) -> int:
        return int(self.entity_id.shape[1])

    @classmethod
    def empty(
        cls,
        batch_size: int,
        capacity: int,
        *,
        next_entity_id: int | torch.Tensor = 1,
        device: str | torch.device = "cpu",
    ) -> TensorEntityPool:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if capacity < 1:
            raise ValueError("capacity must be positive")
        torch_device = torch.device(device)
        if isinstance(next_entity_id, torch.Tensor):
            next_ids = next_entity_id.to(device=torch_device, dtype=torch.int64).clone()
            if next_ids.shape != (batch_size,):
                raise ValueError("next_entity_id tensor must have shape [batch_size]")
        else:
            next_ids = torch.full(
                (batch_size,),
                int(next_entity_id),
                dtype=torch.int64,
                device=torch_device,
            )
        if bool((next_ids < 1).any().item()):
            raise ValueError("next_entity_id values must be positive")
        return cls(
            next_entity_id=next_ids,
            active=torch.zeros(
                (batch_size, capacity), dtype=torch.bool, device=torch_device
            ),
            entity_id=torch.zeros(
                (batch_size, capacity), dtype=torch.int64, device=torch_device
            ),
        )

    @classmethod
    def from_id_sequences(
        cls,
        entity_ids: Sequence[Sequence[int]],
        *,
        capacity: int,
        next_entity_ids: Sequence[int] | None = None,
        device: str | torch.device = "cpu",
    ) -> TensorEntityPool:
        """Construct from oracle state at the Python/tensor boundary.

        The adapter deliberately validates the oracle invariants.  Production
        tick/allocation paths use the tensor methods below and do not call this
        object-by-object adapter.
        """

        pool = cls.empty(len(entity_ids), capacity, device=device)
        inferred_next: list[int] = []
        for batch_index, ids in enumerate(entity_ids):
            ids_tuple = tuple(int(entity_id) for entity_id in ids)
            if len(ids_tuple) > capacity:
                raise ValueError("entity sequence exceeds pool capacity")
            if any(entity_id <= 0 for entity_id in ids_tuple):
                raise ValueError("entity IDs must be positive")
            if tuple(sorted(ids_tuple)) != ids_tuple or len(set(ids_tuple)) != len(
                ids_tuple
            ):
                raise ValueError("oracle entity IDs must be unique and ascending")
            count = len(ids_tuple)
            if count:
                pool.active[batch_index, :count] = True
                pool.entity_id[batch_index, :count] = torch.tensor(
                    ids_tuple, dtype=torch.int64, device=pool.device
                )
            inferred_next.append(ids_tuple[-1] + 1 if ids_tuple else 1)

        supplied = (
            inferred_next
            if next_entity_ids is None
            else [int(v) for v in next_entity_ids]
        )
        if len(supplied) != pool.batch_size:
            raise ValueError("next_entity_ids must have one value per battle")
        next_ids = torch.tensor(supplied, dtype=torch.int64, device=pool.device)
        maximum = pool.entity_id.max(dim=1).values
        if bool((next_ids <= maximum).any().item()):
            raise ValueError("next entity ID must exceed every live entity ID")
        pool.next_entity_id.copy_(next_ids)
        pool.assert_invariants()
        return pool

    def clone(self) -> TensorEntityPool:
        return TensorEntityPool(
            next_entity_id=self.next_entity_id.clone(),
            active=self.active.clone(),
            entity_id=self.entity_id.clone(),
        )

    def assert_invariants(self) -> None:
        if self.next_entity_id.dtype != torch.int64:
            raise TypeError("next_entity_id must use torch.int64")
        if self.active.dtype != torch.bool:
            raise TypeError("active must use torch.bool")
        if self.entity_id.dtype != torch.int64:
            raise TypeError("entity_id must use torch.int64")
        if self.active.shape != self.entity_id.shape:
            raise ValueError("active and entity_id shapes differ")
        if self.next_entity_id.shape != (self.batch_size,):
            raise ValueError("next_entity_id shape differs from batch size")
        if bool((self.entity_id[~self.active] != EMPTY_ENTITY_ID).any().item()):
            raise ValueError("inactive slots must contain the empty entity ID")
        if bool((self.entity_id[self.active] <= EMPTY_ENTITY_ID).any().item()):
            raise ValueError("active slots must contain positive entity IDs")
        if bool((self.entity_id >= self.next_entity_id[:, None]).any().item()):
            raise ValueError("live IDs must be lower than next_entity_id")
        ordered = self.id_order()
        duplicate = ordered.valid[:, 1:] & (
            ordered.entity_ids[:, 1:] == ordered.entity_ids[:, :-1]
        )
        if bool(duplicate.any().item()):
            raise ValueError("entity IDs must be unique within a battle")

    def _validate_batch_matrix(self, tensor: torch.Tensor, name: str) -> torch.Tensor:
        value = tensor.to(device=self.device)
        if value.shape != self.active.shape:
            raise ValueError(f"{name} must have shape [batch_size, capacity]")
        return value

    def _validate_counts(self, counts: torch.Tensor) -> torch.Tensor:
        value = counts.to(device=self.device, dtype=torch.int64)
        if value.shape != (self.batch_size,):
            raise ValueError("counts must have shape [batch_size]")
        if bool((value < 0).any().item()):
            raise ValueError("allocation counts cannot be negative")
        if bool((value > self.capacity).any().item()):
            raise OverflowError("one allocation request exceeds pool capacity")
        return value

    def _selection(self, mask: torch.Tensor) -> EntitySelection:
        selected = (
            self._validate_batch_matrix(mask, "mask").to(dtype=torch.bool) & self.active
        )
        keys = torch.where(
            selected,
            self.entity_id,
            torch.full_like(self.entity_id, _SORT_SENTINEL),
        )
        order = torch.argsort(keys, dim=1, stable=True)
        ordered_ids = torch.gather(self.entity_id, 1, order)
        valid = torch.gather(selected, 1, order)
        slots = torch.where(valid, order, torch.full_like(order, INVALID_SLOT))
        return EntitySelection(
            slots=slots,
            entity_ids=torch.where(valid, ordered_ids, torch.zeros_like(ordered_ids)),
            valid=valid,
        )

    def id_order(self, mask: torch.Tensor | None = None) -> EntitySelection:
        """Return a deterministic padded pass order matching the oracle."""

        selected = self.active if mask is None else mask
        return self._selection(selected)

    def slots_for_ids(self, ids: torch.Tensor) -> torch.Tensor:
        """Resolve padded IDs to physical slots without Python lookup loops."""

        requested = ids.to(device=self.device, dtype=torch.int64)
        if requested.ndim != 2 or requested.shape[0] != self.batch_size:
            raise ValueError("ids must have shape [batch_size, requests]")
        matches = (
            (requested[:, :, None] == self.entity_id[:, None, :])
            & self.active[:, None, :]
            & (requested[:, :, None] > 0)
        )
        found = matches.any(dim=2)
        slots = matches.to(dtype=torch.int64).argmax(dim=2)
        return torch.where(found, slots, torch.full_like(slots, INVALID_SLOT))

    def allocate(self, counts: torch.Tensor) -> EntityAllocation:
        """Allocate sequential oracle IDs into the lowest available slots."""

        request_counts = self._validate_counts(counts)
        available = ~self.active
        available_counts = available.sum(dim=1, dtype=torch.int64)
        if bool((request_counts > available_counts).any().item()):
            raise OverflowError("entity pool capacity exhausted")

        slot_numbers = torch.arange(
            self.capacity, dtype=torch.int64, device=self.device
        )
        available_keys = torch.where(
            available,
            slot_numbers[None, :],
            torch.full_like(self.entity_id, self.capacity),
        )
        slots = torch.sort(available_keys, dim=1).values
        request_index = slot_numbers[None, :].expand(self.batch_size, -1)
        valid = request_index < request_counts[:, None]
        ids = self.next_entity_id[:, None] + request_index

        batch_index = torch.arange(
            self.batch_size, dtype=torch.int64, device=self.device
        )[:, None].expand_as(slots)
        selected_batches = batch_index[valid]
        selected_slots = slots[valid]
        self.active[selected_batches, selected_slots] = True
        self.entity_id[selected_batches, selected_slots] = ids[valid]
        self.next_entity_id.add_(request_counts)

        return EntityAllocation(
            slots=torch.where(valid, slots, torch.full_like(slots, INVALID_SLOT)),
            entity_ids=torch.where(valid, ids, torch.zeros_like(ids)),
            valid=valid,
        )

    def cleanup(self, dead: torch.Tensor) -> EntitySelection:
        """Remove a start-of-cleanup dead snapshot in ascending ID order."""

        dead_mask = (
            self._validate_batch_matrix(dead, "dead").to(dtype=torch.bool) & self.active
        )
        removed = self._selection(dead_mask)
        self.active.masked_fill_(dead_mask, False)
        self.entity_id.masked_fill_(dead_mask, EMPTY_ENTITY_ID)
        return removed

    def cleanup_with_spawns(
        self,
        dead: torch.Tensor,
        spawn_counts_by_slot: torch.Tensor,
    ) -> CleanupSpawnTransition:
        """Apply death children and cleanup with the oracle's allocation order.

        The oracle snapshots dead entities, visits those parents in ascending
        ID order, allocates all of a parent's children, and only then removes
        every dead parent.  This atomic tensor transaction preserves the same
        child IDs and parent mapping.  Reclaimed dead slots may hold children
        in the final representation; physical slots are not observable.
        """

        dead_mask = (
            self._validate_batch_matrix(dead, "dead").to(dtype=torch.bool) & self.active
        )
        spawn_counts = self._validate_batch_matrix(
            spawn_counts_by_slot, "spawn_counts_by_slot"
        ).to(dtype=torch.int64)
        if bool((spawn_counts < 0).any().item()):
            raise ValueError("spawn counts cannot be negative")
        if bool((spawn_counts.masked_select(~dead_mask) != 0).any().item()):
            raise ValueError("spawn counts may only be attached to dead active parents")

        removed = self._selection(dead_mask)
        ordered_parent_counts = torch.gather(
            spawn_counts, 1, removed.slots.clamp_min(0)
        )
        ordered_parent_counts = torch.where(
            removed.valid,
            ordered_parent_counts,
            torch.zeros_like(ordered_parent_counts),
        )
        total_spawns = ordered_parent_counts.sum(dim=1, dtype=torch.int64)
        live_after = self.active.sum(dim=1, dtype=torch.int64) - removed.counts
        if bool((live_after + total_spawns > self.capacity).any().item()):
            raise OverflowError("death spawns exceed entity pool capacity")

        request_index = torch.arange(
            self.capacity, dtype=torch.int64, device=self.device
        )[None, :].expand(self.batch_size, -1)
        cumulative = ordered_parent_counts.cumsum(dim=1)
        belongs = request_index[:, :, None] < cumulative[:, None, :]
        parent_ordinal = belongs.to(dtype=torch.int64).argmax(dim=2)
        spawn_valid = request_index < total_spawns[:, None]
        parent_ids = torch.gather(removed.entity_ids, 1, parent_ordinal)
        parent_slots = torch.gather(removed.slots, 1, parent_ordinal)
        parent_ids = torch.where(spawn_valid, parent_ids, torch.zeros_like(parent_ids))
        parent_slots = torch.where(
            spawn_valid, parent_slots, torch.full_like(parent_slots, INVALID_SLOT)
        )

        self.active.masked_fill_(dead_mask, False)
        self.entity_id.masked_fill_(dead_mask, EMPTY_ENTITY_ID)
        spawned = self.allocate(total_spawns)
        return CleanupSpawnTransition(
            removed=removed,
            spawned=spawned,
            spawn_parent_ids=parent_ids,
            spawn_parent_slots=parent_slots,
        )

    def compaction_plan(self) -> CompactionPlan:
        """Return the explicit ID-order policy used for optional compaction."""

        ordered = self.id_order()
        destination = torch.arange(
            self.capacity, dtype=torch.int64, device=self.device
        )[None, :].expand(self.batch_size, -1)
        return CompactionPlan(
            source_slots=ordered.slots,
            destination_slots=torch.where(
                ordered.valid, destination, torch.full_like(destination, INVALID_SLOT)
            ),
            valid=ordered.valid,
        )

    def compact_by_id(self) -> CompactionPlan:
        """Pack live pool metadata into ascending-ID slots and return its plan."""

        plan = self.compaction_plan()
        safe_sources = plan.source_slots.clamp_min(0)
        ordered_ids = torch.gather(self.entity_id, 1, safe_sources)
        self.active.copy_(plan.valid)
        self.entity_id.copy_(
            torch.where(plan.valid, ordered_ids, torch.zeros_like(ordered_ids))
        )
        return plan
