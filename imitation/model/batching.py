"""Vectorized, read-only feature construction from qualified mmap columns.

The scalar serving adapter remains the reference. All loops here are over a
fixed number of fields/types, never over rows or entities. No derived cache.
"""
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader, BatchSampler, SequentialSampler
from .features import BUCKETS, GLOBAL_COLUMNS, ENTITY_COLUMNS
from .losses import HAZARD_EDGES
from .store import LABELS


def build_batch(store, indices):
    ix = np.asarray(indices, dtype=np.int64)
    a = store.arrays
    n = len(ix)
    if not n:
        raise ValueError('empty batch')
    hand = a['hand_ids'][ix].astype(np.int64)
    levels = a['hand_levels'][ix].astype(np.float32)
    g = a['global_features'][ix]
    button = a['champion_button'][ix].astype(bool)
    deck = np.sort(a['own_deck'][ix], axis=1)
    if (deck <= 0).any() or (np.diff(deck, axis=1) == 0).any():
        raise ValueError('own deck must contain eight known distinct tokens')
    if 'action_mask' in a:
        mask = a['action_mask'][ix].astype(bool)
    else:
        mask = np.unpackbits(a['mask_table'][a['mask_index'][ix]], axis=1,
                             bitorder=getattr(store, 'mask_bitorder', 'little'))[:, :2306].astype(bool)
    if mask.shape != (n, 2306) or not mask.any(1).all():
        raise ValueError('need nonempty action support for every row')
    offsets = a['entity_offsets'][ix]
    counts = a['entity_offsets'][ix+1] - offsets
    if (counts > 128).any():
        raise ValueError('more than 128 visible entities')
    e = int(counts.max())
    # 26 unconditional cycle slots; 32 optional seen/history slots; global.
    width = 59 + e
    ids = np.zeros((n, width), np.int64)
    types = np.zeros((n, width), np.int64)
    num = np.zeros((n, width, 24), np.float32)
    valid = np.ones((n, width), bool)
    ids[:, :4] = hand[:, :4]; types[:, :4] = 1
    # Match the scalar adapter's float64 intermediate arithmetic exactly.
    num[:, :4, 0] = store.costs[hand[:, :4]].astype(np.float64)/10 - g[:, 5, None]
    num[:, :4, 1] = mask[:, :2304].reshape(n, 4, 576).any(2)
    num[:, :4, 2] = button[:, None]; num[:, :4, 3] = levels[:, :4]/16
    ids[:, 4:12] = deck; types[:, 4:12] = 3
    num[:, 4:12, 0] = np.arange(8)/7
    ids[:, 12] = hand[:, 4]; types[:, 12] = 2; num[:, 12, 0] = levels[:, 4]/16
    for begin, end, key, kind in ((13,17,'own_queue',np.arange(4,8)),
                                 (17,21,'opp_hand_known',8),
                                 (22,26,'opp_queue',np.arange(10,14))):
        ids[:, begin:end] = a[key][ix]; types[:, begin:end] = kind
        num[:, begin:end, 0] = ids[:, begin:end] != 0
    ids[:, 21] = a['opp_next_card'][ix]; types[:, 21] = 9
    num[:, 21, 0] = ids[:, 21] != 0
    ids[:, 26:34] = a['opponent_seen_card_ids'][ix]; types[:, 26:34] = 14
    for begin, side, kind in ((34,'opp',15),(42,'own',16)):
        if store.t3:
            h = a[side+'_recent_play_ids'].shape[1]
            ids[:, begin:begin+h] = a[side+'_recent_play_ids'][ix]
            num[:, begin:begin+h, :3] = a[side+'_recent_play_features'][ix]
        else:
            hist = a[side+'_history'][ix]; h = hist.shape[1]
            ids[:, begin:begin+h] = hist[:, :, 0]
            num[:, begin:begin+h, :3] = hist[:, :, 1:]
        types[:, begin:begin+8] = kind
    if store.t3:
        h = a['opp_ability_ids'].shape[1]
        ids[:, 50:50+h] = a['opp_ability_ids'][ix]
        num[:, 50:50+h, 0] = a['opp_ability_ages'][ix].reshape(n, h)
    else:
        hist = a['opp_abilities'][ix]; h = hist.shape[1]
        ids[:, 50:50+h] = hist[:, :, 0]; num[:, 50:50+h, 0] = hist[:, :, 1]
    types[:, 50:58] = 17
    valid[:, 26:58] = ids[:, 26:58] != 0
    types[:, 58] = 18
    num[:, 58, :15] = g[:, GLOBAL_COLUMNS]
    num[~button, 58, 13:15] = 0
    num[:, 58, 15] = a['opp_elixir'][ix].astype(np.float64)/10
    for col, side in ((16,'opp'),(17,'own')):
        num[:, 58, col] = a[side+'_refill_remaining'][ix].astype(np.float64)/(1000 if store.t3 else 1)
    num[:, 58, 18] = a['opp_cards_revealed'][ix].astype(np.float64)/8
    num[:, 58, 19] = a['elixir_exact'][ix]; num[:, 58, 20] = button
    if e:
        active = np.arange(e)[None] < counts[:, None]
        take = np.minimum(offsets[:, None] + np.arange(e), len(a['flat_entity_ids'])-1)
        ids[:, 59:] = a['flat_entity_ids'][take]
        f = a['flat_entity_features'][take]
        if f.shape[-1] == 32:
            f = f[:, :, ENTITY_COLUMNS]
        num[:, 59:, :17] = f
        num[:, 59:, 17] = a['flat_entity_levels'][take].astype(np.float32)/16
        valid[:, 59:] = active
    if ((ids[valid] < 0) | (ids[valid] >= 360)).any() or not np.isfinite(num[valid]).all():
        raise ValueError('invalid public token/numeric feature')
    # Stable compaction reproduces scalar omission of absent historical tokens.
    length = valid.sum(1)
    out_width = next(b for b in BUCKETS if b >= int(length.max())+1)-1
    row, col = np.nonzero(valid)
    dest = (valid.cumsum(1)-1)[row, col]
    b = {}
    for key, source in (('ids',ids),('types',types),('numeric',num)):
        out = np.zeros((n,out_width)+source.shape[2:],source.dtype)
        out[row,dest] = source[row,col]
        b[key] = torch.from_numpy(out)
    b['valid'] = torch.from_numpy(np.arange(out_width)[None] < length[:,None])
    b['action_mask'] = torch.from_numpy(mask)
    if store.t3:
        observed = ~a['intent_censored'][ix].astype(bool)
        delay = a['intent_delay_ticks'][ix].astype(np.float64)/20
        if (delay < 0).any():
            raise ValueError('negative intent time')
        bins = np.where(observed, np.searchsorted(HAZARD_EDGES,delay,side='left'),
                        np.searchsorted(HAZARD_EDGES,delay,side='right'))
        y = {k: a[v][ix] for k,v in LABELS.items() if not k.startswith('intent_')}
        y.update(intent_card=a['intent_deck_index'][ix],intent_bin=bins,
                 intent_observed=observed,intent_valid=np.ones(n,bool))
    else:
        y = {k: a[v][ix] for k,v in LABELS.items()}
    ic = y['intent_card'].astype(np.int64)
    if (ic >= 8).any():
        raise ValueError('intent deck index outside [0,8)')
    token = np.take_along_axis(a['own_deck'][ix],ic.clip(0,7)[:,None],axis=1)[:,0]
    y['intent_card'] = np.where(ic >= 0,(deck < token[:,None]).sum(1),ic)
    action = y['action'].astype(np.int64)
    legal = (action>=0)&(action<2306)&mask[np.arange(n),action.clip(0,2305)]
    if (y['supervised'].astype(bool)&~legal).any():
        raise ValueError('illegal supervised label')
    if ((y['intent_bin']<0)|(y['intent_bin']>12)).any() or not np.isfinite(y['weight']).all() or (y['weight']<0).any():
        raise ValueError('invalid target/weight')
    y.update(row_id=a['row_ids'][ix],perspective=a['perspective_ids'][ix],index=ix)
    return b,{k:torch.from_numpy(np.asarray(v)) for k,v in y.items()}


class BatchedStore(Dataset):
    def __init__(self, store):
        self.store = store
    def __len__(self):
        return len(self.store)
    def __getitem__(self, indices):
        return build_batch(self.store, indices)


class IndexBatches:
    def __init__(self, indices, batch_size):
        self.indices, self.batch_size = indices, batch_size
    def __len__(self):
        return (len(self.indices)+self.batch_size-1)//self.batch_size
    def __iter__(self):
        for start in range(0,len(self.indices),self.batch_size):
            yield self.indices[start:start+self.batch_size]


def batch_loader(store, batch_size, indices=None, workers=0, pin_memory=False, seed=0):
    if not 0 <= workers <= 8:
        raise ValueError('loader workers must be within [0,8]; host budget checked separately')
    sampler = IndexBatches(indices if indices is not None else range(len(store)),batch_size)
    return DataLoader(BatchedStore(store),batch_size=None,sampler=sampler,
                      num_workers=workers,pin_memory=pin_memory,
                      prefetch_factor=2 if workers else None,
                      generator=torch.Generator().manual_seed(seed))
