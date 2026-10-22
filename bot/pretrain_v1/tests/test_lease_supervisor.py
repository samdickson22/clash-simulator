"""Lease supervisor regressions with real harmless local children. Stdlib unittest (runs under host python3.8):
  python3 -m unittest bot.pretrain_v1.tests.test_lease_supervisor -v
Temp files live under the worktree; no lease, job root, remote host or GPU is touched."""
import fcntl, json, os, shutil, signal, subprocess, sys, tempfile, threading, time, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from bot.pretrain_v1 import lease_supervisor as M

ROOT = Path(__file__).resolve().parents[3]
GIB = M.GIB
LEASE = {"project": "clasher", "coordinator_thread": "b4f05b1c", "granted_by": "roader", "purpose": "test",
         "start_utc": "2026-01-01T00:00:00Z", "expected_end_utc": "2099-01-01T00:00:00Z", "max_workers": 96,
         "shared": True, "gpu": True, "gpu_free_min_gb": 8, "pss_cap_gb": 64, "nice_min": 10, "cpu_affinity": None,
         "reclaim": False, "status": "active", "supersedes": "stale"}

# Child writes ready, checkpoints on SIGTERM (contract), exits.
CHECKPOINTER = '''import os, signal, sys, time
def stop(*_):
    open("ckpt", "w").write(open(os.environ["CLASHER_LEASE_STOP_FILE"]).read()); sys.exit(0)
signal.signal(signal.SIGTERM, stop); open("ready", "w").write("1")
while True: time.sleep(0.05)'''
IGNORER = '''import signal, time
signal.signal(signal.SIGTERM, signal.SIG_IGN); open("ready", "w").write("1")
while True: time.sleep(0.05)'''
# Root starts an env-cleared grandchild in its own session (no marker, no shared sid), then exits on "go".
REPARENT = '''import os, subprocess, sys, time
g = subprocess.Popen([sys.executable, "-c", "import time\\nwhile True: time.sleep(0.05)"], env={}, start_new_session=True)
open("grand", "w").write(str(g.pid)); open("ready", "w").write("1")
while not os.path.exists("go"): time.sleep(0.05)'''


def wait_for(cond, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        if cond(): return True
        time.sleep(0.05)
    return False


class Base(unittest.TestCase):
    def setUp(self):
        base = ROOT / '.lease-test-tmp'; base.mkdir(exist_ok=True)
        self.tmp = Path(tempfile.mkdtemp(dir=str(base)))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.work = self.tmp / 'repos/clasher-job'; self.work.mkdir(parents=True)
        self.lease = self.tmp / 'leases/testhost.json'; self.lease.parent.mkdir()
        self.lease.write_text(json.dumps(LEASE, indent=2))
        self.t = time.time()
        self.load = dict(mem=100 * GIB, load=1.0)
        for name, val in [('ALLOWED_ROOTS', (str(self.tmp / 'repos/clasher'), str(self.tmp / 'jobs/clasher') + '/')),
                          ('HOSTS', {'testhost': 96}), ('HARD_STOP', M.iso(self.t + 3 * 86400)),
                          ('now', lambda: self.t), ('gpu_free_gb', lambda: 40.0),
                          ('host_load', lambda: (self.load['mem'], self.load['load']))]:
            p = mock.patch.object(M, name, val); p.start(); self.addCleanup(p.stop)
        self.st = M.State(str(self.tmp / 'jobs/clasher/lease'), 'testhost')
        self.sup_lock = self.st.lock('supervisor.lock'); self.addCleanup(self.sup_lock.close)
        self.addCleanup(self.reap)

    def reap(self):
        for r in self.st.records().values():
            for pid, start in r.get('procs', []) + ([[r['pid'], r['start']]] if r.get('pid') else []):
                M.signal_exact(pid, start, signal.SIGKILL)
        for f in self.work.glob('grand'):
            pid = int(f.read_text()); st = M.proc_stat(pid)
            if st: M.signal_exact(pid, st[4], signal.SIGKILL)

    def admit(self, name='j1', code=CHECKPOINTER, **kw):
        # Leave checkpoint time after the enforced 60-second detection/kill reserve.
        a = dict(name=name, workers=1, pss_gb=1.0, gpu_gb=0.0, grace=120, cwd=str(self.work),
                 cmd=[sys.executable, '-c', code]); a.update(kw)
        M.admit(SimpleNamespace(**a), self.st, str(self.lease))
        self.assertTrue(wait_for(lambda: (self.work / 'ready').exists()))
        return self.st.records()[name]

    def gone(self, sv, name):
        return wait_for(lambda: (sv.poll(), self.st.records()[name]['state'])[1] == 'gone')


class AdmissionTest(Base):
    def test_admit_spawns_detached_niced_with_contract_env_and_refuses_duplicate(self):
        r = self.admit()
        stat = M.proc_stat(r['pid'])
        self.assertEqual((stat[2], stat[4]), (r['pid'], r['start']))       # own session, recorded identity
        self.assertGreaterEqual(stat[3], 10)
        env = Path('/proc/%d/environ' % r['pid']).read_bytes().split(b'\0')
        self.assertIn(('CLASHER_LEASE_JOB=' + r['token']).encode(), env)
        self.assertIn(b'CUDA_VISIBLE_DEVICES=', env)
        self.assertIn(('CLASHER_LEASE_STOP_BY_UTC=' + r['stop_by_utc']).encode(), env)
        with self.assertRaisesRegex(SystemExit, 'j1 is running'): self.admit()

    def test_refusals(self):
        cases = [
            (lambda: self.lease.write_text(json.dumps(dict(LEASE, reclaim=True))), {}, 'reclaim'),
            (lambda: self.lease.write_text(json.dumps(dict(LEASE, status='ended'))), {}, 'status'),
            (lambda: self.lease.write_text('{"max_workers":96 (64 on12)}'), {}, 'unreadable'),
            (lambda: self.load.update(mem=29 * GIB), {}, 'MemAvailable'),
            (lambda: self.load.update(load=90.5), {}, 'load'),
            (None, dict(workers=97), 'procs'),
            (None, dict(pss_gb=65.0), 'pss'),
            (None, dict(grace=1801), 'grace'),
            (None, dict(cwd='/tmp'), 'cwd outside'),
            (None, dict(gpu_gb=33.0), 'gpu free'),
        ]
        for setup, kw, msg in cases:
            with self.subTest(msg=msg):
                self.lease.write_text(json.dumps(LEASE)); self.load.update(mem=100 * GIB, load=1.0)
                if setup: setup()
                with self.assertRaisesRegex(SystemExit, msg): self.admit(**kw)
        with mock.patch.object(M, 'gpu_free_gb', lambda: None):        # CPU-only admission still needs GPU telemetry
            self.lease.write_text(json.dumps(LEASE))
            with self.assertRaisesRegex(SystemExit, 'gpu free None'): self.admit(gpu_gb=0.0)
        with mock.patch.object(M, 'gpu_free_gb', lambda: 7.5):
            with self.assertRaisesRegex(SystemExit, 'gpu free 7.5'): self.admit(gpu_gb=0.0)
        self.t = M.parse_utc(M.HARD_STOP) - M.EXIT_MARGIN - 120 - M.MIN_RUNTIME + 1
        with self.assertRaisesRegex(SystemExit, 'too close'): self.admit()
        self.assertEqual(self.st.records(), {})

    def test_requires_live_supervisor_and_only_one_supervisor(self):
        with self.assertRaisesRegex(SystemExit, 'already live'):
            M.supervise(SimpleNamespace(poll=1), self.st, str(self.lease))
        self.sup_lock.close()
        with self.assertRaisesRegex(SystemExit, 'no live supervisor'): self.admit()

    def test_pidfd_unavailable_fails_closed_without_kill_fallback(self):
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); self.addCleanup(child.kill)
        def enosys(pid): raise OSError(38, 'Function not implemented')
        with mock.patch.object(M, '_pidfd_open', enosys), mock.patch.object(M.os, 'kill') as kill:
            with self.assertRaises(OSError): M.signal_exact(child.pid, M.proc_stat(child.pid)[4], signal.SIGTERM)
            with self.assertRaisesRegex(SystemExit, 'pidfd unavailable'):
                M.supervise(SimpleNamespace(poll=1), self.st, str(self.lease))
            with self.assertRaisesRegex(SystemExit, 'pidfd unavailable'): self.admit()
            kill.assert_not_called()
        self.assertIsNone(child.poll())

    def test_cli_renices_itself_and_rejects_bad_poll(self):
        with mock.patch.object(M, 'host', lambda: 'testhost'), \
             mock.patch.object(M, 'STATE_ROOT', str(self.tmp / 'jobs/clasher/lease')), \
             mock.patch('sys.stdout'):
            M.main(['status'])
        self.assertGreaterEqual(os.getpriority(os.PRIO_PROCESS, 0), 10)
        for bad in (0, -1, 61, float('nan'), float('inf')):
            with self.assertRaisesRegex(SystemExit, 'poll must be'):
                M.supervise(SimpleNamespace(poll=bad), self.st, str(self.lease))

    def test_declared_reservations_count_before_job_ramps(self):
        self.admit(pss_gb=40.0, workers=60)
        os.unlink(str(self.work / 'ready'))
        with self.assertRaisesRegex(SystemExit, 'pss .*procs|procs .*pss'):
            self.admit(name='j2', pss_gb=30.0, workers=40)

    def test_uncertain_records_block_admission_and_lease_end(self):
        for text in ['{not json', json.dumps(dict(name='x', state='intent', token='t'))]:
            with self.subTest(text=text[:10]):
                Path(self.st.jobs, 'x.json').write_text(text)
                with self.assertRaisesRegex(SystemExit, 'uncertain records'): self.admit()
                self.lease.write_text(json.dumps(dict(LEASE, reclaim=True)))
                self.assertIsNone(M.Supervisor(self.st, str(self.lease)).poll())
                self.assertEqual(json.loads(self.lease.read_text())['status'], 'active')
                self.lease.write_text(json.dumps(LEASE))

    def test_spawn_failure_leaves_no_blocking_intent(self):
        with self.assertRaisesRegex(SystemExit, 'spawn failed'):
            M.admit(SimpleNamespace(name='bad', workers=1, pss_gb=1.0, gpu_gb=0.0, grace=60, cwd=str(self.work),
                                    cmd=[str(self.tmp / 'missing')]), self.st, str(self.lease))
        self.assertEqual(self.st.records()['bad']['state'], 'gone')


class StopTest(Base):
    def test_reclaim_checkpoints_then_ends_lease_preserving_fields(self):
        r = self.admit()
        sv = M.Supervisor(self.st, str(self.lease))
        self.assertIsNone(sv.poll())
        edited = dict(LEASE, reclaim=True, note='coordinator edit')
        self.lease.write_text(json.dumps(edited))
        self.assertTrue(self.gone(sv, 'j1'))
        self.assertEqual(json.loads((self.work / 'ckpt').read_text())['reason'], 'reclaim')
        self.assertFalse(M.alive(r['pid'], r['start']))
        self.assertEqual(sv.poll() if json.loads(self.lease.read_text())['status'] != 'ended' else 'ended', 'ended')
        self.assertEqual(json.loads(self.lease.read_text()), dict(edited, status='ended'))

    def test_term_ignored_is_killed_only_after_grace(self):
        r = self.admit(code=IGNORER, grace=120)
        self.lease.write_text(json.dumps(dict(LEASE, reclaim=True)))
        os.utime(str(self.lease), (self.t - 30, self.t - 30))          # reclaim edited 30 s before detection
        sv = M.Supervisor(self.st, str(self.lease), poll=10); sv.poll()
        self.assertEqual(self.st.records()['j1']['kill_at'], self.t - 30 + 120 - M.MAX_POLL)   # grace counts from the edit
        self.t += 29; sv.poll(); time.sleep(0.3)
        self.assertTrue(M.alive(r['pid'], r['start']))
        self.t += 1
        self.assertTrue(self.gone(sv, 'j1'))
        events = Path(self.st.dir, 'events.jsonl').read_text().splitlines()
        self.assertTrue(any(json.loads(l)['ev'] == 'kill' for l in events))

    def test_reparented_env_cleared_descendant_stays_owned_until_stopped(self):
        r = self.admit(code=REPARENT)
        sv = M.Supervisor(self.st, str(self.lease)); sv.poll()            # sees grandchild while root lives
        g = int((self.work / 'grand').read_text()); gstart = M.proc_stat(g)[4]
        (self.work / 'go').write_text('1')
        self.assertTrue(wait_for(lambda: not M.alive(r['pid'], r['start'])))
        sv.poll()
        rec = self.st.records()['j1']
        self.assertEqual((rec['state'], rec['procs']), ('running', [[g, gstart]]))
        self.assertNotEqual(M.proc_stat(g)[1], r['pid'])                   # reparented
        Path(self.st.release).write_text('now')
        self.assertTrue(self.gone(sv, 'j1'))
        self.assertFalse(M.alive(g, gstart))

    def test_pid_reuse_identity_mismatch_is_never_signalled(self):
        other = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        self.addCleanup(other.kill)
        start = M.proc_stat(other.pid)[4]
        self.assertFalse(M.signal_exact(other.pid, start + 1, signal.SIGKILL))
        Path(self.st.jobs, 'old.json').write_text(json.dumps(dict(
            name='old', state='running', token='0' * 32, pid=other.pid, start=start - 1, procs=[[other.pid, start - 1]],
            boot=M.boot_id(), workers=1, pss_gb=1, gpu_gb=0, grace=1, admitted_utc='x',
            stop_file=str(Path(self.st.jobs, 'old.stop')), log=str(Path(self.st.logs, 'old-00000000.log')))))
        Path(self.st.release).write_text('now')
        sv = M.Supervisor(self.st, str(self.lease))
        self.assertEqual(sv.poll(), 'ended')
        self.assertEqual(self.st.records()['old']['state'], 'gone')
        self.assertIsNone(other.poll())

    def test_expiry_stops_with_time_to_exit_before_hard_stop(self):
        self.admit(grace=300)
        hard = M.parse_utc(M.HARD_STOP)
        sv = M.Supervisor(self.st, str(self.lease))
        self.t = hard - M.EXIT_MARGIN - 300 - 1; sv.poll()
        self.assertEqual(self.st.records()['j1']['state'], 'running')
        self.t += 1; sv.poll()
        rec = self.st.records()['j1']
        self.assertEqual((rec['state'], rec['stop_reason']), ('stopping', 'lease expiry'))
        self.assertLessEqual(rec['kill_at'], hard - M.EXIT_MARGIN - sv.poll_s)
        self.assertTrue(self.gone(sv, 'j1'))
        self.assertIsNone(sv.poll())                                      # not ended before EXIT_MARGIN
        self.t = hard - M.EXIT_MARGIN
        self.assertEqual(sv.poll(), 'ended')

    def test_sustained_breach_sheds_newest_owned_job_only(self):
        self.admit('old')
        self.t += 1; os.unlink(str(self.work / 'ready')); self.admit('new')
        sv = M.Supervisor(self.st, str(self.lease))
        self.load['mem'] = 20 * GIB
        sv.poll()
        self.assertEqual(self.st.records()['new']['state'], 'running')     # one breach poll is not enough
        sv.poll()
        recs = self.st.records()
        self.assertEqual((recs['old']['state'], recs['new']['state']), ('running', 'stopping'))
        self.assertTrue(recs['new']['stop_reason'].startswith('resource breach: mem'))

    def test_replaced_lease_stops_jobs_but_is_never_mutated(self):
        self.admit()
        sv = M.Supervisor(self.st, str(self.lease)); sv.poll()
        new = dict(LEASE, coordinator_thread='other-owner', start_utc='2026-01-02T00:00:00Z')
        self.lease.write_text(json.dumps(new))
        self.assertTrue(self.gone(sv, 'j1'))
        self.assertEqual(sv.poll(), 'ended')
        self.assertEqual(json.loads(self.lease.read_text()), new)
        restarted = M.Supervisor(self.st, str(self.lease))              # identity persists across restarts
        self.assertEqual(restarted.poll(), 'ended')
        self.assertEqual(json.loads(self.lease.read_text()), new)
        with self.assertRaisesRegex(RuntimeError, 'identity changed'):
            M.mark_lease_ended(str(self.lease), M.lease_identity(LEASE))
        self.assertEqual(json.loads(self.lease.read_text()), new)

    def test_unobservable_resources_shed_and_poll_errors_drain_owned_work(self):
        r = self.admit(code=IGNORER)
        sv = M.Supervisor(self.st, str(self.lease), poll=1)
        def denied(pid): raise PermissionError(13, 'denied')
        with mock.patch.object(M, 'pss_bytes', denied):
            sv.poll(); sv.poll()
        rec = self.st.records()['j1']
        self.assertEqual(rec['state'], 'stopping'); self.assertIn('unobservable', rec['stop_reason'])
        # Every poll now fails outright: the loop must drain recorded owners rather than spin.
        sv2 = M.Supervisor(self.st, str(self.lease), poll=1)
        def broken(): raise RuntimeError('boom')
        sv2.poll = broken; ticks = []
        def sleep(_):
            ticks.append(1); self.t += 1000
            if len(ticks) > 4: raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt): M.run_loop(sv2, 1, sleep)
        self.assertTrue(wait_for(lambda: not M.alive(r['pid'], r['start'])))
        self.assertTrue(os.path.exists(self.st.halt))
        self.assertEqual(json.loads(self.lease.read_text())['status'], 'active')
        os.unlink(str(self.work / 'ready'))
        with self.assertRaisesRegex(SystemExit, 'halted'): self.admit('j2')

    def test_lease_end_preserves_fields_and_inode(self):
        self.lease.write_text(json.dumps(dict(LEASE, reclaim=True, extended='by coordinator')))
        inode = self.lease.stat().st_ino
        M.mark_lease_ended(str(self.lease), M.lease_identity(LEASE))
        self.assertEqual(self.lease.stat().st_ino, inode)
        self.assertEqual(json.loads(self.lease.read_text()), dict(LEASE, reclaim=True, extended='by coordinator', status='ended'))
        self.assertEqual(sorted(p.name for p in self.lease.parent.iterdir()), ['testhost.json'])


class R30Test(Base):
    def test_scan_keeps_running_sleeping_identity(self):
        pid = os.getpid(); real = M.proc_stat; count = [0]
        def changing(p):
            st = real(p)
            if p == pid:
                count[0] += 1
                return ('R' if count[0] % 2 else 'S',) + st[1:]
            return st
        with mock.patch.object(M, 'proc_stat', changing):
            self.assertTrue(pid in M.scan(), "stable process missing")

    def test_scan_omission_then_reclaim_retains_live_owner(self):
        r = self.admit(code=IGNORER)
        sv = M.Supervisor(self.st, str(self.lease), poll=1)
        with mock.patch.object(M, 'scan', return_value={}): sv.poll()
        self.assertEqual(self.st.records()['j1']['state'], 'running')
        self.lease.write_text(json.dumps(dict(LEASE, reclaim=True)))
        sv.poll()
        self.assertEqual(self.st.records()['j1']['state'], 'stopping')
        self.assertEqual(json.loads(self.lease.read_text())['status'], 'active')
        # Even a previously misclassified gone record must be recovered by its token.
        rec = self.st.records()['j1']; rec.update(state='gone', procs=[]); self.st.save(rec)
        sv.poll()
        self.assertEqual(self.st.records()['j1']['state'], 'stopping')
        self.assertTrue(M.alive(r['pid'], r['start']))

    def test_final_release_scan_recovers_gone_token_after_initial_omission(self):
        r = self.admit(code=IGNORER)
        self.st.save(dict(r, state='gone', procs=[]))
        self.lease.write_text(json.dumps(dict(LEASE, reclaim=True)))
        procs = M.scan()
        with mock.patch.object(M, 'scan', side_effect=[{}, procs]):
            self.assertIsNone(M.Supervisor(self.st, str(self.lease)).poll())
        rec = self.st.records()['j1']
        self.assertEqual(rec['state'], 'running')
        self.assertIn([r['pid'], r['start']], rec['procs'])
        self.assertEqual(json.loads(self.lease.read_text())['status'], 'active')

    def test_emergency_rejects_old_boot_and_malformed_identity(self):
        r = self.admit(code=IGNORER)
        for changes in (dict(boot='old-boot'), dict(procs=[[True, r['start']]]), dict(token=None)):
            bad = dict(r, **changes)
            Path(self.st.jobs, 'j1.json').write_text(json.dumps(bad))
            with mock.patch.object(M, 'signal_exact') as sig:
                M.Supervisor(self.st, str(self.lease)).emergency(self.t)
                sig.assert_not_called()
        self.st.save(r)

    def test_restart_tightens_stopping_deadline_and_reclaim(self):
        r = self.admit(code=IGNORER, grace=120)
        sv = M.Supervisor(self.st, str(self.lease), poll=1)
        Path(self.st.release).write_text('now'); sv.poll(); os.unlink(self.st.release)
        old = self.st.records()['j1']['kill_at']
        self.lease.write_text(json.dumps(dict(LEASE, expected_end_utc=M.iso(self.t + 300))))
        with mock.patch.object(M, 'signal_exact') as sig:
            M.Supervisor(self.st, str(self.lease), poll=1).poll()
            self.assertLess(self.st.records()['j1']['kill_at'], old)
            self.assertTrue(any(c.args[2] == signal.SIGKILL for c in sig.call_args_list))
        self.st.save(dict(r, state='stopping', kill_at=self.t + 900, stop_sent_utc=M.iso(self.t - 20)))
        self.lease.write_text(json.dumps(dict(LEASE, reclaim=True)))
        os.utime(self.lease, (self.t - 100, self.t - 100))
        M.Supervisor(self.st, str(self.lease), poll=1).poll()
        self.assertLessEqual(self.st.records()['j1']['kill_at'], self.t - 100 + 120 - M.MAX_POLL)

    def test_state_rejects_jobs_logs_and_persisted_stop_symlinks(self):
        outside = self.tmp / 'outside'; outside.mkdir()
        for child in ('jobs', 'logs'):
            root = self.tmp / ('jobs/clasher/unsafe-' + child)
            hostdir = root / 'testhost'; hostdir.mkdir(parents=True)
            (hostdir / child).symlink_to(outside, target_is_directory=True)
            with self.assertRaises((OSError, ValueError, SystemExit)): M.State(str(root), 'testhost')
        r = self.admit(code=IGNORER)
        Path(r['stop_file']).symlink_to(outside / 'escaped')
        Path(self.st.release).write_text('now')
        with mock.patch.object(M, 'signal_exact') as sig:
            M.Supervisor(self.st, str(self.lease)).poll()
            sig.assert_not_called()
        self.assertEqual(self.st.records()['j1']['state'], 'uncertain')
        self.assertFalse((outside / 'escaped').exists())
        Path(r['stop_file']).unlink(); self.st.save(r)

    def test_waiting_cooperating_editor_keeps_current_inode(self):
        opened, finished = threading.Event(), threading.Event()
        errors = []
        def editor():
            try:
                with open(self.lease, 'r+') as f:
                    opened.set(); fcntl.flock(f, fcntl.LOCK_EX)
                    d = json.load(f); d.update(reclaim=True, note='waiting editor')
                    f.seek(0); json.dump(d, f); f.truncate(); f.flush(); os.fsync(f.fileno())
            except Exception as e: errors.append(e)
            finally: finished.set()
        # Start editor after supervisor owns the lock, before it writes.
        real = M.fcntl.flock; thread = threading.Thread(target=editor)
        def flock(f, op):
            result = real(f, op)
            if op & fcntl.LOCK_EX and threading.current_thread() is threading.main_thread():
                thread.start(); self.assertTrue(opened.wait(2))
            return result
        with mock.patch.object(M.fcntl, 'flock', flock):
            M.mark_lease_ended(str(self.lease), M.lease_identity(LEASE))
        self.assertTrue(finished.wait(2)); thread.join(2); self.assertEqual(errors, [])
        self.assertEqual(json.loads(self.lease.read_text()), dict(LEASE, status='ended', reclaim=True, note='waiting editor'))

    def test_elapsed_poll_spacing_includes_work(self):
        clock, reads = [0.0], []
        sv = M.Supervisor(self.st, str(self.lease), poll=60)
        def poll():
            reads.append(clock[0]); clock[0] += 30
            return 'ended' if len(reads) == 3 else None
        sv.poll = poll
        def sleep(delay): clock[0] += delay
        with mock.patch.object(M.time, 'monotonic', lambda: clock[0]): M.run_loop(sv, 60, sleep)
        self.assertLessEqual(max(b - a for a, b in zip(reads, reads[1:])), 60)


    def test_real_elapsed_checks_use_fixed_deadlines(self):
        sv = M.Supervisor(self.st, str(self.lease), poll=0.15)
        reads = []
        def step():
            M.load_lease(str(self.lease), 'testhost'); reads.append(time.monotonic())
            time.sleep(0.09)
            if len(reads) == 4: return 'ended'
        sv.poll = step
        M.run_loop(sv, 0.15)
        # Sleep-after-work would yield 0.24 s per read. Allow scheduling jitter.
        self.assertLess((reads[-1] - reads[0]) / 3, 0.21)

    def test_blocking_state_and_lease_locks_drain_without_waiting_another_poll(self):
        r = self.admit()
        sv = M.Supervisor(self.st, str(self.lease))
        for lockpath in (Path(self.st.dir, 'state.lock'), self.lease):
            with self.subTest(lockpath=lockpath.name), open(lockpath, 'r+') as held:
                fcntl.flock(held, fcntl.LOCK_EX)
                sv = M.Supervisor(self.st, str(self.lease))
                start = time.monotonic()
                with mock.patch.object(M, 'LOCK_WAIT', 0.05), mock.patch.object(sv, 'emergency', wraps=sv.emergency) as emergency:
                    with self.assertRaises(KeyboardInterrupt):
                        M.run_loop(sv, 60, lambda _: (_ for _ in ()).throw(KeyboardInterrupt()))
                    emergency.assert_called_once()
                self.assertLess(time.monotonic() - start, 1)
                self.assertTrue(Path(self.st.halt).exists())
        self.assertTrue(wait_for(lambda: not M.alive(r['pid'], r['start'])))
        self.assertEqual(json.loads(self.lease.read_text())['status'], 'active')

    def test_blocking_telemetry_hits_wall_budget_and_drains(self):
        r = self.admit()
        sv = M.Supervisor(self.st, str(self.lease))
        entered = []
        def telemetry():
            entered.append(time.monotonic()); time.sleep(2); return 40
        start = time.monotonic()
        with mock.patch.object(M, 'WORK_BUDGET', 0.2), mock.patch.object(M, 'gpu_free_gb', telemetry), \
                mock.patch.object(sv, 'emergency', wraps=sv.emergency) as emergency:
            with self.assertRaises(KeyboardInterrupt):
                M.run_loop(sv, 60, lambda _: (_ for _ in ()).throw(KeyboardInterrupt()))
            self.assertTrue(entered); emergency.assert_called_once()
        self.assertLess(time.monotonic() - start, 1)
        self.assertTrue(Path(self.st.halt).exists())
        self.assertTrue(wait_for(lambda: not M.alive(r['pid'], r['start'])))
        self.assertEqual(json.loads(self.lease.read_text())['status'], 'active')

    def test_late_monotonic_wakeup_drains_instead_of_readmitting(self):
        sv = M.Supervisor(self.st, str(self.lease))
        clock = [0.0]; calls = []
        def poll(): calls.append(clock[0])
        def sleep(delay):
            if clock[0]: raise KeyboardInterrupt
            clock[0] = 100
        sv.poll = poll
        with mock.patch.object(M.time, 'monotonic', lambda: clock[0]), \
                mock.patch.object(sv, 'emergency', wraps=sv.emergency) as emergency:
            with self.assertRaises(KeyboardInterrupt): M.run_loop(sv, 60, sleep)
            emergency.assert_called_once()
        self.assertEqual(calls, [0]); self.assertTrue(Path(self.st.halt).exists())

    def test_gpu_subprocess_timeout_is_bounded(self):
        # Base patches GPU telemetry, so exercise the original implementation separately.
        import importlib.util
        spec = importlib.util.spec_from_file_location('lease_telemetry_test', M.__file__)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with mock.patch.object(module.subprocess, 'run', side_effect=subprocess.TimeoutExpired('nvidia-smi', 5)) as run:
            self.assertIsNone(module.gpu_free_gb())
            self.assertLessEqual(run.call_args.kwargs['timeout'], 5)

    def test_persisted_log_stop_and_record_paths_fail_closed(self):
        r = self.admit(code=IGNORER)
        for field, value in (('stop_file', str(self.tmp / 'escaped.stop')),
                             ('log', str(self.tmp / 'escaped.log'))):
            self.st.save(dict(r, **{field: value}))
            self.assertEqual(self.st.records()['j1']['state'], 'uncertain')
        self.st.save(r)
        logfile = Path(r['log']); logfile.unlink(); logfile.symlink_to(self.tmp / 'escaped.log')
        self.assertEqual(self.st.records()['j1']['state'], 'uncertain')
        with self.assertRaises((OSError, ValueError)): M.safe_open(str(logfile), 'ab')
        logfile.unlink(); self.st.save(r)
        recordfile = Path(self.st.jobs, 'j1.json'); recordfile.unlink(); recordfile.symlink_to(self.tmp / 'escaped.json')
        with self.assertRaises((OSError, ValueError)): self.st.save(r)
        self.assertEqual(self.st.records()['j1']['state'], 'uncertain')
        self.assertFalse((self.tmp / 'escaped.json').exists())
        recordfile.unlink(); self.st.save(r)

    def test_lease_reader_waits_for_complete_inplace_edit(self):
        partial, finish, done = threading.Event(), threading.Event(), threading.Event()
        errors, result = [], []
        def editor():
            try:
                with open(self.lease, 'r+') as f:
                    fcntl.flock(f, fcntl.LOCK_EX)
                    f.seek(0); f.write('{'); f.truncate(); f.flush(); partial.set()
                    if not finish.wait(2): raise RuntimeError('reader did not finish')
                    f.seek(0); json.dump(dict(LEASE, note='complete edit'), f); f.truncate(); f.flush(); os.fsync(f.fileno())
            except Exception as e: errors.append(e)
        def reader():
            try: result.append(M.load_lease(str(self.lease), 'testhost')[0])
            except Exception as e: errors.append(e)
            finally: done.set()
        writer = threading.Thread(target=editor); writer.start()
        self.assertTrue(partial.wait(2))
        reader_thread = threading.Thread(target=reader); reader_thread.start()
        try: self.assertFalse(done.wait(0.05))
        finally: finish.set(); writer.join(2); reader_thread.join(2)
        self.assertEqual(errors, []); self.assertEqual(result, [dict(LEASE, note='complete edit')])


if __name__ == '__main__':
    unittest.main()
