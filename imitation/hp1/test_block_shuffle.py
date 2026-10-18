"""Sampling membership, deterministic resume, and qualified per-row parity."""
import json
import numpy as np
import pytest
import torch
from imitation.hp1.block_shuffle import BlockShuffle
from imitation.hp1.train import parse, apply_overlay
from imitation.model.batching import build_batch
from imitation.model.store import PackedStore, sha256
from imitation.model.synthetic_store import create
from imitation.t11.sampling import epoch_indices as random_indices


def tiny_store(tmp_path, t3):
    n = 137
    root = create(tmp_path/'train', 'train', n)
    manifest = json.loads((root/'manifest.json').read_text())
    arrays = {k: np.load(root/v) for k, v in manifest['arrays'].items()}
    counts = np.arange(n) % 17
    counts[:8] = 0
    counts[8:16] = 16
    arrays['entity_offsets'] = np.r_[0, np.cumsum(counts)].astype(np.int64)
    for key in ('flat_entity_ids', 'flat_entity_levels', 'flat_entity_features'):
        arrays[key] = arrays[key][np.arange(counts.sum()) % len(arrays[key])]
    arrays['corpus_s122'] = np.arange(n) % 2 == 0
    arrays['expert_action_supervision_valid'][::13] = False
    arrays['weights'] = np.where(arrays['corpus_s122'], 2., 1.)
    if t3:
        for side in ('opp', 'own'):
            hist = arrays.pop(side+'_history')
            arrays[side+'_recent_play_ids'] = hist[:, :, 0].astype(np.int16)
            arrays[side+'_recent_play_features'] = hist[:, :, 1:]
        hist = arrays.pop('opp_abilities')
        arrays['opp_ability_ids'] = hist[:, :, 0].astype(np.int16)
        arrays['opp_ability_ages'] = hist[:, :, 1:]
        np.save(root.parent/'mask_table.npy', np.packbits(arrays.pop('action_mask'), axis=-1))
        arrays['mask_index'] = np.arange(n, dtype=np.int32)
        arrays['episode_ids'] = arrays['perspective_ids']
        arrays['episode_starts'] = np.arange(n) % 8 == 0
        arrays['source_unit'] = np.zeros(n, np.int16)
        arrays['source_row'] = np.arange(n, dtype=np.int32)
        arrays['intent_deck_index'] = arrays.pop('intent_card')
        arrays['intent_censored'] = ~arrays.pop('intent_observed')
        arrays['intent_delay_ticks'] = np.arange(n) % 13
        arrays.pop('intent_valid')
        manifest = {'role': 'train', 'rows': n, 'perspectives': [], 'arrays': {
            k: {'shape': list(v.shape), 'dtype': str(v.dtype)} for k, v in arrays.items()}}
    else:
        manifest['arrays']['corpus_s122'] = 'corpus_s122.npy'
    for k, v in arrays.items():
        np.save(root/f'{k}.npy', v)
    (root/'manifest.json').write_text(json.dumps(manifest))
    if t3:
        (root.parent/'manifest.json').write_text(json.dumps({
            'schema': 'clasher.imitation.packed.v1', 'passed': True,
            'role_manifests': {'train': sha256(root/'manifest.json')},
            'role_file_sha256': '0'*64, 'eval_spec_sha256': '1'*64, 'sidecar_manifest_sha256': '2'*64}))
        (root/'assets.npz.json').write_text(json.dumps({
            'asset_sha256': sha256(root/'assets.npz'), 'token_sha256': '3'*64}))
    return PackedStore(root, 'train', root/'assets.npz')


@pytest.mark.parametrize('t3', [False, True])
@pytest.mark.parametrize('workers', [0, 1])
def test_same_multiset_seed_resume_and_row_logic(tmp_path, t3, workers):
    store = tiny_store(tmp_path, t3)
    # Exercise lag overlays before selection and copying, including invalid rows.
    overlay = {k: store.column(k).copy() for k in (
        'expert_actions', 'expert_action_supervision_valid', 'weights')}
    overlay['weights'][::7] = 0.3
    overlay['expert_actions'][2] = 2304
    overlay['expert_action_supervision_valid'][5] = False
    apply_overlay(store, overlay, 'test-overlay')
    mode = BlockShuffle(.00008)  # many whole-perspective buffers, partial last batch
    for epoch in (0, 1):
        ix = mode.epoch_indices(store, epoch, 37)
        np.testing.assert_array_equal(np.sort(ix), np.sort(random_indices(store, epoch, 37)))
        np.testing.assert_array_equal(ix, mode.epoch_indices(store, epoch, 37))
        assert len(np.unique(ix)) == len(ix)
        assert len(mode.plan(store)) > 3
        counts = np.diff(store.column('entity_offsets'))
        for start in range(0, len(ix), 11):
            part = ix[start:start+11]
            ix[start:start+11] = part[np.argsort(counts[part], kind='stable')]
        actual = list(mode.train_loader(store, 11, ix, workers=workers))
        np.testing.assert_array_equal(torch.cat([y['index'] for _, y in actual]), ix)
        for (b, y), start in zip(actual, range(0, len(ix), 11)):
            bb, yy = build_batch(store, ix[start:start+11])
            s122 = torch.from_numpy(store.column('corpus_s122')[ix[start:start+11]])
            yy['weight'] = yy['weight'].float()*torch.where(s122 & (yy['action'] == 2304), .5, 1.)
            for k in b:
                torch.testing.assert_close(b[k], bb[k], rtol=0, atol=0)
            for k in y:
                torch.testing.assert_close(y[k], yy[k], rtol=0, atol=0)
        resumed = list(mode.train_loader(store, 11, ix[22:], workers=workers))
        for (b, y), (bb, yy) in zip(resumed, actual[2:]):
            for k in b:
                torch.testing.assert_close(b[k], bb[k], rtol=0, atol=0)
            for k in y:
                torch.testing.assert_close(y[k], yy[k], rtol=0, atol=0)
    assert not np.array_equal(mode.epoch_indices(store, 0, 37), mode.epoch_indices(store, 0, 38))


def test_default_off_and_budget_guard(tmp_path):
    assert not parse([])[0].block_shuffle
    assert '--epoch-fraction' in parse(['--block-shuffle', '--epoch-fraction', '.5'])[1]
    with pytest.raises(SystemExit):
        parse(['--block-shuffle', '--epoch-fraction', '0'])
    for invalid in (0, -1, 24.01):
        with pytest.raises(ValueError):
            BlockShuffle(invalid)
    store = tiny_store(tmp_path, True)
    with pytest.raises(ValueError, match='perspective exceeds'):
        BlockShuffle(.000001).plan(store)
    mode = BlockShuffle(.01)
    with pytest.raises(ValueError, match='loader thread'):
        next(mode.train_loader(store, 8, np.arange(8), workers=2))


def test_cross_chunk_padding_with_zero_entity_piece(tmp_path, monkeypatch):
    store = tiny_store(tmp_path, True)
    mode = BlockShuffle(.00008)
    monkeypatch.setattr(mode, 'plan', lambda _: np.array([0, 8, 16, len(store)]))
    ix = np.array([0, 8, 1, 9])
    b, y = next(mode.train_loader(store, 4, ix))
    bb, yy = build_batch(store, ix)
    s122 = torch.from_numpy(store.column('corpus_s122')[ix])
    yy['weight'] = yy['weight'].float()*torch.where(s122 & (yy['action'] == 2304), .5, 1.)
    for k in b:
        torch.testing.assert_close(b[k], bb[k], atol=0, rtol=0)
    for k in y:
        torch.testing.assert_close(y[k], yy[k], atol=0, rtol=0)


@pytest.mark.parametrize('t3', [False, True])
@pytest.mark.parametrize('workers', [0, 1])
def test_fractional_epoch_preserves_iid_prefix_and_schedule(tmp_path, t3, workers):
    import math
    store = tiny_store(tmp_path, t3)
    overlay = {k:store.column(k).copy() for k in (
        'expert_actions','expert_action_supervision_valid','weights')}
    overlay['expert_actions'][::9] = 2304
    overlay['expert_action_supervision_valid'][::13] = False
    overlay['weights'][::7] = .5
    apply_overlay(store, overlay, 'fractional-lag-test')
    mode = BlockShuffle(.00008, epoch_fraction=.5)
    for epoch in (0, 1):
        random = random_indices(store, epoch, 37)
        ordered = mode.epoch_indices(store, epoch, 37)
        assert len(ordered) == len(random)  # original T4 scheduler denominator
        n = math.ceil(len(ordered) * .5)  # qualified trainer's actual truncation
        np.testing.assert_array_equal(np.sort(ordered[:n]), np.sort(random[:n]))
        np.testing.assert_array_equal(np.sort(ordered), np.sort(random))
        np.testing.assert_array_equal(ordered, mode.epoch_indices(store, epoch, 37))
        actual = list(mode.train_loader(store, 11, ordered[:n], workers=workers))
        np.testing.assert_array_equal(torch.cat([y['index'] for _, y in actual]), ordered[:n])
        assert len(np.unique(ordered[:n])) == n
        cursor = 22
        resumed = list(mode.train_loader(store, 11, ordered[cursor:n], workers=workers))
        for (b,y),(bb,yy) in zip(resumed,actual[2:]):
            for k in b:
                torch.testing.assert_close(b[k],bb[k],atol=0,rtol=0)
            for k in y:
                torch.testing.assert_close(y[k],yy[k],atol=0,rtol=0)
    assert mode.pin() != BlockShuffle(.00008).pin()
    for invalid in (0, -1, 1.1):
        with pytest.raises(ValueError):
            BlockShuffle(.00008, invalid)


@pytest.mark.parametrize('fraction_args', [ ['--epoch-fraction', '.5'], ['--epoch-fraction=.5'] ])
def test_fraction_parser_equals_form_uses_iid_prefix(tmp_path, fraction_args):
    import math
    ext, remaining = parse(['--block-shuffle', '--shuffle-buffer-gb', '.00008', *fraction_args])
    assert ext.epoch_fraction == .5
    store = tiny_store(tmp_path, True)
    mode = BlockShuffle(ext.shuffle_buffer_gb, ext.epoch_fraction)
    random = random_indices(store, 0, 37)
    ordered = mode.epoch_indices(store, 0, 37)
    n = math.ceil(len(random)*.5)
    np.testing.assert_array_equal(np.sort(ordered[:n]),np.sort(random[:n]))
