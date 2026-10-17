"""Unit tests for imitation.hp1.train helpers (CPU, tiny synthetic tensors; no store, no GPU).

    python -m pytest imitation/hp1/test_train_helpers.py -q
End-to-end checks (fresh launch, epoch-boundary stop and resume, overlay on the real store) are the CPU smoke runs
on 04 in imitation/hp1/README.md.
"""
import json
import pickle
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pytest
import torch

from imitation.hp1 import lagshift
from imitation.hp1.test_lagshift import build, episode
from imitation.hp1.train import SmokeDev, apply_overlay, config_factory, load_overlay, model_factory, options_path
from imitation.model.network import ModelConfig, SetPolicy


def tiny_inputs(config):
    g = torch.Generator().manual_seed(0)
    return (torch.randn(config.vocab, config.descriptors, generator=g), torch.randn(576, 12, generator=g),
            torch.rand(config.vocab, generator=g) * 10)


def test_options_file_is_outside_the_fresh_output_dir(tmp_path):
    out = tmp_path / 'runs' / 'p1-cap'
    p = options_path(out)
    assert p.parent == out.parent and not str(p).startswith(str(out) + '/')


def test_config_factory_sets_shape():
    c = config_factory(6, 1536)(descriptors=57, tile_width=64)
    assert isinstance(c, ModelConfig) and c.layers == 6 and c.ffn == 1536 and c.width == 192


def test_init_loads_ema_and_rejects_mismatches(tmp_path):
    c = config_factory(1, 64)(descriptors=57, tile_width=16)
    d, t, k = tiny_inputs(c)
    src = SetPolicy(c, d, t, k)
    with torch.no_grad():
        for v in src.parameters():
            v.add_(1.)
    path = tmp_path / 'init.pt'
    torch.save({'config': asdict(c), 'ema': src.state_dict()}, path)
    got = model_factory(path)(c, d, t, k)
    assert all(torch.equal(a, b) for a, b in zip(got.state_dict().values(), src.state_dict().values()))
    with pytest.raises(ValueError, match='config'):
        model_factory(path)(config_factory(2, 64)(descriptors=57, tile_width=16), d, t, k)
    with pytest.raises(ValueError, match='buffer'):
        model_factory(path)(c, d, t, k + 1)
    fresh = model_factory(None)(c, d, t, k)
    assert not torch.equal(next(iter(fresh.parameters())), next(iter(src.parameters())))


class Dummy:
    def __init__(self):
        self.arrays = {'x': np.arange(10)}
        self.t3 = True

    def __len__(self):
        return 10_000


def test_smoke_dev_limits_rows_and_pickles():
    s = SmokeDev(Dummy())
    assert len(s) == 4096 and s.t3 and s.arrays['x'][3] == 3
    s2 = pickle.loads(pickle.dumps(s))
    assert len(s2) == 4096 and s2.t3


def make_store(tmp_path, rows):
    root = tmp_path / 'store'; train = root / 'train'; train.mkdir(parents=True)
    a = build(rows)
    (root / 'manifest.json').write_text('{"store": 1}')
    (train / 'manifest.json').write_text('{"role": "train"}')
    np.save(root / 'mask_table.npy', a.pop('mask_table'))
    for k, v in a.items():
        np.save(train / f'{k}.npy', v)
    return train


def test_overlay_roundtrip_and_hash_checks(tmp_path):
    train = make_store(tmp_path, episode(1, 20, play_at=60, legal_from_tick=0))
    out = tmp_path / 'ov'
    lagshift.main(['--store', str(train), '--out', str(out)])
    meta, arrays = load_overlay(out, train)
    assert meta['stats']['shifted_earlier'] == 1 and meta['delay_ticks'] == 27
    store = type('S', (), {})(); store.arrays = {k: np.load(train / f'{k}.npy') for k in lagshift_fields()}
    store.hashes = {}
    apply_overlay(store, arrays, 'abc')
    assert store.arrays['expert_actions'][6] == 2 * 576 + 100 and store.hashes['hp1_overlay'] == 'abc'
    np.save(train.parent / 'mask_table.npy', np.zeros((20, 289), np.uint8))
    with pytest.raises(ValueError, match='mask table'):
        load_overlay(out, train)


def test_overlay_file_tamper_detected(tmp_path):
    train = make_store(tmp_path, episode(1, 20, play_at=60, legal_from_tick=0))
    out = tmp_path / 'ov'
    lagshift.main(['--store', str(train), '--out', str(out)])
    w = np.load(out / 'weights.npy'); w[0] = 9; np.save(out / 'weights.npy', w)
    with pytest.raises(ValueError, match='changed'):
        load_overlay(out, train)
    with pytest.raises(SystemExit):
        lagshift.main(['--store', str(train), '--out', str(out)])      # written once


def lagshift_fields():
    return ('expert_actions', 'expert_action_supervision_valid', 'weights')
