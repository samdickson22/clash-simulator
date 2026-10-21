"""PREREG G1 imitation / calibration admission report for a pretrain-v1 BC checkpoint (full DEV, natural frequency).

    python -m bot.pretrain_v1.admit_bc --store STORE --ckpt best-calibrated.pt --out admit.json [--device cuda]

Per DEV actor row (retained rows carry inverse-probability weights w_ipw; busy / forced / ambiguous / window rows
have no actor loss and are excluded): model joint NLL (gate/slot + 1[play] tile) and the fixed training-frequency
baseline's (constant hazard, card frequency over legal slots, per-card tile frequency over legal tiles, add-one).
Criteria reported (PREREG section 6, items 1-2; items 3-5 come from the parity audit / Mac benchmark / soak):
  1. joint NLL model - baseline, paired physical-game cluster bootstrap (10,000 draws, PCG64 2026102020, both seats
     together), broad DEV and Hog-cycle DEV: 95% upper bound < 0
  2. gate ECE <= .03, gate Brier <= baseline Brier, plays ratio (expected / actual plays) in [.85, 1.15]; the
     hazard-inversion check across polling intervals needs varied cadence and is not applicable to the 5-tick store
  coverage: compatible DEV plays per target card (>= 100) and per-card top-1 / tile metrics.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import torch

from . import featurize as F
from .policy import load
from .train_bc import Store, losses, to_torch

TARGET = ('Skeletons', 'Musketeer', 'IceGolem', 'Cannon', 'Fireball', 'Zap', 'IceSpirit', 'HogRider')


def baseline_rows(store, tr, idx):
    x = store.x
    w = x['w_ipw'][tr]*x['actor'][tr]
    play = (x['gate'][tr] == 1) & (x['actor'][tr] == 1)
    hazard = float((w*play).sum()/w.sum())
    pi = tr[play]
    cards = x['hand'][pi, x['slot'][pi].astype(int), F.H_CARD]
    cat = F.catalog()
    cf = np.bincount(cards, minlength=cat.n_cards).astype(float) + 1
    tf = np.ones((cat.n_cards, F.NTILE))
    np.add.at(tf, (cards, x['tile'][pi].astype(int)), 1)
    nll = np.zeros(len(idx))
    for k, i in enumerate(idx):
        ok = x['slot_ok'][i]
        if x['gate'][i] == 1:
            s = int(x['slot'][i])
            c = x['hand'][i, :4, F.H_CARD]
            pc = cf[c]*ok
            v = -math.log(hazard) - math.log(pc[s]/pc.sum())
            m = F.tile_mask(int(x['hand'][i, s, F.H_PLACE]), tuple(bool(a) for a in x['alive'][i]))
            pt = tf[c[s]]*m
            nll[k] = v - math.log(pt[int(x['tile'][i])]/pt.sum())
        else:
            nll[k] = -math.log(1 - hazard) if ok.any() else 0.0
    return nll, hazard


def cluster_ci(delta_w, w, groups, draws=10000, seed=2026102020):
    """Ratio estimator sum(w*d)/sum(w), resampling physical games (PCG64), -> (point, lo95, hi95)."""
    uniq, inv = np.unique(groups, return_inverse=True)
    num = np.bincount(inv, weights=delta_w, minlength=len(uniq))
    den = np.bincount(inv, weights=w, minlength=len(uniq))
    rng = np.random.Generator(np.random.PCG64(seed))
    pick = rng.integers(0, len(uniq), size=(draws, len(uniq)))
    stats = num[pick].sum(1)/den[pick].sum(1)
    return float(num.sum()/den.sum()), float(np.quantile(stats, .025)), float(np.quantile(stats, .975)), len(uniq)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--store', required=True)
    ap.add_argument('--ckpt', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--device', default='cuda' if torch.cuda.is_available() else 'cpu')
    ap.add_argument('--split', default='dev')
    a = ap.parse_args(argv)
    torch.set_num_threads(8)
    store = Store(a.store)
    model, ck = load(a.ckpt, map_location=a.device)
    model.to(a.device)
    tr = np.nonzero(store.split == 0)[0]
    code = {'train': 0, 'dev': 1, 'final': 2}[a.split]
    dv = np.nonzero((store.split == code) & (store.x['actor'] == 1))[0]
    joint, ppl, ptrue, top1, t1, tw1, card_of = [], [], [], [], [], [], []
    with torch.inference_mode():
        for i in range(0, len(dv), 2048):
            idx = dv[i:i + 2048]
            nb = store.batch(idx)
            b = to_torch(nb, a.device)
            L = losses(model, b)
            joint.append(L['joint'].cpu().numpy())
            p = L['logp'].exp()
            ppl.append((1 - p[:, 0]).cpu().numpy())
            ptrue.append(L['play'].cpu().numpy())
            pred = L['logp'][:, 1:].argmax(1)
            top1.append((pred == b['slot'].long()).cpu().numpy())
            play = L['play']
            tt = np.full(len(idx), -1)
            tw = np.full(len(idx), -1)
            if play.any():
                pi = play.nonzero().squeeze(1)
                out = L['out']
                z = model.tile_logits(out['cls'][pi], out['hand'][pi], b['slot'][pi].long(), b['tile_ok'][pi])
                tp, tt_ = z.argmax(1), b['tile'][pi].long()
                hit = (tp == tt_).cpu().numpy()
                near = (((tp % F.W - tt_ % F.W).abs() <= 1) & ((tp//F.W - tt_//F.W).abs() <= 1)).cpu().numpy()
                tt[pi.cpu().numpy()] = hit
                tw[pi.cpu().numpy()] = near
            t1.append(tt)
            tw1.append(tw)
            card_of.append(np.where(nb['gate'] == 1, nb['hand'][np.arange(len(idx)), np.maximum(nb['slot'], 0), F.H_CARD], 0))
    joint, ppl, ptrue = np.concatenate(joint), np.concatenate(ppl), np.concatenate(ptrue).astype(float)
    top1, t1, tw1, card_of = np.concatenate(top1), np.concatenate(t1), np.concatenate(tw1), np.concatenate(card_of)
    base, hazard = baseline_rows(store, tr, dv)
    w = store.x['w_ipw'][dv].astype(float)
    phys = store.phys[dv]
    hog = store.hog[dv]
    res = dict(schema='clasher.pretrain_v1.g1.v1', ckpt=a.ckpt, store=a.store, split=a.split,
               feature_hash=F.feature_hash(), gate_bias=float(ck.get('gate_bias', 0.0)), actor_rows=int(len(dv)),
               dev_plays=int(ptrue.sum()), physical_games=int(len(np.unique(phys))))
    for name, m in (('broad', np.ones(len(dv), bool)), ('hog', hog)):
        if not m.any():
            continue
        pt, lo, hi, n = cluster_ci(((joint - base)*w)[m], w[m], phys[m])
        res[f'{name}/joint_nll_model'] = float((joint*w)[m].sum()/w[m].sum())
        res[f'{name}/joint_nll_baseline'] = float((base*w)[m].sum()/w[m].sum())
        res[f'{name}/delta'] = pt
        res[f'{name}/delta_ci95'] = [lo, hi]
        res[f'{name}/games'] = n
        res[f'{name}/G1_1_pass'] = bool(hi < 0)
    bins = np.minimum((ppl*10).astype(int), 9)
    ece = sum(abs((w*(ppl - ptrue))[bins == k].sum()) for k in range(10))/w.sum()
    brier = float((w*(ppl - ptrue)**2).sum()/w.sum())
    brier_base = float((w*(hazard - ptrue)**2).sum()/w.sum())
    ratio = float((w*ppl).sum()/(w*ptrue).sum())
    res.update(gate_ece=float(ece), gate_brier=brier, gate_brier_baseline=brier_base, plays_ratio=ratio,
               G1_2_pass=bool(ece <= .03 and brier <= brier_base and .85 <= ratio <= 1.15),
               hazard_inversion='not applicable: the re-drive store has a single 5-tick cadence')
    for name, m in (('broad', np.ones(len(dv), bool)), ('hog', hog)):
        mm = m & (ptrue > 0)
        if mm.any():
            res[f'{name}/card_top1'] = float(top1[mm].mean())
            res[f'{name}/tile_top1'] = float(t1[mm].mean())
            res[f'{name}/tile_within1'] = float(tw1[mm].mean())
            mb = m & ~np.isnan(ppl)
            res[f'{name}/plays_ratio'] = float((w*ppl)[mb].sum()/(w*ptrue)[mb].sum())
    cat = F.catalog()
    cov = {}
    for c in TARGET:
        mm = (card_of == cat.card(c)) & (ptrue > 0)
        cov[c] = dict(dev_plays=int(mm.sum()), card_top1=float(top1[mm].mean()) if mm.any() else None,
                      tile_within1=float(tw1[mm].mean()) if mm.any() else None)
    res['target_cards'] = cov
    res['target_coverage_pass'] = all(v['dev_plays'] >= 100 for v in cov.values())
    Path(a.out).write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
