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


if __name__=='__main__':unittest.main()
