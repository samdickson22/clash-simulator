import collections,gzip,json
from study import OUT,dump
rows={r['index']:r['payload'] for r in map(json.loads,gzip.open(OUT/'sample50.jsonl.gz','rt'))}
result={}
for name in ['results-terminal-50.jsonl','inferred-order.jsonl','levelled-order.jsonl']:
 rs=[json.loads(l) for l in open(OUT/name)];groups=collections.defaultdict(list)
 for r in rs:
  p=rows[r['index']];levels=[c['level'] for s in ['team','opponent'] for c in p['battle'][s]['players'][0]['deck']]
  mixed=len(set(levels))>1;hero=any('-hero' in c['card_key'] for s in ['team','opponent'] for c in p['battle'][s]['players'][0]['deck']);tower=any(p['battle'][s]['players'][0]['tower_card']['card_key']!='tower-princess' for s in ['team','opponent'])
  for g in ['mixed_levels' if mixed else 'uniform_levels','hero' if hero else 'no_hero','tower_troop' if tower else 'princess_only']:groups[g].append(r)
 result[name]={g:{'n':len(a),'crowns_exact':sum(r['final']['crownsRaw']==[r['recorded'][s]['crowns'] for s in ['team','opponent']] for r in a),'all_injected':sum(all(s['state']=='succeeded' for s in r['action_receipts']) for r in a)} for g,a in groups.items()}
dump('group-summary.json',result);print(json.dumps(result,indent=2))
