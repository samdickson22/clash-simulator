"""Training-frame proposals from a YOLO candidate (never for eval truth): sample battle frames, predict units, write label JSONs in
the YOLO-BRIEF format (card/body, owner, x, y in tiles, box_px in capture pixels, conf 'model') + an index + numbered-box sheets input.

Card names: KataCR name -> our card via the inverse of r3/yolo_labels CARD/BODY maps; otherwise 'OOV:<katacr-name>' (official_to_cr
maps it back to the KataCR class). Frames of EVAL-SPLIT held-out battles must not be passed in.

  python prelabel_yolo.py --weights W.pt --katacr-src SRC --offsets OFFS --runs RUN:VIDEO_DIR:FRAMES_JSONL[:n1,n2,...] ... --per-run 10
      --out-labels DIR --out-index INDEX.json --prefix BBT [--conf .4]
"""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent)); sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'r3'))
from eval_yolo import crop, CROP, WK, HK, NON_UNIT  # noqa: E402
from yolo_labels import BODY, CARD  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--weights', required=True); p.add_argument('--katacr-src', required=True); p.add_argument('--offsets', type=Path)
    p.add_argument('--runs', nargs='+', required=True); p.add_argument('--per-run', type=int, default=10)
    p.add_argument('--out-labels', type=Path, required=True); p.add_argument('--out-index', type=Path, required=True)
    p.add_argument('--prefix', default='BBT'); p.add_argument('--conf', type=float, default=.4); p.add_argument('--device', default='cpu')
    p.add_argument('--arena', default='barbarian-bowl'); p.add_argument('--source-root', help='index source = ROOT/RUN/<n>.jpg (frames copied from 05)')
    a = p.parse_args(); a.out_labels.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, a.katacr_src)
    from katacr.constants.label_list import flying_unit_list, spell_unit_list, object_unit_list
    from katacr.yolov8.train import YOLO_CR
    m = YOLO_CR(a.weights); drop = NON_UNIT | set(spell_unit_list) | set(object_unit_list); fly = set(flying_unit_list)
    offs = json.loads(a.offsets.read_text()) if a.offsets else {}
    body_inv = {v: k for k, v in BODY.items()}
    card_inv = {}
    for k, v in CARD.items():
        if not k.startswith('OOV:'):
            card_inv.setdefault(v, k)
    index = json.loads(a.out_index.read_text()) if a.out_index.exists() else []
    for spec in a.runs:
        run, vdir, fjson = spec.split(':')[:3]
        if len(spec.split(':')) > 3:  # explicit frames: RUN:VIDEO_DIR:-:n1,n2,...
            todo = [int(v) for v in spec.split(':')[3].split(',')]
        else:
            rows = [json.loads(x) for x in Path(fjson).read_text().splitlines() if x.strip()]
            ns = [r['n'] for r in rows if r.get('state') == 'battle']
            if not ns:
                continue
            todo = np.linspace(ns[0]+40, ns[-1]-20, a.per_run).round().astype(int)
        for n in todo:
            src = Path(vdir)/f'{n:06d}.jpg'
            if not src.exists():
                continue
            im = cv2.imread(str(src)); h, w = im.shape[:2]
            x0, y0, x1, y1 = CROP[0]*w/720, CROP[1]*h/1280, CROP[2]*w/720, CROP[3]*h/1280
            sx, sy = WK/(x1-x0), HK/(y1-y0)
            r = m.predict(crop(im), device=a.device, verbose=False, conf=a.conf, iou=.6, imgsz=(896, 576))[0]
            units = []
            for b in r.orig_boxes.cpu().numpy():
                name = m.names[int(b[5])]
                if name in drop:
                    continue
                bx1, by1, bx2, by2 = [float(v) for v in b[:4]]
                o = offs.get(name) or dict(dx=0., dy=.56 if name in fly else -.05)
                card = card_inv.get(name); body = body_inv.get(name)
                if card is None:
                    card = 'OOV:'+name
                units.append(dict(card=card, **({'body': body} if body else {}), owner='opp' if int(b[6]) else 'us',
                                  x=round(((bx1+bx2)/2-6)/30.889+o['dx'], 2), y=round((by2-64)/25+o['dy'], 2),
                                  box_px=[round(bx1/sx+x0, 1), round(by1/sy+y0, 1), round(bx2/sx+x0, 1), round(by2/sy+y0, 1)],
                                  conf='model', score=round(float(b[4]), 3), src='model', katacr=name))
            fid = f'{a.prefix}-{run}-{n:06d}'
            (a.out_labels/f'{fid}.json').write_text(json.dumps(dict(id=fid, labeller='prelabel-yolo', complete=False, exclude=False,
                                                                     notes=f'{Path(a.weights).name} proposals', units=units), indent=1))
            index.append(dict(id=fid, run=run, n=int(n), source=str(Path(a.source_root)/run/f'{n:06d}.jpg') if a.source_root else str(src),
                              arena=a.arena))
    a.out_index.write_text(json.dumps(index, indent=1))
    print('frames', len(index))


if __name__ == '__main__':
    main()
