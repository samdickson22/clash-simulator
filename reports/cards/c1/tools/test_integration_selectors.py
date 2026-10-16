"""Pure AST witness controls, no engine/native execution or host access."""
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


def reject(call):
    try: call()
    except AssertionError: return
    raise AssertionError('wrong/unreached selector witness accepted')


def execution_controls(path,tree):
    helper=ast.parse(path.with_name('probe_dash_clock.py').read_text())
    ids=dict(actor=7,primary=8,bandit=9,other=10,chain=11)
    def exercise(fault=None,persist=False):
        counts=[0]
        def state(tick): return dict(tick=tick,entities=[dict(id=i,hp=100,clock=dict(remaining=0)) for i in range(7,12)])
        class Battle:
            def __init__(self,tick=0,kind='reference'): self.tick,self.kind=tick,kind
            def clone(self):
                if fault=='python-construction': raise ValueError('injected Python clone construction')
                return Battle(self.tick,'clone')
            def step(self):
                self.tick+=1
                if fault=='python-step' and self.kind=='reference' and self.tick==4: raise ValueError('injected partial Python step')
            def state(self):
                if fault=='snapshot' and self.kind=='clone' and self.tick==3: raise ValueError('injected clone snapshot')
                out=state(self.tick)
                if fault=='python-clone' and self.kind=='clone' and self.tick>=3: out['entities'][0]['clock']['remaining']=77
                return out
        class Native:
            def __init__(self,encoded,kind): self.tick=json.loads(encoded)['tick']; self.kind=kind
            def clone(self):
                if fault=='native-construction': raise ValueError('injected native clone construction')
                return Native(self.snapshot(),'clone')
            def snapshot(self):
                out=state(self.tick)
                if fault=='native-clone' and self.kind=='clone' and self.tick>=3: out['entities'][0]['clock']['remaining']=88
                return json.dumps(out)
            def step(self,count):
                self.tick+=count
                if fault=='native-step' and self.kind=='reload' and self.tick==4: raise ValueError('injected partial native step')
            def debug_step(self):
                self.tick+=1
                if fault=='debug-decode' and self.tick==3: return 'malformed phase JSON'
                return json.dumps([['combat',state(self.tick)]])
        def create(encoded):
            counts[0]+=1
            if fault=='reload-construction' and counts[0]==2: raise ValueError('injected reload construction')
            return Native(encoded,'live' if counts[0]%2 else 'reload')
        def templates(result,contract,label,root,offset):
            if fault=='template' and label=='python/clone' and offset==2: raise ValueError('injected selector template')
        def compare(b,cfg,native,contract):
            if fault=='comparison' and b.tick==3: raise ValueError('injected selector comparison')
            delta=[] if json.loads(native.snapshot())==b.state() else [dict(field='test.clock')]
            return delta,[],delta,not delta
        def digest(b): return str(b.tick)+('bad' if fault=='digest' and b.kind=='clone' and b.tick==3 else '')
        fake_T=SimpleNamespace(snapshot=lambda b,cfg,contract:json.dumps(b.state()),validate_templates=templates,
            compare=compare,watched_row=lambda root,identity:next((r for r in root['entities'] if r['id']==identity),None),
            load_contract=lambda path:object(),CONTRACT_SHA='a'*64)
        fake_D=SimpleNamespace(clasher_core=SimpleNamespace(BattleState=create),battle_digest=digest)
        ns=dict(json=json,traceback=traceback,T=fake_T,D=fake_D,observe_reservations=lambda *args:None,
            require_witness=lambda result:None)
        for source,name in ((helper,'capture_roots'),(tree,'row'),(tree,'run_case')):
            node=next(node for node in source.body if isinstance(node,ast.FunctionDef) and node.name==name)
            exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),ns)
        result=dict(kind='secondary',ids=ids);error=None
        try: ns['run_case'](result,Battle(),{},object())
        except (AssertionError,ValueError) as failure: error=str(failure)
        if persist:
            with tempfile.TemporaryDirectory(prefix='c1-selector-failure-') as temp:
                directory=Path(temp);artifact=directory/'fake-native.txt';artifact.write_text('not native')
                fake_D.clasher_core.__file__=str(artifact)
                ns.update(argparse=argparse,Path=Path,hashlib=hashlib,sys=sys,
                    fixture=lambda *args:(Battle(),{},ids))
                node=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='main')
                exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),ns)
                output=directory/'selectors.json';code=None
                args=['probe',str(output),'--contract',str(directory/'fake-contract'),
                    '--native-sha256',hashlib.sha256(artifact.read_bytes()).hexdigest()]
                with patch.object(sys,'argv',args),contextlib.redirect_stdout(io.StringIO()):
                    try: ns['main']()
                    except SystemExit as failure: code=failure.code
                report=json.loads(output.read_text())
                assert code==1 and report['status']=='FOCUSED_FAIL' and len(report['results'])==8
                for index,failed in enumerate(report['results']):
                    context=failed['failure_context'];assert failed['status']=='ERROR' and failed['error']
                    assert context['offset']==2 and len(failed['frames'])==2
                    assert context['after']['python']['clone']['entities'][0]['clock']['remaining']==77
                    assert context['after']['python']['reference']['tick']==3
                    assert context['after']['natives']['reload']['tick']==3
                    assert json.loads(output.with_name('selectors-'+str(index)+'-result.json').read_text())==failed
        return result,error
    result,error=exercise()
    assert error is None and len(result['frames'])==12 and result['first_context'] is None
    for fault,offset,after_tick in (('python-clone',2,3),('native-clone',2,3),('digest',2,3),
            ('python-step',3,4),('native-step',3,4),('snapshot',2,3),('template',2,3),
            ('comparison',2,3),('debug-decode',2,3),('python-construction',-1,0),
            ('native-construction',-1,0),('reload-construction',-1,0)):
        result,error=exercise(fault);assert error is not None,fault
        context=result['failure_context'];assert context['offset']==offset and result['first_context'] is context
        assert context['after']['python']['reference']['tick']==after_tick and context['error']
        if offset>=0: assert result['last_before']['python']['reference']['tick']==offset
        if fault=='python-clone': assert context['after']['python']['clone']['entities'][0]['clock']['remaining']==77
        if fault=='native-clone': assert context['after']['natives']['clone']['entities'][0]['clock']['remaining']==88
        if fault=='native-step': assert 'native/reload' not in context['completed_steps']
        if fault=='snapshot': assert context['after']['python']['clone']['unavailable_error'] and context['root_capture_errors']
        if fault=='debug-decode': assert context['native_debug_raw']=='malformed phase JSON'
        assert json.loads(json.dumps(result))['failure_context']['offset']==offset
    exercise('python-clone',persist=True)
    print('PASS: exact selector run_case/main AST retains clone/digest/partial-step/snapshot/template/comparison/construction/debug failures; all8 saved cases preserve failing and paired roots')


def main():
    path=Path(__file__).with_name('probe_integration_selectors.py')
    tree=ast.parse(path.read_text(),filename=str(path))
    namespace=dict(T=SimpleNamespace(watched_row=lambda state,identity:next((row for row in state['entities'] if row['id']==identity),None)))
    for name in ('row','require_witness'):
        node=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name==name)
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),namespace)
    witness=namespace['require_witness']
    ids=dict(actor=7,primary=8,bandit=9,other=10,chain=11)
    for seat in (0,1):
        for travel in (True,False):
            y=14.5 if seat==0 else 17.5
            bandit=dict(id=9,x=10,y=y,hp=1000 if travel else 900,stun=0 if travel else 0.3,dash=dict(phase='travel' if travel else 'idle'))
            primary=dict(id=8,hp=900); other=dict(id=10,hp=1000)
            base=dict(ids=ids,seat=seat,travel=travel,initial=dict(entities=[dict(id=i,hp=1000) for i in (7,8,9,10)]))
            event=dict(primary=8,reserved=[9],targetable=True,bandit_travel=travel,effect_allowed=not travel)
            rows=dict(bandit=bandit,primary=primary,other=other,actor=dict(id=7,attacked_current=True))
            secondary=dict(base,kind='secondary',reservations=dict(python=[event],clone=[copy.deepcopy(event)]),
                frames=[dict(python_rows=copy.deepcopy(rows),native_rows=copy.deepcopy(rows),native_combat=copy.deepcopy(rows))])
            witness(secondary)
            for mutation in ('missing_reservation','wrong_reserved_id','untargetable','wrong_effect_guard','no_attack','distractor_hit','wrong_bandit_damage'):
                bad=copy.deepcopy(secondary)
                if mutation=='missing_reservation': bad['reservations']['python']=[]
                elif mutation=='wrong_reserved_id':
                    for arm in ('python','clone'): bad['reservations'][arm][0]['reserved']=[10]
                elif mutation=='untargetable':
                    for arm in ('python','clone'): bad['reservations'][arm][0]['targetable']=False
                elif mutation=='wrong_effect_guard':
                    for arm in ('python','clone'): bad['reservations'][arm][0]['effect_allowed']=travel
                elif mutation=='no_attack': bad['frames'][0]['native_combat']['actor']['attacked_current']=False
                elif mutation=='distractor_hit': bad['frames'][0]['native_combat']['other']['hp']=900
                else: bad['frames'][0]['native_combat']['bandit']['hp']=900 if travel else 1000
                reject(lambda:witness(bad))
            chain=dict(id=11,shot_target=9,hit_ids=[8,9],aim=[bandit['x'],bandit['y']],chain_wait=3)
            start=dict(rows,chain=chain)
            finish=dict(rows,chain=None)
            chained=dict(base,kind='chain',frames=[dict(python_rows=copy.deepcopy(start),native_rows=copy.deepcopy(start)),
                dict(python_rows=copy.deepcopy(finish),native_rows=copy.deepcopy(finish))])
            witness(chained)
            for mutation in ('missing_visited','duplicate_visited','wrong_target','wrong_aim','missing_wait','no_impact','wrong_damage','wrong_guard'):
                bad=copy.deepcopy(chained)
                shot=bad['frames'][0]['native_rows']['chain']
                if mutation=='missing_visited': shot['hit_ids']=[8]
                elif mutation=='duplicate_visited': shot['hit_ids']=[8,9,9]
                elif mutation=='wrong_target': shot['shot_target']=10
                elif mutation=='wrong_aim': shot['aim']=[0,0]
                elif mutation=='missing_wait': shot['chain_wait']=0
                elif mutation=='no_impact': bad['frames']=bad['frames'][:1]
                elif mutation=='wrong_damage': bad['frames'][1]['native_rows']['bandit']['hp']=900 if travel else 1000
                elif travel: bad['frames'][1]['native_rows']['bandit']['dash']['phase']='idle'
                else: bad['frames'][1]['native_rows']['bandit']['stun']=0
                reject(lambda:witness(bad))
    print('PASS: both-seat secondary reservation/guard/effect and chain target/visited-ID/multiplicity/aim/impact negative controls; AST/mocks only')
    execution_controls(path,tree)


if __name__=='__main__': main()
