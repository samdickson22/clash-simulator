import json,sys
from pathlib import Path
from collections import Counter,defaultdict
import numpy as np
root=Path(sys.argv[1]);groups=defaultdict(list)
for p in (root/'games').glob('*.json'):
 r=json.loads(p.read_text());groups[r.get('cohort')].append(r)
summary={}
for arm,rows in groups.items():
 s=defaultdict(lambda:[0,0]);attrs=defaultdict(Counter);lat=[];cpulat=[]
 for r in rows:
  for k,v in r['stats']['all'].items():s[k]=[s[k][j]+v[j] for j in (0,1)]
  a=r.get('search_ab',{});lat+=a.get('latency_seconds',[]);cpulat+=a.get('cpu_latency_seconds',[])
  for k,v in a.get('attrition',{}).items():attrs[k].update(v)
 summary[arm]=dict(games=len(rows),losses=sum(r['loss'] or 0 for r in rows),metrics={k:v[0]/v[1] for k,v in s.items() if v[1]},attrition=dict(attrs),latency=dict(n=len(lat),q=np.quantile(lat,[.5,.95,.99,1]).tolist(),over200=sum(x>.2 for x in lat),cpu_q=np.quantile(cpulat,[.5,.95,.99,1]).tolist()) if lat else {})
receipt=json.loads((root/'receipt.json').read_text()) if (root/'receipt.json').exists() else {}
if receipt:receipt={k:v for k,v in receipt.items() if k!='results'};receipt['fresh_games_per_second']=receipt.get('new_games',receipt['games'])/receipt['wall_seconds']
(root/'inspection.json').write_text(json.dumps(dict(summary=summary,receipt=receipt),separators=(',',':')))
print(json.dumps(dict(receipt=receipt,summary={k:{**v,'metrics':{m:x for m,x in v['metrics'].items() if m in ['arrival_under4_fraction','no_affordable_defender_in_hand_fraction'] or any(m.endswith(':'+n) for n in ['Xbow','Giant','Fireball','Rocket','Log'])},'attrition':{n:x for n,x in v['attrition'].items() if n in ['Xbow','Giant','Fireball','Rocket']}} for k,v in summary.items()}),indent=2))
