"""Strict v1 timing, per-card, visibility and HP scoring of frozen predictions."""
import argparse
from dataclasses import asdict
from collections import Counter, defaultdict
import json
import hashlib
import math
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

from clasher.rl.live_inference_contract import parse_public_vision_frame
from clasher.vision.l1_perception import ACTION_NAMES
from evaluate_l1_perception import read, score, match_entities, mean


def perfect_event_reference(dataset,frames,states,prior):
    """Evaluation-only ceiling; no truth repairs enter perceived states."""
    path=Path(__file__).resolve().parents[1]/'reports/strategy_council_20260928/srp-public/derived_public_state.py'
    namespace={'__name__':'l1_oracle_reference','__file__':str(path)}
    exec(compile(path.read_text(),str(path),'exec'),namespace)
    population=json.loads(prior.read_text())
    truth={(r['episode_id'],r['frame_id']):r for r in read(dataset/'evaluation_only/truth.jsonl')}
    events=defaultdict(list)
    for event in read(dataset/'evaluation_only/events.jsonl'):
        if event['player_id']==0:events[event['episode_id']].append((event['tick'],event['card']))
    perceived={(s['episode_id'],s['frame_id']):s for s in states}
    errors=[];known=oracle_correct=prediction_known=prediction_correct=0;failures=[];current=None
    for f in frames:
        key=f.episode_id,f.frame_id;t=truth[key]
        if current!=f.episode_id:
            current=f.episode_id
            tracker=namespace['DerivedPublicState'](population,population['costs'])
        if tracker is None:continue
        try:
            tracker.update(t['tick'],[e for e in events[current] if e[0]<=t['tick']])
            state=tracker.derived();errors.append(abs(tracker.elixir_units/10000-t['opponent_elixir']))
            if state['hand'] is not None:
                known+=1
                expected=sorted(t['opponent_hand'])
                oracle_correct+=sorted(c for c in state['hand'] if c is not None)==expected
                hand=perceived.get(key,{}).get('hand')
                prediction_known+=hand is not None
                prediction_correct+=hand is not None and sorted(c for c in hand if c is not None)==expected
        except (ValueError,KeyError,IndexError) as error:
            failures.append(dict(episode_id=current,frame_id=f.frame_id,error=str(error)));tracker=None
    return dict(scope='Evaluation-only true accepted plays and native ticks; never model inputs',
                elixir_mae=mean(errors),valid_frames=len(errors),hand_determined_frames=known,
                oracle_hand_accuracy=oracle_correct/known if known else None,
                perceived_hand_accuracy_on_determined_frames=prediction_correct/known if known else None,
                perceived_hand_coverage_on_determined_frames=prediction_known/known if known else None,
                failures=failures)


def timed_events(frames, expected):
    observed=[dict(episode=f.episode_id,time=f.timestamp_ms,event=e)
              for f in frames for e in f.play_events]
    costs=np.full((len(observed),len(expected)),1e9)
    for i,p in enumerate(observed):
        for j,t in enumerate(expected):
            e=p['event'];delay=p['time']-t['tick']*50
            if (p['episode'],e.player_id,e.card)==(t['episode_id'],t['player_id'],t['card']) and 0<=delay<=500:
                costs[i,j]=delay
    pairs=[]
    if costs.size:
        ii,jj=linear_sum_assignment(costs)
        pairs=[(int(i),int(j)) for i,j in zip(ii,jj) if costs[i,j]<1e9]
    placed=[];delays=[];by_card=defaultdict(Counter);by_owner=defaultdict(Counter)
    for t in expected:
        by_card[t['card']]['truth']+=1;by_owner[str(t['player_id'])]['truth']+=1
    for p in observed:
        by_card[p['event'].card]['predictions']+=1;by_owner[str(p['event'].player_id)]['predictions']+=1
    for i,j in pairs:
        p,t=observed[i],expected[j];e=p['event']
        by_card[t['card']]['matched']+=1;by_owner[str(t['player_id'])]['matched']+=1
        delays.append(float(costs[i,j]))
        if e.x_tiles is not None:
            d=math.hypot(e.x_tiles-t['x_tiles'],e.y_tiles-t['y_tiles']);placed.append(d)
            by_card[t['card']]['placed_within_one']+=int(d<=1)
            by_owner[str(t['player_id'])]['placed_within_one']+=int(d<=1)
    hit=sum(x<=1 for x in placed)
    return dict(truth=len(expected),predictions=len(observed),matched_within_500_ms=len(pairs),
                false_positive=len(observed)-len(pairs),missed=len(expected)-len(pairs),
                recall=len(pairs)/max(1,len(expected)),precision=len(pairs)/max(1,len(observed)),
                mean_delay_ms=mean(delays),p95_delay_ms=float(np.quantile(delays,.95)) if delays else None,
                placement_readings=len(placed),within_one=hit,
                placement_within_one_all_plays=hit/max(1,len(expected)),
                placement_within_one_detected=hit/max(1,len(pairs)),
                conditional_placement_within_one=hit/len(placed) if placed else None,
                per_card=dict(by_card),per_owner=dict(by_owner))


def evaluate(dataset,predictions,prior):
    base,states,contract_predictions,contract_labels=score(dataset,predictions,prior)
    frames=[parse_public_vision_frame(r) for r in read(predictions)]
    keys=[(f.episode_id,f.frame_id) for f in frames]
    if len(set(keys))!=len(keys):raise ValueError('Duplicate prediction frames')
    labels={(r['episode_id'],r['frame_id']):r for r in read(dataset/'labels.jsonl') if r['split']=='heldout'}
    episodes={f.episode_id for f in frames}
    events=[e for e in read(dataset/'evaluation_only/events.jsonl') if e['episode_id'] in episodes]
    per_card=defaultdict(Counter);positions=defaultdict(list);hp=[];visible_hp=[]
    bodies=visible=uncertain=0
    for f in frames:
        truth=labels[f.episode_id,f.frame_id]['targets']['entities']
        for e in truth:
            per_card[e['card']]['truth']+=1
            if e['card'] not in ('Tower','KingTower'):
                bodies+=1;visible+=e.get('visibility')=='visible';uncertain+=e.get('visibility')!='visible'
        for e in f.entities:per_card[ACTION_NAMES.get(e.card,e.card)]['predictions']+=1
        for i,j,d in match_entities(f.entities,truth):
            p,t=f.entities[i],truth[j];card=t['card']
            per_card[card]['matched']+=1;per_card[card]['within_one']+=int(d<=1);positions[card].append(d)
            if card not in ('Tower','KingTower') and p.hp_fraction is not None:
                err=abs(p.hp_fraction-t['hp_fraction']);hp.append(err)
                per_card[card]['hp_readings']+=1;per_card[card]['hp_absolute_error_sum']+=err
                if t.get('visibility')=='visible':visible_hp.append(err)
    for card,counts in per_card.items():
        for key in ('truth','predictions','matched','within_one','hp_readings','hp_absolute_error_sum'):
            counts.setdefault(key,0)
        counts['precision']=counts['matched']/counts['predictions'] if counts['predictions'] else None
        counts['recall']=counts['matched']/counts['truth'] if counts['truth'] else None
        counts['position_mean_tiles']=mean(positions[card])
        counts['position_p95_tiles']=float(np.quantile(positions[card],.95)) if positions[card] else None
        counts['within_one_all_truth']=counts['within_one']/counts['truth'] if counts['truth'] else None
        counts['hp_mae']=counts['hp_absolute_error_sum']/counts['hp_readings'] if counts['hp_readings'] else None
    base['entities']['per_card_v1']=dict(per_card)
    base['events_v1']=timed_events(frames,events)
    costs=json.loads(prior.read_text())['costs']
    true_spend=sum(costs[e['card']] for e in events if e['player_id']==0)
    perceived_spend=sum(costs[e.card] for f in frames for e in f.play_events if e.player_id==0)
    base['event_error_propagation']=dict(opponent_true_spend=true_spend,opponent_perceived_spend=perceived_spend,
        missed_minus_extra_spend=true_spend-perceived_spend,
        interpretation='Missing spend raises the derived elixir estimate until the cap; extra or wrong plays lower it and can eliminate every hand/order. This spend difference is a diagnostic, not the actual elixir error.')
    base['non_tower_hp']=dict(truth=bodies,readings=len(hp),coverage=len(hp)/max(1,bodies),mae=mean(hp),
                             certified_visible=visible,uncertain_visibility=uncertain,
                             visible_readings=len(visible_hp),visible_coverage=len(visible_hp)/visible if visible else None,
                             visible_mae=mean(visible_hp))
    reference=perfect_event_reference(dataset,frames,states,prior)
    base['perfect_event_reference']=reference
    base['gates_v1']=dict(
        entities=base['entities']['within_one_tile_all_truth']>=.9,
        events=base['events_v1']['recall']>=.9,
        placement=base['events_v1']['placement_within_one_all_plays']>=.9,
        hp=visible>0 and len(visible_hp)/visible>=.6 and mean(visible_hp) is not None and mean(visible_hp)<=.1,
        clock=base['clock']['missing']==0 and base['clock']['mae_seconds']<=1,
        derived_elixir=base['derived']['coverage']==1 and base['derived']['elixir_mae']<=.5,
        derived_hand=reference['hand_determined_frames']>0
            and reference['perceived_hand_accuracy_on_determined_frames']>=.9)
    base['limitations']=['All uncertain visibility labels retained in conservative all-object metrics',
                        'No opponent spell-effect detector; own spell HUD cues have unknown placement',
                        'No compositor tick fence or status reader',
                        'Event latency uses frozen media timestamps; excludes real capture and inference latency',
                        'Derived state stops at posterior collapse; no private-truth repairs']
    return base,states,contract_predictions,contract_labels


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('dataset','predictions','prior','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();result,states,predictions,labels=evaluate(a.dataset,a.predictions,a.prior)
    result['predictions_sha256']=hashlib.sha256(a.predictions.read_bytes()).hexdigest()
    a.output.mkdir(parents=True,exist_ok=False)
    (a.output/'metrics.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    (a.output/'derived.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in states))
    for name,items,is_prediction in [('contract-predictions.jsonl',predictions,True),
                                     ('contract-labels.jsonl',labels,False)]:
        records=[]
        for item in items:
            values=asdict(item)
            identity={key:values.pop(key) for key in ('episode_id','frame_id')}
            if is_prediction:
                identity.update({key:values.pop(key) for key in ('state_step','state_digest')})
            else:identity['split']=values.pop('split')
            records.append(dict(schema_version=1,**identity,
                                **{'predictions' if is_prediction else 'labels':values}))
        (a.output/name).write_text(''.join(json.dumps(r)+'\n' for r in records))
    print(json.dumps(result['gates_v1']),flush=True)


if __name__=='__main__':main()
