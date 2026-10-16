"""Fresh r5 review: pure contracts, inert AST snippets, scratch filesystem only.
Never invokes driver main/run_gate, worker/helper dispatch, OS signal/mask or engine.
"""
import ast
import copy
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import signal
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
TOOLS = REPO / 'reports/cards/c1/tools'
TREE = ast.parse((TOOLS/'final_gate.py').read_text())
spec = importlib.util.spec_from_file_location('r5_pure_contract', TOOLS/'final_gate_contract.py')
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
EVENTS = []


def extract(tree, names, ns):
    nodes = [copy.deepcopy(n) for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<r5 inert helpers>', 'exec'), ns)
    return ns


def scope():
    events = []
    fake_os = SimpleNamespace(**{k: getattr(os, k) for k in
        ('open','close','fdopen','fsync','getuid','O_RDONLY','O_DIRECTORY','O_NOFOLLOW','O_WRONLY','O_CREAT','O_EXCL')})
    fake_os.killpg = lambda pid, sig: events.append(('kill', pid, sig))
    ns = dict(C=C, os=fake_os, Path=Path, stat=stat, json=json, hashlib=hashlib, STOP_SIGNAL=0,
        signal=SimpleNamespace(SIGTERM=15, SIGINT=2, SIGHUP=1, SIGKILL=9),
        subprocess=SimpleNamespace(TimeoutExpired=subprocess.TimeoutExpired, DEVNULL=-3, STDOUT=-2),
        utc=lambda: '2026-10-16T00:00:00Z', events=events)
    return extract(TREE, {'Children','interrupted','check_cancelled','directory','new_file','write_json','check_original'}, ns)


def temp():
    return tempfile.TemporaryDirectory(dir=HERE)


class Fake:
    def __init__(self, pid, code=0, hook=None):
        self.pid, self.code, self.hook, self.calls = pid, code, hook, []
    def wait(self, timeout=None):
        self.calls.append(timeout)
        if self.hook: self.hook(self, timeout)
        return self.code


def cleanup_only(ns, ordinary=False):
    run = next(n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name=='run_gate')
    final = copy.deepcopy(next(n for n in run.body if isinstance(n,ast.Try)).finalbody)
    fn = ast.parse('def cleanup_only(children):\n    pass\n').body[0]
    block = ast.parse("try:\n    raise ValueError('ordinary failure')\nfinally:\n    pass\n").body[0]
    block.finalbody = final
    fn.body = [block] if ordinary else final
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])), '<r5 cleanup only>', 'exec'),ns)
    return ns['cleanup_only']


class Review(unittest.TestCase):
    def test_latch_is_record_only_one_way_and_no_parent_mask(self):
        ns=scope()
        for sig in (15,2,1,15): ns['interrupted'](sig,None)
        self.assertEqual(ns['STOP_SIGNAL'],15)
        with self.assertRaises(InterruptedError): ns['check_cancelled']()
        handler=next(n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name=='interrupted')
        self.assertFalse(any(isinstance(n,(ast.Call,ast.Raise)) for n in ast.walk(handler)))
        self.assertNotIn('pthread_sigmask',(TOOLS/'final_gate.py').read_text())
        children=next(n for n in TREE.body if isinstance(n,ast.ClassDef) and n.name=='Children')
        stop=next(n for n in children.body if isinstance(n,ast.FunctionDef) and n.name=='stop')
        self.assertNotIn('check_cancelled',ast.unparse(stop))

    def test_cleanup_every_line_entry_and_repeat_after_ordinary_failure(self):
        # Discover actual executed cleanup/helper line boundaries, then inject at EACH separately.
        seen=set()
        with temp() as d:
            ns=scope(); ch=ns['Children'](Path(d)); Path(d).chmod(0o700)
            ch.begin_phase('fixtures',['one']); ch.live={'one':(Fake(101,-15),['inert'],'start')}
            fn=cleanup_only(ns)
            def collect(frame,event,arg):
                if event=='line' and frame.f_code.co_filename in ('<r5 cleanup only>','<r5 inert helpers>'):
                    seen.add((frame.f_code.co_name,frame.f_lineno))
                return collect
            sys.settrace(collect)
            try: fn(ch)
            finally: sys.settrace(None)
        for ordinary in (False,True):
            for target in sorted(seen):
                with self.subTest(ordinary=ordinary,target=target),temp() as d:
                    ns=scope(); out=Path(d); out.chmod(0o700); ch=ns['Children'](out)
                    ch.begin_phase('fixtures',['one']); p=Fake(101,17); ch.live={'one':(p,['inert'],'start')}
                    fn=cleanup_only(ns,ordinary)
                    def inject(frame,event,arg):
                        if event=='line' and frame.f_code.co_filename in ('<r5 cleanup only>','<r5 inert helpers>'):
                            if (frame.f_code.co_name,frame.f_lineno)==target:
                                ns['interrupted'](15,None);ns['interrupted'](2,None);ns['interrupted'](1,None)
                        return inject
                    sys.settrace(inject)
                    try:
                        if ordinary:
                            with self.assertRaisesRegex(ValueError,'ordinary failure'): fn(ch)
                        else: fn(ch)
                    finally: sys.settrace(None)
                    self.assertFalse(ch.live); self.assertEqual(p.calls,[10])
                    rows=json.loads((out/'all-child-exits.json').read_text())
                    self.assertEqual(rows[0]['exit_code'],17)
                    self.assertEqual(rows,json.loads((out/'fixtures-final-exits.json').read_text()))
        EVENTS.append(dict(check='cleanup line injection',boundaries=len(seen),ordinary_and_normal_cases=2*len(seen)))

    def test_cancel_at_all_later_waits_preserves_prior_zero_failure_signal(self):
        cases=0
        for count in (2,8):
            for boundary in range(1,count):
                for prior in (0,17,-15):
                    with self.subTest(count=count,boundary=boundary,prior=prior),temp() as d:
                        out=Path(d);out.chmod(0o700);ns=scope();ch=ns['Children'](out)
                        labels=[f'c{i}' for i in range(count)]
                        def hook(p,timeout):
                            if p.pid==100+boundary and len(p.calls)==1:
                                ns['interrupted'](15,None);raise subprocess.TimeoutExpired(['inert'],timeout)
                            if timeout==10: ns['interrupted'](2,None)
                        ch.live={k:(Fake(100+i,prior if i==0 else -15,hook),['inert'],'start') for i,k in enumerate(labels)}
                        with self.assertRaises(InterruptedError):ch.wait('phase',labels)
                        partial=json.loads((out/'phase-exits.json').read_text())
                        self.assertEqual([r['label'] for r in partial],labels[:boundary])
                        ns['interrupted'](1,None);ch.stop()
                        final=json.loads((out/'all-child-exits.json').read_text())
                        self.assertEqual(final[:boundary],partial);self.assertEqual(len(final),count)
                        self.assertEqual(final[0]['exit_code'],prior);self.assertFalse(ch.live)
                        self.assertEqual(len(ns['events']),count-boundary);cases+=1
        EVENTS.append(dict(check='all later fixture/root wait boundaries',cases=cases))

    def test_reaped_status_is_stored_before_latch_check(self):
        with temp() as d:
            ns=scope();out=Path(d);out.chmod(0o700);ch=ns['Children'](out)
            def hook(p,timeout): ns['interrupted'](15,None)
            p=Fake(101,17,hook);ch.live={'one':(p,['inert'],'start')}
            with self.assertRaises(InterruptedError):ch.wait('phase',['one'])
            original=copy.deepcopy(ch.rows)
            self.assertEqual(original[0]['exit_code'],17);self.assertFalse(ch.live)
            ch.stop();self.assertEqual(ch.rows,original);self.assertEqual(p.calls,[1]);self.assertEqual(ns['events'],[])

    def test_spawn_before_during_after_and_exec_failure(self):
        for mode in ('before','during','ordinary-error','success'):
            with self.subTest(mode=mode),temp() as d:
                ns=scope();out=Path(d);out.chmod(0o700);ch=ns['Children'](out);ch.begin_phase('phase',['one'])
                calls=[]
                def spawn(*a,**k):
                    calls.append(k);self.assertTrue(k['start_new_session'])
                    if mode=='ordinary-error':raise OSError('exec failed')
                    if mode=='during':ns['interrupted'](15,None)
                    return Fake(101,17)
                ns['subprocess'].Popen=spawn
                if mode=='before':ns['interrupted'](15,None)
                if mode in ('before','during'):
                    with self.assertRaises(InterruptedError):ch.start('one',['inert'],{})
                elif mode=='ordinary-error':
                    with self.assertRaises(OSError):ch.start('one',['inert'],{})
                else:ch.start('one',['inert'],{})
                self.assertEqual(len(calls),int(mode!='before'))
                ns['interrupted'](2,None);ch.stop()
                rows=json.loads((out/'phase-final-exits.json').read_text())
                self.assertEqual(len(rows),int(mode in ('during','success')))

    def test_cleanup_escalates_and_repeats_during_kill_wait_receipts(self):
        with temp() as d:
            ns=scope();out=Path(d);out.chmod(0o700);ch=ns['Children'](out);ch.begin_phase('roots',['one'])
            def hook(p,timeout):
                ns['interrupted'](15,None)
                if timeout==10:raise subprocess.TimeoutExpired(['inert'],timeout)
            p=Fake(123,-9,hook);ch.live={'one':(p,['inert'],'start')}
            def kill(pid,sig): ns['events'].append((pid,sig));ns['interrupted'](2,None)
            ns['os'].killpg=kill;ch.stop()
            self.assertEqual(ns['events'],[(123,15),(123,9)]);self.assertEqual(p.calls,[10,None])
            self.assertEqual(ch.rows[0]['exit_code'],-9)

    def test_publication_boundaries_latched_stops_exceptions_and_commit_point(self):
        main=next(n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        block=copy.deepcopy(next(n for n in main.body if isinstance(n,ast.Try)))
        start=next(i for i,n in enumerate(block.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='result' for t in n.targets))
        block.body=block.body[start:]
        checkpoints=[n.lineno for n in block.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='check_cancelled']
        return_line=next(n.lineno for n in block.body if isinstance(n,ast.Return))
        targets=[n.lineno for n in block.body]
        for target in targets+[None,'link-error']:
            with self.subTest(target=target),temp() as d:
                ns=scope();out=Path(d);out.chmod(0o700)
                def write(parent,name,value):
                    if name=='FAIL.json':ns['interrupted'](2,None)
                    ns['write_json'](parent,name,value)
                def link(*a,**k):
                    os.link(*a,**k)
                    if target=='link-error':raise OSError('after real scratch link')
                pub=dict(run_gate=lambda *a:{'verdict':'PASS'},run=None,requested=None,utc=ns['utc'],
                    write_json=write,check_cancelled=ns['check_cancelled'],os=SimpleNamespace(link=link))
                fn=ast.parse('def publish(output):\n    pass\n').body[0];fn.body=[block]
                exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),'<r5 publication only>','exec'),pub)
                def inject(frame,event,arg):
                    if event=='line' and frame.f_code.co_filename=='<r5 publication only>' and frame.f_lineno==target:
                        ns['interrupted'](15,None);ns['interrupted'](1,None)
                    return inject
                sys.settrace(inject)
                try:result=pub['publish'](out)
                finally:sys.settrace(None)
                success=target in (None,return_line)
                self.assertEqual(result,0 if success else 1)
                self.assertEqual((out/'PASS.json').exists(),success)
                self.assertEqual((out/'FAIL.json').exists(),not success)
        EVENTS.append(dict(check='publication direct line injection',boundaries=targets,checkpoints=checkpoints,committed_return_line=return_line))

    def test_bootstrap_both_arms_all_guards_with_inert_dispatch(self):
        tree=ast.parse((TOOLS/'gate_worker.py').read_text());capsule=HERE/'never-materialized'
        good=dict(hash_randomization=0,safe_path=True,no_site=1,no_user_site=1)
        variants=[(good,str(capsule/'python'),'3.12.12 mock')]
        variants += [(dict(good,**{k:v}),str(capsule/'python'),'3.12.12 mock') for k,v in [('hash_randomization',1),('safe_path',False),('no_site',0),('no_user_site',0)]]
        variants += [(good,'/ambient','3.12.12 mock'),(good,str(capsule/'python'),'3.12.11 mock')]
        for tag,rt,native in [('pinned','r1','pinned-native'),('total','total-runtime','native')]:
            for i,(flags,prefix,version) in enumerate(variants):
                events=[];ss=SimpleNamespace(base_prefix=prefix,version=version,flags=SimpleNamespace(**flags),path=['/ambient'],argv=['worker',str(capsule),tag,'gate_roots.py','--sample','300'])
                oo=SimpleNamespace(environ={'CLASHER_EVAL_RUNTIME_ROOT':'/stale'})
                ns=extract(tree,{'main'},dict(Path=Path,sys=ss,os=oo,
                    signal=SimpleNamespace(SIG_SETMASK=2,pthread_sigmask=lambda *a:events.append(('reset',a[1]))),
                    runpy=SimpleNamespace(run_path=lambda *a,**k:events.append(('dispatch',a,k)))))
                if i:
                    with self.assertRaises(RuntimeError):ns['main']()
                    self.assertEqual(len(events),1)
                else:
                    ns['main']();self.assertEqual(len(events),2);self.assertEqual(events[0],('reset',set()))
                    self.assertEqual(ss.path[:3],[str(capsule/native),str(capsule/rt/'engine-rs'),str(capsule/rt/'src')])
                    self.assertTrue(all(p.startswith(str(capsule)+'/') for p in ss.path))
                    self.assertEqual(oo.environ['CLASHER_BOT_RUNTIME_PINS'],'r1');self.assertNotIn('CLASHER_EVAL_RUNTIME_ROOT',oo.environ)

    def test_git_full_prefixed_argv_authentication_forbidden_modes(self):
        def oid(kind,data):return hashlib.sha1(kind+b' '+str(len(data)).encode()+b'\0'+data).hexdigest()
        raw=b'commit';blob=b'blob';commit=oid(b'commit',raw);bid=oid(b'blob',blob)
        for prefix in ('','engine-cards','reports/cards/c1/tools'):
            for mode in ('100644','100755','120000','160000','bad-commit','bad-blob'):
                calls=[];name=(prefix+'/' if prefix else 'bot/')+'x'
                def git(repo,*args):
                    calls.append(args)
                    if args[0]=='ls-tree':return f'{mode if mode.isdigit() else "100644"} blob {bid}\t{name}\0'.encode()
                    if args[1]=='commit':return raw if mode!='bad-commit' else b'wrong'
                    return blob if mode!='bad-blob' else b'wrong'
                ns=extract(TREE,{'archive_files'},dict(C=C,hashlib=hashlib,git=git))
                if mode in ('100644','100755'):
                    self.assertEqual(ns['archive_files'](Path('/inert'),commit,prefix),{('x' if prefix else name):C.sha(blob)})
                else:
                    with self.assertRaises(ValueError):ns['archive_files'](Path('/inert'),commit,prefix)
                if mode!='bad-commit':self.assertEqual(calls[1],('ls-tree','-r','-z',commit)+(('--',prefix) if prefix else ()))

    def test_helpers_recover_historical_bytes_with_only_documented_adaptations(self):
        old=REPO/'reports/bot/learned-opponent/native-total-tools'
        f=(TOOLS/'gate_fixtures.py').read_text().replace('import os\nfrom pathlib import Path\n','')
        self.assertEqual(f.count('    rp.D = Path(os.environ["C1_GATE_FIXTURES"])\n'),3)
        f=f.replace('    rp.D = Path(os.environ["C1_GATE_FIXTURES"])\n','').replace(', action_results=actions)',')')
        self.assertEqual(f,(old/'parity_fixtures.py').read_text())
        r=(TOOLS/'gate_roots.py').read_text().replace('import os\n','').replace("sys.path.insert(0, os.environ['C1_GATE_BOT_ROOT'])","sys.path.insert(0, '/mpac/sdicks02/repos/clasher-bot')")
        r=r.replace(", runtime_root=str(rt.root),\n                                  runtime_pins=os.environ['CLASHER_BOT_RUNTIME_PINS']",'').replace("                rec['legal_actions'] = legal\n",'')
        self.assertEqual(r,(old/'parity_roots.py').read_text())
        self.assertEqual((TOOLS/'gate_compare.py').read_bytes(),(old/'compare.py').read_bytes())

    def test_confinement_and_original_controls_content_changes(self):
        ns=scope()
        with temp() as d:
            root=Path(d);real=root/'real';real.mkdir();real.chmod(0o700)
            linked=root/'linked';linked.symlink_to(real,target_is_directory=True)
            with self.assertRaises(ValueError):ns['new_file'](linked,'log')
            sentinel=root/'sentinel';sentinel.write_bytes(b'KEEP');(real/'log').symlink_to(sentinel)
            with self.assertRaises(FileExistsError):ns['new_file'](real,'log')
            (real/'PASS.json').symlink_to(root/'missing')
            with self.assertRaises(FileExistsError):ns['write_json'](real,'PASS.json',{})
            self.assertEqual(sentinel.read_bytes(),b'KEEP')
            inputs=root/'inputs';inputs.mkdir()
            for role in C.ROLES:(inputs/role).mkdir(mode=0o500)
            tool=inputs/'tools/a';(inputs/'tools').chmod(0o700);tool.write_bytes(b'original');tool.chmod(0o400);(inputs/'tools').chmod(0o500)
            initial={'ready.json':b'{"schema":2}','manifest.json':json.dumps(C.inventory(inputs)).encode()}
            for k,v in initial.items():(root/k).write_bytes(v)
            ns['check_original'](root,initial)
            tool.chmod(0o600);tool.write_bytes(b'changed');tool.chmod(0o400)
            with self.assertRaises(ValueError):ns['check_original'](root,initial)
            tool.chmod(0o600);tool.write_bytes(b'original');tool.chmod(0o400);(root/'manifest.json').write_bytes(b'{}')
            with self.assertRaises(ValueError):ns['check_original'](root,initial)

    def test_actual_expectation_derivation_and_config_boundary(self):
        with temp() as d:
            root=Path(d);fixtures=root/'fixtures';fixtures.mkdir()
            matches=[dict(episode=f'e{i}',split='validation' if i%2 else 'train') for i in range(577)]
            matches += [dict(episode='held',split='test'),dict(episode='absent',split='train')]
            (fixtures/'t1-split.json').write_text(json.dumps(dict(matches=matches)))
            for row in matches[:-1]:
                ep=fixtures/'t1-trainval'/row['episode'];ep.mkdir(parents=True)
                if row['split']=='test':continue
                (ep/'setup.json').write_text(json.dumps(dict(entry=dict(start_tick=5,split=row['split']))))
                events=[dict(accepted=True,exec_tick=t,kind=k) for t,k in [(5,'play'),(10,'play'),(11,'play'),(7,'champion ability')]]
                events += [dict(accepted=False,exec_tick=6,kind='play'),dict(accepted=True,exec_tick=None,kind='play')]
                (ep/'events.jsonl').write_text('\n'.join(map(json.dumps,events)))
                with gzip.open(ep/'objects.jsonl.gz','wt') as f:f.write('{"tick":10}\n')
                (ep/'evaluation-only.jsonl.gz').write_bytes(b'presence-only fixture for pure derivation')
            ex=C.fixture_expectations(fixtures);self.assertEqual(len(ex),577);self.assertEqual(ex['e1'],dict(ticks=5,plays=2,split='validation'))
            matches.append(matches[0]);(fixtures/'t1-split.json').write_text(json.dumps(dict(matches=matches)))
            with self.assertRaises(ValueError):C.fixture_expectations(fixtures)
            roots=root/'roots';roots.mkdir();data=b'{}';h=C.sha(data);config=roots/f'config-{h[:16]}.json';config.write_bytes(data)
            rows=[dict(index=i,tick=i,seat=i%2,config=h) for i in range(307)]
            with gzip.open(roots/'roots-0.jsonl.gz','wt') as f:f.write('\n'.join(map(json.dumps,rows)))
            actual,sample=C.root_expectations(roots);self.assertEqual(actual,rows)
            self.assertEqual(sample,sorted(random.Random(20261015).sample(range(307),300)))
            config.write_bytes(b'changed')
            with self.assertRaises(ValueError):C.root_expectations(roots)

    def test_phase_failure_order_and_clean_environment_cpu_contract(self):
        run=next(n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name=='run_gate');source=ast.unparse(run)
        terms=["children.begin_phase('fixtures'","children.wait('fixtures'",'C.audit_fixtures(',"children.begin_phase('roots'","children.wait('roots'",'C.audit_root_shard(',"children.begin_phase('comparator'","children.wait('comparator'","verdict='PASS'"]
        positions=[source.index(x) for x in terms];self.assertEqual(positions,sorted(positions));self.assertEqual(source.count('check_original(run, initial)'),4)
        plan=(TOOLS.parent/'FINAL-GATE-PLAN.md').read_text();launch=plan.split('setsid /usr/bin/env -i ',1)[1].split('```',1)[0]
        self.assertLess(launch.index('USER="$(/usr/bin/id -un)"'),launch.index('/cpu_job.sh'))
        room=Path('/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_room.sh').read_text();self.assertEqual(room.count('ps -u "$USER"'),2)
        node=next(n for n in TREE.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MIN_ENV' for t in n.targets))
        ns={};exec(compile(ast.Module(body=[node],type_ignores=[]),'<literal env>','exec'),ns)
        self.assertEqual(ns['MIN_ENV']['PYTHONHASHSEED'],'0')
        self.assertFalse(set(ns['MIN_ENV'])&{'BASH_ENV','PYTHONOPTIMIZE','PYTHONPATH','PYTHONHOME','LD_PRELOAD','CLASHER_EVAL_RUNTIME_ROOT','CLASHER_BOT_RUNTIME_PINS'})


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Review))
    with (HERE/'boundary-results.json').open('x') as f:json.dump(EVENTS,f,indent=2)
    sys.exit(not result.wasSuccessful())
