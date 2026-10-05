"""Seed-audited sequential halving and preregistered paired confirmation."""
import argparse
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import pickle
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
os.environ.update(CLASHER_ROOT=str(ROOT), PYTHONDONTWRITEBYTECODE='1',
                  OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
sys.path[:0] = [str(HERE/'native'), str(ROOT/'src'), str(ROOT/'engine-rs')]
import numpy as np
import torch
from support import Context, TRAIN_DECKS, DEV_DECKS, HOG_DECKS, CHECKPOINT, cl_eval, maybe_silence_stdio
from public_planner import PublicPlanner, Resources, observe, Information
from tuning import Config, Planner, CURRENT, configurations
from statistics import boot
from clasher.rl.public_action_mask import PublicActionMaskInput

BASE = 1750000003
STYLES = ('balanced', 'pressure', 'defense')


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value, sort_keys=True, indent=2)+'\n'); tmp.replace(path)


def sha(path):
    return hashlib.file_digest(open(path, 'rb'), 'sha256').hexdigest()


def progress(message):
    with (HERE/'PROGRESS.md').open('a') as f:
        f.write(f'\n{datetime.now(timezone.utc).isoformat()} PID {os.getpid()}: {message}\n')


def host():
    return dict(load=os.getloadavg(), processes=subprocess.check_output(
        ['ps','-axo','pid,ppid,ni,%cpu,etime,comm'], text=True))


def prior():
    return dict(decks=sum([json.loads(p.read_text())['decks'] for p in
                          (TRAIN_DECKS, DEV_DECKS, HOG_DECKS)], []))


def audit():
    # Conservatively inspect all seed fields, not only final game receipts.
    proposed = {BASE+offset+p*1009 for offset,count in
                [(0,24),(1000000,48),(2000000,96),(3000000,128),
                 (4000000,22),(5000000,21),(6000000,21),
                 (7000000,11),(8000000,11),(9000000,10),(10000000,4),(11000000,1)]
                for p in range(count)}
    proc = subprocess.Popen(['rg','--hidden','--no-heading','--with-filename','--only-matching',
        r'"[A-Za-z_]*seed"\s*:\s*[0-9]+','reports','-g','*.json','-g','*.jsonl'],
        cwd=ROOT, stdout=subprocess.PIPE, text=True)
    used=set(); overlaps=[]; fields=0
    for line in proc.stdout:
        match=re.search(r':\s*([0-9]+)\s*$',line)
        if match:
            value=int(match[1]);used.add(value);fields+=1
            if value in proposed:overlaps.append(line.strip())
    assert proc.wait() in (0,1)
    result=dict(created=datetime.now(timezone.utc).isoformat(),seed_fields=fields,
                unique_used=len(used),proposed=sorted(proposed),overlaps=overlaps,
                passed=not overlaps,scope='All reports JSON and JSONL seed fields, including this experiment and archives.')
    write(HERE/'seed-audit.json',result)
    assert not overlaps, overlaps[:5]
    progress(f'Seed audit passed: {fields} fields, {len(used)} distinct historical seeds.')


def freeze():
    files=list((ROOT/'src/clasher').rglob('*.py'))+list(HERE.glob('*.py'))
    files += [CHECKPOINT,TRAIN_DECKS,DEV_DECKS,HOG_DECKS,ROOT/'gamedata.json',
              HERE/'native/clasher_core.abi3.so',HERE/'native/differential.py',
              HERE/'native/live_snapshot.py',HERE/'native/es_common.py',HERE/'config.toml',HERE/'DESIGN.md']
    write(HERE/'manifest.json',dict(created=datetime.now(timezone.utc).isoformat(),
          sha256={str(p.relative_to(ROOT)):sha(p) for p in files}))


def verify():
    for name,pin in json.loads((HERE/'manifest.json').read_text())['sha256'].items():
        if sha(ROOT/name)!=pin:raise RuntimeError('dependency drift: '+name)
    size=sum(p.stat().st_size for p in HERE.rglob('*') if p.is_file())
    assert size<1024**3, size
    return sha(HERE/'manifest.json')


def reset(ctx, role, seed, seat, h2h):
    env=ctx.envs(role,seed)[seat];a,b=ctx.pools(role)
    decks=cl_eval._sample_paired_ordered_decks(a,a if h2h and role=='hog26' else b,matchup_seed=seed)
    world=decks if h2h or seat==0 else decks[::-1]
    with maybe_silence_stdio(True):env.reset(seed=seed,ordered_decks=world)
    return env,world


def timed(planner,env,seat,decision):
    t,c=time.perf_counter(),time.process_time();calls=planner.calls
    action,mask=planner.decide(observe(env,seat),decision)
    return action,mask,[time.perf_counter()-t,time.process_time()-c,planner.calls!=calls]


def play(ctx,r,cfg,spec):
    seed=spec['seed']+spec['game']//2*1009;seat=spec['game']%2
    h2h=spec['style']=='search'
    env,world=reset(ctx,spec['role'],seed,seat,h2h)
    torch.manual_seed(seed+271828)
    p=Planner(r,prior(),cfg,seed=seed*2+seat+7919)
    opponent=Planner(r,prior(),CURRENT,seed=seed*2+1-seat+7919) if h2h else None
    timings=[[],[]];failed=[0,0];start=time.perf_counter()
    for d in range(1300):
        action,mask,t=timed(p,env,seat,d);timings[0].append(t)
        if h2h:
            oa,om,t=timed(opponent,env,1-seat,d);timings[1].append(t)
        else:
            packet=observe(env,1-seat).packet
            om=r.mask_builder.build(PublicActionMaskInput.from_confidence_observation(packet))
            oa=int(ctx.bot(spec['style']).select_action(packet))
        assert mask[action] and om[oa]
        with maybe_silence_stdio(True):
            _,done,step=env.step({seat:action,1-seat:oa},pre_action_masks={seat:mask,1-seat:om})
        failed[0]+=int(action!=r.no_op and not step.action_success[seat])
        failed[1]+=int(oa!=r.no_op and not step.action_success[1-seat])
        if done:break
    else:raise RuntimeError('incomplete game')
    assert env.battle.game_over
    outcome='draw' if env.battle.winner is None else 'win' if env.battle.winner==seat else 'loss'
    return dict(spec=spec,config=asdict(cfg),matchup_seed=seed,seat=seat,world_decks=world,
                outcome=outcome,score={'win':1.,'draw':.5,'loss':0.}[outcome],
                ticks=env.battle.tick,failed=failed,timings=timings,
                wall_s=time.perf_counter()-start,pid=os.getpid(),manifest_sha256=verify())


def stage_specs(stage,n):
    return [dict(stage=stage,role='hog26' if (g//2)%3==0 else 'holdout',
                 style='search',game=g,seed=BASE+(stage-1)*1000000) for g in range(n)]


def confirmation_specs():
    out=[dict(stage='confirm',role='hog26' if (g//2)%3==0 else 'holdout',
              style='search',game=g,seed=BASE+3000000,which='winner') for g in range(256)]
    for role,offset,counts in [('holdout',4000000,(44,42,42)),('hog26',7000000,(22,22,20))]:
        for i,(style,n) in enumerate(zip(STYLES,counts)):
            for g in range(n):
                for which in ('winner','current'):
                    out.append(dict(stage='confirm',role=role,style=style,game=g,
                                    seed=BASE+offset+i*1000000,which=which))
    return out


def key(cfg,s):
    return f"{cfg.name}-{s['role']}-{s['style']}-{s['game']:03d}-{s.get('which','candidate')}"


def summary(rows):
    clusters=defaultdict(list)
    for r in rows:clusters[(r['spec']['role'],r['spec']['style'],r['matchup_seed'])].append(r['score'])
    assert all(len(v)==2 for v in clusters.values()), 'incomplete seat pairs'
    return dict(n=len(rows),score=sum(r['score'] for r in rows)/len(rows),
                ci95=boot(list(clusters.values())))


def timing(rows):
    a=np.asarray([t for row in rows for t in row['timings'][0]])
    return dict(n=len(a),wall_p99=float(np.quantile(a[:,0],.99)),wall_max=float(a[:,0].max()),
                search_cpu_mean=float(a[a[:,2]>0,1].mean()),overruns=int((a[:,0]>.25).sum()))


def benchmark():
    ctx=Context();r=Resources(ctx);roots=[]
    for g in range(4):
        seed=BASE+10000000+g*1009
        env,_=reset(ctx,'hog26' if g%2 else 'holdout',seed,g%2,True)
        for d in range(1100):
            if d in (0,20,80,160,320,480,640,800,1000):
                t,c=time.perf_counter(),time.process_time();info=observe(env,g%2)
                roots.append((info,time.perf_counter()-t,time.process_time()-c))
            actions={};masks={}
            for seat in (0,1):
                packet=observe(env,seat).packet
                masks[seat]=r.mask_builder.build(PublicActionMaskInput.from_confidence_observation(packet))
                actions[seat]=int(ctx.bot(STYLES[g%3]).select_action(packet))
            with maybe_silence_stdio(True):_,done,_=env.step(actions,pre_action_masks=masks)
            if done:break
    (HERE/'roots.pkl').write_bytes(pickle.dumps(roots))
    results=dict(host=host(),configs={})
    for cfg in [CURRENT]+configurations():
        samples=[]
        for j,(info,tw,tc) in enumerate(roots):
            p=Planner(r,prior(),cfg,seed=771+j)
            t,c=time.perf_counter(),time.process_time();p.decide(info,0)
            samples.append([time.perf_counter()-t+tw,time.process_time()-c+tc,p.calls>0])
        m=timing([dict(timings=[samples,[]])]);m['samples']=samples
        m['eligible']=m['wall_max']<=.25
        results['configs'][cfg.name]=m
        write(HERE/'benchmark.json',results)
        progress(f"Timing {cfg.name}: p99 {m['wall_p99']:.4f}s, max {m['wall_max']:.4f}s, eligible {m['eligible']}.")
        print(cfg.name,{k:v for k,v in m.items() if k!='samples'},flush=True)
    progress('Initial timing complete. No evaluation games used for latency screening.')


def worker(schedule,index,workers):
    jobs=json.loads(Path(schedule).read_text());verify();ctx=Context();r=Resources(ctx)
    for job in jobs[index::workers]:
        if (HERE/'STOP').exists():break
        cfg=Config(**job['config']);spec=job['spec'];path=HERE/'games'/str(spec['stage'])/(key(cfg,spec)+'.json')
        if spec['stage']=='confirm':
            pins=json.loads((HERE/'confirmation-manifest.json').read_text())
            assert pins['prereg_sha256']==sha(HERE/'PREREG.md')
            assert pins['schedule_sha256']==sha(HERE/'confirmation-schedule.json')
            assert pins['experiment_sha256']==sha(HERE/'manifest.json')
        if path.exists():continue
        verify();rec=play(ctx,r,cfg,spec)
        if spec['stage']=='confirm':rec['confirmation_manifest_sha256']=sha(HERE/'confirmation-manifest.json')
        write(path,rec)
        print(path.name,rec['outcome'],round(rec['wall_s'],2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['audit','freeze','benchmark','worker'])
    parser.add_argument('--schedule');parser.add_argument('--worker',type=int,default=0);parser.add_argument('--workers',type=int,default=3)
    args=parser.parse_args()
    if args.mode=='audit':audit()
    elif args.mode=='freeze':freeze()
    elif args.mode=='benchmark':benchmark()
    else:worker(args.schedule,args.worker,args.workers)
