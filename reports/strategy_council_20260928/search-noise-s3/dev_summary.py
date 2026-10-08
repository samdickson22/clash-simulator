"""Calibration split only sets radius; validation is reported separately."""
from pathlib import Path
import argparse,json
import numpy as np
HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--round',default='v1');ap.add_argument('--partial',action='store_true');args=ap.parse_args()
files=sorted((HERE/f'dev-{args.round}').glob('*.json'))
if not args.partial:assert len(files)==56
allrows=[json.loads(p.read_text()) for p in files];out={};cal={}
for variant in ('T2-N97','T2-N90','T2-N64'):
 train=[s for row in allrows if row['index']<28 for key,ss in row['samples'].items() if key.endswith(variant) for s in ss]
 validation=[s for row in allrows if row['index']>=28 for key,ss in row['samples'].items() if key.endswith(variant) for s in ss]
 if not train:continue
 radius=float(np.quantile([r['residual'] for r in train],.9,method='higher'));cal[variant]=radius
 def summarize(rows,padding):
  if not rows:return None
  n=len(rows);coverage=[];width=[];mae=[];post=[];oldcov=[];oldwidth=[];oldmae=[]
  for r in rows:
   lo=max(0,r['lo']-padding);hi=min(10,r['hi']+padding);yes=lo<=r['truth']<=hi
   coverage.append(yes);width.append(hi-lo);mae.append(abs(r['mean']-r['truth']))
   if r['post_error']:post.append(yes)
   d=r['legacy'];a,b=d['elixir_interval_90'];oldcov.append(a<=r['truth']<=b);oldwidth.append(b-a);oldmae.append(abs(d['elixir_mean']-r['truth']))
  return dict(samples=n,coverage=float(np.mean(coverage)),width=float(np.mean(width)),mae=float(np.mean(mae)),post_error_samples=len(post),post_error_coverage=float(np.mean(post)) if post else None,hand90=float(np.mean([r['hand90'] for r in rows])),legacy=dict(coverage=float(np.mean(oldcov)),width=float(np.mean(oldwidth)),mae=float(np.mean(oldmae))))
 out[variant]=dict(radius=radius,train_raw=summarize(train,0),train_calibrated=summarize(train,radius),validation=summarize(validation,radius))
report=dict(round=args.round,traces=len(files),cells=out,replay_cpu_hours=sum(r['cpu_seconds'] for r in allrows)/3600)
(HERE/f'dev-summary-{args.round}.json').write_text(json.dumps(report,indent=2)+'\n')
if not args.partial:(HERE/'calibration.json').write_text(json.dumps(cal,indent=2)+'\n')
print(json.dumps(report,indent=2))
