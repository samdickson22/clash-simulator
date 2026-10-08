"""Fresh, scoring-only public development traces; no search or win metrics."""
import bootstrap
from bootstrap import HERE,ROOT
import argparse,copy,gzip,importlib.util,json,random,time
from collections import deque
from dataclasses import asdict,replace
import numpy as np
from fair_player import Resources,observe
from clasher.battle import BattleState
from clasher.player import PlayerState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.contract_v5 import champion_ability_cost
from noise import Sensor,SeenEvent
from board import body_card_map,public_bodies
from evaluate import write

def schedule():
    spec=importlib.util.spec_from_file_location('decks',ROOT/'reports/strategy_council_20260928/engine-speed/stage5/decks.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);cats=m.catalogs()
    held={}
    for role in ('eval','eval_ood'):
        for d in cats[role]['decks']:held[tuple(d['cards'])]=held.get(tuple(d['cards']),0)+d['frequency']
    supported={tuple(sorted(d['cards'])) for d in cats['train']['decks']}
    held=[dict(cards=list(d),frequency=n) for d,n in held.items() if tuple(sorted(d)) in supported]
    families=['Hog 2.6','Hog EQ/Firecracker/MM','Royal Hogs/Furnace','X-Bow','bait','Goblinstein','AQ']
    rows=[]
    for i in range(56):
        rng=random.Random(9730800001+1009*i);family=families[i%7]
        def choose(ds):return list(rng.choices(ds,weights=[d['frequency'] for d in ds])[0]['cards'])
        a=choose([d for d in held if m.family(d['cards'])==family]);b=choose(cats['train']['decks']);rng.shuffle(a);rng.shuffle(b)
        rows.append(dict(index=i,seed=9730800001+1009*i,noise_seed=9830800001+1009*i,decks=[a,b],family=family,style=('balanced','pressure','defense')[i%3]))
    return rows

def run(r,index):
    assert json.loads((HERE/'seed-audit-127x04.json').read_text())['passed']
    ep=schedule()[index];folder=HERE/'dev-traces';folder.mkdir(exist_ok=True)
    target=folder/f'{index:03d}.json.gz';assert not target.exists()
    decks=ep['decks'];b=BattleState(players=[PlayerState(i,deck=d,hand=d[:4],cycle_queue=deque(d[4:])) for i,d in enumerate(decks)],rng=random.Random(ep['seed']),card_loader=r.builder.loader)
    variants=('T2-N97','T2-N90','T2-N64')
    sensors={(seat,v):Sensor(v,ep['noise_seed']+seat,r.builder) for seat in (0,1) for v in variants}
    latency={(s,v):np.random.default_rng(ep['noise_seed']+500+s) for s,v in sensors}
    frames={key:deque() for key in sensors};public=[[],[]];rows=[];cpu=time.process_time();space=DiscreteTileActionSpace();seen={key:0 for key in sensors}
    while not b.game_over:
        if b.tick>=90 and b.tick%2==0:
            moves={}
            for seat in (0,1):
                info=observe(b,r.builder,seat,())
                for v in variants:
                    key=(seat,v);sensor=sensors[key];sensor.ingest(public[1-seat]);events=sensor.deliver(b.tick)
                    packet=sensor.capture(info);lag=4 if latency[key].random()<.98 else 8
                    frames[key].append((b.tick,packet));ready=[x for x in frames[key] if x[0]<=b.tick-lag]
                    if ready:
                        rows.append(dict(tick=b.tick,seat=seat,variant=v,bodies=public_bodies(ready[-1][1]),
                            events=[asdict(e) for e in events[seen[key]:]],truth_elixir=b.players[1-seat].elixir,truth_hand=list(b.players[1-seat].hand)))
                        seen[key]=len(events)
                    while frames[key] and frames[key][0][0]<b.tick-20:frames[key].popleft()
                moves[seat]=int(r.bots[ep['style'] if seat else 'balanced'].select_action(info.packet))
            for seat,a in moves.items():
                if a==2304:continue
                name='';amount=0.;x=y=None
                if a==2305:
                    found=b._champion_ability_mechanic(seat)
                    if found is not None:
                        name=found[0].card_stats.name
                        if name=='Goblinstein_doctor':name='Goblinstein'
                        amount=champion_ability_cost(name,loader=r.builder.loader)
                else:
                    name=b.players[seat].hand[a//576]
                    action=space.decode_action(a,seat);x=action.position.x;y=action.position.y
                ok=space.apply_action(b,seat,a)
                if ok:public[seat].append(SeenEvent(b.tick,'ability' if a==2305 else 'card',name,amount,x,y,f'{seat}-{len(public[seat])}'))
        b.step()
        if b.tick>6100:raise RuntimeError('nonterminal')
    payload=dict(episode=ep,costs=r.costs,body_cards=body_card_map(r),rows=rows,audits={f'{s}-{v}':x.audit for (s,v),x in sensors.items()})
    tmp=target.with_suffix('.tmp')
    with gzip.open(tmp,'wt') as f:json.dump(payload,f,separators=(',',':'))
    tmp.replace(target)
    write(folder/f'{index:03d}-receipt.json',dict(index=index,terminal=True,ticks=b.tick,cpu_seconds=time.process_time()-cpu,rows=len(rows)))
    print(json.dumps(dict(index=index,terminal=True,rows=len(rows))),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--index',type=int,required=True);args=ap.parse_args();run(Resources(),args.index)
