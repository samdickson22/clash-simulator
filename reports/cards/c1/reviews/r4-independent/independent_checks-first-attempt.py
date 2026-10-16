"""Fresh r4 independent checks. Only pure/AST snippets, stdlib, scratch files and inert mocks.
The cleanup-entry test deliberately demonstrates a finding; test PASS does not mean approval.
No driver main/run_gate or actual worker/helper is executed. No real masks, signals or gate Popen.
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
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
TOOLS = REPO / 'reports/cards/c1/tools'
TREE = ast.parse((TOOLS/'final_gate.py').read_text())
spec = importlib.util.spec_from_file_location('pure_contract_r4', TOOLS/'final_gate_contract.py')
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)


def extract(tree, names, scope):
    nodes = [copy.deepcopy(n) for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<r4 extracted helper>', 'exec'), scope)
    return scope


def fs_scope():
    fake_signal = SimpleNamespace(SIGTERM=signal.SIGTERM, SIGINT=signal.SIGINT, SIGHUP=signal.SIGHUP,
        SIG_BLOCK=signal.SIG_BLOCK, SIG_SETMASK=signal.SIG_SETMASK, pthread_sigmask=lambda *a: set())
    return extract(TREE, {'Children', 'directory', 'new_file', 'write_json', 'check_original', 'interrupted'},
        dict(C=C, os=os, Path=Path, stat=stat, json=json, subprocess=subprocess, signal=fake_signal,
             utc=lambda: '2026-10-16T11:00:00Z'))


def cleanup_probe(scope, initial_stop=False):
    # ONLY the cleanup finally suite, never run_gate/preflight/dispatch.
    run = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == 'run_gate')
    final = next(n for n in run.body if isinstance(n, ast.Try)).finalbody
    fn = ast.parse('def cleanup_probe(children):\n    pass\n').body[0]
    if initial_stop:
        block = ast.parse("try:\n    raise InterruptedError('first stop during wait')\nfinally:\n    pass\n").body[0]
        block.finalbody = copy.deepcopy(final); fn.body = [block]
    else:
        fn.body = copy.deepcopy(final)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), '<r4 cleanup suite only>', 'exec'), scope)
    return scope['cleanup_probe'], final[0].lineno


class Fake:
    def __init__(self, pid, code=0, interrupt=False):
        self.pid, self.code, self.interrupt, self.calls = pid, code, interrupt, []
    def wait(self, timeout=None):
        self.calls.append(timeout)
        if self.interrupt:
            self.interrupt = False
            raise InterruptedError('synthetic wait stop')
        return self.code


class Review(unittest.TestCase):
    def test_persistent_receipts_all_later_wait_boundaries(self):
        for count in (2, 8):
            for boundary in range(1, count):
                for status in (0, 17, -15):
                    with self.subTest(count=count, boundary=boundary, status=status), tempfile.TemporaryDirectory(dir=HERE) as d:
                        out=Path(d); out.chmod(0o700); ns=fs_scope(); ch=ns['Children'](out)
                        labels=[f'child{i}' for i in range(count)]
                        ch.live={k:(Fake(100+i, status if i==0 else 0, i==boundary), ['inert'], 'start') for i,k in enumerate(labels)}
                        with self.assertRaises(InterruptedError): ch.wait('phase', labels)
                        prior=json.loads((out/'phase-exits.json').read_text())
                        self.assertEqual([r['label'] for r in prior],labels[:boundary])
                        self.assertEqual(prior[0]['exit_code'],status)
                        with patch.object(os,'killpg') as kill: ch.stop()
                        self.assertEqual(kill.call_count,count-boundary)
                        rows=json.loads((out/'all-child-exits.json').read_text())
                        self.assertEqual(len(rows),count); self.assertEqual(rows[:boundary],prior)
                        self.assertEqual(json.loads((out/'phase-final-exits.json').read_text()),rows)

    def test_wait_return_before_persistent_store_recovers_cached_status(self):
        with tempfile.TemporaryDirectory(dir=HERE) as d:
            out=Path(d); out.chmod(0o700); ns=fs_scope(); ch=ns['Children'](out)
            p=Fake(101,17); ch.live={'first':(p,['inert'],'start')}
            def clock(): raise InterruptedError('after wait before persistent store')
            ns['utc']=clock
            with self.assertRaises(InterruptedError): ch.wait('phase',['first'])
            self.assertEqual(ch.rows,[]); self.assertIn('first',ch.live)
            ns['utc']=lambda:'end'
            with patch.object(os,'killpg'): ch.stop()
            self.assertEqual(ch.rows[0]['exit_code'],17); self.assertEqual(p.calls,[None,10])

    def test_store_delete_gap_keeps_first_status_and_timestamp(self):
        with tempfile.TemporaryDirectory(dir=HERE) as d:
            out=Path(d); out.chmod(0o700); ns=fs_scope(); ch=ns['Children'](out)
            class InterruptedMap(dict):
                def __setitem__(self,k,v):
                    super().__setitem__(k,v); raise InterruptedError('after durable bookkeeping')
            ch.completed=InterruptedMap(); p=Fake(101,-9); ch.live={'first':(p,['inert'],'start')}
            with self.assertRaises(InterruptedError): ch.wait('phase',['first'])
            original=copy.deepcopy(ch.rows)
            with patch.object(os,'killpg'): ch.stop()
            self.assertEqual(ch.rows,original); self.assertEqual(p.calls,[None]); self.assertFalse(ch.live)

    def test_spawn_registers_before_deferred_stop_and_preserves_empty_phase(self):
        for fail_spawn in (False,True):
            with self.subTest(fail_spawn=fail_spawn), tempfile.TemporaryDirectory(dir=HERE) as d:
                out=Path(d); out.chmod(0o700); ns=fs_scope(); ch=ns['Children'](out); ch.begin_phase('fixtures',['first','second'])
                events=[]
                def popen(*a,**k):
                    events.append(('spawn',k['start_new_session']))
                    if fail_spawn: raise OSError('synthetic exec failure')
                    return Fake(123,17)
                def mask(how,old):
                    events.append(('mask',int(how)))
                    if how==signal.SIG_SETMASK and not fail_spawn:
                        self.assertIn('first',ch.live); raise InterruptedError('deferred stop')
                    return set()
                ns['subprocess']=SimpleNamespace(Popen=popen,DEVNULL=-3,STDOUT=-2,TimeoutExpired=subprocess.TimeoutExpired)
                ns['signal'].pthread_sigmask=mask
                with self.assertRaises(OSError if fail_spawn else InterruptedError): ch.start('first',['inert'],{})
                with patch.object(os,'killpg'): ch.stop()
                final=json.loads((out/'fixtures-final-exits.json').read_text())
                self.assertEqual([r['label'] for r in final],[] if fail_spawn else ['first'])
                self.assertEqual(final,json.loads((out/'all-child-exits.json').read_text()))

    def test_phase_receipt_written_before_pending_signal_is_restored(self):
        with tempfile.TemporaryDirectory(dir=HERE) as d:
            out=Path(d); out.chmod(0o700); ns=fs_scope(); ch=ns['Children'](out)
            ch.live={'one':(Fake(101),['inert'],'start')}
            def mask(how,old):
                if how==signal.SIG_SETMASK:
                    self.assertTrue((out/'phase-exits.json').exists()); raise InterruptedError('pending cancellation')
                return set()
            ns['signal'].pthread_sigmask=mask
            with self.assertRaises(InterruptedError): ch.wait('phase',['one'])
            with patch.object(os,'killpg'): ch.stop()
            self.assertEqual(len(ch.rows),1)

    def test_cleanup_defers_pending_stop_until_receipts_complete(self):
        with tempfile.TemporaryDirectory(dir=HERE) as d:
            out=Path(d); out.chmod(0o700); ns=fs_scope(); ch=ns['Children'](out)
            ch.begin_phase('fixtures',['one']); ch.live={'one':(Fake(101,-15),['inert'],'start')}
            def mask(how,old):
                if how==signal.SIG_SETMASK:
                    self.assertTrue((out/'all-child-exits.json').exists())
                    raise InterruptedError('pending cancellation after cleanup')
                return set()
            ns['signal'].pthread_sigmask=mask; cleanup,_=cleanup_probe(ns)
            with patch.object(os,'killpg'), self.assertRaises(InterruptedError): cleanup(ch)
            self.assertEqual(ch.rows[0]['exit_code'],-15); self.assertFalse(ch.live)

    def test_R4_cleanup_entry_second_stop_bypasses_reap_and_final_receipts(self):
        with tempfile.TemporaryDirectory(dir=HERE) as d:
            out=Path(d); out.chmod(0o700); ns=fs_scope(); ch=ns['Children'](out)
            ch.begin_phase('fixtures',['one']); p=Fake(101,-15); ch.live={'one':(p,['inert'],'start')}
            events=[]
            ns['signal'].pthread_sigmask=lambda *a: events.append(['mask',int(a[0])]) or set()
            cleanup,boundary=cleanup_probe(ns,initial_stop=True)
            def inject(frame,event,arg):
                if frame.f_code.co_filename=='<r4 cleanup suite only>' and event=='line' and frame.f_lineno==boundary:
                    events.append(['second_handler_at_cleanup_entry',boundary])
                    ns['interrupted'](signal.SIGTERM,None)
                return inject
            with patch.object(os,'killpg') as kill:
                sys.settrace(inject)
                try:
                    with self.assertRaisesRegex(InterruptedError,'received signal'): cleanup(ch)
                finally: sys.settrace(None)
                self.assertEqual(kill.call_count,0)
            self.assertEqual(p.calls,[]); self.assertEqual(events,[['second_handler_at_cleanup_entry',boundary]])
            self.assertIn('one',ch.live); self.assertFalse((out/'all-child-exits.json').exists())
            evidence=dict(candidate='c7de06ea5a6171b4490682a7bb1be9baa825a2b4',
                scope='Only AST-extracted cleanup finally suite and pure handler, fake PID/wait/kill/mask; first stop synthesized in replacement body, second handler injected by stdlib trace before first cleanup mask line. No run_gate/main or real signal/mask/process.',
                line=boundary,events=events,kill_calls=0,wait_calls=p.calls,live_labels=list(ch.live),
                phase_final_exists=(out/'fixtures-final-exits.json').exists(),all_child_exists=False,
                effect='Second stop aborts entry to cleanup; known child is never stopped/waited and final receipts are absent.')
            with (HERE/'cleanup-entry-reproduction.json').open('x') as f: json.dump(evidence,f,indent=2)

    def test_timeout_cleanup_escalates_only_known_pgid_then_reaps(self):
        with tempfile.TemporaryDirectory(dir=HERE) as d:
            out=Path(d); out.chmod(0o700); ns=fs_scope(); ch=ns['Children'](out)
            class Slow(Fake):
                def wait(self,timeout=None):
                    self.calls.append(timeout)
                    if timeout is not None: raise subprocess.TimeoutExpired(['inert'],timeout)
                    return -9
            p=Slow(321); ch.begin_phase('roots',['one']); ch.live={'one':(p,['inert'],'start')}
            with patch.object(os,'killpg') as kill: ch.stop()
            self.assertEqual(kill.call_args_list,[unittest.mock.call(321,signal.SIGTERM),unittest.mock.call(321,signal.SIGKILL)])
            self.assertEqual(ch.rows[0]['exit_code'],-9); self.assertEqual(p.calls,[10,None])

    def test_bootstrap_reset_and_guards_both_arms_with_inert_dispatch(self):
        tree=ast.parse((TOOLS/'gate_worker.py').read_text()); capsule=HERE/'inert'
        good=dict(hash_randomization=0,safe_path=True,no_site=1,no_user_site=1)
        variants=[good]+[dict(good,**{k:v}) for k,v in [('hash_randomization',1),('safe_path',False),('no_site',0),('no_user_site',0)]]
        for tag,role,native in [('pinned','r1','pinned-native'),('total','total-runtime','native')]:
            for flags in variants:
                events=[]; fake_sys=SimpleNamespace(base_prefix=str(capsule/'python'),version='3.12.12 mock',
                    flags=SimpleNamespace(**flags),path=['/ambient'],argv=['worker',str(capsule),tag,'gate_roots.py','--sample','300'])
                fake_os=SimpleNamespace(environ={'CLASHER_EVAL_RUNTIME_ROOT':'/stale','CLASHER_BOT_RUNTIME_PINS':'wrong'})
                ns=extract(tree,{'main'},dict(Path=Path,sys=fake_sys,os=fake_os,
                    signal=SimpleNamespace(SIG_SETMASK=signal.SIG_SETMASK,pthread_sigmask=lambda *a:events.append(['reset',a[1]])),
                    runpy=SimpleNamespace(run_path=lambda *a,**k:events.append(['dispatch',a,k]))))
                if flags!=good:
                    with self.assertRaises(RuntimeError): ns['main']()
                    self.assertEqual([x[0] for x in events],['reset']); continue
                ns['main'](); self.assertEqual([x[0] for x in events],['reset','dispatch'])
                self.assertEqual(events[0][1],set())
                self.assertEqual(fake_sys.path[:3],[str(capsule/native),str(capsule/role/'engine-rs'),str(capsule/role/'src')])
                self.assertTrue(all(x.startswith(str(capsule)+'/') for x in fake_sys.path))
                self.assertNotIn('CLASHER_EVAL_RUNTIME_ROOT',fake_os.environ)
                self.assertEqual(fake_os.environ['CLASHER_BOT_RUNTIME_PINS'],'r1')

    def test_archive_exact_full_engine_and_tools_argv_and_forbidden_modes(self):
        def oid(kind,data): return hashlib.sha1(kind+b' '+str(len(data)).encode()+b'\0'+data).hexdigest()
        raw=b'commit'; blob=b'blob'; commit=oid(b'commit',raw); boid=oid(b'blob',blob)
        for prefix in ('','engine-cards','reports/cards/c1/tools'):
            for mode in ('100644','100755','120000','160000'):
                calls=[]; name=prefix+'/x' if prefix else 'bot/x'
                def git(repo,*args):
                    calls.append(args)
                    if args[0]=='ls-tree': return f'{mode} blob {boid}\t{name}\0'.encode()
                    return raw if args[1]=='commit' else blob
                ns=extract(TREE,{'archive_files'},dict(C=C,hashlib=hashlib,git=git))
                if mode in ('120000','160000'):
                    with self.assertRaises(ValueError): ns['archive_files'](Path('/inert'),commit,prefix)
                else:
                    self.assertEqual(ns['archive_files'](Path('/inert'),commit,prefix),{'x' if prefix else name:C.sha(blob)})
                self.assertEqual(calls[1],('ls-tree','-r','-z',commit)+(('--',prefix) if prefix else ()))

    def test_historical_helper_bytes_after_only_declared_adaptations(self):
        old=REPO/'reports/bot/learned-opponent/native-total-tools'
        f=(TOOLS/'gate_fixtures.py').read_text().replace('import os\nfrom pathlib import Path\n','')
        self.assertEqual(f.count('    rp.D = Path(os.environ["C1_GATE_FIXTURES"])\n'),3)
        f=f.replace('    rp.D = Path(os.environ["C1_GATE_FIXTURES"])\n','').replace(', action_results=actions)',')')
        self.assertEqual(f,(old/'parity_fixtures.py').read_text())
        r=(TOOLS/'gate_roots.py').read_text().replace('import os\n','')
        r=r.replace("sys.path.insert(0, os.environ['C1_GATE_BOT_ROOT'])","sys.path.insert(0, '/mpac/sdicks02/repos/clasher-bot')")
        r=r.replace(", runtime_root=str(rt.root),\n                                  runtime_pins=os.environ['CLASHER_BOT_RUNTIME_PINS']",'')
        r=r.replace("                rec['legal_actions'] = legal\n",'')
        self.assertEqual(r,(old/'parity_roots.py').read_text())
        self.assertEqual((TOOLS/'gate_compare.py').read_bytes(),(old/'compare.py').read_bytes())

    def test_control_and_tool_replacement_rejected_after_modes_restored(self):
        with tempfile.TemporaryDirectory(dir=HERE) as d:
            run=Path(d); root=run/'inputs'; root.mkdir()
            for role in C.ROLES: (root/role).mkdir(mode=0o500)
            (root/'tools').chmod(0o700); tool=root/'tools/a'; tool.write_bytes(b'original'); tool.chmod(0o400); (root/'tools').chmod(0o500)
            initial={'ready.json':b'{"schema":2}','manifest.json':json.dumps(C.inventory(root)).encode()}
            for k,v in initial.items(): (run/k).write_bytes(v)
            ns=fs_scope(); ns['check_original'](run,initial)
            tool.chmod(0o600); tool.write_bytes(b'replacement'); tool.chmod(0o400)
            with self.assertRaises(ValueError): ns['check_original'](run,initial)
            tool.chmod(0o600); tool.write_bytes(b'original'); tool.chmod(0o400); (run/'manifest.json').write_bytes(b'{}')
            with self.assertRaises(ValueError): ns['check_original'](run,initial)

    def test_confinement_link_parent_stale_dangling_and_no_clobber(self):
        ns=fs_scope()
        with tempfile.TemporaryDirectory(dir=HERE) as d:
            root=Path(d); real=root/'real'; real.mkdir(); real.chmod(0o700); sentinel=root/'sentinel'; sentinel.write_text('KEEP')
            linked=root/'linked'; linked.symlink_to(real,target_is_directory=True)
            with self.assertRaises(ValueError): ns['new_file'](linked,'log')
            (real/'log').symlink_to(sentinel)
            with self.assertRaises(FileExistsError): ns['new_file'](real,'log')
            (real/'PASS.json').symlink_to(root/'absent')
            with self.assertRaises(FileExistsError): ns['write_json'](real,'PASS.json',{})
            self.assertEqual(sentinel.read_text(),'KEEP'); self.assertFalse((root/'absent').exists())

    def test_publication_only_tail_success_and_postlink_exception(self):
        main=next(n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        block=copy.deepcopy(next(n for n in main.body if isinstance(n,ast.Try)))
        start=next(i for i,n in enumerate(block.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='result' for t in n.targets))
        block.body=block.body[start:]; fn=ast.parse('def publish(output):\n    pass\n').body[0]; fn.body=[block]
        for fail in (False,True):
            with tempfile.TemporaryDirectory(dir=HERE) as d:
                out=Path(d); out.chmod(0o700)
                def link(*a,**k):
                    os.link(*a,**k)
                    if fail: raise InterruptedError('after link')
                ns=dict(os=SimpleNamespace(link=link),run=None,requested=None,run_gate=lambda *a:{'verdict':'PASS'},
                        write_json=fs_scope()['write_json'],utc=lambda:'end')
                exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),'<publication tail only>','exec'),ns)
                self.assertEqual(ns['publish'](out),int(fail)); self.assertEqual((out/'PASS.json').exists(),not fail)
                self.assertEqual((out/'FAIL.json').exists(),fail)

    def test_expectation_derivation_split_actions_sample_config_negatives(self):
        with tempfile.TemporaryDirectory(dir=HERE) as d:
            p=Path(d); fixtures=p/'fixtures'; fixtures.mkdir()
            matches=[dict(episode=f'e{i}',split='validation' if i%2 else 'train') for i in range(577)]
            (fixtures/'t1-split.json').write_text(json.dumps(dict(matches=matches)))
            for r in matches:
                ep=fixtures/'t1-trainval'/r['episode']; ep.mkdir(parents=True)
                (ep/'setup.json').write_text(json.dumps(dict(entry=dict(start_tick=5,split=r['split']))))
                events=[dict(accepted=True,exec_tick=t,kind=k) for t,k in [(5,'play'),(10,'play'),(11,'play'),(7,'champion ability')]]
                events.append(dict(accepted=False,exec_tick=6,kind='play'))
                (ep/'events.jsonl').write_text('\n'.join(map(json.dumps,events)))
                with gzip.open(ep/'objects.jsonl.gz','wt') as f: f.write('{"tick":10}\n')
                (ep/'evaluation-only.jsonl.gz').write_bytes(b'only presence is needed for this pure expectation check')
            expect=C.fixture_expectations(fixtures); self.assertEqual(len(expect),577)
            self.assertEqual(expect['e1'],dict(ticks=5,plays=2,split='validation'))
            matches.append(matches[0]); (fixtures/'t1-split.json').write_text(json.dumps(dict(matches=matches)))
            with self.assertRaises(ValueError): C.fixture_expectations(fixtures)
            roots=p/'roots'; roots.mkdir(); data=b'{}'; h=C.sha(data); config=roots/f'config-{h[:16]}.json'; config.write_bytes(data)
            rows=[dict(index=i,tick=i,seat=i%2,config=h) for i in range(307)]
            with gzip.open(roots/'roots-0.jsonl.gz','wt') as f: f.write('\n'.join(map(json.dumps,rows)))
            actual,sample=C.root_expectations(roots); self.assertEqual(actual,rows)
            self.assertEqual(sample,sorted(random.Random(20261015).sample(range(307),300)))
            config.write_bytes(b'changed')
            with self.assertRaises(ValueError): C.root_expectations(roots)

    def test_ast_phase_order_cpu_identity_and_minimal_seed_contract(self):
        for name in C.TOOL_FILES+('test_final_gate_contract.py',):
            if name.endswith('.py'): ast.parse((TOOLS/name).read_text())
        run=next(n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name=='run_gate'); source=ast.unparse(run)
        tokens=["children.begin_phase('fixtures'","children.wait('fixtures'",'C.audit_fixtures(',"children.begin_phase('roots'",
                "children.wait('roots'",'C.audit_root_shard(',"children.begin_phase('comparator'","children.wait('comparator'","verdict='PASS'"]
        positions=[source.index(t) for t in tokens]; self.assertEqual(positions,sorted(positions)); self.assertEqual(source.count('check_original(run, initial)'),4)
        plan=(TOOLS.parent/'FINAL-GATE-PLAN.md').read_text(); launch=plan.split('setsid /usr/bin/env -i ',1)[1].split('```',1)[0]
        self.assertLess(launch.index('USER="$(/usr/bin/id -un)"'),launch.index('/cpu_job.sh'))
        self.assertEqual(Path('/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_room.sh').read_text().count('ps -u "$USER"'),2)
        env_node=next(n for n in TREE.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MIN_ENV' for t in n.targets))
        env={}; exec(compile(ast.Module(body=[env_node],type_ignores=[]),'<literal env>','exec'),env)
        self.assertEqual(env['MIN_ENV']['PYTHONHASHSEED'],'0')
        self.assertFalse(set(env['MIN_ENV'])&{'BASH_ENV','PYTHONPATH','PYTHONHOME','PYTHONOPTIMIZE','LD_PRELOAD','CLASHER_EVAL_RUNTIME_ROOT','CLASHER_BOT_RUNTIME_PINS'})


if __name__=='__main__': unittest.main(verbosity=2)
