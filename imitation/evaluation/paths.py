"""Separate immutable model/adapters from the existing engine/data checkout."""
import os
from pathlib import Path
import sys

SNAPSHOT_ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.environ.get('CLASHER_EVAL_RUNTIME_ROOT', os.environ.get('CLASHER_ROOT', str(SNAPSHOT_ROOT)))).resolve()
COUNCIL = ROOT / 'reports/strategy_council_20260928'


def setup():
    paths = [ROOT / 'src', ROOT / 'engine-rs',
             COUNCIL / 'imitation', COUNCIL / 'engine-speed/stage5b-r3',
             COUNCIL / 'engine-speed/stage5', COUNCIL / 'engine-speed',
             COUNCIL / 'c56/engine/root-v3']
    for path in reversed(paths):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    # Own package wins over a changing shared imitation namespace.
    if str(SNAPSHOT_ROOT) in sys.path:
        sys.path.remove(str(SNAPSHOT_ROOT))
    sys.path.insert(0, str(SNAPSHOT_ROOT))
