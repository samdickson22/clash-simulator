"""Local stdlib-only fixture evidence controls. Never imports an engine or touches a host."""
import ast
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
preflight = ast.parse((HERE/'probe_fixture_preflight_v1.py').read_text())
natural = ast.parse((HERE/'probe_dash_natural_v1.py').read_text())
def literal(name):
    return ast.literal_eval(next(n.value for n in preflight.body if isinstance(n,ast.Assign)
                                  and any(isinstance(t,ast.Name) and t.id==name for t in n.targets)))
cases = ast.literal_eval(next(n.value for n in preflight.body if isinstance(n,ast.Assign)
                              and any(isinstance(t,ast.Name) and t.id=='CASES' for t in n.targets)))
ns = dict(json=json, copy=copy, CASES=cases, LEGACY=literal('LEGACY'), LEGACY_VALUES=literal('LEGACY_VALUES'), VERSION='b2-semantic-snapshot-v1',
          natural=SimpleNamespace(FIXTURE='b2-natural-dash-fixture-v1'))
functions = [n for n in preflight.body if isinstance(n,ast.FunctionDef)
             and n.name in ('observe_legacy_fixture','check_collection','check_results')]
exec(compile(ast.Module(body=functions,type_ignores=[]),'preflight-stdlib-functions','exec'),ns)


def evidence():
    roots=[]
    for name,lead,tick,field in ns['LEGACY']:
        for seat in (0,1):
            state=dict(entities=[dict(id=7,stun=.5,frozen_moving=True,route=[[21,23]],dash=dict(phase='travel'))])
            roots.append(dict(case=name,lead=lead,seat=seat,initial_root=dict(python=state,native={'tick':1}),
                              result=dict(first=tick,field=field,cast=dict(python=True,native=True,before_export=False)),
                              first_context=dict(relative_tick=tick,before=dict(python=state,native=state),
                                                 after=dict(python=state,native=state),
                                                 differences=[dict(field=field,python=ns['LEGACY_VALUES'][name][0],
                                                                   native=ns['LEGACY_VALUES'][name][1])])) )
    rows = [dict(case=case,lead=lead,seat=seat,contract=ns['VERSION'],fixture=ns['natural'].FIXTURE,
                 first=None,differences=[],digest_diverged=False,compared_ticks=45,initial_root=dict(python={'tick':1},native={'tick':1}),
                 fresh_troop_templates=['config.cards.Knight'],applicability=[{'raw':'retained'}],
                 cast=dict(python=True,native=True,before_export=False),reference_launch_tick=39,
                 reference_launch=dict(before=dict(charging=True,stunned=False,target_edge_distance=5.8)))
            for case,lead in cases for seat in (0,1)]
    return roots,rows


class FixtureEvidenceTests(unittest.TestCase):
    def test_optimization_fails_before_engine_import_or_host_side_effect(self):
        for name in ('probe_dash_natural_v1.py','probe_fixture_preflight_v1.py','stage_fixture_preflight_v1.py'):
            tree=ast.parse((HERE/name).read_text())
            guard=next(n for n in tree.body if isinstance(n,ast.If) and '__debug__' in ast.dump(n.test))
            code=ast.Module(body=[guard],type_ignores=[])
            with self.assertRaises(SystemExit,msg=name):exec(compile(code,name,'exec',optimize=1),{'sys':SimpleNamespace(flags=SimpleNamespace(optimize=1))})

    def test_observes_old_calls_without_extra_steps_and_restores_on_error(self):
        steps=[]
        class Battle:
            def __init__(self): self.tick=0
            def step(self): steps.append('python'); self.tick+=1
        class Native:
            def __init__(self,raw): self.tick=json.loads(raw)['tick']
            def snapshot(self): return json.dumps(dict(tick=self.tick))
            def digest(self): return self.tick
            def step(self,n): steps.append('native'); self.tick+=n
        module=SimpleNamespace(clasher_core=SimpleNamespace(BattleState=Native),initial=lambda:Battle(),
                               full_compare=lambda b,n,c:([dict(field='facing')],[],[]),
                               battle_digest=lambda b:b.tick,probe_snapshot=lambda b,c:json.dumps(dict(tick=b.tick)))
        original_initial,original_compare=module.initial,module.full_compare
        instances=[]
        def callback():
            b=module.initial(); instances.append(b)
            n=module.clasher_core.BattleState(module.probe_snapshot(b,{}))
            b.step(); n.step(1); module.full_compare(b,n,{})
            return dict(first=0)
        observed=ns['observe_legacy_fixture'](module,callback,{})
        self.assertEqual(steps,['python','native'])
        self.assertEqual(observed['initial_root']['python']['tick'],0)
        self.assertEqual(observed['first_context']['before']['python']['tick'],0)
        self.assertEqual(observed['first_context']['before']['native']['tick'],0)
        self.assertEqual(observed['first_context']['after']['python']['tick'],1)
        self.assertEqual(observed['first_context']['after']['native']['tick'],1)
        self.assertIs(module.clasher_core.BattleState,Native)
        self.assertIs(module.initial,original_initial); self.assertIs(module.full_compare,original_compare)
        self.assertIs(instances[0].step.__func__,Battle.step)
        def fail(): raise RuntimeError('setup failed')
        with self.assertRaises(RuntimeError): ns['observe_legacy_fixture'](module,fail,{})
        self.assertIs(module.clasher_core.BattleState,Native)
        self.assertIs(module.initial,original_initial); self.assertIs(module.full_compare,original_compare)
        with self.assertRaises(AssertionError): ns['observe_legacy_fixture'](module,lambda:None,{})

    def test_exact_fixture_counts_and_mechanical_failures_are_rejected(self):
        roots,rows=evidence(); ns['check_results'](roots,rows)
        for mutation in ('missing','duplicate','history','digest','short','cast','error','stunned_launch','no_band'):
            rr,ss=copy.deepcopy(roots),copy.deepcopy(rows); row=ss[0]
            if mutation=='missing': ss.pop()
            elif mutation=='duplicate': ss[-1]=copy.deepcopy(ss[0])
            elif mutation=='history': row.update(first=0,differences=[dict(field='state.entities.7.route')])
            elif mutation=='digest': row['digest_diverged']=True
            elif mutation=='short': row['compared_ticks']=44
            elif mutation=='cast': row['cast']['native']=False
            elif mutation=='error': row['error']='collector failed'
            elif mutation=='stunned_launch': row['reference_launch']['before']['stunned']=True
            else: row['reference_launch']['before']['target_edge_distance']=None
            with self.assertRaises(AssertionError,msg=mutation): ns['check_results'](rr,ss)

    def test_synthetic_reachability_inference_requires_actual_root_fields(self):
        for mutation in ('stun','frozen','route','phase'):
            roots,rows=evidence(); row=roots[0]['initial_root']['python']['entities'][0]
            if mutation=='stun': row['stun']=0
            elif mutation=='frozen': row['frozen_moving']=False
            elif mutation=='route': row['route']=[]
            else: row['dash']['phase']='idle'
            with self.assertRaises(AssertionError,msg=mutation): ns['check_results'](roots,rows)

    def test_exact_old_blue_roots_ticks_and_values_required(self):
        for mutation in ('missing_context','wrong_tick','wrong_field','wrong_value','missing_pre','missing_post'):
            roots,rows=evidence(); row=roots[2]
            if mutation=='missing_context': row['first_context']=None
            elif mutation=='wrong_tick': row['first_context']['relative_tick']=13
            elif mutation=='wrong_field': row['result']['field']='state.entities.8.target'
            elif mutation=='wrong_value': row['first_context']['differences'][0]['native']=1
            elif mutation=='missing_pre': row['first_context']['before']['native']={}
            else: row['first_context']['after']['python']={}
            with self.assertRaises((AssertionError,TypeError),msg=mutation): ns['check_collection'](roots,rows)

    def test_complete_collection_retains_natural_mechanical_failure(self):
        roots,rows=evidence()
        rows[0].update(first=0,differences=[dict(field='state.entities.7.facing[1]',python=750,native=1250)])
        ns['check_collection'](roots,rows)
        with self.assertRaises(AssertionError): ns['check_results'](roots,rows)

    def test_natural_driver_cannot_force_launch_or_erase_history(self):
        calls={n.func.attr for n in ast.walk(natural) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertFalse(calls & {'_launch_dash','_start_charge','_update_charge','_cancel_charge'})
        targets=[]
        for node in ast.walk(natural):
            if isinstance(node,(ast.Assign,ast.AnnAssign,ast.AugAssign)):
                targets += node.targets if isinstance(node,ast.Assign) else [node.target]
        forbidden={'position','stun_timer','_native_ground_route_cells','_ground_path_cache_key',
                   '_native_moving_when_frozen','_bandit_charging','_bandit_dashing','_bandit_dash_timer'}
        self.assertFalse({n.attr for t in targets for n in ast.walk(t) if isinstance(n,ast.Attribute)} & forbidden)
        self.assertEqual(len(cases),8)


if __name__=='__main__': unittest.main()
