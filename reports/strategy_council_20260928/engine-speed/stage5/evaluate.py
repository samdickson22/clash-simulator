"""Pinned, resumable public C56 matches. Development and confirmation stay separate."""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import random
import time
import numpy as np
import torch
from fair_player import Resources,PublicPlanner,observe
from derived_public_state import PublicEvent
from stage2_matches import battle
from qualify import write
from decks import family

torch.set_num_threads(1);torch.set_num_interop_threads(1)
HERE=Path(__file__).resolve().parent


def verify_manifest(manifest):
    for path,want in manifest['files'].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==want,('source changed',path)


def game(r,prior,ep,seat):
    own=ep['planning_deck'];other=ep['opponent_deck'];decks=[own,other] if seat==0 else [other,own]
    b=battle(dict(seed=ep['seed'],decks=decks),r.builder.loader)
    seed=ep['seed']+100000+seat
    p=PublicPlanner(r,prior,seed)
    p.decide(observe(b,r.builder,seat,[]),0)
    p.core.rng=np.random.default_rng(seed);p.rng=np.random.default_rng(seed+1);p.last=None
    events=[];timings=[];actions=[];checks=0;hand_known=cycle_known=0
    abilities={name:dict(opportunities=0,attempts=0,accepted=0) for name in own if name in ('ArcherQueen','MightyMiner','Goblinstein')}
    rejected=[0,0]
    while not b.game_over:
        if b.tick>=90 and b.tick%5==0:
            start=time.perf_counter();cpu=time.process_time()
            info=observe(b,r.builder,seat,events)
            a,searched=p.decide(info,(b.tick-90)//5)
            timings.append([time.perf_counter()-start,time.process_time()-cpu,searched])
            # Truth is verifier-only and stays outside timed player input.
            enemy=b.players[1-seat]
            assert p.belief.elixir==enemy.elixir,('derived elixir',b.tick,p.belief.elixir,enemy.elixir)
            known=p.belief.derived();checks+=1
            if known['hand'] is not None:
                assert sorted(known['hand'],key=lambda n:n or '')==sorted(enemy.hand,key=lambda n:n or '')
                hand_known+=1
            if known['cycle'] is not None:
                assert known['cycle']==tuple(enemy.cycle_queue);cycle_known+=1
            other_action=r.bots[ep['style']].select_action(r.builder.build_public(b,1-seat))
            found=b._champion_ability_mechanic(seat)
            active_champion=None if found is None else found[0].card_stats.name
            if active_champion=='Goblinstein_doctor':active_champion='Goblinstein'
            if active_champion in abilities:
                abilities[active_champion]['opportunities']+=int(b.can_activate_champion_ability(seat))
            for actor,move in sorted(((seat,a),(1-seat,other_action))):
                if move==2304:continue
                name=b.players[actor].hand[move//576] if move<2304 else active_champion or 'ability'
                ok=p.core.space.apply_action(b,actor,move)
                rejected[int(actor!=seat)]+=not ok
                actions.append([b.tick,actor,int(move),name,bool(ok)])
                if actor==1-seat and ok:
                    assert move<2304,'public opponent scripts mask abilities'
                    events.append(PublicEvent(b.tick,'card',name))
                if actor==seat and move==2305:
                    abilities[name]['attempts']+=1;abilities[name]['accepted']+=int(ok)
        b.step()
    score=.5 if b.winner is None else float(b.winner==seat)
    walls=[t[0] for t in timings];searchwalls=[t[0] for t in timings if t[2]]
    return dict(pair=ep['pair'],seed=ep['seed'],seat=seat,family=ep['family'],style=ep['style'],
        decks=decks,ticks=b.tick,winner=b.winner,score=score,abilities=abilities,rejected=rejected,
        wall_cpu_search=timings,actions=actions,derived_checks=checks,hand_determined=hand_known,cycle_determined=cycle_known,
        timing=dict(p99=float(np.quantile(walls,.99)),max=max(walls),search_p99=float(np.quantile(searchwalls,.99)) if searchwalls else 0,
                    search_max=max(searchwalls,default=0),overruns=sum(t>.25 for t in walls)),
        host=dict(load=os.getloadavg(),pid=os.getpid(),nice=os.getpriority(os.PRIO_PROCESS,0),torch_threads=torch.get_num_threads()))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['development','confirmation'],required=True);ap.add_argument('--worker',type=int,default=0);ap.add_argument('--workers',type=int,default=1);ap.add_argument('--games',type=int,default=8);args=ap.parse_args()
    prior=json.loads((HERE.parent.parent/'c56/engine/root-v3/human_deck_catalog.json').read_text())
    manifest=None
    if args.mode=='confirmation':
        manifest=json.loads((HERE/'evaluation-manifest.json').read_text());verify_manifest(manifest)
        schedule=json.loads((HERE/'schedule.json').read_text())['pairs']
        manifest_sha=hashlib.sha256((HERE/'evaluation-manifest.json').read_bytes()).hexdigest()
    else:
        selected=[]
        for name in ['Hog 2.6','Hog EQ/Firecracker/MM','Royal Hogs/Furnace','X-Bow','bait','Goblinstein','AQ']:
            selected.append(max((d for d in prior['decks'] if family(d['cards'])==name),key=lambda d:d['frequency']))
        schedule=[]
        for i in range(args.games):
            seed=880800+i;rng=random.Random(seed);own=list(selected[i%7]['cards']);other=list(selected[(i+3)%7]['cards']);rng.shuffle(own);rng.shuffle(other)
            schedule.append(dict(pair=i,seed=seed,family=family(own),style=('balanced','pressure','defense')[i%3],planning_deck=own,opponent_deck=other))
        source_paths=[HERE/n for n in ('fair_player.py','derived_public_state.py','decks.py','evaluate.py')]
        manifest_sha=hashlib.sha256(b''.join(p.read_bytes() for p in source_paths)).hexdigest()
    r=Resources();folder=HERE/args.mode
    if args.mode=='development':folder=folder/manifest_sha[:12]
    folder.mkdir(parents=True,exist_ok=True)
    work=[(ep,seat) for ep in schedule for seat in ((0,1) if args.mode=='confirmation' else (ep['pair']%2,))]
    for index,(ep,seat) in enumerate(work):
        if index%args.workers!=args.worker:continue
        path=folder/f"pair{ep['pair']:03d}-seat{seat}.json"
        if path.exists():
            previous=json.loads(path.read_text());assert previous['manifest']==manifest_sha
            continue
        if manifest:verify_manifest(manifest)
        row=game(r,prior,ep,seat);row['manifest']=manifest_sha
        write(path,row);print({k:row[k] for k in ('pair','seed','seat','ticks','timing','abilities')},flush=True);gc.collect()
    write(HERE/f'{args.mode}-worker{args.worker}-done.json',dict(complete=True,manifest=manifest_sha,pid=os.getpid()))

if __name__=='__main__':main()
