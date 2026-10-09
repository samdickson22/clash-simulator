"""Seed-paired bootstrap, common ledger metrics, latency and affordability."""
import argparse,hashlib,json
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from clasher.analysis.loss_review.summarize import bootstrap_matrix
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--reps',type=int,default=2000);a=p.parse_args();root=a.root
selection=json.loads((root/'selection.json').read_text());arms=['0','E','H12','H16','W',selection['combination_arm']];rows={k:{} for k in arms}
for f in (root/'reporting').glob('*/games/*.json'):
 r=json.loads(f.read_text());arm=r['cohort'];seed=r['metadata']['seed'];assert arm in rows and seed not in rows[arm] and r['role']=='exploration' and r['metadata']['terminal'];rows[arm][seed]=r
assert all(len(rows[k])==1000 and rows[k].keys()==rows['0'].keys() for k in arms)
seeds=sorted(rows['0']);assert seeds==list(range(2**48+70010,2**48+71010))
for seed in seeds:
 ref=rows['0'][seed]['metadata']
 for arm in arms:
  assert all(rows[arm][seed]['metadata'][k]==ref[k] for k in ('seed','seat','style','own_deck','opponent_deck','delay_ticks'))
metrics=['game_loss_fraction','game_win_fraction','game_draw_fraction','arrival_under4_fraction','defender_not_in_hand_fraction','no_affordable_defender_in_hand_fraction','time_at_max_fraction','leaked_elixir_lower_bound_per_minute']
# Select ledger's exact cap metric spelling rather than inventing a new one.
common=set().union(*(r['stats']['all'].keys() for r in rows['0'].values()))
metrics=[m for m in metrics if m.startswith('game_') or m in common]
metrics+=sorted(m for m in common if ('cap' in m or 'time_at_max' in m) and m not in metrics)
cards=['Xbow','Giant','Rocket','Fireball','Log'];metrics += ['card_per_deck_minute:'+n for n in cards]
metrics += ['affordable_hand_fraction:'+n for n in cards]
metrics += ['selected_given_offered_fraction:'+n for n in cards]
metrics += ['mean_active_wall_decision_ms','mean_raw_wall_decision_ms','mean_cpu_decision_ms','raw_wall_over200_fraction']
matrix=np.zeros((1000,len(arms)*len(metrics),2));latency={};attrition={};outcomes={};wait_counts={}
def timing(xs):
 v=np.array(xs);return dict(decisions=len(v),p50_ms=float(np.quantile(v,.5)*1000),p95_ms=float(np.quantile(v,.95)*1000),p99_ms=float(np.quantile(v,.99)*1000),max_ms=float(v.max()*1000),over200_fraction=float(np.mean(v>.2)))
for ai,arm in enumerate(arms):
 lat=[];raw=[];cpu=[];attrs=defaultdict(Counter);waits=Counter();loss=win=draw=0
 for si,seed in enumerate(seeds):
  r=rows[arm][seed];ab=r['search_ab'];s=dict(r['stats']['all']);meta=r['metadata'];lost=r['loss'];won=meta['winner']==meta['seat'];drawn=meta['winner'] is None
  loss+=lost;win+=won;draw+=drawn
  s.update(game_loss_fraction=[lost,1],game_win_fraction=[won,1],game_draw_fraction=[drawn,1])
  s.update(mean_active_wall_decision_ms=[1000*sum(ab['latency_seconds']),len(ab['latency_seconds'])],mean_raw_wall_decision_ms=[1000*sum(ab['raw_wall_latency_seconds']),len(ab['raw_wall_latency_seconds'])],mean_cpu_decision_ms=[1000*sum(ab['cpu_latency_seconds']),len(ab['cpu_latency_seconds'])],raw_wall_over200_fraction=[sum(t>.2 for t in ab['raw_wall_latency_seconds']),len(ab['raw_wall_latency_seconds'])])
  for card in cards:
   t=ab['attrition'].get(card,{})
   s['affordable_hand_fraction:'+card]=[t.get('affordable',0),t.get('in_hand',0)]
   s['selected_given_offered_fraction:'+card]=[t.get('selected',0),t.get('scored_opportunities',0)]
  for mi,m in enumerate(metrics):matrix[si,ai*len(metrics)+mi]=s.get(m,[0,0])
  lat+=ab['latency_seconds'];raw+=ab['raw_wall_latency_seconds'];cpu+=ab['cpu_latency_seconds'];waits.update(ab['wait_counts'])
  for card,t in ab['attrition'].items():attrs[card].update(t)
 latency[arm]=dict(active_wall=timing(lat),raw_wall=timing(raw),process_cpu=timing(cpu));attrition[arm]=dict(attrs);wait_counts[arm]=dict(waits);outcomes[arm]=dict(wins=win,losses=int(loss),draws=draw)
point,boots,total=bootstrap_matrix(matrix,8097008,a.reps);estimates={};contrasts={}
for ai,arm in enumerate(arms):
 estimates[arm]={}
 for mi,m in enumerate(metrics):
  k=ai*len(metrics)+mi;good=boots[:,k][np.isfinite(boots[:,k])]
  estimates[arm][m]=dict(value=float(point[k]) if np.isfinite(point[k]) else None,ci95=np.quantile(good,[.025,.975]).tolist() if len(good) else None,numerator=float(total[k,0]),denominator=float(total[k,1]))
 if ai:
  contrasts[arm]={}
  for mi,m in enumerate(metrics):
   k=ai*len(metrics)+mi;diff=boots[:,k]-boots[:,mi];good=diff[np.isfinite(diff)]
   contrasts[arm][m]=dict(difference=float(point[k]-point[mi]) if np.isfinite(point[k]-point[mi]) else None,ci95=np.quantile(good,[.025,.975]).tolist() if len(good) else None)
result=dict(lane='exploration',confirmatory=False,pre_registered=False,eval_heldout_access=False,paired_seeds=1000,arms=arms,seed_range=[seeds[0],seeds[-1]],bootstrap=dict(reps=a.reps,unit='paired seed; shared draws across every arm and metric; pooled numerator/denominator ratios',interval='pointwise percentile, exploratory, unadjusted'),selection=selection,seed_audit=json.loads((root/'seed-audit.json').read_text()),outcomes=outcomes,estimates=estimates,paired_contrasts=contrasts,latency=latency,attrition=attrition,wait_counts=wait_counts,budget_ms=200,required_latency_budget_met=all(latency[k]['raw_wall']['over200_fraction']==0 for k in arms))
(root/'results.json').write_text(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n')
print(json.dumps(dict(outcomes=outcomes,loss_contrasts={k:v['game_loss_fraction'] for k,v in contrasts.items()},latency=latency)))
