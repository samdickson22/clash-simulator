"""Dense-frame weakness audit (standing duty, reports/live/perception/WEAKNESSES.md): pick the busiest live frames and draw what the
live model and a YOLO candidate saw, for a Sol reviewer to list misses / merges / wrong owner / wrong class / phantoms.

scan   (GPU host): run a YOLO candidate on every frame of the given lists and store its unit detections (thr .3).
  python audit_dense.py scan --weights W.pt --katacr-src SRC --frames LIST.txt --out DETS.json
sheets (05): density = number of YOLO units (score >= .5) + overlapping pairs (IoU > .1); dense set = top --top-frac of frames per
battle; a seeded random --n frames from it (plus --include ids), each drawn as  clean | live log units (frames.jsonl `units`, the model
that played) | YOLO boxes.  Live-log units are points (tiles) drawn as a cross + label; YOLO units as boxes. Images stay on 05 scratch.
  python audit_dense.py sheets --dets DETS.json --out DIR --n 40 --seed S [--include RUN:N ...]
"""
import argparse
import json
import random
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_yolo import crop, CROP, WK, HK, NON_UNIT  # noqa: E402

LIVE = Path('/mpac/sdicks02/scratch/live-loop/runs')


def scan(a):
    sys.path.insert(0, a.katacr_src)
    from katacr.constants.label_list import spell_unit_list, object_unit_list
    from katacr.yolov8.train import YOLO_CR
    m = YOLO_CR(a.weights); drop = NON_UNIT | set(spell_unit_list) | set(object_unit_list)
    out = {}
    for ln in Path(a.frames).read_text().split():
        im = cv2.imread(ln)
        if im is None:
            continue
        h, w = im.shape[:2]; x0, y0, x1, y1 = CROP[0]*w/720, CROP[1]*h/1280, CROP[2]*w/720, CROP[3]*h/1280
        sx, sy = WK/(x1-x0), HK/(y1-y0)
        r = m.predict(crop(im), device=a.device, verbose=False, conf=.3, iou=.6, imgsz=(896, 576))[0]
        out[ln] = [dict(name=m.names[int(b[5])], team=int(b[6]), score=round(float(b[4]), 3),
                        box=[round(float(b[0])/sx+x0, 1), round(float(b[1])/sy+y0, 1), round(float(b[2])/sx+x0, 1), round(float(b[3])/sy+y0, 1)])
                   for b in r.orig_boxes.cpu().numpy() if m.names[int(b[5])] not in drop]
    Path(a.out).write_text(json.dumps(out))
    print('frames', len(out))


def iou(a, b):
    ix = max(0, min(a[2], b[2])-max(a[0], b[0])); iy = max(0, min(a[3], b[3])-max(a[1], b[1])); i = ix*iy
    return i/max(1e-6, (a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-i)


def sheets(a):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'r3'))
    from yolo_labels import tile_px
    dets = json.loads(Path(a.dets).read_text())
    by_run = {}
    for path, ds in dets.items():
        ds = [d for d in ds if d['score'] >= .5]
        dens = len(ds) + sum(iou(p['box'], q['box']) > .1 for i, p in enumerate(ds) for q in ds[i+1:])
        run = str(Path(path).parent.parent.relative_to(LIVE)); by_run.setdefault(run, []).append((dens, path))
    dense = []
    for run, v in by_run.items():
        v.sort(reverse=True); dense += v[:max(1, int(len(v)*a.top_frac))]
    rng = random.Random(a.seed); pick = [p for _, p in rng.sample(dense, min(a.n, len(dense)))]
    for inc in a.include:
        run, n = inc.rsplit(':', 1); p = str(LIVE/run/'video'/f'{int(n):06d}.jpg')
        if p not in pick:
            pick.append(p)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True); index = []
    logs = {}
    for p in pick:
        run_dir = Path(p).parent.parent; n = int(Path(p).stem); run = str(run_dir.relative_to(LIVE)).replace('/', '-')
        if run_dir not in logs:
            logs[run_dir] = {r['n']: r for r in (json.loads(x) for x in (run_dir/'frames.jsonl').read_text().splitlines() if x.strip())}
        rec = logs[run_dir].get(n, {}); im = cv2.imread(p); h, w = im.shape[:2]
        live, yol = im.copy(), im.copy()
        for k, (tm, card, x, y) in enumerate(rec.get('units') or []):
            # live log: owner 0 = ours (bottom), x/y tiles with y from the BOTTOM -> label convention y from the top
            gx, gy = tile_px(float(x), 32-float(y), w, h); c = (255, 160, 0) if tm == 0 else (0, 0, 255)
            cv2.drawMarker(live, (int(gx), int(gy)), c, cv2.MARKER_CROSS, 18, 2)
            cv2.putText(live, f'L{k} {card}', (int(gx)+6, int(gy)-4), 0, .4, (0, 0, 0), 3); cv2.putText(live, f'L{k} {card}', (int(gx)+6, int(gy)-4), 0, .4, c, 1)
        ds = [d for d in dets.get(p, []) if d['score'] >= .5]
        for k, d in enumerate(ds):
            c = (255, 160, 0) if d['team'] == 0 else (0, 0, 255); x1, y1, x2, y2 = map(int, d['box'])
            cv2.rectangle(yol, (x1, y1), (x2, y2), c, 1)
            cv2.putText(yol, f"Y{k} {d['name']} {d['score']:.2f}", (x1, y1-3), 0, .35, (0, 0, 0), 3)
            cv2.putText(yol, f"Y{k} {d['name']} {d['score']:.2f}", (x1, y1-3), 0, .35, c, 1)
        y0, y1_ = int(.02*h), int(.80*h); sep = np.full((y1_-y0, 6, 3), 255, np.uint8)
        fid = f'AUD-{run}-{n:06d}'
        cv2.imwrite(str(out/f'{fid}.jpg'), np.hstack([im[y0:y1_], sep, live[y0:y1_], sep, yol[y0:y1_]]), [cv2.IMWRITE_JPEG_QUALITY, 92])
        index.append(dict(id=fid, source=p, live_units=rec.get('units'), yolo=ds))
    (out/'index.json').write_text(json.dumps(index, indent=1))
    print('sheets', len(index), 'dense pool', len(dense))


def main():
    p = argparse.ArgumentParser(); sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('scan'); s.add_argument('--weights', required=True); s.add_argument('--katacr-src', required=True)
    s.add_argument('--frames', required=True); s.add_argument('--out', required=True); s.add_argument('--device', default='0')
    t = sub.add_parser('sheets'); t.add_argument('--dets', required=True); t.add_argument('--out', required=True)
    t.add_argument('--n', type=int, default=40); t.add_argument('--seed', type=int, default=0); t.add_argument('--top-frac', type=float, default=.15)
    t.add_argument('--include', nargs='*', default=[])
    a = p.parse_args()
    scan(a) if a.cmd == 'scan' else sheets(a)


if __name__ == '__main__':
    main()
