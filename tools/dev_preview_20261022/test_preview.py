"""CPU and mock tests. No CUDA calls, remote access, engine, or real data."""
import copy
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np
import torch

import preview as P

ARCHIVE = Path('/mpac/sdicks02/jobs/clasher/pretrain-v1/interim-20261022-b240/source-40ea0b503.tar')
MAP = Path('/mpac/sdicks02/jobs/clasher/supplemental-bc-20261022/staging/source-map.json')


class PreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)
        cls.tmp = tempfile.TemporaryDirectory(prefix='dev-preview-cpu-')
        cls.root = Path(cls.tmp.name)
        cls.source = cls.root/'source'
        # Extract only hash-pinned regular source files into our fresh CPU fixture.
        entries = json.loads(MAP.read_text())
        with tarfile.open(ARCHIVE) as tar:
            for name in entries:
                m = tar.getmember(name)
                assert m.isfile()
                p = cls.source/name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(tar.extractfile(m).read())
        P.verify_map(cls.source, MAP, P.MAPS['source'], 73)
        cls.modules = P.import_reviewed(cls.source)
        F = cls.modules['featurize']
        cat = F.catalog()
        cls.cfg = dict(P.CFG, n_cards=cat.n_cards, n_bodies=cat.n_bodies)
        cls.model = cls.modules['model'].PolicyV1(**cls.cfg)
        cls.ck = dict(model=cls.model.state_dict(), cfg=cls.cfg, feature_hash=P.FEATURE,
                      seed=2026102002, ep=0, dev={'ep': 0, 'step': 6500, 'dev/all/joint_nll': 1.0})
        cls.ckpath = cls.root/'ep00.pt'
        torch.save(cls.ck, cls.ckpath)
        cls.c = dict(path=str(cls.ckpath), sha256=P.sha256(cls.ckpath), bytes=cls.ckpath.stat().st_size,
                     seed=2026102002, ep=0)
        record = dict(tick=100, units=[],
                      towers=[dict(owner=o, kind=k, side=s, hp_frac=1.0, alive=True) for o, k, s in F.TOWER_ORDER],
                      hand=dict(cards=['HogRider', 'Musketeer', 'Zap', 'Cannon'], next='Skeletons'),
                      elixir=5.0, events=[])
        feat = F.observe(record, None, F.History())
        batch = cls.modules['model'].collate([feat, feat])
        batch = {k: v.numpy() for k, v in batch.items()}
        batch.update(gate=np.array([0, 1], np.int8), slot=np.array([-1, 0], np.int8),
                     tile=np.array([-1, 400], np.int16), actor=np.ones(2, bool),
                     w_ipw=np.ones(2, np.float32), w_dom=np.ones(2, np.float32),
                     value=np.array([0, 2], np.int8), hog=np.ones(2, bool),
                     hogzap=np.ones(2, bool), vanilla=np.ones(2, bool),
                     tile_ok=np.ones((2, F.NTILE), bool))
        cls.batch = batch

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def fixture_store(self):
        calls = []
        # FINAL labels live outside batch(). They must never be requested.
        def batch(idx):
            calls.append(list(idx))
            self.assertEqual(list(idx), [1, 3])
            return copy.deepcopy(self.batch)
        store = types.SimpleNamespace(n=4, split=np.array([2, 1, 0, 1]), batch=batch)
        return store, calls

    def checkpoint(self, ck):
        stream = io.BytesIO()
        torch.save(ck, stream)
        stream.seek(0)
        return P.checkpoint_model(stream, self.c, self.modules, torch)

    def test_real_reviewed_full_dev_metrics_and_in_memory_calibration(self):
        store, calls = self.fixture_store()
        idx = P.dev_indices(store, np, rows=4, dev_rows=2)
        before = P.sha256(self.ckpath)
        result = P.evaluate_candidate(self.c, P.DevOnly(store, np), idx, self.modules, torch, 'cpu')
        self.assertEqual(before, P.sha256(self.ckpath))
        self.assertEqual(calls, [[1, 3]]*3)
        for kind in ('raw', 'in_memory_dev_calibrated'):
            metrics = result['metrics'][kind]
            for key in ('all/joint_nll', 'all/card_top1', 'all/ece', 'all/value_brier', 'hog/joint_nll'):
                self.assertTrue(np.isfinite(metrics[key]), key)
        self.assertEqual(set(self.ck), {'model', 'cfg', 'feature_hash', 'seed', 'ep', 'dev'})

    def test_dev_guard_refuses_final_train_invalid_and_empty(self):
        store, calls = self.fixture_store()
        dev = P.DevOnly(store, np)
        for bad in ([0], [2], [-1], [4], []):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                dev.batch(np.array(bad, dtype=int))
        self.assertEqual(calls, [])
        with self.assertRaisesRegex(ValueError, 'full DEV'):
            P.dev_indices(store, np, rows=4, dev_rows=1)

    def test_nonfinite_inputs_and_metrics_refused(self):
        store, _ = self.fixture_store()
        def batch(idx):
            b = copy.deepcopy(self.batch)
            b['w_ipw'][0] = np.nan
            return b
        store.batch = batch
        with self.assertRaisesRegex(ValueError, 'nonfinite DEV'):
            P.DevOnly(store, np).batch(np.array([1, 3]))
        for bad in (float('inf'), float('nan'), -float('inf')):
            with self.assertRaises(ValueError):
                P.finite_report({'nested': [bad]})

    def test_strict_checkpoint_refusals(self):
        cases = [('feature', lambda ck: ck.update(feature_hash='bad')),
                 ('config', lambda ck: ck['cfg'].update(drop=0.0)),
                 ('incomplete', lambda ck: ck.pop('dev')),
                 ('wrong epoch', lambda ck: ck.update(ep=1)),
                 ('dtype metadata', lambda ck: ck.update(config={'dtype': 'float64'})),
                 ('dtype weight', lambda ck: ck['model'].update(gate_bias=torch.tensor(0., dtype=torch.float64))),
                 ('nonfinite', lambda ck: ck['model'].update(gate_bias=torch.tensor(float('nan')))),
                 ('missing weight', lambda ck: ck['model'].pop('cls')),
                 ('extra weight', lambda ck: ck['model'].update(unexpected=torch.tensor(0.)))]
        for name, mutate in cases:
            ck = dict(self.ck, cfg=dict(self.ck['cfg']), model=dict(self.ck['model']))
            mutate(ck)
            with self.subTest(name=name), self.assertRaises((ValueError, RuntimeError)):
                self.checkpoint(ck)

    def test_wrong_hash_size_symlink_and_mutating_input_refused(self):
        store, _ = self.fixture_store()
        for delta in ({'sha256': '0'*64}, {'bytes': self.c['bytes']+1}):
            with self.assertRaises(ValueError):
                P.evaluate_candidate(dict(self.c, **delta), store, [1, 3], self.modules, torch, 'cpu')
        link = self.root/'linked.pt'
        link.symlink_to(self.ckpath)
        with self.assertRaises(ValueError):
            P.evaluate_candidate(dict(self.c, path=str(link)), store, [1, 3], self.modules, torch, 'cpu')
        def changed(*args):
            os.utime(self.ckpath, ns=(self.ckpath.stat().st_atime_ns, self.ckpath.stat().st_mtime_ns+1))
            return {}
        with patch.object(P, 'measure', side_effect=changed), self.assertRaisesRegex(ValueError, 'changed'):
            P.evaluate_candidate(self.c, store, [1, 3], self.modules, torch, 'cpu')

    def test_pinned_map_rejects_changed_bytes_and_extra_files(self):
        with tempfile.TemporaryDirectory(dir=self.root) as td:
            root = Path(td)
            (root/'x').write_text('original')
            m = self.root/'mock-map.json'
            m.write_text(json.dumps({'x': dict(bytes=8, sha256=P.sha256(root/'x'))}))
            P.verify_map(root, m, P.sha256(m), 1)
            with self.assertRaisesRegex(ValueError, 'map SHA'):
                P.verify_map(root, m, '0'*64, 1)
            (root/'x').write_text('modified')
            with self.assertRaisesRegex(ValueError, 'mapped file'):
                P.verify_map(root, m, P.sha256(m), 1)
            (root/'unexpected.py').touch()
            with self.assertRaisesRegex(ValueError, 'tree differs'):
                P.verify_map(root, m, P.sha256(m), 1)

    def test_inventory_requires_external_finalized_raw_sha_pins(self):
        d = json.loads((Path(__file__).parent/'inventory.template.json').read_text())
        with self.assertRaises(ValueError):
            P.validate_inventory(d)
        for c in d['candidates']:
            c.update(sha256='a'*64, bytes=self.c['bytes'], finalized=True)
            c['path'] = str(P.JOB/'inputs'/c['origin_host']/f"M-s{c['seed']}"/('a'*64)/f"ep{c['ep']:02d}.pt")
        P.validate_inventory(d)
        for mutate in (lambda x: x.update(feature_hash='bad'),
                       lambda x: x.update(source_commit='bad'),
                       lambda x: x['cfg'].update(drop=0),
                       lambda x: x['candidates'][0].update(finalized=False),
                       lambda x: x['candidates'][0].update(seed=2026102008),
                       lambda x: x['candidates'][0].update(origin_path='/tmp/best.pt'),
                       lambda x: x['candidates'][0].update(path='/tmp/ep00.pt')):
            bad = copy.deepcopy(d)
            mutate(bad)
            with self.assertRaises(ValueError):
                P.validate_inventory(bad)

    def test_external_receipt_binds_origin_and_finalization_evidence(self):
        root = Path(__file__).parent
        d = json.loads((root/'inventory.frozen.json').read_text())
        P.validate_inventory(d)
        original = Path('/mpac/sdicks02/jobs/clasher/interim-dev-preview-inputs-20261022/ep01-parent-collection/receipt.json')
        d['collection_receipt_path'] = str(original)
        P.verify_collection_receipt(d)
        with self.assertRaisesRegex(ValueError, 'receipt SHA'):
            P.verify_collection_receipt(dict(d, collection_receipt_sha256='0'*64))
        for change in (lambda r: r['rows'][0]['after'].update(inode=0),
                       lambda r: r.update(source_commit='bad'),
                       lambda r: r.update(final_unused=False),
                       lambda r: r['rows'][0].update(local_sha256='0'*64)):
            r = json.loads(original.read_text())
            change(r)
            path = self.root/'bad-receipt.json'
            path.write_text(json.dumps(r))
            with self.assertRaises(ValueError):
                P.verify_collection_receipt(dict(d, collection_receipt_path=str(path),
                                                 collection_receipt_sha256=P.sha256(path)))

    def test_inventory_raw_hash_and_output_path_refusals(self):
        with self.assertRaisesRegex(ValueError, 'inventory SHA'):
            P.load_inventory(Path(__file__).parent/'inventory.template.json', '0'*64)
        with tempfile.TemporaryDirectory(dir=self.root) as td:
            job = Path(td)
            (job/'outputs').mkdir()
            with patch.object(P, 'JOB', job):
                out = P.reserve_output(str(job/'outputs/fresh'))
                self.assertEqual(out.stat().st_mode & 0o777, 0o700)
                with self.assertRaises(FileExistsError):
                    P.reserve_output(str(out))
                with self.assertRaises(ValueError):
                    P.reserve_output(str(job/'selection.json'))
                (job/'outputs/alias').symlink_to(out)
                with self.assertRaises(ValueError):
                    P.reserve_output(str(job/'outputs/alias'))

    def test_outputs_are_exclusive_preview_only_and_private(self):
        with tempfile.TemporaryDirectory(dir=self.root) as td:
            out = Path(td)/'fresh'
            out.mkdir(mode=0o700)
            P.write_report(out, 'a'*64, [{'metrics': {'all/ece': 0.1}}], None)
            self.assertEqual([p.name for p in out.iterdir()], ['unselected-dev-preview.json'])
            report = json.loads((out/'unselected-dev-preview.json').read_text())
            self.assertFalse(report['selected'])
            self.assertEqual(report['purpose'], 'unselected-DEV-PREVIEW')
            self.assertEqual(out.stat().st_mode & 0o777, 0o700)
            with self.assertRaises(FileExistsError):
                P.write_report(out, 'a'*64, [], None)


if __name__ == '__main__':
    unittest.main()
