"""Assemble r1-cards4-dev and live16402d-dev (same procedure as r1-cards3/live16402c; r1-cards3-phase1/assemble.py).

    python assemble.py JOB SRC REPO NATIVE_SO

JOB/runtime/{r1-cards4-dev,live16402d-dev} must not exist. The parent is a private writable copy of the released,
read-only r1-cards3 root (JOB/base-r1-cards3); build_runtime.py overlays the exported engine SRC + NATIVE_SO onto it;
build_live16402.py regenerates the overlay from the four hash-checked live16402c inputs. Writes JOB/ASSEMBLY.json.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

job, src, repo, native = (Path(p).resolve() for p in sys.argv[1:5])
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()  # noqa: E731
BASE_GAMEDATA = '892fbfa01e2ef9c3e4bd2293939dc336550fa626fa7ffb4ef9f91553cafd2f65'
LIVE_GAMEDATA = 'df93121d4cfaff795d784b0111c61e44f0e75e3c9f74e1e5b54de6be3adb81b9'
parent = Path('/mpac/sdicks02/repos/clasher-bot-runtime/r1-cards3')
roots = [job / 'runtime/r1-cards4-dev', job / 'runtime/live16402d-dev']
assert all(not p.exists() and not p.is_symlink() for p in roots), roots
base = job / 'base-r1-cards3'
assert not base.exists()
roots[0].parent.mkdir(parents=True, exist_ok=True)
native_sha = sha(native)
subprocess.run(['rsync', '-a', '--chmod=Du+w', f'{parent}/', f'{base}/'], check=True)
parent_receipt_sha = sha(base / 'RECEIPT.json')
assert parent_receipt_sha == sha(parent / 'RECEIPT.json')
subprocess.run([sys.executable, str(repo / 'bot/cards/build_runtime.py'), '--tree', str(src), '--base', str(base),
                '--target', str(roots[0]), '--native', str(native)], check=True)
# Keep the copied r1-cards3 release receipt under an unambiguous parent name in the new dev root.
(roots[0] / 'RECEIPT.json').rename(roots[0] / 'PARENT-r1-cards3-RECEIPT.json')
old = json.loads(Path('/mpac/sdicks02/repos/clasher-bot-runtime/live16402c/LIVE16402-RECEIPT.json').read_text())
inputs = old['inputs']
for key in ('royalesim_16402', 'royalesim_15535', 'calibration'):
    assert sha(inputs[key]['path']) == inputs[key]['sha256'], key
subprocess.run([sys.executable, str(repo / 'bot/cards/build_live16402.py'), '--base', str(roots[0]), '--target',
                str(roots[1]), '--rs16', inputs['royalesim_16402']['path'], '--rs15', inputs['royalesim_15535']['path'],
                '--calibration', inputs['calibration']['path']], check=True)
manifest = {}
for root, gd in zip(roots, (BASE_GAMEDATA, LIVE_GAMEDATA)):
    assert sha(root / 'native/clasher_core.abi3.so') == native_sha
    assert sha(root / 'gamedata.json') == gd, (root, sha(root / 'gamedata.json'))
    r = json.loads((root / 'CARDS-RUNTIME-RECEIPT.json').read_text())
    for f in r['files']:
        assert sha(root / f['path']) == (gd if f['path'] == 'gamedata.json' else f['sha256']), f['path']
    manifest[str(root)] = dict(native=native_sha, gamedata=gd, overlays=len(r['files']),
                               files={f['path']: sha(root / f['path']) for f in r['files']},
                               receipts={p.name: sha(p) for p in sorted(root.glob('*RECEIPT.json'))})
live = json.loads((roots[1] / 'LIVE16402-RECEIPT.json').read_text())
assert live['comparer_check'] == dict(missing=[], extra=[]), live['comparer_check']
assert sha(base / 'RECEIPT.json') == parent_receipt_sha
(job / 'ASSEMBLY.json').write_text(json.dumps(dict(
    source_commit=r['source_commit'], parent=str(parent), parent_receipt_sha256=parent_receipt_sha,
    native=str(native), native_sha256=native_sha, overlay_actions=live['actions'], roots=manifest), indent=2) + '\n')
print('ASSEMBLY PASS', native_sha, flush=True)
