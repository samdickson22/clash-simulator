"""Restore the source used for the hub build after the concurrent final sweep.

Preserve any newer incoming bytes separately. Does not touch the Mac checkout.
"""
import hashlib
import json
from pathlib import Path
import shutil
import socket

assert socket.gethostname().split('.')[0] == '127x02'
ROOT = Path('/mpac/sdicks02/repos/clasher')
FLEET = ROOT / 'reports/strategy_council_20260928/fleet'
SNAPSHOT = Path('/mpac/sdicks02/snapshots/clasher-fleet-20261007')
INCOMING = Path('/mpac/sdicks02/snapshots/clasher-post-sweep-20261007')
pins = json.loads((FLEET / 'source-mac.json').read_text())['files']
changes = []
for name, expected in pins.items():
    path = ROOT / name
    actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    frozen = SNAPSHOT / name
    if actual == expected:
        if not frozen.exists():
            frozen.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, frozen)
        continue
    assert frozen.exists() and hashlib.sha256(frozen.read_bytes()).hexdigest() == expected, name
    if path.exists():
        saved = INCOMING / name
        saved.parent.mkdir(parents=True, exist_ok=True)
        if saved.exists():
            assert saved.read_bytes() == path.read_bytes(), name
        else:
            shutil.copy2(path, saved)
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(frozen, path)
    changes.append(dict(file=name, incoming_sha256=actual, restored_sha256=expected))
output = Path('/mpac/sdicks02/jobs/clasher/snapshot-restoration.json')
if not output.exists():
    output.write_text(json.dumps(dict(changes=changes), indent=2)+'\n')
print(json.dumps(dict(restored=changes, pinned_files=len(pins)), indent=2))
