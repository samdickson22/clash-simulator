"""Close the B1 increment only when all final receipts agree on source."""
import hashlib
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(root / 'engine-rs'))
from stage2 import fingerprint

folder = Path(__file__).resolve().parent
assert (folder / 'b1_final.exit').read_text().strip() == '0'
focused = json.loads((folder / 'b1_focused_final.json').read_text())
matches = json.loads((folder / 'b1_interactions_final.json').read_text())
assert focused['fingerprint'] == matches['fingerprint'] == fingerprint()
assert len(focused['results']) == 72 and all(r['ok'] for r in focused['results'].values())
assert len(matches['results']) == 12 and all(r['ok'] and r['terminal'] for r in matches['results'].values())
log = (folder.parent / 'logs/stage4_b1_final_retry.log').read_text()
assert 'Ran 55 tests' in log and '\nOK\n' in log
entry = json.loads((folder / 'start_sources.json').read_text())['hashes']
assert all(hashlib.sha256((root / n).read_bytes()).hexdigest() == h for n, h in entry.items() if n.startswith('src/clasher/') or n == 'gamedata.json')
rows = list(matches['results'].values())
paths = [*root.joinpath('engine-rs/src').glob('*.rs'), *root.joinpath('engine-rs').glob('*.py'), root/'engine-rs/build.sh', root/'engine-rs/clasher_core.abi3.so', root/'gamedata.json']
out = dict(scope='B1 increment only; constructed decks; Python C56 controllers',
           fingerprint=focused['fingerprint'], focused_cases=72, focused_ticks=sum(r['ticks'] for r in focused['results'].values()),
           terminal_games=12, match_ticks=sum(r['ticks'] for r in rows), imports=sum(r['imports'] for r in rows),
           accepted_actions=sum(r['accepted'] for r in rows), regressions=55,
           step_speedup=sum(r['python_cpu'] for r in rows)/sum(r['rust_cpu'] for r in rows),
           max_clone_us=max(v for r in rows for v in r['clone_us']),
           hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
(folder/'b1_manifest.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k != 'hashes'},indent=2))
