"""Round 3: select official frames for hand labelling and render labelling sheets (images stay in scratch, never committed).

Each sheet: [frame 1 s earlier | frame | frame with the native tile grid] of the mapped arena (canvas.py), 1.5x.
Grid: x 0..18 from screen left, y 0..32 from screen TOP (native frame; our king at y 29). Lines every tile, labels every 2.

  python label_prep.py OUT_DIR
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

R = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(R/'live/loop')]
import canvas as LC  # noqa: E402

L = Path('/mpac/sdicks02/scratch/live-loop')
GS = [('ladder1', L/'rec/ladder1-r1', 280, 843, 3), ('live1', L/'runs/live1/video', 330, 818, 9),
      ('live2', L/'runs/live2/video', 630, 1271, 9), ('live3', L/'runs/live3/video', 380, 1425, 11),
      ('live4', L/'runs/live4/video', 370, 718, 7), ('live5', L/'runs/live5/video', 310, 1472, 12)]
S = 1.5


def arena_img(path):
    cv = LC.canvas(cv2.imread(str(path)))
    return cv2.resize(cv[200:1000], None, fx=S, fy=S, interpolation=cv2.INTER_CUBIC)


def grid(im):
    g = im.copy()
    H, W = im.shape[:2]
    lab = lambda t, xy: (cv2.putText(g, t, xy, 0, .6, (0, 0, 0), 4), cv2.putText(g, t, xy, 0, .6, (0, 255, 255), 2))
    for x in range(19):
        X = int((LC.TILE_B+LC.TILE_A*x)*S)
        cv2.line(g, (X, 0), (X, H), (255, 255, 255) if x % 2 == 0 else (0, 0, 0), 1)
    for y in range(33):
        Y = int((LC.TILE_D+LC.TILE_C*y-200)*S)
        cv2.line(g, (0, Y), (W, Y), (255, 255, 255) if y % 2 == 0 else (0, 0, 0), 1)
    g = cv2.addWeighted(g, .7, im, .3, 0)
    for x in range(0, 19, 2):
        X = int((LC.TILE_B+LC.TILE_A*x)*S)
        lab(str(x), (X-6, 20)); lab(str(x), (X-6, H-6)); lab(str(x), (X-6, H//2-60))
    for y in range(0, 33, 2):
        Y = int((LC.TILE_D+LC.TILE_C*y-200)*S)
        lab(str(y), (2, Y+6)); lab(str(y), (W-28, Y+6)); lab(str(y), (W//2-10, Y+6))
    return g


def green(path):
    im = cv2.imread(str(path), cv2.IMREAD_REDUCED_COLOR_4)
    h = cv2.cvtColor(im, cv2.COLOR_BGR2HSV); a = h[int(im.shape[0]*.2):int(im.shape[0]*.8)]
    return float(((a[..., 0] > 30) & (a[..., 0] < 50) & (a[..., 1] > 100)).mean())


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    picks = []
    if len(sys.argv) > 2:  # extra set: ARENA:NAME:DIR:FIRST:LAST:N  (e.g. BP:s1m01:/.../video:250:860:25)
        arena, name, d, a, b, n = sys.argv[2].split(':')
        for i in np.linspace(int(a), int(b), int(n)).round().astype(int):
            picks.append((arena, name, Path(d), int(i)))
    else:
        for name, d, a, b, n in GS:
            for i in np.linspace(a, b-15, n).round().astype(int):
                picks.append(('GS', name, d, int(i)))
        tc = L/'rec/tc2-r1'
        cand = [i for i in range(40, 1640, 10) if green(tc/f'{i:06d}.jpg') >= .6]
        for i in [cand[int(k)] for k in np.linspace(0, len(cand)-1, 30).round()]:
            picks.append(('TC', 'tc2', tc, int(i)))
    index = []
    for k, (arena, name, d, i) in enumerate(picks):
        fid = f'{arena}-{name}-{i:06d}'
        prev = d/f'{max(0, i-10):06d}.jpg'
        cur = arena_img(d/f'{i:06d}.jpg')
        sheet = np.hstack([arena_img(prev), np.full((cur.shape[0], 8, 3), 255, np.uint8), cur,
                           np.full((cur.shape[0], 8, 3), 255, np.uint8), grid(cur)])
        cv2.imwrite(str(out/f'{fid}.jpg'), sheet, [cv2.IMWRITE_JPEG_QUALITY, 92])
        index.append(dict(id=fid, arena=arena, source=str(d/f'{i:06d}.jpg'), sheet=str(out/f'{fid}.jpg')))
    old = json.loads((out/'index.json').read_text()) if (out/'index.json').exists() else []
    ids = {x['id'] for x in index}
    (out/'index.json').write_text(json.dumps([x for x in old if x['id'] not in ids]+index, indent=1))
    print(len(index), {a: sum(1 for x in index if x['arena'] == a) for a in {x['arena'] for x in index}})


if __name__ == '__main__':
    main()
