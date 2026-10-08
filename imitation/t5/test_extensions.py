"""Run on a fleet host only: synthetic behavioral tests, no real fitting."""
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import torch
from imitation.model.batching import build_batch
from imitation.model.network import ModelConfig
from imitation.model.synthetic_store import create
from imitation.model.store import PackedStore
from imitation.model.evaluate import metric_rows, frequency_output, compare_paired
from .variants import create_policy, without_d1, history_indices
from .guards import role_guard, sha
from .analyze import paired_intervals
from .baseline import frequency_rows
from .resources import BoundedBatchedStore


class Extensions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        cls.tmp = Path(tempfile.mkdtemp(prefix='t5-synthetic-'))
        root = create(cls.tmp/'train', 'train', 64)
        np.save(root/'perspective_ids.npy', np.r_[np.zeros(40, np.int64), np.ones(24, np.int64)])
        cls.store = PackedStore(root, 'train')
        cls.config = ModelConfig(width=24, heads=6, layers=1, ffn=32, tile_width=16, dropout=0.)

    def model(self, variant):
        a = self.store.assets
        torch.manual_seed(9)
        m = create_policy(variant, self.config, *[torch.tensor(a[k]) for k in ('descriptors', 'tiles', 'costs')])
        if variant == 'gru':
            m.bind_store(self.store)
        return m

    def test_no_d1_invariance(self):
        b, y = build_batch(self.store, [4, 5])
        altered = {k: v.clone() for k, v in b.items()}
        t = b['types']; remove = ((t>=3)&(t<=13))|((t>=15)&(t<=17))
        altered['ids'][remove] = 301
        altered['numeric'][remove] = 123
        altered['numeric'][:, :, 15:20] += (t==18)[..., None]*99
        m = self.model('noD1').eval()
        with torch.no_grad():
            a, c = m(b, torch.empty(0, dtype=torch.long)), m(altered, torch.empty(0, dtype=torch.long))
        for key in a:
            torch.testing.assert_close(a[key], c[key], rtol=0, atol=0)
        out = without_d1(b)
        self.assertFalse(out['valid'][remove].any())
        self.assertTrue(torch.equal(b['action_mask'], out['action_mask']))

    def test_history_window_boundary(self):
        h, valid, n = history_indices([0, 31, 35, 40, 63], np.array([0, 40]))
        self.assertEqual(n.tolist(), [1, 32, 32, 1, 24])
        self.assertEqual(h[2].tolist(), list(range(4, 36)))
        self.assertEqual(h[3][valid[3]].tolist(), [40])
        self.assertTrue(np.all(h <= np.array([0, 31, 35, 40, 63])[:, None]))

    def test_gru_causal_batch_independence_and_context_grad(self):
        m = self.model('gru').eval()
        b, _ = build_batch(self.store, [35, 40, 63]); b['row_index'] = torch.tensor([35, 40, 63])
        with torch.no_grad():
            together = m.encode(b)
            for j, i in enumerate([35, 40, 63]):
                one, _ = build_batch(self.store, [i]); one['row_index'] = torch.tensor([i])
                torch.testing.assert_close(together[j, 0], m.encode(one)[0, 0], atol=2e-6, rtol=2e-6)
        # Unique past-only token receives a gradient through checkpoint replay.
        original = m.history_store
        class Proxy:
            pass
        proxy = Proxy(); proxy.__dict__.update(original.__dict__)
        proxy.arrays = dict(original.arrays)
        proxy.arrays['hand_ids'] = np.array(original.arrays['hand_ids'])
        proxy.arrays['hand_ids'][34, 0] = 350
        m.bind_store(proxy); m.train()
        one, _ = build_batch(proxy, [35]); one['row_index'] = torch.tensor([35])
        m.encode(one)[:, 0].square().sum().backward()
        self.assertGreater(m.card_embed.weight.grad[350].abs().sum().item(), 0)

    def test_role_hash_guards(self):
        p = self.tmp/'train'
        (p.parent/'manifest.json').write_text('{}')
        manifest = {'role_manifests': {'train': sha(p/'manifest.json')},
                    'store_manifest_sha256': sha(p.parent/'manifest.json')}
        role_guard(p, 'train', manifest)
        with self.assertRaises(ValueError): role_guard(p, 'eval', manifest)
        with self.assertRaises(ValueError): role_guard(p, 'train', manifest, heldout=True)
        bad = dict(manifest); bad['store_manifest_sha256'] = '0'*64
        with self.assertRaises(ValueError): role_guard(p, 'train', bad)

    def test_baseline_eligibility_alignment(self):
        b, y = build_batch(self.store, np.arange(16))
        counts = {'gate': np.ones((33, 3)), 'cards': np.ones(360), 'tiles': np.ones((360, 576))}
        o = frequency_output(b['action_mask'], b['ids'][:, :4], torch.arange(16), torch.zeros(16), counts)
        rows = metric_rows(o, y, b['ids'][:, :4])
        comparison = compare_paired(rows, rows, y['perspective'].numpy(), resamples=100, seed=2026100805)
        self.assertTrue(all(v['delta']==0 and v['ci95']==[0, 0] for v in comparison.values()))
        altered = dict(rows); altered['tile_nll'] = rows['tile_nll'].copy(); altered['tile_nll'][0] = np.nan
        with self.assertRaises(ValueError): compare_paired(rows, altered, y['perspective'].numpy(), 10)

    def test_bootstrap_whole_clusters_and_undefined(self):
        from imitation.model.evaluate import _cluster_ci
        clusters = np.array([1, 1, 1, 2, 3, 3])
        values = np.array([1., 2., 3., np.nan, 20., 30.])
        result = paired_intervals({'x': values, 'empty': values*float('nan')}, clusters, 10000)
        np.testing.assert_array_equal(result['x']['ci95'], _cluster_ci(values, clusters, 10000, 2026100805))
        self.assertEqual(result['empty']['valid_resamples'], 0)
        self.assertEqual(result['empty']['undefined_resamples'], 10000)
        self.assertEqual(result['x']['n'], 5)

    def test_zero_frequency_is_not_an_unregistered_pseudocount(self):
        counts = {'gate': np.tile([100., 10., 0.], (33, 1)),
                  'cards': np.ones(360), 'tiles': np.zeros((360, 576))}
        result = frequency_rows(self.store, np.array([0, 1, 2]), counts)
        self.assertAlmostEqual(result['joint_nll'][2], -np.log(1e-300), places=10)
        self.assertTrue(np.isnan(result['card_nll'][1]))

    def test_rss_release_leaves_every_feature_and_target_unchanged(self):
        indices = np.array([0, 3, 7, 35, 40, 63])
        before = build_batch(self.store, indices)
        after = BoundedBatchedStore(self.store)[indices]
        again = BoundedBatchedStore(self.store)[indices]
        for expected, actual, repeated in zip(before, after, again):
            for key in expected:
                torch.testing.assert_close(expected[key], actual[key], rtol=0, atol=0)
                torch.testing.assert_close(expected[key], repeated[key], rtol=0, atol=0)


if __name__ == '__main__':
    unittest.main()
