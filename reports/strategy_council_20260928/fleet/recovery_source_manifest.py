"""Read-only current Mac source pins; stdout is saved on the Linux hub.

The full transfer is separately checksum-verified by rsync. This manifest pins
the historical source scope plus newly added engine, Python and test sources.
It does not replace or reseal source-mac.json or any historical certificate.
"""
import hashlib
import json
import os
from pathlib import Path
import sys

root = Path(sys.argv[1])
fleet = root / "reports/strategy_council_20260928/fleet"
names = set(json.loads((fleet / "source-mac.json").read_text())["files"])
for folder in ("src", "engine-rs", "tests"):
    for directory, dirs, entries in os.walk(root / folder):
        dirs[:] = [name for name in dirs if name not in ("target", "__pycache__")]
        for name in entries:
            path = Path(directory) / name
            if path.is_file() and path.suffix in (".py", ".rs", ".toml", ".lock", ".sh"):
                names.add(str(path.relative_to(root)))
files = {}
total = 0
for name in sorted(names):
    data = (root / name).read_bytes()
    files[name] = hashlib.sha256(data).hexdigest()
    total += len(data)
print(json.dumps(dict(source=str(root), files=files, source_file_count=len(files),
                     source_bytes=total), sort_keys=True, indent=2))
