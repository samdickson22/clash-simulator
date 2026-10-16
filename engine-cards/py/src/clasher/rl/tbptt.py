"""Stored actor state and bounded, gradient-free recurrent burn-in."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import fields

import numpy as np
import torch

from .council_recurrence import _concatenate, _map_inputs
from .model import PolicyInputs


class RecurrentUpdateConfig:
    """Read the same three options from a strict TOML table for PPO or BC."""

    @staticmethod
    def load(path):
        import tomllib
        from pydantic import BaseModel, ConfigDict, Field
        from typing import Literal

        class Options(BaseModel):
            model_config = ConfigDict(extra="forbid", strict=True)
            recurrent_update_mode: Literal["full-prefix", "stored-state"] = "full-prefix"
            tbptt_chunk: int = Field(default=64, ge=1)
            tbptt_burn_in: int = Field(default=16, ge=0)

        with open(path, "rb") as stream:
            return Options.model_validate(tomllib.load(stream)).model_dump()


def apply_cli_config(args):
    path = getattr(args, "recurrent_config", None)
    if path is not None:
        for name, value in RecurrentUpdateConfig.load(path).items():
            if not hasattr(args, name):
                setattr(args, name, value)
    mode = getattr(args, "recurrent_update_mode", "full-prefix")
    validate_mode(mode, getattr(args, "tbptt_chunk", 64), getattr(args, "tbptt_burn_in", 16))
    if mode == "full-prefix":
        # Legacy checkpoint args must not acquire new default keys.
        for name in ("recurrent_config", "recurrent_update_mode", "tbptt_chunk", "tbptt_burn_in"):
            vars(args).pop(name, None)
    return args


def validate_mode(mode: str, chunk: int, burn_in: int) -> None:
    if mode not in {"full-prefix", "stored-state"}:
        raise ValueError("unknown recurrent update mode")
    if chunk < 1 or burn_in < 0:
        raise ValueError("TBPTT chunk must be positive and burn-in nonnegative")


def select_steps(inputs: PolicyInputs, rows, steps) -> PolicyInputs:
    return _map_inputs(inputs, lambda value: value[rows, steps])


class RolloutStateRecorder:
    """Keep pre-observation states and only B prior observations across rollouts.

    State includes both LSTM tensors (or the structured cell's full state). The
    current privileged critic is feed-forward and has no recurrent state.
    """

    def __init__(self, model, state, steps: int, burn_in: int):
        if model.config.dropout != 0:
            raise ValueError("stored-state replay requires dropout zero")
        self.history = getattr(model, "_tbptt_history", None)
        if self.history is None:
            self.history = deque(maxlen=burn_in)
            model._tbptt_history = self.history
        if self.history.maxlen != burn_in:
            raise ValueError("cannot change burn-in on a live collector")
        self.hidden = np.empty((state[0].shape[0], steps, state[0].shape[1]), dtype=np.float32)
        self.cell = np.empty((state[1].shape[0], steps, state[1].shape[1]), dtype=np.float32)
        self.prefixes = None
        self.prefix_hidden = state[0].detach().cpu().numpy().copy()
        self.prefix_cell = state[1].detach().cpu().numpy().copy()
        self.tail_hidden = None
        self.tail_cell = None
        if self.history:
            self.tail_hidden = np.stack([entry[1] for entry in self.history], axis=1)
            self.tail_cell = np.stack([entry[2] for entry in self.history], axis=1)
            joined = _concatenate([entry[0] for entry in self.history])
            self.prefixes = tuple(select_steps(joined, slice(i, i+1), slice(None))
                                  for i in range(joined.batch_size))
            self.prefix_hidden, self.prefix_cell = self.history[0][1:]
        else:
            self.prefixes = (None,) * state[0].shape[0]

    def append(self, inputs, state, step):
        hidden = state[0].detach().cpu().numpy().copy()
        cell = state[1].detach().cpu().numpy().copy()
        self.hidden[:, step] = hidden
        self.cell[:, step] = cell
        if self.history.maxlen:
            public = PolicyInputs(**{
                f.name: None if f.name.startswith("critic_") or getattr(inputs, f.name) is None
                else getattr(inputs, f.name).detach().cpu().clone()
                for f in fields(PolicyInputs)
            })
            self.history.append((public, hidden, cell))

    def payload(self):
        return dict(stored_hidden=self.hidden, stored_cell=self.cell,
                    burn_in_prefixes=self.prefixes, burn_in_hidden=self.prefix_hidden,
                    burn_in_cell=self.prefix_cell, burn_in_states_hidden=self.tail_hidden,
                    burn_in_states_cell=self.tail_cell)


def chunk_minibatches(episode_starts, chunk: int, batch_size: int):
    """Fixed windows with reset masks; include every rollout tail exactly once.

    Splitting at episode resets would put short terminal tails in their own
    optimizer minibatches and overweight them. The model resets both recurrent
    tensors inside a window, including their gradient paths.
    """
    chunks = [(row, begin, min(len(starts), begin + chunk))
              for row, starts in enumerate(episode_starts)
              for begin in range(0, len(starts), chunk)]
    buckets = defaultdict(list)
    for i in np.random.permutation(len(chunks)):
        item = chunks[int(i)]
        bucket = buckets[item[2] - item[1]]
        bucket.append(item)
        if len(bucket) == batch_size:
            yield bucket[:]
            bucket.clear()
    for bucket in buckets.values():
        if bucket:
            yield bucket


@torch.no_grad()
def refresh_states(model, states, prefixes, *, device):
    """Refresh saved pre-burn states using current weights; never retain a graph."""
    was_training = model.training
    model.eval()
    try:
        result = [tuple(x.detach().to(device) for x in state) for state in states]
        groups = defaultdict(list)
        for i, prefix in enumerate(prefixes):
            if prefix is not None:
                groups[prefix.sequence_length].append(i)
        for indices in groups.values():
            # Histories may have different packed entity widths.
            values = {}
            for f in fields(PolicyInputs):
                tensors = [getattr(prefixes[i], f.name) for i in indices]
                if all(t is None for t in tensors):
                    values[f.name] = None
                    continue
                if any(t is None for t in tensors):
                    raise ValueError(f"inconsistent burn-in field {f.name}")
                if f.name.startswith(("entity_", "critic_entity_")):
                    width = max(t.shape[2] for t in tensors)
                    padded = []
                    for t in tensors:
                        shape = list(t.shape); shape[2] = width
                        p = t.new_zeros(shape); p[:, :, :t.shape[2]] = t
                        padded.append(p)
                    tensors = padded
                values[f.name] = torch.cat(tensors, dim=0).to(device)
            state = tuple(torch.cat([result[i][j] for i in indices], dim=0) for j in (0, 1))
            output = model(trim_entity_padding(PolicyInputs(**values)), state).next_state
            for row, i in enumerate(indices):
                result[i] = tuple(x[row:row+1].detach() for x in output)
        return tuple(torch.cat([state[j] for state in result], dim=0).detach() for j in (0, 1))
    finally:
        model.train(was_training)


def rollout_chunk_state(model, rollout, inputs, chunks, burn_in, *, device):
    if rollout.stored_hidden is None or rollout.stored_cell is None:
        raise ValueError("stored-state PPO requires states captured during collection")
    states, prefixes = [], []
    for row, start, _ in chunks:
        begin = max(0, start - burn_in)
        # Never replay context before the most recent reset.
        resets = np.flatnonzero(rollout.episode_starts[row, :start+1])
        if len(resets):
            begin = max(begin, int(resets[-1]))
        prefix = None
        state = (rollout.stored_hidden[row:row+1, begin], rollout.stored_cell[row:row+1, begin])
        parts = []
        external = rollout.burn_in_prefixes[row] if rollout.burn_in_prefixes else None
        if not len(resets) and start < burn_in and external is not None:
            # Collection retained precisely B steps. Recover the state at the
            # start of that tail, then discard surplus steps only after replay.
            # For a chunk at start>0, use its in-rollout state instead when the
            # external tail would exceed B. This case is handled below by the
            # recorder retaining states alongside the tail in the rollout.
            available = external.sequence_length
            needed = burn_in - start
            if available > needed:
                # The state at this offset is supplied by stored tail states.
                offset = available - needed
                state = (rollout.burn_in_states_hidden[row:row+1, offset],
                         rollout.burn_in_states_cell[row:row+1, offset])
                external = select_steps(external, slice(None), slice(offset, None))
            else:
                state = (rollout.burn_in_hidden[row:row+1], rollout.burn_in_cell[row:row+1])
            parts.append(_map_inputs(external, lambda x: x.to(device)))
        if start > begin:
            public = select_steps(inputs, slice(row, row+1), slice(begin, start))
            public = PolicyInputs(**{f.name: None if f.name.startswith('critic_') else getattr(public, f.name)
                                     for f in fields(PolicyInputs)})
            parts.append(public)
        if parts:
            prefix = _concatenate(parts)
        states.append(tuple(torch.as_tensor(x, device=device) for x in state))
        prefixes.append(prefix)
    return refresh_states(model, states, prefixes, device=device)


class ImitationStateCache:
    """One linear, no-grad pass per epoch; store only pre-burn chunk states."""

    @torch.no_grad()
    def __init__(self, model, arrays, chunks, *, episode_offsets, burn_in, device):
        from .imitation import _sequence_batch_inputs

        if model.config.dropout != 0:
            raise ValueError("stored-state replay requires dropout zero")
        self.burn_in = burn_in
        self.episode_offsets = episode_offsets
        self.states = {}
        requests = defaultdict(set)
        for chunk in chunks:
            first = int(chunk[0])
            episode = int(arrays['episode_ids'][first])
            begin = max(episode_offsets[episode], first - burn_in)
            requests[episode].add(begin)
        was_training = model.training
        model.eval()
        try:
            for episode, boundaries in requests.items():
                cursor = episode_offsets[episode]
                state = model.initial_state(1, device=device)
                for boundary in sorted(boundaries):
                    while cursor < boundary:
                        end = min(cursor + 128, boundary)
                        inputs = _sequence_batch_inputs(arrays, np.arange(cursor, end)[None],
                            device, trim_entity_padding=True, reset_memory=False)
                        state = model(inputs, state).next_state
                        cursor = end
                    self.states[boundary] = tuple(x.detach().cpu().clone() for x in state)
        finally:
            model.train(was_training)

    def initial_state(self, model, arrays, chunks, *, device):
        from .imitation import _sequence_batch_inputs

        states, prefixes = [], []
        for chunk in chunks:
            first = int(chunk[0])
            episode = int(arrays['episode_ids'][first])
            begin = max(self.episode_offsets[episode], first - self.burn_in)
            states.append(self.states[begin])
            prefixes.append(None if begin == first else _sequence_batch_inputs(
                arrays, np.arange(begin, first)[None], device,
                trim_entity_padding=True, reset_memory=False))
        return refresh_states(model, states, prefixes, device=device)


def trim_entity_padding(inputs: PolicyInputs) -> PolicyInputs:
    """Crop packed trailing padding before the opt-in learner encoder."""
    widths = {}
    for prefix in ('entity_', 'critic_entity_'):
        mask = getattr(inputs, prefix + 'mask')
        if mask is not None:
            occupied = torch.nonzero(mask.any(dim=(0, 1)), as_tuple=False).flatten()
            widths[prefix] = max(1, int(occupied[-1]) + 1) if len(occupied) else 1
    values = {}
    for f in fields(PolicyInputs):
        value = getattr(inputs, f.name)
        for prefix, width in widths.items():
            if f.name.startswith(prefix) and value is not None:
                value = value[:, :, :width]
        values[f.name] = value
    return PolicyInputs(**values)
