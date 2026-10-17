#!/usr/bin/env python3
"""Side-by-side QA sheets: old diff boxes (red, left) vs SAM boxes (green, right).

Box numbers k follow the QA index.json `boxes` order (= objects with a non-null
diff box, in label order).  Objects with no old box get k = 'n<j>'.
Each sheet row is one object cluster crop: [old | sam], upscaled.
"""
import argparse
import json
import os

import cv2
import numpy as np


def clusters(items, gap=260):
    """Group boxes whose centres are within gap px (single linkage)."""
    n = len(items)
    par = list(range(n))

    def f(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    cs = [((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for b in (it['union'] for it in items)]
    for i in range(n):
        for j in range(i + 1, n):
            if abs(cs[i][0] - cs[j][0]) < gap and abs(cs[i][1] - cs[j][1]) < gap:
                par[f(i)] = f(j)
    g = {}
    for i in range(n):
        g.setdefault(f(i), []).append(items[i])
    return list(g.values())


def draw(panel, items, key, color, x0, y0, s):
    for it in items:
        b = it[key]
        if not b:
            continue
        p1 = (int((b[0] - x0) * s), int((b[1] - y0) * s))
        p2 = (int((b[2] - x0) * s), int((b[3] - y0) * s))
        cv2.rectangle(panel, p1, p2, color, 2)
        t = str(it['k'])
        cv2.putText(panel, t, (p1[0] + 2, p1[1] + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 4)
        cv2.putText(panel, t, (p1[0] + 2, p1[1] + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1)
    for it in items:  # anchor dots
        ax, ay = it['anchor']
        cv2.circle(panel, (int((ax - x0) * s), int((ay - y0) * s)), 3, (255, 255, 0), -1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--index', required=True, help='QA sheets index.json (json + boxes order)')
    ap.add_argument('--sam', required=True, help='sam_boxes.py output')
    ap.add_argument('--out', required=True)
    ap.add_argument('--root-map', nargs=2, metavar=('FROM', 'TO'))
    ap.add_argument('--margin', type=int, default=50)
    ap.add_argument('--min-side', type=int, default=420)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    def local(p):
        return a.root_map[1] + p[len(a.root_map[0]):] if a.root_map and p.startswith(a.root_map[0]) else p

    sam = json.load(open(a.sam))
    idx = json.load(open(a.index))
    out_idx = []
    for e in idx:
        lp = e['json']
        L = json.load(open(local(lp)))
        img = cv2.imread(os.path.join(os.path.dirname(local(lp)), L['frame']))
        H, W = img.shape[:2]
        sb = sam['boxes'].get(lp, {})
        sm = sam['meta'].get(lp, {}).get('objects', {})
        items, k, extra = [], 0, 0
        for o in L['objects']:
            oid = str(o['object_id'])
            need = o['kind'] in ('unit', 'building') and o['phase'] != 'death'
            if o['box'] is not None:
                kk = k
                k += 1
            elif need:
                kk = f'n{extra}'
                extra += 1
            else:
                continue
            new = sb.get(oid) if need else None
            bs = [b for b in (o['box'], new) if b] or [[o['anchor_px'][0] - 30, o['anchor_px'][1] - 60,
                                                         o['anchor_px'][0] + 30, o['anchor_px'][1]]]
            u = [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]
            items.append({'k': kk, 'object_id': o['object_id'], 'class': o['class_name'], 'team': o['team'],
                          'phase': o['phase'], 'old': o['box'], 'old_flags': o['box_flags'], 'sam': new,
                          'sam_flags': sm.get(oid, {}).get('flags'), 'sam_score': sm.get(oid, {}).get('score'),
                          'anchor': o['anchor_px'], 'union': u})
        assert sum(1 for it in items if isinstance(it['k'], int)) == len(e['boxes'])
        rows = []
        for grp in clusters(items):
            x0 = max(0, int(min(it['union'][0] for it in grp)) - a.margin)
            y0 = max(0, int(min(it['union'][1] for it in grp)) - a.margin)
            x1 = min(W, int(max(it['union'][2] for it in grp)) + a.margin)
            y1 = min(H, int(max(it['union'][3] for it in grp)) + a.margin)
            s = max(1.0, a.min_side / max(1, min(x1 - x0, y1 - y0)))
            s = min(s, 900 / max(1, x1 - x0))
            crop = cv2.resize(img[y0:y1, x0:x1], None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
            left, right = crop.copy(), crop.copy()
            draw(left, grp, 'old', (0, 0, 255), x0, y0, s)
            draw(right, grp, 'sam', (0, 255, 0), x0, y0, s)
            sep = np.full((crop.shape[0], 8, 3), 255, np.uint8)
            rows.append(np.hstack([left, sep, right]))
        if not rows:  # no unit/building rows with phase != death: show the arena small
            rows.append(cv2.resize(img[180:2100], None, fx=0.4, fy=0.4, interpolation=cv2.INTER_AREA))
        wmax = max(max(r.shape[1] for r in rows), 560)
        rows = [np.pad(r, ((0, 8), (0, wmax - r.shape[1]), (0, 0)), constant_values=255) for r in rows]
        head = np.full((34, wmax, 3), 40, np.uint8)
        cv2.putText(head, f"#{e['i']} {L['card']} t{L['tick']}  left RED=old diff  right GREEN=SAM", (6, 23),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        sheet = np.vstack([head] + rows)
        name = f"sam-{e['i']:02d}.jpg"
        cv2.imwrite(os.path.join(a.out, name), sheet, [cv2.IMWRITE_JPEG_QUALITY, 92])
        for it in items:
            it.pop('union')
        out_idx.append({'i': e['i'], 'id': e['id'], 'json': lp, 'sheet': name,
                        'sam_ms': sam['meta'].get(lp, {}).get('ms'), 'boxes': items})
    json.dump(out_idx, open(os.path.join(a.out, 'index.json'), 'w'), indent=1)
    print('wrote', len(out_idx), 'sheets to', a.out)


if __name__ == '__main__':
    main()
