"""Independent A20 r1 reviewer tests (2026-10-10). Synthetic files on 05 plus, if
present, copies of real 04 decoder records in A20_REAL_DIR. Never touches 04.

Run from l1 with the composed runtime first on sys.path:
  PYTHONPATH=prepared/amendment20-review-r1/composed-runtime \
  python3.12 -B -m unittest discover -s reviews/a20-reviewer-artifacts -p 'test_rev_a20.py' -v
"""
import contextlib,copy,datetime,fcntl,gzip,hashlib,importlib.util,json,os,subprocess,sys,tempfile,time,types,unittest
from pathlib import Path
from unittest.mock import patch
import a20_io as A
import a19_resources as R
HERE=Path(__file__).resolve().parent;L=HERE.parents[1]
FROZEN_IO=L/'prepared/amendment18-review-r2/queue_audit_io_v4.py'
REAL=Path(os.environ.get('A20_REAL_DIR','/tmp/sdicks02/a20-review-data'))

def frozen_io():
    spec=importlib.util.spec_from_file_location('rev_frozen_io',FROZEN_IO);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def sha(b):return hashlib.sha256(b).hexdigest()

class Base(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name);self.io=frozen_io()
        self.assertEqual(sha(FROZEN_IO.read_bytes()),'1df4d0c1627aaca9945294cd83eac2584b7a0258fb472a191b70ce0c770bff00')
        self.stack=contextlib.ExitStack();self.addCleanup(self.stack.close)
        for obj,name,value in [(A,'LOCK_ROOT',self.root),(R,'LOCK_ROOT',self.root),(self.io,'ROOTS',(str(self.root)+'/',))]:
            self.stack.enter_context(patch.object(obj,name,value))
        self.stack.enter_context(patch.object(self.io,'local',return_value=True))
    def put(self,name,blob):
        p=self.root/name;p.write_bytes(blob);return p
    def run_records(self,adapter,path,pin,consume=lambda s:[bytes(x) for x in s]):
        """adapter: 'frozen' = A19 r5 whole-context lock, 'a20' = narrowed. Returns (outcome, ledger)."""
        wrap=R.io_locks if adapter=='frozen' else A.io_locks
        with self.io.capture_evidence() as ledger:
            try:
                with wrap(self.io,lambda:None),self.io.records('127x04',str(path),pin) as s:out=('ok',consume(s))
            except BaseException as e:out=('err',type(e).__name__,str(e))
        return out,dict(ledger)
    def holder(self,host='127x04',seconds=1.0):
        """External process holding the host lock with a blocking flock (like the serial runner)."""
        ready=self.root/('ready-%f'%time.time())
        code='import fcntl,sys,time,pathlib;f=open(sys.argv[1],"a");fcntl.flock(f,fcntl.LOCK_EX);pathlib.Path(sys.argv[2]).touch();time.sleep(float(sys.argv[3]))'
        p=subprocess.Popen([sys.executable,'-c',code,str(self.root/(host+'.io.lock')),str(ready),str(seconds)])
        while not ready.exists():time.sleep(.01)
        return p

@unittest.skipUnless(REAL.is_dir() and any(REAL.glob('*.gz')),'real 04 record copies absent')
class RealRecordEquivalence(Base):
    def test_real_04_decoder_records_identical_rows_and_ledger(self):
        for src in sorted(REAL.glob('*.gz')):
            with self.subTest(src.name):
                blob=src.read_bytes();p=self.put(src.name,blob);pin=sha(blob)
                f=self.run_records('frozen',p,pin);a=self.run_records('a20',p,pin)
                self.assertEqual(f,a);self.assertEqual(f[0][0],'ok');self.assertEqual(a[1],{('127x04',str(p)):pin})
                # Also semantically: parsed rows identical
                self.assertEqual([json.loads(x) for x in f[0][1]],[json.loads(x) for x in a[0][1]])

class FailureClasses(Base):
    def setUp(self):
        super().setUp();self.good=gzip.compress(b''.join(b'{"i":%d}\n'%i for i in range(2000)),mtime=0)
    def cases(self):
        g=self.good
        return {'truncated':g[:-9],'crc_flip':g[:-8]+bytes([g[-8]^1])+g[-7:],'size_flip':g[:-4]+bytes([g[-4]^1])+g[-3:],
                'trailing_garbage':g+b'garbage!','not_gzip':b'plain text\n','empty':b'','body_flip':g[:40]+bytes([g[40]^0xff])+g[41:],
                'two_members':g+gzip.compress(b'{"i":-1}\n',mtime=0),'zero_padding':g+b'\0'*1024}
    def test_correct_pin_same_outcome_class_message_and_ledger(self):
        # Pin = SHA of the (possibly corrupt) bytes: both scopes must reach gzip identically.
        for name,b in self.cases().items():
            with self.subTest(name):
                p=self.put(name+'.gz',b);self.assertEqual(self.run_records('frozen',p,sha(b)),self.run_records('a20',p,sha(b)))
    def test_wrong_pin_never_passes_and_never_notes(self):
        # Ordering differs by design: A20 rejects on SHA before gzip; frozen may raise a gzip error first.
        for name,b in self.cases().items():
            with self.subTest(name):
                p=self.put(name+'.gz',b)
                for adapter in ('frozen','a20'):
                    out,ledger=self.run_records(adapter,p,sha(self.good) if b!=self.good else '0'*64)
                    self.assertEqual(out[0],'err');self.assertEqual(ledger,{})
                out,_=self.run_records('a20',p,'0'*64);self.assertEqual((out[1],out[2]),('ValueError','Compressed record SHA differs'))
    def test_consumer_exception_and_early_exit_identical(self):
        p=self.put('g.gz',self.good);pin=sha(self.good)
        def boom(s):next(iter(s));raise KeyError('consumer')
        def partial(s):return [next(iter(s))]
        for consume in (boom,partial):
            with self.subTest(consume.__name__):
                self.assertEqual(self.run_records('frozen',p,pin,consume),self.run_records('a20',p,pin,consume))
    def test_ledger_conflict_detected_identically(self):
        p=self.put('g.gz',self.good);pin=sha(self.good)
        for adapter in (R.io_locks,A.io_locks):
            with self.io.capture_evidence():
                self.io.note('127x04',str(p),'f'*64)
                with self.assertRaisesRegex(ValueError,'evidence changed'),adapter(self.io,lambda:None),self.io.records('127x04',str(p),pin) as s:s.read()

class Toctou(Base):
    def setUp(self):
        super().setUp();self.blob=gzip.compress(b'{"a":1}\n'*5000,mtime=0);self.pin=sha(self.blob);self.p=self.put('r.gz',self.blob)
    def test_growth_after_fstat_beyond_budget_fails_closed(self):
        real=os.fstat
        def small(fd):
            st=real(fd);self.p.write_bytes(self.blob+b'x'*64);return st   # writer appends between fstat and read
        with patch.object(A,'MAX_COMPRESSED_BYTES',len(self.blob)+8),patch.object(A.os,'fstat',side_effect=small):
            out,ledger=self.run_records('a20',self.p,self.pin)
        self.assertEqual(out[:2],('err','ValueError'));self.assertIn('exceeds',out[2]);self.assertEqual(ledger,{})
    def test_truncation_after_fstat_is_sha_mismatch(self):
        real=os.fstat
        def shrink(fd):
            st=real(fd);os.truncate(self.p,len(self.blob)//2);return st
        with patch.object(A.os,'fstat',side_effect=shrink):out,ledger=self.run_records('a20',self.p,self.pin)
        self.assertEqual(out[2],'Compressed record SHA differs');self.assertEqual(ledger,{})
    def test_atomic_replace_and_unlink_after_snapshot_cannot_reach_parser(self):
        other=gzip.compress(b'{"a":2}\n'*5000,mtime=0)
        def consume(s):
            tmp=self.root/'tmp.gz';tmp.write_bytes(other);os.replace(tmp,self.p)   # writer swaps inode mid-parse
            rows=[bytes(x) for x in s];self.p.unlink();return rows
        out,ledger=self.run_records('a20',self.p,self.pin,consume)
        self.assertEqual(out[1],[bytes(x) for x in gzip.decompress(self.blob).splitlines(keepends=True)]);self.assertEqual(ledger,{('127x04',str(self.p)):self.pin})
    def test_snapshot_is_exactly_the_hashed_object(self):
        seen={}
        real_sha=A.hashlib.sha256;real_bio=A.memory.BytesIO
        def h(b=b''):seen['hashed']=b;return real_sha(b)
        def bio(b):seen['parsed']=b;return real_bio(b)
        with patch.object(A.hashlib,'sha256',side_effect=h),patch.object(A.memory,'BytesIO',side_effect=bio):
            out,_=self.run_records('a20',self.p,self.pin)
        self.assertEqual(out[0],'ok');self.assertIs(seen['hashed'],seen['parsed']);self.assertIsInstance(seen['parsed'],bytes)

class LockSemantics(Base):
    def setUp(self):
        super().setUp();self.blob=gzip.compress(b'{"a":1}\n'*5000,mtime=0);self.pin=sha(self.blob);self.p=self.put('r.gz',self.blob)
    def test_local_read_waits_for_frozen_scope_holder(self):
        h=self.holder(seconds=1.0);t=time.monotonic()
        out,_=self.run_records('a20',self.p,self.pin);h.wait()
        self.assertEqual(out[0],'ok');self.assertGreaterEqual(time.monotonic()-t,0.7)
    def test_parse_proceeds_while_another_process_holds_the_lock(self):
        holder=[]
        def consume(s):
            holder.append(self.holder(seconds=0.3));rows=[bytes(x) for x in s];return rows
        t=time.monotonic();out,_=self.run_records('a20',self.p,self.pin,consume);holder[0].wait()
        self.assertEqual(out[0],'ok')
    def test_remote_and_non04_local_keep_whole_context(self):
        # 03 remote, and a local non-04 host: original records() runs with the lock held across the consumer.
        for host,local in (('127x03',False),('127x08',True)):
            seen=[]
            @contextlib.contextmanager
            def fake(h,n,e):
                seen.append(h);yield iter([b'x'])
            with self.subTest(host),patch.object(self.io,'local',return_value=local),patch.object(self.io,'records',fake),A.io_locks(self.io,lambda:None):
                with self.io.records(host,'/n',self.pin) as s:self.assertFalse(self.free(host));list(s)
                self.assertTrue(self.free(host));self.assertEqual(seen,[host])
    def test_04_never_held_across_a_yield(self):
        # Nested same-host and cross-host contexts: the 04 lock is free inside every 04 context.
        q=self.put('q.gz',self.blob)
        with A.io_locks(self.io,lambda:None):
            with self.io.records('127x04',str(self.p),self.pin) as a,self.io.records('127x04',str(q),self.pin) as b:
                self.assertTrue(self.free('127x04'));a.read();b.read()
    def free(self,host):
        with (self.root/(host+'.io.lock')).open('a') as f:
            try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(f,fcntl.LOCK_UN);return True
            except BlockingIOError:return False
    def test_same_lock_path_as_serial_runner(self):
        src=(Path(R.__file__)).read_text();self.assertIn("LOCK_ROOT=Path('/mpac/sdicks02/jobs/clasher/v4-queue-independent-verifier-20261009-r1/proofs')",src)
        self.assertIn('from a19_resources import LOCK_ROOT',Path(A.__file__).read_text())

class Budget(Base):
    def test_budget_restored_after_every_exit_path(self):
        blob=gzip.compress(b'{"a":1}\n'*100,mtime=0);p=self.put('r.gz',blob);pin=sha(blob)
        with patch.object(A,'MAX_COMPRESSED_BYTES',len(blob)),A.io_locks(self.io,lambda:None):
            for exc in (KeyError,GeneratorExit,KeyboardInterrupt):
                with self.assertRaises(exc),self.io.records('127x04',str(p),pin):raise exc()
            with self.io.records('127x04',str(p),pin) as s:s.read()   # full budget available again
    def test_exact_limit_accepted_one_over_rejected(self):
        blob=gzip.compress(b'{"a":1}\n'*100,mtime=0);p=self.put('r.gz',blob);pin=sha(blob)
        with patch.object(A,'MAX_COMPRESSED_BYTES',len(blob)):self.assertEqual(self.run_records('a20',p,pin)[0][0],'ok')
        with patch.object(A,'MAX_COMPRESSED_BYTES',len(blob)-1):self.assertIn('exceeds',self.run_records('a20',p,pin)[0][2])
    def test_production_limit_constant(self):self.assertEqual(A.MAX_COMPRESSED_BYTES,512*1024*1024)

class ComposedAuthority(unittest.TestCase):
    """End-to-end composed a19_authority.authenticate() with A19+A20 records (author tested
    authenticate_a20 only in isolation; the r5 AuthorityTests fail on the composed source set)."""
    def setUp(self):
        import a19_authority as a;from a19_common import sha as csha,write,load,STAGES,ORIGINAL_PLAN_SHA,ORIGINAL_APPROVAL_SHA
        self.a=a;self.write=write;self.load=load
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=root=Path(t.name)
        original_path=L/'receipts/a1-body-seal-20261009-r1/execution-plan-a1-deployment-r2.json';old=L/'amendments/coordinator-approval-A1-r2.json'
        original=load(original_path);code_root=a.CODE_ROOT
        sources={p.name:csha(p) for p in code_root.glob('*.py') if p.name.startswith('a19_') or p.name=='a20_io.py'}
        aux={p.name:csha(p) for p in code_root.glob('*.py') if p.name not in sources}
        self.base_plan='7d2a92bc06315c7a1fcabc2636c9818cec1784446ee35fd6b9b5399c28f4fc12'
        scope=dict(revision='A20-r1',hosts=['127x04'],serial_runner_changed=False,lock_scope='local-read-and-compressed-sha-only',max_compressed_bytes=A.MAX_COMPRESSED_BYTES,adapter_sha256=csha(Path(A.__file__)),base_a19_plan_sha256=self.base_plan)
        cand=copy.deepcopy(original);cand['operational_body_verification']=dict(revision='A19-r5',resource_policy=a.RESOURCE_POLICY,original_execution_plan_sha256=ORIGINAL_PLAN_SHA,stages=list(STAGES),hosts=['127x04'],max_workers=12,worker_cpus=list(range(12)),control_cpu=47,early_epoch_verification=False,cached_verification_allowed=False,source_files_sha256=sources,auxiliary_files_sha256=aux,ssh_wrapper_sha256='s'*64,local_io_lock_scope=scope)
        req=self.req={'stage':'a1-verify','original_plan':{'path':str(original_path),'sha256':ORIGINAL_PLAN_SHA},'original_approval':{'path':str(old),'sha256':ORIGINAL_APPROVAL_SHA},'stage_approval':None}
        req['verification_plan']=write(root/'plan.json',cand)
        ap=load(old);ap['execution_plan_sha256']=req['verification_plan']['sha256'];req['a1_approval']=write(root/'a1.json',ap)
        (root/'a19.md').write_text('a19 fixture');(root/'a20.md').write_text('a20 fixture')
        req['amendment']=dict(path=str(root/'a19.md'),sha256=csha(root/'a19.md'));req['a20_amendment']=dict(path=str(root/'a20.md'),sha256=csha(root/'a20.md'))
        req['a19_freeze']=write(root/'a19-freeze.json',dict(decision='FROZEN',execution_plan_sha256=req['verification_plan']['sha256'],source_files_sha256=sources,amendment_sha256=req['amendment']['sha256']))
        bind=dict(execution_plan_sha256=req['verification_plan']['sha256'],base_a19_plan_sha256=self.base_plan,adapter_sha256=scope['adapter_sha256'],amendment_sha256=req['a20_amendment']['sha256'])
        req['a20_freeze']=write(root/'a20-freeze.json',dict(bind,decision='FROZEN'))
        req['a20_approval']=write(root/'a20-approval.json',dict(bind,decision='APPROVE_LOCAL_IO_LOCK_SCOPE',a20_freeze_sha256=req['a20_freeze']['sha256'],hosts=['127x04'],authorized_stages=list(STAGES),serial_runner_changed=False,B_authorized=False,heldout_opening_authorized=False))
        op=dict(decision='APPROVE_PARALLEL_BODY_VERIFICATION',a19_freeze_sha256=req['a19_freeze']['sha256'],a20_freeze_sha256=req['a20_freeze']['sha256'],execution_plan_sha256=req['verification_plan']['sha256'],original_execution_plan_sha256=ORIGINAL_PLAN_SHA,original_approval_sha256=ORIGINAL_APPROVAL_SHA,source_files_sha256=sources,amendment_sha256=req['amendment']['sha256'],handoff_policy='verify-then-retire',exclusive_physical_cpus=list(range(12))+[47],excluded_siblings=list(range(64,76))+[111],no_new_clasher_launches=True,x5_actual_exit_required=True,authorized_stages=list(STAGES),hosts=['127x04'],seal_root=str(a.SEAL_ROOT),seal_binding='authenticated-r4-exit-then-pin-actual-bytes',B_authorized=False,heldout_opening_authorized=False,valid_until_utc='2026-10-11T04:00:00Z',output_parent='/mpac/sdicks02/jobs/clasher/v4-a19-parallel-verification-r5-a20-r1')
        req['operational_approval']=write(root/'op.json',op)
        code=root/'code';code.mkdir();(code/'dominance_orchestration_assembly_a18_v4.py').write_bytes((L/'prepared/amendment18-review-r2/dominance_orchestration_assembly_a18_v4.py').read_bytes())
        base=root/'base';(base/'execution').mkdir(parents=True);cwd=Path.cwd();os.chdir(base/'execution');self.addCleanup(os.chdir,cwd)
        self.calls=[];f=types.SimpleNamespace(__file__=str(code/'dominance_orchestration_assembly_a18_v4.py'),authenticate_plan=lambda *x:self.calls.append(x))
        for p in [patch.object(a,'BASE',base),patch.object(a,'CODE',code),patch.object(a,'PYTHON',sys.executable),patch.object(a.sys,'version_info',(3,12,12)),patch.object(a.importlib,'import_module',return_value=f),patch.dict(sys.modules,{'scipy':types.SimpleNamespace(__version__='1.17.1')}),patch.dict(os.environ,{'PYTHONPATH':original['pythonpath']}),patch.object(a,'sha',side_effect=lambda p:'s'*64 if str(p).endswith('/v4-a1-parallel-r5/bin/ssh') else csha(p)),patch.object(a.time,'time',return_value=1791601200.)]:
            p.start();self.addCleanup(p.stop)
    def rewrite(self,key,update):
        spec=self.req[key];v=self.load(spec['path']);update(v);Path(spec['path']).write_text(json.dumps(v));spec['sha256']=hashlib.sha256(Path(spec['path']).read_bytes()).hexdigest()
    def test_valid_composed_request_authenticates_both_plans(self):
        self.a.authenticate(self.req);self.assertEqual(len(self.calls),2)
    def test_oct13_valid_until_rejected_by_current_cap(self):
        self.rewrite('operational_approval',lambda v:v.update(valid_until_utc='2026-10-13T04:00:00Z'))
        with self.assertRaisesRegex(ValueError,'Approval/cache hardstop'):self.a.authenticate(self.req)
    def test_op_approval_bound_to_other_a20_freeze_rejected(self):
        self.rewrite('operational_approval',lambda v:v.update(a20_freeze_sha256='0'*64))
        with self.assertRaisesRegex(ValueError,'A20 freeze binding'):self.a.authenticate(self.req)
    def test_a20_records_bound_to_base_r5_plan_rejected(self):
        for key in ('a20_freeze','a20_approval'):
            with self.subTest(key):
                self.setUp();self.rewrite(key,lambda v:v.update(execution_plan_sha256=self.base_plan))
                with self.assertRaises(ValueError):self.a.authenticate(self.req)
    def test_base_r5_style_request_without_a20_records_rejected(self):
        for key in ('a20_freeze','a20_approval','a20_amendment'):
            with self.subTest(key):
                self.setUp();self.req.pop(key)
                with self.assertRaises(KeyError):self.a.authenticate(self.req)
    def test_a19_freeze_without_a20_source_pin_rejected(self):
        self.rewrite('a19_freeze',lambda v:v['source_files_sha256'].pop('a20_io.py'))
        with self.assertRaisesRegex(ValueError,'A19 frozen code pins'):self.a.authenticate(self.req)
    def test_base_output_parent_rejected(self):
        self.rewrite('operational_approval',lambda v:v.update(output_parent='/mpac/sdicks02/jobs/clasher/v4-a19-parallel-verification-r5'))
        with self.assertRaisesRegex(ValueError,'Approved output parent'):self.a.authenticate(self.req)
    def test_cap_constant_in_composed_source(self):
        src=Path(self.a.__file__).read_text()
        self.assertIn('datetime.datetime(2026,10,11,4,tzinfo=datetime.timezone.utc)',src);self.assertNotIn('2026,10,13',src)

if __name__=='__main__':unittest.main()
