"""Paired fixed-public-state agreement/latency; no game-outcome conclusions."""
import argparse
import copy
import cProfile
import hashlib
import json
import os
from pathlib import Path
import pickle
import pstats
import sys
import time
import numpy as np
import run


def prepare(rows, out):
    from fair_player import PublicPlanner
    from delay import DelayAwarePlanner
    from planner import legacy_class
    from clasher.rl.c56_rollout_planner import C56SearchConfig
    previous = None
    for row in rows:
        if row['seed'] != previous:
            previous = row['seed']
            p = PublicPlanner(run.R,run.PRIOR,row['seed']+100000)
            core = legacy_class(DelayAwarePlanner)(run.R.builder,run.R.bots,backend='native',
                seed=row['seed']+100001,native=run.R.native,native_config=run.R.config,
                catalog=run.CAT,config=C56SearchConfig(threads=1),command_delay=27,delay_aware=True)
        row['candidate_rng_state']=copy.deepcopy(core.rng.bit_generator.state)
        candidates,_=core.candidates(row['info'].packet)
        assert [a for a in candidates if a != 2305] == row['candidates']
        p.belief.update(row['info'].tick,row['info'].events)
        row['opponent']=p.belief.sample(p.rng)
        row['root_rng_state']=copy.deepcopy(p.rng.bit_generator.state)
        rebuilt=run.R.root(row['info'],row['opponent'],p.rng)
        assert rebuilt.digest() == row['root_digest']
    path=out/'states-ready.pkl'
    path.write_bytes(pickle.dumps(rows,protocol=5))
    (out/'ready-manifest.json').write_text(json.dumps(dict(count=len(rows),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        original_sha256=hashlib.sha256((out/'states.pkl').read_bytes()).hexdigest(),
        state_ids=[r['id'] for r in rows],all_public_root_and_candidate_replays_exact=True),indent=2)+'\n')
    return rows


def core_for(mode, row, variant):
    from delay import DelayAwarePlanner
    from planner import legacy_class,planner_class
    from clasher.rl.c56_rollout_planner import C56SearchConfig
    cls=legacy_class(DelayAwarePlanner) if mode=='original' else planner_class(DelayAwarePlanner)
    kw=dict(backend='native',seed=row['seed']+100001,native=run.R.native,native_config=run.R.config,
        catalog=run.CAT,config=C56SearchConfig(threads=1),command_delay=27,delay_aware=True,variant=variant)
    if mode != 'original':kw.update(arm='W',symmetric_opponent=True,opponent_delay=27,opponent_interval=10,opponent_capacity=1)
    core=cls(run.R.builder,run.R.bots,**kw)
    core.rng.bit_generator.state=copy.deepcopy(row['candidate_rng_state'])
    return core


def decision(mode,row,variant,record=True):
    core=core_for(mode,row,variant)
    rng=np.random.default_rng();rng.bit_generator.state=copy.deepcopy(row['root_rng_state'])
    info=copy.deepcopy(row['info'])
    start,cpu0=time.perf_counter(),time.process_time()
    core.info,core.costs=info,run.R.costs
    candidates,_=core.candidates(info.packet)
    candidates=[a for a in candidates if a != 2305]
    assert candidates == row['candidates']
    root=run.R.root(info,row['opponent'],rng)
    constructed=time.perf_counter()
    action=core.score_candidates(root,info.seat,candidates)
    elapsed=time.perf_counter()-start;cpu=time.process_time()-cpu0
    assert root.digest()==row['root_digest']
    return dict(id=row['id'],action=action,wall_ms=elapsed*1000,cpu_ms=cpu*1000,
        prepare_ms=(constructed-start)*1000,scoring_ms=(elapsed-(constructed-start))*1000,
        candidates=core.last['candidates'],scores=core.last['scores'])


def timing(values):
    a=np.asarray(values)
    return dict(p50_ms=float(np.quantile(a,.5)),p95_ms=float(np.quantile(a,.95)),
                p99_ms=float(np.quantile(a,.99)),over200_fraction=float(np.mean(a>200)),samples=len(a))


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    p.add_argument('--config',type=Path,required=True);a=p.parse_args()
    run.initialize();cfg=json.loads(a.config.read_text())
    rows=pickle.loads((a.out/'states.pkl').read_bytes())
    rows=prepare(rows,a.out)
    variants=cfg['latency']['variants']
    original=variants+['native-'+v for v in variants]
    plans={'original':original,'symmetric':variants}
    raw=[];reference={};profile_summary={}
    for mode, names in plans.items():
        # Exclude all warmup decisions and profile runs from latency distributions.
        os.sched_setaffinity(0,{60})
        for name in names:
            decision(mode,rows[0],name,False)
        profiler=cProfile.Profile()
        profiler.enable()
        for row in rows[::max(1,len(rows)//8)][:8]:decision(mode,row,'full',False)
        profiler.disable();profiler.dump_stats(str(a.out/f'{mode}-full.prof'))
        stats=pstats.Stats(profiler)
        top=sorted(stats.stats.items(),key=lambda kv:kv[1][3],reverse=True)[:30]
        profile_summary[mode]=[dict(function=f'{k[0]}:{k[1]}:{k[2]}',calls=v[1],
                                    own_seconds=v[2],cumulative_seconds=v[3]) for k,v in top]
        for repeat in range(cfg['latency']['repeats']):
            for index,row in enumerate(rows):
                order=names if (index+repeat)%2==0 else list(reversed(names))
                for name in order:
                    budget='four cores' if name.endswith('threads4') else 'one core'
                    os.sched_setaffinity(0,{60,61,62,63} if budget=='four cores' else {60})
                    result=decision(mode,row,name)
                    result.update(mode=mode,variant=name,repeat=repeat,budget=budget)
                    raw.append(result)
                    if name=='full':
                        old=reference.get((mode,row['id']))
                        if old:assert old['action']==result['action'] and old['scores']==result['scores']
                        reference[(mode,row['id'])]=result
                if index%25==0:
                    print(json.dumps(dict(mode=mode,repeat=repeat,state=index,samples=len(raw))),flush=True)
        (a.out/f'{mode}-samples.json').write_text(json.dumps([r for r in raw if r['mode']==mode])+'\n')
    summary={}
    for mode,names in plans.items():
        summary[mode]={}
        for name in names:
            samples=[r for r in raw if r['mode']==mode and r['variant']==name]
            unique=[r for r in samples if r['repeat']==0]
            agree=sum(r['action']==reference[(mode,r['id'])]['action'] for r in unique)
            play_agree=sum((r['action']<2304)==(reference[(mode,r['id'])]['action']<2304) for r in unique)
            exact=0;regrets=[]
            for r in unique:
                ref=reference[(mode,r['id'])]
                scores=dict(zip(ref['candidates'],ref['scores']))
                regrets.append(max(scores.values())-scores[r['action']])
                exact+=r['candidates']==ref['candidates'] and r['scores']==ref['scores']
            summary[mode][name]=dict(states=len(unique),exact_action_agreement=agree/len(unique),
                agreement_count=agree,play_wait_agreement=play_agree/len(unique),exact_score_vectors=exact,
                mean_reference_regret=float(np.mean(regrets)),max_reference_regret=float(max(regrets)),
                wall=timing([r['wall_ms'] for r in samples]),cpu=timing([r['cpu_ms'] for r in samples]),
                prepare=timing([r['prepare_ms'] for r in samples]),scoring=timing([r['scoring_ms'] for r in samples]),
                budget=samples[0]['budget'])
    receipt=dict(state_count=len(rows),repeats=cfg['latency']['repeats'],results=summary,
        profiles=profile_summary,scope='candidate generation + public root reconstruction + complete scoring; prepared public input and sampled belief fixed',
        excluded='sensor/image parsing, belief inference, actuator/network; warmup and profiling samples',
        native_sha256=hashlib.sha256(Path(os.environ['CLASHER_DELAY_NATIVE_DIR'],'clasher_core.abi3.so').read_bytes()).hexdigest(),
        ready_manifest=json.loads((a.out/'ready-manifest.json').read_text()),win_rate_claims=False)
    (a.out/'latency-results.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(summary),flush=True)


if __name__=='__main__':main()
