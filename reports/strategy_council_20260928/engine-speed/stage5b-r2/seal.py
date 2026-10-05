"""Gate all evidence and pin the exact prospective runtime before games."""
import datetime
import hashlib
import json
from pathlib import Path
import clasher_core
from qualify import write
HERE=Path(__file__).resolve().parent
assert (HERE.parent/'stage5b/tests.exit').read_text().strip()=='0'
assert (HERE.parent/'stage5b/parity.exit').read_text().strip()=='0'
assert (HERE/'register.exit').read_text().strip()=='0'
p=json.loads((HERE.parent/'stage5b/parity.json').read_text());assert p['complete'] and len(p['results'])==200
assert all(r['threads']==[1,2,4] for r in p['results'])
from evaluate import verify_manifest
verify_manifest(json.loads((HERE.parent/'stage5b/evaluation-manifest.json').read_text()))
assert hashlib.sha256(Path(clasher_core.__file__).read_bytes()).hexdigest()==hashlib.sha256((HERE.parent/'stage5b/native/clasher_core.abi3.so').read_bytes()).hexdigest()
entry=json.loads((HERE/'entry.json').read_text())
owned={'src/clasher/rl/c56_rollout_planner.py','engine-rs/src/scripts.rs'}
for path,want in entry['files'].items():
    if path not in owned:assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==want,('entry changed',path)
files=[Path(p) for p in entry['files']]
files += list(Path('engine-rs').glob('*.py'))+list((HERE.parent/'stage5').glob('*.py'))
files += list(HERE.glob('*.py'))+list(HERE.glob('*.sh'))
files += [Path(clasher_core.__file__),HERE.parent/'stage5b/parity.json',HERE/'seed-audit.json',HERE/'schedule.json',HERE.parent/'PREREG-C56-deadline-r2.md',HERE.parent/'stage5b/tests.log']
schedule=json.loads((HERE/'schedule.json').read_text())
prior=json.loads((HERE.parent.parent/'c56/engine/root-v3/human_deck_catalog.json').read_text())
supported={tuple(sorted(d['cards'])) for d in prior['decks']}
for ep in schedule['pairs']:
    assert tuple(sorted(ep['planning_deck'])) in supported
    assert tuple(sorted(ep['opponent_deck'])) in supported
for path,want in schedule['sources'].items():
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==want
    files.append(Path(path))
manifest=HERE/'evaluation-manifest.json';assert not manifest.exists()
write(manifest,dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(files))},deadline_seconds=.2,threads=2))
print('sealed',hashlib.sha256(manifest.read_bytes()).hexdigest())
