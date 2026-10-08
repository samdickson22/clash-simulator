"""Dev-only hand reliability curves and matched resource metrics."""
from pathlib import Path
import argparse,json,numpy as np
HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--round',default='v1');ap.add_argument('--limit',type=int,default=56);args=ap.parse_args()
paths=sorted((HERE/f'dev-{args.round}').glob('[0-9][0-9][0-9].json'));assert len(paths)==args.limit,(len(paths),args.limit)
records=[json.loads(p.read_text()) for p in paths]
for r in records:
 control=json.loads((HERE/f'dev-exact-control/{r["index"]:03d}.json').read_text())
 for key,samples in r['samples'].items():
  for sample in samples:sample['metrics']['R-derived']=control['samples'][f'{key[0]}-{sample["tick"]}']
out=dict(round=args.round,traces=len(records),cpu_seconds=sum(r['cpu_seconds'] for r in records),cells={})
edges=[0,.25,.5,.7,.8,.9,.95,.99,1.000001]
for level in ('T2-N97','T2-N90','T2-N64'):
 out['cells'][level]={}
 for split,predicate in [('calibration',lambda i:i<28),('validation',lambda i:i>=28)]:
  out['cells'][level][split]={}
  for name in ('T3','T2','ELT','R-derived'):
   rows=[sample['metrics'][name] for r in records if predicate(r['index']) for key,samples in r['samples'].items() if key.endswith(level) for sample in samples]
   if not rows:continue
   resolved=[x for x in rows if x['mass']>=.9];curves=[]
   for a,b in zip(edges,edges[1:]):
    bucket=[x for x in rows if a<=x['mass']<b]
    curves.append(dict(lower=a,upper=min(1.,b),n=len(bucket),claimed_mass=float(np.mean([x['mass'] for x in bucket])) if bucket else None,accuracy=float(np.mean([x['correct'] for x in bucket])) if bucket else None))
   out['cells'][level][split][name]=dict(samples=len(rows),resolved=len(resolved),resolved_rate=len(resolved)/len(rows),accuracy=float(np.mean([x['correct'] for x in resolved])) if resolved else None,mae=float(np.mean([x['mae'] for x in rows])),coverage=float(np.mean([x['covered'] for x in rows])),width=float(np.mean([x['width'] for x in rows])),calibration_curve=curves)
(HERE/f'dev-summary-{args.round}.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:{s:{n:{m:d[m] for m in ('resolved_rate','accuracy','mae','coverage')} for n,d in v.items()} for s,v in cells.items()} for k,cells in out['cells'].items()},indent=2))
