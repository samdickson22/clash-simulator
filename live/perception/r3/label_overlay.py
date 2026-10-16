"""Draw hand labels (and optional predictions from an eval_official.py output) on mapped official arenas, for checking.

  python label_overlay.py LABEL_DIR OUT.jpg ID... [--eval EVAL.json --thr .5]
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

R = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(R/'live/loop')]
import canvas as LC  # noqa: E402

S = 1.2


def pt(x, y):
    return int((LC.TILE_B+LC.TILE_A*x)*S), int((LC.TILE_D+LC.TILE_C*y-200)*S)


def main():
    args = sys.argv[1:]; ev = None; thr = .5
    if '--eval' in args:
        k = args.index('--eval'); ev = {r['id']: r for r in json.loads(Path(args[k+1]).read_text())['rows']}; args = args[:k]+args[k+2:]
    if '--thr' in args:
        k = args.index('--thr'); thr = float(args[k+1]); args = args[:k]+args[k+2:]
    lab_dir, out, ids = Path(args[0]), args[1], args[2:]
    ix = {x['id']: x for x in json.loads((lab_dir.parent/'label/index.json').read_text())}
    tiles = []
    for i in ids:
        lab = json.loads((lab_dir/f'{i}.json').read_text())
        im = cv2.resize(LC.canvas(cv2.imread(ix[i]['source']))[200:1000], None, fx=S, fy=S)
        for u in lab['units']:
            c = (255, 160, 0) if u['owner'] == 'us' else (0, 0, 255)
            p = pt(u['x'], u['y']); cv2.circle(im, p, 5, c, -1); cv2.circle(im, p, 6, (255, 255, 255), 1)
            cv2.putText(im, u['card'][:6]+u['conf'][0], (p[0]+7, p[1]+4), 0, .38, (0, 0, 0), 3)
            cv2.putText(im, u['card'][:6]+u['conf'][0], (p[0]+7, p[1]+4), 0, .38, (255, 255, 255), 1)
        if ev and i in ev:
            for u in ev[i]['pred']:
                if u['score'] >= thr:
                    p = pt(u['x'], u['y']); c = (255, 160, 0) if u['owner'] == 1 else (0, 0, 255)
                    cv2.drawMarker(im, p, c, cv2.MARKER_TILTED_CROSS, 12, 2)
                    cv2.putText(im, f"{u['identity'][:5]}{u['score']:.2f}", (p[0]-40, p[1]-8), 0, .33, (0, 255, 255), 1)
        cv2.putText(im, f"{i} {lab['frame_confidence']}{' EXCL' if lab.get('exclude') else ''}", (4, 14), 0, .45, (0, 255, 255), 1)
        tiles.append(im)
    cv2.imwrite(out, np.hstack(tiles))


if __name__ == '__main__':
    main()
