"""Certify metadata-only spawner admission on the repaired native kernel."""
import hashlib
import json
from pathlib import Path
import sys

root=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(root/'engine-rs'))
from stage2 import fingerprint
folder=Path(__file__).resolve().parent
for label in ('spawners_checks','spawners_games'):
    assert (folder/(label+'.exit')).read_text().strip()=='0',label
focused=json.loads((folder/'spawners_focused_final.json').read_text())
games=json.loads((folder/'spawners_interactions_final.json').read_text())
identity=fingerprint()
assert focused['fingerprint']==games['fingerprint']==identity
assert len(focused['results'])==16 and all(r['ok'] and r['focal_accepted']>0 for r in focused['results'].values())
rows=list(games['results'].values())
assert len(rows)==12 and all(r['ok'] and r['terminal'] for r in rows)
coverage={card:sum(r['accepted_by_card'].get(card,0) for r in rows) for card in ('FirespiritHut','GoblinHut')}
assert all(coverage.values())
log=(folder.parent/'logs/stage4_spawners_checks.log').read_text()
assert 'Ran 101 tests' in log and '\nOK\n' in log
prior_path=folder/'repairs_manifest.json'
prior=json.loads(prior_path.read_text())
for name,h in prior['hashes'].items():
    if name.startswith('engine-rs/src/') or name=='engine-rs/clasher_core.abi3.so':
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==h,name
entry=json.loads((folder/'start_sources.json').read_text())['hashes']
assert all(hashlib.sha256((root/name).read_bytes()).hexdigest()==h for name,h in entry.items() if name.startswith('src/clasher/') or name=='gamedata.json')
paths=[*root.joinpath('engine-rs/src').glob('*.rs'),*root.joinpath('engine-rs').glob('*.py'),root/'engine-rs/build.sh',root/'engine-rs/clasher_core.abi3.so',root/'gamedata.json']
out=dict(scope='59-card increment; unchanged repaired kernel; Python C56 controllers; no champion/native-controller admission',fingerprint=identity,
         inherited_repairs_certificate_sha256=hashlib.sha256(prior_path.read_bytes()).hexdigest(),
         regressions=101,focused_cases=16,focused_ticks=sum(r['ticks'] for r in focused['results'].values()),
         terminal_games=12,ticks=sum(r['ticks'] for r in rows),imports=sum(r['imports'] for r in rows),accepted_actions=sum(r['accepted'] for r in rows),accepted_spawner_coverage=coverage,
         step_speedup=sum(r['python_cpu'] for r in rows)/sum(r['rust_cpu'] for r in rows),max_clone_us=max(v for r in rows for v in r['clone_us']),
         hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
(folder/'spawners_manifest.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='hashes'},indent=2))
