"""05: sample labelled night frames per box method and draw QA crops for a Sol grade.

  python -B qa_methods.py OUT_DIR [--per 12] [--seed 1]

Sets (box drawn = that method's box; k numbers objects within a frame):
  agreed  `box` (x1h_agreed) on classes outside the first QA set (bat/knight/valkyrie excluded)
  fit     `box_fit` (anchor fit, isolated untrusted bodies)
  split   `box_split` from solo swarm runs (`-solo` in the run id)
Writes OUT_DIR/<set>-NN.jpg crops and OUT_DIR/index.json {set: [{img, label, frame, boxes: [{k, object_id, cls, team,
phase, box}]}]}.
"""
import argparse
import glob
import json
import random
from pathlib import Path

import cv2

NIGHT = '/mpac/sdicks02/scratch/nulls/night'
FIELD = {'agreed': 'box', 'fit': 'box_fit', 'split': 'box_split'}
COL = {'agreed': (0, 220, 0), 'fit': (255, 0, 255), 'split': (0, 165, 255)}


def candidates(files, kind):
    out = []
    for f in files:
        try:
            rec = json.loads(Path(f).read_text())
        except (OSError, ValueError):
            continue
        if rec.get('purpose') != 'scene':
            continue
        objs = [o for o in rec['objects'] if o['kind'] in ('unit', 'building') and o['phase'] != 'death'
                and o.get(FIELD[kind]) and o.get('body_source') == 'empirical']
        if kind == 'agreed':
            objs = [o for o in objs if o['class_name'] not in ('bat', 'knight', 'valkyrie')]
        if objs:
            out.append((f, rec, objs))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out', type=Path)
    ap.add_argument('--per', type=int, default=12)
    ap.add_argument('--seed', type=int, default=1)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(a.seed)
    allf = [f for f in glob.glob(f'{NIGHT}/i*/*/chunk-*/*.json') if '/raw-' not in f]
    rnd.shuffle(allf)
    index = {}
    for kind in ('agreed', 'fit', 'split'):
        pool = [f for f in allf if '-solo' in f] if kind == 'split' else allf
        picked, seen_runs = [], {}
        for f, rec, objs in candidates(pool[:4000], kind):
            run = rec['run']
            if seen_runs.get(run, 0) >= 2:  # spread over runs / classes
                continue
            seen_runs[run] = seen_runs.get(run, 0) + 1
            picked.append((f, rec, objs))
            if len(picked) >= a.per:
                break
        index[kind] = []
        for n, (f, rec, objs) in enumerate(picked):
            img = cv2.imread(str(Path(f).parent / rec['frame']))
            bs = [o[FIELD[kind]] for o in objs]
            x1 = max(0, min(b[0] for b in bs) - 60); y1 = max(0, min(b[1] for b in bs) - 60)
            x2 = min(img.shape[1], max(b[2] for b in bs) + 60); y2 = min(img.shape[0], max(b[3] for b in bs) + 60)
            crop = img[y1:y2, x1:x2].copy()
            s = min(3.0, 700 / max(crop.shape[:2]))
            crop = cv2.resize(crop, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
            rows = []
            for k, o in enumerate(objs):
                b = o[FIELD[kind]]
                q = [int((b[0] - x1) * s), int((b[1] - y1) * s), int((b[2] - x1) * s), int((b[3] - y1) * s)]
                cv2.rectangle(crop, (q[0], q[1]), (q[2], q[3]), COL[kind], 2)
                cv2.putText(crop, str(k), (q[0] + 3, q[1] + 16), cv2.FONT_HERSHEY_SIMPLEX, .6, COL[kind], 2)
                rows.append(dict(k=k, object_id=o['object_id'], cls=o['class_name'], team=o['team'], phase=o['phase'],
                                 box=b, box_det=o.get('box_det'), box_diff=o.get('box_diff')))
            name = f'{kind}-{n:02d}.jpg'
            cv2.imwrite(str(a.out / name), crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
            index[kind].append(dict(img=name, label=f, frame=str(Path(f).parent / rec['frame']), crop_origin=[x1, y1],
                                    scale=s, boxes=rows))
    (a.out / 'index.json').write_text(json.dumps(index, indent=1))
    print({k: len(v) for k, v in index.items()}, '->', a.out)


if __name__ == '__main__':
    main()
