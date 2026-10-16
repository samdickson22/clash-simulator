"""Stdlib-only fail-closed affected-check and exact source mutation controls."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import validate_rage_fix_v1 as validator
from test_r2_harness import semantic_sweep

HERE=Path(__file__).resolve().parent
WORKTREE=HERE.parents[3]


def records():
    new=[]
    for name in (name for group in validator.GROUPS for name in group):
        rows=semantic_sweep(mutation=name!='rage')
        for row in rows:row['case']=name
        new.extend(rows)
    return new,copy.deepcopy(new)


class RageEvidenceTests(unittest.TestCase):
    def test_resigned_historical_references_cannot_replace_pinned_identity(self):
        outer=ast.parse((HERE/'stage_rage_fix_v1.py').read_text())
        remote=next(ast.literal_eval(n.value) for n in outer.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='REMOTE' for t in n.targets))
        tree=ast.parse(remote)
        pin=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CAPTURE_IDENTITY_SHA256' for t in n.targets))
        self.assertEqual(pin,'3995110721b39f0b5c3c705299f533db4ed60383022d853ca98b0b0a548737d5')
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='validate_capture_reference')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);old=root/'old';capture=root/'capture'
            (old/'fid').mkdir(parents=True);(capture/'fid').mkdir(parents=True)
            source=old/'source-and-tools.json';source.write_text('{"engine_files":{}}')
            refs=[old/'fid'/('semv1-20261016T1052Z-semantic-'+str(i)+'.json') for i in range(1,5)]
            for path in refs:path.write_text('[]')
            def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
            identity=capture/'identity.json'
            def resign():
                identity.write_text(json.dumps(dict(inputs={str(path):digest(path) for path in [source]+refs})))
                (capture/'terminal.json').write_text(json.dumps(dict(status='CAPTURE_COMPLETE',exit_code=0,changed_inputs=[],output_sha256='b0ecd196b9cd70a03fa358412c2c4fc8e195dd3960d9bae8689db23574d07358',identity_sha256=digest(identity))))
            resign();fixture_pin=digest(identity)
            def sha(path):
                if path==capture/'fid/fixtures.json':return 'b0ecd196b9cd70a03fa358412c2c4fc8e195dd3960d9bae8689db23574d07358'
                return digest(path)
            namespace=dict(json=json,Path=Path,sha=sha,CAPTURE_IDENTITY_SHA256=fixture_pin)
            exec(compile(ast.Module(body=[function],type_ignores=[]),'reference-control','exec'),namespace)
            check=namespace['validate_capture_reference'];check(capture,old)
            refs[0].write_text('[{"replacement":true}]')
            with self.assertRaises(AssertionError):check(capture,old)
            resign()
            with self.assertRaises(AssertionError):check(capture,old)

    def test_mirror_requires_both_casts_full_duration_expiry_and_no_private_difference(self):
        template=semantic_sweep()[0]['rows'][0]
        rows=[dict(contract=template['contract'],case='rage_mirror',seat=seat,ticks=140,expired=True,
                   first=None,differences=[],fresh_troop_templates=template['fresh_troop_templates'],
                   applicability=copy.deepcopy(template['applicability']),
                   actions=[[0,seat,'Rage',True,True],[4,seat,'Mirror',True,True]]) for seat in (0,1)]
        validator.check_mirror(rows)
        for mutation in ('missing','rejected_mirror','not_expired','short','private_difference'):
            bad=copy.deepcopy(rows)
            if mutation=='missing':bad.pop()
            elif mutation=='rejected_mirror':bad[0]['actions'][1][-1]=False
            elif mutation=='not_expired':bad[0]['expired']=False
            elif mutation=='short':bad[0]['ticks']=139
            else:bad[0]['differences']=[dict(field='scope.child.spell_name')]
            with self.assertRaises(AssertionError,msg=mutation):validator.check_mirror(bad)

    def test_impact_requires_both_seats_all_offsets_and_actual_denied_queries(self):
        template=semantic_sweep()[0]['rows'][0]
        rows=[]
        for lead in (6,8,9,10):
            for seat in (0,1):
                row=copy.deepcopy(template);row.update(lead=lead,seat=seat)
                row['gate_queries']=[dict(source='RageDamage',allowed=False)]
                rows.append(row)
        validator.check_impact(rows)
        for mutation in ('missing','duplicate','no_denial','private_difference','short'):
            bad=copy.deepcopy(rows)
            if mutation=='missing':bad.pop()
            elif mutation=='duplicate':bad[-1]=copy.deepcopy(bad[0])
            elif mutation=='no_denial':
                for row in bad:
                    if row['seat']==1:row['gate_queries'][0]['allowed']=True
            elif mutation=='private_difference':bad[0]['differences']=[dict(field='hit_ids')]
            else:bad[0]['compared_ticks']=44
            with self.assertRaises(AssertionError,msg=mutation):validator.check_impact(bad)

    def test_intended_mutations_remove_one_guard_and_reject_missing_or_duplicate_match(self):
        for arm,path,token in [('mutA','src/c56.rs','!e.dash_travel()'),('mutB','src/lib.rs','target.dash_travel()')]:
            source=(WORKTREE/'engine-cards'/path).read_text()
            changed=validator.mutation(source,arm)
            self.assertEqual(source.count(token)-changed.count(token),1)
            self.assertEqual(len(source.splitlines())-len(changed.splitlines()),1)
            with self.assertRaises(AssertionError):validator.mutation(changed,arm)
            with self.assertRaises(AssertionError):validator.mutation(source+source,arm)

    def test_retained_failures_do_not_become_a_semantic_pass(self):
        new,old=records()
        self.assertEqual(validator.check_baselines(new,old),14)
        self.assertTrue(any(row['mismatches'] for row in new))

    def test_missing_duplicate_changed_guard_rows_and_bad_rage_rejected(self):
        for mutation in ('missing','duplicate','guard_delta','zero_query','bad_rage','short_rage'):
            new,old=records()
            if mutation=='missing':new.pop()
            elif mutation=='duplicate':new[-1]=copy.deepcopy(new[0])
            elif mutation=='guard_delta':new[-1]['rows'][0]['differences'][0]['native']=[8]
            elif mutation=='zero_query':new[-1]['query_count']=0;old[-1]['query_count']=0
            elif mutation=='short_rage':new[0]['rows'].pop()
            else:new[0]['rows'][0]['first']=0;new[0]['mismatches']=1
            with self.assertRaises(AssertionError,msg=mutation):validator.check_baselines(new,old)

    def test_optimized_entrypoints_reject_before_side_effects(self):
        for name in ('stage_rage_fix_v1.py','validate_rage_fix_v1.py','probe_rage_impact_v1.py'):
            tree=ast.parse((HERE/name).read_text())
            guard=next(n for n in tree.body if isinstance(n,ast.If) and '__debug__' in ast.dump(n.test))
            with self.assertRaises(SystemExit):exec(compile(ast.Module(body=[guard],type_ignores=[]),name,'exec',optimize=1),{'sys':__import__('sys')})


if __name__=='__main__':unittest.main()
