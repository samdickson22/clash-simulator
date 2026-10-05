"""Current-weight recurrent reconstruction for the council scalar PPO path.

Full episode prefixes are the exact reference. A finite burn-in limit deliberately
restarts from zero at the retained suffix; it is an approximation, not an exact
replacement for arbitrary earlier history. Neither path reuses old-weight state.
"""
from __future__ import annotations

from dataclasses import fields

import torch
from torch import Tensor

from .model import ClasherPolicy, PolicyInputs

RecurrentPrefixes = tuple[PolicyInputs | None, ...]


def _map_inputs(inputs: PolicyInputs, transform) -> PolicyInputs:
    return PolicyInputs(**{
        field.name: None if getattr(inputs, field.name) is None
        else transform(getattr(inputs, field.name))
        for field in fields(PolicyInputs)
    })


def _concatenate(chunks: list[PolicyInputs]) -> PolicyInputs:
    values = {}
    for field in fields(PolicyInputs):
        tensors = [getattr(chunk, field.name) for chunk in chunks]
        if all(tensor is None for tensor in tensors):
            values[field.name] = None
        elif any(tensor is None for tensor in tensors):
            raise ValueError(f"recurrent history changed optional field {field.name}")
        else:
            if field.name.startswith(("entity_", "critic_entity_")):
                width = max(tensor.shape[2] for tensor in tensors)
                padded = []
                for tensor in tensors:
                    if tensor.shape[2] < width:
                        shape = list(tensor.shape)
                        shape[2] = width
                        expanded = tensor.new_zeros(shape)
                        expanded[:, :, :tensor.shape[2]] = tensor
                        tensor = expanded
                    padded.append(tensor)
                tensors = padded
            values[field.name] = torch.cat(tensors, dim=1)
    return PolicyInputs(**values)


class RecurrentHistory:
    """Owned CPU snapshots of observations since each learner's last reset."""

    def __init__(self, batch_size: int) -> None:
        if batch_size < 1:
            raise ValueError("history needs at least one sequence")
        self._rows: list[list[PolicyInputs]] = [[] for _ in range(batch_size)]

    def append(self, inputs: PolicyInputs) -> None:
        if inputs.batch_size != len(self._rows) or inputs.sequence_length < 1:
            raise ValueError("history input batch or sequence length is invalid")
        for row, chunks in enumerate(self._rows):
            starts = torch.nonzero(inputs.episode_starts[row], as_tuple=False).flatten()
            begin = int(starts[-1]) if len(starts) else 0
            if len(starts):
                chunks.clear()
            elif not chunks:
                raise ValueError("exact recurrent history must begin at an episode reset")
            chunks.append(PolicyInputs(**{
                field.name: None
                if field.name.startswith("critic_") or getattr(inputs, field.name) is None
                else getattr(inputs, field.name)[row:row + 1, begin:].detach().cpu().clone()
                for field in fields(PolicyInputs)
            }))

    def snapshot(self) -> RecurrentPrefixes:
        # torch.cat owns storage, including the one-chunk case. Future appends,
        # resets and caller mutation cannot change this PPO prefix snapshot.
        return tuple(_concatenate(chunks) if chunks else None for chunks in self._rows)


@torch.no_grad()
def reconstruct_recurrent_state(
    model: ClasherPolicy,
    prefixes: RecurrentPrefixes,
    *,
    device: torch.device,
    burn_in_steps: int | None = None,
    replay_chunk_steps: int = 128,
) -> tuple[Tensor, Tensor]:
    """Replay current weights, either exact prefixes or an explicit bounded suffix.

    ``burn_in_steps=None`` reconstructs the full episode state exactly, within
    floating-point tolerance. ``burn_in_steps=32`` replays only the last 32
    observations from zero state. That bounded approximation is useful to measure
    state error and cost, but must not be described as exact full-prefix replay.
    Input prefixes exclude the first observation whose action is being updated.
    """
    if not prefixes:
        raise ValueError("reconstruction needs at least one sequence")
    if burn_in_steps is not None and burn_in_steps < 1:
        raise ValueError("burn-in must be positive or None for full episode replay")
    if replay_chunk_steps < 1:
        raise ValueError("replay chunk size must be positive")
    if model.config.dropout != 0:
        raise ValueError("council recurrent replay requires dropout zero")
    was_training = model.training
    model.eval()
    reconstructed = []
    try:
        for prefix in prefixes:
            state = model.initial_state(1, device=device)
            if prefix is not None:
                if prefix.batch_size != 1 or prefix.sequence_length < 1:
                    raise ValueError("each prefix must contain one nonempty sequence")
                if not bool(prefix.episode_starts[0, 0]):
                    raise ValueError("exact stored prefix must start at episode reset")
                begin = 0 if burn_in_steps is None else max(
                    0, prefix.sequence_length - burn_in_steps
                )
                for start in range(begin, prefix.sequence_length, replay_chunk_steps):
                    inputs = _map_inputs(prefix, lambda tensor: tensor[
                        :, start:start + replay_chunk_steps
                    ].to(device))
                    state = model(inputs, state).next_state
            reconstructed.append(state)
        return tuple(torch.cat([state[i] for state in reconstructed], dim=0).detach()
                     for i in (0, 1))
    finally:
        model.train(was_training)
