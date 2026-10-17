"""Read-only light05 observer, safe during active banks."""
import json
from collections import Counter
from sam_common import ROOT,sha,utc
from fullpool_clean import problems
out=dict(utc=utc(),stages=[],stop=(ROOT/'STOP').exists())
for stage in ('upgrades','max','current'):
 bank=json.loads((ROOT/stage/'validation/bank.json').read_text());digest=sha(ROOT/stage/'validation/bank.json')
 rows=[json.loads(p.read_text()) for p in (ROOT/stage/'validation/rows').glob('*.json')]
 keys=[(r['id'],r['candidate'],r['player']) for r in rows];assert len(keys)==len(set(keys))
 assert all(r['bank_sha256']==digest for r in rows)
 counts=Counter(r['id'] for r in rows);arms=len(bank['candidates'])*len(bank['players'])
 complete=[c for c in bank['cases'] if counts[c['id']]==arms]
 out['stages'].append(dict(stage=stage,games=len(rows),expected=len(bank['cases'])*arms,complete_cases=len(complete),complete_by_policy=dict(Counter(c['opponent'] for c in complete)),
   genuine_flags=[dict(id=r['id'],issues=problems(r)) for r in rows if problems(r)],cutoffs=sum(r.get('result',{}).get('public_diagnostics',{}).get(str(r['seat']),{}).get('cutoff_hits',0) for r in rows)))
receipts=[json.loads(p.read_text()) for p in ROOT.glob('launch-127x*.json')]
out['registered_workers']={h:sum(r['workers'] for r in receipts if r['host']==h) for h in ('127x01','127x03','127x04')}
out['max_replay_passed']=(ROOT/'preflight/replay.json').exists()
out['spending_ready']=(ROOT/'SPENDING-PLAN.json').exists()
out['errors']={p.name:json.loads(p.read_text()) for p in ROOT.glob('*error.json')}
print(json.dumps(out))
