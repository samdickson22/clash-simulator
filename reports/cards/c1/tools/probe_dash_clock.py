"""Forced current-schema Dash deadline controls, not gameplay reachability proof."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import traceback

if sys.flags.optimize: raise RuntimeError('unoptimized dash-clock probe required')

import differential as D
import probe_shared_troop as T

MODES=('cold_zero','cold_equal','loaded_changed','loaded_equal','miss','missing')
KEYS=('id','x','y','hp','clock','clock_initialized','clock_reseed','force_due','cooldown',
      'dash','target','last_target','move_target','moving','started','windup','finish_tick')


def row(state, identity):
    return next((entity for entity in state['entities'] if entity['id']==identity),None)


def fixture(seat,mode):
    b,cfg,ids=T.setup([(seat,'Bandit',9,10.5),(1-seat,'Knight',9,17.5)],seat)
    actor,target=(b.entities[i] for i in ids)
    actor.position=T.point(9,6.5,seat); target.position=T.point(9,12.5,seat)
    actor.target_id=actor._last_combat_target_id=None
    actor._ordinary_clock=None; actor._ordinary_force_due=False
    actor.attack_cooldown=0 if mode=='cold_zero' else 1 if mode.endswith('equal') else 0.4
    if mode.startswith('loaded'):
        from clasher.ordinary_combat_clock import get_clock
        assert get_clock(actor) is not None
    target.deploy_delay_remaining=10
    mechanic=next(m for m in actor.mechanics if type(m).__name__=='BanditDash')
    actor._bandit_seen_target=target.id; mechanic._launch_dash(actor,target)
    if mode=='miss': target.position=T.point(15,25.5,seat)
    elif mode=='missing': del b.entities[target.id]
    return b,cfg,ids


def require_witness(result):
    assert result['ticks']==40 and len(result['frames'])==40
    assert not result['differences'] and not result['errors']
    landings=[frame for frame in result['frames'] if frame['before']['dash']['phase']=='travel'
        and frame['python']['dash']['phase']=='idle']
    assert len(landings)==1, 'no unique actual landing'
    landing=landings[0]; mode=result['mode']; loaded=mode.startswith('loaded')
    hit=mode not in ('miss','missing')
    initial=row(result['initial'],result['actor_id'])
    assert initial['clock_initialized'] is loaded and initial['clock_reseed'] is None
    assert initial['cooldown']==(0 if mode=='cold_zero' else 1 if mode.endswith('equal') else 0.4)
    assert initial['force_due'] is (mode=='cold_zero')
    assert initial['clock']['timeline']==0
    assert initial['clock']['remaining']==(initial['clock']['load'] if mode.endswith('equal') else 0)
    for label in ('python','native'):
        actor=landing[label]; previous=landing['before']
        assert actor['clock_initialized'] is loaded, 'eager or lost clock initialization'
        if hit:
            assert actor['cooldown']==1 and actor['clock']['finish']==previous['clock']['finish']
            assert landing['target_before']-landing['target_'+label]==result['dash_damage']
            if not loaded:
                assert actor['clock']['timeline']==0 and actor['clock']['remaining']==actor['clock']['load']
                assert actor['clock_reseed'] is None and actor['force_due'] is False
                assert {k:v for k,v in actor['clock'].items() if k not in ('timeline','remaining')}=={
                    k:v for k,v in previous['clock'].items() if k not in ('timeline','remaining')}
            else:
                assert actor['clock']==previous['clock'], 'loaded clock eagerly rewritten'
                assert actor['force_due']==previous['force_due']
                assert actor['clock_reseed']==(1000 if mode=='loaded_changed' else None)
        else:
            assert actor['cooldown']==previous['cooldown']!=1, 'non-hit installed full deadline'
            assert actor['clock']==previous['clock'] and actor['clock_reseed']==previous['clock_reseed']
            assert actor['force_due']==previous['force_due']
            assert landing['target_'+label]==landing['target_before'], 'non-hit damaged target'
    if hit:
        later=[frame for frame in result['frames'] if frame['offset']>landing['offset']]
        assert any(frame['python']['clock_initialized'] and frame['native']['clock_initialized'] for frame in later)
        assert any(frame['target_python']<landing['target_python'] and
                   frame['target_native']<landing['target_native'] for frame in later), 'ordinary attack never resumed'
    result['required_witness_observed']=True


def run_case(result,b,cfg,ids,contract):
    actor_id,target_id=ids
    initial=json.loads(T.snapshot(b,cfg,contract))
    result.update(initial=initial,actor_id=actor_id,target_id=target_id,frames=[],differences=[],errors=[],template_checks=[],first_context=None)
    result['dash_damage']=row(initial,actor_id)['stats']['dash']['damage']
    T.validate_templates(result,contract,'python/initial',initial,-1)
    live=D.clasher_core.BattleState(json.dumps(initial)); cloned=b.clone()
    for offset in range(40):
        before=dict(python=json.loads(T.snapshot(b,cfg,contract)),native=json.loads(live.snapshot()))
        result['last_before']=before
        # Recreate both arms at every pre-step boundary, including pre-impact
        # and the first ordinary-clock work after the cold landing.
        arms=dict(live=live,clone=live.clone(),reload=D.clasher_core.BattleState(live.snapshot()))
        b.step(); cloned.step()
        for arm in arms.values(): arm.step(1)
        python=json.loads(T.snapshot(b,cfg,contract)); native=json.loads(live.snapshot())
        T.validate_templates(result,contract,'python',python,offset)
        clone_state=json.loads(T.snapshot(cloned,cfg,contract))
        T.validate_templates(result,contract,'python_clone',clone_state,offset)
        assert clone_state==python, 'Python clone drift'
        for label,arm in arms.items():
            state=json.loads(arm.snapshot()); T.validate_templates(result,contract,label,state,offset)
            differences,applicability,raw,equal=T.compare(b,cfg,arm,contract)
            if differences or not equal:
                result['differences'].append(dict(offset=offset,arm=label,differences=differences,
                    applicability=applicability,raw=raw,digest_equal=equal))
                if result['first_context'] is None:
                    result['first_context']=dict(offset=offset,arm=label,before=before,after=dict(python=python,native=state))
            assert state==native, 'native pre-step clone/reload drift'
        py_actor=row(python,actor_id); native_actor=row(native,actor_id); previous=row(before['python'],actor_id)
        hp=lambda root: None if row(root,target_id) is None else row(root,target_id)['hp']
        frame=dict(offset=offset,tick=b.tick,before={k:previous.get(k) for k in KEYS},
            python={k:py_actor.get(k) for k in KEYS},native={k:native_actor.get(k) for k in KEYS},
            target_before=hp(before['python']),target_python=hp(python),target_native=hp(native))
        result['frames'].append(frame)
        if previous['dash']['phase']=='travel' and py_actor['dash']['phase']=='idle':
            result['landing_roots']=dict(offset=offset,before=before,after=dict(python=python,native=native))
    result['ticks']=40
    require_witness(result)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('output',type=Path)
    parser.add_argument('--contract',type=Path,required=True); parser.add_argument('--native-sha256',required=True)
    args=parser.parse_args(); assert not args.output.exists()
    actual=hashlib.sha256(Path(D.clasher_core.__file__).read_bytes()).hexdigest(); assert actual==args.native_sha256
    contract=T.load_contract(args.contract); results=[]
    for seat in (0,1):
        for mode in MODES:
            result=dict(seat=seat,mode=mode,status='ERROR'); results.append(result)
            try:
                b,cfg,ids=fixture(seat,mode); run_case(result,b,cfg,ids,contract)
                result['status']='FOCUSED_PASS'
            except Exception: result['error']=traceback.format_exc(limit=8)
            print(json.dumps({key:result.get(key) for key in ('seat','mode','status','ticks','error')}),flush=True)
    status='FOCUSED_PASS' if len(results)==12 and all(r['status']=='FOCUSED_PASS' for r in results) else 'FOCUSED_FAIL'
    with args.output.open('x') as stream:
        json.dump(dict(status=status,native_sha256=actual,results=results,scope='forced Dash cold/loaded deadline controls; no natural reachability claim'),stream,indent=1)
    raise SystemExit(0 if status=='FOCUSED_PASS' else 1)


if __name__=='__main__': main()
