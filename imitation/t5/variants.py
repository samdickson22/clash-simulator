"""Explicit noD1 and sliding 32-row GRU extensions of the qualified SetPolicy.

GRU recomputes prior public CLS states under CURRENT weights. No stored/frozen
hidden states, label inputs, future rows, inter-perspective recurrence or
sampling-dependent histories. Context backprop is checkpointed, not detached.
"""
import numpy as np
import torch
from torch import nn
from torch.utils.checkpoint import checkpoint
from imitation.model.network import SetPolicy
from imitation.model.batching import build_batch
from .resources import release_pages


def without_d1(b):
    result = dict(b)
    types = b['types']
    remove = ((types >= 3) & (types <= 13)) | ((types >= 15) & (types <= 17))
    # Physically zero derived values AND exclude their tokens as attention keys.
    result['ids'] = b['ids'].masked_fill(remove, 0)
    result['numeric'] = b['numeric'].masked_fill(remove[..., None], 0).clone()
    global_rows = types == 18
    result['numeric'][:, :, 15:20] *= (~global_rows)[..., None]
    result['valid'] = b['valid'] & ~remove
    return result


def history_indices(indices, starts):
    indices = np.asarray(indices, dtype=np.int64)
    first = starts[np.searchsorted(starts, indices, side='right')-1]
    lengths = np.minimum(32, indices-first+1)
    history = indices[:, None]-lengths[:, None]+1+np.arange(32)
    valid = np.arange(32)[None] < lengths[:, None]
    return np.minimum(history, indices[:, None]), valid, lengths


class NoD1Policy(SetPolicy):
    def forward(self, b, teacher, tile_rows=None):
        return super().forward(without_d1(b), teacher, tile_rows)


class GRUPolicy(SetPolicy):
    context_microbatch = 1024

    def __init__(self, config, descriptors, tiles, costs):
        super().__init__(config, descriptors, tiles, costs)
        self.gru = nn.GRU(config.width, config.width, batch_first=True)
        self.history_store = None
        self.history_starts = None

    def bind_store(self, store):
        self.history_store = store
        if store.t3:
            self.history_starts = np.array([p['target_start'] for p in store.perspectives], dtype=np.int64)
        else:
            p = store.arrays['perspective_ids']
            self.history_starts = np.r_[0, np.flatnonzero(p[1:] != p[:-1])+1]
        if self.history_starts[0] != 0 or np.any(np.diff(self.history_starts) <= 0):
            raise ValueError('invalid perspective partition')

    def encode(self, b):
        # Checkpoint current trunk as well, so past-context replay never holds a
        # second trunk's activation graph. Qualified math/dropout RNG unchanged.
        if self.training and torch.is_grad_enabled():
            keys = tuple(b)
            x = checkpoint(lambda *args: SetPolicy.encode(self, dict(zip(keys, args))),
                           *tuple(b[k] for k in keys), use_reentrant=False)
        else:
            x = super().encode(b)
        if self.history_store is None or 'row_index' not in b:
            raise ValueError('GRU requires a bound same-role store and endpoint indices')
        ix = b['row_index'].detach().cpu().numpy()
        history, valid, lengths = history_indices(ix, self.history_starts)
        unique, inverse = np.unique(history, return_inverse=True)
        # Reuse this microbatch's current states when they also occur in history.
        order = np.argsort(ix)
        position = np.searchsorted(ix[order], unique).clip(0, len(ix)-1)
        present = ix[order[position]] == unique
        values = x.new_zeros((len(unique), x.shape[-1]))
        values = values.index_copy(0, torch.as_tensor(np.flatnonzero(present), device=x.device),
                                  x[torch.as_tensor(order[position[present]], device=x.device), 0])
        missing = np.flatnonzero(~present)
        # Same 8192-row local entity-count ordering / 7168+1024 split as the
        # qualified trunk. This avoids a rare long row padding 7168 other rows.
        pieces = []
        offsets = self.history_store.arrays['entity_offsets']
        for begin in range(0, len(missing), 8192):
            group = missing[begin:begin+8192]
            counts = offsets[unique[group]+1]-offsets[unique[group]]
            group = group[np.argsort(counts, kind='stable')]
            pieces.extend(group[j:j+self.context_microbatch] for j in range(0, len(group), self.context_microbatch))
        for loc in pieces:
            cpu, _ = build_batch(self.history_store, unique[loc])
            release_pages(self.history_store)
            keys = tuple(cpu)
            # Include a CUDA argument so checkpoint preserves CUDA dropout RNG.
            def encode_context(dummy, *args, keys=keys):
                inputs = {k: v.to(dummy.device, non_blocking=True) for k, v in zip(keys, args)}
                return SetPolicy.encode(self, inputs)[:, 0]
            args = tuple(cpu[k] for k in keys)
            if self.training and torch.is_grad_enabled():
                cls = checkpoint(encode_context, x, *args, use_reentrant=False)
            else:
                cls = encode_context(x, *args)
            values = values.index_copy(0, torch.as_tensor(loc, device=x.device), cls)
        sequence = values[torch.as_tensor(inverse.reshape(history.shape), device=x.device)]
        # Right-padded sequences; gather each last valid output, never padding.
        recurrent, _ = self.gru(sequence)
        last = recurrent[torch.arange(len(ix), device=x.device), torch.as_tensor(lengths-1, device=x.device)]
        # Same dimensions/heads. GRU state replaces current CLS; tokens stay public.
        return torch.cat((last[:, None], x[:, 1:]), 1)


def create_policy(variant, config, descriptors, tiles, costs):
    cls = {'main': SetPolicy, 'noD1': NoD1Policy, 'gru': GRUPolicy}[variant]
    return cls(config, descriptors, tiles, costs)
