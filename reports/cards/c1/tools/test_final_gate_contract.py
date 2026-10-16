"""Local serial synthetic verifier checks. No gate, engine, native or remote execution.

Only pure validators and AST-extracted filesystem/wait functions are executed. Children are fakes.
"""
import ast
import copy
import hashlib
import importlib.util
import json
import os
import stat
import subprocess
from pathlib import Path
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('contract', TOOLS / 'final_gate_contract.py')
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
tree = ast.parse((TOOLS / 'final_gate.py').read_text())
scope = dict(C=C, os=os, Path=Path, json=json, stat=stat, hashlib=hashlib)
selected = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
            and n.name in ('directory', 'new_file', 'write_json', 'check_original', 'Children', 'archive_files')]
exec(compile(ast.Module(body=selected, type_ignores=[]), '<extracted pure driver helpers>', 'exec'), scope)
scope['utc'] = lambda: '2026-10-16T00:00:00Z'
H = 'a' * 64


class ContractTests(unittest.TestCase):
    def reject(self, f, *args):
        with self.assertRaises((ValueError, KeyError, TypeError, FileNotFoundError, OSError)):
            f(*args)

    def test_F1_complete_output_then_failure_or_signal(self):
        for code in (17, -9):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as d:
                out = Path(d); out.chmod(0o700)
                waited = []
                class Fake:
                    def __init__(self, pid, status): self.pid, self.status = pid, status
                    def wait(self): waited.append(self.pid); return self.status
                children = scope['Children'](out)
                children.live = {'fixtures-pinned': (Fake(101, code), ['flushed-all-records'], 'start'),
                                 'fixtures-total': (Fake(102, 0), ['flushed-all-records'], 'start')}
                self.reject(children.wait, 'fixtures', list(children.live))
                self.assertEqual(waited, [101, 102])
                rows = json.loads((out / 'fixtures-exits.json').read_text())
                self.assertEqual([x['exit_code'] for x in rows], [code, 0])
                self.assertFalse(children.live)

    def test_F1_root_and_comparator_exit_inventory(self):
        rows = [dict(label='r' + str(i), pid=100 + i, exit_code=0) for i in range(8)]
        labels = [r['label'] for r in rows]
        C.statuses_ok(rows, labels)
        self.reject(C.statuses_ok, rows[:-1], labels)
        rows[7]['exit_code'] = 17
        self.reject(C.statuses_ok, rows, labels)
        self.reject(C.statuses_ok, [dict(label='compare', pid=1, exit_code=-15)], ['compare'])

    def test_F2_manifest_paths_before_reads(self):
        for name in ('/tmp/outside', '../outside', 'engine/../outside', 'engine//a', '.', 'engine/./a',
                     'engine/a\n', 'engine/a\x00', 'engine\\a'):
            self.reject(C.relative, name)
        self.reject(C.decode, b'{"engine":{},"engine":{}}')
        C.relative('engine/src/lib.rs')

    def test_F2_full_manifest_missing_extra_control(self):
        m = {k: dict(kind='dir', mode=0o500) for k in C.ROLES}
        C.validate_manifest(m, copy.deepcopy(m))
        self.reject(C.validate_manifest, {'unrelated': dict(kind='file', mode=0o400, size=0, sha256=H)}, {})
        changed = copy.deepcopy(m); changed['output'] = dict(kind='dir', mode=0o500)
        self.reject(C.validate_manifest, changed, changed)
        observed = copy.deepcopy(m); observed['engine/new.py'] = dict(kind='file', mode=0o400, size=0, sha256=H)
        self.reject(C.validate_manifest, m, observed)
        self.reject(C.validate_manifest, m, {})

    def test_F2_authenticated_Git_archive_and_blob_identity(self):
        commit_data, blob = b'commit bytes', b'integrated engine bytes'
        def oid(kind, data):
            return hashlib.sha1(kind + b' ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        commit, blob_id = oid(b'commit', commit_data), oid(b'blob', blob)
        data = dict(commit=commit_data, blob=blob)
        def fake_git(repo, *args):
            if args[:2] == ('cat-file','commit'): return data['commit']
            if args[0] == 'ls-tree':
                self.assertEqual(args, ('ls-tree','-r','-z',commit,'--','engine-cards') if '--' in args
                                 else ('ls-tree','-r','-z',commit))
                return ('100644 blob ' + blob_id + '\tengine-cards/src/lib.rs\0').encode()
            if args[:2] == ('cat-file','blob'): return data['blob']
            raise ValueError('unexpected Git command')
        scope['git'] = fake_git
        f = scope['archive_files']
        self.assertEqual(f(Path('/unused'), commit, 'engine-cards'), {'src/lib.rs': C.sha(blob)})
        self.assertEqual(f(Path('/unused'), commit), {'engine-cards/src/lib.rs': C.sha(blob)})
        data['commit'] = b'different commit'; self.reject(f, Path('/unused'), commit, 'engine-cards')
        data['commit'] = commit_data; data['blob'] = b'different blob'
        self.reject(f, Path('/unused'), commit, 'engine-cards')
        del scope['git']

    def evidence(self):
        m = {'engine/source': dict(kind='file', sha256=H), 'python/lib': dict(kind='file', sha256=H)}
        ready = dict(schema=2, integrated_commit='1'*40, b2_accepted_commit='2'*40, tools_commit='3'*40,
                     native_sha256=H)
        code = {f: H for f in C.TOOL_FILES}
        receipts = {k: dict(kind=k, authority='owning lead', evidence_id='review/raw/run-id')
                    for k in ('b2', 'integration', 'build', 'tests', 'launcher_review', 'platform')}
        for role, rec in receipts.items():
            path = 'evidence/raw/' + role + '.txt'; m[path] = dict(kind='file', sha256=H)
            rec['raw_evidence'] = {path: H}
        receipts['b2'].update(verdict='ACCEPTED', commit='2'*40, required_integration_cases=['b2-case'])
        engine_hash = C.sha(json.dumps(C.content_map(m, 'engine'), sort_keys=True).encode())
        for role in ('integration', 'build', 'tests'):
            receipts[role].update(source_commit='1'*40, native_sha256=H, engine_inventory_sha256=engine_hash,
                                  verdict='PASS', exit_code=0)
        required = {g: [g + str(i) for i in range(n)] for g, n in C.GROUPS.items()}
        required['b2-integration'] = ['b2-case']
        receipts['integration'].update(b2_commit='2'*40, required_tests=required)
        receipts['build'].update(command=['cargo', '-j8'], pid=123, pgid=123,
                                  started_utc='2026-10-16T00:00:00Z', ended_utc='2026-10-16T00:01:00Z')
        receipts['launcher_review'].update(verdict='APPROVE', reviewed_commit='3'*40, code_hashes=code)
        groups = {}
        for group, names in required.items():
            groups[group] = []
            for case in names:
                artifact = 'evidence/raw/' + case + '.json'
                m[artifact] = dict(kind='file', sha256=H)
                groups[group].append(dict(case=case, verdict='PASS', exit_code=0, artifact=artifact, artifact_sha256=H))
        receipts['tests']['groups'] = groups
        receipts['platform'].update(python_version='3.12.12', python_inventory_sha256=C.sha(
            json.dumps(C.content_map(m, 'python'), sort_keys=True).encode()))
        return ready, receipts, m, code

    def test_F2_typed_source_build_test_review_bindings(self):
        args = self.evidence(); C.check_receipts(*args)
        changes = [('b2', 'verdict', 'REJECT'), ('b2', 'commit', '4'*40),
                   ('integration', 'source_commit', '4'*40), ('build', 'native_sha256', 'b'*64),
                   ('build', 'exit_code', 17), ('tests', 'engine_inventory_sha256', 'b'*64),
                   ('launcher_review', 'reviewed_commit', '4'*40), ('launcher_review', 'verdict', 'REJECT'),
                   ('platform', 'python_inventory_sha256', 'b'*64)]
        for role, field, value in changes:
            with self.subTest(role=role, field=field):
                a = copy.deepcopy(args); a[1][role][field] = value
                self.reject(C.check_receipts, *a)
        a = copy.deepcopy(args); del a[1]['build']; self.reject(C.check_receipts, *a)
        a = copy.deepcopy(args); a[1]['tests']['groups']['review-r2'][0]['case'] = 'invented'
        self.reject(C.check_receipts, *a)
        a = copy.deepcopy(args); del a[2]['evidence/raw/review-r20.json']
        self.reject(C.check_receipts, *a)

    def test_F3_symlink_hardlink_extra_input_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); (p/'outside').write_text('KEEP')
            root = p/'inputs'; root.mkdir(); (root/'engine').symlink_to(p, target_is_directory=True)
            self.reject(C.inventory, root, False)
            (root/'engine').unlink(); os.link(p/'outside', root/'hard')
            self.reject(C.inventory, root, False)
            (root/'hard').unlink(); (root/'dangling').symlink_to(p/'missing')
            self.reject(C.inventory, root, False)

    def test_F3_exclusive_output_never_truncates_external_or_stale_PASS(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d); out.chmod(0o700); outside = out/'sentinel'; outside.write_text('KEEP')
            (out/'gate.log').symlink_to(outside)
            self.reject(scope['new_file'], out, 'gate.log')
            (out/'PASS.json').write_text('old PASS')
            self.reject(scope['write_json'], out, 'PASS.json', dict(verdict='PASS'))
            self.assertEqual(outside.read_text(), 'KEEP')
            (out/'dangling').symlink_to(out/'absent')
            self.reject(scope['new_file'], out, 'dangling')

    def test_F4_original_control_replacement_cannot_rebaseline(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d); root = run/'inputs'; root.mkdir()
            for role in C.ROLES: (root/role).mkdir(mode=0o500)
            m = C.inventory(root); initial = {'ready.json': b'{"schema":2}',
                                             'manifest.json': json.dumps(m).encode()}
            for k, v in initial.items(): (run/k).write_bytes(v)
            scope['check_original'](run, initial)
            (run/'ready.json').write_text('{"schema":3}')
            self.reject(scope['check_original'], run, initial)
            (run/'ready.json').write_bytes(initial['ready.json'])
            (root/'tools').chmod(0o700); (root/'tools'/'changed').write_text('new tool')
            self.reject(scope['check_original'], run, initial)

    def test_F5_clean_environment_and_isolated_worker(self):
        env = next(n for n in tree.body if isinstance(n, ast.Assign) and
                   any(isinstance(t, ast.Name) and t.id == 'MIN_ENV' for t in n.targets))
        g = {}; exec(compile(ast.Module(body=[env], type_ignores=[]), '<literal environment>', 'exec'), g)
        self.assertFalse(set(g['MIN_ENV']) & {'BASH_ENV', 'CLASHER_BOT_RUNTIME_PINS', 'CLASHER_EVAL_RUNTIME_ROOT',
                                            'PYTHONPATH', 'PYTHONHOME', 'PYTHONOPTIMIZE', 'LD_PRELOAD'})
        worker = (TOOLS/'gate_worker.py').read_text()
        self.assertIn("CLASHER_BOT_RUNTIME_PINS='r1'", worker)
        self.assertIn("pop('CLASHER_EVAL_RUNTIME_ROOT', None)", worker)
        self.assertIn('sys.base_prefix', worker)
        shell = (TOOLS/'final_gate.sh').read_text()
        self.assertTrue(shell.startswith('#!/bin/bash -p'))
        self.assertIn('/usr/bin/env -i', shell)

    def test_R2_CPU_identity_and_worker_historical_hash_seed(self):
        plan = (TOOLS.parent/'FINAL-GATE-PLAN.md').read_text()
        launch = plan.split('setsid /usr/bin/env -i ', 1)[1].split('```', 1)[0]
        self.assertIn('USER="$(/usr/bin/id -un)"', launch)
        self.assertNotIn('BASH_ENV=', launch)
        # Only a stdlib flag probe, never a worker, engine, native or host script invocation.
        env = dict(PATH='/usr/bin:/bin', PYTHONHASHSEED='0')
        cmd = ['/mpac/sdicks02/repos/clasher-bot/.venv/bin/python','-P','-s','-S','-B','-c',
               'import sys; print(sys.flags.hash_randomization, sys.flags.safe_path, sys.flags.no_site, sys.flags.no_user_site)']
        p = subprocess.run(cmd, env=env, capture_output=True, text=True)
        self.assertEqual((p.returncode,p.stdout.strip()), (0,'0 True 1 1'))
        source = (TOOLS/'final_gate.py').read_text()
        self.assertIn("'-P', '-s', '-S', '-B'", source)
        self.assertIn('sys.flags.hash_randomization', (TOOLS/'gate_worker.py').read_text())

    def fixture_rows(self):
        expected = {f'episode{i}': dict(ticks=10, plays=2, split='train') for i in range(577)}
        rows = [dict(episode=k, rs=dict(episode=k, split='train', start_match=False, action_mismatch=[],
                first_mismatch=dict(tick=1, rel=1, entities=[], n_entities_diff=0), ticks=1, fixture_ticks=10),
                rust_only=dict(ticks=10, chain=H, final=H, accepted=1, plays=2, action_results=[True, False]))
                for k in expected]
        return rows, expected

    def test_F6_fixtures_positive_residuals_and_negative_controls(self):
        rows, expected = self.fixture_rows(); C.audit_fixtures(rows, expected)
        for mutate in (lambda r: r[0].update(episode='fake'), lambda r: r[0].update(rust_only={}),
                       lambda r: r[0]['rust_only'].update(chain='bad'),
                       lambda r: r[0]['rust_only'].update(ticks=9),
                       lambda r: r[0]['rust_only'].update(action_results=[]),
                       lambda r: r[0]['rs'].update(fixture_ticks=9),
                       lambda r: r[0]['rs'].update(action_mismatch=[[]]),
                       lambda r: r[0]['rs'].update(first_mismatch={})):
            changed = copy.deepcopy(rows); mutate(changed); self.reject(C.audit_fixtures, changed, expected)

    def root_rows(self):
        roots = [dict(index=7, tick=i, seat=i%2) for i in range(300)]
        sample = list(range(300))
        header = dict(native='/frozen/native/clasher_core.abi3.so', native_sha256=H, roots_total=300,
                      sampled=300, args=C.ARGS, runtime_root='/frozen/rt', runtime_pins='r1')
        rows = [dict(k=i, **roots[i], variant=v, digest=H, legal_actions=[], actions=[2304, 2401],
                     rollout_e1=['0x0.0p+0']*6, evaluate='0x0.0p+0', parts=['0x0.0p+0']*7,
                     view=[H,H], mask=[H,H], select=[[2304,H]]*3, step=[[H,H]]*3, root_snapshot=H)
                for i in sample[0::4] for v in ('full','cut')]
        return [header, rows, roots, sample, 0, header['native'], H, '/frozen/rt']

    def test_F6_root_sample_schema_headers_and_checks(self):
        args = self.root_rows(); C.audit_root_shard(*args)
        for field, value in [('roots_total',0), ('sampled',0), ('args',{}), ('native','/wrong'),
                             ('native_sha256','b'*64), ('runtime_root','/other'), ('runtime_pins','live16402')]:
            a = copy.deepcopy(args); a[0][field] = value; self.reject(C.audit_root_shard, *a)
        for field, value in [('k',10000), ('variant','other'), ('rollout_e1',[]), ('select',[]), ('step',[]),
                             ('parts',[]), ('digest',{}), ('actions',[]), ('tick',9000), ('root_snapshot','bad')]:
            a = copy.deepcopy(args); a[1][0][field] = value; self.reject(C.audit_root_shard, *a)
        a = copy.deepcopy(args); a[1][1] = a[1][0]; self.reject(C.audit_root_shard, *a)
        a = copy.deepcopy(args); del a[1][0]['view']; self.reject(C.audit_root_shard, *a)


if __name__ == '__main__':
    unittest.main(verbosity=2)
