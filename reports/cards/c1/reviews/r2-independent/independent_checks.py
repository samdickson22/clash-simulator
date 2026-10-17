"""Independent local synthetic review; no host driver/main, engine or native execution.

Only stdlib, the pure contract, AST-extracted helpers, fake imports/processes, and
scratch filesystem publication are exercised. Scratch stays beside this file.
"""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
TOOLS = REPO / 'reports/cards/c1/tools'
spec = importlib.util.spec_from_file_location('pure_contract', TOOLS/'final_gate_contract.py')
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
DRIVER = ast.parse((TOOLS/'final_gate.py').read_text())


def extracted(tree, names, namespace):
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<independent AST extraction>', 'exec'), namespace)
    return namespace


class IndependentChecks(unittest.TestCase):
    def test_all_new_python_AST(self):
        for name in (*C.TOOL_FILES, 'test_final_gate_contract.py'):
            if name.endswith('.py'):
                ast.parse((TOOLS/name).read_text(), filename=name)

    def test_historical_helper_operations_exactly_preserved(self):
        old = REPO/'reports/bot/learned-opponent/native-total-tools'
        fixtures = (TOOLS/'gate_fixtures.py').read_text()
        fixtures = fixtures.replace('import os\nfrom pathlib import Path\n', '')
        self.assertEqual(fixtures.count('    rp.D = Path(os.environ["C1_GATE_FIXTURES"])\n'), 3)
        fixtures = fixtures.replace('    rp.D = Path(os.environ["C1_GATE_FIXTURES"])\n', '')
        fixtures = fixtures.replace(', action_results=actions)', ')')
        self.assertEqual(fixtures, (old/'parity_fixtures.py').read_text())
        roots = (TOOLS/'gate_roots.py').read_text().replace('import os\n', '')
        roots = roots.replace("sys.path.insert(0, os.environ['C1_GATE_BOT_ROOT'])",
                              "sys.path.insert(0, '/mpac/sdicks02/repos/clasher-bot')")
        roots = roots.replace(", runtime_root=str(rt.root),\n                                  runtime_pins=os.environ['CLASHER_BOT_RUNTIME_PINS']", '')
        roots = roots.replace("                rec['legal_actions'] = legal\n", '')
        self.assertEqual(roots, (old/'parity_roots.py').read_text())
        self.assertEqual((TOOLS/'gate_compare.py').read_bytes(), (old/'compare.py').read_bytes())

    def test_worker_both_arms_frozen_paths_and_policy(self):
        tree = ast.parse((TOOLS/'gate_worker.py').read_text())
        capsule = HERE/'synthetic-capsule'
        for tag, rt, native in [('pinned', 'r1', 'pinned-native'), ('total', 'total-runtime', 'native')]:
            calls = []
            fake_sys = SimpleNamespace(base_prefix=str(capsule/'python'), version='3.12.12 synthetic',
                                       argv=['worker',str(capsule),tag,'gate_roots.py','--sample','300'],
                                       path=['/ambient/site-packages'])
            fake_os = SimpleNamespace(environ={'CLASHER_EVAL_RUNTIME_ROOT':'/stale',
                                               'CLASHER_BOT_RUNTIME_PINS':'live16402'})
            ns = extracted(tree, {'main'}, dict(Path=Path, sys=fake_sys, os=fake_os,
                           runpy=SimpleNamespace(run_path=lambda *a, **k: calls.append((a,k)))))
            ns['main']()
            self.assertEqual(fake_sys.path[:3], [str(capsule/native),str(capsule/rt/'engine-rs'),str(capsule/rt/'src')])
            self.assertTrue(all(p.startswith(str(capsule)+'/') for p in fake_sys.path))
            self.assertNotIn('CLASHER_EVAL_RUNTIME_ROOT', fake_os.environ)
            self.assertEqual(fake_os.environ['CLASHER_BOT_RUNTIME_PINS'], 'r1')
            self.assertEqual(fake_os.environ['C1_GATE_FIXTURES'], str(capsule/'fixtures'))
            self.assertEqual(fake_sys.argv, [str(capsule/'tools/gate_roots.py'),'--sample','300'])
            self.assertEqual(calls, [((str(capsule/'tools/gate_roots.py'),),dict(run_name='__main__'))])

    def test_fixture_main_relocated_readpath_and_pool(self):
        # Execute only extracted helper main with intercepted imports and an inert pool.
        # No callback, fixture loader, engine or native code is run.
        import argparse
        import builtins
        from contextlib import redirect_stdout
        import io
        tree = ast.parse((TOOLS/'gate_fixtures.py').read_text())
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            base = Path(tmp); data = base/'fixtures'; (data/'t1-trainval/ep').mkdir(parents=True)
            out = base/'out.jsonl'; rp = SimpleNamespace(D=Path('/old/absolute/data'))
            native = SimpleNamespace(__file__='/frozen/pinned-native/clasher_core.abi3.so')
            seen = []
            fixture = SimpleNamespace(load_split=lambda p: seen.append(p) or {'ep':'train'})
            def fake_import(name, *a, **k):
                if name == 'clasher_core': return native
                if name == 'bot.fidelity': return SimpleNamespace(rs_parity=rp)
                if name == 'bot.fidelity.fixture': return fixture
                raise AssertionError('unexpected import '+name)
            class FakePool:
                def __init__(self, n): seen.append(('pool',n))
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def imap(self, fn, eps):
                    self_eps = list(eps); seen.append(('imap',self_eps))
                    return iter([dict(episode='ep', rs={}, rust_only={})])
            class FakeParser:
                def add_argument(self,*a,**k): pass
                def parse_args(self): return SimpleNamespace(out=str(out), workers=3, limit=0)
            ns = dict(__builtins__=dict(vars(builtins), __import__=fake_import),
                      argparse=SimpleNamespace(ArgumentParser=FakeParser),
                      Path=Path, os=SimpleNamespace(environ={'C1_GATE_FIXTURES':str(data)}),
                      Pool=FakePool, one=lambda ep: None, json=json)
            extracted(tree, {'main'}, ns)
            log = io.StringIO()
            with redirect_stdout(log): ns['main']()
            self.assertEqual(rp.D, data)
            self.assertEqual(seen, [data/'t1-split.json',('pool',3),('imap',['ep'])])
            self.assertEqual(json.loads(log.getvalue()), dict(native=native.__file__,fixtures=1))
            self.assertEqual(json.loads(out.read_text())['episode'],'ep')

    def test_archive_default_sends_empty_pathspec(self):
        # Real local Git independently returned128 for this exact argument shape.
        raw = b'synthetic commit'
        oid = hashlib.sha1(b'commit '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        seen=[]
        def git(repo,*args):
            seen.append(args)
            if args[:2] == ('cat-file','commit'): return raw
            if args == ('ls-tree','-r','-z',oid,'--',''):
                raise ValueError('fatal: empty string is not a valid pathspec')
            raise AssertionError(args)
        ns=extracted(DRIVER, {'archive_files'},dict(C=C,hashlib=hashlib,git=git))
        with self.assertRaisesRegex(ValueError,'empty string'):
            ns['archive_files'](Path('/fake'),oid)
        self.assertEqual(seen[-1],('ls-tree','-r','-z',oid,'--',''))

    def test_PASS_publication_success_and_postlink_exception(self):
        # Only the publication tail and its actual failure handler, never host main.
        main=next(n for n in DRIVER.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        block=next(n for n in main.body if isinstance(n,ast.Try))
        start=next(i for i,n in enumerate(block.body) if isinstance(n,ast.Assign)
                   and any(isinstance(x,ast.Name) and x.id=='result' for x in n.targets))
        tail=copy.deepcopy(block); tail.body=tail.body[start:]
        func=ast.parse('def publish(output):\n    pass\n').body[0]; func.body=[tail]
        for fail_after_link in (False,True):
            with tempfile.TemporaryDirectory(dir=HERE) as tmp:
                output=Path(tmp); output.chmod(0o700)
                def link(*a,**k):
                    os.link(*a,**k)
                    if fail_after_link: raise InterruptedError('synthetic after-link signal')
                ns=dict(C=C,Path=Path,os=SimpleNamespace(link=link),run=None,requested=None,
                        utc=lambda:'2026-10-16T00:00:00Z',run_gate=lambda *a:dict(verdict='PASS'))
                extracted(DRIVER, {'directory','new_file','write_json'}, ns)
                # Filesystem helpers need the real stdlib OS; publication alone gets the fault-injected link.
                fs=dict(C=C,Path=Path,os=os,stat=stat,json=json)
                extracted(DRIVER,{'directory','new_file','write_json'},fs)
                ns['write_json']=fs['write_json']
                exec(compile(ast.fix_missing_locations(ast.Module(body=[func],type_ignores=[])), '<publication only>', 'exec'),ns)
                code=ns['publish'](output)
                self.assertEqual(code,1 if fail_after_link else 0)
                self.assertEqual((output/'PASS.json').exists(),not fail_after_link)
                self.assertEqual((output/'FAIL.json').exists(),fail_after_link)

    def test_outer_wrapper_environment_source_dependency(self):
        plan=(REPO/'reports/cards/c1/FINAL-GATE-PLAN.md').read_text()
        invocation=plan.split('setsid /usr/bin/env -i ',1)[1].split('```',1)[0]
        self.assertNotIn('USER=',invocation)
        room=Path('/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_room.sh').read_text()
        self.assertEqual(room.count('ps -u "$USER"'),2)
        self.assertIn('$(live) + $(leased_idle) + n > cap',room)
        # This asserts the defect's source trace; it does not run bash, ps, the wrapper or a host command.


if __name__ == '__main__':
    unittest.main(verbosity=2)
