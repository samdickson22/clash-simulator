"""05: compare box sources on a QA frame set and draw side-by-side sheets for a Sol grade.

  python -B compare_boxes.py --index QA_INDEX.json --out DIR [--v2-root ROOT] [--dets DETS.json] [--sam SAM.json]

Methods per object (unit/building, phase != death), keyed by the QA index's box order k:
  v1   current diff box (night tree)            v2   diff v2 (labels under --v2-root, same relative path)
  det  detector box matched to the native object (Hungarian on body-centre distance; team + class aware)
  sam  SAM2 box (prompted with the native anchor)
  comb det if det and sam agree (IoU >= .5); else det if only det; else sam; flagged when they disagree
Writes DIR/boxes.json (all methods, per frame/k) and DIR/sheet-NN.jpg (one row per frame, one panel per method).
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

REPO = Path(__file__).resolve().parents[3]
VOCAB = {n['name']: n for n in json.loads((REPO / 'live/yolo_synth/classes.json').read_text())['names']}
NON_UNIT_KINDS = {'tower', 'spell', 'object', 'ui', 'unknown'}


def iou(a, b):
    if not a or not b:
        return 0.0
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix * iy
    return ix * iy / u if u > 0 else 0.0


def targets(rec):
    return [o for o in rec['objects'] if o['kind'] in ('unit', 'building') and o['phase'] != 'death']


def body_centre(o, priors):
    ax, ay = o['anchor_px']
    air = bool((VOCAB.get(o['class_name']) or {}).get('air'))
    w, h, dy2 = priors.get(o['class_name'], (70.0, 90.0, -45.0 if air else 6.0))
    return ax, ay + dy2 - h / 2, w, h, air


def match_dets(rec, dets, priors):
    objs = targets(rec)
    cand = [d for d in dets if (VOCAB.get(d[4]) or {}).get('kind') not in NON_UNIT_KINDS]
    out = {o['object_id']: None for o in objs}
    if not objs or not cand:
        return out
    cost = np.full((len(objs), len(cand)), 1e6)
    for i, o in enumerate(objs):
        cx, cy, w, h, air = body_centre(o, priors)
        for j, d in enumerate(cand):
            dx = ((d[0] + d[2]) / 2 - cx) / max(w, 30)
            dy = ((d[1] + d[3]) / 2 - cy) / max(h, 30) / (1.6 if air else 1.0)
            dist = (dx * dx + dy * dy) ** .5
            if dist > 1.0:
                continue
            cost[i, j] = dist + (0 if d[5] == o['team'] else .6) + (0 if d[4] == o['class_name'] else .3)
    rows, cols = linear_sum_assignment(cost)
    for i, j in zip(rows, cols):
        if cost[i, j] < 1e5:
            d = cand[j]
            out[objs[i]['object_id']] = dict(box=[int(round(v)) for v in d[:4]], cls=d[4], belong=d[5],
                                             conf=round(float(d[6]), 3))
    return out


def learn_priors(recs):
    acc = {}
    for rec in recs:
        for o in targets(rec):
            if o.get('box') and not o['box_flags']:
                b, (ax, ay) = o['box'], o['anchor_px']
                acc.setdefault(o['class_name'], []).append((b[2] - b[0], b[3] - b[1], b[3] - ay))
    return {k: tuple(np.median(np.array(v), 0)) for k, v in acc.items() if len(v) >= 3}


COLS = {'v1': (0, 0, 255), 'v2': (0, 165, 255), 'det': (0, 220, 0), 'sam': (255, 0, 255), 'comb': (255, 255, 0)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--index', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--v2-root', type=Path)
    ap.add_argument('--dets', type=Path)
    ap.add_argument('--sam', type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    index = json.loads(a.index.read_text())
    dets = json.loads(a.dets.read_text()) if a.dets else {}
    dets = dets.get('frames', dets)
    sam = json.loads(a.sam.read_text()) if a.sam else {}
    sam = sam.get('boxes', sam)
    recs = [json.loads(Path(e['json']).read_text()) for e in index]
    priors = learn_priors(recs)
    methods = ['v1'] + (['v2'] if a.v2_root else []) + (['det'] if dets else []) + (['sam'] if sam else []) + \
        (['comb'] if dets and sam else [])
    allboxes, panels_rows = [], []
    for e, rec in zip(index, recs):
        objs = targets(rec)
        # QA index box order k = r3's converter order (its boxes list); align by class/team in object order
        ks = []
        pool = list(objs)
        for b in e['boxes']:
            o = next((o for o in pool if o['class_name'] == b['class'] and o['team'] == b['team']), None)
            if o is not None:
                pool.remove(o)
            ks.append(o)
        v2 = {}
        if a.v2_root:
            rel = Path(e['json']).relative_to('/mpac/sdicks02/scratch/nulls/night')
            p2 = a.v2_root / rel
            if p2.exists():
                v2 = {o['object_id']: o.get('box') for o in json.loads(p2.read_text())['objects']}
        dm = match_dets(rec, (dets.get(e['json']) or {}).get('dets', []), priors) if dets else {}
        sm = {int(k): v for k, v in (sam.get(e['json']) or {}).items()} if sam else {}
        frame_boxes = []
        for k, o in enumerate(ks):
            if o is None:
                frame_boxes.append(dict(k=k, missing_object=True))
                continue
            oid = o['object_id']
            row = dict(k=k, object_id=oid, cls=o['class_name'], team=o['team'], phase=o['phase'], v1=o.get('box'),
                       flags=o['box_flags'])
            if a.v2_root:
                row['v2'] = v2.get(oid)
            if dets:
                row['det'] = (dm.get(oid) or {}).get('box')
                row['det_info'] = dm.get(oid)
            if sam:
                row['sam'] = sm.get(oid)
            if dets and sam:
                d_, s_ = row['det'], row['sam']
                if d_ and s_:
                    agree = iou(d_, s_)
                    row['comb'], row['comb_src'] = d_, f'det(agree {agree:.2f})' if agree >= .5 else f'det(DISAGREE {agree:.2f})'
                else:
                    row['comb'], row['comb_src'] = (d_, 'det-only') if d_ else (s_, 'sam-only') if s_ else (None, 'none')
            frame_boxes.append(row)
        allboxes.append(dict(i=e['i'], json=e['json'], frame=str(Path(e['json']).parent / rec['frame']), boxes=frame_boxes))
        # panel: crop around all objects
        img = cv2.imread(str(Path(e['json']).parent / rec['frame']))
        pts = [b for r in frame_boxes for m in methods for b in [r.get(m)] if b] + \
              [[o['anchor_px'][0] - 40, o['anchor_px'][1] - 120, o['anchor_px'][0] + 40, o['anchor_px'][1] + 20] for o in objs]
        if not pts:
            continue
        x1 = max(0, int(min(p[0] for p in pts)) - 40); y1 = max(0, int(min(p[1] for p in pts)) - 40)
        x2 = min(img.shape[1], int(max(p[2] for p in pts)) + 40); y2 = min(img.shape[0], int(max(p[3] for p in pts)) + 40)
        crop = img[y1:y2, x1:x2]
        scale = min(1.0, 420 / max(1, crop.shape[0]), 300 / max(1, crop.shape[1])) * 1.6
        panels = []
        for m in methods:
            pimg = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            for r in frame_boxes:
                b = r.get(m)
                if b:
                    q = [int((b[0] - x1) * scale), int((b[1] - y1) * scale), int((b[2] - x1) * scale), int((b[3] - y1) * scale)]
                    cv2.rectangle(pimg, (q[0], q[1]), (q[2], q[3]), COLS[m], 2)
                    cv2.putText(pimg, str(r['k']), (q[0] + 2, q[1] + 14), cv2.FONT_HERSHEY_SIMPLEX, .5, COLS[m], 2)
            cv2.putText(pimg, f"f{e['i']} {m}", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, .55, (255, 255, 255), 2)
            panels.append(pimg)
        h = max(p.shape[0] for p in panels)
        panels = [cv2.copyMakeBorder(p, 0, h - p.shape[0], 0, 6, cv2.BORDER_CONSTANT, value=(40, 40, 40)) for p in panels]
        panels_rows.append(np.hstack(panels))
    (a.out / 'boxes.json').write_text(json.dumps(dict(methods=methods, colours={k: COLS[k] for k in methods},
                                                      frames=allboxes), indent=1))
    for s in range(0, len(panels_rows), 6):
        rows = panels_rows[s:s + 6]
        w = max(r.shape[1] for r in rows)
        sheet = np.vstack([cv2.copyMakeBorder(r, 0, 8, 0, w - r.shape[1], cv2.BORDER_CONSTANT, value=(0, 0, 0)) for r in rows])
        cv2.imwrite(str(a.out / f'sheet-{s // 6:02d}.jpg'), sheet, [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(len(allboxes), 'frames;', methods, '->', a.out)


if __name__ == '__main__':
    main()
