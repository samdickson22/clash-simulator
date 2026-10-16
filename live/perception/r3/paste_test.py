"""Round-3 diagnosis (d): paste canvas-space rectangles between renderer and official frames (same canvas coordinates, so
tiles line up) and decode units at a low threshold.

  python paste_test.py EXPORT_DIR OUT_DIR
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

R = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(R/'src'), str(R/'live/perception'), str(R/'live/loop')]
import canvas as LC  # noqa: E402
import common as C  # noqa: E402
from infer import FRAME_KEYS  # noqa: E402
from clasher.vision.l1_v4 import prepare_pixels  # noqa: E402

L = Path('/mpac/sdicks02/scratch/live-loop')


def decode(frame, vocab, img, thr=.15):
    arena, hud = prepare_pixels(img)
    t = lambda x: torch.from_numpy(np.ascontiguousarray(x)).permute(2, 0, 1)[None].float().div(255)
    with torch.inference_mode():
        out = {k: v.float().numpy() for k, v in zip(FRAME_KEYS, frame(t(arena), t(hud))) if k != 'features'}
    dec = C.decode_frame(out, 0, vocab['cards'], vocab['identities'], threshold=thr, offsets=True, counts=False)
    return [(u['identity'], u['owner'], round(u['x'], 1), round(u['y'], 1), round(u['score'], 3)) for u in dec['units']
            if u['identity'] not in C.TOWER_BODIES]


def main():
    exp, od = Path(sys.argv[1]), Path(sys.argv[2]); od.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(8)
    frame = torch.jit.load(str(exp/'frame.pt'), map_location='cpu').eval(); vocab = json.loads((exp/'vocab.json').read_text())
    ref = {k: cv2.imread(str(L/f'ref/000{k}.png')) for k in (100, 300, 500)}
    off = {k: LC.canvas(cv2.imread(str(L/f'rec/ladder1-r1/{k:06d}.jpg'))) for k in (255, 700)}
    off['tc800'] = LC.canvas(cv2.imread(str(L/'rec/tc2-r1/000800.jpg')))
    cases = [  # (name, dst, src, (x1, y1, x2, y2) canvas box)
        ('ren500 as is', ref[500], None, None),
        ('goblins ren500 -> off255', off[255], ref[500], (375, 740, 475, 850)),
        ('rascals ren500 -> off255', off[255], ref[500], (50, 470, 130, 580)),
        ('rascals+goblins ren500 -> tc800', off['tc800'], ref[500], (50, 470, 130, 580)),
        ('off700 as is', off[700], None, None),
        ('giant off700 -> ren100', ref[100], off[700], (275, 750, 390, 880)),
        ('knight+archers tc800 -> ren100', ref[100], off['tc800'], (85, 345, 185, 480)),
        ('tc800 as is', off['tc800'], None, None),
    ]
    res = {}
    for name, dst, src, box in cases:
        im = dst.copy()
        if src is not None:
            x1, y1, x2, y2 = box; im[y1:y2, x1:x2] = src[y1:y2, x1:x2]
        res[name] = decode(frame, vocab, im)
        cv2.imwrite(str(od/(name.replace(' ', '_').replace('>', '')+'.jpg')), im[200:1000])
        print(name, res[name][:8], flush=True)
    (od/'paste.json').write_text(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
