import hashlib
import json
import os
from pathlib import Path
import runpy
import shlex
import sys
import unittest

ROOT = Path.cwd()
ES = ROOT / 'reports/strategy_council_20260928/engine-speed'
STAGE = ES / 'stage6'
OUT = ROOT / 'reports/strategy_council_20260928/live-loop/v4/mac-native-build48'
sys.path[:0] = [str(ROOT/'engine-rs'), str(ROOT/'src'), str(STAGE), str(ES)]
import clasher_core
native = Path(clasher_core.__file__).resolve()
assert native == ROOT/'engine-rs/clasher_core.abi3.so', native
assert hashlib.sha256(native.read_bytes()).hexdigest() == '9263a8f72d18c202cf490e2e3f8fec214243d51ef91104990fb049458f831180'
print(json.dumps(dict(native=str(native), sha256=hashlib.sha256(native.read_bytes()).hexdigest(), pid=os.getpid(), mode=sys.argv[1])), flush=True)
def main():
    mode = sys.argv[1]
    if mode == 'runtime':
        suite = unittest.defaultTestLoader.discover(str(ROOT/'tests/live_v4'))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        raise SystemExit(0 if result.wasSuccessful() else 1)
    elif mode == 'stage6':
        line = next(x for x in (STAGE/'final_controls.sh').read_text().splitlines() if '-m unittest ' in x)
        names = shlex.split(line.split('-m unittest ', 1)[1])
        suite = unittest.defaultTestLoader.loadTestsFromNames(names)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        raise SystemExit(0 if result.wasSuccessful() else 1)
    elif mode == 'stage5':
        path = STAGE/'stage5_mac_build48.py'
        sys.argv = [str(path), '--output', str(OUT/'stage5-200.json')]
    elif mode == 'p16':
        path = ES.parent/'c56/engine/tools/p16_identity.py'
        sys.argv = [str(path), 'check', str(ES.parent/'c56/engine/p16_identity_baseline_admitted.json')]
    elif mode == 'c56':
        path = ES/'c56_identity.py'
        sys.argv = [str(path), 'check', str(ES/'c56_identity_baseline_canonical.json')]
    elif mode == 'random':
        path = ES/'broad_identity.py'
        sys.argv = [str(path), 'random', 'check', str(ES/'random_identity_baseline_admitted.json'), '--output', str(OUT/'random.json')]
    elif mode.startswith('recorded-'):
        import fcntl
        from fleet_identity_recorded import replay
        index=int(mode.split('-')[1])
        with (OUT/f'recorded-game{index}.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            replay(index)
        raise SystemExit(0)
    else:
        raise ValueError(mode)
    runpy.run_path(str(path), run_name='__main__')

if __name__ == '__main__':
    main()
