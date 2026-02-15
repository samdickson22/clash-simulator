from __future__ import annotations

from dataclasses import dataclass
from multiprocessing import shared_memory
from typing import Dict, List, Tuple

import numpy as np


@dataclass(frozen=True)
class SharedArraySpec:
    shape: Tuple[int, ...]
    dtype: str


@dataclass(frozen=True)
class SharedArrayHandle:
    name: str
    shape: Tuple[int, ...]
    dtype: str


FieldSpecs = Dict[str, SharedArraySpec]
SlotHandles = Dict[str, SharedArrayHandle]


def build_rollout_field_specs(
    *,
    transitions_per_batch: int,
    board_shape: Tuple[int, ...],
    hud_size: int,
    num_actions: int,
    obs_dtype: str,
) -> FieldSpecs:
    return {
        "boards": SharedArraySpec(shape=(transitions_per_batch, *board_shape), dtype=obs_dtype),
        "huds": SharedArraySpec(shape=(transitions_per_batch, hud_size), dtype=obs_dtype),
        "masks": SharedArraySpec(shape=(transitions_per_batch, num_actions), dtype="bool"),
        "actions": SharedArraySpec(shape=(transitions_per_batch,), dtype="int64"),
        "old_log_probs": SharedArraySpec(shape=(transitions_per_batch,), dtype="float32"),
        "values": SharedArraySpec(shape=(transitions_per_batch,), dtype="float32"),
        "rewards": SharedArraySpec(shape=(transitions_per_batch,), dtype="float32"),
        "dones": SharedArraySpec(shape=(transitions_per_batch,), dtype="bool"),
        "player_ids": SharedArraySpec(shape=(transitions_per_batch,), dtype="int8"),
        "next_values": SharedArraySpec(shape=(transitions_per_batch,), dtype="float32"),
        "mask_shadow_checks": SharedArraySpec(shape=(1,), dtype="float32"),
        "mask_shadow_mismatches": SharedArraySpec(shape=(1,), dtype="float32"),
    }


class SharedRolloutPoolOwner:
    """Owns actor rollout shared-memory slots in the learner process."""

    def __init__(
        self,
        *,
        num_actors: int,
        slots_per_actor: int,
        field_specs: FieldSpecs,
    ) -> None:
        self.num_actors = num_actors
        self.slots_per_actor = slots_per_actor
        self._field_specs = field_specs
        self._owned_shms: List[shared_memory.SharedMemory] = []
        self._slot_arrays: Dict[Tuple[int, int], Dict[str, np.ndarray]] = {}
        self._slot_handles: Dict[Tuple[int, int], SlotHandles] = {}

        for actor_id in range(num_actors):
            for slot_id in range(slots_per_actor):
                arrays: Dict[str, np.ndarray] = {}
                handles: SlotHandles = {}
                for field, spec in field_specs.items():
                    dtype = np.dtype(spec.dtype)
                    nbytes = int(np.prod(spec.shape, dtype=np.int64)) * dtype.itemsize
                    shm = shared_memory.SharedMemory(create=True, size=nbytes)
                    arr = np.ndarray(spec.shape, dtype=dtype, buffer=shm.buf)
                    arr.fill(0)
                    self._owned_shms.append(shm)
                    arrays[field] = arr
                    handles[field] = SharedArrayHandle(
                        name=shm.name,
                        shape=spec.shape,
                        dtype=spec.dtype,
                    )
                self._slot_arrays[(actor_id, slot_id)] = arrays
                self._slot_handles[(actor_id, slot_id)] = handles

    def actor_slot_handles(self, actor_id: int) -> List[SlotHandles]:
        return [
            self._slot_handles[(actor_id, slot_id)]
            for slot_id in range(self.slots_per_actor)
        ]

    def read_batch_copy(self, actor_id: int, slot_id: int) -> Dict[str, np.ndarray]:
        slot = self._slot_arrays[(actor_id, slot_id)]
        return {field: np.array(arr, copy=True) for field, arr in slot.items()}

    def close(self) -> None:
        for shm in self._owned_shms:
            try:
                shm.close()
            except Exception:
                pass
            try:
                shm.unlink()
            except Exception:
                pass
        self._owned_shms.clear()
        self._slot_arrays.clear()
        self._slot_handles.clear()


class SharedRolloutWriter:
    """Actor-side shared-memory writer."""

    def __init__(self, slot_handles: List[SlotHandles]) -> None:
        self._attached_shms: List[shared_memory.SharedMemory] = []
        self._slot_arrays: List[Dict[str, np.ndarray]] = []
        for slot in slot_handles:
            arrays: Dict[str, np.ndarray] = {}
            for field, handle in slot.items():
                shm = shared_memory.SharedMemory(name=handle.name)
                dtype = np.dtype(handle.dtype)
                arr = np.ndarray(handle.shape, dtype=dtype, buffer=shm.buf)
                self._attached_shms.append(shm)
                arrays[field] = arr
            self._slot_arrays.append(arrays)

    def write_batch(self, slot_id: int, batch: Dict[str, np.ndarray]) -> None:
        slot = self._slot_arrays[slot_id]
        for field, arr in slot.items():
            value = batch[field]
            if value.shape != arr.shape:
                raise ValueError(
                    f"shape mismatch for {field}: expected {arr.shape}, got {value.shape}"
                )
            arr[...] = value

    def close(self) -> None:
        for shm in self._attached_shms:
            try:
                shm.close()
            except Exception:
                pass
        self._attached_shms.clear()
        self._slot_arrays.clear()
