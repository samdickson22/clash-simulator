"""Independent A19 r4 delta reviewer tests (2026-10-10). Synthetic data and inert local
processes only: no production path, payload, fleet job, STOP or launcher call.

The r4 supervise.py (884f0304) and run_stage.py (8c3c0523) bytes are SHA-checked; only
ROOT/BASE/interpreter/lock-directory string constants are substituted.

Run from the repo root with the production interpreter version (3.12):
  nice -n 19 <python3.12> -B -m unittest discover -s \
    reports/strategy_council_20260928/live-loop/v4/l1/reviews/a19-reviewer-artifacts/r4 -p 'test_rev_a19_r4.py' -v
"""
import ast,contextlib,hashlib,json,math,os,random,signal,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
L1=HERE.parent.parent.parent
PKG=L1/'prepared/amendment19-review-r4'
R4=L1/'receipts/a1-body-seal-20261009-r4'
SUPERVISOR_SHA='884f0304c64c9369eccf7feb4df84616035a08ef5da5351d9c0567581ec46cd8'
RUNNER_SHA='8c3c0523883b53baa7bdb9109ff49c82288984797d8f81300f54e132bd39b9a4'
sys.path.insert(0,str(PKG))
import a19_common as C, a19_handoff, a19_resources

def sha_bytes(b):return hashlib.sha256(b).hexdigest()

def production_lock_source(lock_dir,root):
    """The exact production run_stage.lock() function, AST-extracted from 8c3c0523."""
    data=(R4/'run_stage.py').read_bytes();assert sha_bytes(data)==RUNNER_SHA
    tree=ast.parse(data);fn=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='lock']
    assert len(fn)==1
    src=ast.get_source_segment(data.decode(),fn[0])
    # include decorator line
    start=fn[0].decorator_list[0].lineno-1;end=fn[0].end_lineno
    src='\n'.join(data.decode().splitlines()[start:end])
    old="Path('/mpac/sdicks02/jobs/clasher/v4-queue-independent-verifier-20261009-r1/proofs')"
    assert src.count(old)==1
    return src.replace(old,'Path(%r)'%str(lock_dir))

RUN_STAGE=r'''
import contextlib,fcntl,json,os,random,signal,sys,time,hashlib
from pathlib import Path
ROOT=Path(__file__).parent;root=ROOT;mode=(root/'mode').read_text().strip()
if sys.argv[1]=='seal':
    (root/'state'/'body-seal.json').write_text(json.dumps({'synthetic':True})+'\n');sys.exit(0)
if mode=='complete':
    time.sleep(1.5)
    s=hashlib.sha256((root/'state'/'body-seal.json').read_bytes()).hexdigest()
    (root/'seal-verification.json').write_text(json.dumps(dict(verified=True,body_seal_sha256=s)));sys.exit(0)
if mode.startswith('realstop'):
    # Production lock() semantics: STOP is checked before every new outermost host-lock acquisition.
    _,hold,gap,seed=mode.split(':');hold=float(hold);gap=float(gap);r=random.Random(seed)
    held=set()
    exec((root/'lock_src.py').read_text())
    end=time.monotonic()+150
    while time.monotonic()<end:
        with lock('127x04'):time.sleep(hold)
        time.sleep(r.expovariate(1/gap) if gap>0 else 0)
    sys.exit(0)
time.sleep(150)
'''

class Fixture(unittest.TestCase):
    def start(self,mode):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);root=Path(t.name)/'r4';root.mkdir()
        (root/'state').mkdir();(Path(t.name)/'base/execution').mkdir(parents=True);locks=Path(t.name)/'proofs';locks.mkdir()
        src=(R4/'supervise.py').read_text();self.assertEqual(sha_bytes(src.encode()),SUPERVISOR_SHA)
        for old,new in [("Path('/mpac/sdicks02/jobs/clasher/v4-a1-body-seal-20261009-r4')",'Path(%r)'%str(root)),
                        ("Path('/mpac/sdicks02/jobs/clasher/v4-a1-dryrun-preparation-r2')",'Path(%r)'%str(Path(t.name)/'base')),
                        ("'/mpac/sdicks02/envs/clasher-gpu/bin/python'",repr(sys.executable))]:
            self.assertEqual(src.count(old),1);src=src.replace(old,new)
        (root/'supervise.py').write_text(src);(root/'run_stage.py').write_text(RUN_STAGE);(root/'mode').write_text(mode)
        (root/'lock_src.py').write_text(production_lock_source(locks,root))
        (root/'truth-copy-preflight.json').write_text(json.dumps(dict(preflight_pass=True,validation_episodes=['e%d'%i for i in range(64)])))
        log=(Path(t.name)/'sup.log').open('wb');self.addCleanup(log.close)
        p=subprocess.Popen([sys.executable,'-B',str(root/'supervise.py')],cwd=t.name,stdout=log,stderr=log,start_new_session=True)
        self.addCleanup(self.reap,p,root)
        deadline=time.monotonic()+30
        while not (root/'verify-identity.json').exists():
            self.assertLess(time.monotonic(),deadline);self.assertIsNone(p.poll());time.sleep(.02)
        out=Path(t.name)/'attempt';out.mkdir()
        seal={'path':str(root/'state/body-seal.json'),'sha256':C.sha(root/'state/body-seal.json')}
        return p,root,out,seal
    def reap(self,p,root):
        if (root/'verify-identity.json').exists():
            v=C.load(root/'verify-identity.json')
            with contextlib.suppress(ProcessLookupError,PermissionError):os.killpg(v['pid'],signal.SIGKILL)
        with contextlib.suppress(ProcessLookupError):os.killpg(p.pid,signal.SIGKILL)
        p.wait()
    def proof(self,out,seal):
        inv=out/('verification-'+'b'*32);inv.mkdir()
        return C.write(inv/'verified.json',dict(verified=True,stage='a1-verify',body_seal_sha256=seal['sha256']))
    def handoff(self,root,out,seal,guard=lambda:None,timeout=30,**kw):
        with patch.object(a19_handoff,'PYTHON',sys.executable):
            return a19_handoff.serial_handoff(root,out,seal,True,guard,timeout=timeout,**kw)

class RunnerStopCheckRace(Fixture):
    """F1: production run_stage.lock() raises RuntimeError('Operational stop requested') when it
    sees STOP before the supervisor's 5 s poll sends SIGTERM. The child then exits 1, not -15."""
    def test_runner_stop_check_turns_supersession_into_failure_after_irreversible_stop(self):
        p,root,out,seal=self.start('realstop:0.05:0.05:1')
        with self.assertRaisesRegex(ValueError,'Unexpected serial verification exit'):
            self.handoff(root,out,seal,parallel_receipt=self.proof(out,seal))
        p.wait(timeout=20)
        self.assertTrue((root/'STOP').exists())
        ex=C.load(root/'verify-exit.json');fail=C.load(root/'failure.json')
        self.assertEqual(ex['exit_code'],1)
        self.assertEqual((fail['stage'],fail['exit_code']),('verify',1))
        self.assertIn('RuntimeError: Operational stop requested',(root/'verify.log').read_text())
        self.assertTrue((out/'handoff-intent.json').exists());self.assertFalse((out/'handoff.json').exists())
        # Dead end: no later A19 a1-verify attempt can even pass the read-only pre-check.
        out2=out.parent/'attempt2';out2.mkdir()
        with self.assertRaisesRegex(ValueError,'Pre-existing failure/STOP'):
            self.handoff(root,out2,seal,check_only=True)

    def test_outcome_rate_at_measured_04_lock_cadence(self):
        """04 seal child, 04:05Z, 90 s /proc fd sampling: ~47 new outermost io.lock acquisitions
        (>=0.52/s), lock held 56% of samples => hold ~1.07 s, gap ~0.85 s."""
        outcomes=[]
        for seed in range(6):
            with self.subTest(seed=seed):
                p,root,out,seal=self.start('realstop:1.07:0.85:%d'%seed)
                time.sleep(random.Random(seed).uniform(0,5))  # random phase vs the supervisor's 5 s poll
                try:
                    status,_=self.handoff(root,out,seal,parallel_receipt=self.proof(out,seal));outcomes.append(status)
                except ValueError as exc:outcomes.append(str(exc))
                p.wait(timeout=20)
        (HERE/'stop-race-outcomes.json').write_text(json.dumps(outcomes,indent=1)+'\n')
        self.assertIn('Unexpected serial verification exit',outcomes)

class VerifyThenRetireOrdering(Fixture):
    def test_check_only_never_writes_stop(self):
        p,root,out,seal=self.start('long')
        self.assertEqual(self.handoff(root,out,seal,check_only=True),('SERIAL_RUNNING',None))
        self.assertFalse((root/'STOP').exists());self.assertEqual(sorted(os.listdir(out)),[])
    def test_no_stop_without_or_with_foreign_parallel_proof(self):
        p,root,out,seal=self.start('long')
        with self.assertRaisesRegex(ValueError,'Successful parallel verification required'):self.handoff(root,out,seal)
        other=out.parent/'other';other.mkdir()
        with self.assertRaisesRegex(ValueError,'must belong to this attempt'):
            self.handoff(root,out,seal,parallel_receipt=self.proof(other,seal))
        self.assertFalse((root/'STOP').exists())
    def test_seal_change_before_handoff_blocks_stop(self):
        p,root,out,seal=self.start('long');proof=self.proof(out,seal)
        Path(seal['path']).write_text('{"synthetic": false}\n')
        with self.assertRaisesRegex(ValueError,'Seal changed before handoff'):self.handoff(root,out,seal,parallel_receipt=proof)
        self.assertFalse((root/'STOP').exists())
    def test_serial_finishing_during_parallel_binds_original_and_never_stops(self):
        p,root,out,seal=self.start('complete');p.wait(timeout=20)
        self.assertTrue((root/'complete.json').exists())
        status,rec=self.handoff(root,out,seal,parallel_receipt=self.proof(out,seal))
        self.assertEqual(status,'SERIAL_ALREADY_COMPLETE');self.assertFalse((root/'STOP').exists())
        self.assertEqual(C.pinned(rec)['original_receipt']['path'],str(root/'seal-verification.json'))
        # A second completion record for the same attempt is impossible (exclusive create).
        with self.assertRaises(FileExistsError):self.handoff(root,out,seal,parallel_receipt=self.proof_again(out,seal))
    def proof_again(self,out,seal):
        inv=out/('verification-'+'c'*32);inv.mkdir()
        return C.write(inv/'verified.json',dict(verified=True,stage='a1-verify',body_seal_sha256=seal['sha256']))
    def test_post_stop_guard_exception_strands_attempt_after_irreversible_stop(self):
        """F2: guard() is still called in the post-STOP wait loop; any hard-fail there (PSI 120 s,
        deadline, memory/disk floor) fails the A19 attempt after STOP is already written."""
        p,root,out,seal=self.start('long')
        def guard():
            if (root/'STOP').exists():raise ValueError('Sustained hard host memory pressure')
        with self.assertRaisesRegex(ValueError,'Sustained hard host memory pressure'):
            self.handoff(root,out,seal,guard=guard,parallel_receipt=self.proof(out,seal))
        self.assertEqual(p.wait(timeout=30),1)
        self.assertTrue((root/'STOP').exists());self.assertEqual(C.load(root/'verify-exit.json')['exit_code'],-15)
        self.assertFalse((out/'handoff.json').exists())  # serial retired, A19 has no completion

class PressureSemantics(unittest.TestCase):
    def run_seq(self,seq):
        w=a19_resources.PressureWatch();out=[]
        for t,full in seq:out.append(w.check(dict(some=full,full=full),t))
        return out
    def test_pause_after_30s_not_before(self):
        self.assertFalse(self.run_seq([(0,10.),(29.9,10.)])[-1])
        self.assertTrue(self.run_seq([(0,10.),(30,10.)])[-1])
        self.assertFalse(self.run_seq([(0,10.),(15,9.99),(30,10.)])[-1])  # dip resets
    def test_resume_needs_120s_below_5_and_5_resets(self):
        base=[(0,10.),(30,10.)]
        self.assertTrue(self.run_seq(base+[(31,4.9),(150.9,4.9)])[-1])
        self.assertFalse(self.run_seq(base+[(31,4.9),(151,4.9)])[-1])
        self.assertTrue(self.run_seq(base+[(31,4.9),(100,5.0),(151,4.9),(220,4.9)])[-1])
    def test_some_only_never_pauses(self):
        w=a19_resources.PressureWatch()
        for t in range(0,300,10):self.assertFalse(w.check(dict(some=99.,full=0.),t))
    def test_hard_stop_at_120s_of_30(self):
        w=a19_resources.PressureWatch();w.check(dict(some=30.,full=30.),0);w.check(dict(some=30.,full=30.),119.9)
        with self.assertRaisesRegex(ValueError,'Sustained hard'):w.check(dict(some=30.,full=30.),120)
        w=a19_resources.PressureWatch();w.check(dict(some=30.,full=30.),0);w.check(dict(some=0.,full=29.9),60)
        self.assertTrue(w.check(dict(some=30.,full=30.),179)) # reset by dip; still paused (>=10 for 30 s)
    def test_invalid_psi_rejected(self):
        for bad in ('some avg10=nan avg60=0 avg300=0 total=0\nfull avg10=0 avg60=0 avg300=0 total=0',
                    'some avg10=0 avg60=0 avg300=0 total=0','some avg10=101 avg60=0 avg300=0 total=0\nfull avg10=0 avg60=0 avg300=0 total=0'):
            with self.assertRaises(ValueError):a19_resources.pressure_values(bad)

if __name__=='__main__':unittest.main()
