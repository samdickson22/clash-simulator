"""Mixed-corpus sampling; unmodified T4 shuffle and row hash definition."""
import numpy as np
import torch
from imitation.model.store import hash64
from imitation.model.batching import batch_loader as qualified_loader
from imitation.t5.resources import release_pages


def epoch_indices(store, epoch, seed, subset_fraction=1.):
    if subset_fraction != 1.:
        raise ValueError('v2 production has no perspective subset')
    parts = []
    # Bound temporary arrays while preserving the exact ascending candidate
    # order and T4's final PCG64 iid shuffle.
    for start in range(0, len(store), 1048576):
        stop = min(start+1048576, len(store)); sl = slice(start, stop)
        ids = store.column('row_ids')[sl].astype(np.uint64)
        values = hash64(ids ^ np.uint64(seed) ^ np.uint64((epoch+1)*0x9e3779b9)) >> np.uint64(32)
        s122 = store.column('corpus_s122')[sl]
        threshold = np.where(s122, 2**31, 2**30).astype(np.uint64)
        keep = store.column('expert_action_supervision_valid')[sl].astype(bool)
        keep &= (store.column('expert_actions')[sl] != 2304) | (values < threshold)
        parts.append(np.flatnonzero(keep)+start)
    indices = np.concatenate(parts)
    np.random.default_rng(np.random.SeedSequence([seed, epoch])).shuffle(indices)
    release_pages(store)
    return indices


def train_loader(store, batch_size, indices=None, **kwargs):
    for b,y in qualified_loader(store,batch_size,indices,**kwargs):
        # T4 applies x4 to waits because its scalar keep probability is 1.
        # S122 already stores x2, so compensate by x.5 here: 2*.5*4 = 4.
        # C56: 1*4 = 4. T5's identical bounded mmap loader builds the tensors.
        if store.role == 'train':
            s122 = torch.from_numpy(np.asarray(store.column('corpus_s122')[y['index'].numpy()]))
            y['weight'] = y['weight'].float()*torch.where(s122 & (y['action']==2304), .5, 1.)
            release_pages(store)
        yield b,y
