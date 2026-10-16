"""Temporary-directory regressions for assembler input preservation and symlink safety."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from bot.cards import build_live16402 as live
from bot.cards import build_runtime as runtime


@unittest.skipUnless(shutil.which('rsync'), 'assemblers require rsync')
class AssemblerSafetyTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.make_base(self.root / 'base')
        self.tree = self.root / 'tree'
        rel = 'engine-cards/py/src/clasher/example.py'
        (self.tree / rel).parent.mkdir(parents=True)
        (self.tree / rel).write_text('new overlay\n')
        glue = 'engine-cards/example.py'
        (self.tree / glue).write_text('new glue\n')
        (self.tree / 'SOURCE-GIT.json').write_text(json.dumps(dict(commit='test', tracked=[rel, glue])))
        self.native = self.root / 'native.so'
        self.native.write_bytes(b'new native')
        self.target = self.root / 'runtime'
        self.inputs = {k: self.root / (k + '.json') for k in ('rs16', 'rs15', 'calibration')}
        for p in self.inputs.values():
            p.write_text('{}')

    def make_base(self, path):
        (path / 'native').mkdir(parents=True)
        (path / 'native/clasher_core.abi3.so').write_bytes(b'base native')
        (path / 'src/clasher').mkdir(parents=True)
        (path / 'engine-rs').mkdir()
        (path / 'gamedata.json').write_text('{}')
        for receipt in (runtime.RECEIPT, live.RECEIPT):
            (path / receipt).write_text('{}')
        return path

    def run_main(self, module, *extra):
        args = ['assembler', '--base', str(self.base), '--target', str(self.target)]
        if module is runtime:
            args += ['--tree', str(self.tree), '--native', str(self.native)]
        else:
            for key, path in self.inputs.items():
                args += ['--' + key, str(path)]
            args += ['--link']  # do not make the temporary test directories read-only
        args += list(extra)
        def overlay(base, rs16, rs15, calibration, out, **kw):
            out.write_text('{"overlay": true}')
            return dict(inputs={}, output=dict(sha256=runtime.sha256(out)), actions={},
                        applied_slots=0, comparer_check={}), {}
        with patch('sys.argv', args), contextlib.redirect_stdout(io.StringIO()), \
                patch.object(live.bo, 'run', overlay), patch.object(live.bo, 'c56_names', return_value=[]):
            module.main()

    def test_target_cannot_overlap_inputs(self):
        for module in (runtime, live):
            for target in (self.base, self.base / 'child', self.root):
                with self.subTest(module=module.__name__, target=target):
                    self.target = target
                    with self.assertRaisesRegex(SystemExit, 'target overlaps base'):
                        self.run_main(module)
                    self.assertEqual((self.base / 'gamedata.json').read_text(), '{}')

    def test_backup_cannot_contain_a_base_symlink_referent(self):
        backup = self.root / 'runtime.old'
        backup.mkdir()
        (backup / 'input').write_text('preserve')
        (self.base / 'reference').symlink_to(backup, target_is_directory=True)
        self.make_base(self.target)
        for module in (runtime, live):
            with self.subTest(module=module.__name__):
                with self.assertRaisesRegex(SystemExit, 'backup overlaps base symlink'):
                    self.run_main(module)
                self.assertEqual((backup / 'input').read_text(), 'preserve')
                self.assertTrue(self.target.exists())

    def test_old_backup_cannot_contain_base(self):
        for module in (runtime, live):
            for nested in (False, True):
                with self.subTest(module=module.__name__, nested=nested):
                    self.target = self.root / (module.__name__.split('.')[-1] + str(nested))
                    backup = self.target.with_name(self.target.name + '.old')
                    self.base = self.make_base(backup / 'nested' if nested else backup)
                    self.make_base(self.target)
                    with self.assertRaisesRegex(SystemExit, 'backup overlaps base'):
                        self.run_main(module)
                    self.assertEqual((self.base / 'gamedata.json').read_text(), '{}')
                    self.assertTrue(self.target.exists())

    def test_old_backup_cannot_contain_overlay_or_native(self):
        backup = self.root / 'runtime.old'
        backup.mkdir()
        for which in ('tree', 'native'):
            with self.subTest(which=which):
                source = getattr(self, which)
                moved = backup / source.name
                source.rename(moved)
                setattr(self, which, moved)
                if not self.target.exists():
                    self.make_base(self.target)
                with self.assertRaisesRegex(SystemExit, 'backup overlaps'):
                    self.run_main(runtime)
                self.assertTrue(moved.exists())
                moved.rename(source)
                setattr(self, which, source)

    def test_live_backup_cannot_contain_balance_inputs(self):
        backup = self.root / 'runtime.old'
        backup.mkdir()
        for key, source in list(self.inputs.items()):
            with self.subTest(key=key):
                moved = backup / source.name
                source.rename(moved)
                self.inputs[key] = moved
                with self.assertRaisesRegex(SystemExit, 'backup overlaps ' + key):
                    self.run_main(live)
                self.assertEqual(moved.read_text(), '{}')
                moved.rename(source)
                self.inputs[key] = source

    def test_export_and_build_outputs_checked_before_mutation(self):
        self.base = self.make_base(self.root / 'runtime.source')
        with patch.object(runtime, 'export') as export:
            with self.assertRaisesRegex(SystemExit, 'source export overlaps base'):
                # Invoke directly because --rev and --tree are mutually exclusive.
                with patch('sys.argv', ['assembler', '--base', str(self.base), '--target', str(self.target),
                                        '--rev', 'HEAD', '--native', str(self.native)]):
                    runtime.main()
            export.assert_not_called()
        with self.assertRaisesRegex(SystemExit, 'native build overlaps base'):
            with patch('sys.argv', ['assembler', '--base', str(self.base), '--target', str(self.target),
                                    '--tree', str(self.tree), '--build-dir', str(self.base / 'out')]):
                runtime.main()
        self.assertEqual((self.base / 'gamedata.json').read_text(), '{}')

    def test_replacement_retains_previous_target_as_backup(self):
        for module in (runtime, live):
            with self.subTest(module=module.__name__):
                self.target = self.root / module.__name__.split('.')[-1]
                self.run_main(module)
                (self.target / 'previous').write_text('keep')
                self.run_main(module)
                backup = self.target.with_name(self.target.name + '.old')
                self.assertEqual((backup / 'previous').read_text(), 'keep')
                self.run_main(module)
                self.assertFalse((backup / 'previous').exists())
                self.assertEqual((self.base / 'gamedata.json').read_text(), '{}')

    def test_legacy_staging_base_is_preserved(self):
        for module in (runtime, live):
            with self.subTest(module=module.__name__):
                self.target = self.root / module.__name__.split('.')[-1]
                self.base = self.make_base(self.target.with_name(self.target.name + '.assembling'))
                self.run_main(module)
                self.assertEqual((self.base / 'gamedata.json').read_text(), '{}')
                self.assertEqual((self.base / 'native/clasher_core.abi3.so').read_bytes(), b'base native')
                self.assertTrue((self.target / module.RECEIPT).is_file())

    def test_symlinked_destination_ancestors_rejected(self):
        for relative in ('native', 'src/clasher', 'src', 'engine-rs'):
            with self.subTest(relative=relative):
                destination = self.base / relative
                shutil.rmtree(destination)
                outside = self.root / ('outside-' + relative.replace('/', '-'))
                outside.mkdir()
                (outside / 'sentinel').write_bytes(b'untouched')
                destination.symlink_to(outside, target_is_directory=True)
                with self.assertRaisesRegex(SystemExit, 'symlinked destination ancestor'):
                    self.run_main(runtime)
                self.assertEqual(list(outside.iterdir()), [outside / 'sentinel'])
                self.assertEqual((outside / 'sentinel').read_bytes(), b'untouched')
                destination.unlink()
                destination.mkdir()

    def test_resolved_overlay_input_cannot_live_in_backup(self):
        backup = self.root / 'runtime.old'
        backup.mkdir()
        source = backup / 'example.py'
        source.write_text('input')
        overlay = self.tree / 'engine-cards/py/src/clasher/example.py'
        overlay.unlink()
        overlay.symlink_to(source)
        with self.assertRaisesRegex(SystemExit, 'backup overlaps overlay'):
            self.run_main(runtime)
        self.assertEqual(source.read_text(), 'input')

    def test_backup_symlink_rejected(self):
        backup = self.root / 'runtime.old'
        outside = self.root / 'outside'
        outside.mkdir()
        backup.symlink_to(outside, target_is_directory=True)
        for module in (runtime, live):
            with self.subTest(module=module.__name__):
                with self.assertRaisesRegex(SystemExit, 'symlinked output path: backup'):
                    self.run_main(module)
                self.assertTrue(backup.is_symlink())


if __name__ == '__main__':
    unittest.main()
