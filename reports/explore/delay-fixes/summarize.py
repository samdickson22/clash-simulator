"""Paired-seed ratio bootstrap; exploration-only, pointwise percentile CIs."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np

ARMS=['U0','U27','S0','S27','N2','N4','I0','IF']
METRICS=['win_fraction','loss_fraction','arrival_under4_fraction',
 'post_submission_no_followup_27ticks_fraction','post_execution_no_followup_27ticks_fraction',
 'post_play_no_submission_27ticks_fraction','pending_blocked_decision_fraction',
 'interplay_gap_seconds','no_affordable_defender_in_hand_fraction',
 'response_latency_capped8_seconds','rejected_play_fraction','wincon_low_reserve_fraction',
 'wincon_into_active_threat_fraction','time_at_max_fraction']
CONTRASTS={'opponent_delay_d0':('S0','U0'),'opponent_delay_d27':('S27','U27'),'latency_undelayed':('U27','U0'),
 'latency_delayed':('S27','S0'),'two_outstanding':('N2','S27'),
 'four_outstanding':('N4','S27'),'four_vs_two_outstanding':('N4','N2'),'forward_imitation':('IF','I0'),
 'current_imitation_vs_search':('I0','S27')}


def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
 ap.add_argument('--controls-source',type=Path)
 ap.add_argument('--allow-partial-controls',action='store_true')
 ap.add_argument('--bootstrap',type=int,default=5000);ap.add_argument('--expected-pairs',type=int,required=True)
 a=ap.parse_args();groups={arm:{} for arm in ARMS};hashes={};cpu=0
 for path in sorted(a.source.glob('p*/games/*.json')):
  row=json.loads(path.read_text());arm=row['cohort'];seed=row['metadata']['seed']
  if arm not in groups or seed in groups[arm]:raise ValueError('unexpected/duplicate game')
  if row['role']!='exploration' or not row['metadata']['terminal']:raise ValueError('nonterminal or forbidden role')
  groups[arm][seed]=row;cpu+=row['cpu_seconds']
  hashes[str(path.relative_to(a.source))]=hashlib.sha256(path.read_bytes()).hexdigest()
 control_counts={}
 if a.controls_source:
  groups.update(R0={},R27={})
  for path in sorted(a.controls_source.glob('p*/games/*.json')):
   row=json.loads(path.read_text());cohort=row['cohort'];seed=row['metadata']['seed']
   if cohort not in ('S0','S27'):raise ValueError('unexpected control arm')
   arm={'S0':'R0','S27':'R27'}[cohort]
   schedule=json.loads((path.parent.parent/'schedule.json').read_text())
   if schedule['options']['opponent_delay']!=0 or schedule['options']['opponent_interval']!=10:
    raise ValueError('control timing configuration mismatch')
   if seed in groups[arm] or row['role']!='exploration' or not row['metadata']['terminal']:
    raise ValueError('duplicate/nonterminal/forbidden control game')
   groups[arm][seed]=row;cpu+=row['cpu_seconds']
   hashes['lag-only/'+str(path.relative_to(a.controls_source))]=hashlib.sha256(path.read_bytes()).hexdigest()
 seeds=sorted(groups['U0'])
 if len(seeds)!=a.expected_pairs or any(set(groups[arm])!=set(seeds) for arm in ARMS):
  raise ValueError('incomplete paired arm schedule')
 if seeds!=list(range(2**48+50000,2**48+50000+a.expected_pairs)):
  raise ValueError('unexpected main seed namespace/schedule')
 if a.controls_source:
  for arm in ('R0','R27'):
   if set(groups[arm])-set(seeds):raise ValueError('unexpected control seeds')
   if len(groups[arm])!=len(seeds) and not a.allow_partial_controls:raise ValueError('incomplete controls')
  control_counts={arm:len(groups[arm]) for arm in ('R0','R27')}
 rng=np.random.default_rng(2**48+59001)
 weights=rng.multinomial(len(seeds),np.full(len(seeds),1/len(seeds)),size=a.bootstrap).astype(np.float64)
 def estimate(values,draw_weights=None):
  if draw_weights is None:draw_weights=weights
  num,den=values.sum(axis=0)
  point=float(num/den) if den else None
  totals=draw_weights@values
  samples=np.divide(totals[:,0],totals[:,1],out=np.full(a.bootstrap,np.nan),where=totals[:,1]>0)
  return dict(value=point,ci95=np.nanquantile(samples,[.025,.975]).tolist(),numerator=float(num),denominator=float(den)),samples
 estimates={};samples={};latencies={}
 for arm in groups:
  arm_seeds=sorted(groups[arm])
  if not arm_seeds:continue
  arm_weights=weights if arm_seeds==seeds else np.random.default_rng(2**48+59001).multinomial(len(arm_seeds),np.full(len(arm_seeds),1/len(arm_seeds)),size=a.bootstrap).astype(np.float64)
  rows=[groups[arm][s] for s in arm_seeds];estimates[arm]={};samples[arm]={}
  for metric in METRICS:
   values=np.asarray([r['stats']['all'].get(metric,[0,0]) for r in rows],float)
   if values[:,1].sum():
    estimates[arm][metric],samples[arm][metric]=estimate(values,arm_weights)
  lat=[v for r in rows if r['delay_fixes'].get('latency_clock')=='active-wall-v1' for v in r['delay_fixes']['latency_seconds']]
  legacy_lat=[v for r in rows if r['delay_fixes'].get('latency_clock')!='active-wall-v1' for v in r['delay_fixes']['latency_seconds']]
  raw_lat=[v for r in rows for v in r['delay_fixes'].get('raw_wall_latency_seconds',r['delay_fixes']['latency_seconds'])]
  quantiles=lambda values:np.quantile(values,[.5,.95,.99]).tolist() if values else None
  cpu_lat=[v for r in rows for v in r['delay_fixes']['cpu_latency_seconds']]
  latencies[arm]=dict(cpu_p50_p95_p99_seconds=np.quantile(cpu_lat,[.5,.95,.99]).tolist(),cpu_over200ms=sum(v>.2 for v in cpu_lat),decisions=len(cpu_lat),active_wall_decisions=len(lat),legacy_wall_decisions=len(legacy_lat),latency_clock='active-wall-v1 only; legacy wall separate',p50_p95_p99_seconds=quantiles(lat),over200ms=sum(v>.2 for v in lat),legacy_wall_p50_p95_p99_seconds=quantiles(legacy_lat),raw_wall_p50_p95_p99_seconds=quantiles(raw_lat),
    channel_rejections=sum(r['metadata']['channel']['rejected'] for r in rows),
    opponent_rejections=sum(r['metadata']['opponent_channel']['rejected'] for r in rows),
    peak_pending=max(r['metadata']['channel']['peak_pending'] for r in rows),
    paired_seeds=len(rows),losses=sum(r['loss'] for r in rows),wins=sum(r['metadata']['win'] for r in rows),draws=sum(not r['loss'] and not r['metadata']['win'] for r in rows))
 contrasts={}
 for name,(treatment,control) in CONTRASTS.items():
  contrasts[name]=dict(treatment=treatment,control=control,paired_seeds=len(seeds),metrics={})
  for metric in METRICS:
   if metric not in samples[treatment] or metric not in samples[control]:continue
   point=estimates[treatment][metric]['value']-estimates[control][metric]['value']
   draws=samples[treatment][metric]-samples[control][metric]
   contrasts[name]['metrics'][metric]=dict(delta=point,ci95=np.nanquantile(draws,[.025,.975]).tolist())
 metric='loss_fraction'
 draws=(samples['U27'][metric]-samples['U0'][metric])-(samples['S27'][metric]-samples['S0'][metric])
 inflation=dict(delta=(estimates['U27'][metric]['value']-estimates['U0'][metric]['value'])-(estimates['S27'][metric]['value']-estimates['S0'][metric]['value']),
    ci95=np.quantile(draws,[.025,.975]).tolist())
 matched_inflation=None
 if a.controls_source:
  subset_cache={}
  def subset_estimates(arm,chosen):
   key=(arm,tuple(chosen))
   if key in subset_cache:return subset_cache[key]
   if chosen==seeds:
    subset_cache[key]=(estimates[arm],samples[arm]);return subset_cache[key]
   w=np.random.default_rng(2**48+59001).multinomial(len(chosen),np.full(len(chosen),1/len(chosen)),size=a.bootstrap).astype(np.float64)
   points={};draws={}
   for metric in METRICS:
    values=np.asarray([groups[arm][s]['stats']['all'].get(metric,[0,0]) for s in chosen],float)
    if values[:,1].sum():points[metric],draws[metric]=estimate(values,w)
   subset_cache[key]=(points,draws);return points,draws
  for name,(treatment,control) in {'lag_only_d0':('S0','R0'),'lag_only_d27':('S27','R27'),'latency_undelayed_matched':('R27','R0')}.items():
   chosen=sorted(set(groups[treatment])&set(groups[control]))
   contrasts[name]=dict(treatment=treatment,control=control,paired_seeds=len(chosen),metrics={})
   if not chosen:continue
   tp,td=subset_estimates(treatment,chosen);cp,cd=subset_estimates(control,chosen)
   for metric in METRICS:
    if metric not in td or metric not in cd:continue
    contrasts[name]['metrics'][metric]=dict(delta=tp[metric]['value']-cp[metric]['value'],ci95=np.nanquantile(td[metric]-cd[metric],[.025,.975]).tolist())
  common=sorted(set(groups['R0'])&set(groups['R27']))
  if common:
   values={arm:subset_estimates(arm,common) for arm in ('R0','R27','S0','S27')};metric='loss_fraction'
   point=lambda arm:values[arm][0][metric]['value']
   draw=lambda arm:values[arm][1][metric]
   draws=(draw('R27')-draw('R0'))-(draw('S27')-draw('S0'))
   matched_inflation=dict(delta=(point('R27')-point('R0'))-(point('S27')-point('S0')),ci95=np.quantile(draws,[.025,.975]).tolist(),paired_seeds=len(common))
 out=dict(purpose='non-confirmatory exploration',paired_seeds=len(seeds),games=sum(len(v) for v in groups.values()),
    seed_namespace='2**48 + 50000 + i',seed_range=[seeds[0],seeds[-1]],bootstrap=dict(draws=a.bootstrap,unit='paired seed',method='pooled numerator/denominator ratios; percentile 95%; pointwise, uncorrected'),
    arms=estimates,contrasts=contrasts,loss_latency_asymmetry_inflation=inflation,
    control_completion=dict(target_pairs=a.expected_pairs,completed_by_arm=control_counts,paired_common=len(set(groups.get('R0',{}))&set(groups.get('R27',{}))),status='complete' if control_counts and all(n==len(seeds) for n in control_counts.values()) else 'partial' if a.controls_source else 'not run'),matched_loss_latency_asymmetry_inflation=matched_inflation,diagnostics=latencies,worker_cpu_seconds=cpu)
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,separators=(',',':'))+'\n')
 (a.out.parent/'game-hashes.json').write_text(json.dumps(hashes,separators=(',',':'))+'\n')
 print(json.dumps({k:out[k] for k in ['paired_seeds','games','loss_latency_asymmetry_inflation','diagnostics']},indent=2))


if __name__=='__main__':main()
