"""screens.classify: reward flows remain unknown for deferred manual handling; retain result-row, home and road checks.
Document pre-existing Collection / Pass road matches. Reject the review's synthetic smooth-background Buy target;
this is a regression for the removed generic reward path, not a purchase-screen safety guarantee.
Also scan the available recorded between-battle calibration frames.
   python tests/test_screens.py      (env: RUNS, SHOTS)"""
import os
import sys
from pathlib import Path

import cv2
import numpy as np

cv2.setNumThreads(1)

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import canvas as C  # noqa: E402
import screens  # noqa: E402

RUNS = Path(os.environ.get('RUNS', '/mpac/sdicks02/scratch/live-loop/runs'))
SHOTS = Path(os.environ.get('SHOTS', '/mpac/sdicks02/scratch/live-loop/shots'))
checks = []


def check(name, cond):
    checks.append(bool(cond)); print(('PASS ' if cond else 'FAIL ') + name)


def normalize(f):            # drive.normalize (drive.py is not imported: it needs the driver env)
    w = float(np.percentile(f[1600:1920:2, ::2].max(2), 99.5))
    return f if w >= 245 or w < 80 else cv2.convertScaleAbs(f, alpha=255./w)


def kind(p):
    im = cv2.imread(str(p))
    return screens.classify(normalize(C.to_android(im))) if im is not None else ('missing', None)


def frames(run, ns):
    return [RUNS/run/'video'/f'{n:06d}.jpg' for n in ns]


# s23 m03 / m04 between battles: the free chest flow (orange chest, Gold x400, blue mystery box, purple Snippet)
reward = frames('s23/m03', range(80, 2961, 80)) + frames('s23/m04', [120, 300, 540, 600, 720, 840, 1020, 1200, 1320, 1440])
reward += [SHOTS/f'sol-{n}.png' for n in ('s23-chest-1', 's23-chest-reward', 's23-chest-next', 's23-chestB-snippet',
                                          's23-next-open', 's24-daily-reward', 's24-daily-next', 's24-daily-snippet')]
got = [kind(p) for p in reward]
check(f'deferred manual reward flow: {sum(k is None for k, _ in got)}/{len(got)} frames unknown, no tap',
      all((k, xy) == (None, None) for k, xy in got))
check('no reward navigation kind is enabled', set(screens.STABLE) == {'result', 'home', 'road'})
# Reproduce M1 without writing an image into the repository. The Buy button covers the former reward tap point.
buy = np.full((1920, 1080, 3), 245, np.uint8)
cv2.putText(buy, 'Google Play', (240, 500), cv2.FONT_HERSHEY_SIMPLEX, 1.7, (30, 30, 30), 3)
cv2.putText(buy, 'Confirm purchase', (220, 900), cv2.FONT_HERSHEY_SIMPLEX, 1.3, (30, 30, 30), 2)
cv2.rectangle(buy, (200, 1430), (880, 1570), (90, 155, 35), -1)
cv2.putText(buy, 'BUY', (450, 1520), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
check('synthetic smooth Buy target: unknown, no tap', screens.classify(normalize(buy)) == (None, None))
for p, want in [(SHOTS/'sol-s23-final.png', 'result'), (SHOTS/'sol-s22-finished.png', 'result'),
                (RUNS/'s22/m02/video/000040.jpg', 'result'), (SHOTS/'sol-s20-final.png', 'result'),
                (SHOTS/'sol-s24-home.png', 'road'), (SHOTS/'sol-s17-trophy-road.png', 'road'),
                (RUNS/'s21/m02/video/000080.jpg', 'road'), (SHOTS/'sol-s23-home2.png', 'home'),
                (SHOTS/'sol-home-ready.png', 'home')]:
    k, xy = kind(p)
    check(f'{p.name}: {want} (got {k} {xy})', k == want)
k, xy = kind(RUNS/'s22/m02/video/000040.jpg')
check('the s22 result variant (buttons lower) taps OK on its own row', k == 'result' and xy[0] == 705 and 1700 < xy[1] < 1880)
for name in ('l12g-bs.png', 'sol-pass-s25.png'):
    check(f'pre-existing Collection / Pass corner case: {name} matches road footer',
          kind(SHOTS/name) == ('road', (540, 1845)))
never = [SHOTS/'sol-s23-second-home.png', SHOTS/'sol-s17-m02-end.jpg', SHOTS/'sol-s22-selected.png',
         SHOTS/'sol-mini-choice.png', SHOTS/'sol-mini-choice-ready.png', SHOTS/'sol-750-after.png',
         SHOTS/'sol-s20-chest-next.png', SHOTS/'sol-750-road.png', SHOTS/'sol-s23-deck.png', SHOTS/'sol-bl6-open.png',
         SHOTS/'sol-s23-home.png'] + frames('s18/m02', [90, 95, 110]) + frames('s17/m01', [150, 300])
for p in never:
    k, _ = kind(p)
    check(f'never tapped: {p.parent.parent.name + "/" if p.parent.name == "video" else ""}{p.name} (got {k})', k is None)
# Every available recorded between-battle frame before match_start: no reward kind is emitted.
import json  # noqa: E402
bad, n = [], 0
for ev in sorted(RUNS.glob('s*/m0?/events.jsonl')):
    if not ('s17' <= ev.parent.parent.name <= 's29'):
        continue
    start = next((json.loads(l)['n'] for l in open(ev) if '"match_start"' in l), None)
    for k in range(0, start or 0, 10):
        p = ev.parent/'video'/f'{k:06d}.jpg'
        if not p.exists():
            continue
        n += 1
        kk, _ = kind(p)
        if kk == 'reward':
            bad.append(str(p))
check(f'calibration set: {n} between-battle frames s17-s29, no reward navigation ({bad[:3]})', not bad)
print(f'{sum(checks)} passed, {len(checks) - sum(checks)} failed')
sys.exit(0 if all(checks) else 1)
