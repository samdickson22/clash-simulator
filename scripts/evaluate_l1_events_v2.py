"""Validation selection and heldout event/derived-state scoring, after inference."""
import argparse
from collections import defaultdict
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random
import math

import numpy as np
from scipy.optimize import linear_sum_assignment

from clasher.rl.live_inference_contract import parse_public_vision_frame,PublicPlayEvent
from clasher.vision.l1_events_v2 import EventFusion
from clasher.vision.l1_derived_v2 import RobustPublicState,PublicTickClock
from evaluate_l1_v1 import timed_events
from collect_l1_rendered import REPORT,append,progress


def read(path):return [json.loads(l) for l in path.read_text().splitlines()]


def sample_inputs(dataset,split,fps,output):
    frames=[];episode=None;due=0
    for row in read(dataset/'inputs.jsonl'):
        if row['split']!=split:continue
        if episode!=row['episode_id']:
            episode=row['episode_id'];due=row['timestamp_ms']
        if fps is None or row['timestamp_ms']+1e-6>=due:
            public={k:row[k] for k in ('episode_id','frame_id','timestamp_ms','image')}
            # The existing public contract canonicalizes media time to integer ms.
            public['timestamp_ms']=int(public['timestamp_ms'])
            frames.append(public)
            if fps is not None:
                while due<=row['timestamp_ms']+1e-6:due+=1000/fps
    output.write_text(''.join(json.dumps(r)+'\n' for r in frames))


def replay(inference,threshold,marker_minimum=.4):
    frames=[parse_public_vision_frame(r) for r in read(inference/'frames.jsonl')]
    cues=read(inference/'candidates.jsonl')
    if len(cues)!=len(frames):raise ValueError('Incomplete candidates')
    episode=None;out=[]
    for frame,row in zip(frames,cues):
        if (frame.episode_id,frame.frame_id)!=(row['episode_id'],row['frame_id']):raise ValueError('Mismatched candidates')
        if episode!=frame.episode_id:
            episode=frame.episode_id;fusion=EventFusion(threshold,marker_minimum)
        events=fusion.update(frame.frame_id,frame.timestamp_ms,row['candidates'],fresh=row['fresh'])
        out.append(replace(frame,play_events=tuple(events)))
    return out


def score_events(frames,truth):
    if not truth or 'event_time_interval_ms' not in truth[0]:return timed_events(frames,truth)
    observed=[(f,e) for f in frames for e in f.play_events]
    costs=np.full((len(observed),len(truth)),1e9)
    for i,(f,e) in enumerate(observed):
        for j,t in enumerate(truth):
            lo,hi=t['event_time_interval_ms']
            if ((f.episode_id,e.player_id,e.card)==(t['episode_id'],t['player_id'],t['card'])
                    and f.timestamp_ms>=hi and f.timestamp_ms-lo<=500):
                costs[i,j]=f.timestamp_ms-lo
    pairs=[]
    if costs.size:
        ii,jj=linear_sum_assignment(costs)
        pairs=[(int(i),int(j)) for i,j in zip(ii,jj) if costs[i,j]<1e9]
    placements=[];by_card=defaultdict(lambda:dict(truth=0,predictions=0,matched=0,placed_within_one=0))
    for t in truth:by_card[t['card']]['truth']+=1
    for f,e in observed:by_card[e.card]['predictions']+=1
    for i,j in pairs:
        f,e=observed[i];t=truth[j];by_card[t['card']]['matched']+=1
        if e.x_tiles is not None:
            error=math.hypot(e.x_tiles-t['x_tiles'],e.y_tiles-t['y_tiles']);placements.append(error)
            by_card[t['card']]['placed_within_one']+=int(error<=1)
    hit=sum(d<=1 for d in placements)
    return dict(truth=len(truth),predictions=len(observed),matched_within_500_ms=len(pairs),
        false_positive=len(observed)-len(pairs),missed=len(truth)-len(pairs),
        recall=len(pairs)/max(1,len(truth)),precision=len(pairs)/max(1,len(observed)),
        placement_within_one_all_plays=hit/max(1,len(truth)),within_one=hit,
        placement_within_one_detected=hit/max(1,len(pairs)),per_card=dict(by_card),
        timing='Conservative: prediction after upper event-time bound and <=500 ms after lower bound',
        event_time_bracket_p95_ms=float(np.quantile([e['event_time_interval_ms'][1]-e['event_time_interval_ms'][0] for e in truth],.95)))


def derive(dataset,frames,prior,output,*,corruption=None):
    ns={'__name__':'l1_v2_exact_reference'}
    source=REPORT/'v2/derived_public_state_reference.py'
    exec(compile(source.read_text(),str(source),'exec'),ns)
    exact_type=ns['DerivedPublicState']
    truth={(r['episode_id'],r['frame_id']):r for r in read(dataset/'evaluation_only/truth.jsonl')}
    events=defaultdict(list)
    for e in read(dataset/'evaluation_only/events.jsonl'):
        if e['player_id']==0:events[e['episode_id']].append((e['tick'],e['card']))
    errors=[];reference_errors=[];determined=correct=covered=0;episode=None
    diagnostics=[];rng=random.Random(66106)
    injected=dict(opponent_events=0,missed=0,inserted=0,wrong_identity=0)
    for frame in frames:
        if frame.episode_id!=episode:
            if episode is not None:diagnostics.append(dict(episode_id=episode,**robust.diagnostics))
            episode=frame.episode_id
            robust=RobustPublicState(exact_type,prior,prior['costs'])
            reference=exact_type(prior,prior['costs'])
            clock=PublicTickClock()
            last_tick=0
        t=truth[episode,frame.frame_id];tick=t['tick']
        actual_events=frame.play_events
        if corruption is not None:
            actual_events=[]
            mode,rate=corruption
            for et,card in events[episode]:
                if not last_tick<et<=tick:continue
                injected['opponent_events']+=1
                if mode=='miss' and rng.random()<rate:
                    injected['missed']+=1;continue
                if mode=='wrong' and rng.random()<rate:
                    card=rng.choice([n for n in prior['costs'] if n!=card])
                    injected['wrong_identity']+=1
                batch=[PublicPlayEvent(f'corrupt-{et}',0,card,.99)]
                if mode=='insert' and rng.random()<rate:
                    batch.append(PublicPlayEvent(f'extra-{et}',0,rng.choice(list(prior['costs'])),.99))
                    injected['inserted']+=1
                robust.observe(et,batch)
        # Native ticks locate scoring samples only. Perceived derivation uses
        # visible clock intervals and relative media time, never the frame ID.
        public_tick=tick if corruption is not None else clock.update(frame.visible_clock_seconds,frame.timestamp_ms)
        state=robust.observe(public_tick,actual_events)
        reference.update(tick,[e for e in events[episode] if e[0]<=tick])
        exact=reference.derived()
        errors.append(abs(state['elixir']-t['opponent_elixir']))
        reference_errors.append(abs(reference.elixir_units/10000-t['opponent_elixir']))
        if exact['hand'] is not None:
            determined+=1;covered+=state['hand'] is not None
            correct+=state['hand'] is not None and sorted(n for n in state['hand'] if n) == sorted(t['opponent_hand'])
        if output:
            append(output,dict(episode_id=episode,frame_id=frame.frame_id,**state,
                reference_determined=exact['hand'] is not None,absolute_elixir_error=errors[-1]))
        last_tick=tick
    if episode is not None:diagnostics.append(dict(episode_id=episode,**robust.diagnostics))
    return dict(frames=len(errors),coverage=1. if errors else 0.,elixir_mae=float(np.mean(errors)) if errors else None,
                reference_elixir_mae=float(np.mean(reference_errors)) if errors else None,
                hand_determined_frames=determined,hand_accuracy=correct/determined if determined else None,
                hand_coverage=covered/determined if determined else None,diagnostics=diagnostics,
                injected_errors=injected if corruption is not None else None)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',type=Path,required=True)
    p.add_argument('--inference',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--sample-split',choices=['train','validation','heldout'])
    p.add_argument('--fps',type=float,default=10.)
    p.add_argument('--native-cadence',action='store_true')
    p.add_argument('--select',action='store_true')
    p.add_argument('--selection',type=Path)
    p.add_argument('--corruption',action='store_true')
    p.add_argument('--events-only',action='store_true')
    a=p.parse_args()
    if a.sample_split:
        sample_inputs(a.dataset,a.sample_split,None if a.native_cadence else a.fps,a.output);return
    a.output.mkdir(parents=True,exist_ok=False)
    frames0=replay(a.inference,.3)
    episodes={f.episode_id for f in frames0}
    truth=[e for e in read(a.dataset/'evaluation_only/events.jsonl') if e['episode_id'] in episodes]
    roles={m['episode_id']:m['split'] for m in json.loads((a.dataset/'manifest.json').read_text())['matches']}
    if a.select:
        if {roles[e] for e in episodes}!={'validation'}:raise ValueError('Selection requires validation only')
        results=[]
        for threshold in (.1,.2,.3,.4,.5,.6,.7,.8,.9,1.01):
            for marker in (.4,.6,.8):
                metrics=score_events(replay(a.inference,threshold,marker),truth)
                f1=2*metrics['precision']*metrics['recall']/max(1e-9,metrics['precision']+metrics['recall'])
                results.append(dict(threshold=threshold,marker_minimum=marker,f1=f1,metrics=metrics))
        selected=max(results,key=lambda r:(r['f1'],r['metrics']['placement_within_one_all_plays']))
        (a.output/'selection.json').write_text(json.dumps(selected,indent=2)+'\n')
        (a.output/'sweep.json').write_text(json.dumps(results,indent=2)+'\n')
        progress(f'v2 validation selected event threshold {selected["threshold"]}, marker {selected["marker_minimum"]}; F1 {selected["f1"]:.3f}.')
        return
    if not a.selection:raise ValueError('Frozen validation selection required')
    choice=json.loads(a.selection.read_text())
    frames=replay(a.inference,choice['threshold'],choice['marker_minimum'])
    metrics=score_events(frames,truth)
    if a.events_only:
        result=dict(events=metrics,derived=None,fps=a.fps,
            selection_sha256=hashlib.sha256(a.selection.read_bytes()).hexdigest(),
            inference_hashes=json.loads((a.inference/'complete.json').read_text()),
            gates=dict(events=metrics['recall']>=.9 and metrics['precision']>=.9,
                       placement=metrics['placement_within_one_all_plays']>=.9),
            scope='Continuous event-boundary stepping; sparse native observations cannot certify per-frame derived-state truth')
        (a.output/'metrics.json').write_text(json.dumps(result,indent=2)+'\n')
        progress(f'v2 continuous event-boundary score: recall {metrics["recall"]:.3f}, precision {metrics["precision"]:.3f}, placement {metrics["placement_within_one_all_plays"]:.3f}.')
        return
    prior=json.loads((REPORT/'v2/public-deck-prior.json').read_text())
    derived=derive(a.dataset,frames,prior,a.output/'derived.jsonl')
    result=dict(events=metrics,derived=derived,fps=a.fps,
                selection_sha256=hashlib.sha256(a.selection.read_bytes()).hexdigest(),
                inference_hashes=json.loads((a.inference/'complete.json').read_text()),
                gates=dict(events=metrics['recall']>=.9 and metrics['precision']>=.9,
                    placement=metrics['placement_within_one_all_plays']>=.9,
                    derived_elixir=derived['elixir_mae'] is not None and derived['elixir_mae']<=.5,
                    derived_hand=derived['hand_accuracy'] is not None and derived['hand_accuracy']>=.9))
    (a.output/'metrics.json').write_text(json.dumps(result,indent=2)+'\n')
    if a.corruption:
        # Use one sample per second to keep the independent degradation study bounded.
        reduced=[];last={}
        for f in frames:
            if f.timestamp_ms-last.get(f.episode_id,-1000)>=1000:
                reduced.append(f);last[f.episode_id]=f.timestamp_ms
        corrupt=[]
        for mode in ('miss','insert','wrong'):
            for rate in (0.,.05,.1,.2):
                scores=derive(a.dataset,reduced,prior,None,corruption=(mode,rate))
                corrupt.append(dict(mode=mode,rate=rate,seed=66106,**scores))
        (a.output/'corruption.json').write_text(json.dumps(corrupt,indent=2)+'\n')
    progress(f'v2 heldout evaluation {a.fps} FPS: event recall {metrics["recall"]:.3f}, precision {metrics["precision"]:.3f}, placement {metrics["placement_within_one_all_plays"]:.3f}; gates {result["gates"]}.')


if __name__=='__main__':main()
