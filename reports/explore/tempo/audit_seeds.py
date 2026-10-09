"""Read seed-only inventories; no gate outcomes or registration mutation."""
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[3];out=Path(__file__).resolve().parent
paths=[root/'reports/explore/loss-review/seeds.json']+sorted((root/'imitation/gates-bc/receipts').glob('**/*seeds.json'))+sorted((root/'imitation').glob('gate-*/v1/proposed-seeds.json'))
def numbers(x):
 if isinstance(x,int) and not isinstance(x,bool):yield x
 elif isinstance(x,list):
  for v in x:yield from numbers(v)
 elif isinstance(x,dict):
  for v in x.values():yield from numbers(v)
denied=set();sources=[]
for p in paths:
 values=set(numbers(json.loads(p.read_text())));denied.update(values);sources.append(dict(path=str(p.relative_to(root)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),count=len(values)))
sets=json.loads((root/'reports/explore/search-ab/seed-audit.json').read_text())['sets']
for name,r in sets.items():denied.update(r['base']+i+o for i in range(r['pairs']) for o in (0,100000,100001,100002))
# Delay-fixes experiment uses +20000/+40000; include its seed-only schedule if available.
for p in (root/'reports/explore/delay-fixes').glob('**/seed-audit.json'):
 sources.append(dict(path=str(p.relative_to(root)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),note='seed-audit receipt'))
sets_new=dict(reporting=dict(base=2**48+70000+10,pairs=1000),tuning=dict(base=2**48+80000,pairs=150),combination=dict(base=2**48+85000,pairs=150),smoke=dict(base=2**48+87000,pairs=2))
checked={n:{r['base']+i+o for i in range(r['pairs']) for o in (0,100000,100001,100002)} for n,r in sets_new.items()}
for n,v in checked.items():
 collision=sorted(v&denied)
 if collision:raise ValueError((n,collision))
 for n2,v2 in checked.items():
  if n!=n2 and v&v2:raise ValueError('internal overlap')
(out/'exclusions.json').write_text(json.dumps(dict(proposed=sorted(denied),explicit=[]))+'\n')
(out/'seed-audit.json').write_text(json.dumps(dict(lane='exploration',sources=sources,denied_count=len(denied),prior_search_sets=sets,sets=sets_new,intersections=[],skipped_reporting_offsets=list(range(10)),reason='prior pause-parity registered seed set'),indent=2)+'\n')
print(json.dumps(sets_new))
