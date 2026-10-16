"""Pure AST/mock validation for the future probe; no engine/native execution."""
import ast
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import traceback
from types import SimpleNamespace


PROBE = Path(__file__).with_name('probe_shared_troop.py')
TREE = ast.parse(PROBE.read_text())


def extract(name, namespace):
    node = next(n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name==name)
    exec(compile(ast.Module(body=[copy.deepcopy(node)],type_ignores=[]),str(PROBE),'exec'),namespace)
    return namespace[name]


def reject(function):
    try:
        function()
    except AssertionError:
        return
    raise AssertionError('unreached/incorrect witness accepted')


def main():
    namespace=dict(json=json,math=math,traceback=traceback)
    for name in ('watched_row','trunc_div','projected_remaining','require_zap_witness','require_witness',
                 'validate_templates','movement_observation','observe_finalization'):
        extract(name,namespace)
    witness = namespace['require_witness']
    def result(*actors):
        return dict(frames=[dict(actor=actor) for actor in actors])
    positive = dict(spirit=True,entity_kind=2,stats=dict(ordinary=False,projectile_slow_multiplier=0.7))
    witness('spirit/uniform',0,result(positive,None))
    reject(lambda:witness('spirit/uniform',0,result(dict(positive,spirit=False),None)))
    reject(lambda:witness('spirit/uniform',0,result(dict(positive,stats=dict(positive['stats'],projectile_slow_multiplier=1)),None)))
    reject(lambda:witness('spirit/uniform',0,result(positive,positive)))
    heading=dict(target=7,facing=[0,-1000])
    witness('heading/coincident',0,result(heading))
    reject(lambda:witness('heading/coincident',0,result(dict(heading,target=None))))
    reject(lambda:witness('heading/coincident',0,result(dict(heading,facing=[0,0]))))
    cleanup=dict(spirit=True,target=None,clock=dict(finish=1))
    witness('cleanup/positive_not_started',0,result(cleanup,None))
    reject(lambda:witness('cleanup/positive_not_started',0,result(dict(cleanup,target=7),None)))
    reject(lambda:witness('cleanup/positive_not_started',0,result(dict(cleanup,clock=dict(finish=0)),None)))
    def zap_result(seat, variant):
        route=[] if variant=='empty_route' else ([[21,23],[22,24],[23,25]] if seat==0 else [[21,40],[22,39],[23,38]])
        row=dict(id=7,alive=True,x=9,y=10.5 if seat==0 else 21.5,
            stun=0 if variant=='no_stun' else 0.5,frozen_moving=variant!='not_frozen',
            route=route,direction=[181,181 if seat==0 else -181],
            facing=[1750,1250 if seat==0 else -1250],dash=dict(phase='travel'))
        state=lambda row:dict(entities=[copy.deepcopy(row)])
        out=dict(watched=7,initial=state(row),frames=[],zap_transition_roots=[])
        count=2 if variant=='frozen' else 1
        for offset in range(count):
            pre=dict(position=[9000,(11000 if offset==0 else 12500) if seat==0 else (21000 if offset==0 else 19500)],
                route=copy.deepcopy(row['route']),direction=row['direction'][:],facing=row['facing'][:],phase='travel',
                stun=row['stun'],frozen_moving=row['frozen_moving'],external=[250,1000 if seat==0 else -1000] if variant=='external' else [0,0])
            post=copy.deepcopy(pre)
            post['position']=[p+v for p,v in zip(pre['position'],pre['external'])]
            if pre['stun']>0 and pre['frozen_moving'] and pre['route']:
                head=pre['route'][0]
                post['facing']=[c*500+250-p for c,p in zip(head,pre['position'])]
                if namespace['projected_remaining'](head,post['position'],pre['direction'])<1001:
                    post['route']=pre['route'][1:]
                    delta=[c*500+250-p for c,p in zip(post['route'][0],post['position'])]
                    length=max(1,math.isqrt(sum(d*d for d in delta)))
                    post['direction']=[namespace['trunc_div'](d*256,length) for d in delta]
            after=dict(row,x=post['position'][0]/1000,y=post['position'][1]/1000,
                       facing=post['facing'],direction=post['direction'],route=post['route'])
            transition=dict(python=dict(before=copy.deepcopy(row),after=copy.deepcopy(after)),
                natives={label:dict(before=copy.deepcopy(row),after=copy.deepcopy(after)) for label in ('uninterrupted','clone','reload')})
            event=dict(before=pre,after=post)
            out['frames'].append(dict(offset=offset,actor=copy.deepcopy(after),transition=transition,
                movement=dict(python=[copy.deepcopy(event)],python_clone=[copy.deepcopy(event)])))
            out['zap_transition_roots'].append(dict(offset=offset,
                before=dict(python=state(row),natives={label:state(row) for label in transition['natives']}),
                after=dict(python=state(after),natives={label:state(after) for label in transition['natives']})))
            row=copy.deepcopy(after)
        return out

    for seat in (0,1):
        for variant in ('frozen','external','no_stun','not_frozen','empty_route'):
            good=zap_result(seat,variant)
            witness('zap/'+variant,seat,good)
            for drop in ('all_actors','initial_actor','first_actor','observation','paired_roots'):
                bad=copy.deepcopy(good)
                if drop=='all_actors':
                    for frame in bad['frames']: frame['actor']=None
                elif drop=='initial_actor': bad['initial']['entities']=[]
                elif drop=='first_actor': bad['frames'][0]['actor']=None
                elif drop=='observation': bad['frames'][0]['movement']['python']=[]
                else: bad['zap_transition_roots']=[]
                reject(lambda:witness('zap/'+variant,seat,bad))
            bad=copy.deepcopy(good)
            bad['initial']['entities'][0]['stun']=0.5 if variant=='no_stun' else 0
            reject(lambda:witness('zap/'+variant,seat,bad))
            bad=copy.deepcopy(good)
            bad['initial']['entities'][0]['frozen_moving']=variant=='not_frozen'
            reject(lambda:witness('zap/'+variant,seat,bad))
            bad=copy.deepcopy(good)
            bad['initial']['entities'][0]['route']=[[1,1]]
            reject(lambda:witness('zap/'+variant,seat,bad))
            bad=copy.deepcopy(good)
            for arm in ('python','python_clone'):
                observation=bad['frames'][0]['movement'][arm][0]['before']
                observation['stun']=0.5 if variant=='no_stun' else 0
            reject(lambda:witness('zap/'+variant,seat,bad))
        for mutation in ('late_pop','excessive_pop','wrong_direction','wrong_heading','wrong_pose','wrong_root','no_transport'):
            bad=zap_result(seat,'frozen')
            event=bad['frames'][1]['movement']['python'][0]
            if mutation=='late_pop': event['before']['phase']=event['after']['phase']='idle'
            elif mutation=='excessive_pop': event['after']['route']=[]
            elif mutation=='wrong_direction': event['after']['direction']=[0,0]
            elif mutation=='wrong_heading': event['after']['facing']=[0,0]
            elif mutation=='wrong_pose': event['after']['position'][0]+=1
            elif mutation=='wrong_root': bad['zap_transition_roots'][1]['after']['python']['entities'][0]['x']+=1
            else:
                row=bad['frames'][1]['transition']['python']['before']
                event['before']['position']=[round(row['x']*1000),round(row['y']*1000)]
            # Keep both independent Python arm observations equally wrong.
            bad['frames'][1]['movement']['python_clone']=copy.deepcopy(bad['frames'][1]['movement']['python'])
            reject(lambda:witness('zap/frozen',seat,bad))
        for mutation in ('face_after','advance_before','no_external','native_wrong_order'):
            bad=zap_result(seat,'external')
            event=bad['frames'][0]['movement']['python'][0]
            if mutation=='face_after':
                event['after']['facing']=[c*500+250-p for c,p in zip(event['before']['route'][0],event['after']['position'])]
            elif mutation=='advance_before': event['after']['route']=event['before']['route'][:]
            elif mutation=='no_external': event['before']['external']=[0,0]
            else: bad['frames'][0]['transition']['natives']['clone']['after']['facing']=[0,0]
            bad['frames'][0]['movement']['python_clone']=copy.deepcopy(bad['frames'][0]['movement']['python'])
            reject(lambda:witness('zap/external',seat,bad))

    # Load only the exact frozen stdlib template validator, never engine code.
    contract_path=Path('/mpac/sdicks02/repos/clasher-cards-b2/reports/cards/b2/tools/snapshot_contract_v1.py')
    contract_source=contract_path.read_bytes()
    assert hashlib.sha256(contract_source).hexdigest()=='8ca5826c87c22aa288065cdb2655f06436409fe05cae9d029684d1f89e3dd4e3'
    node=next(n for n in ast.parse(contract_source).body if isinstance(n,ast.FunctionDef) and n.name=='fresh_troop_templates')
    contract_namespace={}
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(contract_path),'exec'),contract_namespace)
    contract=SimpleNamespace(differences=lambda *args:[],fresh_troop_templates=contract_namespace['fresh_troop_templates'])
    fresh=dict(config=dict(unit=dict(**{'class':'Troop'},public_speed_base=None)),entities=[])
    for kind in ('config_nonfresh','clone_nonfresh','missing'):
        bad=copy.deepcopy(fresh)
        if kind=='config_nonfresh': bad['config']['unit']['public_speed_base']=987
        elif kind=='clone_nonfresh': bad['entities']=[dict(id=7,clone_template=dict(**{'class':'Troop'},public_speed_base=987))]
        else: bad['config']={}
        record={}
        reject(lambda:namespace['validate_templates'](record,contract,kind,bad,0))
        assert record['template_checks'][0]['valid'] is False
        assert record['template_checks'][0]['root']==bad

    class Python:
        tick=0
        def clone(self): return Python()
        def step(self): self.tick+=1

    class Native:
        def __init__(self,raw): self.raw=raw
        def clone(self): return Native(self.raw)
        def snapshot(self): return self.raw
        def step(self,_): raise RuntimeError('synthetic-native-step-error')

    def snapshot(python,*_): return json.dumps(dict(fresh,tick=python.tick))
    namespace.update(snapshot=snapshot,D=SimpleNamespace(
        clasher_core=SimpleNamespace(BattleState=Native),battle_digest=lambda python:str(python.tick)))
    continuation=extract('continuation',namespace)
    record={}
    try:
        continuation('synthetic',Python(),{},contract,2,record=record)
    except RuntimeError as error:
        assert str(error)=='synthetic-native-step-error'
    else:
        raise AssertionError('synthetic step did not fail')
    assert record['initial']==dict(fresh,tick=0)
    assert record['last_before']['python']==dict(fresh,tick=0)
    assert record['last_before']['native']==dict(fresh,tick=0)
    assert record['frames']==[] and record['differences']==[]
    assert len(record['template_checks'])==5 and all(check['valid'] for check in record['template_checks'])

    # A latent invalid template in any arm cannot hide behind zero deltas.
    class SteppingNative:
        serial=0
        poison=None
        poison_initial=False
        def __init__(self,raw):
            self.raw=json.loads(raw); self.identity=SteppingNative.serial; SteppingNative.serial+=1
        def clone(self): return SteppingNative(json.dumps(self.raw))
        def snapshot(self):
            root=copy.deepcopy(self.raw)
            if self.identity==self.poison and (self.poison_initial or root.get('tick',0)>0):
                root['config']['unit']['public_speed_base']=987
            return json.dumps(root)
        def step(self,_): self.raw['tick']+=1
    namespace['D'].clasher_core.BattleState=SteppingNative
    namespace['compare']=lambda *args:([],[],[],True)
    for poisoned_arm in (None,0,1,2):
        for initial in (False,True):
            SteppingNative.serial=0; SteppingNative.poison=poisoned_arm; SteppingNative.poison_initial=initial
            record={}
            if poisoned_arm is None:
                continuation('synthetic',Python(),{},contract,1,record=record)
                assert record['status']=='FOCUSED_PASS' and len(record['template_checks'])==10
            else:
                reject(lambda:continuation('synthetic',Python(),{},contract,1,record=record))
                assert record.get('status')!='FOCUSED_PASS'
                assert any(check.get('valid') is False and 'root' in check for check in record['template_checks'])

    class Actor:
        def __init__(self,fail=False):
            self.position=SimpleNamespace(x=9,y=11)
            self._native_ground_route_cells=[(21,23)]
            self._native_ground_route_direction=(181,181)
            self._facing_x_units=1750; self._facing_y_units=1250
            self._bandit_state='travel'; self.stun_timer=0.5
            self._native_moving_when_frozen=True
            self._pending_movement_consumed=False
            self._pending_movement_x=0.25; self._pending_movement_y=1
            self.calls=0; self.fail=fail
        def finish_movement_tick(self,battle):
            assert battle=='sentinel-battle'
            self.calls+=1; self.position.x+=self._pending_movement_x
            if self.fail: raise RuntimeError('synthetic-finalizer-error')
            self.position.y+=self._pending_movement_y
            self._pending_movement_consumed=True
            return 'sentinel-return'
    for fail in (False,True):
        actor=Actor(fail); control=Actor(fail); events=[]
        namespace['observe_finalization'](actor,events)
        for subject in (actor,control):
            try:
                value=subject.finish_movement_tick('sentinel-battle')
                assert not fail and value=='sentinel-return'
            except RuntimeError as error:
                assert fail and str(error)=='synthetic-finalizer-error'
        assert actor.calls==control.calls==1 and len(events)==1
        assert namespace['movement_observation'](actor)==namespace['movement_observation'](control)
        assert events[0]['before']['position']==[9000,11000]
        assert events[0]['after']==namespace['movement_observation'](actor)

    # The guard precedes differential import, so this child cannot import/run it.
    opt=subprocess.run([sys.executable,'-O','-B',str(PROBE)],capture_output=True,text=True)
    assert opt.returncode!=0 and 'unoptimized Python is required' in opt.stderr
    assert 'No module named' not in opt.stderr
    print('PASS: both-seat linked Zap/guard/order controls, exact template prerequisite across native arms, partial-failure roots and optimized-Python guard; no actual native/engine run')


if __name__=='__main__':
    main()
