"""Mine owner-hard TRAINING frames from mirror battles (the opponent's Battle Log deck shares cards with ours): the detector's team
channel learned 'our deck card = ours' (real data: musketeer 92 ours / 4 enemy official, 1930/32 KataCR part2), so enemy copies of
our cards are the examples it lacks. Never pass EVAL-SPLIT held-out battles (refused below).

Runs a YOLO checkpoint on every --stride-th frame of each battle; a detection of a mirror card scores +1 if predicted ENEMY (the rare
case) and +2 if a same-class detection within 1.5 tiles in the previous/next sampled frame has the other team (owner flip = likely
error); buildings x2. Frames are picked greedily by score, >= --gap frames apart, up to --n per run. Output: JSON list of
{run, n, video, score, hits} (feed the frame numbers to prelabel_yolo.py RUN:DIR:-:n1,n2,... and Sol verification).
Selection heuristic only; the labels themselves are verified by hand.

  python mine_mirror.py --weights W.pt --katacr-src SRC --runs RUN:FRAME_DIR:Card1,Card2 ... --out MINED.json [--stride 6 --n 3]
"""
import argparse
import json
import math
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent)); sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'r3'))
from eval_yolo import crop  # noqa: E402
from yolo_labels import CARD  # noqa: E402

HELD_OUT = {'ladder1-r1', 'live1', 'live2', 'live3', 'live4', 'live5', 'tc2-r1', 's1-m01', 's2-m01', 's5-m01', 's5-m02', 's7-m04',
            's14-m02', 's15-m01', 's19-m01', 's19-m02'}  # reports/live/perception/EVAL-SPLIT.md
BUILDINGS = {'cannon', 'goblin-hut', 'tombstone', 'goblin-cage', 'bomb-tower', 'inferno-tower', 'tesla', 'mortar', 'x-bow'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--weights', required=True); p.add_argument('--katacr-src', required=True)
    p.add_argument('--runs', nargs='+', required=True); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--stride', type=int, default=6); p.add_argument('--n', type=int, default=3); p.add_argument('--gap', type=int, default=40)
    p.add_argument('--conf', type=float, default=.4); p.add_argument('--device', default='0'); p.add_argument('--skip', type=int, default=40)
    a = p.parse_args()
    sys.path.insert(0, a.katacr_src)
    from katacr.yolov8.train import YOLO_CR
    from katacr.constants.label_list import spell_unit_list
    m = YOLO_CR(a.weights)
    out = json.loads(a.out.read_text()) if a.out.exists() else []
    done = {r['run'] for r in out}
    for spec in a.runs:
        run, fdir, cards = spec.split(':')
        if run in HELD_OUT:
            sys.exit(f'{run} is an EVAL-SPLIT held-out battle')
        if run in done:
            continue
        mirror = {CARD[c] for c in cards.split(',') if c in CARD} - set(spell_unit_list)
        frames = sorted(Path(fdir).glob('*.jpg'))[a.skip::a.stride]
        dets = []
        for f in frames:
            r = m.predict(crop(cv2.imread(str(f))), device=a.device, verbose=False, conf=a.conf, iou=.6, imgsz=(896, 576))[0]
            ds = []
            for b in r.orig_boxes.cpu().numpy():
                name = m.names[int(b[5])]
                if name in mirror:
                    ds.append((name, int(b[6]), ((b[0]+b[2])/2-6)/30.889, (b[3]-64)/25))
            dets.append((int(f.stem), ds))
        scored = []
        for i, (n, ds) in enumerate(dets):
            s, hits = 0., []
            for name, team, x, y in ds:
                w = 2 if name in BUILDINGS else 1
                flip = any(nm == name and tm != team and math.hypot(xx-x, yy-y) <= 1.5
                           for j in (i-1, i+1) if 0 <= j < len(dets) for nm, tm, xx, yy in dets[j][1])
                v = w*(int(team == 1) + 2*int(flip))
                if v:
                    s += v; hits.append(dict(name=name, team=team, x=round(float(x), 2), y=round(float(y), 2), flip=flip))
            if s:
                scored.append((s, n, hits))
        picked = []
        for s, n, hits in sorted(scored, key=lambda t: -t[0]):
            if len(picked) < a.n and all(abs(n-q['n']) >= a.gap for q in picked):
                picked.append(dict(run=run, n=n, video=fdir, score=s, hits=hits))
        out += picked
        a.out.write_text(json.dumps(out, indent=1))
        print(run, len(frames), 'sampled,', len(scored), 'scored, picked', [(q['n'], q['score']) for q in picked], flush=True)


if __name__ == '__main__':
    main()
