"""Terminal paired games, atomic receipts and no interim strength reporting."""
import bootstrap
from bootstrap import HERE,ROOT,RUNTIME
import argparse,copy,gc,hashlib,json,math,os,random,time,traceback
from collections import deque
from dataclasses import replace
from pathlib import Path
import numpy as np
import torch
from fair_player import Resources,observe
from clasher.battle import BattleState
from clasher.player import PlayerState
from clasher.rl.contract_v5 import champion_ability_cost
from noise import Sensor,SeenEvent,VARIANTS,MODEL
from player import Player

torch.set_num_threads(1);torch.set_num_interop_threads(1)

def write(path,data):
    path=Path(path);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,separators=(',',':'))+'\n');tmp.replace(path)

def verify(manifest):
    for rel,want in manifest['files'].items():
        p=HERE/rel
        if hashlib.sha256(p.read_bytes()).hexdigest()!=want:raise RuntimeError(f'Frozen file changed: {rel}')

def game(r,prior,ep,seat,variant,*,max_tick=None):
    decks=copy.deepcopy([ep['planning_deck'],ep['opponent_deck']])
    if ep['mode']=='scripts' and seat:decks.reverse()
    b=BattleState(players=[PlayerState(i,deck=d,hand=d[:4],cycle_queue=deque(d[4:])) for i,d in enumerate(decks)],rng=random.Random(ep['seed']),card_loader=r.builder.loader)
    players={seat:Player(r,prior,ep['seed']+100000+seat,variant)}
    if ep['mode']=='head-to-head':players[1-seat]=Player(r,prior,ep['seed']+100000+(1-seat),'A')
    sensors={i:Sensor(p.variant,ep['noise_seed']+i,r.builder) for i,p in players.items()}
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
                lag=3 if 'latency' in p.flags else 0
                frames[actor].append((b.tick+lag,info,sensor_wall))
                while frames[actor] and frames[actor][0][0]<=b.tick:
                    _,latest[actor],_=frames[actor].popleft()
                if actor in pending or actor not in latest:continue
                # The clock is exact and extrapolated from public elapsed time.
                info=replace(latest[actor],tick=b.tick,events=events)
                start=time.perf_counter();cpu=time.process_time()
                a,searched=p.decide(info,(b.tick-90)//2,deadline=start+.2-sensor_wall)
                wall=time.perf_counter()-start+sensor_wall
                timings[actor].append([wall,time.process_time()-cpu,bool(searched)])
                if actor==seat and p.core.deadline_stats:
                    truncations+=int(p.core.deadline_stats['truncated']);fallbacks+=int(p.core.deadline_stats['fallback'])
                if 'events' not in p.flags:
                    assert abs(p.belief.elixir-b.players[1-actor].elixir)<1e-7,(b.tick,p.belief.elixir,b.players[1-actor].elixir)
                    d=p.belief.derived();actual=b.players[1-actor]
                    if d['hand'] is not None:assert sorted(d['hand'],key=lambda n:n or '')==sorted(actual.hand,key=lambda n:n or '')
                    checks+=1
                if a!=2304:
                    delay=max(2,int(math.ceil(wall/.05))) if 'latency' in p.flags else 0
                    pending[actor]=(b.tick+delay,int(a))
                if b.tick%20==10:p.diagnostic(b.players[1-actor].elixir,b.players[1-actor].hand)
            # Script cadence is also 10 Hz; both controllers choose before application.
            for actor in (0,1):
                if actor not in players:moves[actor]=int(r.bots[ep['style']].select_action(r.builder.build_public(b,actor)))
        for actor in list(pending):
            due,action=pending[actor]
            if due<=b.tick:moves[actor]=action;del pending[actor]
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
        if max_tick and b.tick>=max_tick:break
        if b.tick>6100:raise RuntimeError('Unexpected nonterminal game beyond time limit')
    walls=np.array([t[0] for t in timings[seat]])
    return dict(pair=ep['pair'],seed=ep['seed'],noise_seed=ep['noise_seed'],seat=seat,variant=variant,mode=ep['mode'],family=ep['family'],style=ep['style'],decks=decks,
        terminal=b.game_over,ticks=b.tick,winner=b.winner,score=(.5 if b.winner is None else float(b.winner==seat)) if b.game_over else None,
        timing=dict(decisions=len(walls),p50=float(np.quantile(walls,.5)) if len(walls) else 0,p99=float(np.quantile(walls,.99)) if len(walls) else 0,max=float(max(walls)) if len(walls) else 0,overruns=int(sum(walls>.25)),truncations=truncations,fallbacks=fallbacks),
        perception=dict(sensors[seat].counts),derived=dict(players[seat].diagnostics),exact_checks=checks,rejected=rejected,action_count=action_count,action_sha256=action_hash.hexdigest(),
        host=dict(load=os.getloadavg(),pid=os.getpid(),nice=os.getpriority(os.PRIO_PROCESS,0),native_threads=2),started=begin,elapsed=time.time()-begin)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--worker',type=int,default=0);ap.add_argument('--workers',type=int,default=3);ap.add_argument('--smoke',action='store_true');ap.add_argument('--max-tick',type=int,default=260);args=ap.parse_args()
    import fcntl
    lock=(HERE/f'worker{args.worker}.lock').open('w') if not args.smoke else None
    if lock:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    prior=json.loads((HERE/'runtime/support/human_deck_catalog.json').read_text());r=Resources()
    if args.smoke:
        deck=['HogRider','Musketeer','IceGolem','IceSpirit','Skeletons','Cannon','Fireball','Log']
        ep=dict(pair=-1,seed=3926710201,noise_seed=3926710301,planning_deck=deck,opponent_deck=deck[::-1],mode='scripts',family='Hog 2.6',style='balanced')
        for variant in VARIANTS:
            row=game(r,prior,ep,0,variant,max_tick=args.max_tick);write(HERE/f'development-{args.max_tick}-{variant}.json',row)
            print(variant,row['ticks'],row['elapsed'],row['perception'],flush=True)
        return
    manifest=json.loads((HERE/'evaluation-manifest.json').read_text());verify(manifest);sha=hashlib.sha256((HERE/'evaluation-manifest.json').read_bytes()).hexdigest()
    schedule=json.loads((HERE/'schedule.json').read_text());folder=HERE/'confirmation';folder.mkdir(exist_ok=True)
    jobs=[(ep,v,seat) for ep in schedule['pairs'] for v in (list(VARIANTS) if ep['mode']=='scripts' else list('ABCD')) for seat in (0,1)]
    for job,(ep,variant,seat) in enumerate(jobs):
        if job%args.workers!=args.worker:continue
        path=folder/f"{ep['mode']}-pair{ep['pair']:03d}-{variant}-seat{seat}.json"
        if path.exists():
            old=json.loads(path.read_text());assert old['manifest']==sha and old['terminal'];continue
        verify(manifest)
        if sum(p.stat().st_size for p in HERE.rglob('*') if p.is_file())>280_000_000:raise RuntimeError('Output cap guard')
        write(HERE/f'worker{args.worker}-current.json',dict(pair=ep['pair'],variant=variant,seat=seat,mode=ep['mode'],started=time.time(),pid=os.getpid()))
        row=game(r,prior,ep,seat,variant);assert row['terminal'];row['manifest']=sha;write(path,row)
        print(json.dumps({k:row[k] for k in ('pair','variant','seat','mode','ticks','elapsed','timing')}),flush=True)
        gc.collect()
    verify(manifest);write(HERE/f'worker{args.worker}-done.json',dict(complete=True,manifest=sha,pid=os.getpid(),finished=time.time()))

if __name__=='__main__':main()
