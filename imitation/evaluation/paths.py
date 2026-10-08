"""Explicit imports of existing research adapters, without modifying them."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
COUNCIL = ROOT / 'reports/strategy_council_20260928'


def setup():
    paths = [ROOT / 'src', ROOT / 'engine-rs',
             COUNCIL / 'imitation', COUNCIL / 'engine-speed/stage5b-r3',
             COUNCIL / 'engine-speed/stage5', COUNCIL / 'engine-speed',
             COUNCIL / 'c56/engine/root-v3']
    for path in reversed(paths):
        sys.path.insert(0, str(path))
