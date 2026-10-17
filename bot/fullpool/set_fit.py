"""Body-set sibling-leaf model on Monte Carlo targets (exploration; BOT LEAD 10-17 learned-leaf track, after mc0 tied phi).

    $GPU_PY -m bot.fullpool.set_fit --data 'J/mcgen1/*,...' --out DIR [--device cuda --steps 8000]

mc0 / mc0r / mc0c (bot/fullpool/sibling_fit.py on lane/tower aggregates) never beat phi on held-out sibling pairs
(0.637 / 0.650 / 0.733 vs phi 0.649 / 0.650 / 0.749): the aggregates are close to what phi already computes. This model
reads every body of the native public view instead: per body an embedding of its token plus (x/18, y/32, hp fraction,
log max hp, cost/10, enemy, building, only_buildings, radius), DeepSets (MLP per body -> sum and mean pool) concatenated
with the global features (bot/value/features base + sibling_fit EXTRA king-risk), MLP -> g. Antisymmetric:
V(leaf) = g(our view) - g(their view). Residual on phi: score = alpha * phi + V, alpha by least squares on train pairs.
Loss: over sibling pairs of a root, w * ((V_i - V_j) - ((y_i - y_j) - alpha (phi_i - phi_j)))^2 with
w = 1 / (SE^2 + 0.02^2) (SE of the MC difference), so confidently separated pairs dominate.
Held out: games with index % 5 == 0 (early stopping on index % 10 == 1). Reported: pair accuracy of alpha*phi + V, phi
and the search's own score, on all pairs and on pairs beyond 2 SE; per opponent; within-root spread -> kappa_max.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import time
from itertools import combinations
from pathlib import Path

import numpy as np

MAXB = 48
NUMB = 9


def body_rows(pv_side):
    out = []
    for b in pv_side['bodies']:
        if b['crown']:
            continue
        mx = max(b['maximum'], 1.)
        out.append((int(b['token']), [b['x'] / 18., b['y'] / 32., max(0., min(1., b['hp'] / mx)), math.log1p(mx) / 9.,
                                      b['cost'] / 10., float(b['enemy']), float(b['building']),
                                      float(b['only_buildings']), b.get('radius', 0.) or 0.]))
    return out[:MAXB]


def load(pattern):
    from bot.fullpool.sibling_fit import encode_ext
    files = sorted(f for d in pattern.split(',') for f in glob.glob(os.path.join(d, 'mc-*.jsonl')))
    roots = []
    for f in files:
        for line in open(f):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if 'error' in r:
                continue
            for x in r['roots']:
                sib = [s for s in x['siblings'] if s.get('mc_mean') is not None]
                if len(sib) < 2:
                    continue
                roots.append(dict(index=r['index'], seat=x['seat'], opp=r['opponent'], sib=sib))
    leaves = []
    for x in roots:
        x['leaf0'] = len(leaves)
        for s in x['sib']:
            a, b = encode_ext(s['pv'], s['parts'], x['seat'], s['tick'], {})   # no hand vocab: globals only
            leaves.append(dict(ga=a, gb=b, ba=body_rows(s['pv'][x['seat']]), bb=body_rows(s['pv'][1 - x['seat']])))
            s.pop('pv'); s.pop('parts')
    return roots, leaves


def tensors(leaves, mu, sd, dev):
    import torch
    n = len(leaves)
    G = np.zeros((2, n, len(mu)), np.float32)
    T = np.zeros((2, n, MAXB), np.int64)
    X = np.zeros((2, n, MAXB, NUMB), np.float32)
    M = np.zeros((2, n, MAXB), np.float32)
    for i, l in enumerate(leaves):
        for k, (g, bs) in enumerate(((l['ga'], l['ba']), (l['gb'], l['bb']))):
            G[k, i] = (g - mu) / sd
            for j, (t, v) in enumerate(bs):
                T[k, i, j] = min(t, 4095); X[k, i, j] = v; M[k, i, j] = 1.
    to = lambda a: torch.tensor(a, device=dev)
    return to(G), to(T), to(X), to(M)


def make_net(nglob, emb=32, hid=128):
    import torch
    from torch import nn

    class SetNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.emb = nn.Embedding(4096, emb)
            self.phi = nn.Sequential(nn.Linear(emb + NUMB, hid), nn.ReLU(), nn.Linear(hid, hid), nn.ReLU())
            self.rho = nn.Sequential(nn.Linear(2 * hid + nglob, hid), nn.ReLU(), nn.Linear(hid, hid), nn.ReLU(),
                                     nn.Linear(hid, 1))

        def g(self, G, T, X, M):
            h = self.phi(torch.cat([self.emb(T), X], -1)) * M[..., None]
            s = h.sum(-2); m = s / M.sum(-1, keepdim=True).clamp_min(1.)
            return self.rho(torch.cat([s, m, G], -1)).squeeze(-1)

        def forward(self, G, T, X, M):
            return self.g(G[0], T[0], X[0], M[0]) - self.g(G[1], T[1], X[1], M[1])
    return SetNet()


def pairs_of(roots, sel):
    I, J, D, DP, W, SE = [], [], [], [], [], []
    for x in roots:
        if not sel(x):
            continue
        for i, j in combinations(range(len(x['sib'])), 2):
            a, b = x['sib'][i], x['sib'][j]
            se2 = (a['mc_std'] ** 2 / max(a['mc_n'], 1)) + (b['mc_std'] ** 2 / max(b['mc_n'], 1))
            I.append(x['leaf0'] + i); J.append(x['leaf0'] + j); D.append(a['mc_mean'] - b['mc_mean'])
            DP.append(a['phi'] - b['phi']); W.append(1. / (se2 + .02 ** 2)); SE.append(math.sqrt(se2))
    return [np.array(v, np.float64) for v in (I, J, D, DP, W, SE)]


def acc(d, s, se, k=0.):
    m = (np.abs(d) > k * se) & (d != 0) & (s != 0) & np.isfinite(s)
    return dict(pairs=int(m.sum()), acc=round(float(((d[m] > 0) == (s[m] > 0)).mean()), 4) if m.any() else None)


def fit(a):
    import torch
    torch.manual_seed(0)
    dev = torch.device(a.device)
    t0 = time.time()
    roots, leaves = load(a.data)
    ga = np.array([l['ga'] for l in leaves]); gb = np.array([l['gb'] for l in leaves])
    mu = np.concatenate([ga, gb]).mean(0); sd = np.concatenate([ga, gb]).std(0); sd = np.where(sd < 1e-2, 1., sd)
    G, T, X, M = tensors(leaves, mu.astype(np.float32), sd.astype(np.float32), dev)
    test = lambda x: x['index'] % 5 == 0
    val = lambda x: x['index'] % 10 == 1
    train = lambda x: not test(x) and not val(x)
    tr, va, te = pairs_of(roots, train), pairs_of(roots, val), pairs_of(roots, test)
    alpha = float((tr[2] * tr[3] * tr[4]).sum() / max((tr[3] ** 2 * tr[4]).sum(), 1e-12))
    print(json.dumps(dict(roots=len(roots), leaves=len(leaves), train_pairs=len(tr[0]), test_pairs=len(te[0]),
                          alpha=round(alpha, 4), seconds=round(time.time() - t0))), flush=True)
    net = make_net(G.shape[-1]).to(dev)
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=a.wd)
    tt = lambda v: torch.tensor(v, device=dev)
    I, J, R, W = tt(tr[0]).long(), tt(tr[1]).long(), tt(tr[2] - alpha * tr[3]).float(), tt(tr[4]).float()
    W = W / W.mean()
    vI, vJ, vR, vW = tt(va[0]).long(), tt(va[1]).long(), tt(va[2] - alpha * va[3]).float(), tt(va[4]).float()
    vW = vW / vW.mean()
    best, best_state, best_step = 1e9, None, 0
    gen = torch.Generator(device='cpu').manual_seed(0)
    for step in range(a.steps):
        net.train()
        k = torch.randint(0, len(I), (min(a.batch, len(I)),), generator=gen).to(dev)
        idx = torch.unique(torch.cat([I[k], J[k]]))
        pos = torch.full((len(leaves),), -1, device=dev, dtype=torch.long); pos[idx] = torch.arange(len(idx), device=dev)
        V = net(G[:, idx], T[:, idx], X[:, idx], M[:, idx])
        loss = (W[k] * ((V[pos[I[k]]] - V[pos[J[k]]]) - R[k]) ** 2).mean()
        opt.zero_grad(); loss.backward(); opt.step()
        if (step + 1) % 100 == 0:
            net.eval()
            with torch.no_grad():
                V = net(G, T, X, M)
                vl = float((vW * ((V[vI] - V[vJ]) - vR) ** 2).mean())
            if vl < best:
                best, best_step = vl, step + 1
                best_state = {kk: v.detach().clone() for kk, v in net.state_dict().items()}
            if (step + 1) % 1000 == 0:
                print(json.dumps(dict(step=step + 1, train=round(float(loss), 6), val=round(vl, 6), best_step=best_step)),
                      flush=True)
    net.load_state_dict(best_state); net.eval()
    with torch.no_grad():
        V = net(G, T, X, M).cpu().numpy().astype(np.float64)
    I_, J_, D, DP, _, SE = te
    I_, J_ = I_.astype(int), J_.astype(int)
    score = np.array([s['score'] if s['score'] is not None else np.nan for x in roots for s in x['sib']])
    sv = alpha * DP + (V[I_] - V[J_])
    dsearch = score[I_] - score[J_]
    res = dict(roots=len(roots), test_pairs=len(D), alpha=round(alpha, 4), best_step=best_step, val_loss=round(best, 6),
               all=dict(model=acc(D, sv, SE), phi=acc(D, DP, SE), search=acc(D, dsearch, SE)),
               beyond_2se=dict(model=acc(D, sv, SE, 2), phi=acc(D, DP, SE, 2), search=acc(D, dsearch, SE, 2)),
               beyond_3se=dict(model=acc(D, sv, SE, 3), phi=acc(D, DP, SE, 3), search=acc(D, dsearch, SE, 3)))
    within = [np.std([V[x['leaf0'] + i] for i in range(len(x['sib']))]) for x in roots if test(x)]
    within_phi = [np.std([s['phi'] for s in x['sib']]) for x in roots if test(x)]
    res['within_root_std'] = dict(V=round(float(np.median(within)), 5), phi=round(float(np.median(within_phi)), 5))
    res['kappa_max'] = round(float(.5 * np.median(within_phi) / max(np.median(within), 1e-9)), 4)
    opp = np.array([x['opp'] for x in roots for _ in combinations(range(len(x['sib'])), 2) if test(x)])
    res['by_opponent'] = {o: dict(model=acc(D[opp == o], sv[opp == o], SE[opp == o], 2)['acc'],
                                  phi=acc(D[opp == o], DP[opp == o], SE[opp == o], 2)['acc'])
                          for o in sorted(set(opp))}
    a.out.mkdir(parents=True, exist_ok=True)
    torch.save(dict(state=best_state, mu=mu, sd=sd, alpha=alpha), a.out / 'set.pt')
    (a.out / 'fit.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--device', default='cuda')
    ap.add_argument('--steps', type=int, default=8000)
    ap.add_argument('--batch', type=int, default=2048)
    ap.add_argument('--lr', type=float, default=1e-3)
    ap.add_argument('--wd', type=float, default=1e-4)
    a = ap.parse_args(argv)
    a.data = ','.join(d for p in a.data.split(',') for d in (sorted(glob.glob(p)) or [p]))
    fit(a)


if __name__ == '__main__':
    main()
