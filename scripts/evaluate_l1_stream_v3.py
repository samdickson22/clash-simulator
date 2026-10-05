"""Select on validation, then score frozen video predictions and public posterior."""
import argparse
from collections import defaultdict
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import numpy as np

from clasher.data import CardDataLoader
from clasher.rl.live_inference_contract import parse_public_vision_frame
from clasher.vision.l1_events_v3 import StreamFusion
from clasher.vision.l1_derived_v3 import OpponentPosterior,StreamPublicClock
from collect_l1_rendered import append,progress
from evaluate_l1_events_v2 import score_events


def read(path):return [json.loads(l) for l in path.read_text().splitlines()]


def threshold_rank(trial,card=None):
    counts=trial['metrics'] if card is None else trial['metrics']['per_card'].get(card,{})
    matched=counts.get('matched_within_500_ms' if card is None else 'matched',0)
    predicted=counts.get('predictions',0);truth=counts.get('truth',0)
    return 2*matched/max(1,truth+predicted),matched,-predicted,trial['threshold']


def replay(frames,cues,thresholds):
    result=[];episode=None
    for frame,cue in zip(frames,cues,strict=True):
        if (frame.episode_id,frame.frame_id)!=(cue['episode_id'],cue['frame_id']):raise ValueError('Mismatched candidates')
        if episode!=frame.episode_id:episode=frame.episode_id;fusion=StreamFusion(thresholds)
        events=fusion.update(frame.frame_id,frame.timestamp_ms,cue['candidates'])
        result.append(replace(frame,play_events=tuple(events)))
    return result


def calibrate_opponent_events(frames,truth,elapsed):
    """Late but correct visual evidence still informs state, despite failing L1's deadline."""
    observed=defaultdict(list);actual=defaultdict(list)
    for frame in frames:
        for event in frame.play_events:
            if event.player_id==0:observed[frame.episode_id,event.card].append(frame.timestamp_ms)
    for event in truth:
        if event['player_id']==0:actual[event['episode_id'],event['card']].append(event['event_time_interval_ms'])
    counts=defaultdict(lambda:dict(truth=0,predictions=0,matched=0))
    for key in set(observed)|set(actual):
        card=key[1];targets=sorted(actual[key]);used=set()
        counts[card]['truth']+=len(targets);counts[card]['predictions']+=len(observed[key])
        for timestamp in sorted(observed[key]):
            candidate=next((i for i,(lo,hi) in enumerate(targets) if i not in used and hi<=timestamp<=lo+2000),None)
            if candidate is not None:used.add(candidate)
        counts[card]['matched']+=len(used)
    probabilities={name:(c['matched']+1)/(c['predictions']+2) for name,c in counts.items()}
    missed=sum(c['truth']-c['matched'] for c in counts.values())
    return probabilities,min(2.,missed/max(1.,elapsed)),dict(counts)


def derived_metrics(dataset,entries,frames,cues,selection,output):
    by_episode=defaultdict(list)
    for frame,cue in zip(frames,cues,strict=True):by_episode[frame.episode_id].append((frame,cue))
    errors=[];covered=[];widths=[];hands_correct=[];rows_out=[];diagnostics=[]
    costs=selection['costs']
    for entry in entries:
        ep=entry['episode_id'];items=by_episode[ep]
        raw=dataset/'evaluation_only'/ep
        native=read(raw/'observations.jsonl');media=read(raw/'frames.jsonl')
        origin=media[0]['received_mono_s']-media[0]['timestamp_ms']/1000
        posterior=OpponentPosterior(costs,particles=1024,missed_plays_per_second=selection['missed_rate'],seed=6107,
            calibration_residuals=selection.get('calibration_residuals'))
        clock=StreamPublicClock();index=0;last_media=None;last_scored=-1e9
        for truth in native:
            query_ms=(truth['start_ns']/1e9-origin)*1000
            if query_ms-last_scored<1000:continue
            while index<len(items) and items[index][1]['available_timestamp_ms']<=query_ms:
                frame,cue=items[index];index+=1
                if last_media is None and frame.visible_clock_seconds is None:continue
                tick=clock.update(frame.visible_clock_seconds,frame.timestamp_ms,cue['clock_phase'])
                if last_media is None:posterior.start_at(tick)
                calibrated=[replace(e,confidence=selection['event_probabilities'].get(e.card,.5)) for e in frame.play_events]
                posterior.observe(max(posterior.tick,tick),calibrated)
                last_media=frame.timestamp_ms
            if last_media is None:continue
            # Extrapolation uses only elapsed host time since the last public
            # frame. Native tick and private state are used below for scoring.
            posterior.advance(max(posterior.tick,round(clock.tick+(query_ms-last_media)/50)))
            d=posterior.distribution();actual=truth['players'][0]
            error=abs(d['elixir_mean']-actual['elixir']);errors.append(error)
            margin=selection.get('interval_margin',0.)
            lo=max(0.,d['elixir_interval_90'][0]-margin);hi=min(10.,d['elixir_interval_90'][1]+margin)
            hit=lo<=actual['elixir']<=hi;covered.append(hit);widths.append(hi-lo)
            hand_correct=None
            if d['hand'] is not None:
                key=lambda x:'' if x is None else x
                hand_correct=tuple(sorted(actual['hand'],key=key))==tuple(d['hand'])
                hands_correct.append(hand_correct)
            row=dict(episode_id=ep,query_ms=query_ms,truth_tick=truth['tick'],actual_elixir=actual['elixir'],
                **d,interval=[lo,hi],covered=hit,hand_correct=hand_correct,
                signed_residual=actual['elixir']-d['elixir_mean'],
                interval_nonconformity=max(d['elixir_interval_90'][0]-actual['elixir'],actual['elixir']-d['elixir_interval_90'][1],0.))
            rows_out.append(row);last_scored=query_ms
        diagnostics.append(dict(episode_id=ep,**posterior.diagnostics))
    for row in rows_out:append(output/'derived.jsonl',row)
    return dict(samples=len(errors),elixir_mae=float(np.mean(errors)) if errors else None,
        interval90_coverage=float(np.mean(covered)) if covered else None,
        interval90_mean_width=float(np.mean(widths)) if widths else None,
        hand_concentrated_samples=len(hands_correct),hand_concentrated_coverage=len(hands_correct)/max(1,len(errors)),
        hand_accuracy_when_concentrated=float(np.mean(hands_correct)) if hands_correct else None,
        diagnostics=diagnostics,nonconformity=[r['interval_nonconformity'] for r in rows_out],
        signed_residuals=[r['signed_residual'] for r in rows_out])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',type=Path,required=True);p.add_argument('--audit',type=Path,required=True)
    p.add_argument('--split',choices=['validation','heldout'],required=True)
    p.add_argument('--inference',type=Path);p.add_argument('--selection',type=Path)
    p.add_argument('--prepare-inputs',action='store_true');p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();manifest=json.loads((a.dataset/'manifest.json').read_text())
    entries=[e for e in manifest['matches'] if e['split']==a.split]
    entries=[e for e in entries if e.get('capture_protocol',0)>=2]
    if not entries:raise ValueError('No complete-tail matches in the selected split')
    for entry in entries:
        audit=json.loads((a.audit/entry['episode_id']/'complete.json').read_text())
        if audit.get('incomplete_event_windows') or audit.get('unresolved_scheduled_commands'):
            raise ValueError('Primary scoring requires every deployment receipt and full cue window')
    if a.prepare_inputs:
        with a.output.open('x') as f:
            for e in entries:
                for row in read(a.audit/e['episode_id']/'inputs.jsonl'):f.write(json.dumps(row)+'\n')
        return
    a.output.mkdir(parents=True,exist_ok=False)
    if not (a.inference/'complete.json').exists():raise ValueError('Inference must finish before scoring')
    frames=[parse_public_vision_frame(r) for r in read(a.inference/'frames.jsonl')]
    cues=read(a.inference/'candidates.jsonl')
    if {f.episode_id for f in frames}!={e['episode_id'] for e in entries}:raise ValueError('Wrong inference split')
    truth=[r for e in entries for r in read(a.audit/e['episode_id']/'events.jsonl')]
    if a.split=='heldout' and a.selection is None:raise ValueError('Heldout requires frozen validation selection')
    if a.selection is None:
        trials=[]
        for threshold in (.3,.4,.5,.6,.7,.8,.9):
            prediction=replay(frames,cues,{'default':threshold})
            # Output completion latency counts against the event deadline.
            scored=[replace(f,timestamp_ms=round(c['available_timestamp_ms'])) for f,c in zip(prediction,cues)]
            score=score_events(scored,truth)
            trials.append(dict(threshold=threshold,metrics=score))
        best=max(trials,key=threshold_rank)
        thresholds={'default':best['threshold']}
        for name in manifest['cards']:
            counts=best['metrics']['per_card'].get(name,{})
            if counts.get('truth',0)<5:continue
            thresholds[name]=max(trials,key=lambda trial:threshold_rank(trial,name))['threshold']
        selected_frames=replay(frames,cues,thresholds)
        selected_score=score_events([replace(f,timestamp_ms=round(c['available_timestamp_ms']))
            for f,c in zip(selected_frames,cues)],truth)
        loader=CardDataLoader();costs={n:float(loader.get_card(n)._raw_entry['manaCost']) for n in manifest['cards']}
        elapsed=sum((read(a.dataset/'evaluation_only'/e['episode_id']/'frames.jsonl')[-1]['timestamp_ms']-
            read(a.dataset/'evaluation_only'/e['episode_id']/'frames.jsonl')[0]['timestamp_ms'])/1000 for e in entries)
        probabilities,missed_rate,state_counts=calibrate_opponent_events(selected_frames,truth,elapsed)
        selection=dict(thresholds=thresholds,costs=costs,
            event_probabilities=probabilities,missed_rate=missed_rate,interval_margin=0.,
            state_event_match_window_ms=2000,state_event_counts=state_counts,
            selected_split='validation',trials=trials)
    else:selection=json.loads(a.selection.read_text())
    prediction=replay(frames,cues,selection['thresholds'])
    scored=[replace(f,timestamp_ms=round(c['available_timestamp_ms'])) for f,c in zip(prediction,cues)]
    events=score_events(scored,truth)
    derived=derived_metrics(a.dataset,entries,prediction,cues,selection,a.output)
    nonconformity=derived.pop('nonconformity')
    residuals=derived.pop('signed_residuals')
    if a.selection is None:
        selection['calibration_residuals']=np.quantile(residuals,np.linspace(.01,.99,63)).tolist() if residuals else None
        selection['calibration_samples']=len(nonconformity)
        (a.output/'selection.json').write_text(json.dumps(selection,indent=2)+'\n')
    gates=dict(event_recall=events['recall']>=.9,event_precision=events['precision']>=.9,
        placement=events['placement_within_one_all_plays']>=.9,
        elixir_mae=derived['elixir_mae'] is not None and derived['elixir_mae']<=.75,
        uncertainty_coverage=derived['interval90_coverage'] is not None and .85<=derived['interval90_coverage']<=.95,
        concentrated_hand=derived['hand_accuracy_when_concentrated'] is not None and derived['hand_accuracy_when_concentrated']>=.9,
        frame_timing_certified=all(json.loads((a.audit/e['episode_id']/'complete.json').read_text())['timing_certified'] for e in entries))
    metrics=dict(split=a.split,events=events,derived=derived,gates=gates,L2_ready=all(gates.values()),
        selection_sha256=hashlib.sha256((a.selection or a.output/'selection.json').read_bytes()).hexdigest(),
        note='Posterior scored at one-second native query times using only already-completed pixel predictions and elapsed host time.')
    (a.output/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
    progress(f"v3 {a.split}: recall {events['recall']:.3f}, precision {events['precision']:.3f}, placement {events['placement_within_one_all_plays']:.3f}; gates {gates}.")


if __name__=='__main__':main()
