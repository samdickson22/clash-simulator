"""Leaf value for K4L search: predicted +30 s margin change from a native state's public view (exploration; plan step 2).

    python -m bot.fullpool.leaf_value fit --data DIR[,DIR...] --out MODELDIR [--horizon 600] [--tag d30]

Data: bot.value.gen root files (DIR/roots/game-*.jsonl.gz: header + one row per searched decision with both seats'
native public_view, phi's evaluation_parts and the tick). Features = bot/value/features.encode (seat-relative base
features + own-hand multi-hot), so the same model reads any native BattleState: a search root or a rollout leaf.
Target: margin(t + horizon) - margin(t) for the row's seat, margin = (own - enemy crowns)/3 + (own - enemy tower
HP)/15000 (princess 3052, king 4824 HP; crowns = destroyed towers, king = 3; the units of value_net.py and
bot/livediag/dumpbank_fit.py). margin(t + horizon) is the first later row of the same game at tick >= t + horizon,
else the game's final towers (header). Model: antisymmetric z = g(F(me)) - g(F(them)) (2x128 ReLU MLP, and the
linear model for coefficients), MSE; split by game (game % 5 == 0 held out; early stopping on a train slice).
Reports held-out-game Pearson correlation (MLP, linear, phi difference as a baseline), the linear model's raw
coefficients and the MLP's mean change for +1 own / +1 enemy elixir (expected > 0 / < 0). Writes MODELDIR/<kind><tag>.npz
(bot/value/model.py ValueModel; k_phi = 1, so .logit() is the predicted margin change) and fit<tag>.json.

Search use (install): leaf += kappa * clip(d_hat(leaf), -1, 1) on non-terminal leaves; see bot/search/lopp.py
`core.leaf_value` and the K4L token vl<P> (kappa = P/100).
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
from pathlib import Path

import numpy as np

PRINCESS, KING, HP_UNIT = 3052., 4824., 15000.


def margin_pv(towers):
    """towers = pv['towers'] fractions [own L, R, K, enemy L, R, K]."""
    own, opp = towers[:3], towers[3:]

    def crowns(t):
        return 3. if t[2] <= 0 else float(t[0] <= 0) + float(t[1] <= 0)
    hp = lambda t: PRINCESS * (t[0] + t[1]) + KING * t[2]
    return (crowns(opp) - crowns(own)) / 3 + (hp(own) - hp(opp)) / HP_UNIT


def margin_final(head, seat):
    """Header towers {seat: [king, left, right]} in HP."""
    t = head['towers']
    get = lambda s: t[str(s)] if str(s) in t else t[s]
    me, them = get(seat), get(1 - seat)
    frac = lambda x: [x[1] / PRINCESS, x[2] / PRINCESS, x[0] / KING]
    return margin_pv(frac(me) + frac(them))


def load(dirs, horizon, min_count=50):
    from bot.value.features import encode, phi_from
    games, vocab_count = [], {}
    for d in dirs:
        for f in sorted(Path(d).glob('roots/game-*.jsonl.gz')):
            lines = gzip.open(f, 'rt').read().splitlines()
            if len(lines) < 2:
                continue
            head = json.loads(lines[0])
            rows = [json.loads(x) for x in lines[1:]]
            for r in rows:
                for t in r['pv'][r['seat']]['hand']:
                    vocab_count[t] = vocab_count.get(t, 0) + 1
            games.append((f'{d}|{head["game"]}', head, rows))
    vocab = {t: i for i, t in enumerate(sorted(t for t, c in vocab_count.items() if c >= min_count))}
    X1, X2, Y, G, T, PHI, OPP = [], [], [], [], [], [], []
    for gi, (key, head, rows) in enumerate(games):
        rows.sort(key=lambda r: r['tick'])
        ticks = np.array([r['tick'] for r in rows])
        for r in rows:
            s = r['seat']
            m0 = margin_pv(r['pv'][s]['towers'])
            j = int(np.searchsorted(ticks, r['tick'] + horizon, side='left'))
            m1 = margin_pv(rows[j]['pv'][rows[j]['seat']]['towers']) if j < len(rows) and rows[j]['seat'] == s else \
                margin_final(head, s)
            a, b = encode(r['pv'], r['parts'], s, r['tick'], vocab)
            X1.append(a); X2.append(b); Y.append(m1 - m0); G.append(gi); T.append(r['tick'])
            OPP.append(head.get('opponent', ''))
            PHI.append(phi_from(a[:7], a[7], a[8]) - phi_from(b[:7], b[7], b[8]))
    return dict(x_me=np.array(X1, np.float32), x_them=np.array(X2, np.float32), y=np.array(Y, np.float32),
                game=np.array(G), tick=np.array(T), phi=np.array(PHI, np.float32), opponent=np.array(OPP),
                vocab=[t for t, _ in sorted(vocab.items(), key=lambda kv: kv[1])], n_games=len(games))


def train(kind, xa, xb, y, val, hidden=128, steps=4000, lr=3e-3, wd=1e-4, seed=0, device='cpu'):
    import torch
    torch.manual_seed(seed)
    mu = np.concatenate([xa, xb]).mean(0); sd = np.concatenate([xa, xb]).std(0)
    sd = np.where(sd < 1e-2, 1., sd).astype(np.float32)
    d = xa.shape[1]
    net = (torch.nn.Linear(d, 1, bias=False) if kind == 'lin' else
           torch.nn.Sequential(torch.nn.Linear(d, hidden), torch.nn.ReLU(), torch.nn.Linear(hidden, hidden),
                               torch.nn.ReLU(), torch.nn.Linear(hidden, 1))).to(device)
    A = torch.tensor((xa - mu) / sd, device=device); B = torch.tensor((xb - mu) / sd, device=device)
    Y = torch.tensor(y, device=device)
    VA = torch.tensor((val[0] - mu) / sd, device=device); VB = torch.tensor((val[1] - mu) / sd, device=device)
    VY = torch.tensor(val[2], device=device)
    opt = torch.optim.AdamW(net.parameters(), lr=lr, weight_decay=wd)
    gen = torch.Generator(device='cpu').manual_seed(seed)
    best = (None, 1e9, 0)
    for step in range(steps):
        idx = torch.randint(0, len(y), (8192,), generator=gen).to(device)
        z = (net(A[idx]) - net(B[idx])).squeeze(1)
        loss = ((z - Y[idx]) ** 2).mean()
        opt.zero_grad(); loss.backward(); opt.step()
        if (step + 1) % 50 == 0:
            with torch.no_grad():
                vl = float((((net(VA) - net(VB)).squeeze(1) - VY) ** 2).mean())
            if vl < best[1]:
                best = ({k: v.detach().cpu().clone() for k, v in net.state_dict().items()}, vl, step + 1)
    net.load_state_dict(best[0])
    net.eval()
    return net.cpu(), mu, sd, best[2]


def predict(net, xa, xb, mu, sd):
    import torch
    with torch.no_grad():
        return (net(torch.tensor((xa - mu) / sd)) - net(torch.tensor((xb - mu) / sd))).squeeze(1).numpy()


def corr(a, b):
    return round(float(np.corrcoef(a, b)[0, 1]), 4) if np.std(a) > 0 and np.std(b) > 0 else None


def fit(a):
    import torch
    from bot.value.features import BASE_NAMES
    from bot.value.fit import export
    torch.set_num_threads(int(os.environ.get('OMP_NUM_THREADS', '4')))
    D = load(a.data.split(','), a.horizon)
    test = D['game'] % 5 == 0
    va = ~test & (D['game'] % 10 == 1)
    tr = ~test & ~va
    xa, xb, y = D['x_me'], D['x_them'], D['y']
    nbase = len(BASE_NAMES)
    res = dict(rows=int(len(y)), games=D['n_games'], test_rows=int(test.sum()), horizon=a.horizon,
               target_mean=round(float(y.mean()), 4), target_std=round(float(y.std()), 4),
               baseline_phi_diff=dict(corr=corr(D['phi'][test], y[test])), models={})
    a.out.mkdir(parents=True, exist_ok=True)
    i_me, i_them = BASE_NAMES.index('elixir_me'), BASE_NAMES.index('elixir_them')
    for kind in ('lin', 'mlp'):
        cols = slice(0, nbase) if kind == 'lin' else slice(None)
        net, mu, sd, step = train(kind, xa[tr][:, cols], xb[tr][:, cols], y[tr], (xa[va][:, cols], xb[va][:, cols], y[va]),
                                  steps=2000 if kind == 'lin' else a.steps)
        p = predict(net, xa[test][:, cols], xb[test][:, cols], mu, sd)
        row = dict(best_step=step, corr=corr(p, y[test]),
                   ev=round(float(1 - np.var(y[test] - p) / np.var(y[test])), 4))
        for lo, hi in ((0, 1200), (1200, 2400), (2400, 3600), (3600, 9000)):
            m = (D['tick'][test] >= lo) & (D['tick'][test] < hi)
            if m.sum() > 100:
                row[f'corr_{lo}_{hi}'] = corr(p[m], y[test][m])
        for opp in sorted(set(D['opponent'][test])):
            m = D['opponent'][test] == opp
            if m.sum() > 100:
                row[f'corr_vs_{opp}'] = corr(p[m], y[test][m])
        # +1 own elixir: own perspective elixir_me and the other perspective's elixir_them both move
        ea, eb = xa[test][:, cols].copy(), xb[test][:, cols].copy()
        ea[:, i_me] += 1; eb[:, i_them] += 1
        d_own = predict(net, ea, eb, mu, sd) - p
        ea, eb = xa[test][:, cols].copy(), xb[test][:, cols].copy()
        ea[:, i_them] += 1; eb[:, i_me] += 1
        d_opp = predict(net, ea, eb, mu, sd) - p
        row['own_elixir_plus1'] = dict(mean=round(float(d_own.mean()), 5), share_pos=round(float((d_own > 0).mean()), 3))
        row['opp_elixir_plus1'] = dict(mean=round(float(d_opp.mean()), 5), share_pos=round(float((d_opp > 0).mean()), 3))
        if kind == 'lin':
            w = net.weight.detach().numpy()[0] / sd[:nbase]
            row['coef_raw'] = {n: round(float(x), 5) for n, x in zip(BASE_NAMES, w)}
        name = f'{kind}{a.tag}'
        export(a.out / f'{name}.npz', kind, net, mu, sd, nbase, [] if kind == 'lin' else D['vocab'], 1.0,
               dict(data=a.data, target=f'margin change +{a.horizon} ticks', best_step=step, base=BASE_NAMES))
        res['models'][name] = row
    (a.out / f'fit{a.tag}.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


def install(core, model_path, kappa, seat_of=None):
    """Set core.leaf_value(sim, seat, tick) = kappa * clip(d_hat, -1, 1) (read by bot/search/lopp.py)."""
    from bot.value.model import ValueModel
    model = ValueModel(model_path)
    native = core.native

    def leaf_value(sim, seat, tick):
        pv = [json.loads(native.public_view(sim, s)) for s in (0, 1)]
        return kappa * max(-1., min(1., model.logit(pv, list(native.evaluation_parts(sim)), seat, tick)))
    core.leaf_value = leaf_value
    return leaf_value


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    f = sub.add_parser('fit')
    f.add_argument('--data', required=True)
    f.add_argument('--out', required=True, type=Path)
    f.add_argument('--horizon', type=int, default=600)
    f.add_argument('--steps', type=int, default=4000)
    f.add_argument('--tag', default='-d30')
    a = ap.parse_args(argv)
    fit(a)


if __name__ == '__main__':
    main()
