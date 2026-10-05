"""Admit B3 only from complete receipts for this exact native/source build."""
import hashlib
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(root / 'engine-rs'))
from stage2 import fingerprint

folder = Path(__file__).resolve().parent
for name in ('b3_checks', 'b3_interactions_r1', 'b3_prior_games'):
    assert (folder / (name + '.exit')).read_text().strip() == '0', name
focused = json.loads((folder/'b1_b2_b3_focused_r34.json').read_text())
games = json.loads((folder/'b3_interactions_r1.json').read_text())
prior = [json.loads((folder/(name+'_at_b3.json')).read_text()) for name in ('b1','b2')]
identity = fingerprint()
assert all(r['fingerprint'] == identity for r in (focused, games, *prior))
assert len(focused['results']) == 240
assert all(r['ok'] and r['focal_accepted'] > 0 for r in focused['results'].values())
assert len(games['results']) == 12
assert all(r['ok'] and r['terminal'] for r in games['results'].values())
for receipt in prior:
    assert len(receipt['results']) == 12 and all(r['ok'] and r['terminal'] for r in receipt['results'].values())
log = (folder.parent/'logs/stage4_b3_checks_r34.log').read_text()
assert 'Ran 80 tests' in log and '\nOK\n' in log
entry = json.loads((folder/'start_sources.json').read_text())['hashes']
assert all(hashlib.sha256((root/n).read_bytes()).hexdigest() == h for n,h in entry.items() if n.startswith('src/clasher/') or n == 'gamedata.json')
paths = [*root.joinpath('engine-rs/src').glob('*.rs'), *root.joinpath('engine-rs').glob('*.py'), root/'engine-rs/build.sh', root/'engine-rs/clasher_core.abi3.so',root/'gamedata.json']
rows = list(games['results'].values())
out = dict(scope='B3 increment; cumulative B1/B2/B3 focused tests; constructed decks; Python C56 controllers', fingerprint=identity,
           regressions=80, prior_bundle_games=24, focused_cases=240, focused_ticks=sum(r['ticks'] for r in focused['results'].values()),
           terminal_games=len(rows), ticks=sum(r['ticks'] for r in rows), imports=sum(r['imports'] for r in rows), accepted_actions=sum(r['accepted'] for r in rows),
           step_speedup=sum(r['python_cpu'] for r in rows)/sum(r['rust_cpu'] for r in rows), max_clone_us=max(v for r in rows for v in r['clone_us']),
           hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
(folder/'b3_manifest.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='hashes'},indent=2))
