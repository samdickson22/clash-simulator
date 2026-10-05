"""Admit the repaired-card increment only from complete common-build receipts."""
import hashlib
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(root / 'engine-rs'))
from stage2 import fingerprint
from stage4_matches import BUNDLES

folder = Path(__file__).resolve().parent
for name in ('repairs_regressions_r48', 'repairs_focused_r48', 'repairs_games', 'repairs_extra'):
    assert (folder/(name+'.exit')).read_text().strip() == '0', name
focused = json.loads((folder/'repairs_focused_r48.json').read_text())
games = json.loads((folder/'repairs_interactions_r3.json').read_text())
extra = json.loads((folder/'repairs_extra_r48.json').read_text())
prior = [json.loads((folder/(name+'_at_repairs.json')).read_text()) for name in ('B1','B2','B3','B4')]
identity = fingerprint()
assert all(receipt['fingerprint'] == identity for receipt in (focused, games, extra, *prior))
assert len(focused['results']) == 328
assert all(r['ok'] and r['focal_accepted'] > 0 for r in focused['results'].values())
assert len(games['results']) == 6 and all(r['ok'] and r['terminal'] and r['styles']==['fixture_schedule']*2 for r in games['results'].values())
assert set(extra['results']) == {str(i) for i in range(6,12)}
assert all(r['ok'] and r['terminal'] and r['styles']==['fixture_schedule']*2 for r in extra['results'].values())
repair_rows = [*games['results'].values(), *extra['results'].values()]
coverage = {card:sum(r['accepted_by_card'].get(card,0) for r in repair_rows) for card in BUNDLES['R']}
assert all(coverage.values()), coverage
for receipt in prior:
    assert len(receipt['results']) == 12 and all(r['ok'] and r['terminal'] for r in receipt['results'].values())
log = (folder.parent/'logs/stage4_repairs_regressions_r48.log').read_text()
assert 'Ran 98 tests' in log and '\nOK\n' in log
entry = json.loads((folder/'start_sources.json').read_text())['hashes']
assert all(hashlib.sha256((root/name).read_bytes()).hexdigest() == h for name,h in entry.items() if name.startswith('src/clasher/') or name == 'gamedata.json')
paths = [*root.joinpath('engine-rs/src').glob('*.rs'), *root.joinpath('engine-rs').glob('*.py'), root/'engine-rs/build.sh', root/'engine-rs/clasher_core.abi3.so',root/'gamedata.json']
rows = repair_rows
out = dict(scope='57-card engine increment; 6 repaired cards use an engine fixture schedule, not C56 controller admission', fingerprint=identity,
           regressions=98, prior_bundle_games=48, focused_cases=328, focused_ticks=sum(r['ticks'] for r in focused['results'].values()),
           repaired_terminal_games=len(rows), repaired_ticks=sum(r['ticks'] for r in rows), repaired_imports=sum(r['imports'] for r in rows), repaired_accepted_actions=sum(r['accepted'] for r in rows), accepted_repaired_card_coverage=coverage,
           repaired_step_speedup=sum(r['python_cpu'] for r in rows)/sum(r['rust_cpu'] for r in rows), repaired_max_clone_us=max(v for r in rows for v in r['clone_us']),
           hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
(folder/'repairs_manifest.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='hashes'},indent=2))
