"""Round 2: unit decode variants (count head) on raw frame outputs of a checkpoint, validation frames only.

  python live/perception/r2/decode_grid.py CKPT OUT.json [--matches 8] [--frames-per-match 40] [--device cpu]
Truth = round-1 dense labels (Ghost ignored), units id x owner within 1 tile, greedy by score (eval_val.match).
"""
import argparse, json, math, sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common as C  # noqa: E402
import dense_labels as D  # noqa: E402
from eval_val import match  # noqa: E402
from scipy.ndimage import maximum_filter  # noqa: E402

LABELS = Path('/mpac/sdicks02/jobs/clasher/live-perception-20261014/labels')


def window_decode(out, b, bodies, thr, cmin, floor, radius=1):
    """Peaks as decode_frame; per peak (desc score) the expected bodies in its (2r+1)^2 window = sum of the owner's count
    map over unclaimed cells; extras = round(sum) - peaks in the window, placed on the window's highest-count cells."""
    heat = 1/(1+np.exp(-out['body_heatmap'][b])); nb = len(bodies); box = out['body_box'][b]
    n_unit = len(bodies)-sum(str(n).startswith('fx:') for n in bodies)-2
    peaks = (heat == maximum_filter(heat, size=(1, 3, 3), mode='constant')) & (heat >= thr)
    cs, ys, xs = np.nonzero(peaks)
    order = np.argsort(-heat[cs, ys, xs])
    units = []; cnt = box[2:4].copy(); h, w = heat.shape[-2:]
    pk = [(int(cs[k]), int(ys[k]), int(xs[k])) for k in order if int(cs[k]) % nb < n_unit]
    claimed = np.zeros((2, h, w), bool)
    peakcount = np.zeros((2, h, w), int)
    for c, gy, gx in pk:
        peakcount[c//nb, gy, gx] += 1
    for c, gy, gx in pk:
        o = c//nb
        units.append(dict(identity=bodies[c % nb], owner=o, x=(gx+box[0, gy, gx])/2, y=(gy+box[1, gy, gx])/2, score=float(heat[c, gy, gx])))
        y0, y1, x0, x1 = max(0, gy-radius), min(h, gy+radius+1), max(0, gx-radius), min(w, gx+radius+1)
        free = ~claimed[o, y0:y1, x0:x1]
        tot = float((np.clip(cnt[o, y0:y1, x0:x1], 0, None)*free).sum())
        n_pk = int((peakcount[o, y0:y1, x0:x1]*free).sum())
        extra = int(math.floor(tot-n_pk+1-cmin)) if tot-n_pk >= cmin else 0
        claimed[o, y0:y1, x0:x1] = True
        if extra <= 0 or bodies[c % nb] not in C.MULTI_BODY:
            continue
        cells = sorted(((float(cnt[o, y, x])-peakcount[o, y, x], y, x) for y in range(y0, y1) for x in range(x0, x1)), reverse=True)
        k = 0
        while extra > 0 and k < 3*len(cells):
            r, y, x = cells[k % len(cells)]
            if heat[c, y, x] >= floor:
                j = k//len(cells)
                ang = 2.4*k
                units.append(dict(identity=bodies[c % nb], owner=o, x=(x+box[0, y, x]+.3*j*math.cos(ang))/2,
                                  y=(y+box[1, y, x]+.3*j*math.sin(ang))/2, score=float(heat[c, gy, gx])*.95))
                extra -= 1
            k += 1
    return units


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('ckpt'); ap.add_argument('out')
    ap.add_argument('--matches', type=int, default=8); ap.add_argument('--frames-per-match', type=int, default=40)
    ap.add_argument('--device', default='cpu'); ap.add_argument('--threads', type=int, default=2)
    a = ap.parse_args(); torch.set_num_threads(a.threads)
    from clasher.vision.l1_v4 import PerceptionV4
    st = torch.load(a.ckpt, map_location='cpu', weights_only=False)
    bodies = st['identities']; cards = st['cards']
    model = PerceptionV4(len(cards), len(bodies)); model.load_state_dict(st['model']); model.eval().to(a.device)
    guard = C.HeldoutGuard(); eps = guard.episodes('validation')[::max(1, 64//a.matches)][:a.matches]; guard.check(eps)
    variants = {'peaks': None, 'cell(.2) multi': ('cell', .2), 'cell(.2) all': ('cell-all', .2)}
    for cmin in (.5, .7, .9):
        for floor in (.2, .4):
            variants[f'win r1 cmin{cmin} f{floor}'] = ('win', cmin, floor)
    variants['win r2 cmin.7 f.2'] = ('win2', .7, .2)
    tot = {k: [0, 0, 0] for k in variants}; tot_s = {k: [0, 0, 0] for k in variants}
    for ep in eps:
        lab = D.load(LABELS/f'{ep}.npz'); px = C.Pixels(guard, ep, C.load_receipt(guard, ep, 'validation'))
        idx = [i for i in np.linspace(0, px.n-1, a.frames_per_match).astype(int) if lab['row'][i] >= 0]
        for i in idx:
            k = i//px.bs; ar, hu = px.block(k)
            t = lambda x: torch.from_numpy(np.ascontiguousarray(x)).permute(2, 0, 1)[None].float().div(255).to(a.device)
            with torch.no_grad():
                o = model.encode(t(ar[i-k*px.bs]), t(hu[i-k*px.bs]))
            out = {kk: v.float().cpu().numpy() for kk, v in o.items() if kk != 'features'}
            cls, own, x, y, frac, ign = D.frame_objects(lab, i)
            tr = [(float(xx), float(yy), (int(ow), bodies[int(c)])) for c, ow, xx, yy in zip(cls, own, x, y) if int(c) < 56]
            swarm = {'SkeletonArmy', 'MinionHorde', 'GoblinGang', 'Minions', 'Goblins', 'Skeletons', 'Bats', 'Barbarians', 'Wallbreakers'}
            for name, v in variants.items():
                if v is None:
                    us = C.decode_frame(out, 0, cards, bodies, threshold=.4, offsets=True, counts=False)['units']
                elif v[0] in ('cell', 'cell-all'):
                    us = [u for u in C.decode_frame(out, 0, cards, bodies, threshold=.4, offsets=True, counts=True if v[0] == 'cell' else 'all',
                                                    count_floor=v[1])['units'] if u['score'] >= .4]
                else:
                    us = window_decode(out, 0, bodies, .4, v[1], v[2], radius=2 if v[0] == 'win2' else 1)
                pr = [(u['score'], u['x'], u['y'], (u['owner'], u['identity'])) for u in us if u['identity'] not in C.TOWER_BODIES]
                tp, fp, used = match(pr, tr, 1., True)
                tot[name][0] += len(tp); tot[name][1] += len(fp); tot[name][2] += len(tr)-len(used)
                trs = [t_ for t_ in tr if t_[2][1] in swarm]; prs = [p_ for p_ in pr if p_[3][1] in swarm]
                tp, fp, used = match(prs, trs, 1., True)
                tot_s[name][0] += len(tp); tot_s[name][1] += len(fp); tot_s[name][2] += len(trs)-len(used)
    f = lambda tp, fp, fn: dict(P=round(tp/max(1, tp+fp), 4), R=round(tp/max(1, tp+fn), 4), F1=round(2*tp/max(1, 2*tp+fp+fn), 4))
    res = {k: dict(all=f(*tot[k]), swarm=f(*tot_s[k])) for k in variants}
    Path(a.out).write_text(json.dumps(dict(ckpt=a.ckpt, matches=eps, res=res), indent=1))
    for k, v in res.items():
        print(k, v)


if __name__ == '__main__':
    main()
