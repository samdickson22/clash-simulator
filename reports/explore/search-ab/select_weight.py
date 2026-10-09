"""Tuning-only weight selection. Never reads a reporting game."""
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]);weights=[]
for weight,run,arm in [(0,'tune-w0w16','0'),(1,'tune-w1','R'),(4,'tune-w4','R'),(16,'tune-w0w16','R'),(64,'tune-w64','R')]:
 d=root/run;receipt=json.loads((d/'receipt.json').read_text());rows=[]
 for p in (d/'games').glob('*.json'):
  r=json.loads(p.read_text())
  if r['cohort']==arm:rows.append(r)
 assert len(rows)==150 and all(r['metadata']['terminal'] for r in rows)
 assert {r['metadata']['seed'] for r in rows}=={2**48+30000+i for i in range(150)}
 weights.append(dict(weight=weight,losses=sum(r['loss'] for r in rows),wins=sum(r['metadata']['winner']==r['metadata']['seat'] for r in rows),games=150,source=run,arm=arm))
selected=min(weights,key=lambda r:(r['losses'],r['weight']))['weight']
ex=json.loads((root/'exclusions.json').read_text());registered=set(ex['proposed'])|set(ex['explicit'])
schedules={'ledger':(0,150),'reporting':(10000,2000),'tuning':(30000,150),'budget_check':(50000,100),'public_native_smoke':(90000,11),'coexistence':(60000,1000),'pause_parity':(70000,5)}
sets={k:{2**48+base+i+off for i in range(n) for off in (0,100000,100001,100002)} for k,(base,n) in schedules.items()}
audit=dict(gate_seed_count=len(set(ex['proposed'])),historical_seed_count=len(set(ex['explicit'])),exclusions_sha256=hashlib.sha256((root/'exclusions.json').read_bytes()).hexdigest(),sets={k:dict(base=2**48+base,pairs=n,checked_count=len(sets[k]),registered_intersections=sorted(sets[k]&registered)) for k,(base,n) in schedules.items()},pairwise_intersections={a+'-'+b:sorted(sets[a]&sets[b]) for i,a in enumerate(sets) for b in list(sets)[i+1:]})
assert audit['gate_seed_count']==4356
assert not any(v['registered_intersections'] for v in audit['sets'].values())
assert not any(audit['pairwise_intersections'].values())
(root/'seed-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
if '--audit-only' in sys.argv:
 assert json.loads((root/'tuning.json').read_text())['selected_weight']==selected
else:
 (root/'tuning.json').write_text(json.dumps(dict(lane='exploration',criterion='minimum losses, tie lower weight',weights=weights,selected_weight=selected,reporting_access_before_selection=False),indent=2)+'\n')
print(selected)
