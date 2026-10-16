"""Fresh serial review: pure validators, AST snippets, inert mocks and scratch files only.

No driver main/run_gate, real worker/helper, native or engine is executed.
The interruption test explicitly reproduces a finding; its PASS is not approval.
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
import tempfile
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
TOOLS = REPO / 'reports/cards/c1/tools'
DRIVER = ast.parse((TOOLS / 'final_gate.py').read_text())
spec = importlib.util.spec_from_file_location('contract_only', TOOLS / 'final_gate_contract.py')
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)


def extract(tree, names, ns):
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    exec(compile(ast.Module(body=copy.deepcopy(nodes), type_ignores=[]), '<review AST helper>', 'exec'), ns)
    return ns


def fs_scope():
    return extract(DRIVER, {'directory', 'new_file', 'write_json', 'Children', 'check_original'},
                   dict(C=C, os=os, stat=stat, json=json, Path=Path,
                        utc=lambda: '2026-10-16T00:00:00Z'))


class ReviewTests(unittest.TestCase):
    def test_all_python_AST_and_phase_order(self):
        for name in C.TOOL_FILES + ('test_final_gate_contract.py',):
            if name.endswith('.py'):
                ast.parse((TOOLS/name).read_text())
        fn = next(n for n in DRIVER.body if isinstance(n, ast.FunctionDef) and n.name == 'run_gate')
        body = ast.unparse(fn)
        positions = [body.index(s) for s in ("children.wait('fixtures'", 'C.audit_fixtures(',
                     "children.start(label", "children.wait('roots'", 'C.audit_root_shard(',
                     "children.start('compare'", "children.wait('comparator'", "verdict='PASS'")]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(body.count('check_original(run, initial)'), 4)

    def test_R2_archive_full_and_prefix_exact_argv(self):
        commit_data, blob = b'synthetic commit', b'synthetic source'
        def oid(kind, data):
            return hashlib.sha1(kind + b' ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        commit, blob_id = oid(b'commit', commit_data), oid(b'blob', blob)
        for prefix in ('', 'engine-cards', 'reports/cards/c1/tools'):
            name = prefix + '/x.py' if prefix else 'bot/x.py'
            calls = []
            def fake_git(repo, *args):
                calls.append(args)
                if args == ('cat-file', 'commit', commit): return commit_data
                if args[0] == 'ls-tree':
                    return f'100644 blob {blob_id}\t{name}\0'.encode()
                if args == ('cat-file', 'blob', blob_id): return blob
                raise AssertionError(args)
            ns = extract(DRIVER, {'archive_files'}, dict(C=C, hashlib=hashlib, git=fake_git))
            self.assertEqual(ns['archive_files'](Path('/inert'), commit, prefix),
                             {'x.py' if prefix else name: C.sha(blob)})
            self.assertEqual(calls[1], ('ls-tree', '-r', '-z', commit) + (('--', prefix) if prefix else ()))

    def test_R2_CPU_identity_source_and_minimal_worker_command(self):
        plan = (TOOLS.parent/'FINAL-GATE-PLAN.md').read_text()
        invocation = plan.split('setsid /usr/bin/env -i ', 1)[1].split('```', 1)[0]
        self.assertIn('USER="$(/usr/bin/id -un)"', invocation)
        self.assertLess(invocation.index('USER='), invocation.index('/cpu_job.sh'))
        room = Path('/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_room.sh').read_text()
        self.assertEqual(room.count('ps -u "$USER"'), 2)
        env_ast = next(n for n in DRIVER.body if isinstance(n, ast.Assign) and
                       any(isinstance(t, ast.Name) and t.id == 'MIN_ENV' for t in n.targets))
        ns = {}; exec(compile(ast.Module(body=[env_ast], type_ignores=[]), '<literal env>', 'exec'), ns)
        self.assertEqual(ns['MIN_ENV']['PYTHONHASHSEED'], '0')
        self.assertFalse(set(ns['MIN_ENV']) & {'BASH_ENV', 'PYTHONPATH', 'PYTHONHOME', 'PYTHONOPTIMIZE',
                         'CLASHER_EVAL_RUNTIME_ROOT', 'CLASHER_BOT_RUNTIME_PINS', 'LD_PRELOAD'})
        cmd = next(n for n in ast.walk(DRIVER) if isinstance(n, ast.FunctionDef) and n.name == 'command')
        ns = dict(capsule=HERE/'inert-capsule')
        exec(compile(ast.Module(body=[cmd], type_ignores=[]), '<command builder only>', 'exec'), ns)
        args = ns['command']('total', 'gate_roots.py', '--sample', 300)
        self.assertEqual(args[3:8], [str(HERE/'inert-capsule/python/bin/python3.12'), '-P', '-s', '-S', '-B'])

    def test_bootstrap_guard_AST_with_inert_runpy_both_arms_and_bad_flags(self):
        # Run only an AST-extracted bootstrap function against fake sys/os/runpy.
        # No gate_worker module execution or dispatch into a real helper occurs.
        tree = ast.parse((TOOLS/'gate_worker.py').read_text())
        capsule = HERE/'inert-capsule'
        good = dict(hash_randomization=0, safe_path=True, no_site=1, no_user_site=1)
        variants = [good] + [dict(good, **{k: v}) for k, v in
                    [('hash_randomization', 1), ('safe_path', False), ('no_site', 0), ('no_user_site', 0)]]
        for tag, rt, native in [('pinned', 'r1', 'pinned-native'), ('total', 'total-runtime', 'native')]:
            for flags in variants:
                calls = []
                fake_sys = SimpleNamespace(base_prefix=str(capsule/'python'), version='3.12.12 mock',
                    flags=SimpleNamespace(**flags), path=['/ambient'],
                    argv=['worker', str(capsule), tag, 'gate_roots.py', '--sample', '300'])
                fake_os = SimpleNamespace(environ={'CLASHER_EVAL_RUNTIME_ROOT': '/stale',
                                                  'CLASHER_BOT_RUNTIME_PINS': 'wrong'})
                ns = extract(tree, {'main'}, dict(sys=fake_sys, os=fake_os, Path=Path,
                    runpy=SimpleNamespace(run_path=lambda *a, **k: calls.append((a, k)))))
                if flags != good:
                    with self.assertRaises(RuntimeError): ns['main']()
                    self.assertEqual(calls, [])
                    continue
                ns['main']()
                self.assertEqual(fake_sys.path[:3], [str(capsule/native), str(capsule/rt/'engine-rs'), str(capsule/rt/'src')])
                self.assertTrue(all(p.startswith(str(capsule) + '/') for p in fake_sys.path))
                self.assertEqual(fake_os.environ['CLASHER_BOT_RUNTIME_PINS'], 'r1')
                self.assertNotIn('CLASHER_EVAL_RUNTIME_ROOT', fake_os.environ)
                self.assertEqual(fake_sys.argv, [str(capsule/'tools/gate_roots.py'), '--sample', '300'])
                self.assertEqual(len(calls), 1)

    def test_historical_helpers_exactly_preserved_after_declared_adaptations(self):
        old = REPO/'reports/bot/learned-opponent/native-total-tools'
        f = (TOOLS/'gate_fixtures.py').read_text().replace('import os\nfrom pathlib import Path\n', '')
        self.assertEqual(f.count('    rp.D = Path(os.environ["C1_GATE_FIXTURES"])\n'), 3)
        f = f.replace('    rp.D = Path(os.environ["C1_GATE_FIXTURES"])\n', '').replace(', action_results=actions)', ')')
        self.assertEqual(f, (old/'parity_fixtures.py').read_text())
        r = (TOOLS/'gate_roots.py').read_text().replace('import os\n', '')
        r = r.replace("sys.path.insert(0, os.environ['C1_GATE_BOT_ROOT'])", "sys.path.insert(0, '/mpac/sdicks02/repos/clasher-bot')")
        r = r.replace(", runtime_root=str(rt.root),\n                                  runtime_pins=os.environ['CLASHER_BOT_RUNTIME_PINS']", '')
        r = r.replace("                rec['legal_actions'] = legal\n", '')
        self.assertEqual(r, (old/'parity_roots.py').read_text())
        self.assertEqual((TOOLS/'gate_compare.py').read_bytes(), (old/'compare.py').read_bytes())

    def test_frozen_control_and_input_content_replacements(self):
        ns = fs_scope()
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            run = Path(tmp); root = run/'inputs'; root.mkdir()
            for role in C.ROLES: (root/role).mkdir(mode=0o500)
            (root/'tools').chmod(0o700)
            tool = root/'tools/f.py'; tool.write_bytes(b'original'); tool.chmod(0o400)
            (root/'tools').chmod(0o500)
            initial = {'ready.json': b'{"schema":2}', 'manifest.json': json.dumps(C.inventory(root)).encode()}
            for k, v in initial.items(): (run/k).write_bytes(v)
            ns['check_original'](run, initial)
            tool.chmod(0o600); tool.write_bytes(b'replaced'); tool.chmod(0o400)
            with self.assertRaises(ValueError): ns['check_original'](run, initial)
            tool.chmod(0o600); tool.write_bytes(b'original'); tool.chmod(0o400)
            (run/'manifest.json').write_bytes(b'{}')
            with self.assertRaises(ValueError): ns['check_original'](run, initial)

    def test_output_parent_and_stale_dangling_paths_reject(self):
        ns = fs_scope()
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            root = Path(tmp); real = root/'real'; real.mkdir(mode=0o700); real.chmod(0o700)
            linked = root/'linked'; linked.symlink_to(real, target_is_directory=True)
            with self.assertRaises(ValueError): ns['new_file'](linked, 'log')
            (real/'PASS.json').symlink_to(root/'absent')
            with self.assertRaises(FileExistsError): ns['write_json'](real, 'PASS.json', {'verdict': 'PASS'})
            self.assertFalse((root/'absent').exists())

    def test_publication_tail_postlink_failure_removes_PASS(self):
        main = next(n for n in DRIVER.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        block = copy.deepcopy(next(n for n in main.body if isinstance(n, ast.Try)))
        start = next(i for i, n in enumerate(block.body) if isinstance(n, ast.Assign) and
                     any(isinstance(t, ast.Name) and t.id == 'result' for t in n.targets))
        block.body = block.body[start:]
        fn = ast.parse('def publish(output):\n    pass\n').body[0]; fn.body = [block]
        for failed in (False, True):
            with tempfile.TemporaryDirectory(dir=HERE) as tmp:
                out = Path(tmp); out.chmod(0o700)
                def link(*a, **k):
                    os.link(*a, **k)
                    if failed: raise InterruptedError('injected immediately after PASS link')
                ns = dict(os=SimpleNamespace(link=link), run=None, requested=None,
                          run_gate=lambda *a: {'verdict': 'PASS'}, utc=lambda: '2026-10-16T00:00:00Z',
                          write_json=fs_scope()['write_json'])
                exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), '<publication tail only>', 'exec'), ns)
                self.assertEqual(ns['publish'](out), int(failed))
                self.assertEqual((out/'PASS.json').exists(), not failed)
                self.assertEqual((out/'FAIL.json').exists(), failed)

    def test_expected_fixture_and_root_derivation_from_synthetic_files(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            p = Path(tmp); fixtures = p/'fixtures'; fixtures.mkdir()
            matches = [{'episode': f'e{i}', 'split': 'train'} for i in range(577)]
            (fixtures/'t1-split.json').write_text(json.dumps({'matches': matches}))
            for row in matches:
                d = fixtures/'t1-trainval'/row['episode']; d.mkdir(parents=True)
                (d/'setup.json').write_text(json.dumps({'entry': {'split': 'train', 'start_tick': 5}}))
                (d/'events.jsonl').write_text('\n'.join(json.dumps(x) for x in [
                    {'accepted': True, 'exec_tick': 8, 'kind': 'play'},
                    {'accepted': True, 'exec_tick': 11, 'kind': 'play'},
                    {'accepted': True, 'exec_tick': 7, 'kind': 'champion ability'},
                    {'accepted': False, 'exec_tick': 7, 'kind': 'play'}]))
                with gzip.open(d/'objects.jsonl.gz', 'wt') as f: f.write('{"tick":10}\n')
                (d/'evaluation-only.jsonl.gz').write_bytes(b'only existence checked by expectation validator')
            got = C.fixture_expectations(fixtures)
            self.assertEqual(len(got), 577)
            self.assertEqual(got['e0'], dict(ticks=5, plays=1, split='train'))
            roots = p/'roots'; roots.mkdir(); config = b'{}'; h = C.sha(config)
            (roots/f'config-{h[:16]}.json').write_bytes(config)
            rows = [dict(index=i, tick=i, seat=i%2, config=h) for i in range(303)]
            with gzip.open(roots/'roots-0.jsonl.gz', 'wt') as f:
                f.write('\n'.join(map(json.dumps, rows)))
            actual, sample = C.root_expectations(roots)
            self.assertEqual(actual, rows)
            self.assertEqual(sample, sorted(random.Random(20261015).sample(range(303), 300)))
            (roots/f'config-{h[:16]}.json').write_bytes(b'{"changed":1}')
            with self.assertRaises(ValueError): C.root_expectations(roots)

    def test_reproduce_interrupted_wait_loses_already_reaped_exit_receipt(self):
        ns = fs_scope(); events = []
        class Fake:
            def __init__(self, pid, interrupt=False): self.pid, self.interrupt = pid, interrupt
            def wait(self, timeout=None):
                events.append(['wait', self.pid, timeout])
                if self.interrupt:
                    self.interrupt = False
                    raise InterruptedError('synthetic SIGTERM while waiting for second child')
                return 0
        with tempfile.TemporaryDirectory(dir=HERE) as tmp:
            out = Path(tmp); out.chmod(0o700)
            children = ns['Children'](out)
            children.live = {'fixtures-pinned': (Fake(101), ['inert'], 'start'),
                             'fixtures-total': (Fake(102, True), ['inert'], 'start')}
            with self.assertRaises(InterruptedError):
                children.wait('fixtures', ['fixtures-pinned', 'fixtures-total'])
            ns['write_json'] = fs_scope()['write_json']
            ns['os'] = SimpleNamespace(killpg=lambda pid, sig: events.append(['killpg', pid, sig]))
            ns['signal'] = signal
            children.stop()
            rows = json.loads((out/'all-child-exits.json').read_text())
            # These assertions prove the defect, not correct behavior.
            self.assertEqual([r['label'] for r in rows], ['fixtures-total'])
            self.assertEqual(children.rows, rows)
            self.assertFalse((out/'fixtures-exits.json').exists())
            with (HERE/'interrupted-wait-reproduction-rerun.json').open('x') as f:
                json.dump(dict(events=events, actual_all_child_exits=rows,
                    expected_labels=['fixtures-pinned', 'fixtures-total'],
                    missing_label='fixtures-pinned', phase_receipt_exists=False,
                    scope='AST-extracted Children with fake waits/killpg only; no processes started'), f, indent=2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
