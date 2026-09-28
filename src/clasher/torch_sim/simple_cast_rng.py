"""CPU-owned exact cast randomness with explicit device transfers.

This owner is not yet connected to SimpleGymRuntime. It preserves supplied
CPython states; matching whole games also requires identical state ingress and
consumer order. No device-resident or throughput claim is implied.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

import torch

from .rng import TensorPythonRandom


@dataclass(frozen=True)
class CastRandomDraws:
    angles: torch.Tensor
    mask_bytes_to_cpu: int
    angle_bytes_to_device: int


class CPUExactCastRNG:
    """One independent exact stream per battle, never implicitly reseeded."""

    def __init__(self, sources: Sequence[random.Random]) -> None:
        self.state = TensorPythonRandom.from_randoms(sources, device="cpu")

    @property
    def batch_size(self) -> int:
        return self.state.batch_size

    def fork(self, rows: Sequence[int] | torch.Tensor) -> CPUExactCastRNG:
        result = object.__new__(type(self))
        result.state = self.state.fork(rows)
        return result

    def reset_rows_(self, reset_mask: torch.Tensor, sources: Sequence[random.Random]) -> None:
        """Copy supplied full-batch episode states into selected rows only."""
        if reset_mask.shape != (self.batch_size,) or reset_mask.dtype != torch.bool:
            raise ValueError("reset_mask must be bool [batch]")
        if len(sources) != self.batch_size:
            raise ValueError("reset states must cover the full batch")
        incoming = TensorPythonRandom.from_randoms(sources, device="cpu")
        mask = reset_mask.detach().cpu()
        for name in ("words", "index", "gauss_value", "gauss_cached"):
            destination = getattr(self.state, name)
            destination[mask] = getattr(incoming, name)[mask]

    def fanout_from_(self, source: CPUExactCastRNG, source_row: int = 0) -> None:
        """Copy one supplied stream into independent destination rows."""
        incoming = source.state.fork([source_row] * self.batch_size)
        for name in ("words", "index", "gauss_value", "gauss_cached"):
            getattr(self.state, name).copy_(getattr(incoming, name))

    def draw_angles(self, accepted_casts: torch.Tensor, *, members: int = 30) -> CastRandomDraws:
        """Draw randrange(359) in command/member order for accepted casts.

        Admission and capacity checks must finish before calling. A [batch,
        command] mask is transferred once to CPU; output is returned to that
        mask's device. False entries neither draw nor change their stream.
        Transfer byte counts describe payload, not measured synchronization time.
        """
        if (accepted_casts.ndim != 2 or accepted_casts.shape[0] != self.batch_size
                or accepted_casts.dtype != torch.bool):
            raise ValueError("accepted_casts must be bool [batch, commands]")
        if not isinstance(members, int) or isinstance(members, bool) or members < 1:
            raise ValueError("members must be a positive integer")
        mask = accepted_casts.detach().cpu()
        angles = torch.zeros((*mask.shape, members), dtype=torch.int64)
        for command in range(mask.shape[1]):
            active = mask[:, command]
            for member in range(members):
                angles[:, command, member] = self.state.randrange(359, active=active)
        remote = accepted_casts.device.type != "cpu"
        return CastRandomDraws(
            angles=angles.to(accepted_casts.device),
            mask_bytes_to_cpu=mask.numel() * mask.element_size() if remote else 0,
            angle_bytes_to_device=angles.numel() * angles.element_size() if remote else 0,
        )
