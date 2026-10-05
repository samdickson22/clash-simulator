"""Refuse evaluation until the prospective gates and every source pin agree."""
import datetime
import hashlib
import json
from pathlib import Path
import clasher_core
from qualify import write
from scope_pins import fingerprint

HERE=Path(__file__).resolve().parent
path=HERE/'evaluation-manifest.json'
assert not path.exists(),'sealed manifests are immutable'
receipts={name:json.loads((HERE/name).read_text()) for name in ('parity-r3.json','parity-scoped.json','native-games-scoped.json','scoped-sources.json','abilities.json','public-templates.json','derived-games.json','collector.json','seed-audit.json','seed-audit-binary.json','schedule.json')}
assert receipts['parity-r3.json']['complete'] and len(receipts['parity-r3.json']['results'])>=200
assert receipts['parity-scoped.json']['complete'] and len(receipts['parity-scoped.json']['results'])>=200
assert receipts['parity-scoped.json']['fingerprint']==fingerprint()==receipts['native-games-scoped.json']['fingerprint']
assert receipts['native-games-scoped.json']['complete'] and len(receipts['native-games-scoped.json']['games'])>=8
for name in ('abilities.json','public-templates.json','derived-games.json','collector.json'):
    assert receipts[name]['complete'],name
assert receipts['seed-audit.json']['passed'] and receipts['seed-audit-binary.json']['passed']
for name in ('parity-r3','parity-scoped','native-games-scoped','abilities','public-templates-r2','derived-games-r2','collector-r4','stage4-regressions3','p16-regressions','audit-binary'):
    assert (HERE/f'{name}.exit').read_text().strip()=='0',name
end=json.loads((HERE/'development-worker0-done.json').read_text())
assert end['complete']
current_development_hash=hashlib.sha256(b''.join((HERE/n).read_bytes() for n in ('fair_player.py','derived_public_state.py','decks.py','evaluate.py'))).hexdigest()
assert end['manifest']==current_development_hash, 'development receipt is from a different player/driver'
dev=list((HERE/'development'/end['manifest'][:12]).glob('pair*.json'))
assert len(dev)==8
# Development outcomes are not used for tuning or scheduling. Timing remains an
# independently reported acceptance criterion even if the fixed run exceeds it.
timings=[t[0] for p in dev for t in json.loads(p.read_text())['wall_cpu_search']]
files=[*(p for p in Path('src/clasher').rglob('*.py') if 'vision' not in p.relative_to('src/clasher').parts[:1]),*Path('engine-rs/src').glob('*.rs'),*Path('engine-rs').glob('*.py'),
       Path('gamedata.json'),Path(clasher_core.__file__),HERE.parent/'PREREG-C56.md']
files += [HERE/n for n in ('fair_player.py','derived_public_state.py','decks.py','evaluate.py','analyze.py','schedule.json','seed-audit.json')]
for name in receipts:files.append(HERE/name)
entry=json.loads((HERE/'entry_sources.json').read_text())['files']
for source,want in entry.items():
    if source.startswith('src/clasher/') and not source.startswith('src/clasher/vision/'):
        assert hashlib.sha256(Path(source).read_bytes()).hexdigest()==want,('Python oracle changed',source)
assert hashlib.sha256(Path('gamedata.json').read_bytes()).hexdigest()==entry['gamedata.json']
assert hashlib.sha256(Path('engine-rs/clasher_core.abi3.so').read_bytes()).hexdigest()==entry['engine-rs/clasher_core.abi3.so']
write(path,dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),preregistered=True,
    files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(files))},
    gates={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in receipts},
    development_games=8,development_max_wall=max(timings),development_budget_pass=max(timings)<=.25,
    native_library=str(Path(clasher_core.__file__).resolve())))
print('sealed',hashlib.sha256(path.read_bytes()).hexdigest(),'development maximum',max(timings))
