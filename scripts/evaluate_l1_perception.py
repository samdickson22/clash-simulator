"""Score frozen pixel predictions against separate offline L1 truth."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from collections import Counter,defaultdict
from dataclasses import asdict
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment
from clasher.vision.l1_perception import ACTION_NAMES

from clasher.rl.live_inference_contract import (
    EvaluationLabels, ModelPrediction, PlacementPrediction, evaluate_predictions,
    parse_public_vision_frame,
)


def read(path):
    return [json.loads(l) for l in path.read_text().splitlines()]


def mean(values):
    return float(np.mean(values)) if values else None


def match_entities(predicted, truth):
    """Post-inference association only; identity/owner errors cannot match."""
    if not predicted or not truth:
        return []
    distances=np.full((len(predicted),len(truth)),1e6)
    for i,p in enumerate(predicted):
        for j,t in enumerate(truth):
            if (ACTION_NAMES.get(p.card,p.card),p.player_id)==(t['card'],t['player_id']):
                distances[i,j]=math.hypot(p.x_tiles-t['x_tiles'],p.y_tiles-t['y_tiles'])
    ii,jj=linear_sum_assignment(distances)
    return [(int(i),int(j),float(distances[i,j])) for i,j in zip(ii,jj) if distances[i,j]<=3]


def score(dataset, prediction_path, prior_path):
    # Predictions are already frozen before labels/private evaluation truth open.
    frames=[parse_public_vision_frame(r) for r in read(prediction_path)]
    labels={(r['episode_id'],r['frame_id']):r for r in read(dataset/'labels.jsonl') if r['split']=='heldout'}
    truth={(r['episode_id'],r['frame_id']):r for r in read(dataset/'evaluation_only/truth.jsonl')}
    events=defaultdict(list)
    for e in read(dataset/'evaluation_only/events.jsonl'):
        events[e['episode_id']].append(e)
    if {(f.episode_id,f.frame_id) for f in frames} != set(labels):
        raise ValueError('Prediction/heldout frame coverage differs')
    prior=json.loads(prior_path.read_text())
    module_path=Path(__file__).resolve().parents[1]/'reports/strategy_council_20260928/srp-public/derived_public_state.py'
    spec=importlib.util.spec_from_file_location('l1_derived_readonly',module_path)
    module=importlib.util.module_from_spec(spec)
    # Execute the unchanged upstream source without creating bytecode files
    # in the protected srp-public directory.
    exec(compile(module_path.read_text(),str(module_path),'exec'),module.__dict__)
    per_card=defaultdict(Counter)
    position_errors=[]; hp_errors=[]; tower_hp_errors=[]
    total_truth=total_predictions=correct=within_one=hand_correct=hand_total=next_correct=elixir_correct=0
    hand_all=0; elixir_errors=[]; clock_errors=[]; clock_missing=0
    derived_errors=[]; derived_hand_correct=derived_hand_known=derived_hand_total=0
    collapse_episodes=[]; states=[]
    contract_pred=[]; contract_truth=[]
    event_tp=event_fp=event_total=0
    current=None; tracker=None; history=[]; last_tick=0; previous_truth_tick=0
    for step,f in enumerate(frames):
        key=(f.episode_id,f.frame_id); row=labels[key]; t=row['targets']; private=truth[key]
        if current!=f.episode_id:
            current=f.episode_id; history=[]; last_tick=0; previous_truth_tick=0
            tracker=module.DerivedPublicState(prior,prior['costs'])
        # Derivation uses only the perceived public clock and perceived plays.
        if f.visible_clock_seconds is not None:
            perceived_tick=max(last_tick, round((180-f.visible_clock_seconds)*20+10))
        else:
            perceived_tick=last_tick
        if tracker is not None:
            for e in f.play_events:
                if e.player_id==0:
                    history.append((perceived_tick,e.card))
            try:
                tracker.update(perceived_tick,history)
                derived=tracker.derived()
                derived_elixir=tracker.elixir_units/10000
                derived_cycle={n:0 for n in (derived['hand'] or ()) if n is not None}
                for index,(n,known) in enumerate(zip(derived['cycle_positions'],derived['cycle_positions_known'])):
                    if known and n is not None:
                        derived_cycle[n]=min(4,index+1)
                derived_errors.append(abs(derived_elixir-private['opponent_elixir']))
                derived_hand_total+=1
                if derived['hand'] is not None:
                    derived_hand_known+=1
                    derived_hand_correct+=int(sorted(n for n in derived['hand'] if n is not None)==sorted(private['opponent_hand']))
                states.append(dict(episode_id=current,frame_id=f.frame_id,opponent_elixir=derived_elixir,
                                   hand=derived['hand'],posterior_size=len(tracker.states)))
            except (ValueError,KeyError,IndexError) as error:
                collapse_episodes.append(dict(episode_id=current,frame_id=f.frame_id,error=str(error)))
                tracker=None; derived_elixir=None; derived_cycle={}
        else:
            derived_elixir=None; derived_cycle={}
        last_tick=perceived_tick
        if f.visible_clock_seconds is None: clock_missing+=1
        else: clock_errors.append(abs(f.visible_clock_seconds-t['visible_clock_seconds']))
        hand_total+=4
        hand_correct+=sum(a==b for a,b in zip(f.own_hand,t['own_hand']))
        hand_all+=int(list(f.own_hand)==t['own_hand'])
        next_correct+=int(f.own_next_card==t['own_next_card'])
        if f.own_elixir is not None:
            elixir_errors.append(abs(f.own_elixir-t['own_elixir']))
            elixir_correct+=int(round(f.own_elixir)==int(t['own_elixir']))
        total_truth+=len(t['entities']); total_predictions+=len(f.entities)
        matched=match_entities(f.entities,t['entities'])
        correct+=len(matched)
        pred_hp={}; label_hp={}
        for j,entity in enumerate(t['entities']):
            label_hp[f'gt-{j}']=entity['hp_fraction']
            per_card[entity['card']]['truth']+=1
        for i,j,error in matched:
            p,gt=f.entities[i],t['entities'][j]
            position_errors.append(error); within_one+=int(error<=1)
            per_card[gt['card']]['matched']+=1
            per_card[gt['card']]['within_one']+=int(error<=1)
            if p.hp_fraction is not None:
                hp_errors.append(abs(p.hp_fraction-gt['hp_fraction']))
                pred_hp[f'gt-{j}']=p.hp_fraction
                if gt['card'] in ('Tower','KingTower'):
                    tower_hp_errors.append(abs(p.hp_fraction-gt['hp_fraction']))
        expected=[e for e in events[current] if previous_truth_tick<e['tick']<=private['tick']]
        previous_truth_tick=private['tick']
        event_total+=len(expected)
        # Match play identities within the current cadence interval. Missing
        # events, including spells, remain in the contract denominator.
        remaining=set(range(len(f.play_events))); pp=[]; lp=[]
        for j,e in enumerate(expected):
            event_id=f'event-{j}'
            lp.append(PlacementPrediction(event_id,e['x_tiles'],e['y_tiles']))
            candidates=[i for i in remaining if (f.play_events[i].player_id,f.play_events[i].card)==(e['player_id'],e['card'])]
            if candidates:
                i=min(candidates,key=lambda k: math.hypot(f.play_events[k].x_tiles-e['x_tiles'],f.play_events[k].y_tiles-e['y_tiles'])
                      if f.play_events[k].x_tiles is not None else float('inf'))
                p=f.play_events[i]; remaining.remove(i); event_tp+=1
                if p.x_tiles is not None:
                    pp.append(PlacementPrediction(event_id,p.x_tiles,p.y_tiles))
        event_fp+=len(remaining)
        for i in remaining:
            p=f.play_events[i]
            if p.x_tiles is not None:
                pp.append(PlacementPrediction(f'extra-{i}',p.x_tiles,p.y_tiles))
        digest=hashlib.sha256(json.dumps(history).encode()).hexdigest()
        contract_pred.append(ModelPrediction(current,f.frame_id,step,digest,f.visible_clock_seconds,
                                             derived_elixir,derived_cycle,tuple(pp),pred_hp,{}))
        true_cycle={n:0 for n in private['opponent_hand']}
        true_cycle.update({n:min(4,i+1) for i,n in enumerate(private['opponent_cycle'])})
        contract_truth.append(EvaluationLabels('heldout',current,f.frame_id,t['visible_clock_seconds'],
                                               private['opponent_elixir'],true_cycle,tuple(lp),label_hp,{}))
    report=dict(frames=len(frames),clock=dict(mae_seconds=mean(clock_errors),missing=clock_missing),
                entities=dict(truth=total_truth,predictions=total_predictions,matched=correct,
                    precision=correct/max(1,total_predictions),recall=correct/max(1,total_truth),
                    within_one_tile_all_truth=within_one/max(1,total_truth),
                    matched_mean_error_tiles=mean(position_errors),per_card=dict(per_card)),
                hp=dict(mae=mean(hp_errors),coverage=len(hp_errors)/max(1,total_truth),
                        samples=len(hp_errors),tower_mae=mean(tower_hp_errors)),
                hud=dict(hand_slot_accuracy=hand_correct/max(1,hand_total),
                         full_hand_accuracy=hand_all/len(frames),next_accuracy=next_correct/len(frames),
                         own_elixir_integer_accuracy=elixir_correct/len(frames),own_elixir_mae=mean(elixir_errors)),
                events=dict(true_positive=event_tp,false_positive=event_fp,truth=event_total,
                            precision=event_tp/max(1,event_tp+event_fp),recall=event_tp/max(1,event_total)),
                derived=dict(elixir_mae=mean(derived_errors),valid_frames=len(derived_errors),
                             coverage=len(derived_errors)/len(frames),hand_resolved=derived_hand_known,
                             hand_accuracy_when_resolved=derived_hand_correct/derived_hand_known if derived_hand_known else None,
                             hand_exact_recovery_rate=derived_hand_correct/len(frames),
                             hand_unknown_frames=len(frames)-derived_hand_known,
                             hand_resolution_coverage=derived_hand_known/len(frames),posterior_collapses=collapse_episodes,
                             source_sha256=hashlib.sha256(module_path.read_bytes()).hexdigest(),
                             prior_sha256=hashlib.sha256(prior_path.read_bytes()).hexdigest(),
                             time_source='perceived clock midpoint, monotonically clamped; no native tick input'),
                contract=evaluate_predictions(contract_pred,contract_truth),
                limitations=['weak pixel boxes','no spell detector','no status reader',
                             'play cues from body-track births','unknown HP is not imputed',
                             'derived posterior failures stop derivation; no truth repair'])
    return report,states,contract_pred,contract_truth


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',type=Path,required=True)
    p.add_argument('--predictions',type=Path,required=True)
    p.add_argument('--prior',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    report,states,predictions,labels=score(args.dataset,args.predictions,args.prior)
    report['predictions_sha256']=hashlib.sha256(args.predictions.read_bytes()).hexdigest()
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'metrics.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    (args.output/'derived.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in states))
    for filename,items,is_prediction in [('contract-predictions.jsonl',predictions,True),
                                          ('contract-labels.jsonl',labels,False)]:
        records=[]
        for item in items:
            values=asdict(item)
            identity={key:values.pop(key) for key in ('episode_id','frame_id')}
            if is_prediction:
                identity.update({key:values.pop(key) for key in ('state_step','state_digest')})
            else:
                identity['split']=values.pop('split')
            records.append(dict(schema_version=1,**identity,
                                **{'predictions' if is_prediction else 'labels':values}))
        (args.output/filename).write_text(''.join(json.dumps(r)+'\n' for r in records))
    print(json.dumps({k:report[k] for k in ('frames','clock','hp','hud','events','derived')}))


if __name__=='__main__':
    main()
