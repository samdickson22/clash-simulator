"""Admit champions only after common-build parity and external repair completion."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import shutil

root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(root / 'engine-rs'))
from stage2 import fingerprint

parser=argparse.ArgumentParser()
parser.add_argument('--candidate',default='r64')
parser.add_argument('--provisional',action='store_true',help='preserve passed card checks while external source repair is pending; never admit')
parser.add_argument('--checkpoint',type=Path,help='finalize a preserved card kernel after controller-only development')
args=parser.parse_args()
tag=args.candidate
folder=Path(__file__).resolve().parent
for label in ('champions_checks','champion_games','champions_cumulative','champions_prior'):
    assert (folder/f'{label}_{tag}.exit').read_text().strip()=='0',label
checkpoint=json.loads(args.checkpoint.read_text()) if args.checkpoint else None
identity=checkpoint['fingerprint'] if checkpoint else fingerprint()
if checkpoint:
    assert not args.provisional
    frozen_binary=root/checkpoint['frozen_native_library']
    assert hashlib.sha256(frozen_binary.read_bytes()).hexdigest()==checkpoint['hashes']['engine-rs/clasher_core.abi3.so']
    # Only controller sources may change after this frozen physics checkpoint.
    exporters={'differential.py','live_snapshot.py','scope_snapshot.py','spawn_snapshot.py','champion_snapshot.py'}
    for name,digest in checkpoint['hashes'].items():
        if (name.startswith('engine-rs/src/') and name!='engine-rs/src/scripts.rs') or (name.startswith('engine-rs/') and Path(name).name in exporters):
            assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest, f'card kernel changed; recertification required: {name}'

focused=json.loads((folder/f'champions_cumulative_{tag}.json').read_text())
games=json.loads((folder/f'champion_games_{tag}.json').read_text())
prior=[json.loads((folder/f'{bundle}_at_champions_{tag}.json').read_text()) for bundle in ('B1','B2','B3','B4','R','S')]
assert all(r['fingerprint']==identity for r in (focused,games,*prior)), 'source drift'
assert len(focused['results'])==368
assert all(r['ok'] and r['focal_accepted']>0 for r in focused['results'].values())
for receipt in (games,*prior):
    assert len(receipt['results'])==12
    assert all(r['ok'] and r['terminal'] for r in receipt['results'].values())
rows=list(games['results'].values())
coverage={c:sum(r['accepted_by_card'].get(c,0) for r in rows) for c in ('ArcherQueen','MightyMiner','Goblinstein')}
abilities={c:sum(r['accepted_abilities'].get(c,0) for r in rows) for c in coverage}
assert all(coverage.values()) and all(abilities.values()), (coverage,abilities)
log=(folder.parent/f'logs/stage4_champions_checks_{tag}.log').read_text()
assert 'Ran 121 tests' in log and '\nOK\n' in log
entry=json.loads((folder/'start_sources.json').read_text())['hashes']
assert all(hashlib.sha256((root/name).read_bytes()).hexdigest()==h for name,h in entry.items() if name.startswith('src/clasher/') or name=='gamedata.json')
repair=root/'reports/strategy_council_20260928/c56/data/qa/v3b/gates.json'
source=root/'src/clasher/cards/c56_champions.py'
if not args.provisional:
    gate=json.loads(repair.read_text())
    assert gate['checks']['sweep']['attempted']==27649 and gate['checks']['sweep']['failures']==0
    assert gate['checks']['reuse']['attempted']>=253 and gate['checks']['reuse']['failures']==0
    assert gate['identity']['mismatches']==0
    frozen=root/'reports/strategy_council_20260928/c56/data/runtime-engine-v3b/src/clasher/cards/c56_champions.py'
    assert source.read_bytes()==frozen.read_bytes(), 'final champion source requires re-sync'
speed=sum(r['python_cpu'] for r in rows)/sum(r['rust_cpu'] for r in rows)
clone=max(v for r in rows for v in r['clone_us'])
assert speed>=30 and clone<20, (speed,clone)
paths=[*root.joinpath('engine-rs/src').glob('*.rs'),*root.joinpath('engine-rs').glob('*.py'),root/'engine-rs/build.sh',root/'engine-rs/clasher_core.abi3.so',root/'gamedata.json']
frozen_library=folder/f'native-card-kernel-{tag}.so'
if checkpoint:
    frozen_library=root/checkpoint['frozen_native_library']
else:
    if frozen_library.exists():
        assert frozen_library.read_bytes()==(root/'engine-rs/clasher_core.abi3.so').read_bytes()
    else:
        shutil.copy2(root/'engine-rs/clasher_core.abi3.so',frozen_library)
out=dict(status='provisional: external Python repair admission pending' if args.provisional else 'card kernel admitted; native C56 controller/final gates separate',frozen_native_library=str(frozen_library.relative_to(root)),scope='62 engine cards including 56 actor cards and six repaired opponent extras; native controller and final full-C56 gates pending',fingerprint=identity,regressions=121,focused_cases=368,focused_ticks=sum(r['ticks'] for r in focused['results'].values()),prior_bundle_games=72,champion_games=12,champion_ticks=sum(r['ticks'] for r in rows),champion_imports=sum(r['imports'] for r in rows),accepted_cards=coverage,accepted_abilities=abilities,step_speedup=speed,max_clone_us=clone,repair_gate_sha256=None if args.provisional else hashlib.sha256(repair.read_bytes()).hexdigest(),final_champion_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),hashes=checkpoint['hashes'] if checkpoint else {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
(folder/('champions_provisional_manifest.json' if args.provisional else 'champions_manifest.json')).write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='hashes'},indent=2))
