"""CPU-only adversarial fixtures. Never inspect current jobs or call GPU/engine tools."""
import copy
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

import operate as O

TESTS = Path(__file__).absolute().parent/'cpu-tests'


def row(data):
    return dict(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))



# A separate subreaper owns every PID used here. Its scanner reads captured fixture PIDs only.
REAPING_FIXTURE = r"""
import ctypes,json,os,subprocess,sys,time
sys.path.insert(0,sys.argv[1]);import operate as O
assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0
S=O.r37();me=os.getpid();start=S.proc_stat(me)[4]
foreign=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(30)'])
foreign_dead=subprocess.Popen([sys.executable,'-B','-c','raise SystemExit(23)'])
job=O.Job.__new__(O.Job);job.S=S;job.children=[]
job.record=dict(pid=me,start=start,token='a'*32,boot='fixture',procs=[[me,start]])
if hasattr(job,'init_child_boundary'):job.init_child_boundary()
pid=None;direct=None;p=None
try:
 code='import os,time;pid=os.fork();\nif pid==0: time.sleep(.05);os._exit(0)\nprint(pid,flush=True);os._exit(11)'
 p=subprocess.Popen([sys.executable,'-B','-c',code],stdout=subprocess.PIPE,text=True)
 job.children.append(p);pid=int(p.stdout.readline());p.wait(timeout=3)
 direct=subprocess.Popen([sys.executable,'-B','-c','raise SystemExit(7)'])
 job.children.append(direct)
 end=time.monotonic()+3
 while time.monotonic()<end:
  st=S.proc_stat(pid);dead=S.proc_stat(foreign_dead.pid)
  if st is not None and st[0]=='Z' and st[1]==me and dead is not None and dead[0]=='Z':break
  time.sleep(.01)
 else:raise AssertionError('fixture adoption/death did not complete')
 def scan():
  out={}
  for x in (me,p.pid,pid,direct.pid,foreign.pid,foreign_dead.pid):
   st=S.proc_stat(x)
   if st is not None and st[0] not in 'ZX':
    out[x]=dict(ppid=st[1],sid=st[2],nice=st[3],start=st[4],env=b'',cmd=b'',cwd='')
  return out
 # Foreign children are visible, so boundary exclusion must protect their wait status.
 S.scan=scan
 S.boot_id=lambda:'fixture'
 job.cleanup()
 after=S.proc_stat(pid)
 assert after is None, 'R53-01: cleanup returned with never-scanned adopted zombie '+str(after)
 assert p.returncode==11 and p.wait(timeout=1)==11
 assert direct.returncode==7 and direct.wait(timeout=1)==7
 assert foreign.poll() is None
 assert foreign_dead.wait(timeout=2)==23, 'foreign Popen status was stolen'
 print(json.dumps(dict(adopted_reaped=True,direct_status=direct.returncode,launcher_status=p.returncode,foreign_status=23)))
finally:
 # Exact captured fixture cleanup, including the deliberately failing baseline.
 for child in (p,direct,foreign,foreign_dead):
  if child is not None:
   if child.poll() is None:child.kill()
   child.wait(timeout=3)
   if child.stdout:child.stdout.close()
 if pid is not None:
  st=S.proc_stat(pid)
  if st is not None:
   assert st[1]==me
   if st[0] not in 'ZX':S.signal_exact(pid,st[4],9)
   os.waitpid(pid,0)
  assert S.proc_stat(pid) is None
"""

class Fixtures(unittest.TestCase):
    def setUp(self):
        TESTS.mkdir(exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix='fixture-', dir=TESTS))
        # Preserve every attempt for independent review, including failing fixtures.
        self.home = self.root/'package'
        self.home.mkdir()
        for key, value in [('JOBS', self.root), ('HOME', self.home), ('DRIVER', self.home/'driver'),
                           ('READY', self.root/'ready')]:
            p = patch.object(O, key, value)
            p.start()
            self.addCleanup(p.stop)

    def put(self, name, obj):
        p = self.root/'receipts'/name
        p.parent.mkdir(exist_ok=True)
        data = O.encoded(obj) if not isinstance(obj, bytes) else obj
        p.write_bytes(data)
        return dict(path=str(p), sha256=row(data)['sha256'])

    def authorities(self):
        report = self.put('review.txt', b'CPU TEST FIXTURE ONLY')
        r49 = self.put('r49.txt', b'Narrow source eligibility, no operational authority')
        measurement = self.put('maxshape.json', {'status': 'pass'})
        physical = self.put('physical.json', dict(status='pass', scope='full-cuda-process', size='M',
            dtype='float64', anchor_sha256='b'*64, peak_process_bytes=12*2**30))
        gate = self.put('qualification.json', {'gates': {'independent_sol_high': {'evidence': report}}})
        precision = self.put('precision.json', {'parity_evidence': {'M': report, 'S100': report}})
        config = dict(host='127x09', size='M', workers=32, qualification_only=True, precision='float64',
            runtime=str(O.READY/'runtime'), actor_source=str(O.READY/'actor_source'),
            runtime_manifest={'path': str(self.root/'joint'), 'sha256': 'c'*64},
            anchor={'path': str(self.root/'anchor'), 'sha256': 'b'*64},
            precision_registration=precision, qualification_gate_receipt=gate,
            immutable_science={'seed': 2026102101, 'updates': 32},
            gpu_admission=dict(measurement=measurement, process_measurement=physical,
                               peak_process_bytes=12*2**30, peak_reserved_bytes=10*2**30))
        final = self.put('final.json', config)
        inv = dict(source_commit='f'*40, source_sha256='e'*64, r49_sha256=r49['sha256'],
                   joint_sha256='c'*64, inputs={}, source_files={}, prepared_config_values={'127x09': copy.deepcopy(config)})
        release = self.put('release.json', dict(schema='qualification-r40-release-v1', status='released',
            host='127x09', source_commit=inv['source_commit'], source_sha256=inv['source_sha256'],
            final_config=final, explicit_per_host_release=True, actual_measurement=True,
            exact_owned_tree_reaped=True, full_gpu_free=True, physical_measurement=physical,
            utc='2026-10-22T00:00:00Z'))
        extra_refs = [report, r49, measurement, physical, gate, precision, final, release]
        extras = [dict(x, bytes=Path(x['path']).stat().st_size) for x in extra_refs]
        review = self.put('operational-review.json', dict(schema='qualification-operational-review-v1', status='GO',
            scope='separate-six-hour-qualification', model='gpt-6.1-sol', effort='high', independent=True,
            host='127x09', source_commit=inv['source_commit'], source_sha256=inv['source_sha256'],
            final_config=final, package_sha256='a'*64, release=release, r49=r49, report=report,
            inventory_sha256=O.digest(inv), extra_files_sha256=O.digest(extras), phases=['source', 'inputs', 'soak']))
        c = dict(schema='qualification-operation-v1', host='127x09', source_commit=inv['source_commit'],
            source_sha256=inv['source_sha256'], package_sha256='a'*64, final_config=final,
            release=release, operational_review=review, r49=r49, extra_files=extras+[
                dict(review, bytes=Path(review['path']).stat().st_size)],
            out=str(O.HOME/'hosts/127x09/soak'), supervisor={'path': str(O.SUPERVISOR), 'sha256': O.SUPERVISOR_SHA},
            job_names={'source': 'qual-fe6-source', 'inputs': 'qual-fe6-inputs', 'soak': 'qual-fe6-soak'})
        return c, inv, config

    def replace_ref_json(self, c, key, update):
        obj = O.read_json(c[key]['path'])
        update(obj)
        Path(c[key]['path']).write_bytes(O.encoded(obj))
        c[key]['sha256'] = O.sha(c[key]['path'])


    def main_fixture(self, c, inv):
        incoming = self.home/'incoming'
        for relative, dst, frozen in O.payload_rows(inv, c, 'inputs'):
            O.copy_exact(dst, incoming/relative, frozen)
        contract = self.root/'contract.json'
        contract.write_bytes(O.encoded(c))
        (self.home/'inventory.json').write_bytes(O.encoded(inv))
        return contract, incoming

    def admit_fixture(self, c, contract, incoming, execve):
        from contextlib import ExitStack
        stack = ExitStack()
        ready_python = O.READY/'python/bin/python3.12'
        argv = ['operate.py', 'admit', 'source', '--contract', str(contract),
                '--contract-sha256', O.sha(contract), '--incoming', str(incoming)]
        for obj, key, value in [(O, 'HERE', self.home), (O, 'PYTHON', ready_python),
                (O.sys, 'base_prefix', str(O.READY/'python')), (O.sys, 'executable', str(ready_python)),
                (O.sys, 'argv', argv), (O.socket, 'gethostname', lambda: '127x09'),
                (O, 'package_pin', lambda: 'a'*64),
                (O, 'r37', lambda: SimpleNamespace(EXIT_MARGIN=600, STATE_ROOT=str(self.root/'state'),
                    boot_id=lambda: 'fixture', proc_stat=lambda pid: ('S', 1, pid, 10, 100))),
                (O, 'check_lease', lambda *a: (0, 96, 64)), (O, 'check_resources', lambda *a: None),
                (O.os, 'execve', execve)]:
            stack.enter_context(patch.object(obj, key, value))
        return stack

    def test_r53_failed_handoff_leaves_durable_exclusive_attempt(self):
        c, inv, _ = self.authorities()
        contract, incoming = self.main_fixture(c, inv)
        with self.admit_fixture(c, contract, incoming, Mock(side_effect=OSError('fixture exec failure'))):
            with self.assertRaisesRegex(OSError, 'exec failure'):
                O.main()
        attempt = self.home/'hosts/127x09/source.attempt.json'
        self.assertTrue(attempt.exists(), 'R53-02: failed handoff lost the phase attempt')
        handed = Mock(side_effect=AssertionError('duplicate reached R37'))
        with self.admit_fixture(c, contract, incoming, handed):
            with self.assertRaisesRegex(ValueError, 'phase already attempted'):
                O.main()
        handed.assert_not_called()

    def test_r53_real_orphan_exits_before_first_live_scan(self):
        script = self.root/'reaping-fixture.py'
        script.write_text(REAPING_FIXTURE)
        result = subprocess.run([sys.executable, '-B', str(script), str(O.HERE)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=15)
        (self.root/'reaping-fixture.log').write_text(result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)


    def claim(self, c, inv, phase='source'):
        S = SimpleNamespace(STATE_ROOT=str(self.root/'state'), boot_id=lambda: 'fixture',
                            proc_stat=O.r37().proc_stat)
        return O.claim_attempt(S, c, inv, phase)

    def test_r53_two_concurrent_admitters_only_one_reaches_r37_exec(self):
        c, inv, _ = self.authorities()
        contract, incoming = self.main_fixture(c, inv)
        read_fd, write_fd = os.pipe()
        pids = []
        def handoff(*args):
            O.write_new(self.home/('exec-'+str(os.getpid())+'.json'), {'argv': args[1]})
            os._exit(0)
        try:
            with self.admit_fixture(c, contract, incoming, handoff):
                for _ in range(2):
                    pid = os.fork()
                    if pid == 0:
                        os.close(write_fd)
                        os.read(read_fd, 1)
                        try:
                            O.main()
                        except (ValueError, FileExistsError):
                            os._exit(23)
                        except BaseException:
                            import traceback
                            traceback.print_exc()
                            os._exit(99)
                        os._exit(98)
                    pids.append(pid)
                os.write(write_fd, b'xx')
                statuses = [os.waitpid(pid, 0)[1] for pid in pids]
                pids.clear()
            self.assertEqual(sorted(os.waitstatus_to_exitcode(x) for x in statuses), [0, 23])
            handoffs = list(self.home.glob('exec-*.json'))
            self.assertEqual(len(handoffs), 1)
            argv = O.read_json(handoffs[0])['argv']
            self.assertEqual(argv[3], 'admit')
            self.assertIn('--admission-sha256', argv)
            self.assertEqual(argv[-1], O.sha(O.attempt_path(c, 'source')))
        finally:
            os.close(read_fd)
            os.close(write_fd)
            for pid in pids:
                os.waitpid(pid, 0)

    def test_r53_intent_fsync_completes_before_handoff(self):
        c, inv, _ = self.authorities()
        contract, incoming = self.main_fixture(c, inv)
        events = []
        original = O.os.fsync
        def sync(fd):
            events.append(('dir' if O.stat.S_ISDIR(os.fstat(fd).st_mode) else 'file',
                           os.readlink('/proc/self/fd/'+str(fd))))
            original(fd)
        def handoff(*_):
            path = str(O.attempt_path(c, 'source'))
            self.assertIn(('file', path), events)
            self.assertEqual(events[-1], ('dir', str(Path(path).parent)))
            self.assertIn(('dir', str(self.home)), events)  # hosts entry persisted
            self.assertIn(('dir', str(self.home/'hosts')), events)
            raise OSError('durable handoff')
        with self.admit_fixture(c, contract, incoming, handoff), patch.object(O.os, 'fsync', sync):
            with self.assertRaisesRegex(OSError, 'durable handoff'):
                O.main()

    def test_r54_winner_syncs_ancestor_while_creator_is_held_before_sync(self):
        import select
        c, inv, _ = self.authorities()
        contract, incoming = self.main_fixture(c, inv)
        created_r, created_w = os.pipe()
        release_r, release_w = os.pipe()
        pid = None
        events, captured = [], {}
        original = O.os.fsync
        try:
            pid = os.fork()
            if pid == 0:
                os.close(created_r)
                os.close(release_w)
                signal.signal(signal.SIGALRM, signal.SIG_DFL)
                signal.alarm(10)
                def held_sync(fd):
                    if os.readlink('/proc/self/fd/'+str(fd)) == str(self.home):
                        assert (self.home/'hosts').is_dir()
                        os.write(created_w, b'created')
                        assert os.read(release_r, 1) == b'x'
                        os._exit(71)  # Exit before this ancestor's real fsync.
                    original(fd)
                try:
                    with self.admit_fixture(c, contract, incoming, lambda *_: os._exit(99)), \
                         patch.object(O.os, 'fsync', held_sync):
                        O.main()
                except BaseException:
                    import traceback
                    traceback.print_exc()
                os._exit(98)
            os.close(created_w)
            created_w = None
            os.close(release_r)
            release_r = None
            self.assertTrue(select.select([created_r], [], [], 5)[0], 'creator did not reach hold')
            self.assertEqual(os.read(created_r, 64), b'created')
            self.assertFalse((self.home/'hosts/127x09').exists())
            def sync(fd):
                original(fd)
                events.append(('dir' if O.stat.S_ISDIR(os.fstat(fd).st_mode) else 'file',
                               os.readlink('/proc/self/fd/'+str(fd))))
            class Handoff(BaseException):
                pass
            def handoff(_, argv, env):
                captured.update(argv=argv, intent_sha256=O.sha(O.attempt_path(c, 'source')))
                raise Handoff
            with self.admit_fixture(c, contract, incoming, handoff), patch.object(O.os, 'fsync', sync):
                with self.assertRaises(Handoff):
                    O.main()
            os.write(release_w, b'x')
            _, status = os.waitpid(pid, 0)
            pid = None
            evidence = dict(creator_exit_status=os.waitstatus_to_exitcode(status),
                            winner_fsync_events=events, handoff=captured)
            (self.root/'r54-ancestor-sync.json').write_bytes(O.encoded(evidence)+b'\n')
            self.assertEqual(evidence['creator_exit_status'], 71)
            self.assertEqual(captured['argv'][-1], captured['intent_sha256'])
            path = O.attempt_path(c, 'source')
            self.assertIn(('dir', str(self.home)), events,
                          'R54-01: winner handed off without syncing the concurrently created ancestor')
            for ancestor in path.parents:
                self.assertIn(('dir', str(ancestor)), events)
            self.assertIn(('file', str(path)), events)
            self.assertEqual(events[-1], ('dir', str(path.parent)))
        finally:
            # Release and reap only the captured fixture, also on baseline failure.
            if pid is not None:
                os.close(release_w)
                release_w = None
                os.waitpid(pid, 0)  # Child's alarm bounds an unexpected stalled creator.
            for fd in (created_r, created_w, release_r, release_w):
                if fd is not None:
                    os.close(fd)

    def test_r53_failed_file_or_directory_fsync_preserves_refused_attempt(self):
        for kind in ('file', 'dir'):
            c, inv, _ = self.authorities()
            c['host'] = '127x09'
            # Independent retained fixture for each failure point.
            home = self.home/kind
            home.mkdir()
            with patch.object(O, 'HOME', home):
                directory = home/'hosts/127x09'
                directory.mkdir(parents=True)
                original = O.os.fsync
                def sync(fd):
                    target = os.readlink('/proc/self/fd/'+str(fd))
                    isdir = O.stat.S_ISDIR(os.fstat(fd).st_mode)
                    if (kind == 'file' and not isdir) or (kind == 'dir' and target == str(directory)):
                        raise OSError('fixture fsync failure')
                    original(fd)
                with patch.object(O.os, 'fsync', sync), self.assertRaisesRegex(OSError, 'fsync failure'):
                    self.claim(c, inv)
                self.assertTrue(O.attempt_path(c, 'source').exists())
                with self.assertRaisesRegex(ValueError, 'phase already attempted'):
                    self.claim(c, inv)

    def test_r53_early_entry_failure_and_duplicate_start_remain_refused(self):
        for boundary in ('r37', 'lease', 'job', 'subreaper'):
            c, inv, _ = self.authorities()
            home = self.home/boundary
            home.mkdir()
            with patch.object(O, 'HOME', home):
                pin = self.claim(c, inv)
                S = SimpleNamespace(EXIT_MARGIN=600)
                job = SimpleNamespace(record={'token': 'a'*32})
                with patch.object(O, 'r37', side_effect=OSError('early r37') if boundary == 'r37' else None,
                                  return_value=S), \
                     patch.object(O, 'check_lease', side_effect=ValueError('early lease') if boundary == 'lease' else None), \
                     patch.object(O, 'Job', side_effect=ValueError('early job') if boundary == 'job' else None,
                                  return_value=job), \
                     patch.object(O.ctypes, 'CDLL', return_value=SimpleNamespace(prctl=lambda *_: -1)):
                    with self.assertRaisesRegex((OSError, ValueError), 'early|subreaper'):
                        O.run_job(c, inv, 'source', home/'incoming', pin)
                self.assertTrue(O.attempt_path(c, 'source').exists())
                self.assertTrue((home/'hosts/127x09/source.started.json').exists())
                with self.assertRaisesRegex(ValueError, 'phase already attempted'):
                    self.claim(c, inv)
                with patch.object(O, 'r37', side_effect=AssertionError('second startup')):
                    with self.assertRaises(FileExistsError):
                        O.run_job(c, inv, 'source', home/'incoming', pin)

    def test_r53_real_stale_lease_entry_retains_intent_and_refuses_main(self):
        c, inv, _ = self.authorities()
        contract, incoming = self.main_fixture(c, inv)
        pin = self.claim(c, inv)
        S, lease, path, state, status, now = self.lease_fixture()
        with patch.object(O, 'r37', return_value=S), patch.object(O.time, 'time', return_value=now+61):
            with self.assertRaisesRegex(ValueError, 'stale/ending'):
                O.run_job(c, inv, 'source', incoming, pin)
        records = state/'jobs'
        records.mkdir()
        (records/(c['job_names']['source']+'.json')).write_bytes(O.encoded({'state': 'gone', 'token': 'd'*32}))
        execve = Mock(side_effect=AssertionError('readmission'))
        with self.admit_fixture(c, contract, incoming, execve):
            with self.assertRaisesRegex(ValueError, 'phase already attempted'):
                O.main()
        execve.assert_not_called()

    def test_r53_prior_ambiguous_generation_refused_without_marker(self):
        c, inv, _ = self.authorities()
        contract, incoming = self.main_fixture(c, inv)
        record = self.root/'state/127x09/jobs'/(c['job_names']['source']+'.json')
        record.parent.mkdir(parents=True)
        for raw in (b'{"state":"gone"}', b'{"state":"running"}', b'partial generation'):
            record.write_bytes(raw)
            execve = Mock(side_effect=AssertionError('old generation admitted'))
            with self.admit_fixture(c, contract, incoming, execve):
                with self.assertRaisesRegex(ValueError, 'prior R37 generation'):
                    O.main()
            execve.assert_not_called()
        self.assertFalse(O.attempt_path(c, 'source').exists())

    def test_r53_intent_binds_contract_phase_source_host_inventory_and_config(self):
        c, inv, _ = self.authorities()
        pin = self.claim(c, inv)
        cases = [('source_commit', '1'*40), ('source_sha256', '1'*64), ('package_sha256', '1'*64),
                 ('final_config', dict(c['final_config'], sha256='1'*64)),
                 ('job_names', dict(c['job_names'], source='qual-fe6-new'))]
        for key, value in cases:
            changed = copy.deepcopy(c)
            changed[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'binding changed'):
                O.enter_attempt(changed, inv, 'source', pin)
        with self.assertRaisesRegex(ValueError, 'binding changed'):
            O.enter_attempt(c, dict(inv, extra='changed'), 'source', pin)
        for key, value in [('host', '127x12'), ('phase', 'inputs')]:
            changed = copy.deepcopy(c)
            phase = 'source'
            if key == 'host':
                changed[key] = value
            else:
                phase = value
            target = O.attempt_path(changed, phase)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(O.attempt_path(c, 'source').read_bytes())
            with self.assertRaisesRegex(ValueError, 'binding changed'):
                O.enter_attempt(changed, inv, phase, pin)
        with self.assertRaisesRegex(ValueError, 'pin required'):
            O.enter_attempt(c, inv, 'source', None)
        O.attempt_path(c, 'source').write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, 'pin changed'):
            O.enter_attempt(c, inv, 'source', pin)
        self.assertFalse((self.home/'hosts/127x09/source.started.json').exists())

    def reaping_job(self):
        me = os.getpid()
        root = ('S', 1, me, 10, 100)
        job = O.Job.__new__(O.Job)
        job.children = [SimpleNamespace(pid=700009, returncode=0, poll=lambda: 0)]
        job.foreign_children, job.known_children = {}, set()
        job.child_boundary = (me, 100, me)
        job.child_generation = ('fixture', 'a'*32)
        job.record = dict(pid=me, start=100, boot='fixture', token='a'*32, procs=[[me, 100]])
        job.S = SimpleNamespace(proc_stat=lambda pid: root if pid == me else ('Z', me, me, 10, 110),
                                boot_id=lambda: 'fixture', signal_exact=Mock())
        job.members = lambda: {}
        return job

    def test_r53_reap_peek_does_not_consume_direct_or_foreign_popen(self):
        job = self.reaping_job()
        job.children = [SimpleNamespace(pid=700001)]
        job.foreign_children = {700002: 110}
        with patch.object(O, 'child_pids', return_value={700001, 700002}), \
             patch.object(O.os, 'waitid') as peek, patch.object(O.os, 'waitpid') as reap:
            self.assertTrue(job.reap_adopted())
        peek.assert_not_called()
        reap.assert_not_called()

    def test_r53_reap_rejects_pid_reuse_parent_change_and_unwaitable_zombie(self):
        me = os.getpid()
        for failure in ('reuse', 'parent', 'unwaitable', 'echild', 'not-reaped', 'old'):
            job = self.reaping_job()
            states = [('Z', me, me, 10, 110), ('Z', me, me, 10, 110)]
            if failure == 'reuse':
                states[1] = ('Z', me, me, 10, 111)
            if failure == 'parent':
                states[1] = ('Z', 2, me, 10, 110)
            if failure == 'old':
                states[0] = ('Z', me, me, 10, 99)
            root_stat = job.S.proc_stat
            job.S.proc_stat = lambda pid: root_stat(pid) if pid == me else states.pop(0)
            with patch.object(O, 'child_pids', return_value={700001}), \
                 patch.object(O.os, 'waitid', return_value=None if failure == 'unwaitable' else SimpleNamespace(si_pid=700001),
                              side_effect=ChildProcessError() if failure == 'echild' else None), \
                 patch.object(O.os, 'waitpid', return_value=(0, 0)) as reap:
                with self.subTest(failure=failure), self.assertRaises((ValueError, ChildProcessError)):
                    job.reap_adopted()
            if failure != 'not-reaped':
                reap.assert_not_called()

    def test_r53_unknown_owned_zombie_reaped_by_exact_pid_and_wnowait(self):
        job = self.reaping_job()
        with patch.object(O, 'child_pids', return_value={700001}), \
             patch.object(O.os, 'waitid', return_value=SimpleNamespace(si_pid=700001)) as peek, \
             patch.object(O.os, 'waitpid', return_value=(700001, 0)) as reap:
            self.assertTrue(job.reap_adopted())
        peek.assert_called_once_with(os.P_PID, 700001, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        reap.assert_called_once_with(700001, os.WNOHANG)
        self.assertIn((700001, 110), job.known_children)

    def test_r53_cleanup_refuses_unknown_unreaped_children_and_outer_deadline(self):
        job = self.reaping_job()
        job.reap_adopted = lambda: True
        clock = [0.0]
        with patch.object(O.time, 'monotonic', lambda: clock[0]), \
             patch.object(O.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0]+seconds)):
            with self.assertRaisesRegex(ValueError, 'cleanup incomplete'):
                job.cleanup()
            self.assertLessEqual(clock[0], 10.1)
            clock[0] = 0
            with self.assertRaisesRegex(ValueError, 'cleanup deadline'):
                job.cleanup(cooperative=1000)
            self.assertLessEqual(clock[0], 180.1)
        job.S.signal_exact.assert_not_called()


    def test_r53_cleanup_outer_alarm_interrupts_blocked_scan_and_restores_phase_wall(self):
        job = self.reaping_job()
        job.reap_adopted = lambda: False
        job.members = lambda: O.time.sleep(3)
        original_timer = O.signal.setitimer
        timers = []
        def shortened(which, seconds, *args):
            timers.append(seconds)
            return original_timer(which, .05 if seconds == 180 else seconds, *args)
        old_handler = O.signal.getsignal(O.signal.SIGALRM)
        started = O.time.monotonic()
        with patch.object(O.signal, 'setitimer', shortened):
            with self.assertRaisesRegex(TimeoutError, 'cleanup deadline'):
                O.bounded_cleanup(job)
        self.assertLess(O.time.monotonic()-started, 1)
        self.assertIn(180, timers)
        self.assertEqual(O.signal.getsignal(O.signal.SIGALRM), old_handler)
        self.assertEqual(O.signal.getitimer(O.signal.ITIMER_REAL)[0], 0)
        # A shorter phase timer keeps precedence and is not extended by cleanup.
        try:
            original_timer(O.signal.ITIMER_REAL, 10)
            job.cleanup = Mock()
            O.bounded_cleanup(job)
            remaining = O.signal.getitimer(O.signal.ITIMER_REAL)[0]
            self.assertGreater(remaining, 0)
            self.assertLessEqual(remaining, 10)
        finally:
            original_timer(O.signal.ITIMER_REAL, 0)

    def test_r53_reap_rejects_changed_boot_session_token_or_known_identity(self):
        me = os.getpid()
        for field in ('boot', 'session', 'token', 'known-start'):
            job = self.reaping_job()
            if field == 'boot':
                job.S.boot_id = lambda: 'changed'
            elif field == 'session':
                job.child_boundary = (me, 100, me+1)
            elif field == 'token':
                job.record['token'] = 'b'*32
            else:
                job.known_children.add((700001, 109))
            with patch.object(O, 'child_pids', return_value={700001}), \
                 patch.object(O.os, 'waitid') as peek, patch.object(O.os, 'waitpid') as reap:
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'boundary changed|PID was reused'):
                    job.reap_adopted()
            peek.assert_not_called()
            reap.assert_not_called()


    def test_r53_cleanup_reentry_cannot_renew_180_second_budget(self):
        job = self.reaping_job()
        clock = [0.0]
        job.cleanup = Mock(side_effect=lambda **_: clock.__setitem__(0, 181.0))
        with patch.object(O.time, 'monotonic', lambda: clock[0]), \
             patch.object(O.signal, 'setitimer') as timer:
            O.bounded_cleanup(job)
            with self.assertRaisesRegex(ValueError, 'cleanup deadline'):
                O.bounded_cleanup(job, cooperative=160)
        self.assertEqual(job.cleanup.call_count, 1)
        self.assertEqual(timer.call_args_list, [unittest.mock.call(signal.ITIMER_REAL, 180),
                                               unittest.mock.call(signal.ITIMER_REAL, 0)])


    def test_r53_unknown_child_without_owned_launch_refuses_reaping(self):
        job = self.reaping_job()
        job.children = []
        with patch.object(O, 'child_pids', return_value={700001}), \
             patch.object(O.os, 'waitid') as peek, patch.object(O.os, 'waitpid') as reap:
            with self.assertRaisesRegex(ValueError, 'no owned launch'):
                job.reap_adopted()
        peek.assert_not_called()
        reap.assert_not_called()

    def test_r53_partial_attempt_and_prior_start_or_receipt_are_terminal(self):
        c, inv, _ = self.authorities()
        S = SimpleNamespace(STATE_ROOT=str(self.root/'state'))
        for phase, suffix in [('source', '.attempt.json'), ('inputs', '.started.json'), ('soak', '.json')]:
            path = self.home/'hosts/127x09'/(phase+suffix)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'partial')
            with self.assertRaisesRegex(ValueError, 'phase already attempted'):
                O.refuse_attempt(S, c, phase)

    def test_no_overwrite_and_matching_file_idempotence(self):
        src, dst = self.root/'src', self.home/'tree/data'
        src.write_bytes(b'pinned')
        O.copy_exact(src, dst, row(b'pinned'))
        O.copy_exact(src, dst, row(b'pinned'))
        dst.write_bytes(b'sentinel')
        with self.assertRaisesRegex(ValueError, 'hash changed'):
            O.copy_exact(src, dst, row(b'pinned'))
        self.assertEqual(dst.read_bytes(), b'sentinel')

    def test_paths_links_and_special_files_fail_closed(self):
        src = self.root/'src'
        src.write_bytes(b'x')
        for target in (str(self.home)+'/../escape', '/tmp/outside', str(self.home)+'//escape'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                O.copy_exact(src, target, row(b'x'))
        (self.home/'link').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError):
            O.copy_exact(src, self.home/'link/escape', row(b'x'))
        (self.home/'file-link').symlink_to(src)
        with self.assertRaises(OSError):
            O.copy_exact(src, self.home/'file-link', row(b'x'))
        fifo = self.root/'fifo'
        os.mkfifo(fifo)
        with self.assertRaisesRegex(ValueError, 'regular file'):
            O.sha(fifo)

    def test_source_change_during_copy_is_retained_as_failed_partial(self):
        src, dst = self.root/'src', self.home/'partial'
        src.write_bytes(b'a'*(5 << 20))
        expected = row(src.read_bytes())
        calls = [0]
        def race():
            calls[0] += 1
            if calls[0] == 3:  # first copy block, after prevalidation
                src.write_bytes(b'z'*(5 << 20))
        with self.assertRaisesRegex(ValueError, 'source changed'):
            O.copy_exact(src, dst, expected, race)
        self.assertTrue(dst.exists())

    def test_write_new_is_exclusive(self):
        path = self.home/'receipt.json'
        O.write_new(path, {'status': 'fixture'})
        with self.assertRaises(FileExistsError):
            O.write_new(path, {'status': 'overwrite'})

    def test_duplicate_json_and_zero_pin_rejected(self):
        p = self.root/'duplicate.json'
        p.write_bytes(b'{"status":"GO","status":"NO-GO"}')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            O.read_json(p)
        with self.assertRaisesRegex(ValueError, 'nonzero'):
            O.ref({'path': str(p), 'sha256': '0'*64})
        for data in (b'{"x":1e9999}', b'{"x":NaN}', b'{"x":'+b'1'*1025+b'}'):
            p.write_bytes(data)
            with self.assertRaises(ValueError):
                O.read_json(p)

    def test_contract_valid_and_complete_authority_closure(self):
        c, inv, _ = self.authorities()
        O.validate_contract(c, inv, 'a'*64, '127x09')
        self.assertEqual(O.check_authority(c, inv)['host'], '127x09')
        # Constructing a valid external contract is possible without a hash cycle.
        incoming = self.home/'incoming'
        for rel, dst, r in O.payload_rows(inv, c, 'inputs'):
            O.copy_exact(dst, incoming/rel, r)
        self.assertEqual(O.check_authority(c, inv, O.payload_lookup(incoming, c, inv))['size'], 'M')

    def test_r54_installed_supervisor_binding_and_handoff(self):
        c, inv, _ = self.authorities()
        installed = '/mpac/sdicks02/repos/clasher-pv1-lease-r37-7851936824/lease_supervisor.py'
        c['supervisor'] = dict(path=installed,
            sha256='0613d6db62371eb197bb5d41cbf342b57f1998ddeb91e04c7c5ab2be36ac0ffc')
        O.validate_contract(c, inv, 'a'*64, '127x09')
        for key, value in [('path', '/mpac/sdicks02/repos/clasher-pv1-lease-20261022/bot/pretrain_v1/lease_supervisor.py'),
                           ('sha256', '1'*64)]:
            bad = copy.deepcopy(c)
            bad['supervisor'][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'R37 pin required'):
                O.validate_contract(bad, inv, 'a'*64, '127x09')
        contract, incoming = self.main_fixture(c, inv)
        handoff = Mock(side_effect=OSError('bound handoff'))
        with self.admit_fixture(c, contract, incoming, handoff):
            with self.assertRaisesRegex(OSError, 'bound handoff'):
                O.main()
        self.assertEqual(handoff.call_args.args[1][2], installed)

    def test_missing_release_and_changed_config(self):
        c, inv, _ = self.authorities()
        Path(c['release']['path']).unlink()
        with self.assertRaises(FileNotFoundError):
            O.check_authority(c, inv)
        c, inv, _ = self.authorities()
        Path(c['final_config']['path']).write_text('{}')
        with self.assertRaisesRegex(ValueError, 'pin changed'):
            O.check_authority(c, inv)

    def test_changed_source_package_host_and_review_are_rejected(self):
        for key, value in [('source_commit', '1'*40), ('source_sha256', '2'*64),
                           ('package_sha256', '3'*64), ('host', '127x12')]:
            c, inv, _ = self.authorities()
            c[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                O.validate_contract(c, inv, 'a'*64, '127x09')
        c, inv, _ = self.authorities()
        self.replace_ref_json(c, 'operational_review', lambda x: x.update(independent=False))
        with self.assertRaisesRegex(ValueError, 'operational review'):
            O.check_authority(c, inv)

    def test_release_claims_are_all_required(self):
        for flag in ('explicit_per_host_release', 'actual_measurement', 'exact_owned_tree_reaped', 'full_gpu_free'):
            c, inv, _ = self.authorities()
            self.replace_ref_json(c, 'release', lambda x: x.update({flag: False}))
            with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, 'physical release'):
                O.check_authority(c, inv)

    def test_extras_cannot_overwrite_code_prepared_tree_or_inputs(self):
        c, inv, _ = self.authorities()
        for path in (str(self.home/'operate.py'), str(self.root/'rl-input-roots-20261022/prepared-attempt2/new'),
                     str(self.root/'lease-20261022/127x09/HALT'),
                     str(self.root/'lease-1316-extension-20261022/r40-physical-0912/result.json')):
            bad = copy.deepcopy(c)
            bad['extra_files'].append(dict(path=path, sha256='1'*64, bytes=10))
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'overlaps'):
                O.validate_contract(bad, inv, 'a'*64, '127x09')
        inv['inputs'][c['final_config']['path']] = row(b'x')
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            O.validate_contract(c, inv, 'a'*64, '127x09')

    def test_final_science_change_rejected_even_with_rebound_authority(self):
        c, inv, _ = self.authorities()
        inv['prepared_config_values']['127x09']['immutable_science']['updates'] = 33
        self.replace_ref_json(c, 'operational_review', lambda x: x.update(inventory_sha256=O.digest(inv)))
        with self.assertRaisesRegex(ValueError, 'science/inputs'):
            O.check_authority(c, inv)

    def test_unlisted_and_changed_payload_receipts_rejected(self):
        c, inv, _ = self.authorities()
        lookup = O.payload_lookup(self.home/'incoming', c, inv)
        with self.assertRaisesRegex(ValueError, 'not explicitly supplied'):
            lookup(dict(path=str(self.root/'unknown'), sha256='1'*64))
        for rel, dst, r in O.payload_rows(inv, c, 'inputs'):
            O.copy_exact(dst, self.home/'incoming'/rel, r)
        Path(lookup(c['final_config'])).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'hash changed'):
            lookup(c['final_config'])

    def test_original_402_measurement_can_resolve_in_payload(self):
        c, inv, _ = self.authorities()
        item = c['extra_files'].pop(2)
        inv['inputs'][item['path']] = {k: item[k] for k in ('sha256', 'bytes')}
        for rel, dst, r in O.payload_rows(inv, c, 'inputs'):
            O.copy_exact(dst, self.home/'incoming'/rel, r)
        lookup = O.payload_lookup(self.home/'incoming', c, inv)
        self.assertEqual(O.sha(lookup({k: item[k] for k in ('path', 'sha256')})), item['sha256'])

    def test_full_source_includes_tests_and_rejects_extra_python(self):
        files = {'bot/__init__.py': b'', 'bot/pretrain_v1/a.py': b'x=1\n',
                 'bot/pretrain_v1/tests/test_a.py': b'# test\n', 'bot/pretrain_v1/catalog/catalog.json': b'{}'}
        for name, data in files.items():
            p = O.DRIVER/name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        refs = {n: row(v) for n, v in files.items()}
        inv = dict(source_files=refs, source_sha256=O.digest({n: v['sha256'] for n, v in refs.items()
                    if n.startswith('bot/pretrain_v1/') and n.endswith('.py')}))
        O.verify_source(inv)
        (O.DRIVER/'bot/pretrain_v1/extra.py').write_text('')
        with self.assertRaisesRegex(ValueError, 'extra/missing'):
            O.verify_source(inv)
        (O.DRIVER/'bot/pretrain_v1/extra.py').unlink()
        (O.DRIVER/'bot/pretrain_v1/tests/test_a.py').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'hash changed'):
            O.verify_source(inv)

    def test_ready_trees_reject_extra_changed_and_linked_files(self):
        config, manifest = {}, {}
        for key, location in (('files', 'runtime'), ('source_files', 'actor_source')):
            p = O.READY/location/'module.py'
            p.parent.mkdir(parents=True)
            p.write_bytes(b'pinned ready source')
            config[location] = str(p.parent)
            manifest[key] = {'module.py': O.sha(p)}
        config['runtime_manifest'] = self.put('joint.json', manifest)
        inv = {'joint_sha256': config['runtime_manifest']['sha256']}
        with patch.object(O, 'READY_COUNTS', {'files': 1, 'source_files': 1}):
            O.verify_ready(config, inv)
            extra = O.READY/'actor_source/untracked.py'
            extra.write_bytes(b'fallback source')
            with self.assertRaisesRegex(ValueError, 'extra/missing'):
                O.verify_ready(config, inv)
            extra.unlink()
            p = O.READY/'runtime/module.py'
            p.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'ready source changed'):
                O.verify_ready(config, inv)
            p.unlink()
            p.symlink_to(O.READY/'actor_source/module.py')
            with self.assertRaisesRegex(ValueError, 'contains link'):
                O.verify_ready(config, inv)

    def lease_fixture(self):
        now = O.utc('2026-10-22T22:00:00Z')
        lease = dict(project='clasher', coordinator_thread='test-thread', granted_by='test-parent',
            start_utc='2026-10-22T20:00:00Z', expected_end_utc='2026-10-25T07:53:00Z',
            reclaim=False, refused=False, status='active', max_workers=96, pss_cap_gb=64)
        S = O.r37()  # Module load only. No scans, telemetry, admission or live state calls.
        S.LEASE_DIR, S.STATE_ROOT = str(self.root/'leases'), str(self.root/'state')
        Path(S.LEASE_DIR).mkdir()
        leasepath = Path(S.LEASE_DIR)/'127x09.json'
        leasepath.write_bytes(O.encoded(lease))
        state = Path(S.STATE_ROOT)/'127x09'
        state.mkdir(parents=True)
        watcher = dict(pid=3363731, start=245569826, boot='test-boot')
        (state/'supervisor.json').write_bytes(O.encoded(watcher))
        status = dict(status='watching', reason=None, utc='2026-10-22T22:00:00Z', boot='test-boot',
            observed_lease=dict(valid=True, observed_at=now, sha256=O.sha(leasepath)),
            lease_identity=S.lease_identity(lease))
        (state/'status.json').write_bytes(O.encoded(status))
        S.boot_id = lambda: 'test-boot'
        S.alive = lambda pid, start: (pid, start) == (3363731, 245569826)
        return S, lease, leasepath, state, status, now

    def test_active_lease_reopened_by_path_and_refused_or_reclaim_stops(self):
        S, lease, path, state, status, now = self.lease_fixture()
        O.check_lease(S, '127x09', 24000, now)
        for key in ('reclaim', 'refused'):
            replacement = path.with_name('replacement')
            replacement.write_bytes(O.encoded(dict(lease, **{key: True})))
            os.replace(replacement, path)  # Independent arbitrary writer, no cooperative lock.
            with self.assertRaisesRegex(ValueError, 'reclaim/refused'):
                O.check_lease(S, '127x09', 24000, now)

    def test_stale_observation_changed_watcher_and_short_horizon(self):
        S, lease, path, state, status, now = self.lease_fixture()
        with self.assertRaisesRegex(ValueError, 'stale/ending'):
            O.check_lease(S, '127x09', 10, now+61)
        with self.assertRaisesRegex(ValueError, 'horizon'):
            O.check_lease(S, '127x09', 7*86400, now)
        S.alive = lambda *_: False
        with self.assertRaisesRegex(ValueError, 'watcher identity'):
            O.check_lease(S, '127x09', 10, now)

    def test_missing_lease_is_not_an_admission(self):
        S, lease, path, state, status, now = self.lease_fixture()
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            O.check_lease(S, '127x09', 10, now)

    def test_r37_unreadable_300_second_window_and_latched_refusal(self):
        S, lease, path, state, status, now = self.lease_fixture()
        st = SimpleNamespace(dir=str(state), h='127x09', requests=lambda: [], request_issues={})
        S.now = lambda: now
        sv = S.Supervisor(st, str(path))
        self.assertIsNotNone(sv.observe_lease())
        path.write_bytes(b'partial arbitrary writer')
        self.assertIsNone(sv.observe_lease())
        S.now = lambda: now+300
        self.assertIsNone(sv.observe_lease())
        self.assertIsNone(sv.ending)
        S.now = lambda: now+301
        self.assertIsNone(sv.observe_lease())
        self.assertEqual(sv.ending, 'lease unreadable')
        other = S.Supervisor(st, str(path))
        path.write_bytes(O.encoded(dict(lease, refused=True, status=None)))
        self.assertIsNone(other.observe_lease())  # Malformed schema cannot conceal the trigger.
        self.assertEqual(other.ending, 'refused')
        path.write_bytes(O.encoded(lease))
        other.observe_lease()
        self.assertEqual(other.ending, 'refused')

    def test_resource_caps_count_all_processes_and_pss_not_only_learner(self):
        procs = {i: dict(nice=10, clasher=True) for i in range(64)}
        S = SimpleNamespace(scan=lambda: procs, is_clasher=lambda p: p['clasher'],
            pss_bytes=lambda pid: 1 << 30, host_load=lambda: (64 << 30, 1))
        O.check_resources(S, 64, 64)
        for kwargs in ({'reserve_procs': 1}, {'reserve_pss': 1}):
            with self.assertRaises(ValueError):
                O.check_resources(S, 64, 64, **kwargs)
        procs[0]['nice'] = 0
        with self.assertRaisesRegex(ValueError, 'mem/load/nice'):
            O.check_resources(S, 64, 64)
        procs[0]['nice'] = 10
        S.host_load = lambda: (31 << 30, 1)
        with self.assertRaisesRegex(ValueError, 'mem/load/nice'):
            O.check_resources(S, 64, 64)
        S.host_load = lambda: (64 << 30, 91)
        with self.assertRaisesRegex(ValueError, 'mem/load/nice'):
            O.check_resources(S, 64, 64)

    def test_whole_tree_cleanup_includes_detached_token_and_descendants(self):
        S = O.r37()
        me = os.getpid()
        token = 'a'*32
        def proc(ppid, sid, start, marker=False):
            return dict(ppid=ppid, sid=sid, start=start, nice=10, cwd='', cmd=b'',
                        env=('CLASHER_LEASE_JOB='+token).encode() if marker else b'')
        procs = {me: proc(1, me, 1), 700001: proc(me, me, 2),
                 700002: proc(700001, 700002, 3), 700003: proc(1, 700003, 4, True),
                 700004: proc(1, 700004, 5)}
        S.scan = lambda: dict(procs)
        S.boot_id = lambda: 'fixture'
        S.proc_stat = lambda pid: None if pid not in procs else ('S', procs[pid]['ppid'],
                     procs[pid]['sid'], 10, procs[pid]['start'])
        signalled = []
        def exact(pid, start, sig):
            self.assertEqual(start, procs[pid]['start'])
            signalled.append((pid, sig))
            del procs[pid]
        S.signal_exact = exact
        job = O.Job.__new__(O.Job)
        job.S, job.children = S, []
        job.record = dict(pid=me, start=1, token=token, boot='fixture', procs=[[me, 1]])
        job.child_boundary = (me, 1, me)
        job.child_generation = ('fixture', token)
        job.foreign_children, job.known_children = {}, set()
        with patch.object(O, 'child_pids', return_value=set()):
            job.cleanup()
        self.assertEqual({pid for pid, _ in signalled}, {700001, 700002, 700003})
        self.assertIn(700004, procs)
        self.assertIn(me, procs)

    def test_stuck_cleanup_escalates_only_exact_owned_identities_within_bound(self):
        job = O.Job.__new__(O.Job)
        child = dict(start=123)
        job.children, job.record = [], {'procs': []}
        live, signals = {700001: child}, []
        job.members = lambda: dict(live)
        job.reap_adopted = Mock(return_value=False)  # Synthetic signal-only fixture.
        def exact(pid, start, sig):
            signals.append((pid, start, sig))
            if sig == signal.SIGKILL:
                live.pop(pid)
        job.S = SimpleNamespace(proc_stat=lambda _: None, signal_exact=exact)
        clock = [0.0]
        with patch.object(O.time, 'monotonic', lambda: clock[0]), patch.object(O.time, 'sleep',
                lambda seconds: clock.__setitem__(0, clock[0]+seconds)):
            job.cleanup()
        self.assertTrue(any(sig == signal.SIGKILL for _, _, sig in signals))
        self.assertLess(clock[0], 11)
        self.assertTrue(all((pid, start) == (700001, 123) for pid, start, _ in signals))

    def test_cpu_child_failure_and_timeout_use_bounded_owned_cleanup(self):
        # Launch only these known disposable CPU children. No /proc scan of current jobs.
        S = O.r37()
        job = O.Job.__new__(O.Job)
        job.children, job.tick = [], lambda: None
        job.S = SimpleNamespace(proc_stat=S.proc_stat, signal_exact=S.signal_exact, boot_id=lambda: 'fixture')
        job.record = dict(pid=os.getpid(), start=S.proc_stat(os.getpid())[4],
                          token='a'*32, boot='fixture', procs=[])
        job.init_child_boundary()
        def members():
            out = {}
            for child in job.children:
                st = S.proc_stat(child.pid)
                if st is not None and st[0] not in 'ZX':
                    out[child.pid] = {'start': st[4]}
            return out
        job.members = members
        try:
            with self.assertRaisesRegex(ValueError, 'child failed'):
                job.run([sys.executable, '-B', '-c', 'raise SystemExit(3)'], os.environ.copy(), 3)
            with self.assertRaisesRegex(ValueError, 'deadline'):
                job.run([sys.executable, '-B', '-c', 'import time; time.sleep(30)'], os.environ.copy(), .05)
            job.cleanup()
        finally:
            for p in job.children:
                if p.poll() is None:
                    p.kill()
                p.wait(timeout=3)
        self.assertTrue(all(p.poll() is not None for p in job.children))

    def test_failed_readiness_receipt_cannot_authorize_soak(self):
        c, inv, _ = self.authorities()
        p = O.receipt_path(c, 'inputs')
        O.write_new(p, dict(status='failed', host='127x09', phase='inputs'))
        with self.assertRaisesRegex(ValueError, 'receipt mismatch'):
            O.verify_receipt(c, inv, 'inputs')

    def test_next_phase_requires_prior_root_gone_and_no_whole_tree_survivors(self):
        c, inv, _ = self.authorities()
        record = dict(state='running', token='a'*32, boot='fixture')
        path = self.root/'state/127x09/jobs'/ (c['job_names']['source']+'.json')
        path.parent.mkdir(parents=True)
        path.write_bytes(O.encoded(record))
        S = SimpleNamespace(STATE_ROOT=str(self.root/'state'), boot_id=lambda: 'fixture', scan=lambda: {},
                            owned=Mock(return_value={}))
        with patch.object(O, 'verify_receipt', return_value={'lease_token': 'a'*32}):
            with self.assertRaisesRegex(ValueError, 'not R37 gone'):
                O.phase_done(S, c, inv, 'source')
            record['state'] = 'gone'
            path.write_bytes(O.encoded(record))
            S.owned.return_value = {700001: {'start': 123}}
            with self.assertRaisesRegex(ValueError, 'survivors'):
                O.phase_done(S, c, inv, 'source')
            S.owned.return_value = {}
            O.phase_done(S, c, inv, 'source')

    def test_readiness_failure_keeps_attempt_without_success_or_soak(self):
        c, inv, config = self.authorities()
        job = SimpleNamespace(record={'token': 'a'*32}, started=O.time.monotonic(), tick=Mock(),
                              cleanup=Mock(), peak_procs=1, peak_pss=1)
        def failed_probe(argv, env, seconds, result):
            O.write_new(result, {'source_sha256': inv['source_sha256'], 'cuda_initialized': True,
                                  'audit': {'status': 'NO-GO'}})
        job.run = Mock(side_effect=failed_probe)
        admission = self.claim(c, inv, 'inputs')
        with patch.object(O, 'r37', return_value=SimpleNamespace(EXIT_MARGIN=600)), \
             patch.object(O, 'check_lease'), patch.object(O, 'Job', return_value=job), \
             patch.object(O, 'check_authority', return_value=config), patch.object(O, 'payload_rows', return_value=[]), \
             patch.object(O, 'phase_done'), patch.object(O, 'verify_source'), patch.object(O, 'verify_ready'), \
             patch.object(O.signal, 'signal'), patch.object(O.signal, 'setitimer') as alarm, \
             patch.object(O.ctypes, 'CDLL', return_value=SimpleNamespace(prctl=lambda *_: 0)):
            with self.assertRaisesRegex(ValueError, 'CPU readiness failure'):
                O.run_job(c, inv, 'inputs', self.home/'incoming', admission)
        self.assertFalse(O.receipt_path(c, 'inputs').exists())
        self.assertTrue((self.home/'hosts/127x09/inputs.attempt.json').exists())
        self.assertEqual(job.run.call_count, 1)
        job.cleanup.assert_called_once_with(cooperative=0)
        self.assertIn(unittest.mock.call(O.signal.ITIMER_REAL, 180), alarm.call_args_list)

    def test_owned_staging_budget_is_enforced_separately_from_global_caps(self):
        job = O.Job.__new__(O.Job)
        job.started, job.last, job.limit, job.stopping = O.time.monotonic(), 0, 300, False
        job.stop_at, job.stop_file = O.time.time()+1000, self.home/'none.stop'
        job.c, job.phase, job.peak_procs, job.peak_pss = {'host': '127x09'}, 'source', 0, 0
        job.members = lambda: {i: {} for i in range(4)}
        job.S = SimpleNamespace(pss_bytes=lambda _: 1)
        with patch.object(O, 'check_lease', return_value=(0, 96, 64)), patch.object(O, 'check_resources'):
            with self.assertRaisesRegex(ValueError, 'owned job'):
                job.tick()
            job.members = lambda: {1: {}}
            job.S.pss_bytes = lambda _: 5 << 30
            with self.assertRaisesRegex(ValueError, 'owned job'):
                job.tick()

    def test_env_preserves_lease_and_device_and_sets_thread_one(self):
        inherited = dict(CLASHER_LEASE_JOB='a'*32, CLASHER_LEASE_STOP_FILE='/fixture/test.stop',
            CLASHER_LEASE_STOP_BY_UTC='2026-10-24T00:00:00Z', CUDA_VISIBLE_DEVICES='GPU-fixture',
            PYTHONPATH='/unreviewed', CLASHER_ROOT='/old', OMP_NUM_THREADS='128')
        with patch.dict(os.environ, inherited):
            cpu, gpu = O.environment(True), O.environment(False)
        for k in ('CLASHER_LEASE_JOB', 'CLASHER_LEASE_STOP_FILE', 'CLASHER_LEASE_STOP_BY_UTC'):
            self.assertEqual(gpu[k], inherited[k])
        self.assertEqual(gpu['CUDA_VISIBLE_DEVICES'], 'GPU-fixture')
        self.assertEqual(cpu['CUDA_VISIBLE_DEVICES'], '')
        self.assertNotIn('PYTHONPATH', gpu)
        self.assertNotIn('CLASHER_ROOT', gpu)
        self.assertTrue(all(gpu[k] == '1' for k in O.THREADS))


class FrozenInventory(unittest.TestCase):
    def test_exact_reviewed_source_aggregate_and_402_paths(self):
        inv = O.read_json(O.HERE/'inventory.json')
        self.assertEqual(inv['source_commit'], 'fe6d64214200679372f337bb37b33606f5c9997d')
        py = {n: r['sha256'] for n, r in inv['source_files'].items()
              if n.startswith('bot/pretrain_v1/') and n.endswith('.py')}
        self.assertEqual(len(py), 83)
        self.assertEqual(O.digest(py), 'ff71c87aa81d069f2574dcb30aff0df988a56a7a20d7b925a96f1441c669dd0e')
        self.assertTrue(any('/tests/' in n for n in py))
        self.assertEqual(len(inv['source_files']), 96)
        source = Path('/mpac/sdicks02/repos/clasher-pv1-input-roots-20261022')
        for name, frozen in inv['source_files'].items():
            O.verify(source/name, frozen)
        self.assertEqual(len(inv['inputs']), 402)
        for path in inv['inputs']:
            self.assertTrue(path.startswith('/mpac/sdicks02/jobs/clasher/rl-input-roots-20261022/prepared-attempt2/files/'))
        self.assertEqual({k: x['host'] for k, x in inv['prepared_config_values'].items()},
                         {'127x09': '127x09', '127x12': '127x12'})
        for ref in inv['prepared_configs']:
            self.assertEqual(O.sha(ref['path']), ref['sha256'])
            config = O.read_json(ref['path'])
            self.assertEqual(config, inv['prepared_config_values'][config['host']])


if __name__ == '__main__':
    unittest.main(verbosity=2)
