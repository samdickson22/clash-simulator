from types import SimpleNamespace

import numpy as np
import pytest
import torch
from compact_public import compact_public, compact_public_batch
from scalar_dataset import PUBLIC_FIELDS, public_batch


def game(width, occupied):
    rng = np.random.default_rng(width)
    n = 7
    values = {
        'entity_ids': rng.integers(0, 20, (n, width), dtype=np.int64),
        'entity_features': rng.normal(size=(n, width, 32)).astype(np.float32),
        'entity_mask': np.zeros((n, width), bool),
        'entity_id_confidence': rng.random((n, width), dtype=np.float32),
        'entity_feature_confidence': rng.random((n, width, 32), dtype=np.float32),
        'hand_ids': rng.integers(0, 20, (n, 4), dtype=np.int64),
        'hand_id_confidence': rng.random((n, 4), dtype=np.float32),
        'global_features': rng.random((n, 18), dtype=np.float32),
        'global_feature_confidence': rng.random((n, 18), dtype=np.float32),
    }
    for tick, slot in occupied:
        values['entity_mask'][tick, slot] = True
    last = max([slot for _, slot in occupied], default=0) + 1
    for key, value in values.items():
        if key.startswith('entity_'):
            value[:, last:] = 0
    return SimpleNamespace(public=values)


@pytest.mark.parametrize('occupied', [[], [(0, 0)], [(0, 1), (6, 10)], [(6, 127)]])
def test_compaction_leaves_original_model_batch_bit_identical(occupied):
    original = [game(128, occupied), game(128, [(2, 5)])]
    compact = [SimpleNamespace(public=compact_public(g.public)) for g in original]
    before, before_lengths = public_batch(original)
    after, after_lengths = compact_public_batch(compact)
    assert torch.equal(before_lengths, after_lengths)
    for field in PUBLIC_FIELDS:
        assert torch.equal(getattr(before, field), getattr(after, field)), field
    for old, new in zip(original, compact, strict=True):
        assert len(old.public['entity_mask']) == len(new.public['entity_mask'])
        assert old.public['entity_mask'].sum() == new.public['entity_mask'].sum()
        assert not np.shares_memory(old.public['entity_features'], new.public['entity_features'])


def test_malformed_entity_field_rejected():
    g = game(128, [(2, 5)]).public
    g['entity_features'] = g['entity_features'][:, :4]
    with pytest.raises(ValueError, match='shape'):
        compact_public(g)


def test_nonzero_discarded_storage_rejected():
    g = game(128, [(2, 5)]).public
    g['entity_features'][0, 127, 0] = 1
    with pytest.raises(ValueError, match='zero padding'):
        compact_public(g)
