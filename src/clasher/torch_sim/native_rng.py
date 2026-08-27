"""Fast device-native RNG streams for non-parity training workloads.

``NativeTrainingRNG`` is deliberately separate from ``TensorPythonRandom``.
It uses counter-vectorized SplitMix64 streams and therefore does *not* match
CPython's MT19937 values or consumption contract.  Exact simulator modes must
continue using ``TensorPythonRandom``; callers may explicitly opt into this
generator only where native training randomness is semantically allowed.

The implementation keeps one signed-int64 counter per batch row.  A block of
samples is generated with tensor arithmetic only, without a Python loop over
draws, per-draw host synchronization, or ``torch.Generator`` objects per row.
Integer overflow is the intended two's-complement modulo-2**64 arithmetic.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import prod

import torch

# Unsigned SplitMix64 constants represented in signed int64 form.  PyTorch
# integer arithmetic wraps on both CPU and CUDA, which implements the required
# modulo-2**64 ring without uint64 kernels.
_GAMMA = -7046029254386353131  # 0x9E3779B97F4A7C15
_MIX_1 = -4658895280553007687  # 0xBF58476D1CE4E5B9
_MIX_2 = -7723592293110705685  # 0x94D049BB133111EB
_UINT64_MODULUS = 1 << 64
_INT64_LIMIT = 1 << 63
_FLOAT32_SCALE = 1.0 / (1 << 24)
_FLOAT64_SCALE = 1.0 / (1 << 53)


def _signed_int64(value: int) -> int:
    """Normalize one Python signed/unsigned 64-bit seed to int64."""

    integer = int(value)
    if integer < -_INT64_LIMIT or integer >= _UINT64_MODULUS:
        raise ValueError("seed is outside the signed/unsigned 64-bit range")
    unsigned = integer % _UINT64_MODULUS
    return unsigned if unsigned < _INT64_LIMIT else unsigned - _UINT64_MODULUS


def _logical_right_shift(value: torch.Tensor, bits: int) -> torch.Tensor:
    """Unsigned right shift expressed with signed-int64 tensor operations."""

    if bits <= 0 or bits >= 64:
        raise ValueError("logical shift must be between 1 and 63 bits")
    mask = (1 << (64 - bits)) - 1
    return torch.bitwise_and(torch.bitwise_right_shift(value, bits), mask)


def _mix_splitmix64(counter: torch.Tensor) -> torch.Tensor:
    mixed = counter ^ _logical_right_shift(counter, 30)
    mixed = mixed * _MIX_1
    mixed ^= _logical_right_shift(mixed, 27)
    mixed *= _MIX_2
    return mixed ^ _logical_right_shift(mixed, 31)


def _sample_dimensions(
    sample_shape: int | Sequence[int] | torch.Size,
) -> tuple[tuple[int, ...], int]:
    shape: tuple[int, ...]
    if isinstance(sample_shape, int):
        shape = (sample_shape,)
    else:
        shape = tuple(int(dimension) for dimension in sample_shape)
    if any(dimension < 0 for dimension in shape):
        raise ValueError("sample dimensions cannot be negative")
    return shape, prod(shape)


@dataclass
class NativeTrainingRNG:
    """Independent, batched, device-resident native training RNG streams.

    This class makes no exact-oracle guarantee.  Its stable guarantees are:

    * one independent state lane per batch row;
    * deterministic results for a given state, device-independent bit mixer;
    * masked rows neither advance nor publish nonzero samples;
    * clone/fork copy state and never alias mutable storage.
    """

    state: torch.Tensor

    def __post_init__(self) -> None:
        if self.state.dtype != torch.int64:
            raise TypeError("native RNG state must use torch.int64")
        if self.state.ndim != 1 or self.state.numel() < 1:
            raise ValueError("native RNG state must have shape [batch_size]")

    @property
    def device(self) -> torch.device:
        return self.state.device

    @property
    def batch_size(self) -> int:
        return int(self.state.shape[0])

    @classmethod
    def from_seed(
        cls,
        seed: int,
        batch_size: int,
        *,
        device: str | torch.device = "cpu",
    ) -> NativeTrainingRNG:
        """Derive deterministic, SplitMix-scrambled batch row streams."""

        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        torch_device = torch.device(device)
        base = torch.full(
            (batch_size,),
            _signed_int64(seed),
            dtype=torch.int64,
            device=torch_device,
        )
        row = torch.arange(1, batch_size + 1, dtype=torch.int64, device=torch_device)
        gamma = torch.tensor(_GAMMA, dtype=torch.int64, device=torch_device)
        return cls(_mix_splitmix64(base + row * gamma))

    @classmethod
    def from_seeds(
        cls,
        seeds: Sequence[int] | torch.Tensor,
        *,
        device: str | torch.device | None = None,
    ) -> NativeTrainingRNG:
        """Create explicitly seeded independent rows without consuming them."""

        if isinstance(seeds, torch.Tensor):
            target = seeds.device if device is None else torch.device(device)
            state = seeds.to(device=target, dtype=torch.int64).clone()
        else:
            normalized = [_signed_int64(seed) for seed in seeds]
            target = torch.device("cpu" if device is None else device)
            state = torch.tensor(normalized, dtype=torch.int64, device=target)
        return cls(state)

    def clone(self) -> NativeTrainingRNG:
        return type(self)(self.state.clone())

    def fork(
        self,
        rows: Sequence[int] | torch.Tensor,
    ) -> NativeTrainingRNG:
        """Copy selected row streams in requested order for speculative work."""

        indices = torch.as_tensor(rows, dtype=torch.int64, device=self.device)
        if indices.ndim != 1 or indices.numel() < 1:
            raise ValueError("fork rows must be a non-empty vector")
        if bool(((indices < 0) | (indices >= self.batch_size)).any().item()):
            raise IndexError("fork row is outside the RNG batch")
        return type(self)(self.state.index_select(0, indices).clone())

    def to(self, device: str | torch.device) -> NativeTrainingRNG:
        """Copy streams to another device without changing their counters."""

        return type(self)(self.state.to(device=torch.device(device)).clone())

    def state_dict(self) -> dict[str, torch.Tensor]:
        return {"state": self.state.clone()}

    def load_state_dict_(self, state_dict: dict[str, torch.Tensor]) -> None:
        incoming = state_dict.get("state")
        if incoming is None:
            raise ValueError("native RNG state_dict is missing 'state'")
        value = incoming.to(device=self.device, dtype=torch.int64)
        if value.shape != self.state.shape:
            raise ValueError("native RNG state_dict has a different batch shape")
        self.state.copy_(value)

    def _active_mask(self, active: torch.Tensor | None) -> torch.Tensor:
        if active is None:
            return torch.ones(self.batch_size, dtype=torch.bool, device=self.device)
        mask = torch.as_tensor(active, dtype=torch.bool, device=self.device)
        if mask.shape != (self.batch_size,):
            raise ValueError("active mask must have shape [batch_size]")
        return mask

    def advance(
        self,
        draws: int,
        *,
        active: torch.Tensor | None = None,
    ) -> None:
        """Skip a fixed number of draws in selected streams without output."""

        count = int(draws)
        if count < 0:
            raise ValueError("draw count cannot be negative")
        if count == 0:
            return
        mask = self._active_mask(active)
        increment = torch.tensor(_GAMMA, dtype=torch.int64, device=self.device) * count
        self.state.add_(torch.where(mask, increment, 0))

    def random(
        self,
        sample_shape: int | Sequence[int] | torch.Size = (),
        *,
        active: torch.Tensor | None = None,
        dtype: torch.dtype = torch.float32,
    ) -> torch.Tensor:
        """Return uniform samples in ``[0, 1)`` with shape ``[batch, *shape]``."""

        if dtype not in {
            torch.float16,
            torch.bfloat16,
            torch.float32,
            torch.float64,
        }:
            raise TypeError("native random output must use a floating dtype")
        shape, draw_count = _sample_dimensions(sample_shape)
        mask = self._active_mask(active)
        if draw_count == 0:
            return torch.empty(
                (self.batch_size, *shape), dtype=dtype, device=self.device
            )

        gamma = torch.tensor(_GAMMA, dtype=torch.int64, device=self.device)
        offsets = torch.arange(1, draw_count + 1, dtype=torch.int64, device=self.device)
        counters = self.state[:, None] + offsets[None, :] * gamma
        bits = _mix_splitmix64(counters)
        if dtype == torch.float64:
            mantissa = _logical_right_shift(bits, 11)
            samples = mantissa.to(torch.float64) * _FLOAT64_SCALE
        else:
            mantissa = _logical_right_shift(bits, 40)
            samples = (mantissa.to(torch.float32) * _FLOAT32_SCALE).to(dtype)
        samples = torch.where(mask[:, None], samples, 0.0)
        self.advance(draw_count, active=mask)
        return samples.reshape(self.batch_size, *shape)
