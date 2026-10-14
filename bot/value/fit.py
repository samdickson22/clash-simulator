"""Fit leaf values V(state, seat) -> P(seat wins) on bot.value.gen roots (exploration).

    python -m bot.value.fit --data DIR[,DIR...] --out MODELDIR [--test-mod 5]

Models (all antisymmetric: z = g(F(me)) - g(F(them)), P = sigmoid(z); draws are label 0.5):
- phi:  z = k * phi(me)                 (phi recomputed from parts + elixir; k = unit conversion)
- lin:  g linear in the base features  (the "recalibrated phi", option c)
- mlp:  g = 2x128 ReLU MLP on base features + own-hand multi-hot (option a)
Split by game: game % test_mod == 0 is held out. Reports held-out log-loss / AUC overall and by
time bucket; writes MODELDIR/<name>.npz (numpy inference, bot/value/model.py) + fit.json.
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np

from .features import BASE_NAMES, encode, phi_from


def load(dirs, cache=None):
    if cache and Path(cache).exists():
        z = np.load(cache, allow_pickle=True)
        return {k: z[k] for k in z.files}
    rows, vocab_count = [], {}
    files = sorted(f for d in dirs for f in Path(d).glob('roots/game-*.jsonl.gz'))
    for f in files:
        lines = gzip.open(f, 'rt').read().splitlines()
        head = json.loads(lines[0])
        for line in lines[1:]:
            r = json.loads(line)
            for s in (0, 1):
                for t in r['pv'][s]['hand']:
                    vocab_count[t] = vocab_count.get(t, 0) + 1
            rows.append((head, r))
    vocab = {t: i for i, t in enumerate(sorted(t for t, c in vocab_count.items() if c >= 50))}
    X1, X2, Y, G, T, PHI, OPP = [], [], [], [], [], [], []
    for head, r in rows:
        seat = r['seat']
        a, b = encode(r['pv'], r['parts'], seat, r['tick'], vocab)
        X1.append(a); X2.append(b)
        Y.append(head['score']); G.append(head['game']); T.append(r['tick']); OPP.append(head['opponent'])
        PHI.append(phi_from(a[:7], a[7], a[8]))
    out = dict(x_me=np.array(X1, np.float32), x_them=np.array(X2, np.float32), y=np.array(Y, np.float32),
               game=np.array(G), tick=np.array(T), phi=np.array(PHI, np.float32), opponent=np.array(OPP),
               vocab=np.array(sorted(vocab, key=vocab.get)))
    if cache:
        np.savez(cache, **out)
    return out


def auc(y, s):
    m = y != .5
    y, s = y[m], s[m]
    order = np.argsort(s)
    r = np.empty(len(s)); r[order] = np.arange(1, len(s)+1)
    n1 = (y == 1).sum(); n0 = len(y) - n1
    return float((r[y == 1].sum() - n1*(n1+1)/2)/max(n1*n0, 1))


def logloss(y, p):
    p = np.clip(p, 1e-6, 1-1e-6)
    return float(-(y*np.log(p) + (1-y)*np.log(1-p)).mean())


def train(kind, xa, xb, y, nbase, hidden=128, steps=3000, lr=3e-3, wd=1e-4, seed=0, device='cpu', val=None, nohand=False,
          dropout=0.):
    import torch
    torch.manual_seed(seed)
    if kind == 'lin' or nohand:
        xa, xb = xa[:, :nbase], xb[:, :nbase]
    mu = np.concatenate([xa, xb]).mean(0); sd = np.concatenate([xa, xb]).std(0)
    # (near-)constant features (e.g. 'early', rare hand tokens) must not explode when they move at a leaf
    sd = np.where(sd < 1e-2, 1., sd).astype(np.float32)
    d = xa.shape[1]
    if kind == 'lin':
        net = torch.nn.Linear(d, 1, bias=False)
    else:
        net = torch.nn.Sequential(torch.nn.Linear(d, hidden), torch.nn.ReLU(), torch.nn.Dropout(dropout),
                                  torch.nn.Linear(hidden, hidden), torch.nn.ReLU(), torch.nn.Dropout(dropout),
                                  torch.nn.Linear(hidden, 1))
    net = net.to(device)
    A = torch.tensor((xa-mu)/sd, device=device); B = torch.tensor((xb-mu)/sd, device=device)
    Y = torch.tensor(y, device=device)
    opt = torch.optim.AdamW(net.parameters(), lr=lr, weight_decay=wd)
    n, bs = len(y), 8192
    gen = torch.Generator(device='cpu').manual_seed(seed)
    best = (None, 1e9, 0)
    for step in range(steps):
        idx = torch.randint(0, n, (bs,), generator=gen).to(device)
        z = (net(A[idx]) - net(B[idx])).squeeze(1)
        loss = torch.nn.functional.binary_cross_entropy_with_logits(z, Y[idx])
        opt.zero_grad(); loss.backward(); opt.step()
        if val is not None and (step+1) % 50 == 0:
            net.eval()
            vl = logloss(val[2], predict_torch(net, 'lin' if nohand else kind, val[0], val[1], mu, sd, nbase, device))
            net.train()
            if vl < best[1]:
                best = ({k: v.detach().cpu().clone() for k, v in net.state_dict().items()}, vl, step+1)
    if best[0] is not None:
        net.load_state_dict(best[0])
    net.eval()
    return net, mu, sd, best[2]


def predict_torch(net, kind, xa, xb, mu, sd, nbase, device='cpu'):
    import torch
    if kind == 'lin':
        xa, xb = xa[:, :nbase], xb[:, :nbase]
    with torch.no_grad():
        A = torch.tensor((xa-mu)/sd, device=device); B = torch.tensor((xb-mu)/sd, device=device)
        z = (net(A) - net(B)).squeeze(1).cpu().numpy()
    return 1/(1+np.exp(-z))


def export(path, kind, net, mu, sd, nbase, vocab, k_phi, meta):
    layers = [m for m in (net if hasattr(net, '__iter__') else [net]) if hasattr(m, 'weight')]
    arrs = {f'W{i}': m.weight.detach().cpu().numpy().astype(np.float64) for i, m in enumerate(layers)}
    arrs.update({f'b{i}': (m.bias.detach().cpu().numpy() if m.bias is not None else np.zeros(m.weight.shape[0]))
                 .astype(np.float64) for i, m in enumerate(layers)})
    np.savez(path, kind=kind, mu=mu.astype(np.float64), sd=sd.astype(np.float64), nbase=nbase,
             vocab=np.asarray(vocab), k_phi=k_phi, layers=len(layers), meta=json.dumps(meta), **arrs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--cache')
    ap.add_argument('--test-mod', type=int, default=5)
    ap.add_argument('--steps', type=int, default=4000)
    ap.add_argument('--hidden', type=int, default=128)
    ap.add_argument('--tag', default='')
    ap.add_argument('--nohand', action='store_true')
    ap.add_argument('--wd', type=float, default=1e-4)
    ap.add_argument('--dropout', type=float, default=0.)
    ap.add_argument('--lr', type=float, default=3e-3)
    a = ap.parse_args()
    import torch
    torch.set_num_threads(4)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    D = load(a.data.split(','), a.cache)
    nbase = len(BASE_NAMES)
    test = D['game'] % a.test_mod == 0
    tr = ~test
    # validation for early stopping = a slice of the TRAIN games (game % (2*mod) == 1), never the test games
    va = tr & (D['game'] % (2*a.test_mod) == 1)
    fit_rows = tr & ~va
    y, phi = D['y'], D['phi'].astype(np.float64)
    # phi model: 1-D antisymmetric logistic z = k*phi (Newton on k)
    k = 1.
    for _ in range(50):
        p = 1/(1+np.exp(-k*phi[fit_rows]))
        g = ((p - y[fit_rows])*phi[fit_rows]).sum(); h = (p*(1-p)*phi[fit_rows]**2).sum() + 1e-9
        k -= g/h
    res = dict(n_rows=int(len(y)), n_games=int(len(np.unique(D['game']))), test_games=int(len(np.unique(D['game'][test]))),
               k_phi=float(k), models={})
    preds = {'phi': 1/(1+np.exp(-k*phi))}
    a.out.mkdir(parents=True, exist_ok=True)
    vocab = [int(t) for t in D['vocab']]
    for kind in ('lin', 'mlp'):
        net, mu, sd, best_step = train(kind, D['x_me'][fit_rows], D['x_them'][fit_rows], y[fit_rows], nbase,
                                       hidden=a.hidden, steps=a.steps if kind == 'mlp' else 2000, device=device,
                                       val=(D['x_me'][va], D['x_them'][va], y[va]), nohand=a.nohand and kind == 'mlp',
                                       wd=a.wd if kind == 'mlp' else 1e-4, dropout=a.dropout, lr=a.lr)
        sl = 'lin' if (kind == 'lin' or a.nohand) else kind
        preds[kind] = predict_torch(net, sl, D['x_me'], D['x_them'], mu, sd, nbase, device)
        name = f'{kind}{a.tag}'
        export(a.out / f'{name}.npz', kind, net.cpu(), mu, sd, nbase, [] if (a.nohand or kind == 'lin') else vocab, k,
               dict(data=a.data, best_step=best_step, hidden=a.hidden, base=BASE_NAMES, nohand=a.nohand, wd=a.wd,
                    dropout=a.dropout))
        res['models'][name] = dict(best_step=best_step)
        if kind == 'lin':
            w = net.weight.detach().cpu().numpy()[0]/sd[:nbase]
            res['lin_weights_raw_units'] = {n: float(x) for n, x in zip(BASE_NAMES, w)}
    buckets = [(0, 1200), (1200, 2400), (2400, 3600), (3600, 7000)]
    for name, p in preds.items():
        row = dict(logloss=logloss(y[test], p[test]), auc=auc(y[test], p[test]),
                   train_logloss=logloss(y[fit_rows], p[fit_rows]))
        for lo, hi in buckets:
            m = test & (D['tick'] >= lo) & (D['tick'] < hi)
            if m.sum():
                row[f'auc_{lo}_{hi}'] = auc(y[m], p[m]); row[f'll_{lo}_{hi}'] = logloss(y[m], p[m])
        res['models'].setdefault(name if name == 'phi' else f'{name}{a.tag}', {}).update(row)
    res['base_rate_logloss'] = logloss(y[test], np.full(test.sum(), y[fit_rows].mean()))
    (a.out / f'fit{a.tag}.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
