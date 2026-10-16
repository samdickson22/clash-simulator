"""Official labelled frames (box_px in the capture) -> KataCR training samples: 568x896 arena crop JPEG + `name_idx cx cy w h belong`
(normalised) txt, plus a list file of `image label` pairs for train_cr.py --real.

Crop box (720x1280 capture px; scaled for other capture sizes): x 42.2..674.2, y 31.3..1019.3, which maps our calibrated tile grid
(live/loop/canvas.py) onto KataCR's grid xyxy (6, 64, 562, 864). Only `complete` frames are converted; units of names outside KataCR's
unit_list (e.g. 'unknown' / OOV) are dropped from the txt, so use frames whose OOV units are rare.

  python official_to_cr.py LABEL_DIR INDEX_JSON OUT_DIR LIST_FILE --katacr-src SRC [--exclude-battles ...]
"""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

CROP = (42.2, 31.3, 674.2, 1019.3)
WK, HK = 568, 896


def main():
    p = argparse.ArgumentParser()
    p.add_argument('labels', type=Path); p.add_argument('index', type=Path); p.add_argument('out', type=Path); p.add_argument('list', type=Path)
    p.add_argument('--katacr-src', required=True); p.add_argument('--require-complete', action='store_true')
    a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'r3')); sys.path.insert(0, a.katacr_src)
    from katacr.constants.label_list import unit2idx
    from yolo_labels import BODY, CARD
    ix = {x['id']: x for x in json.loads(a.index.read_text())}
    pairs, n_units, dropped = [], 0, {}
    for f in sorted(a.labels.glob('*.json')):
        lab = json.loads(f.read_text())
        if lab.get('exclude') or (a.require_complete and not lab.get('complete')):
            continue
        if any(u.get('owner') not in ('us', 'opp') for u in lab['units']):
            # an unsettled owner ('unsure') can be neither a team label nor dropped (it would become background): skip the frame
            dropped['frames-owner-unsure'] = dropped.get('frames-owner-unsure', 0)+1; continue
        src = ix[lab['id']]['source']; im = cv2.imread(src); h, w = im.shape[:2]
        x0, y0, x1, y1 = CROP[0]*w/720, CROP[1]*h/1280, CROP[2]*w/720, CROP[3]*h/1280
        sx, sy = WK/(x1-x0), HK/(y1-y0)
        M = np.array([[sx, 0, -x0*sx], [0, sy, -y0*sy]])
        crop = cv2.warpAffine(im, M, (WK, HK), flags=cv2.INTER_AREA)
        rows = []
        for u in lab['units']:
            name = BODY.get(u.get('body')) or CARD.get(u['card']) or u.get('katacr') or \
                (u['card'][4:] if u['card'].startswith('OOV:') else None)
            if name not in unit2idx or not u.get('box_px'):
                dropped[u['card']] = dropped.get(u['card'], 0)+1; continue
            bx1, by1, bx2, by2 = u['box_px']
            cx1, cy1, cx2, cy2 = (bx1-x0)*sx, (by1-y0)*sy, (bx2-x0)*sx, (by2-y0)*sy
            cx1, cy1, cx2, cy2 = max(0, cx1), max(0, cy1), min(WK, cx2), min(HK, cy2)
            if cx2-cx1 < 3 or cy2-cy1 < 3:
                continue
            rows.append(f"{unit2idx[name]} {(cx1+cx2)/2/WK:.6f} {(cy1+cy2)/2/HK:.6f} {(cx2-cx1)/WK:.6f} {(cy2-cy1)/HK:.6f} "
                        f"{0 if u['owner'] == 'us' else 1}")
        ip, lp = a.out/f"{lab['id']}.jpg", a.out/f"{lab['id']}.txt"
        cv2.imwrite(str(ip), crop, [cv2.IMWRITE_JPEG_QUALITY, 95]); lp.write_text('\n'.join(rows)+('\n' if rows else ''))
        pairs.append(f'{ip} {lp}'); n_units += len(rows)
    a.list.write_text('\n'.join(pairs)+'\n')
    print('frames', len(pairs), 'units', n_units, 'dropped', dropped)


if __name__ == '__main__':
    main()
