"""Contained R34 regressions: synthetic PIDs, real locks/I/O, mocked spawn and signals."""
import contextlib
import io
import json
import signal
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from bot.pretrain_v1 import lease_supervisor as M
from bot.pretrain_v1.tests import test_lease_supervisor as T


class R34Test(T.Base):
    def setUp(self):
        super().setUp()
        self.r = dict(name='job', state='running', token='a'*32, boot=M.boot_id(), pid=9000000,
                      start=12345, procs=[[9000000,12345]], workers=1, pss_gb=1, gpu_gb=0,
                      grace=1800, admitted_utc=M.iso(self.t),
                      stop_file=str(Path(self.st.jobs, 'job.stop')),
                      log=str(Path(self.st.logs, 'job-aaaaaaaa.log')))
        self.st.save(self.r)
        self.procs = {9000000: dict(ppid=1, sid=9000000, nice=10, start=12345,
                                  env=(M.MARKER+'='+'a'*32).encode(), cmd=b'', cwd='')}
        for key, val in [('scan', lambda: dict(self.procs)),
                         ('proc_stat', lambda pid: ('S',1,pid,10,self.procs[pid]['start']) if pid in self.procs else None),
                         ('sample', lambda *a: dict(procs=0,pss=0,mem=100*M.GIB,load=1)),
                         ('LOCK_WAIT', .04)]:
            p = mock.patch.object(M, key, val); p.start(); self.addCleanup(p.stop)
        p = mock.patch.object(M, 'signal_exact', side_effect=self.signal)
        self.send = p.start(); self.addCleanup(p.stop)
        self.sv = M.Supervisor(self.st, str(self.lease))
        self.args = SimpleNamespace(name='job', workers=1, pss_gb=1, gpu_gb=0, grace=1800,
                                    cwd=str(self.work), cmd=['synthetic-command'])

    def signal(self, pid, start, sig):
        self.assertTrue(Path(self.r['stop_file']).exists())
        self.assertIn(pid, self.procs)
        self.assertEqual(start, self.procs[pid]['start'])
        return True

    def spawn(self, *args, **kw):
        self.procs[9000001] = dict(ppid=1,sid=9000001,nice=10,start=23456,
                                 env=(M.MARKER+'='+kw['env'][M.MARKER]).encode(),cmd=b'',cwd='')
        return SimpleNamespace(pid=9000001)

    def test_stale_gone_snapshot_cannot_overwrite_admission(self):
        # Same two-thread seam as SOL-R34: admission holds state.lock in sampling;
        # emergency captures the old gone generation while state.lock times out.
        self.st.save(dict(self.r, state='gone', procs=[])); self.procs.clear()
        self.sv.read_lease()
        sampled, proceed, captured, resume, gate = [threading.Event() for _ in range(5)]
        errors = []
        real_records, real_lock = self.st.records, self.st.lock
        def records():
            snapshot = real_records()
            if threading.current_thread().name == 'r34-recovery':
                captured.set(); self.assertTrue(resume.wait(3))
            return snapshot
        def lock(name, *a, **kw):
            if name == 'generation.lock' and threading.current_thread().name == 'r34-admission': gate.set()
            return real_lock(name, *a, **kw)
        def sample(*a):
            sampled.set(); self.assertTrue(proceed.wait(3))
            return dict(procs=0,pss=0,mem=100*M.GIB,load=1)
        def admission():
            try: M.admit(self.args, self.st, str(self.lease))
            except SystemExit: pass
            except BaseException as e: errors.append(e)
        def recovery():
            try:
                try: self.sv.poll()
                except TimeoutError: self.sv.emergency(self.t)
            except BaseException as e: errors.append(e)
        a = threading.Thread(target=admission, name='r34-admission')
        b = threading.Thread(target=recovery, name='r34-recovery')
        with mock.patch.object(self.st, 'records', records), mock.patch.object(self.st, 'lock', lock), \
             mock.patch.object(M, 'sample', sample), mock.patch.object(M.subprocess, 'Popen', self.spawn), \
             contextlib.redirect_stdout(io.StringIO()):
            try:
                a.start(); self.assertTrue(sampled.wait(3)); b.start(); self.assertTrue(captured.wait(3))
                proceed.set(); gate.wait(.02); resume.set()
            finally:
                proceed.set(); resume.set(); a.join(3); b.join(3)
        self.assertFalse(a.is_alive() or b.is_alive()); self.assertEqual(errors, [])
        self.assertNotIn(9000001, self.procs, 'HALT observed before final spawn gate must prevent spawn')
        self.assertEqual(real_records()['job']['state'], 'gone', 'empty gone snapshot must not be adopted')

    def spawn_race(self, point, fail_save=False):
        self.st.save(dict(self.r, state='gone', procs=[])); self.procs.clear(); self.sv.read_lease()
        entered, resume = threading.Event(), threading.Event()
        errors = []; real_save = self.st.save
        def popen(*a, **kw):
            if point == 'during': entered.set(); self.assertTrue(resume.wait(3))
            return self.spawn(*a, **kw)
        def save(r):
            if threading.current_thread().name == 'r34-admission' and r['state'] == 'running':
                if point == 'after': entered.set(); self.assertTrue(resume.wait(3))
                if fail_save: raise OSError('injected running save failure')
            if fail_save == 'all' and threading.current_thread().name == 'r34-admission' and r['state']=='stopping':
                raise OSError('injected stopping save failure')
            return real_save(r)
        def admission():
            try: M.admit(self.args, self.st, str(self.lease))
            except (SystemExit, OSError): pass
            except BaseException as e: errors.append(e)
        a = threading.Thread(target=admission, name='r34-admission')
        with mock.patch.object(M.subprocess, 'Popen', popen), mock.patch.object(self.st, 'save', save), \
             contextlib.redirect_stdout(io.StringIO()):
            try:
                a.start(); self.assertTrue(entered.wait(3))
                with self.assertRaises(TimeoutError): self.sv.poll()
                self.sv.emergency(self.t)
            finally: resume.set(); a.join(3)
        self.assertFalse(a.is_alive()); self.assertEqual(errors, [])
        r = self.st.records()['job']
        self.assertNotEqual(r['token'], self.r['token'])
        self.assertTrue(any(c.args[0] == 9000001 for c in self.send.call_args_list))
        self.assertTrue(Path(r['stop_file']).exists())
        restarted = M.Supervisor(self.st, str(self.lease)); self.assertIsNone(restarted.poll())
        self.assertFalse(Path(self.st.dir, 'ended.json').exists())
        self.assertIn([9000001,23456], self.st.records()['job']['procs'])
        self.t += 1740; restarted.poll()
        self.assertTrue(any(c.args == (9000001,23456,signal.SIGKILL) for c in self.send.call_args_list))
        self.procs.clear(); self.assertEqual(restarted.poll(), 'ended')
        self.assertFalse(json.loads(Path(self.st.dir, 'ended.json').read_text())['owner_lease_updated'])

    def test_emergency_during_spawn_keeps_new_generation_owned(self): self.spawn_race('during')
    def test_emergency_after_spawn_keeps_new_generation_owned(self): self.spawn_race('after')
    def test_emergency_during_spawn_and_running_save_failure(self): self.spawn_race('during', True)
    def test_emergency_after_spawn_and_running_save_failure(self): self.spawn_race('after', True)
    def test_emergency_during_spawn_and_all_record_saves_fail(self): self.spawn_race('during', 'all')
    def test_emergency_after_spawn_and_all_record_saves_fail(self): self.spawn_race('after', 'all')

    def test_emergency_save_failure_still_signals_owned_process(self):
        self.sv.poll()
        with mock.patch.object(self.st, 'save', side_effect=OSError('injected recovery save failure')):
            with self.assertRaises(OSError): self.sv.emergency(self.t)
        self.assertEqual(self.send.call_args.args[-1], signal.SIGTERM)
        self.t += 1740
        with mock.patch.object(self.st, 'save', side_effect=OSError('injected recovery save failure')):
            with self.assertRaises(OSError): self.sv.emergency(self.t-1740)
        self.assertEqual(self.send.call_args.args[-1], signal.SIGKILL)

    def test_failed_recovery_save_retains_origin_on_healthy_restart(self):
        self.sv.poll(); epoch = self.t
        with mock.patch.object(self.st, 'save', side_effect=OSError('injected recovery save failure')):
            with self.assertRaises(OSError): self.sv.emergency(epoch)
        self.t = epoch+1900
        restarted = M.Supervisor(self.st, str(self.lease)); restarted.poll()
        self.assertEqual(restarted.recovery_origin, epoch)
        self.assertLessEqual(self.st.records()['job']['kill_at'],epoch+1740)
        self.assertEqual(self.send.call_args.args[-1],signal.SIGKILL)

    def test_admission_publication_failure_without_emergency_keeps_intent_and_drains(self):
        self.st.save(dict(self.r,state='gone',procs=[])); self.procs.clear()
        real_save=self.st.save
        def save(r):
            if r['state']!='intent': raise OSError('injected publication failure')
            real_save(r)
        with mock.patch.object(self.st,'save',save), mock.patch.object(M.subprocess,'Popen',self.spawn):
            with self.assertRaises(OSError): M.admit(self.args,self.st,str(self.lease))
        self.assertEqual(self.st.records()['job']['state'],'intent')
        self.assertEqual(self.send.call_args.args,(9000001,23456,signal.SIGTERM))
        self.assertTrue(Path(self.st.halt).exists())
        self.t+=1900
        restarted=M.Supervisor(self.st,str(self.lease)); self.assertIsNone(restarted.poll())
        self.assertEqual(self.send.call_args.args,(9000001,23456,signal.SIGKILL))
        self.assertFalse(Path(self.st.dir,'ended.json').exists())

    def test_emergency_save_failure_does_not_skip_other_jobs_or_identities(self):
        other=dict(self.r,name='other',stop_file=str(Path(self.st.jobs,'other.stop')),
                   log=str(Path(self.st.logs,'other-aaaaaaaa.log')))
        self.st.save(other)
        with mock.patch.object(self.st,'save',side_effect=OSError('save failed')):
            with self.assertRaises(OSError): self.sv.emergency(self.t)
        self.assertTrue(Path(other['stop_file']).exists())
        self.assertGreaterEqual(self.send.call_count,2)

    def test_control_exceptions_escape_lease_retry_and_emergency_reload(self):
        for control in (M.CadenceError, KeyboardInterrupt, SystemExit):
            with self.subTest(control=control.__name__), mock.patch.object(M,'read_snapshot',side_effect=control):
                with self.assertRaises(control): self.sv.read_lease()
                self.assertIsNone(self.sv.unreadable_since)
                with self.assertRaises(control): self.sv.emergency(self.t)

    def test_emergency_enforces_cached_bound_before_external_read_control_failure(self):
        self.sv.poll(); self.sv.emergency(self.t); self.t+=1900
        with mock.patch.object(self.sv,'read_lease',side_effect=M.CadenceError('external read budget')):
            with self.assertRaises(M.CadenceError): self.sv.emergency(self.t)
        self.assertEqual(self.send.call_args.args[-1],signal.SIGKILL)

    def test_normal_poll_cannot_erase_concurrent_recovery_origin(self):
        self.sv.poll(); epoch=self.t
        observed, resume=threading.Event(),threading.Event(); errors=[]
        read=self.sv.read_lease
        def paused_read():
            result=read(); observed.set(); self.assertTrue(resume.wait(3)); return result
        def scan():
            if threading.current_thread().name=='r34-poll': raise M.CadenceError('failed after observation')
            return dict(self.procs)
        def poll():
            try: self.sv.poll()
            except M.CadenceError: pass
            except BaseException as e: errors.append(e)
        thread=threading.Thread(target=poll,name='r34-poll')
        with mock.patch.object(self.sv,'read_lease',paused_read), mock.patch.object(M,'scan',scan):
            try:
                thread.start(); self.assertTrue(observed.wait(3))
                M.Supervisor(self.st,str(self.lease)).emergency(epoch)
            finally: resume.set(); thread.join(3)
        self.assertFalse(thread.is_alive()); self.assertEqual(errors,[])
        self.assertEqual(json.loads(Path(self.sv.bound_path).read_text())['recovery_origin'],epoch)
        self.t=epoch+1900; restarted=M.Supervisor(self.st,str(self.lease)); restarted.poll()
        self.assertLessEqual(self.st.records()['job']['kill_at'],epoch+1740)
        self.assertEqual(self.send.call_args.args[-1],signal.SIGKILL)

    def test_nested_partial_json_real_loop_never_enters_emergency_at_two_polls(self):
        self.sv.poll(); self.lease.write_text('['*50000); epoch=self.t
        def sleep(_):
            self.t += 30
            if self.t > epoch+300: raise KeyboardInterrupt
        with mock.patch.object(self.sv,'emergency',wraps=self.sv.emergency) as emergency:
            with self.assertRaises(KeyboardInterrupt): M.run_loop(self.sv,30,sleep)
            emergency.assert_not_called()
        self.assertEqual(self.sv.unreadable_since,epoch)
        self.assertFalse(Path(self.st.halt).exists()); self.send.assert_not_called()

    def test_huge_caps_flags_and_cached_emergency_deadlines(self):
        for flag in (None, 'reclaim', 'refused'):
            with self.subTest(flag=flag):
                # Each variant gets a fresh contained state, with no live fixture children.
                self.st.save(self.r); self.t += 3000
                for p in ('deadline-bound.json', 'lease-identity.json', 'HALT', 'ended.json'):
                    path = Path(self.st.dir, p)
                    if path.exists(): path.unlink()
                stop = Path(self.r['stop_file'])
                if stop.exists(): stop.unlink()
                self.lease.write_text(json.dumps(T.LEASE)); self.send.reset_mock()
                sv = M.Supervisor(self.st, str(self.lease)); sv.poll(); epoch = self.t
                data = dict(T.LEASE, max_workers=10**400)
                if flag: data[flag] = True
                self.lease.write_text(json.dumps(data))
                for elapsed in (0,30,300):
                    self.t = epoch + elapsed; sv = M.Supervisor(self.st, str(self.lease)); sv.poll()
                    self.assertFalse(Path(self.st.halt).exists())
                    self.assertEqual(sv.unreadable_since, epoch)
                    if not flag:
                        self.assertEqual(self.st.records()['job']['state'], 'running'); self.send.assert_not_called()
                self.t = epoch+301; sv.poll()
                self.assertEqual(self.st.records()['job']['stop_reason'], flag or 'lease unreadable')
                self.assertTrue(stop.exists()); self.assertEqual(self.send.call_args.args[-1],signal.SIGTERM)
                # Any validation exception during emergency must leave cached bounds enforceable.
                self.t = epoch+2100
                with mock.patch.object(sv, 'read_lease', side_effect=OverflowError('external validation')):
                    sv.emergency(epoch+301)
                self.assertEqual(self.send.call_args.args[-1], signal.SIGKILL)
                self.assertLessEqual(self.st.records()['job']['kill_at'],epoch+(1740 if flag else 2041))

    def test_parser_errors_retry_across_restart_through_300_seconds(self):
        cases = ['['*50000, b'\xff', '{"max_workers":'+('1'*50000)+'}', 'x'*(1024*1024+1)]
        for raw in cases:
            with self.subTest(kind=str(raw[:20])):
                self.st.save(self.r); self.t += 1000
                stop=Path(self.r['stop_file'])
                if stop.exists(): stop.unlink()
                bound = Path(self.st.dir, 'deadline-bound.json')
                if bound.exists(): bound.unlink()
                self.lease.write_text(json.dumps(T.LEASE)); self.send.reset_mock()
                sv = M.Supervisor(self.st, str(self.lease)); sv.poll(); epoch = self.t
                self.lease.write_bytes(raw if isinstance(raw,bytes) else raw.encode())
                for elapsed in (0,30,299,300):
                    self.t = epoch+elapsed; sv = M.Supervisor(self.st,str(self.lease)); sv.poll()
                    self.assertEqual(sv.unreadable_since,epoch)
                    self.assertEqual(self.st.records()['job']['state'],'running')
                    self.assertFalse(Path(self.st.halt).exists()); self.send.assert_not_called()
                    self.assertFalse(stop.exists())
                self.t=epoch+301; sv.poll()
                self.assertEqual(self.st.records()['job']['stop_reason'],'lease unreadable')
                self.assertEqual(self.send.call_args.args[-1],signal.SIGTERM)
                self.lease.write_text(json.dumps(T.LEASE)); sv.read_lease()
                self.assertIsNone(sv.unreadable_since)

    def test_schema_total_for_parsed_json_values(self):
        values = [None,True,False,[],{},'',0,-1,10**400,float('inf'),float('nan')]
        for key in ('max_workers','pss_cap_gb','start_utc','expected_end_utc','status','reclaim','refused'):
            for value in values:
                with self.subTest(key=key,value=repr(value)[:25]):
                    try: M.validate_lease(dict(T.LEASE, **{key:value}), 'testhost')
                    except (ValueError,KeyError,TypeError): pass


class R34RealProcessTest(T.Base):
    def test_huge_cap_true_flags_create_atomic_checkpoint_before_real_term(self):
        atomic = T.CHECKPOINTER.replace('open("ckpt", "w").write(open(os.environ["CLASHER_LEASE_STOP_FILE"]).read());',
            'open("ckpt.tmp", "w").write(open(os.environ["CLASHER_LEASE_STOP_FILE"]).read()); os.replace("ckpt.tmp","ckpt");')
        for flag in ('reclaim','refused'):
            with self.subTest(flag=flag):
                for name in ('ready','ckpt'):
                    p=self.work/name
                    if p.exists(): p.unlink()
                bound=Path(self.st.dir,'deadline-bound.json')
                if bound.exists(): bound.unlink()
                self.lease.write_text(json.dumps(T.LEASE))
                r=self.admit(name=flag,code=atomic,grace=1800)
                self.lease.write_text(json.dumps(dict(T.LEASE,max_workers=10**400,**{flag:True})))
                sv=M.Supervisor(self.st,str(self.lease)); sv.poll()
                self.assertTrue(T.wait_for(lambda:not M.alive(r['pid'],r['start'])))
                self.assertEqual((self.work/'ckpt').read_bytes(),Path(r['stop_file']).read_bytes())
                self.assertIn(flag,(self.work/'ckpt').read_text())

    def test_huge_cap_without_flags_retries_then_real_kill_at_reserved_bound(self):
        r=self.admit(code=T.IGNORER,grace=120); epoch=self.t
        sv=M.Supervisor(self.st,str(self.lease)); sv.poll()
        self.lease.write_text(json.dumps(dict(T.LEASE,max_workers=10**400)))
        for elapsed in (0,30,300):
            self.t=epoch+elapsed; sv=M.Supervisor(self.st,str(self.lease)); sv.poll()
            self.assertTrue(M.alive(r['pid'],r['start']))
            self.assertFalse(Path(r['stop_file']).exists()); self.assertFalse(Path(self.st.halt).exists())
        self.t=epoch+301; sv.poll()
        self.assertTrue(Path(r['stop_file']).exists()); self.assertTrue(M.alive(r['pid'],r['start']))
        self.t=epoch+360; sv.poll(); self.assertTrue(M.alive(r['pid'],r['start']))
        self.t=epoch+361; sv.poll()
        self.assertTrue(T.wait_for(lambda:not M.alive(r['pid'],r['start'])))


if __name__ == '__main__':
    unittest.main()
