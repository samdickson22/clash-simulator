"""Frozen public crown/result replay on unchanged round-2 training dev only."""
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import json
import sys
import time
import cv2
import numpy as np
from extract import decode,rows,sha,SPLIT_SHA
ROOT=Path(__file__).resolve().parents[5]
STUDY=Path(__file__).resolve().parent
OUT=STUDY/'runtime/r3'
SOURCE=ROOT.parent/'clasher-v4-cpu/matches'
CACHE=ROOT.parent/'clasher-v4-cache'
sys.path.insert(0,str(ROOT/'src'))
from clasher.live.tower_channel import TowerChannel
from clasher.live.crown_counter import CrownCounterReader
from clasher.live.result_screen import ResultScreenDetector


def replay(ep):
    cv2.setNumThreads(1)
    truth=json.loads((STUDY/'runtime/r2'/(ep+'.truth.json')).read_text())
    frames=rows(SOURCE/ep/'frames.jsonl')
    receipt=json.loads((SOURCE/ep/'receipt.json').read_text())
    index=json.loads((CACHE/ep/'index.json').read_text())
    assert index['split']==receipt['split']=='train'
    assert sha(SOURCE/ep/'receipt.json')==index['receipt_sha256']==truth['provenance']['receipt_sha256']
    assert sha(SOURCE/ep/'frames.jsonl')==receipt['files']['frames.jsonl']
    assert sha(CACHE/ep/'raw.zst')==index['sha256']['raw.zst']==truth['provenance']['raw_sha256']
    model=ROOT/'src/clasher/live/tower_channel_templates.json'
    before,after=TowerChannel(model),TowerChannel(model)
    crowns,results=CrownCounterReader(),ResultScreenDetector()
    first=[{},{}];dead=[set(),set()];counts=Counter();times=[];false_slots=set();crown_examples=[];result_first=None
    with (CACHE/ep/'raw.zst').open('rb') as stream:
        for block in index['blocks']:
            offset,size=block['raw.zst'];stream.seek(offset)
            images=decode(stream.read(size),block['count'])
            for j,image in enumerate(images):
                i=block['start']+j;frame=frames[i];label=truth['labels'][i]
                stamp=round((frame['produced_at']-frames[0]['produced_at'])*1000)
                old=before.step(image,ep,stamp)
                start=time.perf_counter_ns()
                score=crowns.read(image,ep,stamp)
                new=after.step(image,ep,stamp,crowns=score)
                ended=results.step(image,ep,stamp,score)
                elapsed=(time.perf_counter_ns()-start)/1e6
                if i>=16:times.append(elapsed)
                if ended is not None and result_first is None:
                    result_first=dict(ordinal=i,tick_lo=frame['tick_lo'],tick_hi=frame['tick_hi'],observation=asdict(ended))
                if frame['tick_hi']<receipt['terminal']['tick']:
                    counts['preterminal_frames']+=1
                    counts['false_terminal_frames']+=ended is not None
                elif frame['tick_lo']>=receipt['terminal']['tick'] and receipt['terminal']['ended']:
                    counts['terminal_frames']+=1
                    counts['detected_terminal_frames']+=ended is not None
                for variant,obs in enumerate((old,new)):
                    prefix='before_' if variant==0 else 'after_'
                    for s,o in enumerate(obs):
                        if o.state=='destroyed':
                            dead[variant].add(s)
                            first[variant].setdefault(s,dict(ordinal=i,tick_lo=frame['tick_lo'],tick_hi=frame['tick_hi'],evidence=o.destruction_evidence))
                        if label['states'][s]=='alive':
                            counts[prefix+'alive_towers']+=1
                            counts[prefix+'false_towers']+=s in dead[variant]
                            if s%3:
                                counts[prefix+'alive_princess']+=1
                                counts[prefix+'false_princess']+=s in dead[variant]
                                if variant==1 and s in dead[variant]:false_slots.add(s)
                if score is not None:
                    counts['crown_read_frames']+=1
                    for scorer,value in enumerate(score.crowns):
                        if value is None:continue
                        victim=1-scorer;slots=(victim*3+1,victim*3+2)
                        states=[label['states'][s] for s in slots]
                        if all(v is not None for v in states):
                            counts['crown_scored_counts']+=1
                            counts['crown_exact_counts']+=value==states.count('destroyed')
                            counts['crown_ahead_counts']+=value>states.count('destroyed')
                    if len(crown_examples)<8:crown_examples.append(dict(ordinal=i,observation=asdict(score)))
                if i==len(frames)-1:cv2.imwrite(str(OUT/f'{ep}-last.jpg'),image)
    events=[]
    for e in truth['events']:
        event=dict(e,episode=ep)
        for v,name in enumerate(('before','after')):
            hit=first[v].get(e['slot']);event[name]=hit
            if hit:
                event[name+'_lower_ms']=max(0,(hit['tick_lo']-e['destruction_tick'])*50)
                event[name+'_upper_ms']=max(0,(hit['tick_hi']-e['last_positive_tick'])*50)
        events.append(event)
    print(ep,len(frames),'frames',len(events),'events',counts,flush=True)
    return dict(episode=ep,counts=dict(counts),events=events,times=times,false_slots=sorted(false_slots),first_result=result_first,crown_examples=crown_examples,provenance=truth['provenance'])


def main():
    freeze=json.loads((STUDY/'round3-freeze.json').read_text())
    for p,digest in freeze['files_sha256'].items():assert sha(ROOT/p)==digest,(p,'changed after freeze')
    assert sha(STUDY.parent/'split.json')==SPLIT_SHA
    manifest=json.loads((STUDY/'round2-manifest.json').read_text())
    members={r['seed']:r['split'] for r in json.loads((STUDY.parent/'split.json').read_text())['matches']}
    assert not set(manifest['dev'])&set(manifest['fit'])
    assert all(members[int(ep.rsplit('-',1)[1])]=='train' for ep in manifest['dev'])
    with ProcessPoolExecutor(max_workers=4) as pool:matches=list(pool.map(replay,manifest['dev']))
    counts=Counter();times=[];events=[]
    for match in matches:
        counts.update(match['counts']);times+=match.pop('times');events+=match['events']
    latency={}
    for name in ('before','after'):
        hits=[e for e in events if e[name]]
        latency[name]=dict(confirmed=len(hits),total=len(events),mean_lower_ms=float(np.mean([e[name+'_lower_ms'] for e in hits])),mean_upper_ms=float(np.mean([e[name+'_upper_ms'] for e in hits])),p50_lower_ms=float(np.median([e[name+'_lower_ms'] for e in hits])),p50_upper_ms=float(np.median([e[name+'_upper_ms'] for e in hits])))
    false=counts['after_false_princess'];alive=counts['after_alive_princess']
    report=dict(schema='clasher.public-tower-dev.r3',freeze_sha256=sha(STUDY/'round3-freeze.json'),manifest_sha256=sha(STUDY/'round2-manifest.json'),matches=matches,counts=dict(counts),events=events,destruction_latency=latency,false_destroyed=dict(princess_false=false,princess_alive=alive,one_sided_95_princess_frame_upper=1-.05**(1/alive) if false==0 else None,match_errors=sum(bool(m['false_slots']) for m in matches),matches=len(matches),one_sided_95_match_upper=1-.05**(1/len(matches)) if all(not m['false_slots'] for m in matches) else None),compute_ms=dict(samples=len(times),mean=float(np.mean(times)),p95=float(np.quantile(times,.95)),p99=float(np.quantile(times,.99))),dev_used_for_fit=False,validation_payloads_opened=False,heldout_payloads_opened=False,workers=4,host='127x03',nice=10,cpu_only=True)
    (OUT/'dev-result.json').write_text(json.dumps(report,indent=2)+'\n')
    print('complete',latency,report['false_destroyed'],flush=True)

if __name__=='__main__':main()
