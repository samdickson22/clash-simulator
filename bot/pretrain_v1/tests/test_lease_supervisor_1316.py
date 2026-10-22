"""Host-cap and real process/thread affinity controls for the 13-16 extension."""
import json, os, signal, subprocess, sys, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from bot.pretrain_v1 import lease_supervisor as M
from bot.pretrain_v1.tests.test_lease_supervisor import Base, LEASE, CHECKPOINTER, wait_for


class HostCaps(unittest.TestCase):
    def test_hard_limits_and_tighter_lease_caps(self):
        for h, n in M.HOSTS.items():
            pss = 32 if h in M.AFFINITY_HOSTS else 64
            with self.subTest(host=h):
                self.assertEqual(M.validate_lease(dict(LEASE, max_workers=999, pss_cap_gb=999), h)[1:], (n, pss))
                self.assertEqual(M.validate_lease(dict(LEASE, max_workers=17, pss_cap_gb=19), h)[1:], (17, 19))
                self.assertEqual(M.validate_lease({k:v for k,v in LEASE.items() if k not in ('max_workers','pss_cap_gb')}, h)[1:], (n, pss))

    def test_old_hosts_do_not_touch_affinity(self):
        with mock.patch.object(M.os, 'sched_setaffinity') as put, mock.patch.object(M.os, 'sched_getaffinity') as get:
            for h in ('127x09','127x12','127x17'):
                M.constrain_self(h); self.assertIsNone(M.affinity_issue(h, {1: {}}))
            put.assert_not_called(); get.assert_not_called()

    def test_empty_intersection_refuses(self):
        with mock.patch.object(M.os, 'sched_getaffinity', return_value={32}), mock.patch.object(M.os, 'sched_setaffinity') as put:
            with self.assertRaisesRegex(RuntimeError, 'no allowed CPUs'): M.constrain_self('127x13')
            put.assert_not_called()


class Affinity(Base):
    def setUp(self):
        super().setUp()
        self.original = os.sched_getaffinity(0)
        self.addCleanup(os.sched_setaffinity, 0, self.original)
        self.inside = self.original & M.CPU_LIMIT
        if not self.inside: self.skipTest('fixture needs an allowed CPU in 0-31')
        for name, val in [('AFFINITY_HOSTS', frozenset(('testhost',))), ('HOSTS', {'testhost':32})]:
            p=mock.patch.object(M,name,val);p.start();self.addCleanup(p.stop)

    def test_admission_hard_process_and_pss_caps(self):
        for kw, reason in [(dict(workers=33),'procs'), (dict(pss_gb=33),'pss')]:
            with self.subTest(kw=kw), self.assertRaisesRegex(SystemExit,reason): self.admit(**kw)
        self.assertEqual(self.st.records(),{})

    def test_tighter_caps_persist_across_restart(self):
        self.lease.write_text(json.dumps(dict(LEASE,max_workers=20,pss_cap_gb=21)))
        sv=M.Supervisor(self.st,str(self.lease));sv.read_lease()
        self.lease.write_text(json.dumps(LEASE))
        restored=M.Supervisor(self.st,str(self.lease));restored.read_lease()
        self.assertEqual((restored.cap,restored.pss_cap),(20,21))

    def test_admit_inherits_narrower_mask_and_thread_descendants(self):
        cpu=min(self.inside);os.sched_setaffinity(0,{cpu})
        code='''import os,subprocess,sys,time,threading,json
p=subprocess.Popen([sys.executable,'-c','import os,time;open("grandmask","w").write(str(sorted(os.sched_getaffinity(0))));time.sleep(60)'])
open('grand','w').write(str(p.pid))
def run():
 open('threadmask','w').write(str(sorted(os.sched_getaffinity(0))))
 while True:time.sleep(.05)
threading.Thread(target=run,daemon=True).start()
open('ready','w').write('1')
while True:time.sleep(.05)'''
        r=self.admit(code=code)
        self.assertTrue(wait_for(lambda:(self.work/'grandmask').exists() and (self.work/'threadmask').exists()))
        self.assertEqual(os.sched_getaffinity(r['pid']),{cpu})
        self.assertEqual((self.work/'grandmask').read_text(),str([cpu]))
        self.assertEqual((self.work/'threadmask').read_text(),str([cpu]))
        self.assertIsNone(M.affinity_issue('testhost',M.owned(r,M.scan(),M.boot_id())))

    def escaped(self, kind):
        outside=self.original-M.CPU_LIMIT
        if not outside:self.skipTest('fixture needs CPU outside0-31')
        cpu=min(outside)
        code='''import os,time,threading,subprocess,sys
open('ready','w').write('1')
while not os.path.exists('go'):time.sleep(.01)
'''
        action="import os,time;os.sched_setaffinity(0,{%d});open('escaped','w').write('1');time.sleep(60)"%cpu
        if kind=='thread':code+="threading.Thread(target=lambda:exec(%r),daemon=True).start()\n"%action
        elif kind=='descendant':code+="p=subprocess.Popen([sys.executable,'-c',%r]);open('grand','w').write(str(p.pid))\n"%action
        else:code+=action+'\n'
        code+='while True:time.sleep(.05)'
        r=self.admit(code=code);(self.work/'go').touch()
        self.assertTrue(wait_for(lambda:(self.work/'escaped').exists()))
        # Unrelated fixture is never adopted or signalled.
        foreign=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],cwd='/',env={},start_new_session=True)
        self.addCleanup(foreign.wait);self.addCleanup(foreign.kill)
        sv=M.Supervisor(self.st,str(self.lease));sv.poll()
        saved=self.st.records()['j1'];self.assertEqual(saved['state'],'stopping')
        self.assertIn('CPU affinity',saved['stop_reason'])
        self.assertTrue(Path(saved['stop_file']).exists())
        self.assertTrue(list(Path(self.st.recovery).glob('*.json')))
        self.assertTrue(self.gone(sv,'j1'));self.assertIsNone(foreign.poll())

    def test_escaped_root_drains(self):self.escaped('root')
    def test_escaped_descendant_drains(self):self.escaped('descendant')
    def test_escaped_thread_drains(self):self.escaped('thread')

    def test_unobservable_affinity_drains(self):
        r=self.admit();get=os.sched_getaffinity
        def unavailable(pid):
            if pid==r['pid']:raise PermissionError('fixture denied')
            return get(pid)
        with mock.patch.object(M.os,'sched_getaffinity',unavailable):
            sv=M.Supervisor(self.st,str(self.lease));sv.poll()
        self.assertIn('unobservable',self.st.records()['j1']['stop_reason'])
        self.assertTrue(self.gone(sv,'j1'))

    def test_existing_escape_refuses_new_admission(self):
        r=self.admit();get=os.sched_getaffinity
        def escaped(pid):return {32} if pid==r['pid'] else get(pid)
        with mock.patch.object(M.os,'sched_getaffinity',escaped):
            with self.assertRaisesRegex(SystemExit,'existing job CPU affinity'):
                self.admit(name='other')
        self.assertNotIn('other',self.st.records())


    def test_live_task_listing_enoent_and_esrch_refuse_then_drain(self):
        r=self.admit(code="import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);open('ready','w').write('1');time.sleep(60)")
        listing=os.listdir
        for error in (FileNotFoundError,ProcessLookupError):
            def fail(path):
                if path=='/proc/%d/task'%r['pid']:raise error('live task listing fault')
                return listing(path)
            with mock.patch.object(M.os,'listdir',fail):
                with self.assertRaisesRegex(SystemExit,'existing job CPU affinity'):
                    self.admit(name='other')
                sv=M.Supervisor(self.st,str(self.lease));sv.poll()
                self.assertEqual(self.st.records()['j1']['state'],'stopping')
                self.assertTrue(M.group_alive(r['pid'],r['start']))
                self.assertTrue(Path(r['stop_file']).exists())
                self.assertTrue(list(Path(self.st.recovery).glob('*.json')))
        self.t+=130
        self.assertTrue(self.gone(sv,'j1'))

    def test_per_tid_esrch_is_unobservable_for_a_live_task(self):
        r=self.admit();get=os.sched_getaffinity
        def fail(pid):
            if pid==r['pid']:raise ProcessLookupError('live affinity read failed')
            return get(pid)
        with mock.patch.object(M.os,'sched_getaffinity',fail):
            sv=M.Supervisor(self.st,str(self.lease));sv.poll()
        self.assertEqual(self.st.records()['j1']['state'],'stopping')
        self.assertTrue(self.gone(sv,'j1'))

    def test_genuine_exited_task_does_not_report_affinity_failure(self):
        self.assertIsNone(M.affinity_issue('testhost',{99999999:{'start':1}}))

    def test_zombie_leader_retains_worker_through_restart_reclaim_and_kill(self):
        outside=self.original-M.CPU_LIMIT
        if not outside:self.skipTest('fixture needs an outside CPU')
        code="""import os,time,threading,ctypes,signal
signal.signal(signal.SIGTERM,signal.SIG_IGN)
def run():
 open('tid','w').write(str(threading.get_native_id()))
 while not os.path.exists('go'):time.sleep(.01)
 os.sched_setaffinity(0,{%d});open('escaped','w').write('1')
 while True:time.sleep(.05)
threading.Thread(target=run).start();open('ready','w').write('1')
while not os.path.exists('go'):time.sleep(.01)
ctypes.CDLL(None).pthread_exit(None)
"""%min(outside)
        children=[];spawn=subprocess.Popen
        def capture(*a,**kw):
            p=spawn(*a,**kw);children.append(p);return p
        with mock.patch.object(M.subprocess,'Popen',capture):r=self.admit(code=code)
        child=children[0]
        self.addCleanup(child.wait)
        self.addCleanup(lambda:M.signal_exact(r['pid'],r['start'],signal.SIGKILL,groups=True))
        (self.work/'go').touch()
        self.assertTrue(wait_for(lambda:(self.work/'escaped').exists() and M.proc_stat(r['pid'])[0]=='Z'))
        self.assertFalse(M.alive(r['pid'],r['start']))
        self.assertTrue(M.group_alive(r['pid'],r['start']))
        self.assertIn(r['pid'],M.job_scan('testhost'))
        self.assertGreater(M.group_pss_bytes(r['pid']),0)
        sv=M.Supervisor(self.st,str(self.lease));sv.poll()
        saved=self.st.records()['j1'];self.assertEqual(saved['state'],'stopping')
        self.assertIn([r['pid'],r['start']],saved['procs'])
        bound=saved['kill_at']
        self.lease.write_text(json.dumps(dict(LEASE,reclaim=True)))
        sv=M.Supervisor(self.st,str(self.lease));sv.poll()
        self.assertFalse(Path(self.st.dir,'ended.json').exists())
        self.assertIsNone(child.poll())
        self.assertLessEqual(self.st.records()['j1']['kill_at'],bound)
        self.t+=130;self.assertTrue(self.gone(sv,'j1'))
        self.assertEqual(child.wait(timeout=5),-signal.SIGKILL)
        self.assertEqual(sv.poll(),'ended')
        receipt=json.loads(Path(self.st.dir,'ended.json').read_text())
        self.assertTrue(receipt['jobs_drained']);self.assertFalse(receipt['owner_lease_updated'])

    def test_leader_can_exit_during_spawn_without_losing_admitted_group(self):
        code="""import time,threading,ctypes
threading.Thread(target=lambda:time.sleep(60)).start();open('ready','w').write('1')
ctypes.CDLL(None).pthread_exit(None)
"""
        children=[];spawn=subprocess.Popen
        def capture(*a,**kw):
            p=spawn(*a,**kw);children.append(p)
            self.assertTrue(wait_for(lambda:M.proc_stat(p.pid)[0]=='Z'))
            return p
        with mock.patch.object(M.subprocess,'Popen',capture):r=self.admit(code=code)
        self.addCleanup(children[0].wait)
        self.addCleanup(lambda:M.signal_exact(r['pid'],r['start'],signal.SIGKILL,groups=True))
        self.assertTrue(M.group_alive(r['pid'],r['start']))
        sv=M.Supervisor(self.st,str(self.lease));sv.poll()
        self.assertEqual(self.st.records()['j1']['state'],'running')
        self.assertIn([r['pid'],r['start']],self.st.records()['j1']['procs'])


if __name__=='__main__':unittest.main()
