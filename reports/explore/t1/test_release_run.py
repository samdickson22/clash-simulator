"""Offline synthetic fixtures only. No canonical checkout or real game access."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import release_run as driver


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='t1-release-driver-synthetic-')
        self.base = Path(self.temp.name)
        self.ledger = self.base / 'blind.json'
        self.ledger.write_text('{"events": []}')
        self.sidecar = {'utc': 'old', 'schema': 'synthetic', 'blocks': [{'id': 'synthetic-0'}]}
        self.calls = []
        self.directory = self.base / 'private'

    def tearDown(self):
        if self.directory.exists():
            os.chmod(self.directory, 0o700)
        self.temp.cleanup()

    def health(self, root, events, digest):
        self.calls.append('health')
        self.assertEqual(root, self.base)
        self.assertEqual(events, [])
        self.assertEqual(digest, driver.sha(self.ledger))
        return {**self.sidecar, 'utc': 'new'}

    def barrier(self):
        self.calls.append('barrier')

    def reducer(self, output, out, err):
        self.calls.append('reducer')
        # Deliberately sensitive synthetic output, never printed by the wrapper.
        print('SYNTHETIC SECRET stdout')
        emitted = output.with_name(output.name + '.ssh-sensitivity-ledger.json')
        emitted.write_text(json.dumps({**self.sidecar, 'utc': 'newer'}))
        digest = driver.sha(emitted)
        result = {key: {'ledger_sha256': digest} for key in
                  ('ssh_sensitivity', 'apt_sensitivity', 'ssh_or_apt_sensitivity')}
        result['synthetic_secret'] = 'SYNTHETIC SECRET result'
        output.write_text(json.dumps(result))
        return 0

    def run_guard(self, health=None, barrier=None, reducer=None):
        return driver.execute_guarded(self.base, self.ledger, self.sidecar, self.directory,
                                      health or self.health, barrier or self.barrier, reducer or self.reducer)

    def test_matching_except_utc_orders_barrier_before_reducer_and_hides_output(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            record = self.run_guard()
        self.assertEqual(self.calls, ['health', 'barrier', 'reducer'])
        self.assertTrue(record['passes'])
        self.assertNotIn('SECRET', json.dumps(record))
        self.assertEqual(stdout.getvalue(), '')
        self.assertIn('SECRET stdout', (self.directory / 'reducer.stdout').read_text())
        self.assertEqual(self.directory.stat().st_mode & 0o777, 0o700)

    def test_preguard_mismatch_never_invokes_barrier_or_reducer(self):
        with self.assertRaises(driver.ReleaseFailure) as caught:
            self.run_guard(health=lambda *a: {**self.sidecar, 'blocks': []})
        self.assertEqual(self.calls, [])
        self.assertFalse(self.directory.exists())
        self.assertEqual(caught.exception.health['stage'], 'pre_guard')

    def test_health_exception_aborts_before_output_or_game_reader(self):
        def broken(*args):
            raise RuntimeError('SECRET never disclose')
        with self.assertRaises(driver.ReleaseFailure) as caught:
            self.run_guard(health=broken)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.directory.exists())
        self.assertNotIn('SECRET', json.dumps(caught.exception.health))

    def test_barrier_failure_prevents_reducer_and_locks(self):
        def broken():
            self.calls.append('barrier')
            raise ValueError('SECRET')
        self.assert_locked_failure(barrier=broken, stage='barrier')
        self.assertEqual(self.calls, ['health', 'barrier'])

    def assert_locked_failure(self, stage='post_check', **kwargs):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), self.assertRaises(driver.ReleaseFailure) as caught:
            self.run_guard(**kwargs)
        self.assertEqual(stdout.getvalue(), '')
        self.assertEqual(self.directory.stat().st_mode & 0o777, 0)
        self.assertTrue(caught.exception.health['outputs_locked'])
        self.assertEqual(caught.exception.health['stage'], stage)
        self.assertNotIn('SECRET', json.dumps(caught.exception.health))

    def test_reducer_nonzero_locks_stdout_and_output(self):
        def bad(*args):
            self.reducer(*args)
            return 23
        self.assert_locked_failure(reducer=bad, stage='reducer')

    def test_reducer_exception_locks_and_hides_exception_text(self):
        def bad(*args):
            self.reducer(*args)
            raise RuntimeError('SECRET')
        self.assert_locked_failure(reducer=bad, stage='reducer')

    def test_emitted_ledger_difference_locks(self):
        def bad(output, *rest):
            self.reducer(output, *rest)
            output.with_name(output.name + '.ssh-sensitivity-ledger.json').write_text('{"blocks": []}')
            return 0
        self.assert_locked_failure(reducer=bad)

    def test_each_sensitivity_binding_checked(self):
        for key in ('ssh_sensitivity', 'apt_sensitivity', 'ssh_or_apt_sensitivity'):
            with self.subTest(key=key):
                def bad(output, *rest):
                    self.reducer(output, *rest)
                    value=json.loads(output.read_text());value[key]['ledger_sha256']='wrong'
                    output.write_text(json.dumps(value));return 0
                self.assert_locked_failure(reducer=bad)
                os.chmod(self.directory, 0o700)
                # Each subcase has a fresh exclusive destination.
                self.directory = self.base / (key + '-next')

    def test_missing_apt_and_union_both_rejected(self):
        for key in ('apt_sensitivity', 'ssh_or_apt_sensitivity'):
            with self.subTest(key=key):
                def bad(output, *rest):
                    self.reducer(output, *rest)
                    value=json.loads(output.read_text());del value[key]
                    output.write_text(json.dumps(value));return 0
                self.assert_locked_failure(reducer=bad)
                os.chmod(self.directory, 0o700)
                self.directory = self.base / (key + '-next')

    def test_existing_output_directory_is_not_overwritten(self):
        self.directory.mkdir();(self.directory / 'sentinel').write_text('keep')
        with self.assertRaises(driver.ReleaseFailure):
            self.run_guard()
        self.assertEqual((self.directory / 'sentinel').read_text(), 'keep')
        self.assertEqual(self.calls, ['health'])

    def test_real_health_function_reads_only_synthetic_metadata(self):
        from ssh_sensitivity import health_ledger
        block = self.base / 'synthetic-0'
        (block / 'games').mkdir(parents=True)
        (block / 'games/not-json').write_bytes(b'synthetic opaque bytes')
        (block / 'complete.json').write_text(json.dumps(dict(
            host='127x01', descriptor=dict(id='synthetic-0', population='primary', cell=0),
            interference={})))
        opened = []
        original = Path.open
        def guarded_open(path, *args, **kwargs):
            self.assertNotIn('games', path.parts)
            opened.append(path)
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', guarded_open):
            health = health_ledger(self.base, [], driver.sha(self.ledger))
        self.assertEqual(health['blocks'][0]['id'], 'synthetic-0')
        self.assertTrue(opened)


if __name__ == '__main__':
    unittest.main()
