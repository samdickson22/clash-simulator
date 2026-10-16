"""Eight bounded current-schema selector witnesses, never natural reachability proof.

Keep targetability distinct from damage/effect eligibility. Native secondary IDs
are not exported: retain Python reservations, native combat-phase effects and a
paired idle positive control; chain visited/target IDs are observed directly.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import traceback

if sys.flags.optimize: raise RuntimeError('unoptimized selector probe required')

import differential as D
import probe_shared_troop as T
from probe_dash_clock import capture_roots


def fixture(seat,kind,travel):
    name='ElectroWizard' if kind=='secondary' else 'ElectroDragon'
    b,cfg,ids=T.setup([(seat,name,9,10.5),(1-seat,'Knight',9,17.5),
        (1-seat,'Bandit',11,17.5),(1-seat,'Musketeer',13,20.5)],seat)
    actor,primary,bandit,other=(b.entities[i] for i in ids)
    for entity,position in ((actor,(9,13.5)),(primary,(9,15)),(bandit,(10,14.5)),(other,(11,15.5))):
        entity.position=T.point(*position,seat)
        entity._native_natural_movement_active=False
        entity._movement_target_id=None
        entity.target_id=entity._last_combat_target_id=None
        entity.stun_timer=0
        entity._native_moving_when_frozen=False
        entity.deploy_delay_remaining=10 if entity in (primary,other) or kind=='chain' and entity is actor else 0
    if travel:
        dash=next(m for m in bandit.mechanics if type(m).__name__=='BanditDash')
        king=next(e for e in b.entities.values() if e.player_id==seat and getattr(e,'_crown_tower_slot',None)=='king')
        bandit._bandit_seen_target=king.id
        dash._launch_dash(bandit,king)
    else:
        # The control is deployed but immobile, without a travel/tail guard.
        bandit.deploy_delay_remaining=10
    actor.target_id=actor._last_combat_target_id=primary.id
    actor.attack_cooldown=0 if kind=='secondary' else 10
    actor._attack_windup_active=False
    watched=None
    if kind=='chain':
        from clasher.entities import ChainLightning
        mechanic=next(m for m in actor.mechanics if type(m).__name__=='ElectroDragonChainLightning')
        # Explicit valid midflight root: impact the primary next frame, so the
        # next node is released by BOTH implementations after native import.
        chain=ChainLightning(id=b.next_entity_id,position=D.Position(primary.position.x,primary.position.y),
            player_id=seat,card_stats=actor.card_stats,hitpoints=1,max_hitpoints=1,
            damage=actor.damage,range=0,sight_range=0,
            origin=D.Position(primary.position.x,primary.position.y),remaining_bounces=2,
            chain_range=mechanic.chain_range,travel_speed=mechanic.projectile_speed_tiles_per_second,
            stun_duration=mechanic.stun_duration_ms/1000,visited_ids={primary.id},
            current_target_id=primary.id,hop_wait_ticks=3,wait_remaining=0,
            aim=D.Position(primary.position.x,primary.position.y))
        chain._birth_tick=b.tick-1
        b.entities[chain.id]=chain; b.next_entity_id+=1; watched=chain.id
    return b,cfg,dict(actor=actor.id,primary=primary.id,bandit=bandit.id,other=other.id,chain=watched)


def observe_reservations(b,ids,events):
    actor=b.entities[ids['actor']]
    mechanic=next(m for m in actor.mechanics if type(m).__name__=='MultipleTargetAttack')
    original=mechanic.on_attack_start
    def observed(entity,target):
        answer=original(entity,target)
        bandit=b.entities[ids['bandit']]
        events.append(dict(tick=b.tick,primary=target.id,reserved=list(mechanic._secondary_target_ids),
            bandit_travel=bandit._bandit_state=='travel',
            targetable=entity.can_attack_target(bandit),effect_allowed=bandit.can_receive_effect(entity.card_stats.name)))
        return answer
    mechanic.on_attack_start=observed


def row(state,identity): return T.watched_row(state,identity)


def require_witness(result):
    ids=result['ids']; travel=result['travel']; kind=result['kind']
    first=result['frames'][0]; initial=result['initial']
    assert first['python_rows']['bandit'] is not None and first['native_rows']['bandit'] is not None
    if kind=='secondary':
        events=result['reservations']['python']
        assert events and events==result['reservations']['clone'], 'no paired Python reservation'
        event=events[0]
        assert event['primary']==ids['primary'] and event['reserved']==[ids['bandit']]
        assert event['targetable'] is True and event['bandit_travel'] is travel
        assert event['effect_allowed'] is (not travel)
        combat=first['native_combat']
        assert combat['actor']['attacked_current'] is True, 'no actual native direct attack'
        assert combat['primary']['hp']<row(initial,ids['primary'])['hp'], 'primary attack did not land'
        assert combat['other']['hp']==row(initial,ids['other'])['hp'], 'secondary skipped dash and selected distractor'
        recipient=combat['bandit']
        if travel:
            assert recipient['dash']['phase']=='travel' and recipient['hp']==row(initial,ids['bandit'])['hp']
            assert recipient['stun']==0, 'travel recipient received status'
        else:
            assert recipient['hp']<row(initial,ids['bandit'])['hp'] and recipient['stun']>0, 'idle positive control never hit'
        result['native_secondary_evidence']='combat effects plus paired idle positive control and inspected two-recipient selector; IDs not serialized'
    else:
        # Release happens after movement: compare actual selected node and aim,
        # rather than substituting the start-of-frame Bandit coordinate.
        for state in (first['python_rows'],first['native_rows']):
            chain=state['chain']; target=state['bandit']
            assert chain is not None and chain['shot_target']==ids['bandit']
            assert sorted(chain['hit_ids'])==sorted([ids['primary'],ids['bandit']])
            assert chain['aim']==[target['x'],target['y']]
            assert chain['chain_wait']==3
        impacted=[frame for frame in result['frames'] if frame['native_rows']['chain'] is None]
        assert impacted, 'reserved chain did not actually finish its hop'
        final=impacted[0]
        for rows in (final['python_rows'],final['native_rows']):
            assert rows['other']['hp']==row(initial,ids['other'])['hp']
            if travel:
                assert rows['bandit']['dash']['phase']=='travel', 'travel guard not live at impact'
                assert rows['bandit']['hp']==row(initial,ids['bandit'])['hp'] and rows['bandit']['stun']==0
            else:
                assert rows['bandit']['hp']<row(initial,ids['bandit'])['hp'] and rows['bandit']['stun']>0
    result['required_witness_observed']=True


def run_case(result,b,cfg,contract):
    result.update(frames=[],differences=[],errors=[],template_checks=[],first_context=None)
    pythons=dict(reference=b); arms={}
    context=dict(offset=-1,operation='setup',before={},after={},completed_steps=[])
    result['current_context']=context
    try:
        initial=json.loads(T.snapshot(b,cfg,contract)); result['initial']=initial
        context['before']=dict(python=dict(reference=initial),natives={})
        T.validate_templates(result,contract,'python/initial',initial,-1)
        context['operation']='native/initial'
        live=D.clasher_core.BattleState(json.dumps(initial)); arms['live']=live
        context['operation']='native/clone'
        arms['clone']=live.clone()
        context['operation']='native/reload'
        arms['reload']=D.clasher_core.BattleState(live.snapshot())
        context['operation']='python/clone'
        cloned=b.clone(); pythons['clone']=cloned
        reservations=dict(python=[],clone=[]); result['reservations']=reservations
        context['operation']='reservation_observers'
        if result['kind']=='secondary':
            observe_reservations(b,result['ids'],reservations['python'])
            observe_reservations(cloned,result['ids'],reservations['clone'])
        context['before'],errors=capture_roots(pythons,arms,cfg,contract)
        assert not errors, 'initial root capture failed: '+repr(errors)
        for label,state in context['before']['natives'].items():
            context['operation']='initial_template/'+label
            T.validate_templates(result,contract,label+'/initial',state,-1)
        T.validate_templates(result,contract,'clone/initial',context['before']['python']['clone'],-1)
        for offset in range(12):
            context=dict(offset=offset,operation='before',before={},after={},completed_steps=[])
            result['current_context']=context
            context['before'],errors=capture_roots(pythons,arms,cfg,contract)
            result['last_before']=context['before']
            assert not errors, 'pre-step root capture failed: '+repr(errors)
            for label,arm in pythons.items():
                context['operation']='python/step/'+label
                arm.step(); context['completed_steps'].append('python/'+label)
            context['operation']='native/debug_step'
            encoded=live.debug_step(); context['completed_steps'].append('native/live')
            context['operation']='native/debug_decode'
            try: phases=dict(json.loads(encoded))
            except BaseException:
                context['native_debug_raw']=encoded
                raise
            context['native_phases']=phases
            for label in ('clone','reload'):
                context['operation']='native/step/'+label
                arms[label].step(1); context['completed_steps'].append('native/'+label)
            context['operation']='after'
            context['after'],errors=capture_roots(pythons,arms,cfg,contract)
            assert not errors, 'post-step root capture failed: '+repr(errors)
            python=context['after']['python']['reference']; native=context['after']['natives']['live']
            for label,state in context['after']['python'].items():
                context['operation']='python/validate/'+label
                T.validate_templates(result,contract,'python/'+label,state,offset)
                assert state==python, 'Python clone drift: '+label
                assert D.battle_digest(pythons[label])==D.battle_digest(b), 'Python clone digest drift: '+label
            outcomes={}
            for label,arm in arms.items():
                context['operation']='native/compare/'+label
                state=context['after']['natives'][label]
                T.validate_templates(result,contract,label,state,offset)
                delta,applicability,raw,equal=T.compare(b,cfg,arm,contract)
                outcomes[label]=dict(differences=delta,applicability=applicability,raw=raw,digest_equal=equal)
                if delta or not equal:
                    result['differences'].append(dict(offset=offset,arm=label,**outcomes[label]))
                    context.setdefault('first_failure',dict(operation=context['operation'],arm=label,kind='semantic'))
                    if result['first_context'] is None: result['first_context']=context
                assert state==native, 'native clone/reload/debug-step drift: '+label
            ids=result['ids']
            result['frames'].append(dict(offset=offset,tick=b.tick,
                python_rows={name:row(python,identity) if identity is not None else None for name,identity in ids.items()},
                native_rows={name:row(native,identity) if identity is not None else None for name,identity in ids.items()},
                native_combat={name:row(phases['combat'],identity) if identity is not None else None for name,identity in ids.items()},outcomes=outcomes))
        context['operation']='required_witness'
        require_witness(result)
        result['status']='FOCUSED_FAIL' if result['differences'] or result['errors'] else 'FOCUSED_PASS'
    except BaseException:
        original=traceback.format_exc(limit=12)
        roots,errors=capture_roots(pythons,arms,cfg,contract)
        context['exception_observed']=roots; context['root_capture_errors']=errors
        if not context['after']: context['after']=roots
        context['error']=original
        result['errors'].append(dict(offset=context['offset'],operation=context['operation'],error=original))
        if result['first_context'] is None: result['first_context']=context
        result['failure_context']=context
        raise


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('output',type=Path)
    parser.add_argument('--contract',required=True,type=Path); parser.add_argument('--native-sha256',required=True)
    args=parser.parse_args(); assert not args.output.exists()
    native_path=Path(D.clasher_core.__file__); native_sha=hashlib.sha256(native_path.read_bytes()).hexdigest()
    assert native_sha==args.native_sha256
    contract=T.load_contract(args.contract); results=[]
    for seat in (0,1):
        for kind in ('secondary','chain'):
            for travel in (True,False):
                result=dict(seat=seat,kind=kind,travel=travel,status='ERROR')
                try:
                    b,cfg,ids=fixture(seat,kind,travel); result['ids']=ids
                    # Preserve construction even if native initialization or stepping crashes.
                    initial=json.loads(T.snapshot(b,cfg,contract))
                    with args.output.with_name(args.output.stem+'-'+str(len(results))+'-initial.json').open('x') as out: json.dump(initial,out)
                    run_case(result,b,cfg,contract)
                except BaseException: result.update(status='ERROR',error=traceback.format_exc(limit=10))
                results.append(result)
                with args.output.with_name(args.output.stem+'-'+str(len(results)-1)+'-result.json').open('x') as out: json.dump(result,out,indent=1)
                print(json.dumps({key:result[key] for key in ('seat','kind','travel','status')}),flush=True)
    assert hashlib.sha256(native_path.read_bytes()).hexdigest()==native_sha
    report=dict(native_sha256=native_sha,contract_sha256=T.CONTRACT_SHA,results=results,
        status='FOCUSED_PASS' if len(results)==8 and all(result['status']=='FOCUSED_PASS' for result in results) else 'FOCUSED_FAIL',
        engine_acceptance=False,scope='8 explicit selector continuations; no natural-reachability or full-gate claim')
    with args.output.open('x') as out: json.dump(report,out,indent=1)
    raise SystemExit(0 if report['status']=='FOCUSED_PASS' else 1)


if __name__=='__main__': main()
