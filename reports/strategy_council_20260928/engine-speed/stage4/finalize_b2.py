"""Close the B2 increment only from complete common-build receipts."""
import hashlib
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(root / 'engine-rs'))
from stage2 import fingerprint

folder = Path(__file__).resolve().parent
for name in ('b2_final_checks', 'b2_final_games'):
    assert (folder / (name + '.exit')).read_text().strip() == '0', name
focused = json.loads((folder/'b1_b2_focused_final.json').read_text())
b1 = json.loads((folder/'b1_at_b2_final.json').read_text())
b2 = json.loads((folder/'b2_interactions_final.json').read_text())
identity = fingerprint()
assert all(r['fingerprint'] == identity for r in (focused, b1, b2))
assert len(focused['results']) == 152 and all(r['ok'] for r in focused['results'].values())
for receipt in (b1, b2):
    assert len(receipt['results']) == 12 and all(r['ok'] and r['terminal'] for r in receipt['results'].values())
log = (folder.parent/'logs/stage4_b2_final_checks_retry.log').read_text()
assert 'Ran 75 tests' in log and '\nOK\n' in log
entry = json.loads((folder/'start_sources.json').read_text())['hashes']
assert all(hashlib.sha256((root/n).read_bytes()).hexdigest() == h for n,h in entry.items() if n.startswith('src/clasher/') or n == 'gamedata.json')
paths = [*root.joinpath('engine-rs/src').glob('*.rs'), *root.joinpath('engine-rs').glob('*.py'), root/'engine-rs/build.sh', root/'engine-rs/clasher_core.abi3.so',root/'gamedata.json']
def summary(receipt):
    rows=list(receipt['results'].values())
    return dict(terminal_games=len(rows), ticks=sum(r['ticks'] for r in rows), imports=sum(r['imports'] for r in rows), accepted_actions=sum(r['accepted'] for r in rows),
                step_speedup=sum(r['python_cpu'] for r in rows)/sum(r['rust_cpu'] for r in rows), max_clone_us=max(v for r in rows for v in r['clone_us']))
out = dict(scope='B1/B2 increment only; constructed decks; Python C56 controllers', fingerprint=identity,
           regressions=75, focused_cases=152, focused_ticks=sum(r['ticks'] for r in focused['results'].values()),
           b1=summary(b1), b2=summary(b2),
           hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
(folder/'b2_manifest.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='hashes'},indent=2))
