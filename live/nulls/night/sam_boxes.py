#!/usr/bin/env python3
"""SAM2 box labeller for Null's night-label frames.

For every unit/building object (phase != death) prompt SAM2 with
  - a positive point at the expected body centre (ground: anchor_y - 0.45 h_prior;
    air: anchor_y - 0.5 h_prior - lift),
  - a box prompt = per-class prior box around the anchor (padded),
  - negative points at other objects' body centres within --neg-radius px,
and take the tight bbox of the best mask.

SAM2 resizes its input to 1024x1024, which would shrink a 1080x2280 frame to
~0.45x vertically (a Bat ~15 px).  So objects are grouped into square crops of
--crop px (default 384, upsampled ~2.7x) and each crop is encoded once.

Output JSON: {"boxes": {label_json: {object_id: [x1,y1,x2,y2] | null}},
              "meta": {label_json: {ms, n_crops, objects: {object_id: diag}}}, ...}
"""
import argparse
import glob
import json
import os
import sys
import time

import cv2
import numpy as np

GROUND_FALLBACK = (70.0, 90.0)
AIR_LIFT_FALLBACK = 45.0
PRIOR_MIN_N = 20


def load_air(classes_json):
    d = json.load(open(classes_json))
    return {c['name'] for c in d['names'] if c.get('air')}


def compute_priors(globs):
    """Median w/h/bottom offset of clean diff boxes (empty box_flags) per class."""
    acc = {}
    for g in globs:
        for f in glob.glob(g):
            try:
                L = json.load(open(f))
            except Exception:
                continue
            if not isinstance(L, dict):
                continue
            for o in L.get('objects', []):
                if (o['kind'] in ('unit', 'building') and o.get('box') and not o.get('box_flags')
                        and o['phase'] != 'death' and o.get('class_name')):
                    x1, y1, x2, y2 = o['box']
                    acc.setdefault(o['class_name'], []).append((x2 - x1, y2 - y1, y2 - o['anchor_px'][1]))
    out = {}
    for c, v in acc.items():
        a = np.array(v, float)
        out[c] = {'n': len(v), 'w': float(np.median(a[:, 0])), 'h': float(np.median(a[:, 1])),
                  'bottom_off': float(np.median(a[:, 2]))}
    return out


class Prior:
    def __init__(self, priors, air):
        self.p, self.air = priors, air

    def get(self, cls):
        """-> (w, h, lift, is_air, source, bottom_off). lift = px from anchor up to the sprite bottom (air only)."""
        is_air = cls in self.air
        q = self.p.get(cls)
        if q and q['n'] >= PRIOR_MIN_N:
            w = float(np.clip(q['w'], 24, 220))
            h = float(np.clip(q['h'], 24, 240))
            lift = max(0.0, -q['bottom_off']) if is_air else 0.0
            if is_air and lift < 10:
                lift = AIR_LIFT_FALLBACK
            return w, h, lift, is_air, 'prior', float(np.clip(q['bottom_off'], 0, 0.45 * h))
        w, h = GROUND_FALLBACK
        return w, h, (AIR_LIFT_FALLBACK if is_air else 0.0), is_air, 'fallback', 0.1 * h


def prompts_for(objs, prior):
    """Per target object: centre point and prior box (full-frame px)."""
    out = []
    for o in objs:
        ax, ay = o['anchor_px']
        w, h, lift, is_air, src, boff = prior.get(o.get('class_name'))
        if is_air:
            cy = ay - 0.5 * h - lift
            bottom = ay - lift
        elif o['kind'] == 'building':
            bottom = ay + boff  # anchor = footprint centre; aim at the prior box centre
            cy = bottom - 0.5 * h
        else:
            cy = ay - 0.45 * h
            bottom = ay + boff
        box = [ax - w / 2, bottom - h, ax + w / 2, bottom]
        out.append({'o': o, 'pt': (ax, cy), 'box': box, 'w': w, 'h': h, 'air': is_air, 'src': src})
    return out


def tower_points(L):
    cal = L.get('arena_calib') or {}
    return [tuple(v) for v in cal.values()]


def cluster(prs, crop, img_w, img_h):
    """Greedy grouping of prompt boxes into square crop windows."""
    left = list(range(len(prs)))
    groups = []
    while left:
        i = left.pop(0)
        bx = list(prs[i]['box'])
        mem = [i]
        for j in list(left):
            b = prs[j]['box']
            u = [min(bx[0], b[0]), min(bx[1], b[1]), max(bx[2], b[2]), max(bx[3], b[3])]
            if u[2] - u[0] <= crop * 0.75 and u[3] - u[1] <= crop * 0.75:
                bx = u
                mem.append(j)
                left.remove(j)
        # window must cover every member's padded box; grow past crop if one object is larger
        side = max(crop, (bx[2] - bx[0]) * 1.4, (bx[3] - bx[1]) * 1.4)
        cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
        x0 = int(round(np.clip(cx - side / 2, 0, max(0, img_w - side))))
        y0 = int(round(np.clip(cy - side / 2, 0, max(0, img_h - side))))
        groups.append((mem, (x0, y0, int(min(img_w, x0 + side)), int(min(img_h, y0 + side)))))
    return groups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('labels', nargs='*', help='label JSON paths')
    ap.add_argument('--list', help='file with one label JSON per line, or an index.json with "json" keys')
    ap.add_argument('--out', required=True)
    ap.add_argument('--priors', help='class_priors.json (computed from --prior-glob if absent)')
    ap.add_argument('--prior-glob', action='append', default=[])
    ap.add_argument('--classes', required=True, help='yolo_synth classes.json (air flags)')
    ap.add_argument('--ckpt', required=True)
    ap.add_argument('--cfg', default='configs/sam2.1/sam2.1_hiera_b+.yaml')
    ap.add_argument('--crop', type=int, default=384)
    ap.add_argument('--pad', type=float, default=0.25, help='prior-box padding fraction for the box prompt')
    ap.add_argument('--clip-pad', type=float, default=0.6,
                    help='mask kept only inside the prior box grown by this fraction of w/h per side (0 = off)')
    ap.add_argument('--no-component', dest='component', action='store_false',
                    help='keep all mask pixels instead of the component at the point')
    ap.add_argument('--neg-radius', type=float, default=120.0)
    ap.add_argument('--tower-neg-radius', type=float, default=220.0, help='radius for tower-centre negatives')
    ap.add_argument('--no-neg', action='store_true')
    ap.add_argument('--root-map', nargs=2, metavar=('FROM', 'TO'),
                    help='rewrite label path prefix FROM->TO when reading (output keys keep original paths)')
    ap.add_argument('--device', default='cuda')
    a = ap.parse_args()

    labels = list(a.labels)
    if a.list:
        if a.list.endswith('.json'):
            labels += [e['json'] for e in json.load(open(a.list))]
        else:
            labels += [l.strip() for l in open(a.list) if l.strip()]

    def local(p):
        return a.root_map[1] + p[len(a.root_map[0]):] if a.root_map and p.startswith(a.root_map[0]) else p

    if a.priors and os.path.exists(a.priors):
        priors = json.load(open(a.priors))
    else:
        priors = compute_priors(a.prior_glob)
        if a.priors:
            json.dump(priors, open(a.priors, 'w'), indent=1)
    prior = Prior(priors, load_air(a.classes))

    import torch
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    torch.backends.cuda.matmul.allow_tf32 = True
    model = build_sam2(a.cfg, a.ckpt, device=a.device)
    pred = SAM2ImagePredictor(model)

    boxes, meta = {}, {}
    t_all = time.time()
    for li, lp in enumerate(labels):
        t0 = time.time()
        L = json.load(open(local(lp)))
        if not isinstance(L, dict) or not L.get('frame'):
            continue  # chunk manifests etc.
        img_path = os.path.join(os.path.dirname(local(lp)), L['frame'])
        img = cv2.imread(img_path)[:, :, ::-1]
        H, W = img.shape[:2]
        targets = [o for o in L['objects'] if o['kind'] in ('unit', 'building') and o['phase'] != 'death']
        prs = prompts_for(targets, prior)
        others = [(p['o']['object_id'], p['pt']) for p in prs] + [(None, t) for t in tower_points(L)]
        fb, fm = {}, {}
        groups = cluster(prs, a.crop, W, H)
        for mem, (x0, y0, x1, y1) in groups:
            crop = np.ascontiguousarray(img[y0:y1, x0:x1])
            with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                pred.set_image(crop)
                pts, lbs, bxs = [], [], []
                for i in mem:
                    p = prs[i]
                    pl = [p['pt']]
                    ll = [1]
                    if not a.no_neg:
                        for oid, q in others:
                            if oid == p['o']['object_id']:
                                continue
                            rad = a.tower_neg_radius if oid is None else a.neg_radius
                            if np.hypot(q[0] - p['pt'][0], q[1] - p['pt'][1]) <= rad:
                                pl.append(q)
                                ll.append(0)
                    pts.append(pl)
                    lbs.append(ll)
                    b = p['box']
                    pw, ph = (b[2] - b[0]) * a.pad, (b[3] - b[1]) * a.pad
                    bxs.append([b[0] - pw, b[1] - ph, b[2] + pw, b[3] + ph])
                P = max(len(x) for x in pts)
                pc = np.zeros((len(mem), P, 2), np.float32)
                pll = -np.ones((len(mem), P), np.int32)
                for r, (pl, ll) in enumerate(zip(pts, lbs)):
                    pc[r, :len(pl)] = np.array(pl) - (x0, y0)
                    pll[r, :len(ll)] = ll
                bb = np.array(bxs, np.float32) - (x0, y0, x0, y0)
                masks, scores, _ = pred.predict(point_coords=pc, point_labels=pll, box=bb,
                                                multimask_output=True, normalize_coords=True)
            if masks.ndim == 3:
                masks, scores = masks[None], scores[None]
            for r, i in enumerate(mem):
                p = prs[i]
                oid = str(p['o']['object_id'])
                prior_area = p['w'] * p['h']
                px, py = p['pt'][0] - x0, p['pt'][1] - y0
                cand = []
                # clip window: prior box grown by --clip-pad of its w/h on every side (crop coords)
                b = p['box']
                cw, ch = (b[2] - b[0]) * a.clip_pad, (b[3] - b[1]) * a.clip_pad
                wx0, wy0 = int(max(0, b[0] - cw - x0)), int(max(0, b[1] - ch - y0))
                wx1, wy1 = int(min(x1 - x0, b[2] + cw - x0)), int(min(y1 - y0, b[3] + ch - y0))
                for m in range(masks.shape[1]):
                    raw = masks[r, m] > 0
                    raw_px = int(raw.sum())
                    mk = np.zeros_like(raw)
                    if a.clip_pad > 0:
                        mk[wy0:wy1, wx0:wx1] = raw[wy0:wy1, wx0:wx1]
                    else:
                        mk = raw
                    if a.component and mk.any():
                        n, cc, st, _ = cv2.connectedComponentsWithStats(mk.astype(np.uint8), connectivity=8)
                        ix, iy = int(np.clip(px, 0, mk.shape[1] - 1)), int(np.clip(py, 0, mk.shape[0] - 1))
                        keep = cc[iy, ix]
                        if keep == 0:  # point off-mask: nearest component to the point
                            ys, xs = np.nonzero(mk)
                            j = int(np.argmin((xs - px) ** 2 + (ys - py) ** 2))
                            keep = cc[ys[j], xs[j]]
                        big = st[keep, cv2.CC_STAT_AREA]
                        # keep the chosen component plus any >= 25% of its size (detached wings/weapons)
                        sel = [keep] + [c for c in range(1, n) if c != keep and st[c, cv2.CC_STAT_AREA] >= 0.25 * big]
                        mk = np.isin(cc, sel)
                    ys, xs = np.nonzero(mk)
                    if len(xs) == 0:
                        cand.append((-9.0, m, None, 0, raw_px))
                        continue
                    bx = [int(xs.min()) + x0, int(ys.min()) + y0, int(xs.max()) + 1 + x0, int(ys.max()) + 1 + y0]
                    area = (bx[2] - bx[0]) * (bx[3] - bx[1])
                    s = float(scores[r, m])
                    hit = mk[int(np.clip(py, 0, mk.shape[0] - 1)), int(np.clip(px, 0, mk.shape[1] - 1))]
                    # prefer masks covering the point, with box area near the prior, and little spill outside the window
                    spill = 1.0 - mk.sum() / max(1, raw_px)
                    pen = (0.0 if hit else 0.15) + 0.15 * abs(np.log(max(area, 1) / prior_area)) + 0.3 * spill
                    cand.append((s - pen, m, bx, int(mk.sum()), raw_px))
                cand.sort(key=lambda c: -c[0])
                best = cand[0]
                bx = best[2]
                flags = []
                if bx is None:
                    flags.append('empty')
                else:
                    area = (bx[2] - bx[0]) * (bx[3] - bx[1])
                    if area > 3 * prior_area:
                        flags.append('gt3x_prior')
                    if area > 0.5 * (x1 - x0) * (y1 - y0):
                        flags.append('huge')
                    if area < 0.1 * prior_area:
                        flags.append('tiny')
                fb[oid] = bx
                if bx is not None and best[4] > 1.5 * max(1, best[3]):
                    flags.append('clipped_spill')
                fm[oid] = {'score': round(float(scores[r, best[1]]), 4), 'mask_px': best[3], 'raw_px': best[4],
                           'flags': flags,
                           'prior': [round(v, 1) for v in p['box']], 'prior_src': p['src'],
                           'pt': [round(v, 1) for v in p['pt']], 'n_neg': sum(1 for v in lbs[r] if v == 0),
                           'crop': [x0, y0, x1, y1], 'class': p['o'].get('class_name')}
        torch.cuda.synchronize()
        ms = (time.time() - t0) * 1000
        boxes[lp] = fb
        meta[lp] = {'ms': round(ms, 1), 'n_obj': len(prs), 'n_crops': len(groups), 'objects': fm}
        if li % 20 == 0:
            print(f'{li}/{len(labels)} {ms:.0f} ms obj={len(prs)} crops={len(groups)}', flush=True)
    import torch as _t
    out = {'boxes': boxes, 'meta': meta,
           'run': {'n_frames': len(labels), 'total_s': round(time.time() - t_all, 2),
                   'max_mem_alloc_mb': round(_t.cuda.max_memory_allocated() / 2**20, 1),
                   'max_mem_reserved_mb': round(_t.cuda.max_memory_reserved() / 2**20, 1),
                   'cfg': a.cfg, 'ckpt': os.path.basename(a.ckpt), 'crop': a.crop, 'pad': a.pad, 'clip_pad': a.clip_pad, 'component': a.component,
                   'neg_radius': None if a.no_neg else a.neg_radius, 'torch': _t.__version__,
                   'cuda': _t.version.cuda, 'gpu': _t.cuda.get_device_name(0)}}
    json.dump(out, open(a.out, 'w'))
    print(json.dumps(out['run']))


if __name__ == '__main__':
    sys.exit(main())
