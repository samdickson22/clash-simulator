"""Replay frozen pixel model, then score untouched training-only dev truth."""
import argparse
from collections import Counter,defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import json
from pathlib import Path
import sys,time
import cv2
import numpy as np
from extract import sha,decode,rows,SPLIT_SHA
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'src'))
from clasher.live.tower_channel import TowerChannel,SLOT_NAMES,number_family


def replay(args):
    ep,root,source,cache,model=args
    cv2.setNumThreads(1)
    truth=json.loads((root/(ep+'.truth.json')).read_text());frames=rows(source/ep/'frames.jsonl');idx=json.loads((cache/ep/'index.json').read_text())
    if sha(cache/ep/'raw.zst')!=truth['provenance']['raw_sha256']:raise ValueError('Dev pixels changed')
    c=TowerChannel(model);counts=defaultdict(Counter);latencies=[];first={};latched=set();false_slots=set();predictions=[]
    with (cache/ep/'raw.zst').open('rb') as f:
        for b in idx['blocks']:
            offset,size=b['raw.zst'];f.seek(offset);images=decode(f.read(size),b['count'])
            for j,image in enumerate(images):
                i=b['start']+j;frame=frames[i];label=truth['labels'][i];stamp=round((frame['produced_at']-frames[0]['produced_at'])*1000)
                t=time.perf_counter_ns();obs=c.step(image,ep,stamp);ms=(time.perf_counter_ns()-t)/1e6
                if i>=16:latencies.append(ms)
                for s,o in enumerate(obs):
                    k=counts[o.slot];state=label['states'][s];hp=label['hp'][s];active=label['active'][s]
                    k['all_frames']+=1;k['all_'+o.state]+=1
                    if o.state=='destroyed':
                        latched.add(s);first.setdefault(s,dict(ordinal=i,tick=label['tick'],tick_lo=frame['tick_lo'],tick_hi=frame['tick_hi'],timestamp_ms=stamp))
                    if state:
                        k[state+'_truth']+=1;k[state+'_to_'+o.state]+=1
                        if state=='alive' and s in latched:k['alive_latched_destroyed']+=1;false_slots.add(s)
                    if hp is not None and hp>0:
                        family=number_family(s);n=counts[family];n['hp_eligible']+=1
                        if o.hp is not None:
                            n['number_accepted']+=1;n['number_exact']+=o.hp==hp
                            if k is not n:
                                k['number_accepted']+=1;k['number_exact']+=o.hp==hp
                        if o.hp_fraction is not None:
                            k['bar_accepted']+=1;k['bar_within_5pct']+=abs(o.hp_fraction-hp/(4824 if s%3==0 else 3052))<=.05
                    if active is not None:
                        k['activation_eligible']+=1
                        k['truth_active' if active else 'truth_sleeping']+=1
                        if o.king_active is not None:
                            k['activation_accepted']+=1;k['activation_exact']+=o.king_active==active
                            k[('active' if active else 'sleeping')+'_to_'+str(o.king_active)]+=1
                    if o.state=='destroyed' and s not in first:raise AssertionError()
                    if hp is not None and o.hp is not None and hp!=o.hp:predictions.append(dict(ordinal=i,observation=asdict(o),truth_hp=hp))
    events=[]
    for e in truth['events']:
        hit=first.get(e['slot']);r=dict(e,episode=ep,confirmed=hit)
        if hit:
            r['latency_lower_ms']=max(0,(hit['tick_lo']-e['destruction_tick'])*50)
            r['latency_upper_ms']=max(0,(hit['tick_hi']-e['last_positive_tick'])*50)
            r['early']=hit['tick_hi']<e['last_positive_tick']
        events.append(r)
    print(ep,len(frames),'frames',len(events),'events',flush=True)
    return dict(episode=ep,counts={s:dict(v) for s,v in counts.items()},events=events,latencies=latencies,false_slots=sorted(false_slots),number_errors=predictions,provenance=truth['provenance'])


def main(a):
    freeze=json.loads(a.freeze.read_text())
    for p,d in freeze['files_sha256'].items():
        if sha(Path(p))!=d:raise ValueError('Frozen model/source changed')
    manifest=json.loads((a.root/'manifest.json').read_text())
    if sha(a.split)!=SPLIT_SHA:raise ValueError('Split changed')
    members={r['seed']:r['split'] for r in json.loads(a.split.read_text())['matches']}
    if set(manifest['dev'])&(set(manifest['fit'])|set(manifest['round1_excluded_from_dev'])):raise ValueError('Dev leakage')
    if any(members[int(ep.rsplit('-',1)[-1])]!='train' for ep in manifest['dev']):raise ValueError('Forbidden membership')
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        results=list(pool.map(replay,[(ep,a.root,a.source,a.cache,a.model) for ep in manifest['dev']]))
    counts=defaultdict(Counter);events=[];times=[]
    for r in results:
        for s,v in r['counts'].items():counts[s].update(v)
        events+=r['events'];times+=r.pop('latencies')
    alive=sum(counts[s]['alive_truth'] for s in SLOT_NAMES);false=sum(counts[s]['alive_to_destroyed'] for s in SLOT_NAMES)
    princess_alive=sum(counts[s]['alive_truth'] for s in SLOT_NAMES if not s.endswith('king'))
    princess_false=sum(counts[s]['alive_to_destroyed'] for s in SLOT_NAMES if not s.endswith('king'))
    hits=[e for e in events if e['confirmed']]
    policy={f:bool(counts[f]['number_accepted'] and counts[f]['number_exact']/counts[f]['number_accepted']>=.99) for f in ('opp_princess','own_king')}
    a.output.write_text(json.dumps(dict(schema='clasher.public-tower-dev.r2',manifest_sha256=sha(a.root/'manifest.json'),freeze_sha256=sha(a.freeze),matches=results,counts={s:dict(v) for s,v in counts.items()},destruction_events=events,princess_event_recall=dict(confirmed=len(hits),total=len(events)),false_destroyed=dict(false=false,alive=alive,princess_false=princess_false,princess_alive=princess_alive,one_sided_95_frame_upper=1-.05**(1/alive) if false==0 else None,one_sided_95_princess_frame_upper=1-.05**(1/princess_alive) if princess_false==0 else None,match_errors=sum(bool(r['false_slots']) for r in results),matches=len(results),one_sided_95_match_upper=1-.05**(1/len(results)) if all(not r['false_slots'] for r in results) else None),confirmation_latency_ms=dict(interval_censored=True,mean_lower=float(np.mean([e['latency_lower_ms'] for e in hits])) if hits else None,mean_upper=float(np.mean([e['latency_upper_ms'] for e in hits])) if hits else None),number_acceptance_policy=policy,latency_ms=dict(samples=len(times),mean=float(np.mean(times)),p95=float(np.quantile(times,.95)),p99=float(np.quantile(times,.99))),workers=a.workers,validation_payloads_opened=False,heldout_payloads_opened=False,dev_used_for_fit=False),indent=2)+'\n')
    print('complete',dict(counts),len(hits),len(events),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('root','source','cache','model','freeze','split','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--workers',type=int,default=4);main(p.parse_args())
