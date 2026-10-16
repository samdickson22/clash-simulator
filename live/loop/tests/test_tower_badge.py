"""Tower HP reader vs troop level badges (s28-m03: an enemy Giant's level-5 badge over the hidden enemy king latched king
HP 5 for 22 s; the bot spent a Fireball on it).   python tests/test_tower_badge.py   (env: RUNS, OLD = the previous
towers.py for the before/after cases, default 05 scratch towers-old/towers.py = deployed 82097878)"""
import ast
import importlib.util
import os
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import canvas as C  # noqa: E402
import towers as TW  # noqa: E402

cv2.setNumThreads(1)
# Execute only the driver's normalization function, without importing its runtime/models/manifest hooks.
tree = ast.parse((HERE/'drive.py').read_text())
normalizer = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'normalize')
ns = {'cv2': cv2, 'np': np}
exec(compile(ast.Module(body=[normalizer], type_ignores=[]), str(HERE/'drive.py'), 'exec'), ns)
normalize = ns['normalize']

RUNS = Path(os.environ.get('RUNS', '/mpac/sdicks02/scratch/live-loop/runs'))
OLD = os.environ.get('OLD', '/mpac/sdicks02/scratch/live-loop/towers-old/towers.py')
checks = []


def check(name, cond):
    checks.append(bool(cond)); print(('PASS ' if cond else 'FAIL ') + name)


def frame(run, n, lift=0):
    f = C.to_android(cv2.imread(str(RUNS/run/'video'/f'{n:06d}.jpg')))
    return normalize(f)[0] if lift is None else np.clip(f.astype(np.int16) + lift, 0, 255).astype(np.uint8)


old = None
if Path(OLD).exists():
    spec = importlib.util.spec_from_file_location('towers_old', OLD)
    old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)

# 1. the s28-m03 frames: the Giant's '5' badge inside the enemy king box. The saved JPEGs are a little dimmer than the
#    raw frames the driver read, so they are lifted by +25 (raw brightness) to reproduce the live reading.
KB = TW.BOX[('opp', 'king')]
badge = [n for n in (178, 179, 180, 181) if (RUNS/'s28/m03/video'/f'{n:06d}.jpg').exists()]
check('all four regression frames are present', len(badge) == 4)
check('before-fix reference reader is available', old is not None)
if badge:
    if old is not None:
        check('old reader: the Giant badge reads as king HP 5 (n178-181, raw brightness)',
              all(old.read_number(frame('s28/m03', n, 25), KB) == 5 for n in badge))
    # +25 is an artificial additive reproduction of the old bug. Regression assertions below use unmodified
    # recorded frames and the actual live normalization, rather than treating that artificial offset as truth.
    if old is not None:
        check('old reader reproduces HP 5 after exact live normalization',
              all(old.read_number(frame('s28/m03', n, None), KB) == 5 for n in badge))
    check('new reader rejects all four badges after exact live normalization',
          all(TW.read_number(frame('s28/m03', n, None), KB) is None for n in badge))
    check('badge rejection survives uniform dimming before live normalization',
          all(TW.read_number(normalize(cv2.convertScaleAbs(frame('s28/m03', n), alpha=.75))[0], KB) is None
              for n in badge))
    reader = TW.TowerReader(); reader.level = {'opp': 6, 'own': 6}
    hp = [reader.update(frame('s28/m03', n, None))[('opp', 'king')][1] for n in badge]
    check('the actual normalized badge sequence never lowers hidden king HP',
          hp == [TW.tower_hp('king', 6)]*len(badge))
# 2. Use the same normalization as the live driver. Raw dim JPEGs plus an arbitrary +25 lift left only 12 readable
# numbers, so that original test did not actually exercise normal HP digits across the recorded battles.
if old is not None:
    diff, total = [], 0
    corpus = ('s24/m01', 's24/m04', 's25/m02', 's26/m03', 's28/m03')
    check('all five baseline battle recordings are available', all((RUNS/run/'video').is_dir() for run in corpus))
    for run in corpus:
        d = RUNS/run/'video'
        if not d.exists():
            continue
        for fn in sorted(os.listdir(d))[::40]:
            for lift in (None, 25):
                raw = C.to_android(cv2.imread(str(d/fn)))
                f = normalize(raw)[0] if lift is None else np.clip(raw.astype(np.int16) + lift, 0, 255).astype(np.uint8)
                for k, box in TW.BOX.items():
                    a, b = old.read_number(f, box), TW.read_number(f, box)
                    total += a is not None
                    if a != b and not (run == 's28/m03' and int(Path(fn).stem) in badge and k == ('opp', 'king')
                                       and a == 5 and b is None):
                        diff.append((run, fn, lift, k, a, b))
    check(f'real HP numbers unchanged: {total} old readings, {len(diff)} differ {diff[:3]}', total > 100 and not diff)


# 3. TowerReader logic on scripted readings (read_number stubbed per frame)
def run_reader(seq, key=('opp', 'king'), level=6, module=TW):
    r = module.TowerReader(); r.level = {'opp': level, 'own': level}
    out = []
    orig = module.read_number
    try:
        for v in seq:
            module.read_number = lambda f, box, v=v, k=key: v if box == module.BOX[k] else None
            out.append(r.update(None)[key][1])
    finally:
        module.read_number = orig
    return out, r


hp, _ = run_reader([None]*5 + [3221, 3221] + [3063, 3063] + [None, 3063]*10)
check('a real first king hit (>= half of max) is read after 2 readings, blinking keeps it', hp[6] == 3221 and hp[-1] == 3063)
hp, _ = run_reader([3063, 3063] + [None]*90)
check('a damaged king remains damaged through long unreadable/occluded intervals', hp[-1] == 3063)
princess_max = TW.tower_hp('princess', 6)
low_princess = princess_max//2 - 1  # 1200 is ABOVE half of the level-6 princess's 2030 HP.
hp, _ = run_reader([None]*5 + [low_princess]*2 + [None]*3, key=('opp', 'left'), level=6)
check('princess first-damage reading retains the deployed two-confirmation behavior', hp[-1] == low_princess)
if old is not None:
    seq = [None]*5 + [3221, 3221, None, 3063, 3063] + [None]*35 + [150, 150]*3
    check('temporal king tracking matches the deployed reader including occlusion and large drops',
          run_reader(seq)[0] == run_reader(seq, module=old)[0])
print(f'{sum(checks)} passed, {len(checks) - sum(checks)} failed')
sys.exit(0 if all(checks) else 1)
