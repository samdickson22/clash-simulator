"""Local fixtures only. No SSH, live paths, launch, signals, or model loading."""
import base64
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('copy_receipts', HERE/'copy_next_receipts_05.py')
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)


def raw(value):
    return (json.dumps(value, indent=2)+'\r\n').encode()


def receipts(size):
    phase = C.SIZES[size]
    out = C.SOURCE+'/'+phase
    cfg = C.W.registered_config(size)
    args = dict(store=str(C.W.SNAPSHOT/C.W.STORE), out=out, device='cuda', threads=3,
                max_gpu_hours=64, dev_cap=400000, hog_share=0.5, max_row_exposure=5.0, drop_ages=0.05,
                train_frac=1.0, seed=2026102001, bs=512, patience=2, epochs=8, eval_every=1,
                warmup_steps=0, steps_per_epoch=0, lr=3e-4 if size == 'S100' else 2e-4,
                wd=1e-4 if size == 'S100' else 0.01, amp='none' if size == 'S100' else 'bf16')
    args.update({k:v for k,v in cfg.items() if k not in ('n_cards','n_bodies')})
    original = json.loads((HERE/'next_eval_original.json').read_bytes())['files']
    run = dict(schema='clasher.pretrain_v1.bc-run.v1', args=args, cfg=cfg, rows=8143577,
               store=args['store'], seed=2026102001,
               code_sha256={n:original['bot/pretrain_v1/'+n] for n in ('train_bc.py','model.py','featurize.py')},
               feature_hash='ce6e509ee43a2a4a8c484261b5341b9a3f1b0c71a1a77a2024de89a80fa4773d')
    summary = dict(best_ep=3, wall_h=1, gate_bias=0, dev_cal={k:0.1 for k in
                   ('dev_cal/all/joint_nll','dev_cal/all/ece','dev_cal/hog/joint_nll')})
    selected = dict(file='anchor.pt', smoke=False, admitted=True, eligible=1, selected=out+'/ep03.pt',
                    ep=3, seed=2026102001, sha256=C.digest(b'anchor'),
                    selection=dict(eligible=True, seed=2026102001, ep=3, ckpt=out+'/ep03.pt'))
    return {'run.json':raw(run), 'summary.json':raw(summary), 'selection.json':raw(selected)}


def fixture(root, size):
    phase = C.SIZES[size]
    data = receipts(size)
    hashes = {}
    for n,b in data.items():
        p = root/('select-'+phase if n == 'selection.json' else phase)/n
        p.parent.mkdir(exist_ok=True); p.write_bytes(b)
        hashes[str(p.relative_to(root))] = C.digest(b)
    anchor = root/('select-'+phase)/'anchor.pt'
    anchor.write_bytes(b'anchor'); hashes[str(anchor.relative_to(root))] = C.digest(b'anchor')
    state = root/'allocation-0102'; state.mkdir(exist_ok=True)
    allocation = dict(controller_sha256=C.CONTROLLER, phases={'next-S100':'127x02','next-M100':'127x01'})
    ap = state/'allocation.json'; ap.write_bytes(raw(allocation))
    claim = dict(controller_sha256=C.CONTROLLER, phase=phase, host=allocation['phases'][phase], allocation_sha256=C.digest(ap.read_bytes()))
    for name,value in [('claim',claim), ('bundle',dict(controller_sha256=C.CONTROLLER, files=hashes)),
                       ('published',dict(controller_sha256=C.CONTROLLER, phase=phase, files=hashes))]:
        (state/(name+'-'+phase+'.json')).write_bytes(raw(value))


def remote(root):
    # Execute the actual fixed helper locally against one substituted temporary root.
    script = C.REMOTE.replace(repr(C.SOURCE), repr(str(root)), 1)
    return json.loads(subprocess.check_output([sys.executable, '-B', '-c', script]))


def response(root):
    value = remote(root)
    for size in C.SIZES:
        if value.get(size, {}).get('status') == 'ready':
            b = value[size]['binding']
            b['source'] = C.SOURCE+'/'+C.SIZES[size]
            b['selected'] = C.SOURCE+'/select-'+C.SIZES[size]
    return value


class CopyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src = Path(self.tmp.name)/'source'; self.src.mkdir()
        self.dst = Path(self.tmp.name)/'dest'; self.dst.mkdir()

    def ready(self):
        for size in C.SIZES:
            fixture(self.src, size)
        return response(self.src)

    def test_missing_then_atomic_complete_one_connection_each(self):
        with patch.object(C, 'fetch', return_value=response(self.src)) as fetch:
            done, wait = C.attempt(self.dst)
            self.assertFalse(done); self.assertEqual(len(wait), 2); fetch.assert_called_once()
        value = self.ready()
        original = C.rename_new
        def rename(path, dest):
            self.assertFalse(dest.exists())
            self.assertEqual({p.name for p in path.iterdir()}, {'run.json','summary.json','copy-receipt.json'})
            self.assertEqual((path/'run.json').read_bytes(), receipts(dest.name)['run.json'])
            self.assertEqual((path/'summary.json').read_bytes(), receipts(dest.name)['summary.json'])
            return original(path, dest)
        with patch.object(C, 'fetch', return_value=value) as fetch, patch.object(C, 'rename_new', rename):
            done, wait = C.attempt(self.dst)
            fetch.assert_called_once()
        self.assertEqual(set(done), set(C.SIZES)); self.assertFalse(wait)

    def test_first_size_independent_and_idempotent(self):
        fixture(self.src, 'S100')
        with patch.object(C, 'fetch', side_effect=lambda: response(self.src)):
            first, wait = C.attempt(self.dst)
            inode = (self.dst/'next-run-receipts/S100').stat().st_ino
            second, _ = C.attempt(self.dst)
        self.assertEqual(first, second); self.assertEqual(len(wait), 1)
        self.assertEqual((self.dst/'next-run-receipts/S100').stat().st_ino, inode)

    def test_conflicts_and_stale_binding_never_overwritten(self):
        value = self.ready()
        with patch.object(C, 'fetch', return_value=value):
            C.attempt(self.dst)
        p = self.dst/'next-run-receipts/S100/run.json'; p.write_bytes(b'conflict')
        with self.assertRaisesRegex(RuntimeError, 'conflict'):
            C.publish(self.dst, 'S100', value['S100'])
        self.assertEqual(p.read_bytes(), b'conflict')
        p.write_bytes(receipts('S100')['run.json'])
        changed = copy.deepcopy(value['S100']); changed['binding']['receipts']['claim'] = '0'*64
        with self.assertRaisesRegex(RuntimeError, 'conflict'):
            C.publish(self.dst, 'S100', changed)

    def test_no_local_symlink(self):
        value = self.ready()['S100']
        (self.dst/'next-run-receipts').symlink_to(self.src, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, 'symlink'):
            C.publish(self.dst, 'S100', value)
        (self.dst/'next-run-receipts').unlink()
        C.publish(self.dst, 'S100', value)
        p = self.dst/'next-run-receipts/S100/run.json'; p.unlink(); p.symlink_to(self.src/'next-S100/run.json')
        with self.assertRaisesRegex(RuntimeError, 'symlink'):
            C.publish(self.dst, 'S100', value)

    def test_hash_mismatch_and_scientific_mismatch(self):
        value = self.ready()['S100']
        value['files']['run.json']['sha256'] = '0'*64
        with self.assertRaisesRegex(RuntimeError, 'hash mismatch'):
            C.publish(self.dst, 'S100', value)
        value = self.ready()['S100']
        b = receipts('M')['run.json']
        value['files']['run.json'] = dict(base64=base64.b64encode(b).decode(), sha256=C.digest(b))
        value['binding']['files']['next-S100/run.json'] = C.digest(b)
        with self.assertRaisesRegex(RuntimeError, 'registered'):
            C.publish(self.dst, 'S100', value)
        self.assertFalse((self.dst/'next-run-receipts').exists())

    def test_failed_local_write_leaves_no_publication(self):
        value = self.ready()['S100']
        with patch.object(C.os, 'fsync', side_effect=OSError('fixture disk error')):
            with self.assertRaises(OSError):
                C.publish(self.dst, 'S100', value)
        self.assertFalse((self.dst/'next-run-receipts/S100').exists())
        self.assertFalse(list((self.dst/'next-run-receipts').iterdir()))

    def test_raced_destination_never_replaced(self):
        value = self.ready()['S100']
        original = C.rename_new
        def race(source, dest):
            dest.mkdir()
            return original(source, dest)
        with patch.object(C, 'rename_new', race):
            with self.assertRaises(FileExistsError):
                C.publish(self.dst, 'S100', value)
        self.assertEqual(list((self.dst/'next-run-receipts/S100').iterdir()), [])

    def test_duplicate_owner(self):
        lock = self.dst/'owner.lock'
        with C.locked(lock):
            with self.assertRaises(BlockingIOError):
                with C.locked(lock):
                    self.fail('duplicate acquired')

    def test_remote_missing_selection_and_provisional_wait(self):
        self.ready()
        p = self.src/'select-next-S100/selection.json'; p.unlink()
        self.assertEqual(remote(self.src)['S100']['status'], 'missing')
        fixture(self.src, 'S100')
        d = json.loads(p.read_bytes()); d['admitted'] = False; d['file'] = 'PROVISIONAL-not-admitted.pt'
        p.write_bytes(raw(d))
        self.assertEqual(remote(self.src)['S100']['status'], 'missing')

    def test_remote_bad_present_json_anchor_and_published_hash_fail_closed(self):
        for which in ('json', 'anchor', 'publication'):
            self.ready()
            p = self.src/'next-S100/run.json'
            if which == 'json': p.write_bytes(b'{')
            if which == 'anchor': (self.src/'select-next-S100/anchor.pt').write_bytes(b'changed')
            if which == 'publication': p.write_bytes(p.read_bytes()+b' ')
            self.assertIn('error', remote(self.src))

    def test_remote_read_only_and_source_no_symlinks(self):
        self.ready()
        before = {str(p):p.read_bytes() for p in self.src.rglob('*') if p.is_file()}
        remote(self.src)
        self.assertEqual(before, {str(p):p.read_bytes() for p in self.src.rglob('*') if p.is_file()})
        p = self.src/'next-S100/run.json'; p.unlink(); p.symlink_to(self.src/'next-M100/run.json')
        self.assertIn('source symlink', remote(self.src)['error'])

    def fake_ssh(self, code):
        real = subprocess.Popen
        def launch(command, **kwargs):
            self.assertEqual(command[-2:], ['127x08', 'python3 -B -'])
            self.assertNotIn('shell', kwargs)
            return real([sys.executable, '-B', '-c', code], **kwargs)
        return patch.object(C.subprocess, 'Popen', side_effect=launch)

    def test_bounded_response_and_network_failure(self):
        with self.fake_ssh('import sys; sys.stdout.write("x"*2097153)'):
            with self.assertRaisesRegex(RuntimeError, '2 MiB'):
                C.fetch()
        with self.fake_ssh('raise SystemExit(255)'):
            with self.assertRaises(C.TransportError):
                C.attempt(self.dst)
        self.assertFalse(list(self.dst.iterdir()))

    def test_fetch_timeout_is_retryable(self):
        with self.fake_ssh('import time; time.sleep(2)'), patch.object(C.selectors.DefaultSelector, 'select', return_value=[]):
            with self.assertRaisesRegex(C.TransportError, 'timeout'):
                C.attempt(self.dst)

    def test_owner_records_network_wait_and_done_with_identity(self):
        value = self.ready()
        original = Path.read_text
        def read_text(path, *args, **kwargs):
            if str(path) == '/proc/self/stat': return '1 (fixture) '+ ' '.join(['0']*19+['12345'])
            if str(path) == '/proc/sys/kernel/random/boot_id': return 'fixture-boot'
            if str(path) == '/proc/meminfo': return 'MemAvailable: 40000000 kB\n'
            return original(path, *args, **kwargs)
        def slept(seconds):
            self.assertEqual(seconds, 60)
            state = json.loads((self.dst/'next-run-receipts-owner.json').read_bytes())
            self.assertEqual(state['status'], 'waiting')
            self.assertEqual(state['last_failure'], 'fixture network failure')
        with patch.object(C, 'ROOT', self.dst), patch.object(C.W, 'verify_review'), \
             patch.object(C.os, 'uname', return_value=SimpleNamespace(nodename='127x05')), \
             patch.object(C.os, 'getpriority', return_value=10), patch.object(C.os, 'getloadavg', return_value=(1,1,1)), \
             patch.object(Path, 'read_text', read_text), patch.object(C.time, 'sleep', side_effect=slept) as sleep, \
             patch.object(C, 'fetch', side_effect=[C.TransportError('fixture network failure'), value]) as fetch:
            C.run('f'*40)
        state = json.loads((self.dst/'next-run-receipts-owner.json').read_bytes())
        self.assertEqual(state['status'], 'done'); self.assertEqual(set(state['done']), set(C.SIZES))
        self.assertEqual(state['start'], '12345'); self.assertEqual(state['boot_id'], 'fixture-boot')
        self.assertEqual(state['script_sha256'], C.digest(C.HERE.read_bytes()))
        self.assertEqual(fetch.call_count, 2); sleep.assert_called_once()

    def test_local_ssh_setup_errors_fail_closed(self):
        for target in (C.tempfile, C.subprocess):
            name = 'TemporaryFile' if target is C.tempfile else 'Popen'
            with patch.object(target, name, side_effect=OSError('local setup failure')):
                with self.assertRaisesRegex(OSError, 'local setup failure'):
                    C.attempt(self.dst)

    def test_crash_after_rename_reuse_restores_durability(self):
        value = self.ready()['S100']
        parent = self.dst/'next-run-receipts'
        original = C.sync
        def interrupted(path):
            if path == parent: raise OSError('fixture crash after rename')
            original(path)
        with patch.object(C, 'sync', side_effect=interrupted):
            with self.assertRaisesRegex(OSError, 'after rename'):
                C.publish(self.dst, 'S100', value)
        self.assertTrue((parent/'S100/run.json').is_file())
        with patch.object(C, 'sync', wraps=C.sync) as sync, patch.object(C.os, 'fsync', wraps=C.os.fsync) as fsync:
            C.publish(self.dst, 'S100', value)
        self.assertEqual([c.args[0] for c in sync.call_args_list], [parent/'S100', parent])
        self.assertEqual(fsync.call_count, 5)

    def test_local_error_not_transport_retry(self):
        with patch.object(C, 'fetch', return_value=self.ready()), patch.object(C, 'publish', side_effect=OSError('disk')):
            with self.assertRaisesRegex(OSError, 'disk'):
                C.attempt(self.dst)


if __name__ == '__main__':
    unittest.main()
