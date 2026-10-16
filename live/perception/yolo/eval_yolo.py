"""Score a KataCR-format YOLO detector on the EVAL-SPLIT official set (reports/live/perception/EVAL-SPLIT.md).

Each eval frame is cropped KataCR-style (official_to_cr.CROP -> 568x896), predicted, and every box becomes a ground point in tiles:
x = box centre + dx, y = box bottom + dy, with per-class (dx, dy) medians measured on our TRAINING-battle box labels
(--offsets ground-offsets.json); classes without a measurement: flyers +.56, buildings -.8, others -.05 tile.
Tiles: x = (px - 6)/30.889, y = (py - 64)/25 in the crop (KataCR grid; equals our tile grid by construction).
Identity is scored at SPRITE level: truth (card, body) -> KataCR name via r3/yolo_labels BODY/CARD; truth outside KataCR's names is an
ignore region for identity and counts for owner-only. Matching: same team, <= 1 tile (and 1.5), greedy by score (as eval_official).
Towers / non-unit classes (bars, clock, text, elixir, emote, ...) are dropped from predictions.

  python eval_yolo.py --weights W.pt [--weights2 W2.pt] --katacr-src SRC --labels LABEL_DIR --index INDEX_JSON --empties EMPTIES \
      --out OUT.json [--device 0] [--conf .1]
"""
import argparse
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

CROP = (42.2, 31.3, 674.2, 1019.3)
WK, HK = 568, 896
THRS = (.2, .3, .4, .5, .6, .7)
NON_UNIT = {'king-tower', 'queen-tower', 'cannoneer-tower', 'dagger-duchess-tower', 'dagger-duchess-tower-bar', 'tower-bar',
            'king-tower-bar', 'bar', 'bar-level', 'clock', 'emote', 'text', 'elixir', 'selected', 'skeleton-king-bar'}


def crop(im):
    h, w = im.shape[:2]
    x0, y0, x1, y1 = CROP[0]*w/720, CROP[1]*h/1280, CROP[2]*w/720, CROP[3]*h/1280
    sx, sy = WK/(x1-x0), HK/(y1-y0)
    return cv2.warpAffine(im, np.array([[sx, 0, -x0*sx], [0, sy, -y0*sy]]), (WK, HK), flags=cv2.INTER_AREA)


def match(preds, truth, radius, ignore=()):
    used, tp, fp = set(), 0, 0
    for s, x, y, c in sorted(preds, key=lambda p: -p[0]):
        best, bd = None, radius+1e-9
        for j, (tx, ty, tc) in enumerate(truth):
            if j in used or tc != c:
                continue
            d = math.hypot(tx-x, ty-y)
            if d <= bd:
                best, bd = j, d
        if best is not None:
            used.add(best); tp += 1
        elif not any(math.hypot(ix-x, iy-y) <= 1. and io == c[0] for ix, iy, io in ignore):
            fp += 1
    match.used = used
    return tp, fp, len(truth)-len(used)


def score(rows, emp, vocab_names=None, drop=()):
    """Metrics from stored rows (truth + predictions) and empty-frame predictions; `drop` = predicted names to ignore."""
    rows = [dict(r, pred=[d for d in r['pred'] if d['name'] not in drop]) for r in rows]
    emp = {k: [d for d in v if d['name'] not in drop] for k, v in emp.items()}
    res = dict(frames=len(rows), metrics={})
    for t in THRS:
        for rad in (1., 1.5):
            agg = {}
            for r in rows:
                pr = [(d['score'], d['x'], d['y'], (d['team'], d['name'])) for d in r['pred'] if d['score'] >= t]
                tid = [(u['x'], u['y'], (u['team'], u['name'])) for u in r['truth'] if u['vocab']]
                ign = [(u['x'], u['y'], u['team']) for u in r['truth'] if not u['vocab']]
                tow = [(u['x'], u['y'], u['team']) for u in r['truth']]
                for key, (pp, tt, ig) in dict(id=(pr, tid, ign), owner=([(s, x, y, k[0]) for s, x, y, k in pr], tow, ())).items():
                    if key == 'owner':
                        tp, fp, fn = match([(s, x, y, (c, 0)) for s, x, y, c in pp], [(x, y, (c, 0)) for x, y, c in tt], rad)
                    else:
                        tp, fp, fn = match(pp, tt, rad, ig)
                        for j, (_, _, (tm, nm)) in enumerate(tt):
                            pc = agg.setdefault(f"{r['arena']}:card", {}).setdefault(nm, [0, 0]); pc[0] += j in match.used; pc[1] += 1
                    for g in (r['arena'], 'all'):
                        s_ = agg.setdefault(f'{g}:{key}', dict(tp=0, fp=0, fn=0, frames=0))
                        s_['tp'] += tp; s_['fp'] += fp; s_['fn'] += fn; s_['frames'] += 1
            for k, s_ in agg.items():
                if not k.endswith(':card'):
                    s_['P'] = round(s_['tp']/max(1, s_['tp']+s_['fp']), 3); s_['R'] = round(s_['tp']/max(1, s_['tp']+s_['fn']), 3)
                    s_['fp_per_frame'] = round(s_['fp']/max(1, s_['frames']), 3)
            res['metrics'][f'thr{t}_r{rad}'] = agg
    res['empty'] = {f'thr{t}': round(float(np.mean([sum(d['score'] >= t for d in v) for v in emp.values()])), 3) for t in THRS}
    return res


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--weights', required=True); p.add_argument('--weights2'); p.add_argument('--katacr-src', required=True)
    p.add_argument('--labels', type=Path, required=True); p.add_argument('--index', type=Path, required=True)
    p.add_argument('--empties', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--device', default='0'); p.add_argument('--conf', type=float, default=.1)
    p.add_argument('--offsets', type=Path, default=None)
    p.add_argument('--imgsz', default='896,576', help='predict size h,w (train imgsz 1024 -> 1024,672)')
    a = p.parse_args()
    sys.path.insert(0, a.katacr_src); sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'r3'))
    from katacr.constants.label_list import flying_unit_list, tower_unit_list, spell_unit_list, object_unit_list
    drop = NON_UNIT | set(spell_unit_list) | set(object_unit_list)
    offs = json.loads(a.offsets.read_text()) if a.offsets else {}
    buildings = {'goblin-hut', 'goblin-cage', 'tombstone', 'cannon', 'tesla', 'inferno-tower', 'bomb-tower', 'x-bow', 'mortar',
                 'furnace', 'barbarian-hut', 'elixir-collector', 'goblin-drill'}
    from katacr.yolov8.train import YOLO_CR
    from yolo_labels import BODY, CARD
    models = [YOLO_CR(w) for w in (a.weights, a.weights2) if w]
    fly = set(flying_unit_list)

    def predict(path):
        im = crop(cv2.imread(path)); out = []
        for m in models:
            r = m.predict(im, device=a.device, verbose=False, conf=a.conf, iou=.6, imgsz=tuple(int(v) for v in a.imgsz.split(',')))[0]
            for b in r.orig_boxes.cpu().numpy():
                name = m.names[int(b[5])]
                if name in drop:
                    continue
                x1, y1, x2, y2 = b[:4]
                o = offs.get(name) or dict(dx=0., dy=.56 if name in fly else -.8 if name in buildings else -.05)
                ty = (y2-64)/25+o['dy']
                out.append(dict(name=name, team=int(b[6]), x=float(((x1+x2)/2-6)/30.889+o['dx']), y=float(ty), score=float(b[4]),
                                box=[float(v) for v in b[:4]]))
        return out

    ix = {x['id']: x for x in json.loads(a.index.read_text())}
    rows = []
    for f in sorted(a.labels.glob('*.json')):
        lab = json.loads(f.read_text())
        if lab.get('exclude'):
            continue
        truth = []
        for u in lab['units']:
            name = BODY.get(u.get('body')) or CARD.get(u['card'])
            truth.append(dict(x=float(u['x']), y=float(u['y']), team=0 if u['owner'] == 'us' else 1, name=name,
                              vocab=name is not None and name in models[0].names.values()))
        rows.append(dict(id=lab['id'], arena=lab['id'][:2], truth=truth, pred=predict(ix[lab['id']]['source'])))
    emp = {s: predict(s) for s in a.empties.read_text().split()}
    res = score(rows, emp, models[0].names.values())
    res['weights'] = [a.weights, a.weights2]; res['empty_preds'] = emp
    res['rows'] = rows
    a.out.write_text(json.dumps(res, indent=1))
    for t in ('0.3', '0.5'):
        m = res['metrics'][f'thr{t}_r1.0']
        print(t, {k: (v['P'], v['R']) for k, v in m.items() if not k.endswith(':card') and k.split(':')[0] in ('GS', 'TC', 'BP', 'all')},
              'empty', res['empty'][f'thr{t}'])


if __name__ == '__main__':
    main()
