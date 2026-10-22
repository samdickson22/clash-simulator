"""CPU-only tests. All fixture paths are temporary; no fleet jobs are touched."""
import concurrent.futures
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


m = load('allocation_test_target', HERE / 'allocation_0102.py')
legacy = load('immutable_legacy', HERE / 'followup_08.py')


class AllocationTests(unittest.TestCase):
    def test_exclusive_reservation_races_legacy_open_x(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(30):
                p = Path(tmp) / f'intent-{i}.json'
                barrier = threading.Barrier(2)

                def reserve():
                    barrier.wait()
                    try:
                        m.exclusive(p, {'reserved_by': 'new-owner'})
                        return 'new-owner'
                    except FileExistsError:
                        return None

                def old_launch_intent():
                    barrier.wait()
                    try:
                        with p.open('x') as f:
                            json.dump({'reserved_by': 'legacy'}, f)
                        return 'legacy'
                    except FileExistsError:
                        return None

                with concurrent.futures.ThreadPoolExecutor(2) as pool:
                    a, b = pool.submit(reserve), pool.submit(old_launch_intent)
                    winners = [x for x in (a.result(), b.result()) if x]
                self.assertEqual(len(winners), 1)
                self.assertEqual(m.read(p)['reserved_by'], winners[0])

    def test_real_legacy_preserves_m50_and_m25_then_refuses_next_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); out = root / 'out'; old = root / 'old'
            old.mkdir(); out.mkdir()
            for size in ('S', 'M'):
                (old / f'peaks-{size}.json').write_text(json.dumps(m.PEAKS[size]))
            m.exclusive(out / 'intent-next-S100.json', {'reserved_by': 'new-owner'})
            new = root / 'new'; new.mkdir()
            (new / 'STORE-READY.json').write_text(json.dumps(dict(store_name='store', batches=83, rows=8143577, manifest_sha256='same')))
            calls = []
            fake = types.SimpleNamespace(log=lambda *a: None, reap=lambda: None)
            fake.train_cmd = lambda run, size, extra: ['train', str(run)]
            fake.select_cmd = lambda runs, selected: ['select', str(selected)]

            def launch(name, command, cap, log):
                calls.append(name)
                dest = out / name
                dest.mkdir()
                artifact = dest / ('selection.json' if name.startswith('select-') else 'summary.json')
                artifact.write_text('{}')
                return types.SimpleNamespace(pid=123, wait=lambda: 0)

            fake.launch = launch
            fake_spec = types.SimpleNamespace(loader=types.SimpleNamespace(exec_module=lambda module: None))
            with patch.object(legacy, 'OUT', out), patch.object(legacy, 'OLD', old), patch.object(legacy, 'NEW_STORE', new), \
                 patch.object(legacy, 'sha', return_value='same'), \
                 patch.object(legacy.os, 'uname', return_value=types.SimpleNamespace(nodename='127x08')), \
                 patch.object(legacy.importlib.util, 'spec_from_file_location', return_value=fake_spec), \
                 patch.object(legacy.importlib.util, 'module_from_spec', return_value=fake):
                with self.assertRaises(FileExistsError):
                    legacy.main()
            self.assertEqual(calls, ['M50', 'select-M50', 'M25', 'select-M25'])
            self.assertTrue((out / 'completed-M50.json').exists())
            self.assertTrue((out / 'completed-select-M50.json').exists())
            self.assertTrue((out / 'completed-M25.json').exists())
            self.assertTrue((out / 'completed-select-M25.json').exists())
            self.assertFalse((out / 'next-S100').exists())

    def test_changed_or_missing_reservation_refuses_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); state = root / 'state'; state.mkdir()
            reservations = {}
            for phase in m.PHASES:
                p = root / f'intent-{phase}.json'; m.exclusive(p, {'host': m.PHASES[phase]})
                reservations[p.name] = m.sha(p)
            a = dict(controller_sha256='go', phases=m.PHASES,
                     mechanism='legacy-exclusive-prelaunch-intents', reservations=reservations,
                     source_inventory_sha256='inventory', dataset_inventory_sha256='inventory')
            m.exclusive(state / 'allocation.json', a)
            original = m.checked_files
            def check(root_arg, files):
                if root_arg == root:
                    original(root_arg, files)
            with patch.object(m, 'OUT', root), patch.object(m, 'STATE', state), \
                 patch.object(m, 'reviewed'), patch.object(m, 'sha', side_effect=lambda p: 'inventory' if p.parent == m.INPUTS else __import__('hashlib').sha256(p.read_bytes()).hexdigest()), \
                 patch.object(m, 'checked_files', side_effect=check), patch.object(m, 'read', side_effect=lambda p: a if p == state / 'allocation.json' else {'files': {'x': 'y'}}):
                self.assertEqual(m.allocation('go'), a)
                (root / 'intent-next-S100.json').write_text('changed')
                with self.assertRaisesRegex(RuntimeError, 'hash mismatch'):
                    m.allocation('go')

    def test_reservation_collision_never_publishes_allocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); state = root / 'state'
            m.exclusive(root / 'intent-next-M100.json', {'owner': 'legacy'})
            with patch.object(m, 'OUT', root), patch.object(m, 'STATE', state), \
                 patch.object(m, 'reviewed'), patch.object(m, 'validate_legacy'), \
                 patch.object(m, 'checked_files'), patch.object(m, 'read', return_value={'files': {}}):
                with self.assertRaises(FileExistsError):
                    m.handoff('go')
            self.assertFalse((state / 'allocation.json').exists())
            self.assertEqual(m.read(root / 'intent-next-M100.json'), {'owner': 'legacy'})

    def test_publication_is_atomic_compatible_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); state = root / 'state'; incoming = state / 'incoming-next-M100'
            selected = incoming / 'select-next-M100'; selected.mkdir(parents=True)
            (selected / 'anchor.pt').write_bytes(b'checkpoint')
            selection = dict(file='anchor.pt', smoke=False, sha256=m.sha(selected / 'anchor.pt'))
            (selected / 'selection.json').write_text(json.dumps(selection))
            run = incoming / 'next-M100'; run.mkdir()
            for name in ('run.json', 'summary.json'):
                (run / name).write_text('{}')
            m.exclusive(state / 'claim-next-M100.json', dict(host='127x01', controller_sha256='go'))
            m.exclusive(state / 'bundle-next-M100.json', dict(files=m.tree_hashes(incoming), controller_sha256='go'))
            with patch.object(m, 'OUT', root), patch.object(m, 'STATE', state), \
                 patch.object(m, 'host', return_value='127x08'), patch.object(m, 'allocation'):
                receipt = m.publish('next-M100', 'go')
                self.assertEqual(m.publish('next-M100', 'go'), receipt)
                self.assertEqual(m.validate_bundle(root, 'next-M100'), selection)
                # The existing 05 copy reader accepts the completed mirror unchanged.
                consumer = load('consumer05_test', HERE / 'followup_05.py')
                self.assertEqual(consumer.copy_selected('unused', root / 'select-next-M100'), selection)
                (root / 'select-next-M100/anchor.pt').write_bytes(b'changed')
                with self.assertRaisesRegex(RuntimeError, 'existing incompatible mirror'):
                    m.publish('next-M100', 'go')

    def test_host_telemetry_fails_closed_without_spawn(self):
        with patch.object(m.os, 'getloadavg', return_value=(90.5, 1, 1)):
            self.assertFalse(m.host_ok())
        with patch.object(m, 'host_ok', return_value=False), patch.object(m.subprocess, 'Popen') as spawn:
            self.assertEqual(m.guard(['never-launch']), 75)
            spawn.assert_not_called()

    def test_registered_commands(self):
        source = Path('/mpac/sdicks02/repos/clasher-pv1-host01-inputs-20261022/source')
        # On staged test hosts use the identical immutable source already present there.
        if not source.exists():
            source = m.SOURCE
        with patch.object(m, 'SOURCE', source), patch.object(m, 'host', return_value='127x01'):
            def options(phase):
                args = m.command(phase)
                return {args[i]: args[i + 1] for i in range(len(args) - 1) if args[i].startswith('--')}
            for phase in ('next-M100', 'next-S100'):
                a = options(phase)
                self.assertEqual(a['--epochs'], '8')
                self.assertEqual(a['--warmup-steps'], '0')
                self.assertEqual(a['--patience'], '2')
                self.assertIn(m.NEXT, a['--store'])
            self.assertEqual(options('next-S100')['--d'], '192')
            self.assertEqual(options('next-M100')['--d'], '320')

    def test_bad_go_has_no_control_side_effects(self):
        with patch.object(m, 'validate_legacy') as validate, patch.object(m, 'exclusive') as write:
            with self.assertRaises(RuntimeError):
                m.handoff('unreviewed')
            validate.assert_not_called(); write.assert_not_called()

    def test_m50_cannot_be_trained(self):
        with self.assertRaisesRegex(RuntimeError, 'not allocated'):
            m.command('M50')

    def test_corrupt_checkpoint_blocks_consumer_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); run = root / 'next-M100'; run.mkdir()
            for name in ('run.json', 'summary.json'):
                (run / name).write_text('{}')
            selected = root / 'select-next-M100'; selected.mkdir()
            (selected / 'anchor.pt').write_bytes(b'checkpoint')
            receipt = dict(file='anchor.pt', sha256=m.sha(selected / 'anchor.pt'), smoke=False)
            (selected / 'selection.json').write_text(json.dumps(receipt))
            self.assertEqual(m.validate_bundle(root, 'next-M100'), receipt)
            (selected / 'anchor.pt').write_bytes(b'corrupt')
            with self.assertRaisesRegex(RuntimeError, 'checkpoint hash mismatch'):
                m.validate_bundle(root, 'next-M100')

    def test_changed_input_and_path_escape_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); p = root / 'tensor.npy'; p.write_bytes(b'data')
            m.checked_files(root, {'tensor.npy': m.sha(p)})
            with self.assertRaisesRegex(RuntimeError, 'hash mismatch'):
                m.checked_files(root, {'tensor.npy': 'wrong'})
            with self.assertRaisesRegex(RuntimeError, 'unsafe relative path'):
                m.checked_files(root, {'../escape': 'wrong'})


if __name__ == '__main__':
    unittest.main()
