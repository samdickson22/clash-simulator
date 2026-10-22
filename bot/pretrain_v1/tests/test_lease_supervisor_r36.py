"""R36 fault regressions. Only disposable local state and reaped fixture children."""
import contextlib
import errno
import io
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from unittest import mock

from bot.pretrain_v1 import lease_supervisor as M
from bot.pretrain_v1.tests import test_lease_supervisor as T
from bot.pretrain_v1.tests import test_lease_supervisor_r35 as R35


class R36Test(T.Base):
    capture_children = R35.R35Test.capture_children

    def stopping_fixture(self):
        children, spawn = self.capture_children()
        with mock.patch.object(M.subprocess, 'Popen', spawn), contextlib.redirect_stdout(io.StringIO()):
            r = self.admit(code=T.IGNORER, grace=1800)
        epoch = self.t
        self.lease.write_text(json.dumps(dict(T.LEASE, reclaim=True)))
        sv = M.Supervisor(self.st, str(self.lease))
        sv.poll()
        r = self.st.records()[r['name']]
        self.assertEqual((r['state'], r['kill_at']), ('stopping', epoch+1740))
        self.assertTrue(M.alive(r['pid'], r['start']))
        self.assertIn((M.MARKER+'='+r['token']).encode(),
                      Path('/proc/%d/environ'%r['pid']).read_bytes().split(b'\0'))
        path = next(p for p in Path(self.st.recovery).glob('*.json')
                    if json.loads(p.read_text())['kind'] == 'stop')
        return r, sv, epoch, children[0][0], path

    def run_three(self, sv):
        cycles = []
        def cycle(_):
            cycles.append(1)
            if len(cycles) == 3: raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt): M.run_loop(sv, 30, cycle)
        self.assertEqual(len(cycles), 3)

    def test_republication_enospc_kills_real_child_while_seven_writes_fail(self):
        r, _, epoch, child, _ = self.stopping_fixture()
        before = Path(r['stop_file']).read_bytes()
        self.t = epoch+1900
        sv = M.Supervisor(self.st, str(self.lease))
        original = M.write_atomic
        failures = []
        def atomic(path, data):
            if path == r['stop_file']:
                failures.append(path)
                raise OSError(errno.ENOSPC, 'notification replacement unavailable')
            return original(path, data)
        # Keep exercising normal and emergency recovery after real KILL. The fault
        # stays installed through all seven publication attempts and liveness checks.
        with mock.patch.object(M, 'write_atomic', atomic), \
             mock.patch.object(M, 'scan', side_effect=OSError('unavailable telemetry')), \
             mock.patch.object(M, 'signal_exact', wraps=M.signal_exact) as sent:
            self.run_three(sv)
            self.assertIn(mock.call(r['pid'], r['start'], signal.SIGKILL), sent.call_args_list)
            self.assertTrue(T.wait_for(lambda: not M.alive(r['pid'], r['start']), 3))
            child.wait(timeout=5)
            for _ in range(max(0, 7-len(failures))): sv.stop_owned(dict(r), epoch)
        self.assertEqual(len(failures), 7)
        self.assertEqual(Path(r['stop_file']).read_bytes(), before)
        self.assertFalse(Path(self.st.dir, 'ended.json').exists())

    def test_no_first_signal_without_complete_current_generation_notification(self):
        r, _, epoch, child, _ = self.stopping_fixture()
        original = json.loads(Path(r['stop_file']).read_text())
        self.t = epoch+1900
        real_atomic = M.write_atomic
        def atomic(path, data):
            if path == r['stop_file']: raise OSError(errno.ENOSPC, 'notification unavailable')
            return real_atomic(path, data)
        variants = [None, '{', {}, dict(original, token='1'*32), dict(original, boot='old-boot'),
                    dict(original, name='previous-job'), dict(original, utc='bad'),
                    dict(original, reason=None), dict(reason='old', utc=M.iso(epoch))]
        for data in variants:
            with self.subTest(data=data):
                path = Path(r['stop_file'])
                if data is None: path.unlink(missing_ok=True)
                else: path.write_text(data if isinstance(data, str) else json.dumps(data))
                with mock.patch.object(M, 'write_atomic', atomic), \
                     mock.patch.object(M, 'signal_exact', wraps=M.signal_exact) as sent:
                    with self.assertRaises((OSError, ValueError)):
                        M.Supervisor(self.st, str(self.lease)).emergency(epoch)
                    sent.assert_not_called()
                self.assertTrue(M.alive(child.pid, r['start']))

    def test_initial_notification_write_failure_never_signals(self):
        children, spawn = self.capture_children()
        with mock.patch.object(M.subprocess, 'Popen', spawn), contextlib.redirect_stdout(io.StringIO()):
            r = self.admit(code=T.IGNORER, grace=1800)
        real_atomic = M.write_atomic
        def atomic(path, data):
            if path == r['stop_file']: raise OSError(errno.ENOSPC, 'initial notification unavailable')
            return real_atomic(path, data)
        with mock.patch.object(M, 'write_atomic', atomic), \
             mock.patch.object(M, 'signal_exact', wraps=M.signal_exact) as sent:
            with self.assertRaises(OSError): M.Supervisor(self.st, str(self.lease)).emergency(self.t)
            sent.assert_not_called()
            self.assertTrue(M.alive(children[0][0].pid, r['start']))

    def test_bad_journal_entries_isolated_existing_and_restart(self):
        for kind in ('json', 'schema', 'unreadable', 'unsafe', 'unsafe-record'):
            for historical in (False, True):
                for restart in (False, True):
                    with self.subTest(kind=kind, historical=historical, restart=restart):
                        # Each variant has independent observations, journal, and real children.
                        x = R36Test(); x.setUp()
                        try: x.bad_journal_case(kind, historical, restart)
                        finally: x.doCleanups()

    def bad_journal_case(self, kind, historical, restart):
        r, sv, epoch, child, path = self.stopping_fixture()
        good = path.read_bytes()
        if historical:
            request = json.loads(good)
            request['record']['token'] = '1'*32
            request['record']['log'] = str(Path(self.st.logs)/(r['name']+'-11111111.log'))
            self.st.journal(request)
            path = next(p for p in Path(self.st.recovery).glob('*.json')
                        if json.loads(p.read_text()).get('record', {}).get('token') == '1'*32)
            good = path.read_bytes()
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        if kind == 'json': path.write_text('{')
        if kind == 'schema':
            request = json.loads(good); request['record']['procs'] = 'invalid'
            # Correct digest: this tests schema validation independently of integrity.
            path.unlink()
            path = Path(self.st.recovery)/(M.request_digest(request)+'.json')
            M.write_atomic(str(path), request)
        if kind == 'unsafe-record':
            request = json.loads(good); request['record']['stop_file'] = str(self.tmp/'outside.stop')
            path.unlink()
            path = Path(self.st.recovery)/(M.request_digest(request)+'.json')
            M.write_atomic(str(path), request)
        if kind == 'unreadable':
            original_open = M.safe_open
            def opened(p, mode):
                if p == str(path) and mode in ('r', 'rb'): raise PermissionError('unreadable journal')
                return original_open(p, mode)
            stack.enter_context(mock.patch.object(M, 'safe_open', opened))
        if kind == 'unsafe':
            path.unlink(); outside = self.tmp/'untrusted.json'; outside.write_bytes(good)
            path.symlink_to(outside)
        self.t = epoch+1900
        if restart: sv = M.Supervisor(self.st, str(self.lease))
        with mock.patch.object(M, 'signal_exact', wraps=M.signal_exact) as sent:
            self.run_three(sv)
            self.assertIn(mock.call(r['pid'], r['start'], signal.SIGKILL), sent.call_args_list)
            self.assertTrue(T.wait_for(lambda: not M.alive(child.pid, r['start']), 3))
            child.wait(timeout=5)
        # Even after a fresh restart and confirmed draining, bad journals block receipts.
        for _ in range(2):
            self.assertIsNone(M.Supervisor(self.st, str(self.lease)).poll())
            self.assertFalse(Path(self.st.dir, 'ended.json').exists())
        self.assertTrue(sv.journal_issues)
        self.assertLessEqual(self.st.records()[r['name']]['kill_at'], epoch+1740)
        stack.close()
        if path.is_symlink(): path.unlink()
        path.write_bytes(good)
        # Schema case moved to a new filename. Restore under its canonical identity.
        if kind in ('schema', 'unsafe-record'):
            path.unlink()
            self.st.journal(json.loads(good))
        fresh = M.Supervisor(self.st, str(self.lease))
        self.assertFalse(fresh.journal_issues)
        self.assertEqual(fresh.poll(), 'ended')
        receipt = json.loads(Path(self.st.dir, 'ended.json').read_text())
        self.assertTrue(receipt['jobs_drained'])
        self.assertIs(receipt['owner_lease_updated'], False)

    def test_uncertain_journal_blocks_admission_without_global_stop(self):
        path = Path(self.st.recovery)/('0'*64+'.json'); path.write_text('{')
        with mock.patch.object(M.subprocess, 'Popen') as spawn:
            with self.assertRaisesRegex(SystemExit, 'uncertain.*journal'):
                self.admit()
            spawn.assert_not_called()

    def test_journal_damage_during_spawn_retains_and_stops_the_new_generation(self):
        children, spawn = self.capture_children()
        epoch = self.t
        def damaged(*a, **kw):
            child = spawn(*a, **kw)
            Path(self.st.recovery, '0'*64+'.json').write_text('{')
            return child
        with mock.patch.object(M.subprocess, 'Popen', damaged):
            with self.assertRaisesRegex(SystemExit, 'stop requested during spawn'):
                self.admit(code=T.IGNORER, grace=1800)
        r = self.st.records()['j1']; child, start = children[0]
        self.assertEqual(r['state'], 'stopping')
        self.assertIn([child.pid, start], r['procs'])
        self.t = epoch+1900
        self.assertIsNone(M.Supervisor(self.st, str(self.lease)).poll())
        self.assertTrue(T.wait_for(lambda: not M.alive(child.pid, start), 3))
        child.wait(timeout=5)
        self.assertFalse(Path(self.st.dir, 'ended.json').exists())

    def test_valid_global_request_survives_bad_entry_without_observation_cache(self):
        r, sv, epoch, child, _ = self.stopping_fixture()
        sv.halt(epoch)
        # Only the valid journal carries the global origin after this simulated restart.
        Path(sv.bound_path).unlink(); Path(self.st.halt).unlink()
        Path(self.st.recovery, '0'*64+'.json').write_text('{')
        self.st.save(dict(r, state='running'))
        self.t = epoch+1900
        sv = M.Supervisor(self.st, str(self.lease))
        self.assertEqual(sv.recovery_origin, epoch)
        with mock.patch.object(M, 'read_snapshot', side_effect=M.CadenceError('external budget')):
            with self.assertRaises(M.CadenceError): sv.poll()
            self.assertTrue(T.wait_for(lambda: not M.alive(child.pid, r['start']), 3))
            child.wait(timeout=5)
        self.assertTrue(sv.journal_issues)
        self.assertFalse(Path(self.st.dir, 'ended.json').exists())

    def test_damaged_duplicate_global_request_cannot_block_emergency_kill(self):
        r, sv, epoch, child, _ = self.stopping_fixture()
        sv.halt(epoch)
        path = next(p for p in Path(self.st.recovery).glob('*.json')
                    if json.loads(p.read_text())['kind'] == 'recovery')
        path.write_text('{')
        self.t = epoch+1900
        sv = M.Supervisor(self.st, str(self.lease))
        locks = [self.st.lock(n) for n in ('state.lock', 'generation.lock', 'observation.lock')]
        try:
            with mock.patch.object(M, 'LOCK_WAIT', .02), \
                 mock.patch.object(M, 'read_snapshot', side_effect=M.CadenceError('external budget')):
                sv.emergency(epoch)  # Held observation lock prevents reaching the external read.
                self.assertTrue(T.wait_for(lambda: not M.alive(child.pid, r['start']), 3))
                child.wait(timeout=5)
        finally:
            for lk in reversed(locks): lk.close()
        self.assertTrue(sv.journal_issues)
        self.assertIsNone(sv.poll())
        self.assertFalse(Path(self.st.dir, 'ended.json').exists())

    def test_uncertainty_survives_own_state_write_failures_without_masking_kill(self):
        r, sv, epoch, child, path = self.stopping_fixture()
        path.write_text('{')
        self.t = epoch+1900
        sv = M.Supervisor(self.st, str(self.lease))
        real_atomic = M.write_atomic
        def atomic(path, data):
            if path in (sv.bound_path, self.st.halt, str(Path(self.st.dir, 'status.json'))):
                raise OSError(errno.ENOSPC, 'own observation/receipt state unavailable')
            return real_atomic(path, data)
        with mock.patch.object(M, 'write_atomic', atomic):
            self.run_three(sv)
            self.assertTrue(sv.journal_issues)
            self.assertTrue(T.wait_for(lambda: not M.alive(child.pid, r['start']), 3))
            child.wait(timeout=5)
        self.assertTrue(M.Supervisor(self.st, str(self.lease)).journal_issues)
        self.assertIsNone(sv.poll())
        self.assertFalse(Path(self.st.dir, 'ended.json').exists())

    def test_changed_journal_never_adopts_unrelated_real_identity(self):
        for control in ('changed-list', 'changed-root', 'other-token', 'other-boot', 'wrong-start'):
            for restart in (False, True):
                with self.subTest(control=control, restart=restart):
                    x = R36Test(); x.setUp()
                    try: x.changed_identity_case(control, restart)
                    finally: x.doCleanups()

    def changed_identity_case(self, control, restart):
        r, sv, epoch, child, path = self.stopping_fixture()
        sv.restore_journal()  # Preserve previously validated proof in existing-instance variants.
        environment = dict(os.environ); environment.pop(M.MARKER, None)
        other = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                                 env=environment, start_new_session=True, cwd=str(self.work))
        start = M.proc_stat(other.pid)[4]
        def cleanup():
            M.signal_exact(other.pid, start, signal.SIGKILL); other.wait(timeout=5)
        self.addCleanup(cleanup)
        self.assertNotIn(other.pid, M.owned(dict(r), M.scan(), M.boot_id()))
        self.assertNotIn((M.MARKER+'='+r['token']).encode(),
                         Path('/proc/%d/environ'%other.pid).read_bytes().split(b'\0'))
        request = json.loads(path.read_text())
        request['record']['procs'].append([other.pid, start+(control == 'wrong-start')])
        if control == 'changed-root':
            request['record'].update(pid=other.pid, start=start, procs=[[other.pid, start]])
        if control == 'other-token':
            request['record']['token'] = '1'*32
            request['record']['log'] = str(Path(self.st.logs)/(r['name']+'-11111111.log'))
        if control == 'other-boot': request['record']['boot'] = 'old-boot'
        if control in ('changed-list', 'changed-root'): path.write_text(json.dumps(request))
        else: self.st.journal(request)
        self.t = epoch+1900
        if restart: sv = M.Supervisor(self.st, str(self.lease))
        with mock.patch.object(M, 'signal_exact', wraps=M.signal_exact) as sent:
            sv.poll()
            self.assertFalse(any(c.args[:2] == (other.pid, start) for c in sent.call_args_list))
        self.assertTrue(T.wait_for(lambda: not M.alive(child.pid, r['start']), 3))
        child.wait(timeout=5)
        self.assertTrue(M.alive(other.pid, start))
        if control in ('changed-list', 'changed-root'):
            self.assertTrue(sv.journal_issues)
            self.assertIsNone(sv.poll())
            self.assertFalse(Path(self.st.dir, 'ended.json').exists())


if __name__ == '__main__':
    import unittest
    unittest.main()
