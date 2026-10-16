"""Full-label proposals for YOLO training frames: targeted human labels (labels-nc) + model detections of every other unit.

Model units (score >= --thr) that lie within 1 tile (same owner) of a human-labelled unit are dropped; the rest are added with
conf='model' for the helpers to verify. Output: one JSON per frame in the base-brief format (card, body, owner, x, y, conf), plus
`complete: false` until a helper verifies the frame.

  python prelabel.py --ckpt CKPT --labels-nc labels-nc-raw --index label-nc/index.json --out labels-yolo-pre [--thr .5]
"""
import argparse
import json
import math
import sys
from pathlib import Path

import cv2
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_official import Model  # noqa: E402  (puts src/, live/perception and live/loop on the path)
import canvas as LC  # noqa: E402
import common as C  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--ckpt'); p.add_argument('--export'); p.add_argument('--labels-nc', type=Path, required=True)
    p.add_argument('--index', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--thr', type=float, default=.5)
    a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True); torch.set_num_threads(12)
    m = Model(a.ckpt, a.export)
    ix = {x['id']: x for x in json.loads(a.index.read_text())}
    n_h = n_m = 0
    for f in sorted(a.labels_nc.glob('*.json')):
        lab = json.loads(f.read_text())
        if lab.get('exclude'):
            continue
        dec = m(LC.canvas(cv2.imread(ix[lab['id']]['source'])))
        units = [dict(u, src='human') for u in lab['units']]
        for d in dec['units']:
            if d['identity'] in C.TOWER_BODIES or d['score'] < a.thr:
                continue
            owner = 'us' if d['owner'] == 1 else 'opp'
            if any(u['owner'] == owner and math.hypot(float(u['x'])-d['x'], float(u['y'])-d['y']) <= 1. for u in units):
                continue
            units.append(dict(card=d['identity'], owner=owner, x=round(d['x'], 2), y=round(d['y'], 2), conf='model',
                              score=round(d['score'], 3), src='model'))
            n_m += 1
        n_h += len(lab['units'])
        (a.out/f.name).write_text(json.dumps(dict(id=lab['id'], labeller='prelabel', complete=False, exclude=False,
                                                  notes='targeted human labels + model proposals', units=units), indent=1))
    print('frames', len(list(a.out.glob('*.json'))), 'human', n_h, 'model', n_m)


if __name__ == '__main__':
    main()
