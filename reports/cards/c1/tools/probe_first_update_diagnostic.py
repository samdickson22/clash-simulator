"""All 21 Batch A paths/both seats with complete, validated causal controls.

Original Batch A helper/results stay unchanged. This diagnostic retains script-
born victims, full controls and failed roots, without reducing the 42-row set.
"""
import hashlib
import json
from pathlib import Path
import sys
import traceback

if sys.flags.optimize: raise RuntimeError('unoptimized first-update diagnostic required')

import differential as D
import probe_first_update_paths as A


def control_case(case):
    side,name=case['victim']
    return dict(case,setup=[op for op in case['setup'] if op[0]=='step' or
        op[0] in ('deploy','hp','move') and (op[1],op[2])==(side,name)],
        script=[entry for entry in case['script'] if (entry[1],entry[2])==(side,name)])


def validate_pair(result):
    control=result['control']
    assert result['native']=='ok' and not result.get('error') and result['status']=='COMPLETE'
    assert result['first_mismatch'] is None and result['completed_ticks']==result['requested_ticks']
    assert control['status']=='CONTROL_COMPLETE' and not control.get('error')
    assert control['completed_ticks']==control['requested_ticks']==result['requested_ticks']
    assert control['case']==result['case'] and control['victim']==result['victim']
    assert result['victim_observations'] and control['victim_observations']
    for key in ('owner','name','x','y','observed_tick','hp','stats_sha256'):
        assert [row[key] for row in result['victim_observations']]==[row[key] for row in control['victim_observations']],key
    assert result['victim_death'] is not None and result['victim_death']!=control['victim_death']
    assert all(action[3] is True and action[4] is True for action in result['actions'])
    assert all(action[3] is True and action[4] is None for action in control['actions'])
    result['causal_control_validated']=True


def one(name,case,prefix,control=False):
    out=dict(case=name,victim=list(case['victim']),requested_ticks=case['end'],completed_ticks=0,
        status='ERROR',native='python-control' if control else 'not-started',
        actions=[],first_mismatch=None,victim_death=None,victim_observations=[])
    b=cfg=native=None
    operation='setup';offset=None;completed_steps=[]
    try:
        need={0:[],1:[]}
        for op in case['setup']:
            if op[0]=='deploy': need[op[1]].append(op[2])
        for _,side,card,_ in case['script']:
            if card!='ABILITY': need[side].append(card)
        cards=tuple(dict.fromkeys(need[0]+need[1]+list(A.FILL)))[:8]
        cfg=D.config(cards); b=D.initial(7,cards=cards)
        for side,player in enumerate(b.players):
            mine=list(dict.fromkeys(need[side])); player.elixir=10
            player.hand=(mine+[card for card in cards if card not in mine])[:4]
            player.cycle_queue.clear();player.cycle_queue.extend(card for card in cards if card not in player.hand)
        for op in case['setup']:
            if op[0]=='deploy':
                assert b.deploy_card(op[1],op[2],D.Position(*op[3])),op
                b.players[op[1]].elixir=10
            elif op[0]=='step':
                for _ in range(op[1]): b.step()
            elif op[0] in ('hp','move'):
                found=A.find(b,op[1],op[2]); assert found,('missing setup subject',op)
                for entity in found:
                    if op[0]=='hp': entity.hitpoints=float(op[3])
                    else: entity.position=D.Position(*op[3])
            else: raise AssertionError(('unknown setup operation',op))
        for player in b.players: player.elixir=10
        if control:
            # Counterfactual after the shared setup window: no enemy attacker,
            # including pre-existing crown towers in tower-shot fixtures. Keep
            # victim creation commands, HP/placement/setup time and its stats.
            removed=[eid for eid,entity in b.entities.items() if entity.player_id!=case['victim'][0]]
            for eid in removed: del b.entities[eid]
            out['removed_opponent_ids']=removed
        initial=json.loads(D.snapshot(b,cfg)); out['initial']=initial
        with prefix.with_name(prefix.name+'-initial.json').open('x') as stream: json.dump(initial,stream)
        native=None if control else D.clasher_core.BattleState(json.dumps(initial))
        victims=[]; seen=set()
        def observe_victims():
            for entity in A.find(b,*case['victim']):
                if entity.id in seen: continue
                seen.add(entity.id);victims.append(entity)
                out['victim_observations'].append(dict(id=entity.id,owner=entity.player_id,
                    name=entity.card_stats.name,x=entity.position.x,y=entity.position.y,
                    observed_tick=b.tick,hp=entity.hitpoints,
                    stats_sha256=hashlib.sha256(json.dumps(D.entity(entity)['stats'],sort_keys=True).encode()).hexdigest()))
        observe_victims()
        bytick={}
        for tick,side,card,tile in case['script']: bytick.setdefault(tick,[]).append((side,card,tile))
        for tick in range(case['end']):
            offset=tick;operation='before';completed_steps=[]
            out['last_before']=dict(python=json.loads(D.snapshot(b,cfg)),native=None if control else json.loads(native.snapshot()))
            previous_hp=sum(entity.hitpoints for entity in victims if entity.is_alive)
            operation='actions'
            for side,card,tile in bytick.get(tick,[]):
                if card=='ABILITY':
                    py=bool(b.activate_champion_ability(side));rs=None if control else bool(native.activate_champion_ability(side))
                else:
                    py=bool(b.deploy_card(side,card,D.Position(*tile)));rs=None if control else bool(native.apply_action(side,card,*tile))
                out['actions'].append([tick,side,card,py,rs]); assert py,('rejected Python action',tick,card)
                if not control and py!=rs and out['first_mismatch'] is None: out['first_mismatch']='action@'+str(tick)
                observe_victims()
            if previous_hp==0: previous_hp=sum(entity.hitpoints for entity in victims if entity.is_alive)
            previous_tick=b.tick
            operation='python/step'
            b.step()
            completed_steps.append('python');operation='python/tickguard'
            assert b.tick==previous_tick+1,'fixture/control stopped advancing'
            if native is not None:
                operation='native/step';native.step(1);completed_steps.append('native')
            operation='post-step-validation'
            observe_victims();out['completed_ticks']=tick+1
            if out['victim_death'] is None and victims and not any(entity.is_alive for entity in victims):
                out['victim_death']=tick;out['hp_before_death']=previous_hp
            if not control and native.digest()!=D.battle_digest(b) and out['first_mismatch'] is None: out['first_mismatch']=tick
            if out['first_mismatch'] is not None:
                out['first_context']=dict(before=out['last_before'],after=dict(python=json.loads(D.snapshot(b,cfg)),native=json.loads(native.snapshot())))
                break
        assert victims,'fixture never created its intended victim'
        out['native']='python-control' if control else 'ok'
        out['status']='CONTROL_COMPLETE' if control else 'COMPLETE' if out['first_mismatch'] is None else 'MISMATCH'
        out['final_digest']=D.battle_digest(b)
    except BaseException:
        out.update(status='ERROR',error=traceback.format_exc(limit=8))
        context=dict(offset=offset,operation=operation,completed_steps=completed_steps,
            before=out.get('last_before'),after={},root_capture_errors=[])
        for label,arm in (('python',b),('native',native)):
            if arm is None:
                context['after'][label]=None
                continue
            try:
                encoded=D.snapshot(arm,cfg) if label=='python' else arm.snapshot()
                context['after'][label]=json.loads(encoded)
            except BaseException:
                error=traceback.format_exc(limit=8)
                context['after'][label]=dict(unavailable_error=error)
                context['root_capture_errors'].append(dict(arm=label,error=error))
        out['exception_context']=context
        if not control: out['native']='error'
    return out


def main():
    output=Path(sys.argv[1]);assert not output.exists();results=[]
    for name,blue in A.CASES.items():
        for seat,case in (('blue',blue),('red',A.mirror(blue))):
            identity=name+'/'+seat;prefix=output.with_name(output.stem+'-'+str(len(results)))
            result=one(identity,case,prefix)
            result['control']=one(identity,control_case(case),prefix.with_name(prefix.name+'-control'),control=True)
            result['control_death']=result['control']['victim_death']
            try: validate_pair(result)
            except BaseException: result['validation_error']=traceback.format_exc(limit=6)
            results.append(result)
            with prefix.with_name(prefix.name+'-result.json').open('x') as stream: json.dump(result,stream,indent=1)
            print(identity,result['status'],result.get('first_mismatch'),'control',result['control']['status'],bool(result.get('causal_control_validated')),flush=True)
    with output.open('x') as stream: json.dump(results,stream,indent=1)
    raise SystemExit(0 if len(results)==42 and all(row.get('causal_control_validated') for row in results) else 1)


if __name__=='__main__': main()
