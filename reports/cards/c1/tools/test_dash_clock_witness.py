"""Local source/AST witness controls only; no engine or native import."""
import ast
import argparse
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import traceback
from types import SimpleNamespace
from unittest.mock import patch

path=Path(__file__).with_name('probe_dash_clock.py')
namespace={}
tree=ast.parse(path.read_text())
for name in ('row','require_witness'):
    node=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name==name)
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),namespace)


def reject(result):
    try: namespace['require_witness'](result)
    except (AssertionError,TypeError,KeyError): return
    raise AssertionError('bad dash-clock witness accepted')


def sample(mode,seat):
    loaded=mode.startswith('loaded'); hit=mode not in ('miss','missing')
    equal=mode.endswith('equal'); zero=mode=='cold_zero'
    initial=dict(id=7,clock_initialized=loaded,clock_reseed=None,force_due=zero,
        cooldown=0 if zero else 1 if equal else 0.4,
        clock=dict(interval=1000,load=600,timeline=0,remaining=600 if equal else 0,finish=0),dash=dict(phase='travel'))
    after=copy.deepcopy(initial); after['dash']['phase']='idle'
    if hit:
        after['cooldown']=1
        if not loaded: after['clock']['remaining']=600; after['force_due']=False
        elif not equal: after['clock_reseed']=1000
    hp=None if mode=='missing' else 10
    frames=[]
    for offset in range(40):
        actor=copy.deepcopy(initial if offset<5 else after)
        if hit and offset>5: actor['clock_initialized']=True
        frames.append(dict(offset=offset,before=copy.deepcopy(initial if offset<=5 else after),
            python=copy.deepcopy(actor),native=copy.deepcopy(actor),target_before=hp,
            target_python=hp if not hit else 10 if offset<5 else 8 if offset==5 else 7,
            target_native=hp if not hit else 10 if offset<5 else 8 if offset==5 else 7))
    return dict(seat=seat,mode=mode,ticks=40,initial=dict(entities=[initial]),actor_id=7,
        differences=[],errors=[],frames=frames,dash_damage=2)


def run_case_controls():
    """Execute exact run_case wiring, with all engine operations replaced."""
    def exercise(fault=None,persist=False):
        calls=[]
        class Battle:
            def __init__(self,tick=0,kind='reference',bad=False):
                self.tick,self.kind,self.bad=tick,kind,bad
            def clone(self):
                calls.append(self.tick)
                if fault=='clone-construction' and self.tick==6: raise ValueError('injected clone construction')
                kind='initial_clone' if len(calls)==1 else 'pre_step_clone'
                bad=fault=='post-landing-clone' and self.tick==6 or fault=='initial-clone' and kind=='initial_clone'
                return Battle(self.tick,kind,bad)
            def step(self):
                self.tick+=1
                if fault=='step' and self.kind=='reference' and self.tick==4: raise ValueError('injected partial step')
            def state(self):
                if fault=='snapshot' and self.kind=='pre_step_clone' and self.tick==7: raise ValueError('injected snapshot')
                value=dict(tick=self.tick,entities=[dict(id=1,hp=100,stats=dict(dash=dict(damage=2)),
                    dash=dict(phase='travel' if self.tick<6 else 'idle'),clock=dict(remaining=0)),dict(id=2,hp=100)])
                if self.bad and self.tick>=3: value['entities'][0]['clock']['remaining']=77
                return value
        class Native:
            def __init__(self,encoded): self.tick=json.loads(encoded)['tick']; self.bad=False
            def snapshot(self):
                value=Battle(self.tick).state()
                if self.bad: value['entities'][0]['clock']['remaining']=88
                return json.dumps(value)
            def clone(self):
                if fault=='native-clone-construction' and self.tick==6: raise ValueError('injected native clone construction')
                arm=Native(self.snapshot()); arm.bad=fault=='native-clone' and self.tick==6
                return arm
            def step(self,ticks): self.tick+=ticks
        def templates(result,contract,label,state,offset):
            if fault=='template' and label=='python/pre_step_clone' and offset==6: raise ValueError('injected template')
        def compare(b,cfg,native,contract):
            if fault=='comparison' and b.tick==7: raise ValueError('injected comparison')
            delta=[] if json.loads(native.snapshot())==b.state() else [dict(field='test.clock')]
            return delta,[],delta,not delta
        fake_T=SimpleNamespace(snapshot=lambda b,cfg,contract:json.dumps(b.state()),
            validate_templates=templates,compare=compare)
        fake_D=SimpleNamespace(clasher_core=SimpleNamespace(BattleState=Native),
            battle_digest=lambda b:json.dumps(b.state(),sort_keys=True))
        ns=dict(json=json,traceback=traceback,T=fake_T,D=fake_D,KEYS=('id','hp','clock','dash'),
            row=namespace['row'],require_witness=lambda result:None)
        for name in ('capture_roots','run_case'):
            node=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name==name)
            exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),ns)
        result={}; error=None
        try: ns['run_case'](result,Battle(),{},(1,2),object())
        except (AssertionError,ValueError) as failure: error=str(failure)
        if persist:
            with tempfile.TemporaryDirectory(prefix='c1-dash-case-evidence-') as temp:
                directory=Path(temp); artifact=directory/'fake-native.txt'; artifact.write_text('not a native library')
                fake_D.clasher_core.__file__=str(artifact)
                fake_T.load_contract=lambda path:object()
                ns.update(argparse=argparse,Path=Path,hashlib=hashlib,sys=sys,
                    MODES=('cold_zero','cold_equal','loaded_changed','loaded_equal','miss','missing'),
                    fixture=lambda seat,mode:(Battle(),{},(1,2)))
                node=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='main')
                exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),ns)
                output=directory/'partial-cases.json'
                args=['probe',str(output),'--contract',str(directory/'fake-contract'),
                    '--native-sha256',hashlib.sha256(artifact.read_bytes()).hexdigest()]
                code=None
                with patch.object(sys,'argv',args),contextlib.redirect_stdout(io.StringIO()):
                    try: ns['main']()
                    except SystemExit as failure: code=failure.code
                saved=json.loads(output.read_text())
                assert code==1 and saved['status']=='FOCUSED_FAIL' and len(saved['results'])==12
                for failed in saved['results']:
                    context=failed['failure_context']
                    assert context['offset']==6 and failed['status']=='ERROR' and failed['error']
                    assert context['after']['python']['reference']['tick']==7
                    assert context['after']['python']['pre_step_clone']['entities'][0]['clock']['remaining']==77
                    assert context['after']['natives']['reload']['tick']==7
        return result,calls,error
    result,calls,error=exercise()
    assert error is None and calls==[0]+list(range(40)), calls
    assert result['clone_boundaries']==[dict(offset=i,tick=i) for i in range(40)]
    assert len(result['frames'])==40 and result['first_context'] is None
    for fault,offset,after_tick in (('post-landing-clone',6,7),('initial-clone',2,3),
            ('native-clone',6,7),('step',3,4),('snapshot',6,7),('template',6,7),
            ('comparison',6,7),('clone-construction',6,6),('native-clone-construction',6,6)):
        result,calls,error=exercise(fault)
        assert error is not None, fault
        context=result['failure_context']
        assert context['offset']==offset and result['first_context'] is context
        assert context['error'] and result['errors'] and len(result['frames'])==offset
        assert context['before']['python']['reference']['tick']==offset
        assert result['last_before']['python']['reference']['tick']==offset
        assert context['after']['python']['reference']['tick']==after_tick
        assert 'initial_clone' in context['after']['python'] and 'live' in context['after']['natives']
        if fault=='post-landing-clone':
            assert context['after']['python']['pre_step_clone']['entities'][0]['clock']['remaining']==77
            assert context['after']['natives']['reload']['tick']==after_tick
        if fault=='initial-clone':
            assert context['after']['python']['initial_clone']['entities'][0]['clock']['remaining']==77
        if fault=='native-clone':
            assert context['after']['natives']['clone']['entities'][0]['clock']['remaining']==88
        if fault=='step':
            assert context['completed_steps']==[] and context['after']['natives']['live']['tick']==offset
        if fault=='snapshot':
            assert 'unavailable_error' in context['after']['python']['pre_step_clone']
            assert context['root_capture_errors'] and context['after']['natives']['live']['tick']==after_tick
        # The case main can serialize exactly these partial results after it
        # catches the exception; no traceback-local recovery is needed.
        restored=json.loads(json.dumps(result))
        assert restored['failure_context']['offset']==offset
    exercise('post-landing-clone',persist=True)
    print('PASS: exact run_case AST clones Python at all40 pre-steps; post-landing/initial/native clone faults and step/snapshot/template/comparison/construction exceptions retain first-bad roots; exact main persists all12 failed cases with available arms/completed-step inventory')


def main():
    modes=('cold_zero','cold_equal','loaded_changed','loaded_equal','miss','missing')
    for seat in (0,1):
        for mode in modes:
            result=sample(mode,seat); namespace['require_witness'](result)
            for label in ('python','native'):
                bad=copy.deepcopy(result); bad['frames'][5][label]['clock_initialized']=not mode.startswith('loaded'); reject(bad)
                bad=copy.deepcopy(result); bad['frames'][5][label]['clock']['finish']=1; reject(bad)
                bad=copy.deepcopy(result); bad['frames'][5][label]['clock_reseed']=777; reject(bad)
                if mode.startswith('cold'):
                    # Exact old native failure and a stale force-due flag.
                    bad=copy.deepcopy(result); bad['frames'][5][label]['clock']['remaining']=0
                    bad['frames'][5][label]['clock_reseed']=1000; reject(bad)
                    bad=copy.deepcopy(result); bad['frames'][5][label]['force_due']=True; reject(bad)
                if mode in ('miss','missing'):
                    bad=copy.deepcopy(result); bad['frames'][5][label]['cooldown']=1; reject(bad)
            bad=copy.deepcopy(result); bad['frames']=bad['frames'][:-1]; reject(bad)
            bad=copy.deepcopy(result); bad['frames'][5]['python']['dash']['phase']='travel'; reject(bad)
            bad=copy.deepcopy(result); bad['errors']=[dict(error='partial run')]; reject(bad)
            if mode not in ('miss','missing'):
                bad=copy.deepcopy(result)
                for frame in bad['frames'][6:]: frame['target_python']=frame['target_native']=8
                reject(bad)
    print('PASS: both-seat cold-zero/full, loaded changed/equal and miss/missing witness controls; old captured seed/remaining split, eager-init, finish/seed/force drift, incomplete/absent landing and missing ordinary resume rejected; AST only')
    run_case_controls()


if __name__=='__main__': main()
