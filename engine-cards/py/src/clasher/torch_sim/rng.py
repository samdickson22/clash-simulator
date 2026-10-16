"""Tensor-resident implementation of the simulator's ``random.Random`` stream.

The Python oracle uses CPython's MT19937 implementation.  Simulator kernels
must consume that stream in exactly the same order so a tensor prefix can
return to Python without changing the rest of an episode.  This module imports
and exports the complete Python state and implements the two primitives used by
the simulator: ``random()`` and one-argument ``randrange()``.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

import torch

_MT_N = 624
_MT_M = 397
_MT_MATRIX_A = 0x9908B0DF
_MT_UPPER_MASK = 0x80000000
_MT_LOWER_MASK = 0x7FFFFFFF
_UINT32_MASK = 0xFFFFFFFF
_PYTHON_RANDOM_VERSION = 3


@dataclass
class TensorPythonRandom:
    """Independent CPython-compatible random streams stored in batch tensors."""

    device: torch.device
    words: torch.Tensor
    index: torch.Tensor
    gauss_value: torch.Tensor
    gauss_cached: torch.Tensor

    @property
    def batch_size(self) -> int:
        return int(self.index.shape[0])

    @classmethod
    def from_randoms(
        cls,
        randoms: Sequence[random.Random],
        *,
        device: str | torch.device = "cpu",
    ) -> TensorPythonRandom:
        """Copy complete Python RNG states without consuming either stream."""

        if not randoms:
            raise ValueError("at least one Python random stream is required")
        torch_device = torch.device(device)
        states = [source.getstate() for source in randoms]
        versions = {int(state[0]) for state in states}
        if versions != {_PYTHON_RANDOM_VERSION}:
            raise ValueError(
                "TensorPythonRandom requires CPython random state version 3"
            )
        internal_states = [state[1] for state in states]
        if any(len(internal) != _MT_N + 1 for internal in internal_states):
            raise ValueError("unexpected CPython MT19937 state length")
        words = torch.tensor(
            [internal[:_MT_N] for internal in internal_states],
            dtype=torch.int64,
            device=torch_device,
        )
        indices = torch.tensor(
            [internal[_MT_N] for internal in internal_states],
            dtype=torch.int64,
            device=torch_device,
        )
        gauss_cached = torch.tensor(
            [state[2] is not None for state in states],
            dtype=torch.bool,
            device=torch_device,
        )
        gauss_value = torch.tensor(
            [0.0 if state[2] is None else float(state[2]) for state in states],
            dtype=torch.float64,
            device=torch_device,
        )
        return cls(
            device=torch_device,
            words=words,
            index=indices,
            gauss_value=gauss_value,
            gauss_cached=gauss_cached,
        )

    def _row_indices(
        self,
        rows: Sequence[int] | torch.Tensor,
    ) -> torch.Tensor:
        row_indices = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        if row_indices.ndim != 1:
            raise ValueError("fork rows must be a one-dimensional sequence")
        if bool(((row_indices < 0) | (row_indices >= self.batch_size)).any().item()):
            raise IndexError("fork row is outside the RNG batch")
        return row_indices

    def fork(self, rows: Sequence[int] | torch.Tensor) -> TensorPythonRandom:
        """Create independently mutable streams selected from parent rows."""

        row_indices = self._row_indices(rows)
        return type(self)(
            device=self.device,
            words=self.words.index_select(0, row_indices),
            index=self.index.index_select(0, row_indices),
            gauss_value=self.gauss_value.index_select(0, row_indices),
            gauss_cached=self.gauss_cached.index_select(0, row_indices),
        )

    def clone(self) -> TensorPythonRandom:
        """Clone every stream with no shared mutable tensor storage."""

        return self.fork(torch.arange(self.batch_size, device=self.device))

    def python_state(self, row: int) -> tuple[object, ...]:
        """Return one state in the exact shape accepted by ``Random.setstate``."""

        if row < 0 or row >= self.batch_size:
            raise IndexError("RNG row is outside the batch")
        internal = tuple(int(value) for value in self.words[row].tolist()) + (
            int(self.index[row].item()),
        )
        gauss_next = (
            float(self.gauss_value[row].item())
            if bool(self.gauss_cached[row].item())
            else None
        )
        return (_PYTHON_RANDOM_VERSION, internal, gauss_next)

    def sync_to_randoms(self, randoms: Sequence[random.Random]) -> None:
        """Publish resident streams back to Python without drawing a value."""

        if len(randoms) != self.batch_size:
            raise ValueError("Python random stream count does not match tensor batch")
        for row, target in enumerate(randoms):
            target.setstate(self.python_state(row))

    def _active_mask(self, active: torch.Tensor | None) -> torch.Tensor:
        if active is None:
            return torch.ones(
                (self.batch_size,), dtype=torch.bool, device=self.device
            )
        mask = active.to(device=self.device, dtype=torch.bool)
        if mask.shape != (self.batch_size,):
            raise ValueError("active RNG mask must have shape (batch_size,)")
        return mask

    def _twist(self, rows: torch.Tensor) -> None:
        if rows.numel() == 0:
            return
        state = self.words.index_select(0, rows).clone()

        first = torch.arange(0, _MT_N - _MT_M, device=self.device)
        y = (state[:, first] & _MT_UPPER_MASK) | (
            state[:, first + 1] & _MT_LOWER_MASK
        )
        state[:, first] = (
            state[:, first + _MT_M]
            ^ (y >> 1)
            ^ ((y & 1) * _MT_MATRIX_A)
        ) & _UINT32_MASK

        # The wrapped half reads already-twisted values.  Split it at the
        # second dependency boundary so each vectorized block sees the same
        # in-place ordering as CPython's two scalar loops.
        for start, stop in (
            (_MT_N - _MT_M, 2 * (_MT_N - _MT_M)),
            (2 * (_MT_N - _MT_M), _MT_N - 1),
        ):
            wrapped = torch.arange(start, stop, device=self.device)
            y = (state[:, wrapped] & _MT_UPPER_MASK) | (
                state[:, wrapped + 1] & _MT_LOWER_MASK
            )
            state[:, wrapped] = (
                state[:, wrapped + (_MT_M - _MT_N)]
                ^ (y >> 1)
                ^ ((y & 1) * _MT_MATRIX_A)
            ) & _UINT32_MASK

        y = (state[:, _MT_N - 1] & _MT_UPPER_MASK) | (
            state[:, 0] & _MT_LOWER_MASK
        )
        state[:, _MT_N - 1] = (
            state[:, _MT_M - 1]
            ^ (y >> 1)
            ^ ((y & 1) * _MT_MATRIX_A)
        ) & _UINT32_MASK
        self.words[rows] = state
        self.index[rows] = 0

    def _next_uint32(self, active: torch.Tensor | None = None) -> torch.Tensor:
        mask = self._active_mask(active)
        twist_rows = torch.nonzero(mask & (self.index >= _MT_N), as_tuple=False).flatten()
        self._twist(twist_rows)

        rows = torch.nonzero(mask, as_tuple=False).flatten()
        result = torch.zeros(
            (self.batch_size,), dtype=torch.int64, device=self.device
        )
        if rows.numel() == 0:
            return result
        positions = self.index.index_select(0, rows)
        value = self.words[rows, positions]
        self.index[rows] = positions + 1

        value ^= value >> 11
        value ^= (value << 7) & 0x9D2C5680
        value ^= (value << 15) & 0xEFC60000
        value ^= value >> 18
        result[rows] = value & _UINT32_MASK
        return result

    def random(self, active: torch.Tensor | None = None) -> torch.Tensor:
        """Match ``random.Random.random`` and consume two words per active row."""

        mask = self._active_mask(active)
        high = self._next_uint32(mask) >> 5
        low = self._next_uint32(mask) >> 6
        value = (
            high.to(torch.float64) * 67_108_864.0 + low.to(torch.float64)
        ) * (1.0 / 9_007_199_254_740_992.0)
        return torch.where(mask, value, torch.zeros_like(value))

    def getrandbits(
        self,
        bit_count: int,
        active: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Match CPython ``getrandbits`` for values representable in int64."""

        if bit_count < 0 or bit_count > 63:
            raise ValueError("tensor getrandbits supports 0 through 63 bits")
        mask = self._active_mask(active)
        result = torch.zeros(
            (self.batch_size,), dtype=torch.int64, device=self.device
        )
        if bit_count == 0:
            return result
        word_count = (bit_count - 1) // 32 + 1
        for word_index in range(word_count):
            word = self._next_uint32(mask)
            remaining = bit_count - 32 * word_index
            if remaining < 32:
                word >>= 32 - remaining
            result |= word << (32 * word_index)
        return torch.where(mask, result, torch.zeros_like(result))

    def randbelow(
        self,
        upper_bound: int | torch.Tensor,
        active: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Match Python's rejection-sampled ``_randbelow_with_getrandbits``."""

        bounds = torch.as_tensor(
            upper_bound, dtype=torch.int64, device=self.device
        )
        if bounds.ndim == 0:
            bounds = bounds.expand(self.batch_size)
        if bounds.shape != (self.batch_size,):
            raise ValueError("RNG upper bounds must be scalar or shape (batch_size,)")
        mask = self._active_mask(active)
        if bool((bounds[mask] <= 0).any().item()):
            raise ValueError("RNG upper bounds must be positive for active rows")
        if bool((bounds[mask] > (1 << 62)).any().item()):
            raise ValueError("tensor randbelow supports upper bounds through 2**62")

        result = torch.zeros(
            (self.batch_size,), dtype=torch.int64, device=self.device
        )
        pending = mask.clone()
        bit_counts = torch.zeros_like(bounds)
        for row in torch.nonzero(mask, as_tuple=False).flatten().tolist():
            bit_counts[row] = int(bounds[row].item()).bit_length()
        while bool(pending.any().item()):
            for bit_count in torch.unique(bit_counts[pending]).tolist():
                group = pending & (bit_counts == int(bit_count))
                candidate = self.getrandbits(int(bit_count), group)
                accepted = group & (candidate < bounds)
                result[accepted] = candidate[accepted]
                pending &= ~accepted
        return result

    def randrange(
        self,
        stop: int | torch.Tensor,
        active: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Match the one-argument ``Random.randrange(stop)`` used by Clasher."""

        return self.randbelow(stop, active)
