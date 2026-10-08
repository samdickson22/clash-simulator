"""Unit and isolated real-process tests; run on a Clasher home host, not 127x05.

No live lease, v1 wrapper, production job or owner path is changed.
"""
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name('lease_watch_v2.py')
spec = importlib.util.spec_from_file_location('lease_watch_v2', SOURCE)
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)
POLICY = '''Total worker processes per host ≤96 of 128, ≤16 if `~/.local/bin/fleet-console-users` reports a console user.
Everything nice 10+. GPU borrowers leave ≥8 GB of GPU memory free.
The borrower keeps memory ≤ 64 GB measured as PSS.
'''


def job(kind='v2', sequence=1, count=2, pss=100, declared_count=4, declared_pss=200, known=None):
    value = dict(kind=kind, sequence=sequence, processes=count, pss_bytes=pss, known=known or {})
    if kind == 'v2':
        value.update(declared_processes=declared_count, declared_pss_bytes=declared_pss)
    return value


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.host = patch.object(w, 'HOST', '127x15')
        self.host.start()
        self.addCleanup(self.host.stop)
        self.cap = dict(processes=80, pss_bytes=64_000_000_000)

    def test_live_lease_and_stricter_host_caps(self):
        for host, cap in w.HOST_CAPS.items():
            with patch.object(w, 'HOST', host):
                self.assertEqual(w.limits({'max_workers': 96}, 0, POLICY)['processes'], cap)
                self.assertEqual(w.limits({'max_workers': 12}, 0, POLICY)['processes'], 12)

    def test_console_helper_cap(self):
        self.assertEqual(w.limits({'max_workers': 96}, 1, POLICY)['processes'], 16)

    def test_clasher_argv_explicit_allowlist(self):
        paths = ['repos/clasher/train.py', 'repos/clasher', 'repos/clasher-lease/run.sh',
                 'repos/clasher-v4-data/a', 'repos/clasher-eval-snapshots/a',
                 'repos/clasher-checkpoints/a', 'repos/clasher-t11-test/a',
                 'jobs/clasher/job.py', 'envs/clasher-gpu/bin/python',
                 'tmp/t5-test/job.py', 'tmp/t11-test/job.py', 'tmp/v4-test/job.py']
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(w.clasher_argv([b'python', ('/mpac/sdicks02/' + path).encode()]))
        for path in ('repos/clasherish/a', 'jobs/clasher-other/a', 'envs/other/bin/python',
                     'tmp/other/a', 'tools/python', 'repos/another/a'):
            with self.subTest(path=path):
                self.assertFalse(w.clasher_argv([b'python', ('/mpac/sdicks02/' + path).encode()]))

    def test_roader_and_desktop_exclusions_override_clasher_arguments(self):
        for argv in ([b'python', b'/mpac/sdicks02/repos/roader-perf2/run.py'],
                     [b'/mpac/sdicks02/roader-shell'],
                     [b'bwrap', b'/mpac/sdicks02/.roadforge/worker'],
                     [b'python', b'/mpac/sdicks02/repos/roader/run.py',
                      b'/mpac/sdicks02/repos/clasher-lease/data'],
                     [b'/usr/bin/dbus-daemon', b'/mpac/sdicks02/repos/clasher/cache'],
                     [b'/usr/libexec/gvfsd', b'/mpac/sdicks02/repos/clasher/cache']):
            with self.subTest(argv=argv):
                self.assertTrue(w.excluded_argv(argv))
                self.assertFalse(w.clasher_argv(argv))

    def test_pending_versioned_launchers_are_not_external_jobs(self):
        for name in ('lease_watch_v2.py', 'run_v2.sh',
                     'lease_watch_v2_hotfix_20261008_r1.py', 'run_v2_hotfix_20261008_r1.sh',
                     'run_v2_current.sh'):
            self.assertTrue(w.pending_launcher([b'python', str(w.BASE / name).encode()]))
        self.assertFalse(w.pending_launcher([str(w.BASE / 'repo/job.py').encode()]))

    def test_refresh_preserves_live_supervisor_with_empty_known_set(self):
        entry = {**job(known={'2': 'gone'}), 'supervisor_pid': 1, 'supervisor_start': 'a'}
        registry = {'jobs': {'v2:fast': entry}}
        with patch.object(w, 'legacy_holders', return_value=[]):
            w.refresh(registry, {1: (0, 'a', 10, 'S', 10)})
        self.assertEqual(registry['jobs']['v2:fast']['known'], {'1': 'a'})
        self.assertEqual(w.reserved_usage(registry['jobs'])['processes'], 4)

    def test_refresh_drops_dead_or_reused_supervisor_after_descendants_exit(self):
        for rows in ({}, {1: (0, 'a', 10, 'Z', 10)}, {1: (0, 'new', 10, 'S', 10)}):
            registry = {'jobs': {'v2:fast': {**job(), 'supervisor_pid': 1, 'supervisor_start': 'a'}}}
            with patch.object(w, 'legacy_holders', return_value=[]):
                w.refresh(registry, rows)
            self.assertEqual(registry['jobs'], {})

    def test_discovery_reclassifies_stale_roader_without_measuring_it(self):
        rows = {101: (0, 'clasher', 10, 'S', 10), 102: (0, 'roader', 20, 'S', 0),
                103: (0, 'desktop', 30, 'S', 0), 104: (101, 'child', 10, 'S', 10)}
        argv = {101: [b'python', b'/mpac/sdicks02/repos/clasher-v4-data/job.py'],
                102: [b'bwrap', b'/mpac/sdicks02/repos/roader-perf2/run.py'],
                103: [b'/usr/bin/dbus-daemon'], 104: [b'python', b'-c', b'pass']}
        registry = {'jobs': {'external:102:roader': job('external', known={'102': 'roader'})}}
        with patch.object(w, 'legacy_holders', return_value=[]), \
                patch.object(w, 'process_argv', side_effect=lambda pid: argv[pid]), \
                patch.object(w, 'tree_pss', side_effect=lambda known: len(known) * 10) as pss:
            w.refresh(registry, rows, discover=True)
            result = w.measure(registry, rows)
        self.assertEqual(result, {'processes': 2, 'pss_bytes': 20})
        self.assertEqual(set(registry['jobs']), {'external:101:clasher'})
        self.assertTrue(all(102 not in call.args[0] for call in pss.call_args_list))
        self.assertEqual(next(iter(registry['jobs'].values()))['minimum_nice'], 10)

    def test_live_policy_can_tighten_caps(self):
        policy = POLICY.replace('≤96', '≤70').replace('≤16', '≤8').replace('64 GB', '32 GB')
        self.assertEqual(w.limits({'max_workers': 96}, 0, policy)['processes'], 70)
        self.assertEqual(w.limits({'max_workers': 96}, 1, policy)['processes'], 8)
        self.assertEqual(w.limits({'max_workers': 96}, 0, policy)['pss_bytes'], 32_000_000_000)

    def test_policy_missing_controls_fails_closed(self):
        with self.assertRaises(ValueError):
            w.limits({'max_workers': 96}, 0, '')

    def test_policy_absent_uses_bundled_controls(self):
        with patch.object(w, 'POLICY', Path('/nonexistent-fleet-sharing-policy')):
            text, source = w.read_policy()
        self.assertIn('bundled', source)
        self.assertEqual(w.limits({'max_workers': 96}, 0, text)['pss_bytes'], 64_000_000_000)

    def test_unreadable_policy_fails_closed(self):
        with patch.object(Path, 'read_text', side_effect=PermissionError('unreadable')):
            with self.assertRaises(PermissionError):
                w.read_policy()

    def test_admission_exact_boundary_with_v1(self):
        jobs = {'v1': job('v1', count=14, pss=11_000_000_000)}
        used = w.admission(jobs, self.cap, 66, 53_000_000_000)
        self.assertEqual(used, dict(processes=14, pss_bytes=11_000_000_000))

    def test_admission_process_overflow(self):
        with self.assertRaisesRegex(ValueError, 'processes'):
            w.admission({'old': job('v1', count=14)}, self.cap, 67, 100)

    def test_admission_pss_overflow(self):
        with self.assertRaisesRegex(ValueError, 'pss_bytes'):
            w.admission({'old': job('v1', pss=63_000_000_000)}, self.cap, 2, 1_000_000_001)

    def test_reserves_growth_before_second_admission(self):
        jobs = {'first': job(count=2, declared_count=70)}
        with self.assertRaisesRegex(ValueError, 'processes'):
            w.admission(jobs, self.cap, 11, 100)
        w.admission(jobs, self.cap, 10, 100)

    def test_reservation_never_understates_measured_usage(self):
        self.assertEqual(w.reserved_usage({'first': job(count=6, pss=300)}),
                         dict(processes=6, pss_bytes=300))

    def test_newest_first_and_v1_never_a_victim(self):
        jobs = {'legacy': job('v1', -1, 60), 'old': job(sequence=1, count=10),
                'new': job(sequence=2, count=20)}
        self.assertEqual(w.newest_victims(jobs, self.cap), ['new'])
        self.assertEqual(w.newest_victims(jobs, dict(processes=10, pss_bytes=10000)), ['new', 'old'])

    def test_already_stopping_job_not_reselected(self):
        jobs = {'legacy': job('v1', -1, 70), 'old': job(sequence=1, count=5),
                'new': {**job(sequence=2, count=20), 'stop_reason': 'aggregate'}}
        self.assertEqual(w.newest_victims(jobs, self.cap), [])

    def test_memory_overage_selects_newest(self):
        jobs = {'old': job(sequence=1, pss=40_000_000_000),
                'new': job(sequence=2, pss=30_000_000_000)}
        self.assertEqual(w.newest_victims(jobs, self.cap), ['new'])

    def test_pid_reuse_and_zombies_excluded_reparented_retained(self):
        rows = {1: (0, 'a', 100, 'S', 10), 2: (1, 'b', 100, 'S', 10),
                3: (2, 'c', 100, 'S', 10), 4: (99, 'd', 100, 'S', 10),
                5: (1, 'new', 100, 'S', 10), 6: (1, 'z', 100, 'Z', 10)}
        self.assertEqual(w.expand(rows, {'1': 'a', '4': 'd', '5': 'old', '6': 'z'}),
                         {1: 'a', 2: 'b', 3: 'c', 4: 'd', 5: 'new'})
        # The recycled PID is included only as a verified current descendant.
        self.assertEqual(w.expand(rows, {'5': 'old'}), {})

    def test_overlapping_trees_count_each_pid_once(self):
        rows = {1: (0, 'a', 20, 'S', 10), 2: (1, 'b', 30, 'S', 10)}
        registry = {'jobs': {'v1': job('v1', known={'1': 'a', '2': 'b'}),
                             'sidecar': job('external', known={'2': 'b'})}}
        with patch.object(w, 'tree_pss', side_effect=lambda known: sum(pid * 10 for pid in known)):
            self.assertEqual(w.measure(registry, rows), dict(processes=2, pss_bytes=30))

    def test_mark_stop_does_not_modify_v1(self):
        legacy = job('v1')
        w.mark_stop(legacy, 'reclaim')
        self.assertNotIn('stop_reason', legacy)

    def test_earlier_lease_tightens_deadlines(self):
        stop, end = w.deadlines({'expected_end_utc': '2026-10-09T04:00Z'})
        self.assertEqual(stop.hour, 3)
        self.assertEqual((end.hour, end.minute), (3, 30))

    def test_fixed_return_deadlines(self):
        self.assertEqual(w.deadlines({'expected_end_utc': '2026-10-09T05:30Z'}), (w.STOP_AT, w.EXIT_BY))

    def test_check_all_propagates_missing_lease_to_every_v2(self):
        registry = {'jobs': {'a': job(), 'b': job(sequence=2), 'legacy': job('v1')}}
        with patch.object(w, 'refresh'), patch.object(w, 'measure', return_value={'processes': 0, 'pss_bytes': 0}), \
                patch.object(w, 'read_lease', side_effect=FileNotFoundError('missing lease')):
            w.check_all(registry, {})
        self.assertIn('missing lease', registry['jobs']['a']['stop_reason'])
        self.assertIn('missing lease', registry['jobs']['b']['stop_reason'])
        self.assertNotIn('stop_reason', registry['jobs']['legacy'])

    def test_measurement_failure_requests_all_v2_stops(self):
        registry = {'jobs': {'a': job(), 'b': job(sequence=2)}}
        with patch.object(w, 'refresh'), patch.object(w, 'measure', side_effect=PermissionError('PSS unreadable')):
            w.check_all(registry, {})
        self.assertTrue(all(j['stop_reason'] for j in registry['jobs'].values()))

    def test_return_waits_for_legacy_or_other_jobs(self):
        with patch.object(w, 'refresh'), patch.object(w, 'processes', return_value={}), \
                patch.object(Path, 'unlink') as unlink:
            w.return_lease_if_idle({'jobs': {'v1': job('v1')}})
            unlink.assert_not_called()

    def test_return_deletes_only_idle_matching_reclaimed_lease(self):
        value = {'project': 'clasher', 'coordinator_thread': w.COORDINATOR,
                 'reclaim': True, 'expected_end_utc': '2099-01-01T00:00Z'}
        with patch.object(w, 'refresh'), patch.object(w, 'processes', return_value={}), \
                patch.object(Path, 'read_text', return_value=json.dumps(value)), \
                patch.object(Path, 'unlink') as unlink:
            w.return_lease_if_idle({'jobs': {}})
            unlink.assert_called_once()

    def test_return_does_not_delete_another_borrower(self):
        value = {'project': 'another', 'coordinator_thread': 'another',
                 'reclaim': True, 'expected_end_utc': '2000-01-01T00:00Z'}
        with patch.object(w, 'refresh'), patch.object(w, 'processes', return_value={}), \
                patch.object(Path, 'read_text', return_value=json.dumps(value)), \
                patch.object(Path, 'unlink') as unlink:
            w.return_lease_if_idle({'jobs': {}})
            unlink.assert_not_called()

    def test_signaling_rejects_reused_pid_and_never_signals_self(self):
        rows = {12: (0, 'new', 0, 'S', 10), 13: (0, 'same', 0, 'S', 10),
                os.getpid(): (0, 'self', 0, 'S', 10)}
        with patch.object(w, 'processes', return_value=rows), patch.object(w.os, 'kill') as kill:
            w.send({12: 'old', 13: 'same', os.getpid(): 'self'}, signal.SIGTERM)
            kill.assert_called_once_with(13, signal.SIGTERM)


DRIVER = '''import importlib.util,json,sys,datetime as dt
from pathlib import Path
spec=importlib.util.spec_from_file_location('watch',sys.argv.pop(1)); w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
w.BASE=Path(sys.argv.pop(1));w.HOST='127x15';w.LEASE=w.BASE/'lease.json';w.POLICY=w.BASE/'policy.md';w.CONSOLE_HELPER=w.BASE/'console'
w.CHECK_INTERVAL=.08;w.POLL_INTERVAL=.02;w.TERM_AFTER=.15;w.KILL_AFTER=.3
w.STOP_AT=dt.datetime(2099,1,1,tzinfo=dt.timezone.utc);w.EXIT_BY=dt.datetime(2099,1,2,tzinfo=dt.timezone.utc)
# Production argv classification has dedicated synthetic unit tests. Process
# fixtures must not discover or measure unrelated live Clasher home-host jobs.
w.process_argv=lambda pid: []
config=w.BASE/'config.json'
if config.exists():
 c=json.loads(config.read_text())
 for key in ('STOP_AT','EXIT_BY'):
  if key in c:setattr(w,key,w.timestamp(c[key]))
 for key in ('TERM_AFTER','KILL_AFTER'):
  if key in c:setattr(w,key,c[key])
if 'gpu-free' in json.loads((w.BASE/'options.json').read_text()):
 original=w.subprocess.check_output
 def check(args,**kwargs):
  if args[0]=='nvidia-smi':return json.loads((w.BASE/'options.json').read_text())['gpu-free']
  return original(args,**kwargs)
 w.subprocess.check_output=check
if json.loads((w.BASE/'options.json').read_text()).get('drop-own-entry'):
 original_refresh=w.refresh
 def refresh(registry,rows,discover=False):
  original_refresh(registry,rows,discover)
  registry['jobs'].pop('v2:missing-entry',None)
 w.refresh=refresh
sys.exit(w.main())
'''


class ProcessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.uname().nodename.split('.')[0] == '127x05':
            raise RuntimeError('Run real-process tests on a Clasher home host')
        cls.directory = Path(tempfile.mkdtemp(prefix='lease-wrapper-v2-tests-'))
        cls.driver = cls.directory / 'driver.py'
        cls.driver.write_text(DRIVER)

    def setUp(self):
        self.base = self.directory / self._testMethodName
        (self.base / 'jobs').mkdir(parents=True)
        (self.base / 'policy.md').write_text(POLICY)
        self.current = dict(project='clasher', coordinator_thread=w.COORDINATOR,
                            expected_end_utc='2099-01-03T00:00Z', max_workers=96, shared=True, gpu=True)
        self.lease()
        self.helper(0)
        (self.base / 'options.json').write_text('{}')
        self.launched = []

    def tearDown(self):
        # Only direct test-owned supervisor PIDs are signaled; children normally
        # already exited. Use fixture reclaim to let supervisors clean up.
        self.current['reclaim'] = True
        self.lease()
        for proc in self.launched:
            try:
                proc.communicate(timeout=4)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=3)

    def lease(self):
        w.atomic(self.base / 'lease.json', self.current)

    def helper(self, count):
        path = self.base / 'console'
        path.write_text('#!/bin/sh\necho ' + str(count) + '\n')
        path.chmod(0o700)

    def launch(self, label, code='import time; time.sleep(.25)', processes=2, pss=.1, detached=False, gpu=False):
        args = [sys.executable, '-B', str(self.driver), str(SOURCE), str(self.base),
                '--max-processes', str(processes), '--expected-pss-gb', str(pss)]
        if not detached:
            args += ['--foreground']
        if gpu:
            args += ['--gpu']
        args += [label, '--', sys.executable, '-c', code]
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.launched.append(proc)
        return proc

    def wait_file(self, name, timeout=4):
        path = self.base / 'jobs' / name
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if path.exists():
                return json.loads(path.read_text())
            time.sleep(.02)
        self.fail('missing ' + str(path))

    def finish(self, proc, label, status='pass'):
        output, _ = proc.communicate(timeout=5)
        receipt = self.wait_file(label + '.exit.json')
        self.assertEqual(receipt['status'], status, output + repr(receipt))
        if 'pid' in receipt:
            self.assertFalse(Path('/proc', str(receipt['pid'])).exists())
        return receipt

    def test_normal_completion_pss_and_nice(self):
        proc = self.launch('normal')
        receipt = self.finish(proc, 'normal')
        self.assertEqual(receipt['exit_code'], 0)
        self.assertEqual(receipt['peak_processes'], 2)
        self.assertGreater(receipt['peak_sampled_pss_bytes'], 0)
        self.assertEqual(receipt['effective_process_cap'], 80)
        self.assertEqual(json.loads((self.base / 'jobs/aggregate-v2.json').read_text())['jobs'], {})

    def test_fast_child_preserves_true_exit_status(self):
        for code, expected, status in [('pass', 0, 'pass'), ('import sys; sys.exit(7)', 7, 'fail')]:
            label = 'fast-' + str(expected)
            proc = self.launch(label, code=code)
            receipt = self.finish(proc, label, status)
            self.assertEqual(receipt['exit_code'], expected)
            self.assertEqual(proc.returncode, expected)
            self.assertNotIn('error', receipt)
            self.assertIsNone(receipt['stop_reason'])

    def test_missing_own_entry_reaps_child_and_writes_normal_receipt(self):
        (self.base / 'options.json').write_text(json.dumps({'drop-own-entry': True}))
        proc = self.launch('missing-entry', code='import sys; sys.exit(7)')
        receipt = self.finish(proc, 'missing-entry', 'fail')
        self.assertEqual(receipt['exit_code'], 7)
        self.assertEqual(proc.returncode, 7)
        self.assertNotIn('error', receipt)
        self.assertIsNone(receipt['stop_reason'])

    def test_child_forks_then_exits_and_adopted_descendant_is_cleaned_up(self):
        code = '''import os,time
from pathlib import Path
r,wr=os.pipe()
pid=os.fork()
if pid:
 os.close(wr);os.read(r,1);os._exit(7)
os.close(r)
Path('forked.pid').write_text(str(os.getpid()))
os.write(wr,b'x');os.close(wr)
time.sleep(3)
'''
        receipt = self.finish(self.launch('fork-exit', code=code, processes=3), 'fork-exit', 'stopped')
        self.assertEqual(receipt['exit_code'], 7)
        self.assertIn('descendants', receipt['stop_reason'])
        self.assertNotIn('error', receipt)
        pid = int((self.base / 'forked.pid').read_text())
        self.assertFalse(Path('/proc', str(pid)).exists())

    def test_two_concurrent_fast_admissions_both_finish_cleanly(self):
        a = self.launch('fast-a', code='pass')
        b = self.launch('fast-b', code='pass')
        receipts = [self.finish(a, 'fast-a'), self.finish(b, 'fast-b')]
        self.assertTrue(all(r['exit_code'] == 0 and 'error' not in r for r in receipts))
        self.assertEqual(len({r['admission_sequence'] for r in receipts}), 2)
        self.assertEqual(json.loads((self.base / 'jobs/aggregate-v2.json').read_text())['jobs'], {})

    def test_console_occupancy_limits_admission(self):
        self.helper(1)
        proc = self.launch('console', processes=17)
        receipt = self.finish(proc, 'console', 'fail')
        self.assertNotIn('pid', receipt)
        self.assertIn('processes', receipt['error'])

    def test_refused_and_missing_helper_block_start(self):
        self.current['refused'] = True
        self.lease()
        receipt = self.finish(self.launch('refused'), 'refused', 'fail')
        self.assertNotIn('pid', receipt)
        self.current.pop('refused')
        self.lease()
        (self.base / 'console').unlink()
        receipt = self.finish(self.launch('missing-helper'), 'missing-helper', 'fail')
        self.assertNotIn('pid', receipt)

    def test_concurrent_admission_reserves_capacity(self):
        a = self.launch('a', code='import time; time.sleep(.8)', processes=60)
        b = self.launch('b', code='import time; time.sleep(.8)', processes=60)
        a.communicate(timeout=4)
        b.communicate(timeout=4)
        receipts = [self.wait_file(label + '.exit.json') for label in ('a', 'b')]
        self.assertEqual(sorted(r['status'] for r in receipts), ['fail', 'pass'])
        self.assertEqual(sum('pid' in r for r in receipts), 1)

    def test_detached_launch_and_duplicate_label(self):
        proc = self.launch('detached', detached=True)
        output, _ = proc.communicate(timeout=4)
        self.assertEqual(proc.returncode, 0, output)
        self.assertIn('pid=', output)
        receipt = self.wait_file('detached.exit.json')
        self.assertEqual(receipt['status'], 'pass', receipt)
        original = (self.base / 'jobs/detached.exit.json').read_bytes()
        duplicate = self.launch('detached')
        duplicate.communicate(timeout=3)
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertEqual((self.base / 'jobs/detached.exit.json').read_bytes(), original)

    def test_v1_lock_coexistence_is_read_only(self):
        script = self.base / 'lease_watch.py'
        script.write_text('''import fcntl,time,subprocess,sys,os
from pathlib import Path
lock=Path(__file__).parent/'jobs/host-workload.lock'
with lock.open('a') as f:
 fcntl.flock(f,fcntl.LOCK_EX)
 p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(2)'])
 (lock.parent/'legacy-ready').write_text(str(os.getpid()))
 p.wait()
''')
        legacy = subprocess.Popen(['nice', '-n', '10', sys.executable, str(script)])
        self.addCleanup(lambda: legacy.wait(timeout=4))
        ready = self.base / 'jobs/legacy-ready'
        deadline = time.monotonic() + 3
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertTrue(ready.exists())
        lock = self.base / 'jobs/host-workload.lock'
        before = lock.stat()
        receipt = self.finish(self.launch('alongside'), 'alongside')
        self.assertEqual(receipt['admission_aggregate']['processes'], 2)
        self.assertTrue(any(j['kind'] == 'v1' for j in receipt['admission_jobs'].values()))
        self.assertIsNone(legacy.poll())
        after = lock.stat()
        self.assertEqual((before.st_ino, before.st_size, before.st_mtime_ns),
                         (after.st_ino, after.st_size, after.st_mtime_ns))

    def test_reclaim_applies_to_all_jobs_checkpoint_and_forced_cleanup(self):
        code = "import signal,time,sys; from pathlib import Path; signal.signal(signal.SIGTERM,lambda *_:(Path('saved').write_text('yes'),sys.exit(0))); time.sleep(3)"
        a = self.launch('checkpoint', code=code)
        b = self.launch('stubborn', code='import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(3)')
        self.wait_file('checkpoint.state.json')
        self.wait_file('stubborn.state.json')
        time.sleep(.1)
        self.current['reclaim'] = True
        self.lease()
        saved = self.finish(a, 'checkpoint', 'stopped')
        forced = self.finish(b, 'stubborn', 'stopped')
        self.assertTrue((self.base / 'saved').exists())
        self.assertEqual(saved['exit_code'], 0)
        self.assertEqual(forced['exit_code'], -signal.SIGKILL)
        self.assertFalse((self.base / 'lease.json').exists())

    def test_missing_or_expired_lease_requests_stop(self):
        for label in ('missing', 'expired'):
            self.current['expected_end_utc'] = '2099-01-03T00:00Z'
            self.lease()
            proc = self.launch(label, code='import time; time.sleep(3)')
            self.wait_file(label + '.state.json')
            if label == 'missing':
                (self.base / 'lease.json').unlink()
            else:
                self.current['expected_end_utc'] = '2000-01-01T00:00Z'
                self.lease()
            receipt = self.finish(proc, label, 'stopped')
            self.assertIsNotNone(receipt['stop_reason'])

    def test_declared_process_and_pss_caps(self):
        code = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time; time.sleep(3)']); time.sleep(3)"
        receipt = self.finish(self.launch('too-many', code=code), 'too-many', 'stopped')
        self.assertIn('process cap', receipt['stop_reason'])
        receipt = self.finish(self.launch('too-much', pss=.001), 'too-much', 'stopped')
        self.assertIn('PSS cap', receipt['stop_reason'])

    def test_cap_reduction_stops_newest_first(self):
        a = self.launch('old', code='import time; time.sleep(1)')
        self.wait_file('old.state.json')
        b = self.launch('new', code='import time; time.sleep(3)')
        self.wait_file('new.state.json')
        self.current['max_workers'] = 2
        self.lease()
        receipt = self.finish(b, 'new', 'stopped')
        self.assertIn('newest', receipt['stop_reason'])
        self.finish(a, 'old')

    def test_gpu_gate_and_cpu_skips_gpu_query(self):
        (self.base / 'options.json').write_text(json.dumps({'gpu-free': '8191\n'}))
        receipt = self.finish(self.launch('gpu', gpu=True), 'gpu', 'fail')
        self.assertNotIn('pid', receipt)
        self.finish(self.launch('cpu'), 'cpu')

    def test_stop_and_exit_deadlines(self):
        now = dt.datetime.now(dt.timezone.utc)
        (self.base / 'config.json').write_text(json.dumps({
            'STOP_AT': (now + dt.timedelta(seconds=.7)).isoformat(),
            'EXIT_BY': (now + dt.timedelta(seconds=2)).isoformat(),
            'TERM_AFTER': 8, 'KILL_AFTER': 10}))
        receipt = self.finish(self.launch('deadline', code='import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(3)'),
                              'deadline', 'stopped')
        self.assertIn('deadline', receipt['stop_reason'])
        self.assertEqual(receipt['exit_code'], -signal.SIGKILL)
        self.assertLess(w.timestamp(receipt['finished_utc']), now + dt.timedelta(seconds=3))


if __name__ == '__main__':
    unittest.main(verbosity=2)
