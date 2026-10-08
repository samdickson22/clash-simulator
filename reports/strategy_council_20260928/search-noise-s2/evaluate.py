"""Terminal paired games, atomic receipts and no interim strength reporting."""
import bootstrap
from bootstrap import HERE,ROOT,RUNTIME
import argparse,copy,gc,hashlib,json,math,os,random,time,traceback
from collections import deque,Counter
from dataclasses import replace
from pathlib import Path
import numpy as np
import torch
from fair_player import Resources,observe
from clasher.battle import BattleState
from clasher.player import PlayerState
from clasher.rl.contract_v5 import champion_ability_cost
from noise import Sensor,SeenEvent,VARIANTS,MODEL
from cells import CELLS,H2H
from player import Player
from derived_public_state import DerivedPublicState
from trace import snapshot

torch.set_num_threads(1);torch.set_num_interop_threads(1)

def write(path,data):
    path=Path(path);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,separators=(',',':'))+'\n');tmp.replace(path)

def verify(manifest):
    for rel,want in manifest['files'].items():
        p=HERE/rel
        if hashlib.sha256(p.read_bytes()).hexdigest()!=want:raise RuntimeError(f'Frozen file changed: {rel}')

def game(r,prior,ep,seat,variant,*,max_tick=None,trace_enabled=True):
    decks=copy.deepcopy([ep['planning_deck'],ep['opponent_deck']])
    if ep['mode']=='scripts' and seat:decks.reverse()
    b=BattleState(players=[PlayerState(i,deck=d,hand=d[:4],cycle_queue=deque(d[4:])) for i,d in enumerate(decks)],rng=random.Random(ep['seed']),card_loader=r.builder.loader)
    players={seat:Player(r,prior,ep['seed']+100000+seat,variant)}
    if ep['mode']=='head-to-head':players[1-seat]=Player(r,prior,ep['seed']+100000+(1-seat),'A')
    sensors={i:Sensor(p.variant,ep['noise_seed']+i,r.builder) for i,p in players.items()}
    for sensor in sensors.values():sensor.identity_templates={key:value for key,value in r.templates.items() if key[0] in r.bots['balanced'].bodies}
    latency_rng={i:np.random.default_rng(ep['noise_seed']+500+i) for i in players}
    failure_rng={i:np.random.default_rng(ep['noise_seed']+700+i) for i in players}
    latency_model=json.loads((HERE/'latency.json').read_text())
    failures=Counter();attempts=Counter();elt_trace=[]
    trace_cell=trace_enabled and variant in ('A+derived','R-events')
    game_cpu=time.process_time()
    public=[[],[]];frames={i:deque() for i in players};latest={};pending={};timings={i:[] for i in players};rejected=[0,0]
    action_hash=hashlib.sha256();action_count=0;checks=0;truncations=fallbacks=0;begin=time.time()
    # Initialization is identical and excluded from decision timings.
    for i,p in players.items():
        info=observe(b,r.builder,i,());p.decide(info,0,time.perf_counter()+.2)
        seed=ep['seed']+100000+i;p.rng=np.random.default_rng(seed+1);p.core.rng=np.random.default_rng(seed)
    while not b.game_over:
        moves={}
        if b.tick>=90 and b.tick%2==0:
            for actor,p in players.items():
                sensor=sensors[actor];sensor.ingest(public[1-actor]);events=sensor.deliver(b.tick)
                started=time.perf_counter()
                clean=observe(b,r.builder,actor,())
                info=sensor.capture(clean)
                sensor_wall=time.perf_counter()-started
                level=p.cell['latency']
                if level=='clean':lag=0
                elif level=='old':lag=3
                elif level=='target':lag=4 if latency_rng[actor].random()<.98 else 8
                else:lag=max(1,int(math.ceil(float(latency_rng[actor].choice(latency_model['l2_ms']))/50)))
                # Sample observation age at each poll, so variable latency cannot
                # create artificial head-of-line blocking in a FIFO arrival queue.
                frames[actor].append((b.tick,info,sensor_wall))
                ready=[row for row in frames[actor] if row[0]<=b.tick-lag]
                if ready:latest[actor]=ready[-1][1]
                # Keep enough history for every frozen empirical latency sample.
                while frames[actor] and frames[actor][0][0]<b.tick-latency_model['max_ticks']-4:
                    frames[actor].popleft()
                if actor in pending or actor not in latest:continue
                # The clock is exact and extrapolated from public elapsed time.
                info=replace(latest[actor],tick=b.tick,events=events)
                start=time.perf_counter();cpu=time.process_time()
                a,searched=p.decide(info,(b.tick-90)//2,deadline=start+.2-sensor_wall,public_truth=tuple(public[1-actor]))
                if trace_cell and actor==seat:
                    elt_trace.append(snapshot(p.belief,b.tick,b.players[1-actor].elixir,b.players[1-actor].hand))
                wall=time.perf_counter()-start+sensor_wall
                timings[actor].append([wall,time.process_time()-cpu,bool(searched)])
                if actor==seat and p.core.deadline_stats:
                    truncations+=int(p.core.deadline_stats['truncated']);fallbacks+=int(p.core.deadline_stats['fallback'])
                if isinstance(p.belief,DerivedPublicState):
                    assert abs(p.belief.elixir-b.players[1-actor].elixir)<1e-7,(b.tick,p.belief.elixir,b.players[1-actor].elixir)
                    d=p.belief.derived();actual=b.players[1-actor]
                    if d['hand'] is not None:assert sorted(d['hand'],key=lambda n:n or '')==sorted(actual.hand,key=lambda n:n or '')
                    checks+=1
                if a!=2304:
                    delay=0 if level=='clean' else (2 if level=='old' else 0)
                    pending[actor]=(b.tick+delay,int(a),False)
                    attempts[actor]+=1
                    if p.arm.startswith('E'):p.own_state.submit(p.last_info,int(a),r.costs,r.builder)
                if b.tick%20==10:p.diagnostic(b.players[1-actor].elixir,b.players[1-actor].hand)
            # Script cadence is also 10 Hz; both controllers choose before application.
            for actor in (0,1):
                if actor not in players:moves[actor]=int(r.bots[ep['style']].select_action(r.builder.build_public(b,actor)))
        for actor in list(pending):
            due,action,retry=pending[actor]
            if due<=b.tick:
                if not retry and failure_rng[actor].random()<players[actor].cell['failure']:
                    failures[actor]+=1;pending[actor]=(b.tick+3,action,True)
                else:
                    moves[actor]=action;del pending[actor]
        for actor in (0,1):
            a=moves.get(actor,2304)
            if a==2304:continue
            name='';amount=0.;x=y=None
            if a==2305:
                found=b._champion_ability_mechanic(actor)
                if found is not None:
                    name=found[0].card_stats.name
                    if name=='Goblinstein_doctor':name='Goblinstein'
                    amount=champion_ability_cost(name,loader=r.builder.loader)
            else:
                name=b.players[actor].hand[a//576]
                decoded=players[seat].core.space.decode_action(a,actor);x=decoded.position.x;y=decoded.position.y
            ok=players[seat].core.space.apply_action(b,actor,a)
            rejected[int(actor!=seat)]+=not ok;action_count+=1
            action_hash.update(json.dumps([b.tick,actor,a,name,bool(ok)]).encode())
            if ok:public[actor].append(SeenEvent(b.tick,'ability' if a==2305 else 'card',name,amount,x,y,f'{actor}-{len(public[actor])}'))
        b.step()
        # Own verification follows execution; use the next public noisy HUD packet.
        for actor in moves:
            if actor in players and players[actor].arm.startswith('E'):
                cue=sensors[actor].capture(observe(b,r.builder,actor,()))
                players[actor].own_state.reconcile(cue)
        if max_tick and b.tick>=max_tick:break
        if b.tick>6100:raise RuntimeError('Unexpected nonterminal game beyond time limit')
    walls=np.array([t[0] for t in timings[seat]])
    return dict(pair=ep['pair'],seed=ep['seed'],noise_seed=ep['noise_seed'],seat=seat,variant=variant,mode=ep['mode'],family=ep['family'],style=ep['style'],decks=decks,
        terminal=b.game_over,ticks=b.tick,winner=b.winner,score=(.5 if b.winner is None else float(b.winner==seat)) if b.game_over else None,
        timing=dict(decisions=len(walls),p50=float(np.quantile(walls,.5)) if len(walls) else 0,p99=float(np.quantile(walls,.99)) if len(walls) else 0,max=float(max(walls)) if len(walls) else 0,overruns=int(sum(walls>.25)),truncations=truncations,fallbacks=fallbacks),
        elt_trace=elt_trace,event_audit=sensors[seat].audit if trace_cell else [],perception=dict(sensors[seat].counts),derived=dict(players[seat].diagnostics),exact_checks=checks,rejected=rejected,action_count=action_count,action_sha256=action_hash.hexdigest(),
        host=dict(load=os.getloadavg(),pid=os.getpid(),nice=os.getpriority(os.PRIO_PROCESS,0),native_threads=1,hostname=__import__('socket').gethostname()),started=begin,elapsed=time.time()-begin,cpu_seconds=time.process_time()-game_cpu,failed_taps=failures[seat],tap_attempts=attempts[seat])
