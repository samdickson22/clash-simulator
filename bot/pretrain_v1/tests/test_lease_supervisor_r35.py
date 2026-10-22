"""R35 regressions with disposable local children, actual locks and exact pidfd signals."""
import contextlib
import io
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from bot.pretrain_v1 import lease_supervisor as M
from bot.pretrain_v1.tests import test_lease_supervisor as T


class R35Test(T.Base):
    def capture_children(self):
        children = []
        real_popen = subprocess.Popen
        def spawn(*a, **kw):
            child = real_popen(*a, **kw)
            children.append((child, M.proc_stat(child.pid)[4]))
            self.assertTrue(T.wait_for(lambda: (self.work/'ready').exists(), 3))
            return child
        def cleanup():
            for child, start in children:
                M.signal_exact(child.pid, start, signal.SIGKILL)
                child.wait(timeout=5)
        self.addCleanup(cleanup)
        return children, spawn

    def test_failed_intent_publication_restart_budget_cannot_skip_cached_kill(self):
        children, spawn = self.capture_children()
        real_save = self.st.save
        def save(r):
            if r['state'] != 'intent': raise OSError('post-intent record writes unavailable')
            real_save(r)
        args = SimpleNamespace(name='job', workers=1, pss_gb=1, gpu_gb=0, grace=1800,
                               cwd=str(self.work), cmd=[sys.executable, '-c', T.IGNORER])
        with mock.patch.object(self.st, 'save', save), mock.patch.object(M.subprocess, 'Popen', spawn):
            with self.assertRaises(OSError): M.admit(args, self.st, str(self.lease))
        r = self.st.records()['job']; child, start = children[0]
        self.assertEqual((r['state'], r['pid'], r['procs']), ('intent', None, []))
        self.assertIn((M.MARKER+'='+r['token']).encode(), Path('/proc/%d/environ'%child.pid).read_bytes().split(b'\0'))
        self.assertIn(child.pid, M.owned(dict(r), M.scan(), M.boot_id()))
        epoch = self.t
        self.lease.write_text(json.dumps(dict(T.LEASE, reclaim=True)))
        M.Supervisor(self.st, str(self.lease)).read_lease()
        self.t = epoch+1900
        restarted = M.Supervisor(self.st, str(self.lease))
        reads, cycles, sends = [], [], []
        real_signal = M.signal_exact
        def blocked(_):
            reads.append(1); time.sleep(2)
            self.fail('SIGALRM must interrupt the external read')
        def sent(pid, st, sig):
            sends.append((pid, st, sig)); return real_signal(pid, st, sig)
        def cycle(_):
            cycles.append(1)
            if len(cycles) == 3: raise KeyboardInterrupt
        with mock.patch.object(M, 'read_snapshot', blocked), mock.patch.object(M, 'WORK_BUDGET', .04), \
             mock.patch.object(M, 'signal_exact', sent):
            with self.assertRaises(KeyboardInterrupt): M.run_loop(restarted, 30, cycle)
        self.assertEqual((len(reads), len(cycles)), (6, 3))
        self.assertIn((child.pid, start, signal.SIGKILL), sends)
        self.assertTrue(T.wait_for(lambda: not M.alive(child.pid, start), 3))
        child.wait(timeout=5)
        self.assertLessEqual(self.st.records()['job']['kill_at'], epoch+1740)
        self.assertFalse(Path(self.st.dir, 'ended.json').exists())

    def test_gone_token_is_discovered_before_normal_or_emergency_external_read(self):
        children, spawn = self.capture_children()
        with mock.patch.object(M.subprocess, 'Popen', spawn), contextlib.redirect_stdout(io.StringIO()):
            r = self.admit(code=T.IGNORER, grace=1800)
        child, start = children[0]; epoch = self.t
        self.lease.write_text(json.dumps(dict(T.LEASE, reclaim=True)))
        M.Supervisor(self.st, str(self.lease)).read_lease()
        self.st.save(dict(r, state='gone', procs=[]))
        self.t = epoch+1900
        # Suppress delivery in the normal call so both paths must discover a real live token.
        real_signal = M.signal_exact
        sends = []
        def observe(pid, st, sig): sends.append((pid, st, sig)); return False
        with mock.patch.object(M, 'read_snapshot', side_effect=M.CadenceError('blocked read')), \
             mock.patch.object(M, 'signal_exact', observe):
            with self.assertRaises(M.CadenceError): M.Supervisor(self.st, str(self.lease)).poll()
        self.assertIn((child.pid, start, signal.SIGKILL), sends)
        # Remove the normal stop record and journal to exercise token-only emergency discovery too.
        for p in Path(self.st.dir, 'recovery').glob('*.json'): p.unlink()
        self.st.save(dict(r, state='gone', procs=[]))
        with mock.patch.object(M, 'read_snapshot', side_effect=M.CadenceError('blocked read')), \
             mock.patch.object(M, 'signal_exact', wraps=real_signal) as delivered:
            with self.assertRaises(M.CadenceError): M.Supervisor(self.st, str(self.lease)).emergency(epoch)
        self.assertIn(mock.call(child.pid, start, signal.SIGKILL), delivered.call_args_list)
        self.assertTrue(T.wait_for(lambda: not M.alive(child.pid, start), 3))

    def test_three_held_admission_locks_persist_request_before_term_and_restart_kill(self):
        children, spawn = self.capture_children()
        with mock.patch.object(M.subprocess, 'Popen', spawn), contextlib.redirect_stdout(io.StringIO()):
            r = self.admit(code=T.IGNORER, grace=1800)
        child, start = children[0]; epoch = self.t
        sv = M.Supervisor(self.st, str(self.lease)); sv.poll()
        locks = [self.st.lock(name) for name in ('state.lock', 'generation.lock', 'observation.lock')]
        real_signal = M.signal_exact
        seen = []
        def send(pid, st, sig):
            fresh = M.Supervisor(self.st, str(self.lease))
            self.assertEqual(fresh.recovery_origin, epoch)
            self.assertTrue(fresh.ending)
            # This journal is the durable stopping state while the generation lock forbids replacement.
            requests = [json.loads(p.read_text()) for p in Path(self.st.dir, 'recovery').glob('*.json')]
            jobs = [q['record'] for q in requests if q['kind'] == 'stop']
            self.assertTrue(any(q['token'] == r['token'] and q['boot'] == r['boot'] and
                                q['state'] == 'stopping' and q['kill_at'] <= epoch+1740 and
                                [pid, st] in q['procs'] for q in jobs))
            self.assertIsInstance(json.loads(Path(r['stop_file']).read_text()), dict)
            seen.append(sig)
            return real_signal(pid, st, sig)
        try:
            with mock.patch.object(M, 'LOCK_WAIT', .02), mock.patch.object(M, 'signal_exact', send):
                with self.assertRaises(TimeoutError): sv.poll()
                sv.emergency(epoch)
            self.assertTrue(seen)
            self.assertEqual(self.st.records()[r['name']]['state'], 'running')
        finally:
            for lk in reversed(locks): lk.close()
        # Prove restore does not depend on HALT or the observation-state writer catching up.
        Path(self.st.halt).unlink()
        self.t = epoch+1900
        restarted = M.Supervisor(self.st, str(self.lease))
        self.assertEqual(restarted.recovery_origin, epoch)
        with mock.patch.object(M, 'read_snapshot', side_effect=M.CadenceError('external budget')), \
             mock.patch.object(M, 'signal_exact', send):
            with self.assertRaises(M.CadenceError): restarted.poll()
        self.assertIn(signal.SIGKILL, seen)
        self.assertTrue(T.wait_for(lambda: not M.alive(child.pid, start), 3))
        child.wait(timeout=5)
        self.assertLessEqual(self.st.records()[r['name']]['kill_at'], epoch+1740)
        self.assertFalse(Path(self.st.dir, 'ended.json').exists())

    def test_repeated_notification_publication_preserves_real_atomic_checkpoint(self):
        code = '''import os, signal, sys, time
from pathlib import Path
def stop(*_):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    Path('handler').write_text('ready')
    while not Path('read-now').exists(): time.sleep(.001)
    data = Path(os.environ['CLASHER_LEASE_STOP_FILE']).read_bytes()
    with open('ckpt.tmp', 'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace('ckpt.tmp', 'ckpt'); sys.exit(0)
signal.signal(signal.SIGTERM, stop); Path('ready').write_text('ready')
while True: time.sleep(.01)
'''
        children, spawn = self.capture_children()
        with mock.patch.object(M.subprocess, 'Popen', spawn), contextlib.redirect_stdout(io.StringIO()):
            r = self.admit(code=code, grace=1800)
        original_open, original_replace, real_signal = M.safe_open, M.os.replace, M.signal_exact
        writes = []
        def gate():
            writes.append(1)
            if len(writes) == 2:
                self.assertTrue(T.wait_for(lambda: (self.work/'handler').exists(), 3))
                (self.work/'read-now').write_text('go')
                self.assertTrue(T.wait_for(lambda: (self.work/'ckpt').exists(), 3))
        def opened(path, mode):
            f = original_open(path, mode)
            if path == r['stop_file'] and mode == 'w': gate()
            return f
        def replace(src, dst, *a, **kw):
            if dst == os.path.basename(r['stop_file']): gate()
            return original_replace(src, dst, *a, **kw)
        def send(pid, start, sig):
            disk = self.st.records()[r['name']]
            self.assertEqual(disk['state'], 'stopping')
            self.assertIn([pid, start], disk['procs'])
            return real_signal(pid, start, sig)
        with mock.patch.object(M, 'safe_open', opened), mock.patch.object(M.os, 'replace', replace), \
             mock.patch.object(M, 'signal_exact', send):
            M.Supervisor(self.st, str(self.lease)).emergency(self.t)
        self.assertGreaterEqual(len(writes), 2)
        self.assertTrue(T.wait_for(lambda: (self.work/'ckpt').exists(), 3))
        checkpoint = json.loads((self.work/'ckpt').read_text())
        self.assertTrue(checkpoint['reason'])
        self.assertIn('utc', checkpoint)
        child, _ = children[0]; child.wait(timeout=5)

    def test_confirmed_exit_does_not_grow_stopping_journal_on_later_polls(self):
        children, spawn = self.capture_children()
        with mock.patch.object(M.subprocess, 'Popen', spawn), contextlib.redirect_stdout(io.StringIO()):
            r = self.admit(grace=1800)
        sv = M.Supervisor(self.st, str(self.lease))
        generation = self.st.lock('generation.lock')
        try: sv.begin_stop(r, 'resource breach: test', sv.deadline_bound)
        finally: generation.close()
        M.signal_exact(r['pid'], r['start'], signal.SIGTERM)
        children[0][0].wait(timeout=5)
        sv.poll()
        self.assertEqual(self.st.records()[r['name']]['state'], 'gone')
        entries = set(Path(self.st.recovery).glob('*.json'))
        for _ in range(3):
            self.t += 30
            self.assertIsNone(sv.poll())
        self.assertEqual(entries, set(Path(self.st.recovery).glob('*.json')))


if __name__ == '__main__':
    import unittest
    unittest.main()
