"""One deterministic initial-order hypothesis, explicitly not recovered truth."""
import copy,gzip,json
from study import OUT,IDS,base_slug,config_for,run_one
rows=[json.loads(l) for l in gzip.open(OUT/'sample50.jsonl.gz','rt')]
baselines={r['index']:r for r in map(json.loads,open(OUT/'results-terminal-50.jsonl'))}
with (OUT/'inferred-order.jsonl').open('w') as f:
 for row in rows:
  p=row['payload'];c=config_for(p);base=baselines[row['index']]
  for owner,side in enumerate(['team','opponent']):
   prior=base['initial_observe']['players'][owner]
   permutation=[v['deckSlot'] for v in prior['hand']+prior['cycle']]
   entries={v['d']:v for v in c['battle'][f'deck{owner}']['sp']};order=[]
   for e in p['events']:
    if e['side']==side and e['kind']=='play_card':
     cid=IDS[base_slug(e['card_key'])[0]]
     if cid not in order and cid in entries:order.append(cid)
   order += [cid for cid in entries if cid not in order]
   dest=[None]*8
   for slot,cid in zip(permutation,order):dest[slot]=entries[cid]
   c['battle'][f'deck{owner}']['sp']=dest
  r=run_one(row,config_override=c);r['assumption']='first unique plays assigned to baseline shuffled hand then queue slots; no seed recovery or future state exposed to actor'
  f.write(json.dumps(r)+'\n');f.flush();print(row['index'],r.get('failure'),sum(a['state']=='failed' for a in r.get('action_receipts',[])),flush=True)
