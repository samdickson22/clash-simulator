"""Independent A19 r2 reviewer tests (2026-10-10). Synthetic data and inert local
processes only: no production path, payload, fleet job, STOP or launcher call.

Run from the repo root with the production interpreter version (3.12):
  nice -n 19 <python3.12> -B -m unittest discover -s \
    reports/strategy_council_20260928/live-loop/v4/l1/reviews/a19-reviewer-artifacts -p 'test_rev_a19.py' -v
"""
import ast,contextlib,copy,fcntl,hashlib,importlib.util,itertools,json,os,random,signal,subprocess,sys,tempfile,time,types,unittest
from pathlib import Path
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
L1=HERE.parent.parent
PKG=L1/'prepared/amendment19-review-r2'
SNAP=L1/'prepared/amendment18-review-r2'
FROZEN=SNAP/'dominance_orchestration_assembly_a18_v4.py'
FROZEN_SHA='002d68943ca3f57799480c7afa240ce66283bcf6e049fe13ccf4259b7972610a'
R4=L1/'receipts/a1-body-seal-20261009-r4'
SUPERVISOR_SHA='884f0304c64c9369eccf7feb4df84616035a08ef5da5351d9c0567581ec46cd8'
PLAN_SHA='68e2472255ba5d1b79ec9f45217aa14208a31b6c44ccec890af332909efe8bc8'
sys.path.insert(0,str(PKG))
import a19_common as C, a19_kernel as K, a19_a2, a19_handoff, a19_resources, a19_pool, a19_authority

def sha_bytes(b):return hashlib.sha256(b).hexdigest()

# ---------------------------------------------------------------- 1. kernel vs frozen
def synthetic(salt):
    """Deterministic synthetic scorer/ranker with awkward JSON values."""
    def score(a):
        s,e,b=a;r=random.Random('%s-%d-%d'%(s,e,b))
        m=r.randint(0,500);t=r.randint(1,600);p=r.randint(0,700)
        return dict(epoch=e,body_threshold=b/10,readiness={'salt':s,'pop':64,'pins':{str(i):'%064x'%i for i in range(3)}},
                    micro=dict(matched=m,truth=t,predictions=p),
                    floats=[r.random(),0.1+0.2,1e-308,-0.0,r.uniform(-1e6,1e6),2**53+1],
                    nested={'deep':[{'k':r.random()} for _ in range(3)],'u':'é✓'},flag=r.random()<.5)
    def rank(cells):
        best=max(cells,key=lambda c:(2*c['micro']['matched']/(c['micro']['truth']+c['micro']['predictions']),c['body_threshold']))
        return dict(epoch=cells[0]['epoch'],readiness=cells[0]['readiness'],body_threshold=best['body_threshold'],
                    micro=best['micro'],ratio=best['micro']['matched']/best['micro']['truth'],selection_seal=False)
    return score,rank

def frozen_subset(score,rank):
    data=FROZEN.read_bytes();assert sha_bytes(data)==FROZEN_SHA
    tree=ast.parse(data);names={'canonical','digest','json_identity','recompute_body','verify_body'}
    mod=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[])
    ns=dict(json=json,hashlib=hashlib,FREEZE_SHA='f'*64,score_body_records=score,rank_body_cells=rank,
            args_for=lambda p,e,b:(p['salt'],e,b),verify_sources=lambda p:None,state_root=lambda r:Path(r),
            load=lambda p:json.loads(Path(p).read_text()))  # frozen dominance_file_verifier load
    exec(compile(mod,str(FROZEN),'exec'),ns)
    return types.SimpleNamespace(**ns)

def leaves(v,path=()):
    if isinstance(v,dict):
        for k in v:yield from leaves(v[k],path+(k,))
    elif isinstance(v,list):
        for i,x in enumerate(v):yield from leaves(x,path+(i,))
    yield path

def mutate(value,r):
    v=copy.deepcopy(value);paths=[p for p in leaves(v) if p]
    p=r.choice(paths);parent=v
    for k in p[:-1]:parent=parent[k]
    k=p[-1];x=parent[k];kind=r.choice(['num','type','delete','add','str','bool','negzero','list'])
    if kind=='num' and type(x) in (int,float) and type(x) is not bool:parent[k]=x+(1 if type(x) is int else 1e-12*max(1,abs(x)))
    elif kind=='type' and type(x) is int and type(x) is not bool:parent[k]=float(x)
    elif kind=='type' and type(x) is float and x.is_integer():parent[k]=int(x)
    elif kind=='delete' and isinstance(parent,dict):del parent[k]
    elif kind=='add' and isinstance(parent,dict):parent['zz-added']=0
    elif kind=='str' and isinstance(x,str):parent[k]=x+'x'
    elif kind=='bool' and type(x) is bool:parent[k]=int(x)
    elif kind=='negzero' and x==0 and type(x) is float:parent[k]=0.0 if str(x)=='-0.0' else -0.0
    elif kind=='list' and isinstance(x,list):x.append(None)
    else:parent[k]=['changed']
    return v

class KernelDifferential(unittest.TestCase):
    """Run the frozen serial verify_body and the A19 worker->file->reducer chain on identical inputs."""
    def pipeline(self,salt,root):
        score,rank=synthetic(salt);f=frozen_subset(score,rank);plan={'salt':salt}
        serial=f.json_identity(dict(f.recompute_body(plan),execution_plan_sha256=PLAN_SHA))
        state=root/'state';state.mkdir()
        # Seal bytes exactly as frozen durable_json writes them.
        with (state/'body-seal.json').open('x') as fh:json.dump(serial,fh,sort_keys=True,indent=2,allow_nan=False);fh.write('\n')
        order=list(range(1,25));random.Random(salt).shuffle(order);rows=[]
        for e in order:  # completion order is arbitrary; each epoch round-trips a worker file
            spec=C.write(root/('epoch-%02d.json'%e),K.recompute_epoch(f,plan,e));rows.append(C.pinned(spec))
        seal_spec={'path':str(state/'body-seal.json'),'sha256':C.sha(state/'body-seal.json')}
        return f,plan,state,rows,seal_spec
    def test_accepts_exactly_what_serial_accepts_over_many_inputs(self):
        for salt in range(12):
            with tempfile.TemporaryDirectory() as t:
                f,plan,state,rows,seal=self.pipeline(salt,Path(t))
                frozen=f.verify_body(plan,state,PLAN_SHA)
                ours=K.reduce_and_compare(f,plan,rows,C.pinned(seal),PLAN_SHA)
                self.assertEqual(f.canonical(frozen),f.canonical(ours))
    def test_seal_mutations_never_accepted_by_kernel_when_frozen_rejects(self):
        r=random.Random(1919);stricter=0;n=0
        with tempfile.TemporaryDirectory() as t:
            f,plan,state,rows,seal=self.pipeline('mut',Path(t));original=C.pinned(seal)
            for i in range(300):
                bad=mutate(original,r);n+=1
                (state/'body-seal.json').unlink()
                with (state/'body-seal.json').open('x') as fh:json.dump(bad,fh,sort_keys=True,indent=2,allow_nan=False);fh.write('\n')
                try:f.verify_body(plan,state,PLAN_SHA);frozen_ok=True
                except ValueError:frozen_ok=False
                try:K.reduce_and_compare(f,plan,rows,C.load(state/'body-seal.json'),PLAN_SHA);ours_ok=True
                except (ValueError,KeyError,TypeError):ours_ok=False
                self.assertFalse(ours_ok and not frozen_ok,'kernel accepted a seal frozen rejects: %r'%i)
                stricter+=frozen_ok and not ours_ok
        print('\n[seal-mutation] %d mutations, kernel-only (stricter) rejections: %d'%(n,stricter),file=sys.stderr)
    def test_worker_row_mutations_never_accepted(self):
        r=random.Random(77)
        with tempfile.TemporaryDirectory() as t:
            f,plan,state,rows,seal=self.pipeline('rows',Path(t));original=C.pinned(seal);tolerated=[0]
            for i in range(300):
                j=r.randrange(24);bad=copy.deepcopy(rows);bad[j]=mutate(rows[j],r)
                try:K.reduce_and_compare(f,plan,bad,original,PLAN_SHA);ok=True
                except (ValueError,KeyError,TypeError,AttributeError):ok=False
                if ok:
                    # Only the redundant top-level copy of readiness may differ, and only by Python ==
                    # (e.g. 64 vs 64.0): frozen recompute_body applies the same == check across epochs.
                    self.assertEqual(f.canonical(bad[j]['row']),f.canonical(rows[j]['row']))
                    self.assertEqual(bad[j]['readiness'],rows[j]['readiness']);tolerated[0]+=1
        print('\n[row-mutation] accepted mutations confined to redundant readiness copy: %d'%tolerated[0],file=sys.stderr)
    def test_swapped_epoch_results_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            f,plan,state,rows,seal=self.pipeline('swap',Path(t));bad=copy.deepcopy(rows)
            a=next(x for x in bad if x['epoch']==3);b=next(x for x in bad if x['epoch']==4)
            a['row'],b['row']=b['row'],a['row']
            with self.assertRaises(ValueError):K.reduce_and_compare(f,plan,bad,C.pinned(seal),PLAN_SHA)
    def test_new_verification_plan_sha_cannot_enter_seal_comparison(self):
        with tempfile.TemporaryDirectory() as t:
            f,plan,state,rows,seal=self.pipeline('plan',Path(t))
            with self.assertRaises(ValueError):K.reduce_and_compare(f,plan,rows,C.pinned(seal),'544f419fb31e0295ee689cb6bcaac8fc19c6a9d8f7b3bfecda5944d551738c1e')

# ---------------------------------------------------------------- 2. A2 private binding on the REAL frozen module
_count=itertools.count()
def real_frozen(extra=None):
    """Exec the exact SHA-pinned frozen file; only its imported dependencies are stubbed."""
    assert C.sha(FROZEN)==FROZEN_SHA
    def mod(name,**attrs):
        m=types.ModuleType(name);m.__dict__.update(attrs);return m
    @contextlib.contextmanager
    def owner_lock(root):
        root=Path(root);root.mkdir(parents=True,exist_ok=True)
        with (root/'controller.lock').open('a') as fh:
            fcntl.flock(fh,fcntl.LOCK_EX|fcntl.LOCK_NB)
            try:yield root
            finally:fcntl.flock(fh,fcntl.LOCK_UN)
    def durable_json(path,value):
        with Path(path).open('x') as fh:json.dump(value,fh,sort_keys=True,indent=2,allow_nan=False);fh.write('\n')
        return Path(path)
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    stubs=dict(
        dominance_state_v4=mod('dominance_state_v4',durable_json=durable_json,owner_lock=owner_lock,authenticated_next=None,refuse_suspended=lambda r:None),
        dominance_file_verifier_v4_r2=mod('dominance_file_verifier_v4_r2',sha=sha,load=lambda p:json.loads(Path(p).read_text()),checked=None,read_rows=None,
                                          verify_all_bound_seals=lambda paths,**k:[json.loads(Path(p).read_text()) for p in paths]),
        measured_dominance_v4=mod('measured_dominance_v4',bound_cell=None,GRID=[.5]),
        clock_free_body_score_assembly_a18_v4=mod('clock_free_body_score_assembly_a18_v4',score_body_records=None),
        clock_free_body_ranking_v4=mod('clock_free_body_ranking_v4',rank_body_cells=None),
        portable_fit_admission_v4=mod('portable_fit_admission_v4',validate_portable=None),
        epoch_assembly_admission_a18_v4=mod('epoch_assembly_admission_a18_v4',authenticate_record_capture=None,record_rows=None),
        clock_free_records_v4=mod('clock_free_records_v4',event_predictions=None),
        validation_replay_v4=mod('validation_replay_v4',frame_times=None),
        validation_score_v4=mod('validation_score_v4',mapped_truth=None,card_kinds=None))
    with patch.dict(sys.modules,stubs):
        spec=importlib.util.spec_from_file_location('rev_frozen_%d'%next(_count),FROZEN)
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    for k,v in (extra or {}).items():setattr(m,k,v)  # test-instance-only dependency stubs
    return m

class A2Binding(unittest.TestCase):
    def test_identical_code_and_untouched_module_globals(self):
        m=real_frozen();before={k:id(v) for k,v in vars(m).items()};cb=lambda *a:None
        adapters=a19_a2.bind(m,cb)
        self.assertEqual(before,{k:id(v) for k,v in vars(m).items()})
        for name in ('build_bounds','verified_bounds'):
            f,o=adapters[name],getattr(m,name)
            self.assertIs(f.__code__,o.__code__);self.assertIs(f.__defaults__,o.__defaults__);self.assertIs(f.__closure__,o.__closure__)
            g=f.__globals__;self.assertIsNot(g,vars(m));self.assertEqual(set(g),set(vars(m)))
            self.assertEqual([k for k in g if g[k] is not vars(m)[k]],['verify_body']);self.assertIs(g['verify_body'],cb)
            for n in f.__code__.co_names:
                if n in vars(m):self.assertTrue(n=='verify_body' or g[n] is vars(m)[n])
        # Bounds computation itself never resolves verify_body and keeps the module globals.
        self.assertNotIn('verify_body',m.recompute_bounds.__code__.co_names)
        self.assertIs(m.recompute_bounds.__globals__,vars(m))
    def test_every_outer_call_verifies_first_and_failure_blocks_bounds(self):
        order=[]
        def recompute(p,seal,seal_sha):
            order.append('bounds');return [dict(epoch=1,threshold=.5,v=seal['x'])],json.dumps([{'t':1}]).encode()
        m=real_frozen(dict(recompute_bounds=recompute))
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'state';root.mkdir();(root/'body-seal.json').write_text('{"x": 1}\n')
            def fresh(p,r,s):
                order.append('verify');self.assertEqual(s,PLAN_SHA);return json.loads((Path(r)/'body-seal.json').read_text())
            ad=a19_a2.bind(m,fresh)
            ad['build_bounds']({},root,PLAN_SHA)
            self.assertEqual(order,['verify','bounds'])
            self.assertEqual(json.loads((root/'bounds/complete.json').read_text())['execution_plan_sha256'],PLAN_SHA)
            ad['verified_bounds']({},root,PLAN_SHA);self.assertEqual(order,['verify','bounds','verify','bounds'])
            with self.assertRaisesRegex(ValueError,'already exist'):ad['build_bounds']({},root,PLAN_SHA)
            self.assertEqual(order[-1],'verify')  # repeated call still re-verifies before refusing
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'state';root.mkdir();(root/'body-seal.json').write_text('{"x": 1}\n')
            def failing(*a):raise ValueError('fresh verification failed')
            with self.assertRaisesRegex(ValueError,'fresh verification failed'):a19_a2.bind(m,failing)['build_bounds']({},root,PLAN_SHA)
            self.assertFalse((root/'bounds').exists())

# ---------------------------------------------------------------- 3. handoff against the PRODUCTION r4 supervisor bytes
RUN_STAGE=r'''
import json,os,signal,sys,time,hashlib
from pathlib import Path
root=Path(__file__).parent;mode=(root/'mode').read_text().strip()
if sys.argv[1]=='seal':
    (root/'state'/'body-seal.json').write_text(json.dumps({'synthetic':True})+'\n');sys.exit(0)
if mode=='ignore_term':signal.signal(signal.SIGTERM,signal.SIG_IGN)
if mode=='fail':sys.exit(1)
if mode=='complete':
    time.sleep(2)
    s=hashlib.sha256((root/'state'/'body-seal.json').read_bytes()).hexdigest()
    (root/'seal-verification.json').write_text(json.dumps(dict(verified=True,body_seal_sha256=s)));sys.exit(0)
time.sleep(150)
'''
class ProductionSupervisorHandoff(unittest.TestCase):
    """Only ROOT/BASE/interpreter string constants of the pinned r4 supervise.py are substituted."""
    def start(self,mode):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);root=Path(t.name)/'r4';root.mkdir()
        (root/'state').mkdir();(Path(t.name)/'base/execution').mkdir(parents=True)
        src=(R4/'supervise.py').read_text();self.assertEqual(sha_bytes(src.encode()),SUPERVISOR_SHA)
        for old,new in [("Path('/mpac/sdicks02/jobs/clasher/v4-a1-body-seal-20261009-r4')",'Path(%r)'%str(root)),
                        ("Path('/mpac/sdicks02/jobs/clasher/v4-a1-dryrun-preparation-r2')",'Path(%r)'%str(Path(t.name)/'base')),
                        ("'/mpac/sdicks02/envs/clasher-gpu/bin/python'",repr(sys.executable))]:
            self.assertEqual(src.count(old),1);src=src.replace(old,new)
        (root/'supervise.py').write_text(src);(root/'run_stage.py').write_text(RUN_STAGE);(root/'mode').write_text(mode)
        (root/'truth-copy-preflight.json').write_text(json.dumps(dict(preflight_pass=True,validation_episodes=['e%d'%i for i in range(64)])))
        log=(Path(t.name)/'sup.log').open('wb');self.addCleanup(log.close)
        p=subprocess.Popen([sys.executable,'-B',str(root/'supervise.py')],cwd=t.name,stdout=log,stderr=log,start_new_session=True)
        self.addCleanup(self.reap,p,root)
        deadline=time.monotonic()+30
        while not (root/'verify-identity.json').exists():
            self.assertLess(time.monotonic(),deadline);self.assertIsNone(p.poll());time.sleep(.02)
        out=Path(t.name)/'new';out.mkdir()
        seal={'path':str(root/'state/body-seal.json'),'sha256':C.sha(root/'state/body-seal.json')}
        return p,root,out,seal
    def reap(self,p,root):
        for f in ('verify-identity.json',):
            if (root/f).exists():
                v=C.load(root/f)
                with contextlib.suppress(ProcessLookupError,PermissionError):os.killpg(v['pid'],signal.SIGKILL)
        with contextlib.suppress(ProcessLookupError):os.killpg(p.pid,signal.SIGKILL)
        p.wait()
    def handoff(self,root,out,seal,timeout):
        with patch.object(a19_handoff,'PYTHON',sys.executable):
            return a19_handoff.serial_handoff(root,out,seal,True,lambda:None,timeout=timeout)
    def test_stop_retires_only_verify_with_exact_records(self):
        p,root,out,seal=self.start('long');status,rec=self.handoff(root,out,seal,30)
        self.assertEqual(status,'SERIAL_VERIFY_SUPERSEDED');self.assertEqual(p.wait(timeout=10),1)
        self.assertEqual(C.load(root/'verify-exit.json')['exit_code'],-15)
        self.assertEqual(C.load(root/'seal-exit.json')['exit_code'],0)
        self.assertTrue((root/'STOP').exists());self.assertFalse((root/'complete.json').exists())
        self.assertEqual(C.sha(seal['path']),seal['sha256'])
    def test_exit0_racing_stop_uses_genuine_serial_result(self):
        p,root,out,seal=self.start('complete');status,rec=self.handoff(root,out,seal,30)
        self.assertEqual(status,'SERIAL_ALREADY_COMPLETE');p.wait(timeout=10)
        self.assertFalse((root/'failure.json').exists());self.assertEqual(C.load(root/'verify-exit.json')['exit_code'],0)
    def test_scientific_failure_is_never_relabelled(self):
        p,root,out,seal=self.start('fail')
        with self.assertRaises(ValueError):self.handoff(root,out,seal,30)
        p.wait(timeout=10);self.assertEqual(C.load(root/'failure.json')['exit_code'],1)
        self.assertIsNone(C.load(root/'failure.json')['reason']);self.assertFalse((out/'handoff.json').exists())
    def test_sigterm_ignoring_child_fails_closed_but_original_records_are_lost(self):
        """Documents a residual: supervisor p.wait(timeout=60) raises, so r4 writes no verify-exit/failure."""
        p,root,out,seal=self.start('ignore_term')
        with self.assertRaisesRegex(ValueError,'handoff timeout'):self.handoff(root,out,seal,8)
        self.assertFalse((out/'handoff.json').exists())
        rc=p.wait(timeout=90)
        self.assertNotEqual(rc,0);self.assertFalse((root/'verify-exit.json').exists());self.assertFalse((root/'failure.json').exists())
        v=C.load(root/'verify-identity.json');self.assertTrue(C.live({k:v[k] for k in ('pid','starttime','boot_id')}))  # orphan survives

# ---------------------------------------------------------------- 4. resource guard deployment gaps
class ResourceGuard(unittest.TestCase):
    def test_inventory_permission_error_on_cwd_propagates(self):
        """127x04 case: same-UID sshd/(sd-pam)/gnome-keyring deny /proc/<pid>/cwd."""
        real=os.readlink;victim='/proc/%d/cwd'%os.getpid()
        def readlink(path,*a,**k):
            if str(path)==victim:raise PermissionError(13,'Permission denied',victim)
            return real(path,*a,**k)
        with patch.object(a19_resources.os,'readlink',readlink):
            with self.assertRaises(PermissionError):a19_resources.inventory()
    def test_inventory_permission_error_on_smaps_propagates(self):
        real=Path.read_text;victim=Path('/proc/%d/smaps_rollup'%os.getpid())
        def read_text(self,*a,**k):
            if self==victim:raise PermissionError(13,'Permission denied',str(victim))
            return real(self,*a,**k)
        if 'clasher' not in os.getcwd():self.skipTest('run from the repo root so this process is Clasher-marked by cwd')
        with patch.object(Path,'read_text',read_text):
            with self.assertRaises(PermissionError):a19_resources.inventory()
    def test_capacity_starvation_waits_without_launch_and_handoff_precedes_any_capacity_check(self):
        calls=[0]
        def guard():
            calls[0]+=1
            if calls[0]>50:raise ValueError('Approval/cache deadline')
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(ValueError,'deadline'):
                a19_pool.run_pool(Path(t)/'w',list(range(1,25)),lambda *a:self.fail('launched'),guard,lambda:0,None,poll_seconds=0)
            self.assertEqual(C.load(Path(t)/'w/failure.json')['completed_epochs'],[])
        src=(PKG/'a19_launcher.py').read_text()
        body=src[src.index('def execute('):]
        self.assertLess(body.index('serial_handoff(SEAL_ROOT'),body.index('verify(plan,SEAL_ROOT'))
        self.assertNotIn('capacity',body[:body.index('serial_handoff(SEAL_ROOT')])  # no admission before irreversible STOP

# ---------------------------------------------------------------- 5. A2 prerequisite accepts an incomplete parallel attempt
class A2Prerequisite(unittest.TestCase):
    def test_parallel_receipt_without_attempt_completion_is_accepted(self):
        with tempfile.TemporaryDirectory() as t:
            t=Path(t);root=t/'r4';(root/'state/incidents').mkdir(parents=True)
            for n in ('run_stage.py','supervise.py'):(root/n).write_bytes((R4/n).read_bytes())
            ident=dict(pid=2499719,starttime='94874747',boot_id='bd010cb6-41a6-4832-af28-14e902d3cb7c')
            (root/'seal.log').write_text('log')
            C.write(root/'seal-identity.json',ident)
            C.write(root/'launch.json',dict(supervisor=dict(pid=2499718,starttime='94874743',boot_id=ident['boot_id']),approval_sha256=C.ORIGINAL_APPROVAL_SHA,
                    runner_sha256=C.sha(root/'run_stage.py'),supervisor_sha256=C.sha(root/'supervise.py')))
            C.write(root/'seal-exit.json',dict(identity=ident,exit_code=0,reason=None,log_sha256=C.sha(root/'seal.log')))
            C.write(root/'state/body-seal.json',dict(execution_plan_sha256=PLAN_SHA,epochs={str(e):{'cell_sha256':{str(b):'x' for b in range(1,10)}} for e in range(1,25)}))
            seal_sha=C.sha(root/'state/body-seal.json')
            attempt=t/'parent/a1-verify-x';(attempt/'verification-y').mkdir(parents=True)
            C.write(attempt/'failure.json',dict(error='launcher failed after reducer'))  # attempt FAILED, no complete.json
            receipt=C.write(attempt/'verification-y/verified.json',dict(schema='clasher.v4.a19-parallel-body-verification.v2',verified=True,
                    body_seal_sha256=seal_sha,stage='a1-verify',verification_execution_plan_sha256='v'*64))
            stage=C.write(t/'stage.json',dict(decision='APPROVE_A2',body_seal_sha256=seal_sha,a1_verification_receipt=receipt))
            request=dict(stage='a2-build-bounds',stage_approval=stage,verification_plan={'sha256':'v'*64})
            frozen=types.SimpleNamespace(refuse_suspended=lambda r:None)
            with patch.object(a19_authority,'SEAL_ROOT',root):
                spec=a19_authority.seal_barrier(frozen,request)
            self.assertEqual(spec['sha256'],seal_sha)  # accepted: gap (see review condition C4)

class ProposedInventoryR3(unittest.TestCase):
    """Reference fix: inaccessible same-UID processes are counted, never excluded or fatal."""
    def setUp(self):
        sys.path.insert(0,str(HERE));import proposed_inventory_r3;self.m=proposed_inventory_r3
    def test_real_host_does_not_raise_and_counts_inaccessible(self):
        rows=self.m.inventory();self.assertTrue(all(r['pss_bytes']>=0 for r in rows))
    def test_injected_cwd_and_smaps_denial_is_counted_conservatively(self):
        me=os.getpid();real_link=os.readlink;real_read=Path.read_text
        def readlink(path,*a,**k):
            if str(path)=='/proc/%d/cwd'%me:raise PermissionError(13,'denied')
            return real_link(path,*a,**k)
        def read_text(self,*a,**k):
            if str(self)=='/proc/%d/smaps_rollup'%me:raise PermissionError(13,'denied')
            return real_read(self,*a,**k)
        with patch.object(self.m.os,'readlink',readlink),patch.object(Path,'read_text',read_text):
            rows={r['pid']:r for r in self.m.inventory()}
        self.assertIn(me,rows);self.assertTrue(rows[me]['inaccessible']);self.assertGreater(rows[me]['pss_bytes'],0)

if __name__=='__main__':unittest.main()
