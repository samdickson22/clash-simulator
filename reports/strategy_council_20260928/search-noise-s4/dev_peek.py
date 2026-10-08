from pathlib import Path
import json
from collections import defaultdict
HERE=Path(__file__).resolve().parent
rows=defaultdict(list);indices=[]
for p in (HERE/'dev-v2').glob('*.json'):
 r=json.loads(p.read_text())
 if r['index']>=28:continue
 indices.append(r['index'])
 for key,samples in r['samples'].items():
  for sample in samples:
   for name,d in sample['metrics'].items():
    if name!='R-derived':rows[(key[2:],name)].append(d)
out={}
for (level,name),xs in rows.items():
 high=[x for x in xs if x['mass']>=.9];out[f'{level}/{name}']=dict(n=len(xs),resolved=len(high),correct=sum(x['correct'] for x in high),rate=len(high)/len(xs),accuracy=sum(x['correct'] for x in high)/len(high) if high else None)
print(json.dumps(dict(calibration_indices=sorted(indices),metrics=out),indent=2))
