"""Light05observer: no Runtime, games, claims or result mutations."""
from pathlib import Path
import hashlib,json,subprocess
from collections import Counter
from fullpool_clean import problems
J=Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2');D=J/'fullpool'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
bank=json.loads((D/'validation/bank.json').read_text());digest=sha(D/'validation/bank.json')
rows=[json.loads(p.read_text()) for p in (D/'validation/rows').glob('*.json')]
assert all(r['bank_sha256']==digest for r in rows)
keys=[(r['id'],r['candidate'],r['player']) for r in rows];assert len(set(keys))==len(keys)
counts=Counter(r['id'] for r in rows);arms=len(bank['candidates'])*len(bank['players'])
complete=[c for c in bank['cases'] if counts[c['id']]==arms]
old=json.loads((D/'resume-manifest.json').read_text())['preserved_rows']
assert all(sha(D/'validation/rows'/p)==v for p,v in old.items())
flags=[dict(id=r['id'],candidate=r['candidate'],player=r['player'],issues=problems(r)) for r in rows if problems(r)]
print(json.dumps(dict(utc=subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip(),games=len(rows),expected=4500,
 complete_cases=len(complete),complete_by_policy=dict(Counter(c['opponent'] for c in complete)),genuine_flags=flags,
 cutoff_hits=sum(r.get('result',{}).get('public_diagnostics',{}).get(str(r['seat']),{}).get('cutoff_hits',0) for r in rows),
 preserved_hashes_ok=len(old),stop=(D/'STOP').exists(),pipeline_error=json.loads((D/'pipeline-error.json').read_text()) if (D/'pipeline-error.json').exists() else None,
 interim_ready=(D/'interim-50/result.json').exists(),final_ready=(D/'VALIDATION-READY.json').exists())))
