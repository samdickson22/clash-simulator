"""Read-only lease classifier check; emits only PID/nice, never command lines."""
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path

path = Path('/mpac/sdicks02/repos/clasher-lease/lease_watch_v2_hotfix_20261009_r3.py')
spec = importlib.util.spec_from_file_location('lease_read_only_classifier', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
bad = []
for entry in Path('/proc').iterdir():
    if not entry.name.isdigit():
        continue
    pid = int(entry.name)
    argv = module.process_argv(pid)
    if not argv or not module.clasher_argv(argv):
        continue
    try:
        value = os.getpriority(os.PRIO_PROCESS, pid)
    except ProcessLookupError:
        continue
    if value < 10:
        bad.append(dict(pid=pid, nice=value))
print(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(), clear=not bad,
                      minimum_nice=10, offending_pids=bad,
                      classifier_revision=module.REVISION)))
raise SystemExit(1 if bad else 0)
