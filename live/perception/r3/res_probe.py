"""Round 3: does capture resolution limit small units? Renderer validation frames (truth known), arena input degraded to
match each capture path, per-card recall/precision (identity x owner, <=1 tile) at a threshold.

Effective source px per arena-cache px: renderer 2.41, official native 1020x1816 capture 2.06 (factor .85), official
720x1280 capture 1.45 (factor .60). Degrade = INTER_AREA down by the factor, bilinear back up.

  python r3/res_probe.py --ckpt A.pt [--ckpt B.pt] --out OUT.json [--matches 16] [--thr .5]
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common as C  # noqa: E402
import dense_labels as D  # noqa: E402
from finetune import Blocks, flat  # noqa: E402
from eval_val import match  # noqa: E402

FACTORS = (1.0, .85, .6)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--ckpt', action='append', required=True); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--matches', type=int, default=16); p.add_argument('--thr', type=float, default=.5)
    p.add_argument('--labels', type=Path, default=Path('/mpac/sdicks02/jobs/clasher/live-perception-20261014/labels'))
    a = p.parse_args(); torch.set_num_threads(4)
    guard = C.HeldoutGuard(); val = guard.episodes('validation')[:a.matches]; guard.check(val)
    fixed = []
    for ep in val:
        lab = D.load(a.labels/f'{ep}.npz'); n = len(lab['row'])
        for k in range(0, n//16, 6):
            ok = [i for i in range(k*16, min(n, k*16+16)) if lab['row'][i] >= 0]
            if len(ok) >= 4:
                fixed.append((ep, k, ok[::max(1, len(ok)//4)][:4]))
    loader = torch.utils.data.DataLoader(Blocks(val, a.labels, 'validation', 0, 0, fixed=fixed), batch_size=8, num_workers=4)
    from clasher.vision.l1_v4 import PerceptionV4
    res = {}
    for ck in a.ckpt:
        st = torch.load(ck, map_location='cpu', weights_only=False)
        model = PerceptionV4(len(st['cards']), len(st['identities'])); model.load_state_dict(st['model']); model.cuda().eval()
        ids = st['identities']
        tot = {f: defaultdict(lambda: [0, 0, 0]) for f in FACTORS}  # card -> tp, fn, fp
        for b in loader:
            b = flat(b, 'cuda')
            arena = b['arena'].permute(0, 3, 1, 2).float()/255; hud = b['hud'].permute(0, 3, 1, 2).float()/255
            P = b['pos'].cpu().numpy()
            for f in FACTORS:
                x = arena if f == 1. else F.interpolate(F.interpolate(arena, scale_factor=f, mode='area'), size=arena.shape[-2:],
                                                        mode='bilinear', align_corners=False)
                with torch.no_grad(), torch.autocast('cuda', dtype=torch.bfloat16):
                    out = model.encode(x, hud)
                o = {k: out[k].float().cpu().numpy() for k in ('body_heatmap', 'body_box', 'body_hp', 'body_hp_visible', 'hud_cards',
                                                             'elixir_digit', 'elixir_fraction', 'clock_seconds', 'phase')}
                for i in range(len(P)):
                    if bool(b['stale'][i]):
                        continue
                    dec = C.decode_frame(o, i, ids[:56], ids, threshold=a.thr, offsets=True, counts=False)
                    pv = P[i][P[i][:, 5] > 0]
                    tr = [(x_, y_, (int(ow), ids[int(c)])) for c, ow, x_, y_, fr, v in pv if int(c) < 56]
                    pr = [(u['score'], u['x'], u['y'], (u['owner'], u['identity'])) for u in dec['units'] if u['identity'] not in C.TOWER_BODIES]
                    tp, fp, used = match(pr, tr, 1., True)
                    for j, (_, _, (_, card)) in enumerate(tr):
                        tot[f][card][0 if j in used else 1] += 1
                    for k in fp:
                        tot[f][pr[k][3][1]][2] += 1
        res[ck] = {str(f): {c: v for c, v in sorted(t.items())} for f, t in tot.items()}
        for f in FACTORS:
            t = tot[f]; tp = sum(v[0] for v in t.values()); fn = sum(v[1] for v in t.values()); fp = sum(v[2] for v in t.values())
            sm = {c: round(t[c][0]/max(1, t[c][0]+t[c][1]), 3) for c in ('Archers', 'Minions', 'Knight', 'Giant', 'MiniPekka', 'Musketeer',
                                                                         'Goblins', 'Skeletons', 'SkeletonArmy', 'Bats')}
            print(Path(ck).name, f, 'P', round(tp/max(1, tp+fp), 3), 'R', round(tp/max(1, tp+fn), 3), sm, flush=True)
    a.out.write_text(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
