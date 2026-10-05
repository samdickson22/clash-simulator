"""Seal a completed early increment without claiming final S122 admission."""
from collections import Counter
import hashlib
import json
from pathlib import Path

import clasher_core
from stage2 import fingerprint

folder=Path(__file__).resolve().parent
for label in ('early-r4','early-r4-tests','early-r4-interactions','early-r4-focused','early-r4-c56-tests'):
    assert (folder/f'{label}.exit').read_text().strip()=='0',label
games=json.loads((folder/'early-r4-interactions.json').read_text())
focused=json.loads((folder/'early-r4-focused.json').read_text())
native_hash=hashlib.sha256(Path(clasher_core.__file__).read_bytes()).hexdigest()
for receipt in (games,focused):
    assert receipt['pins']['source']==fingerprint()
    assert receipt['pins']['native']==native_hash
    assert all(r['ok'] for r in receipt['results'].values())
assert len(games['results'])==12 and len(focused['results'])==80
accepted=Counter()
rows=list(games['results'].values())
for row in rows:
    assert row['terminal'];accepted.update(row['accepted'])
assert all(accepted[c]>0 for c in focused['cards'])
root=folder.parents[3]
entry=json.loads((folder/'entry.json').read_text())['sha256']
for name,expected in entry.items():
    if name.startswith('src/clasher/') or name in ('gamedata.json','engine-rs/clasher_core.abi3.so'):
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==expected,name
files=['early-r4-interactions.json','early-r4-focused.json','early-r4.log','test_early.py','test_ram.py','interactions.py','focused.py','regressions.py','early_gate.sh','scope.json','scope-inputs.json','build3/pins.json']
manifest=dict(status='early increment qualified; final Stage 6 NOT admitted',cards=focused['cards'],
              source=fingerprint(),native=native_hash,focused_cases=80,
              focused_ticks=sum(r['ticks'] for r in focused['results'].values()),
              terminal_games=len(rows),game_ticks=sum(r['ticks'] for r in rows),
              live_imports=sum(len(r['imports']) for r in rows),
              accepted_placements=sum(accepted.values()),accepted_by_card=dict(accepted),
              stepping_speedup=sum(r['python_cpu'] for r in rows)/sum(r['rust_cpu'] for r in rows),
              clone_us_max=max(i['clone_us'] for r in rows for i in r['imports']),
              mismatches=0,reference_preserved=True,final_s122_admitted=False,
              receipts={n:hashlib.sha256((folder/n).read_bytes()).hexdigest() for n in files})
(folder/'early-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({k:v for k,v in manifest.items() if k!='receipts'},indent=2))
