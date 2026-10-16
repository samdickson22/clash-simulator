"""Manifest + coverage of generated shards, and label-overlay sheets for eyeballing.

  python inspect_shards.py manifest OUT [--classes classes.json]      -> OUT/manifest.json (+ printed summary)
  python inspect_shards.py overlay SHARD_DIR SHEET.jpg [--n 20] [--classes ...]   (boxes + name/team drawn on frames)
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent


def manifest(out, classes):
    names = {x['idx']: x for x in json.loads(Path(classes).read_text())['names']}
    shards, tot = [], Counter()
    frames = boxes = 0
    for d in sorted(Path(out).glob('*/DONE.json')):
        done = json.loads(d.read_text())
        shards.append(dict(dir=d.parent.name, frames=done['frames'], boxes=done['boxes'], created=done['created']))
        frames += done['frames']; boxes += done['boxes']
        tot.update(done['counts'])
    per = {}
    for key, n in tot.items():
        idx, b = map(int, key.split('_'))
        per.setdefault(names[idx]['name'], [0, 0])[b] += n
    labelled = [x['name'] for x in names.values() if x['labelled']]
    missing = {n: [t for t in (0, 1) if per.get(n, [0, 0])[t] == 0] for n in labelled}
    missing = {k: v for k, v in missing.items() if v}
    doc = dict(root=str(Path(out).resolve()), frames=frames, boxes=boxes, shards=shards, per_name=per, missing_name_team=missing,
               layout='SHARD/images/<id>.jpg + SHARD/labels/<id>.txt (name_idx cx cy w h belong; yolo id = 2*name_idx+belong) + meta.jsonl',
               classes=str(Path(classes).resolve()))
    (Path(out)/'manifest.json').write_text(json.dumps(doc, indent=1))
    return doc


def overlay(shard, sheet, n, classes):
    names = {x['idx']: x['name'] for x in json.loads(Path(classes).read_text())['names']}
    imgs = sorted((Path(shard)/'images').glob('*.jpg'))[:n]
    tiles = []
    for f in imgs:
        im = cv2.imread(str(f))
        for line in (Path(shard)/'labels'/(f.stem+'.txt')).read_text().split('\n'):
            if not line.strip():
                continue
            idx, cx, cy, w, h, b = line.split()
            cx, cy, w, h = float(cx)*568, float(cy)*896, float(w)*568, float(h)*896
            col = (255, 160, 0) if b == '0' else (0, 0, 255)
            p1, p2 = (int(cx-w/2), int(cy-h/2)), (int(cx+w/2), int(cy+h/2))
            cv2.rectangle(im, p1, p2, col, 1)
            cv2.putText(im, f'{names[int(idx)][:12]}', (p1[0], max(8, p1[1]-2)), 0, .3, col, 1)
        tiles.append(im)
    while len(tiles) % 5:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.concatenate(tiles[i:i+5], 1) for i in range(0, len(tiles), 5)]
    cv2.imwrite(str(sheet), np.concatenate(rows, 0), [cv2.IMWRITE_JPEG_QUALITY, 85])


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd', required=True)
    m = sub.add_parser('manifest'); m.add_argument('out')
    o = sub.add_parser('overlay'); o.add_argument('shard'); o.add_argument('sheet'); o.add_argument('--n', type=int, default=20)
    for s in (m, o):
        s.add_argument('--classes', default=str(HERE/'classes.json'))
    a = p.parse_args()
    if a.cmd == 'manifest':
        d = manifest(a.out, a.classes)
        print(f"{d['frames']} frames, {d['boxes']} boxes, {len(d['shards'])} shards; names with boxes {len(d['per_name'])}; "
              f"missing name/team {len(d['missing_name_team'])}")
    else:
        overlay(a.shard, a.sheet, a.n, a.classes)


if __name__ == '__main__':
    main()
