"""Diagnose unit false negatives on a few validation matches: score at truth cell, freshness (no same
card/owner truth within 1.5 tiles ~1 s earlier), swarm neighbours. Validation only."""
import json, math, sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np, torch
import common as C, dense_labels as D
from clasher.vision.l1_v4 import PerceptionV4

ck, nm, stride = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
st = torch.load(ck, map_location='cpu', weights_only=False); ident = st['identities']; K = len(ident)
m = PerceptionV4(56, K); m.load_state_dict(st['model']); m.cuda().eval()
g = C.HeldoutGuard(); eps = g.episodes('validation')[:nm]; g.check(eps)
stats = defaultdict(Counter); scores = defaultdict(list)
for ep in eps:
    lab = D.load(Path('/mpac/sdicks02/jobs/clasher/live-perception-20261014/labels')/f'{ep}.npz')
    px = C.Pixels(g, ep, C.load_receipt(g, ep, 'validation')); tick = lab['tick']
    for k in range(0, len(px.idx['blocks']), stride):
        ar, hu = px.block(k); i = k*16
        if i >= len(tick) or lab['row'][i] < 0: continue
        x = lambda a: torch.from_numpy(np.ascontiguousarray(a[:1])).cuda().permute(0, 3, 1, 2).float()/255
        with torch.inference_mode():
            o = m.encode(x(ar), x(hu)); o = {k2: v.float().cpu().numpy() for k2, v in o.items() if k2 != 'features'}
        dec = C.decode_frame(o, 0, st['cards'], ident, threshold=.4, offsets=True)
        heat = 1/(1+np.exp(-o['body_heatmap'][0]))
        cls, own, tx, ty, fr, ig = D.frame_objects(lab, i)
        j = int(np.searchsorted(tick, tick[i]-20)); prev = D.frame_objects(lab, j) if lab['row'][j] >= 0 else None
        preds = [(u['score'], u['x'], u['y'], (u['owner'], u['identity'])) for u in dec['units'] if u['identity'] not in C.TOWER_BODIES]
        from eval_val import match
        truth = [(float(a), float(b), (int(o_), ident[int(c)])) for c, o_, a, b in zip(cls, own, tx, ty) if c < 56]
        tp, fp, used = match(preds, truth, 1., True)
        for jx, (a, b, (o_, name)) in enumerate(truth):
            hit = jx in used
            fresh = prev is None or not any(int(pc) < 56 and ident[int(pc)] == name and int(po) == o_ and math.hypot(pa-a, pb-b) <= 1.5
                                            for pc, po, pa, pb in zip(prev[0], prev[1], prev[2], prev[3]))
            crowd = sum(1 for a2, b2, k2 in truth if k2 == (o_, name) and math.hypot(a2-a, b2-b) <= 1.0)-1
            cls_i = ident.index(name); gy, gx = min(63, int(b*2)), min(35, int(a*2))
            s = heat[o_*K+cls_i, max(0, gy-1):gy+2, max(0, gx-1):gx+2].max()
            key = 'fresh' if fresh else ('crowd' if crowd else 'single')
            stats[key]['tp' if hit else 'fn'] += 1
            if not hit: scores[key].append(float(s))
print(json.dumps({k: dict(v, recall=round(v['tp']/max(1, v['tp']+v['fn']), 3)) for k, v in stats.items()}))
for k, v in scores.items():
    v = np.asarray(v); print(k, 'FN max-score-near-truth quantiles', np.round(np.quantile(v, [.1, .25, .5, .75, .9]), 3).tolist(), 'frac>=0.2', round(float((v >= .2).mean()), 3))
