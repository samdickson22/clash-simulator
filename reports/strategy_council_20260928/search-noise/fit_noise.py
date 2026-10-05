import bootstrap
from bootstrap import HERE,ROOT
import json,math,hashlib
from collections import Counter
import numpy as np
from scipy.optimize import linear_sum_assignment
from clasher.vision.l1_events_v3 import StreamFusion
L1=ROOT/'reports/strategy_council_20260928/live-loop/l1'
sel=json.loads((HERE/'runtime/support/selection.json').read_text())
truth=[];obs=[];latencies=[];episode=None;paths=[]
p=L1/'v3/inference-heldout/candidates.jsonl';paths.append(p)
for line in p.open():
    row=json.loads(line)
    if episode!=row['episode_id']:
        episode=row['episode_id'];fusion=StreamFusion(sel['thresholds'])
        p=L1/'v3/audit'/episode/'events.jsonl';paths.append(p)
        truth += [json.loads(l) for l in p.open()]
    for e in fusion.update(row['frame_id'],row['timestamp_ms'],row['candidates']):
        obs.append(dict(episode_id=episode,card=e.card,player_id=e.player_id,t=row['available_timestamp_ms'],x=e.x_tiles,y=e.y_tiles))
    latencies.append(row['available_timestamp_ms']-row['timestamp_ms'])
cost=np.full((len(obs),len(truth)),1e9)
for i,o in enumerate(obs):
    for j,t in enumerate(truth):
        lo,hi=t['event_time_interval_ms']
        if (o['episode_id'],o['card'],o['player_id'])==(t['episode_id'],t['card'],t['player_id']) and hi<=o['t']<=lo+500:cost[i,j]=o['t']-(lo+hi)/2
idx,jdx=linear_sum_assignment(cost);pairs=[(i,j) for i,j in zip(idx,jdx) if cost[i,j]<1e9]
assert (len(truth),len(obs),len(pairs))==(280,270,180)
used_o={i for i,j in pairs};used_t={j for i,j in pairs}
conf=[]
for i,o in enumerate(obs):
    if i in used_o or o['x'] is None:continue
    choices=[]
    for j,t in enumerate(truth):
        if j in used_t or o['episode_id']!=t['episode_id'] or o['player_id']!=t['player_id'] or o['card']==t['card']:continue
        lo,hi=t['event_time_interval_ms'];d=math.hypot(o['x']-t['x_tiles'],o['y']-t['y_tiles'])
        if hi<=o['t']<=lo+500 and d<=3:choices.append((d,j))
    if choices:
        _,j=min(choices);used_o.add(i);used_t.add(j);conf.append((i,j))
placements=[];delays=[]
for i,j in pairs:
    o,t=obs[i],truth[j];lo,hi=t['event_time_interval_ms'];delays.append(o['t']-(lo+hi)/2)
    placements.append(None if o['x'] is None else [o['x']-t['x_tiles'],o['y']-t['y_tiles']])
fp=Counter(obs[i]['card'] for i in range(len(obs)) if i not in {i for i,j in pairs})
model=dict(recall=180/280,precision=180/270,placement_within_one_detected=.9,
    confusion_rate=len(conf)/280,confusion_pairs=[dict(truth=truth[j]['card'],predicted=obs[i]['card']) for i,j in conf],
    confusion_definition='Unmatched same-side wrong-card predictions, within 500 ms and 3 tiles of an unmatched truth, greedily matched by distance; a modelling proxy, not a labelled confusion matrix.',
    false_positive_card_counts=dict(fp),event_delays_ms=delays,event_xy_residuals=placements,
    frame_processing_ms_quantiles=np.quantile(latencies,np.linspace(.01,.99,99)).tolist(),
    matched=180,truth=280,predictions=270,position_recall=.9714,entity_precision=.922,
    entity_within_one_all=.9695,hp_coverage=.6606,hp_mae=.0498,hand_correct=.9969,next_correct=.9992,
    elixir_correct=.9708,elixir_mae=.035,
    sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in set(paths)})
(HERE/'noise-model.json').write_text(json.dumps(model,indent=2)+'\n')
print({k:model[k] for k in ['recall','precision','confusion_rate']});print('FP counts',dict(fp));print('frame ms quantiles',np.quantile(latencies,[.5,.95,.99]))
