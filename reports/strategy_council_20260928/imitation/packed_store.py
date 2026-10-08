"""Read-only mmap reader. Audit files are intentionally outside this interface."""
import json
from pathlib import Path
import numpy as np


class PackedStore:
    def __init__(self, root, role):
        self.root = Path(root)
        self.role = role
        self.manifest = json.loads((self.root/role/'manifest.json').read_text())
        self.arrays = {name:np.load(self.root/role/f'{name}.npy', mmap_mode='r', allow_pickle=False)
                       for name in self.manifest['arrays']}
        self.mask_table = np.load(self.root/'mask_table.npy', mmap_mode='r', allow_pickle=False)

    def __len__(self): return self.manifest['rows']

    def batch(self, rows):
        rows = np.asarray(rows, dtype=np.int64)
        result = {n:np.asarray(a[rows]) for n,a in self.arrays.items()
                  if not n.startswith('flat_entity_') and n != 'entity_offsets'}
        result['action_masks'] = np.unpackbits(self.mask_table[result['mask_index']],axis=-1,count=2306).astype(bool)
        counts = result['entity_counts']; width = int(counts.max(initial=0))
        result['entity_mask'] = np.arange(width)[None,:] < counts[:,None]
        offsets = self.arrays['entity_offsets'][rows]
        for source,target in [('flat_entity_ids','entity_ids'),('flat_entity_levels','entity_levels'),('flat_entity_features','entity_features')]:
            values = self.arrays[source]
            padded = np.zeros((len(rows),width,*values.shape[1:]),values.dtype)
            for i,(offset,count) in enumerate(zip(offsets,counts)):
                padded[i,:count] = values[offset:offset+count]
            result[target] = padded
        return result
