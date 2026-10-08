"""Run only on 127x01, at nice 10+, to capture a consistent, minimal working source."""
from pathlib import Path
import hashlib
import json
import os
import socket
import subprocess
assert socket.gethostname().split('.')[0] == '127x01'
root = Path('/mpac/sdicks02/repos/clasher')
out = Path('/mpac/sdicks02/jobs/clasher/lease-source-20261008')
assert not out.exists(), 'Use a fresh snapshot; never overwrite a published snapshot'
out.mkdir()
source = out / 'repo'
source.mkdir()
pins = json.loads(Path('/mpac/sdicks02/jobs/clasher/recovery-source-mac.json').read_text())['files']
files = set(os.fsdecode(x) for x in subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z']).split(b'\0') if x)
files.update(pins)
for folder in ('src', 'scripts', 'imitation', 'engine-rs', 'reports/strategy_council_20260928/imitation'):
    for here, dirs, names in os.walk(root / folder):
        dirs[:] = [d for d in dirs if d not in {'target', '.venv', '.git', '__pycache__', 'data', 'checkpoints', 'datasets', 'node_modules'}]
        for name in names:
            p = Path(here) / name
            if p.suffix in {'.py', '.sh', '.toml', '.lock', '.rs', '.md'}:
                files.add(str(p.relative_to(root)))
files.update({'reports/strategy_council_20260928/c56/engine/p16_identity_baseline_admitted.json', 'gamedata.json', 'decks.json', 'hitboxes.json'})
for p in (root / 'reports/strategy_council_20260928/m0/data/roles_v2').rglob('*'):
    if p.is_file(): files.add(str(p.relative_to(root)))
files = sorted(f for f in files if (root / f).is_file() and not (root / f).is_symlink() and not any(x in Path(f).parts for x in ('.git', '.venv', 'target', 'node_modules', '__pycache__', 'checkpoints', 'datasets')) and Path(f).suffix.lower() not in {'.apk', '.apks', '.xapk', '.so', '.dylib', '.pyc'})
(out / 'files.list').write_bytes(b'\0'.join(os.fsencode(f) for f in files) + b'\0')
subprocess.run(['rsync', '-a', '--from0', '--files-from=' + str(out / 'files.list'), str(root) + '/', str(source) + '/'], check=True)
manifest = {f: hashlib.sha256((source / f).read_bytes()).hexdigest() for f in files}
(out / 'source-sha256.json').write_text(json.dumps(manifest, indent=2) + '\n')
(out / 'historical-pin-drift.json').write_text(json.dumps({f: {'historical': h, 'snapshot': manifest.get(f)} for f, h in pins.items() if manifest.get(f) != h}, indent=2) + '\n')
print(json.dumps({'files': len(files), 'bytes': sum((source / f).stat().st_size for f in files), 'snapshot': str(out)}))
