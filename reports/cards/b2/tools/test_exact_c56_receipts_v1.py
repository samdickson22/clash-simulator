"""Local stdlib-only exact C56 denominator and equality negative controls."""
import copy
import ast
import io
import tempfile
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('c56_receipts',Path(__file__).with_name('exact_c56_receipts_v1.py'))
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)


def evidence():
    episodes=[str(index) for index in range(577)]
    fixtures=[dict(episode=e,rs=dict(episode=e,split='train',start_match=True,first_mismatch=None if int(e)<429 else {'tick':1},action_mismatch=[]),
                   rust_only=dict(chain='a'*64,final='b'*64,ticks=100,accepted=2,plays=3)) for e in episodes]
    source=[dict(index=i%12,tick=100+i,seat=i%2) for i in range(1043)]
    rows=[dict(k=i,variant=v,index=source[i]['index'],tick=source[i]['tick'],seat=source[i]['seat'],
               select=[[2304,'7']]*3,step=[['7','c'*64]]*3,view=['v']*2,mask=['m']*2,
               actions=[2304,2401,3],rollout_e1=['0x0.0p+0']*9,root_snapshot='d'*64,
               apply=['True','7','e'*64]) for i in range(300) for v in ('full','cut')]
    headers={arm:[dict(native_sha256=native,roots_total=1043,sampled=300,args=copy.deepcopy(gate.ARGS)) for _ in range(2)]
             for arm,native in [('pinned',gate.PIN),('total',gate.TOTAL)]}
    return dict(pinned=copy.deepcopy(fixtures),total=copy.deepcopy(fixtures)),dict(pinned=copy.deepcopy(rows),total=copy.deepcopy(rows)),headers,episodes,source,list(range(300))


class ExactGateTests(unittest.TestCase):
    def test_canonical_drift_rejected_and_nested_audit_hashes_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            job=Path(tmp);directory=job/'canonical';directory.mkdir()
            names=('parity_fixtures.py','parity_roots.py','compare.py')
            for name in names:(directory/name).write_text('original '+name)
            provenance=dict(gate_tools={name:gate.sha(directory/name) for name in names})
            gate.check_canonical(directory,provenance)
            (directory/names[0]).write_text('changed canonical source')
            with self.assertRaises(AssertionError):gate.check_canonical(directory,provenance)
            audit=job/'gate/audit-total';audit.mkdir(parents=True)
            path=audit/'worker-123.jsonl';path.write_text('native errors: zero')
            outputs=gate.output_hashes(job)
            self.assertIn('gate/audit-total/worker-123.jsonl',outputs)
            path.write_text('native errors: one')
            self.assertNotEqual(outputs,gate.output_hashes(job))
    def test_native_exception_observer_preserves_returns_and_exposes_caught_errors(self):
        spec=importlib.util.spec_from_file_location('observer',Path(__file__).with_name('observe_c56_fixtures_v1.py'))
        observer=importlib.util.module_from_spec(spec);spec.loader.exec_module(observer)
        observer.NATIVE_SHA=gate.TOTAL;observer.AUDIT=io.StringIO()
        calls=[]
        class Native:
            def snapshot(self):calls.append('snapshot');return 'state'
            def digest(self):calls.append('digest');return '7'
            def step(self):calls.append('step')
            def apply_action(self):calls.append('apply');raise ValueError('native action failed')
        def one(episode):
            proxy=observer.NativeProxy(observer.call_observed('constructor',Native))
            self.assertEqual(proxy.snapshot(),'state');self.assertEqual(proxy.digest(),'7');proxy.step()
            try:proxy.apply_action()
            except ValueError:pass # The canonical producer catches this; the audit must retain it.
            return {'canonical':'unchanged'}
        observer.ORIGINAL_ONE=one
        self.assertEqual(observer.observed_one('episode'),{'canonical':'unchanged'})
        self.assertEqual(calls,['snapshot','digest','step','apply'])
        record=__import__('json').loads(observer.AUDIT.getvalue())
        self.assertEqual(record['errors'][0]['method'],'apply_action')
        with self.assertRaises(AssertionError):gate.validate_audit([record],['episode'],gate.TOTAL)
        record['errors']=[];self.assertEqual(gate.validate_audit([record],['episode'],gate.TOTAL),1)

    def test_both_arms_wrong_arguments_and_repeated_logical_roots_fail(self):
        f,r,h,e,s,i=evidence()
        for arm in h:
            for header in h[arm]:header['args'].update(horizon=0,command_delay=0,opponent_delay=0)
        with self.assertRaises(AssertionError):gate.validate_records(f,r,h,e,s,i)
        f,r,h,e,s,i=evidence();s[-1]=copy.deepcopy(s[0])
        with self.assertRaises(AssertionError):gate.validate_records(f,r,h,e,s,i)

    def test_optimized_modules_reject_before_side_effects(self):
        for name in ('stage_exact_c56_v1.py','exact_c56_receipts_v1.py','observe_c56_fixtures_v1.py'):
            tree=ast.parse(Path(__file__).with_name(name).read_text())
            guard=next(n for n in tree.body if isinstance(n,ast.If) and '__debug__' in ast.dump(n.test))
            with self.assertRaises(SystemExit,msg=name):exec(compile(ast.Module(body=[guard],type_ignores=[]),name,'exec',optimize=1),{'sys':__import__('sys')})
    def test_exact_complete_same_arms(self):
        result=gate.validate_records(*evidence())
        self.assertEqual(result['fixtures'],577);self.assertEqual(result['roots'],600)
        self.assertEqual(result['selections'],1800)

    def test_both_arms_same_missing_or_duplicate_still_fail(self):
        for category in ('fixture_missing','fixture_duplicate','root_missing','root_duplicate'):
            f,r,h,e,s,i=evidence()
            target=f if category.startswith('fixture') else r
            for arm in target:
                if category.endswith('missing'):target[arm].pop()
                else:target[arm][-1]=copy.deepcopy(target[arm][0])
            with self.assertRaises(AssertionError,msg=category):gate.validate_records(f,r,h,e,s,i)

    def test_changed_semantics_native_error_parity_or_header_fail(self):
        for mutation in ('chain','native_error','reference_count','header','sample_size','source_key','selection_count','rollout_count','args'):
            f,r,h,e,s,i=evidence()
            if mutation=='chain':f['total'][0]['rust_only']['chain']='f'*64
            elif mutation=='native_error':f['total'][0]['rust_only']['error']='panic'
            elif mutation=='reference_count':f['total'][0]['rs']['first_mismatch']={'tick':1}
            elif mutation=='header':h['total'][0]['native_sha256']=gate.PIN
            elif mutation=='sample_size':h['total'][0]['sampled']=299
            elif mutation=='source_key':r['total'][0]['tick']+=1
            elif mutation=='selection_count':r['total'][0]['select'].pop()
            elif mutation=='rollout_count':r['total'][0]['rollout_e1'].pop()
            else:h['total'][0]['args']['horizon']=41
            with self.assertRaises(AssertionError,msg=mutation):gate.validate_records(f,r,h,e,s,i)


if __name__=='__main__':unittest.main()
