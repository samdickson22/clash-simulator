#!/usr/bin/env python3
"""Controlled spell geometry/duration probes, using instantiated entities only.

Each trial has one level-11 Knight with HP raised to 10000 and speed set to zero
in both engines. It stands at x=9+offset, y=19.5 (offense) or y=12.5 (Rage),
away from enemy tower fire; the spell is normally deployed at x=9, same y.
This isolates hitbox coverage and effect clocks.
RoyaleSim's public reset(spawns=) and save/load are used; no upstream tables are
ported or saved. RoyaleSim is MIT licensed.
"""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import argparse
import json
import traceback

from scenarios import START, adapters, fixture, make_engine, load_edited_snapshot

OFFSETS = [0, 1.5, 2, 2.49, 2.5, 2.51, 2.99, 3, 3.01, 3.49, 3.5, 3.51, 3.99, 4, 4.01, 4.49, 4.5, 4.51, 5]
CARDS = ['Freeze','Snowball','Vines','Rage','DarkMagic','GoblinCurse']


def trial(name, offset, kind, table):
    e, ids = make_engine(kind,[name],['Knight'],table)
    _,_,Play=adapters()
    side = 0 if name=='Rage' else 1
    cy = 12.5 if side == 0 else 19.5
    if kind=='ours':
        from clasher.arena import Position
        uid=e.b.next_entity_id
        e.b._spawn_unit_at_position(Position(9+offset,cy),side,e.b.card_loader.get_card('Knight'),
                                   deploy_delay_override=0,snap_to_valid=False)
        u=e.b.entities[uid];u.speed=0;u.hitpoints=u.max_hitpoints=10000
    else:
        _,fix=fixture([name],['Knight'])
        id_to_name={v:k for k,v in ids.items()}
        decks=[[e._idx(id_to_name[i]) for i in fix.initial_order[s]] for s in (0,1)]
        e.b.reset(seed=START,decks=decks,shuffle=0,start_tick=START,elixir_milli=[10000]*2,
                  tower_hp=None,spawns=[(side,e._idx('Knight'),int((9+offset)*1000*e.sub),int(cy*1000*e.sub),10000)])
        es=json.loads(e.b.save());es['ents']['speed'][-1]=0;es['ents']['max_hp'][-1]=10000
        uid=es['ents']['team_seq'][-1]*2+side
        load_edited_snapshot(e.b, es);e._state=None
    play=Play(side=0,card=name,card_id=ids[name],kind='card',tile=(9,cy),exec_tick=START,command_tick=START,slot=-1)
    ok=e.deploy(play)
    events=[]; effects=[]; hp=10000; max_duration=0
    positions=[]
    for t in range(1,321):
        e.step()
        if kind=='ours':
            u=e.b.entities.get(uid)
            if not u: break
            nhp=round(u.hitpoints)
            durations=[u.stun_timer,u.slow_timer,u.haste_timer]
            durations += [v.remaining for v in u._periodic_damage_effects.values()]
            active=any(d>1e-8 for d in durations)
            max_duration=max(max_duration,round(max(durations)*20))
            p=[round(u.position.x,4),round(u.position.y,4)]
        else:
            F=e.F
            u=next((r for r in e._st()['entities'] if r[F['uid']]==uid),None)
            if u is None:break
            nhp=u[F['hp']]
            durations=[u[F['stun_ticks']]]+[int((v[1]+49)//50) for v in u[F['buffs']]]
            active=any(d>0 for d in durations)
            max_duration=max(max_duration,max(durations,default=0))
            p=[round(u[F['x']]/e.sub/1000,4),round(u[F['y']]/e.sub/1000,4)]
        if hp!=nhp:events.append([t,hp-nhp])
        hp=nhp
        if active:effects.append(t)
        if t in (1,20,40,80,160,320):positions.append([t,*p])
    return dict(deploy_ok=bool(ok),damage=10000-hp,hits=events,
                effect_first=effects[0] if effects else None,effect_last=effects[-1] if effects else None,
                effect_ticks=len(effects),max_effect_remaining_ticks=max_duration,positions=positions,
                counters=dict(e.counters))


def paired(task):
    name,offset,table=task
    r=dict(card=name,scenario='stationary_knight',offset_tiles=offset,table=table,
           intervention='Knight speed=0; hp=max_hp=10000; only spell follows normal deploy path')
    for k in ('ours','rsim'):
        try:r[k]=trial(name,offset,k,table)
        except Exception:r[k]=dict(error=traceback.format_exc())
    diffs=[]
    if any('error' in r[k] for k in ('ours','rsim')):
        r['verdict']='HARNESS-GAP'
    else:
        for f in ('damage','effect_first','effect_last','effect_ticks','max_effect_remaining_ticks'):
            x,y=r['ours'][f],r['rsim'][f]
            equal=abs(x-y)<=1 if x is not None and y is not None else x==y
            if not equal:diffs.append(dict(metric=f,ours=x,royalesim=y))
        a,b=r['ours']['hits'],r['rsim']['hits']
        if len(a)!=len(b):diffs.append(dict(metric='hit_count',ours=len(a),royalesim=len(b)))
        for i,(x,y) in enumerate(zip(a,b)):
            if abs(x[0]-y[0])>1 or abs(x[1]-y[1])>1:
                diffs.append(dict(metric=f'hit[{i}]',ours=x,royalesim=y))
        r['verdict']='DIFF' if diffs else 'PASS'
    r['differences']=diffs
    return r


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    p.add_argument('--workers',type=int,default=4);p.add_argument('--cards',nargs='+',default=CARDS)
    p.add_argument('--offsets',nargs='+',type=float,default=OFFSETS);p.add_argument('--table',default='adapter')
    a=p.parse_args();tasks=[(n,d,a.table) for n in a.cards for d in a.offsets]
    with ProcessPoolExecutor(a.workers) as ex,a.out.open('w') as f:
        for r in ex.map(paired,tasks):
            f.write(json.dumps(r,separators=(',',':'))+'\n');f.flush()
            print(r['card'],r['offset_tiles'],r['verdict'],flush=True)


if __name__=='__main__':main()
