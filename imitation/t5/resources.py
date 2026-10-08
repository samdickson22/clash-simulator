"""Bound process RSS without changing read-only store data or batch tensors."""
import mmap
import numpy as np
from imitation.model import batching

OriginalBatchedStore = batching.BatchedStore


def release_pages(store):
    seen = set()
    for value in store.arrays.values():
        owner = value
        while getattr(owner, 'base', None) is not None and not isinstance(owner, np.memmap):
            owner = owner.base
        mapping = getattr(owner, '_mmap', None)
        if mapping is not None and id(mapping) not in seen:
            if isinstance(owner, np.memmap) and owner.mode not in ('r', 'c'):
                raise ValueError('only read-only input mappings may be released')
            mapping.madvise(mmap.MADV_DONTNEED)
            seen.add(id(mapping))


class BoundedBatchedStore(OriginalBatchedStore):
    def __getitem__(self, indices):
        result = super().__getitem__(indices)
        # build_batch uses fancy-index copies and independent output tensors.
        release_pages(self.store)
        return result


def install():
    batching.BatchedStore = BoundedBatchedStore
