"""Lease supervisor regressions with real harmless local children. Stdlib unittest (runs under host python3.8):
  python3 -m unittest bot.pretrain_v1.tests.test_lease_supervisor -v
Temp files live under the worktree; no lease, job root, remote host or GPU is touched."""
import json, os, shutil, signal, subprocess, sys, tempfile, time, unittest
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
        a = dict(name=name, workers=1, pss_gb=1.0, gpu_gb=0.0, grace=60, cwd=str(self.work),
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
        self.t = M.parse_utc(M.HARD_STOP) - M.EXIT_MARGIN - 60 - M.MIN_RUNTIME + 1
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
        self.assertEqual(self.st.records()['j1']['kill_at'], self.t - 30 + 120 - 10)   # grace counts from the edit
        self.t += 79; sv.poll(); time.sleep(0.3)
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
            stop_file=str(self.tmp / 'old.stop'))))
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

    def test_lease_end_never_clobbers_concurrent_edit(self):
        real = os.chmod; calls = []
        def racing_chmod(path, mode):
            if not calls: self.lease.write_text(json.dumps(dict(LEASE, reclaim=True, extended='by coordinator')))
            calls.append(path); real(path, mode)
        with mock.patch.object(M.os, 'chmod', racing_chmod): M.mark_lease_ended(str(self.lease), M.lease_identity(LEASE))
        self.assertEqual(len(calls), 2)
        self.assertEqual(json.loads(self.lease.read_text()), dict(LEASE, reclaim=True, extended='by coordinator', status='ended'))
        self.assertEqual(sorted(p.name for p in self.lease.parent.iterdir()), ['testhost.json'])


if __name__ == '__main__':
    unittest.main()
