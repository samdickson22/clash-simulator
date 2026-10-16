from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch
from torch import Tensor

ACTION_TIME_RECURRENT_STATE_CONTRACT = (
    "after-current-public-observation-before-environment-action-v1"
)


@dataclass(frozen=True)
class ActionTimeRecurrentState:
    cell: np.ndarray
    previous_play_hazard: np.ndarray
    contract: str = ACTION_TIME_RECURRENT_STATE_CONTRACT


def snapshot_action_time_recurrent_state(
    next_state: tuple[Tensor, Tensor],
    *,
    expected_memory_size: int,
) -> ActionTimeRecurrentState:
    """Detach the policy state that actually produced the pending action."""

    if expected_memory_size <= 0:
        raise ValueError("expected recurrent memory size must be positive")
    hidden, cell = next_state
    expected_shape = (1, expected_memory_size)
    for name, value in (("hidden", hidden), ("cell", cell)):
        if not isinstance(value, Tensor):
            raise TypeError(f"action-time recurrent {name} must be a tensor")
        if tuple(value.shape) != expected_shape:
            raise ValueError(
                f"action-time recurrent {name} shape {tuple(value.shape)} "
                f"does not match {expected_shape}"
            )
        if value.dtype != torch.float32:
            raise TypeError(f"action-time recurrent {name} must be float32")
        if not bool(torch.isfinite(value).all().item()):
            raise FloatingPointError(
                f"action-time recurrent {name} contains non-finite values"
            )
    if not torch.equal(hidden[:, :-1], cell[:, :-1]):
        raise ValueError(
            "structured-hazard hidden state does not share the cell prefix"
        )
    cell_array = cell[0].detach().cpu().numpy().copy()
    previous_play_hazard = hidden[0, -1:].detach().cpu().numpy().copy()
    cell_array.flags.writeable = False
    previous_play_hazard.flags.writeable = False
    return ActionTimeRecurrentState(
        cell=cell_array,
        previous_play_hazard=previous_play_hazard,
    )


def validate_action_time_recurrent_arrays(
    cell: np.ndarray,
    previous_play_hazard: np.ndarray,
    *,
    expected_rows: int,
    expected_memory_size: int,
) -> None:
    """Fail closed on a serialized batch of compact recurrent states."""

    cell = np.asarray(cell)
    hazard = np.asarray(previous_play_hazard)
    if cell.shape != (expected_rows, expected_memory_size):
        raise ValueError("serialized recurrent cell shape is invalid")
    if hazard.shape != (expected_rows, 1):
        raise ValueError("serialized play-hazard shape is invalid")
    if cell.dtype != np.float32 or hazard.dtype != np.float32:
        raise TypeError("serialized recurrent state must be float32")
    if not np.isfinite(cell).all() or not np.isfinite(hazard).all():
        raise FloatingPointError("serialized recurrent state contains non-finite values")
    if np.any(cell[:, 0] < 0.0) or np.any(cell[:, 0] > 2.0):
        raise ValueError("serialized model-owned clock is outside [0, 2]")
    if np.any(cell[:, 1] < 0.0) or np.any(cell[:, 1] > 1.0):
        raise ValueError("serialized opponent-elixir belief is outside [0, 1]")
    if np.any(cell[:, 2:] < -1.0) or np.any(cell[:, 2:] > 1.0):
        raise ValueError("serialized leaky accumulator is outside [-1, 1]")
    if np.any(hazard < 0.0) or np.any(hazard > 1.0):
        raise ValueError("serialized play hazard is outside [0, 1]")
