"""Prospective paired public C56 games; no interim strength reporting."""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import numpy as np
import torch
from fair_player import Resources, PublicPlanner, observe
from deadline_player import DeadlinePublicPlanner
from derived_public_state import PublicEvent
from clasher.rl.contract_v5 import champion_ability_cost
from stage2_matches import battle
from qualify import write

torch.set_num_threads(1); torch.set_num_interop_threads(1)
HERE=Path(__file__).resolve().parent

def verify_manifest(manifest):
    for path, want in manifest['files'].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==want, ('source changed',path)

def check_belief(p,b,seat):
    enemy=b.players[1-seat];known=p.belief.derived()
    assert p.belief.elixir==enemy.elixir, ('derived elixir',b.tick,seat,p.belief.elixir,enemy.elixir)
    if known['hand'] is not None:
        assert sorted(known['hand'],key=lambda n:n or '')==sorted(enemy.hand,key=lambda n:n or '')
    if known['cycle'] is not None:assert known['cycle']==tuple(enemy.cycle_queue)

def game(r,prior,ep,seat):
    decks=[ep['planning_deck'],ep['opponent_deck']]
    if seat and ep['mode']=='scripts':decks.reverse()
    b=battle(dict(seed=ep['seed'],decks=decks),r.builder.loader)
    candidate=DeadlinePublicPlanner(r,prior,ep['seed']+100000+seat)
    baseline=PublicPlanner(r,prior,ep['seed']+100000+(1-seat)) if ep['mode']=='head-to-head' else None
    players={seat:candidate}
    if baseline:players[1-seat]=baseline
    for actor,p in players.items():
        seed=ep['seed']+100000+actor
        p.decide(observe(b,r.builder,actor,[]),0)
        p.core.rng=np.random.default_rng(seed);p.rng=np.random.default_rng(seed+1);p.last=None
    events=[[],[]];timings=[];baseline_timings=[];actions=[];rejected=[0,0];checks=0
    abilities={};truncations=fallbacks=completed=total=0
    begin=time.time()
    while not b.game_over:
        if b.tick>=90 and b.tick%5==0:
            moves={}
            # Fixed order of decision calls; actions are applied only after both.
            for actor in (0,1):
                p=players.get(actor)
                if p is None:
                    moves[actor]=int(r.bots[ep['style']].select_action(r.builder.build_public(b,actor)))
                    continue
                start=time.perf_counter();cpu=time.process_time()
                info=observe(b,r.builder,actor,events[1-actor])
                if actor==seat:a,searched=p.decide(info,(b.tick-90)//5,deadline=start+.2)
                else:a,searched=p.decide(info,(b.tick-90)//5)
                wall=time.perf_counter()-start;cpu=time.process_time()-cpu
                moves[actor]=int(a)
                target=timings if actor==seat else baseline_timings
                target.append([wall,cpu,bool(searched)])
                if actor==seat and p.core.deadline_stats:
                    st=p.core.deadline_stats
                    truncations+=st['truncated'];fallbacks+=st['fallback'];completed+=st['completed'];total+=st['total']
                check_belief(p,b,actor);checks+=1
            for actor in (0,1):
                a=moves[actor]
                if a==2304:continue
                if a==2305:
                    found=b._champion_ability_mechanic(actor)
                    assert found is not None
                    name=found[0].card_stats.name
                    if name=='Goblinstein_doctor':name='Goblinstein'
                else:name=b.players[actor].hand[a//576]
                ok=candidate.core.space.apply_action(b,actor,a)
                rejected[int(actor!=seat)]+=not ok
                actions.append([b.tick,actor,a,name,bool(ok)])
                if ok:
                    if a==2305:
                        events[actor].append(PublicEvent(b.tick,'ability',name,champion_ability_cost(name,loader=r.builder.loader)))
                        key=f'{"candidate" if actor==seat else "baseline"}/{name}'
                        abilities[key]=abilities.get(key,0)+1
                    else:events[actor].append(PublicEvent(b.tick,'card',name))
        b.step()
    walls=[t[0] for t in timings];searched=[t[0] for t in timings if t[2]]
    return dict(pair=ep['pair'],seed=ep['seed'],seat=seat,mode=ep['mode'],family=ep['family'],style=ep['style'],decks=decks,
        ticks=b.tick,winner=b.winner,score=.5 if b.winner is None else float(b.winner==seat),
        timings=timings,baseline_timings=baseline_timings,actions=actions,rejected=rejected,abilities=abilities,derived_checks=checks,
        timing=dict(decisions=len(walls),p99=float(np.quantile(walls,.99)),max=max(walls),search_p99=float(np.quantile(searched,.99)) if searched else 0,
                    overruns=sum(t>.25 for t in walls),truncations=truncations,fallbacks=fallbacks,completed_candidates=completed,total_candidates=total),
        host=dict(load=os.getloadavg(),pid=os.getpid(),nice=os.getpriority(os.PRIO_PROCESS,0),native_threads=2),started=begin,elapsed=time.time()-begin)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--worker',type=int,required=True);ap.add_argument('--workers',type=int,default=3);args=ap.parse_args()
    manifest_path=HERE/'evaluation-manifest.json';manifest=json.loads(manifest_path.read_text());verify_manifest(manifest)
    manifest_sha=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    prior=json.loads((HERE.parent.parent/'c56/engine/root-v3/human_deck_catalog.json').read_text())
    schedule=json.loads((HERE/'schedule.json').read_text())['pairs']
    (HERE/f'host-worker{args.worker}.txt').write_text(subprocess.check_output(['ps','-axo','pid,ppid,nice,%cpu,etime,command'],text=True))
    r=Resources();folder=HERE/'confirmation';folder.mkdir(exist_ok=True)
    # Pair-level assignment keeps both seats on one worker.
    for ep in schedule:
        if ep['pair']%args.workers!=args.worker:continue
        for seat in (0,1):
            path=folder/f"pair{ep['pair']:03d}-seat{seat}.json"
            if path.exists():
                assert json.loads(path.read_text())['manifest']==manifest_sha
                continue
            verify_manifest(manifest)
            row=game(r,prior,ep,seat);row['manifest']=manifest_sha
            write(path,row)
            print({k:row[k] for k in ('pair','seat','mode','ticks','timing','elapsed')},flush=True)
            gc.collect()
    verify_manifest(manifest)
    write(HERE/f'worker{args.worker}-done.json',dict(complete=True,pid=os.getpid(),manifest=manifest_sha))

if __name__=='__main__':main()
