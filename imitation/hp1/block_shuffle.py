"""Opt-in bounded RAM shuffle over sequential, whole-perspective mmap chunks.

T11 decides which rows survive, including overlay labels. Only their order changes.
The qualified build_batch still constructs every feature/target. One loader thread
owns one raw chunk, so workers cannot multiply the buffer. Resume reconstructs
order from seed/epoch and the qualified trainer's saved row cursor.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import copy
import hashlib
import json
import mmap

import numpy as np
import torch
import torch.nn.functional as F

from imitation.model.batching import build_batch
from imitation.model.store import D1_KEYS, LABELS, PACKET_KEYS
from imitation.t11.sampling import epoch_indices as random_indices
from imitation.t5.resources import release_pages

T3_D1 = tuple(k for k in D1_KEYS if k not in ('opp_history', 'own_history', 'opp_abilities')) + (
    'opp_recent_play_ids', 'opp_recent_play_features', 'own_recent_play_ids',
    'own_recent_play_features', 'opp_ability_ids', 'opp_ability_ages')
FLAT = ('flat_entity_ids', 'flat_entity_levels', 'flat_entity_features')


def row_fields(store):
    targets = tuple(v for k, v in LABELS.items() if not store.t3 or not k.startswith('intent_'))
    if store.t3:
        targets += ('intent_censored', 'intent_delay_ticks', 'intent_deck_index')
    return tuple(dict.fromkeys((*PACKET_KEYS, *(T3_D1 if store.t3 else D1_KEYS), *targets,
                               'row_ids', 'perspective_ids', 'corpus_s122',
                               'action_mask' if 'action_mask' in store.arrays else 'mask_index')))


def sequential(array):
    owner = array
    while getattr(owner, 'base', None) is not None and not isinstance(owner, np.memmap):
        owner = owner.base
    mapping = getattr(owner, '_mmap', None)
    if mapping is not None:
        mapping.madvise(mmap.MADV_SEQUENTIAL)
    # Kernel sequential readahead follows the contiguous copy below. No whole-file
    # WILLNEED: it would evict other jobs' working sets for a 100+ GiB column.


def sequential_copy(array, first=0, last=None):
    """Copy at most 64 MiB of source pages before dropping their mmap RSS."""
    last = len(array) if last is None else last
    sequential(array)
    out = np.empty((last-first, *array.shape[1:]), dtype=array.dtype)
    stride = array.strides[0]
    rows = max(1, (64 << 20) // max(1, stride))
    owner = array
    while getattr(owner, 'base', None) is not None and not isinstance(owner, np.memmap):
        owner = owner.base
    mapping = getattr(owner, '_mmap', None)
    for begin in range(first, last, rows):
        end = min(last, begin+rows)
        out[begin-first:end-first] = array[begin:end]
        if mapping is not None:
            offset = (owner.offset % mmap.PAGESIZE + array.ctypes.data - owner.ctypes.data
                      + begin * stride)
            page = offset // mmap.PAGESIZE * mmap.PAGESIZE
            stop = min(len(mapping), ((offset+(end-begin)*stride+mmap.PAGESIZE-1)
                                      // mmap.PAGESIZE)*mmap.PAGESIZE)
            mapping.madvise(mmap.MADV_DONTNEED, page, stop-page)
    return out


class BlockShuffle:
    def __init__(self, buffer_gb=20.):
        if not 0 < buffer_gb <= 24:
            raise ValueError('shuffle buffer must be in (0,24] GiB')
        self.budget = int(buffer_gb * 2**30)

    def plan(self, store):
        key = (self.budget, row_fields(store))
        if getattr(store, '_hp1_block_key', None) == key:
            return store._hp1_block_bounds
        fields = row_fields(store)
        fixed = sum(a.dtype.itemsize * int(np.prod(a.shape[1:])) for a in
                    (store.arrays[k] for k in fields)) + 8  # entity_offsets
        entity_bytes = sum(a.dtype.itemsize * int(np.prod(a.shape[1:])) for a in
                           (store.arrays[k] for k in FLAT))
        offsets = store.column('entity_offsets')
        sequential(offsets)
        shared = store.arrays.get('mask_table')
        usable = self.budget - (shared.nbytes if shared is not None else 0) - 8
        # Episode starts are the packed perspective boundaries. Synthetic stores
        # can use contiguous perspective IDs instead.
        if 'episode_starts' in store.arrays:
            starts = np.flatnonzero(store.column('episode_starts'))
        else:
            p = store.column('perspective_ids')
            starts = np.r_[0, np.flatnonzero(p[1:] != p[:-1]) + 1]
        ends = np.unique(np.r_[starts, len(store)]).astype(np.int64)
        if not len(ends) or ends[0] != 0:
            raise ValueError('packed perspectives must start at row zero')
        cumulative = ends * fixed + offsets[ends] * entity_bytes
        bounds = [0]
        pos = 0
        while pos < len(ends) - 1:
            stop = int(np.searchsorted(cumulative, cumulative[pos] + usable, side='right')) - 1
            if stop <= pos:
                raise ValueError('one perspective exceeds the shuffle buffer')
            bounds.append(int(ends[stop])); pos = stop
        store._hp1_block_key, store._hp1_block_bounds = key, np.asarray(bounds, np.int64)
        return store._hp1_block_bounds

    def epoch_indices(self, store, epoch, seed, subset_fraction=1.):
        ix = random_indices(store, epoch, seed, subset_fraction)
        ix.sort()
        bounds = self.plan(store)
        rng = np.random.default_rng(np.random.SeedSequence([seed, epoch, 0x485031]))
        cuts = np.searchsorted(ix, bounds)
        for first, last in zip(cuts[:-1], cuts[1:]):
            rng.shuffle(ix[first:last])
        release_pages(store)
        return ix

    def train_loader(self, store, batch_size, indices=None, workers=0, pin_memory=False, seed=0):
        if workers not in (0, 1):
            raise ValueError('block shuffle uses 0 or 1 loader thread, never per-worker buffers')
        if indices is None:
            indices = np.arange(len(store), dtype=np.int64)
        bounds = self.plan(store)
        shared = {}
        if 'mask_table' in store.arrays:
            shared['mask_table'] = sequential_copy(store.arrays['mask_table'])
        cached_id, cached = None, None

        def load(block):
            nonlocal cached_id, cached
            if cached_id == block:
                return cached
            cached = None  # free the previous buffer BEFORE allocating its replacement
            first, last = map(int, bounds[block:block+2])
            arrays = dict(shared)
            for key in row_fields(store):
                arrays[key] = sequential_copy(store.arrays[key], first, last)
            offsets = store.column('entity_offsets')
            begin, end = int(offsets[first]), int(offsets[last])
            arrays['entity_offsets'] = sequential_copy(offsets, first, last+1)
            arrays['entity_offsets'] -= begin
            for key in FLAT:
                arrays[key] = sequential_copy(store.arrays[key], begin, end)
            if sum(a.nbytes for a in arrays.values()) > self.budget:
                raise RuntimeError('shuffle buffer exceeded byte budget')
            cached = copy(store); cached.arrays = arrays
            cached_id = block
            release_pages(store)
            return cached

        def batches():
            for start in range(0, len(indices), batch_size):
                ix = np.asarray(indices[start:start+batch_size], np.int64)
                blocks = np.searchsorted(bounds, ix, side='right') - 1
                pieces, positions = [], []
                for block in np.unique(blocks):
                    pos = np.flatnonzero(blocks == block)
                    local = ix[pos] - bounds[block]
                    view = load(int(block))
                    b, y = build_batch(view, local)
                    s122 = torch.from_numpy(view.column('corpus_s122')[local])
                    y['weight'] = y['weight'].float()*torch.where(s122 & (y['action'] == 2304), .5, 1.)
                    y['index'] = torch.from_numpy(ix[pos].copy())
                    pieces.append((b, y)); positions.extend(pos)
                    # No view reference may keep an evicted raw chunk alive.
                    del view
                if len(pieces) == 1:
                    b, y = pieces[0]
                else:
                    order = torch.from_numpy(np.argsort(positions))
                    width = max(p[0]['ids'].shape[1] for p in pieces)
                    b = {}
                    for key in pieces[0][0]:
                        parts = [p[0][key] for p in pieces]
                        if key in ('ids', 'types', 'valid', 'numeric'):
                            parts = [F.pad(v, (0, 0, 0, width-v.shape[1])) if key == 'numeric'
                                     else F.pad(v, (0, width-v.shape[1])) for v in parts]
                        b[key] = torch.cat(parts)[order]
                    y = {key: torch.cat([p[1][key] for p in pieces])[order] for key in pieces[0][1]}
                if pin_memory:
                    b = {k: v.pin_memory() for k, v in b.items()}
                    y = {k: v.pin_memory() for k, v in y.items()}
                yield b, y

        iterator = iter(batches())
        if not workers:
            yield from iterator
            return
        # At most one prepared batch plus one being consumed, one raw buffer.
        sentinel = object()
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix='hp1-loader') as pool:
            pending = pool.submit(next, iterator, sentinel)
            while True:
                result = pending.result()
                if result is sentinel:
                    break
                pending = pool.submit(next, iterator, sentinel)
                yield result

    def pin(self):
        return hashlib.sha256(json.dumps({'mode': 'block-shuffle-v1', 'budget': self.budget},
                                         sort_keys=True).encode()).hexdigest()
