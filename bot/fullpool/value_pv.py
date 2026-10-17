"""Value-net v1 on native public-view features, with a sibling pair loss (exploration; BOT LEAD overnight plan 10-17).

    $GPU_PY -m bot.fullpool.value_pv --states 'J/leafgen*,J/leafdata/*' --siblings 'J/sibgen1/*' --out DIR [--device cuda]

Why native features: v0 (bot/fullpool/value_net.py) reads v5 packets, which native rollout leaves do not have, so it
cannot score sibling leaves inside search. This net reads exactly what the vl leaf term reads (bot/fullpool/
sibling_fit.encode_ext: bot/value/features + king-risk EXTRA), so its d30 head is directly a K4L leaf term.
Data:
- STATES: bot.value.gen roots (leafgen1/2/2b/2c/3 full-pool games of the bundle's search, strong-opponent heavy, and
  the old C56 value-gen roots): per root our seat's public views, evaluation_parts, tick, and per game the series of
  roots. Targets: realized margin change at +15/30/60 s (bot/fullpool/leaf_value.margin_pv; end of game -> final
  towers), outcome (+1/0/-1), and where present (leafgen2*) the vn0b teacher's d30 head ('vn').
- SIBLINGS: bot/fullpool/sibling_gen roots (2-3 sibling leaves, realized 30 s margin change of each forced branch).
Model: antisymmetric MLP (z = g(F(me)) - g(F(them)), 3 x 256 ReLU, 5 heads: d15, d30, d60, outcome (tanh), vn30).
Loss: MSE per head in target-std units (vn30 only where labelled) + PAIR_W * mean over sibling pairs of
((d30_i - d30_j) - (y_i - y_j))^2 / std(y diff)^2. Split by game: index % 5 == 0 held out (states and siblings).
Gates reported (held out): corr per head (all, vs K4C-r16/LIVE-K4CW-r16, king slice: >= 1 own princess down and an
enemy unit within 7 tiles of our king), elixir signs (+1 own / +1 opponent on the d30 head), sibling pair accuracy
of the d30 head vs phi and vs the search's own score (baseline 0.571), and the within-root spread ratio -> kappa_max.
Writes DIR/vpv1.npz: the d30 head as a bot/value/model.py MLP (meta extras=True, so leaf_value.install / vl<P>
reads it), DIR/vpv1.pt (all heads), DIR/fit.json.
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import math
import os
import random
import time
from itertools import combinations
from pathlib import Path

import numpy as np

HEADS = ('d15', 'd30', 'd60', 'outcome', 'vn30')
HORIZONS = dict(d15=300, d30=600, d60=1200)
PAIR_W = 1.0
TIE = 0.02


def expand(patterns):
    return [d for p in patterns.split(',') for d in (sorted(glob.glob(p)) or [p])]


def load_states(dirs, vocab_min=50):
    from bot.fullpool.leaf_value import margin_pv, margin_final
    games, vocab_count = [], {}
    for d in dirs:
        for f in sorted(Path(d).glob('roots/game-*.jsonl.gz')):
            try:
                lines = gzip.open(f, 'rt').read().splitlines()
            except (OSError, EOFError):
                continue
            if len(lines) < 2:
                continue
            head = json.loads(lines[0])
            rows = [json.loads(x) for x in lines[1:]]
            for r in rows:
                for t in r['pv'][r['seat']]['hand']:
                    vocab_count[t] = vocab_count.get(t, 0) + 1
            games.append((d, head, rows))
    return games, vocab_count


def load_siblings(dirs):
    roots = []
    for d in dirs:
        for f in glob.glob(os.path.join(d, 'sib-*.jsonl')):
            for line in open(f):
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if 'error' in r:
                    continue
                for x in r['roots']:
                    sib = [s for s in x['siblings'] if s.get('d30') is not None and s.get('replay_ok', True)]
                    if len(sib) >= 2:
                        roots.append(dict(index=r['index'], seat=x['seat'], opp=r['opponent'], sib=sib))
    return roots


def build(a):
    from bot.fullpool.leaf_value import margin_pv, margin_final
    from bot.fullpool.sibling_fit import encode_ext, king_slice
    t0 = time.time()
    games, vc = load_states(expand(a.states))
    sroots = load_siblings(expand(a.siblings))
    for x in sroots:
        for s in x['sib']:
            for t in s['pv'][x['seat']]['hand']:
                vc[t] = vc.get(t, 0) + 1
    vocab = {t: i for i, t in enumerate(sorted(t for t, c in vc.items() if c >= 50))}
    XA, XB, Y, M, G, OPP, KING = [], [], [], [], [], [], []
    for gi, (d, head, rows) in enumerate(games):
        rows.sort(key=lambda r: r['tick'])
        ticks = np.array([r['tick'] for r in rows])
        seat = rows[0]['seat']
        mf = margin_final(head, seat)
        ms = [margin_pv(r['pv'][r['seat']]['towers']) for r in rows]
        out = {1.0: 1., 0.0: -1., 0.5: 0.}.get(head.get('score'), 0.)
        held = (head['game'] % 5 == 0)
        for k, r in enumerate(rows):
            s = r['seat']
            y = []
            for h in ('d15', 'd30', 'd60'):
                j = int(np.searchsorted(ticks, r['tick'] + HORIZONS[h], side='left'))
                y.append((ms[j] if j < len(rows) else mf) - ms[k])
            vn = r.get('vn')
            y += [out, vn[1] if vn else 0.]
            a_, b_ = encode_ext(r['pv'], r['parts'], s, r['tick'], vocab)
            XA.append(a_); XB.append(b_); Y.append(y); M.append([1, 1, 1, 1, 1 if vn else 0])
            G.append(1 if held else 0); OPP.append(head.get('opponent', '')); KING.append(king_slice(r['pv'][s]))
    S = dict(A=np.array(XA, np.float32), B=np.array(XB, np.float32), Y=np.array(Y, np.float32),
             M=np.array(M, np.float32), held=np.array(G, bool), opp=np.array(OPP), king=np.array(KING, bool))
    sib = []
    for x in sroots:
        xs = [encode_ext(s['pv'], s['parts'], x['seat'], s['tick'], vocab) for s in x['sib']]
        sib.append(dict(A=np.array([p for p, _ in xs], np.float32), B=np.array([q for _, q in xs], np.float32),
                        y=np.array([s['d30'] for s in x['sib']], np.float32),
                        phi=np.array([s['phi'] for s in x['sib']], np.float32),
                        score=np.array([s['score'] if s['score'] is not None else np.nan for s in x['sib']], np.float32),
                        held=x['index'] % 5 == 0, opp=x['opp'],
                        king=any(king_slice(s['pv'][x['seat']]) for s in x['sib'])))
    print(json.dumps(dict(state_games=len(games), states=int(len(Y)), held_states=int(S['held'].sum()),
                          vn_labelled=int(S['M'][:, 4].sum()), sibling_roots=len(sib), vocab=len(vocab),
                          seconds=round(time.time() - t0))), flush=True)
    return S, sib, [t for t, _ in sorted(vocab.items(), key=lambda kv: kv[1])]


def make_net(d, hidden=256, depth=3):
    import torch
    from torch import nn
    layers, w = [], d
    for _ in range(depth):
        layers += [nn.Linear(w, hidden), nn.ReLU()]   # ReLU: bot/value/model.py inference
        w = hidden
    layers += [nn.Linear(w, len(HEADS))]
    return nn.Sequential(*layers)


def pair_acc(sib, vals, key='V'):
    hit = n = 0
    for x, v in zip(sib, vals):
        for i, j in combinations(range(len(x['y'])), 2):
            dy = x['y'][i] - x['y'][j]
            dv = v[i] - v[j]
            if abs(dy) <= TIE or not np.isfinite(dv) or dv == 0:
                continue
            n += 1; hit += (dy > 0) == (dv > 0)
    return dict(pairs=n, acc=round(hit / n, 4) if n else None)


def corr(a, b):
    return round(float(np.corrcoef(a, b)[0, 1]), 4) if len(a) > 2 and np.std(a) > 0 and np.std(b) > 0 else None


def fit(a):
    import torch
    torch.manual_seed(0); np.random.seed(0)
    dev = torch.device(a.device)
    S, sib, vocab = build(a)
    tr = ~S['held']
    mu = np.concatenate([S['A'][tr], S['B'][tr]]).mean(0)
    sd = np.concatenate([S['A'][tr], S['B'][tr]]).std(0); sd = np.where(sd < 1e-2, 1., sd).astype(np.float32)
    ysd = np.array([max(1e-3, float(S['Y'][tr & (S['M'][:, k] > 0), k].std())) for k in range(len(HEADS))], np.float32)
    ysd[HEADS.index('outcome')] = 1.
    T = lambda x: torch.tensor((x - mu) / sd, device=dev)
    A, B = T(S['A']), T(S['B'])
    Y, Mk = torch.tensor(S['Y'], device=dev), torch.tensor(S['M'], device=dev)
    ysd_t = torch.tensor(ysd, device=dev)
    tr_idx = torch.tensor(np.flatnonzero(tr), device=dev)
    # sibling pairs (train)
    pI, pJ, pY, pa, pb, off = [], [], [], [], [], 0
    for x in sib:
        if x['held']:
            continue
        for i, j in combinations(range(len(x['y'])), 2):
            pI.append(off + i); pJ.append(off + j); pY.append(x['y'][i] - x['y'][j])
        pa.append(x['A']); pb.append(x['B']); off += len(x['y'])
    PA, PB = T(np.concatenate(pa)), T(np.concatenate(pb))
    pI, pJ = torch.tensor(pI, device=dev), torch.tensor(pJ, device=dev)
    pY = torch.tensor(np.array(pY, np.float32), device=dev)
    pysd = float(max(1e-3, pY.std().item()))
    net = make_net(A.shape[1], a.hidden, a.depth).to(dev)
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=a.wd)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=a.steps, pct_start=.05)

    def heads(XA, XB):
        z = net(XA) - net(XB)
        return torch.cat([z[:, :3], torch.tanh(z[:, 3:4]), z[:, 4:5]], 1)
    gen = torch.Generator(device='cpu').manual_seed(0)
    log = []
    t0 = time.time()
    for step in range(a.steps):
        idx = tr_idx[torch.randint(0, len(tr_idx), (a.batch,), generator=gen).to(dev)]
        h = heads(A[idx], B[idx])
        ls = ((((h - Y[idx]) / ysd_t) ** 2) * Mk[idx]).sum(0) / Mk[idx].sum(0).clamp_min(1)
        loss = ls.sum()
        if len(pY):
            k = torch.randint(0, len(pY), (min(a.pair_batch, len(pY)),), generator=gen).to(dev)
            v = (net(PA) - net(PB))[:, 1]      # all sibling leaves (tens of thousands of rows) per step
            dv = v[pI[k]] - v[pJ[k]]
            loss = loss + a.pair_w * (((dv - pY[k]) / pysd) ** 2).mean()
        opt.zero_grad(); loss.backward(); opt.step(); sched.step()
        if (step + 1) % 500 == 0:
            log.append(dict(step=step + 1, loss=round(float(loss), 4), per_head=[round(float(x), 4) for x in ls],
                            wall=round(time.time() - t0)))
            print(json.dumps(log[-1]), flush=True)
    net.eval()
    with torch.no_grad():
        H = heads(A, B).cpu().numpy()
        # elixir sensitivity on held-out states: +1 own elixir (own perspective elixir_me, other perspective elixir_them)
        from bot.value.features import BASE_NAMES
        im, it = BASE_NAMES.index('elixir_me'), BASE_NAMES.index('elixir_them')
        held = np.flatnonzero(S['held'])[:20000]
        a0, b0 = S['A'][held].copy(), S['B'][held].copy()
        base = H[held, 1]
        a1, b1 = a0.copy(), b0.copy(); a1[:, im] += 1; b1[:, it] += 1
        d_own = heads(T(a1), T(b1)).cpu().numpy()[:, 1] - base
        a2, b2 = a0.copy(), b0.copy(); a2[:, it] += 1; b2[:, im] += 1
        d_opp = heads(T(a2), T(b2)).cpu().numpy()[:, 1] - base
        sv = [((net(T(x['A'])) - net(T(x['B'])))[:, 1]).cpu().numpy() for x in sib]
    h = S['held']
    res = dict(states=int(len(h)), held_states=int(h.sum()), sibling_roots=len(sib), steps=a.steps, log=log[-3:],
               corr={hd: corr(H[h, k], S['Y'][h, k]) if hd != 'vn30' else corr(H[h & (S['M'][:, 4] > 0), k],
                                                                                S['Y'][h & (S['M'][:, 4] > 0), k])
                     for k, hd in enumerate(HEADS)})
    for o in ('K4C-r16', 'LIVE-K4CW-r16'):
        m = h & (S['opp'] == o)
        res[f'corr_d30_vs_{o}'] = corr(H[m, 1], S['Y'][m, 1])
    m = h & S['king']
    res['king_slice'] = dict(states=int(m.sum()), corr_d30=corr(H[m, 1], S['Y'][m, 1]))
    res['elixir_d30'] = dict(own_plus1=round(float(d_own.mean()), 5), own_share_pos=round(float((d_own > 0).mean()), 3),
                             opp_plus1=round(float(d_opp.mean()), 5), opp_share_neg=round(float((d_opp < 0).mean()), 3))
    res['sign_gate'] = bool(d_own.mean() > 0 and (d_own > 0).mean() >= .8 and d_opp.mean() < 0 and (d_opp < 0).mean() >= .6)
    hs = [x for x in sib if x['held']]
    hv = [v for x, v in zip(sib, sv) if x['held']]
    res['siblings'] = dict(held_roots=len(hs), V=pair_acc(hs, hv), phi=pair_acc(hs, [x['phi'] for x in hs]),
                           search_score=pair_acc(hs, [x['score'] for x in hs]))
    hk = [(x, v) for x, v in zip(hs, hv) if x['king']]
    res['siblings']['king_slice'] = dict(roots=len(hk), V=pair_acc([x for x, _ in hk], [v for _, v in hk]),
                                         phi=pair_acc([x for x, _ in hk], [x['phi'] for x, _ in hk]))
    spv = np.median([np.std(v) for v in hv]) if hv else 0.
    spp = np.median([np.std(x['phi']) for x in hs]) if hs else 0.
    res['within_root_std'] = dict(V=round(float(spv), 5), phi=round(float(spp), 5))
    res['kappa_max'] = round(float(.5 * spp / max(spv, 1e-9)), 4)
    a.out.mkdir(parents=True, exist_ok=True)
    torch.save(dict(state=net.state_dict(), mu=mu, sd=sd, vocab=vocab, heads=HEADS, hidden=a.hidden, depth=a.depth),
               a.out / 'vpv1.pt')
    # d30 head as a bot/value/model.py MLP: the last layer keeps only row 1
    from bot.value.features import BASE_NAMES
    lin = [m for m in net if hasattr(m, 'weight')]
    arrs = {}
    for i, m in enumerate(lin):
        W = m.weight.detach().cpu().numpy().astype(np.float64); b = m.bias.detach().cpu().numpy().astype(np.float64)
        if i == len(lin) - 1:
            W, b = W[1:2], b[1:2]
        arrs[f'W{i}'], arrs[f'b{i}'] = W, b
    np.savez(a.out / 'vpv1.npz', kind='mlp', mu=mu.astype(np.float64), sd=sd.astype(np.float64), nbase=len(BASE_NAMES),
             vocab=np.asarray(vocab), k_phi=1.0, layers=len(lin),
             meta=json.dumps(dict(extras=True, target='d30 head of value-net v1 (states + sibling pairs)',
                                  kappa_max=res['kappa_max'])), **arrs)
    (a.out / 'fit.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--states', required=True)
    ap.add_argument('--siblings', required=True)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--device', default='cuda')
    ap.add_argument('--steps', type=int, default=20000)
    ap.add_argument('--batch', type=int, default=4096)
    ap.add_argument('--pair-batch', type=int, default=2048)
    ap.add_argument('--pair-w', type=float, default=PAIR_W)
    ap.add_argument('--hidden', type=int, default=256)
    ap.add_argument('--depth', type=int, default=3)
    ap.add_argument('--lr', type=float, default=1e-3)
    ap.add_argument('--wd', type=float, default=1e-4)
    a = ap.parse_args(argv)
    fit(a)


if __name__ == '__main__':
    main()
