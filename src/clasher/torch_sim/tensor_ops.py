"""Small device-portable tensor reductions shared by resident kernels."""

from __future__ import annotations

import torch


def scatter_any_(
    destination: torch.Tensor,
    dim: int,
    index: torch.Tensor,
    source: torch.Tensor,
) -> torch.Tensor:
    """In-place boolean OR scatter on CPU and CUDA.

    CUDA does not implement ``scatter_reduce_(amax)`` for boolean tensors.
    Reducing the same zero/one values as int32 is equivalent and keeps callers
    free of backend-specific branches.
    """

    if destination.dtype is not torch.bool or source.dtype is not torch.bool:
        raise TypeError("scatter_any_ requires boolean destination and source")
    reduced = destination.to(torch.int32)
    reduced.scatter_reduce_(
        dim,
        index,
        source.to(torch.int32),
        reduce="amax",
        include_self=True,
    )
    destination.copy_(reduced > 0)
    return destination


__all__ = ["scatter_any_"]
