"""Within-root leaf term from sibling leaves (exploration; BOT LEAD 2026-10-17: the leaf must separate SIBLINGS).

    python -m bot.fullpool.sibling_fit --data 'J/sibgen1/*' --out MODELDIR [--steps 4000]

Data: bot/fullpool/sibling_gen.py rows: per root, 2-3 sibling candidates with their balanced native leaf (public views,
evaluation_parts, phi, tick) and the realized 30 s margin change of each sibling's branch (base game or a forced
replay; replays with replay_ok False are dropped). Our deck rotates (deck-diversity rule).
Features: bot/value/features.encode (both kings' / princesses' HP fractions, crowns, pressures, lane values, own hand)
plus EXTRA (BOT LEAD / live-diag s69 king-collapse case): king activated (king damaged or a princess down) for each side,
enemy unit count and value within KING_R tiles of our king, ours within KING_R of theirs, princesses down per side,
last-tower risk (both princesses down) x (1 - king fraction) per side, and the distance-weighted enemy value near our
king (x (1 + our princesses down)). Base features already hold both kings' HP fractions, both elixirs and crowns.
Model: antisymmetric MLP V = g(F(me)) - g(F(them)); loss over all sibling pairs (i, j) of a root:
((V_i - V_j) - (d30_i - d30_j))^2. Only differences matter, as in search (a constant shift does not reorder).
Held out: games with index % 5 == 0 (early stopping on index % 10 == 1, also not trained on). Report (held-out):
- pairwise accuracy: share of sibling pairs with |d30_i - d30_j| > TIE where sign(V_i - V_j) == sign(d30_i - d30_j);
  baselines: phi (the leaf as is) and the search's own score of each sibling;
- the same on the KING slice: roots whose leaves show >= 1 of our princesses down and an enemy unit within KING_R of
  our king;
- kappa for spread: within-root std of V vs std of phi (median over roots); kappa_max = 0.5 * std(phi)/std(V), the
  largest kappa whose term spread stays <= 0.5x phi's (BOT LEAD gate);
- per own deck and per opponent: pairwise accuracy of V and phi.
Writes MODELDIR/sib.npz (bot/value/model.py format, meta extras=True, kappa_max) and fit.json.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from itertools import combinations
from pathlib import Path

import numpy as np

KING_R = 7.0     # tiles: an enemy body this close to our king (own king at (9, 3), seat-relative frame)
TIE = 0.02       # margin units: pairs closer than this are not scored
EXTRA_NAMES = ['king_active_me', 'king_active_them', 'enemy_near_my_king_n', 'enemy_near_my_king_value',
               'mine_near_their_king_n', 'mine_near_their_king_value', 'princess_down_me', 'princess_down_them',
               'last_tower_risk_me', 'last_tower_risk_them', 'enemy_king_threat_eta']


def extras(pv_me):
    """EXTRA features from one seat's public view (seat-relative frame: own king (9, 3), enemy king (9, 29))."""
    tw = pv_me['towers']   # own L, R, K, enemy L, R, K (fractions)
    down_me = float(tw[0] <= 0) + float(tw[1] <= 0)
    down_them = float(tw[3] <= 0) + float(tw[4] <= 0)
    near = [0., 0., 0., 0.]
    threat = 0.
    for b in pv_me['bodies']:
        if b['crown']:
            continue
        v = b['cost'] * max(0., min(1., b['hp'] / max(b['maximum'], 1.)))
        dist = ((b['x'] - 9.) ** 2 + (b['y'] - 3.) ** 2) ** .5
        if b['enemy']:
            threat += v / (1. + max(0., dist - 3.) / 2.)     # remaining enemy value, nearer to our king counts more
        if b['enemy'] and dist <= KING_R:
            near[0] += 1; near[1] += v
        if not b['enemy'] and ((b['x'] - 9.) ** 2 + (b['y'] - 29.) ** 2) ** .5 <= KING_R:
            near[2] += 1; near[3] += v
    risk_me = float(down_me == 2) * (1. - tw[2])        # live-diag s69: last tower standing x king damage
    risk_them = float(down_them == 2) * (1. - tw[5])
    return ([float(tw[2] < 1 or down_me > 0), float(tw[5] < 1 or down_them > 0)] + near + [down_me, down_them] +
            [risk_me, risk_them, threat * (1. + down_me)])


def encode_ext(pv, parts, seat, tick, vocab):
    from bot.value.features import encode
    a, b = encode(pv, parts, seat, tick, vocab)
    return np.concatenate([a, extras(pv[seat])]), np.concatenate([b, extras(pv[1 - seat])])


def king_slice(pv_me):
    e = extras(pv_me)
    return e[6] >= 1 and e[2] >= 1


def load(pattern, min_count=50, target='d30'):
    files = sorted(f for d in pattern.split(',') for pat in ('sib-*.jsonl', 'mc-*.jsonl')
                   for f in glob.glob(os.path.join(d, pat)))
    roots, vocab_count = [], {}
    for f in files:
        for line in open(f):
            try:
                r = json.loads(line)
            except ValueError:      # a partly written last line of a running block
                continue
            if 'error' in r:
                continue
            for x in r['roots']:
                if target == 'mc':      # bot/fullpool/mc_gen.py rows: mean continuation margin per sibling
                    for s in x['siblings']:
                        s['d30'] = s.get('mc_mean')
                sib = [s for s in x['siblings'] if s.get('d30') is not None and s.get('replay_ok', True)]
                if len(sib) < 2:
                    continue
                for s in sib:
                    for t in s['pv'][x['seat']]['hand']:
                        vocab_count[t] = vocab_count.get(t, 0) + 1
                roots.append(dict(game=f'{r["base"]}|{r["index"]}', index=r['index'], seat=x['seat'],
                                  own=','.join(r['own_deck']), opp=r['opponent'], sib=sib))
    vocab = {t: i for i, t in enumerate(sorted(t for t, c in vocab_count.items() if c >= min_count))}
    for x in roots:
        xs = [encode_ext(s['pv'], s['parts'], x['seat'], s['tick'], vocab) for s in x['sib']]
        x['A'] = np.array([a for a, _ in xs], np.float32)
        x['B'] = np.array([b for _, b in xs], np.float32)
        x['y'] = np.array([s['d30'] for s in x['sib']], np.float32)
        x['phi'] = np.array([s['phi'] for s in x['sib']], np.float32)
        x['se2'] = np.array([(s.get('mc_std') or 0.) ** 2 / max(s.get('mc_n') or 1, 1) for s in x['sib']], np.float32)
        x['score'] = np.array([s['score'] if s['score'] is not None else np.nan for s in x['sib']], np.float32)
        x['king'] = any(king_slice(s['pv'][x['seat']]) for s in x['sib'])
        for s in x['sib']:
            s.pop('pv'); s.pop('parts')
    return roots, [t for t, _ in sorted(vocab.items(), key=lambda kv: kv[1])]


CONF = 0.     # --confident k: only pairs with |dy| > k * SE(dy) (MC targets) are trained on / scored


def pair_ok(x, i, j):
    dy = x['y'][i] - x['y'][j]
    if CONF > 0:
        return abs(dy) > CONF * float(np.sqrt(x['se2'][i] + x['se2'][j])) and dy != 0
    return abs(dy) > TIE


def pair_acc(roots, key):
    hit = n = 0
    for x in roots:
        v = x[key]
        for i, j in combinations(range(len(x['y'])), 2):
            dy = x['y'][i] - x['y'][j]
            dv = v[i] - v[j]
            if not pair_ok(x, i, j) or not np.isfinite(dv) or dv == 0:
                continue
            n += 1; hit += (dy > 0) == (dv > 0)
    return dict(pairs=n, acc=round(hit / n, 4) if n else None)


def fit(a):
    import torch
    from bot.value.features import BASE_NAMES
    from bot.value.fit import export
    torch.manual_seed(0)
    torch.set_num_threads(int(os.environ.get('OMP_NUM_THREADS', '4')))
    roots, vocab = load(a.data, target=a.target)
    test = [x for x in roots if x['index'] % 5 == 0]
    va_roots = [x for x in roots if x['index'] % 10 == 1]          # early stopping: games never trained on
    train = [x for x in roots if x['index'] % 5 != 0 and x['index'] % 10 != 1]
    alpha = 0.
    if a.residual:      # the leaf term is ADDED to phi: learn the correction to a*phi (a by least squares on train pairs)
        dy = np.array([x['y'][i] - x['y'][j] for x in train for i, j in combinations(range(len(x['y'])), 2)])
        dp = np.array([x['phi'][i] - x['phi'][j] for x in train for i, j in combinations(range(len(x['y'])), 2)])
        alpha = float((dy * dp).sum() / max((dp * dp).sum(), 1e-12))
        for x in roots:
            x['y_raw'] = x['y']; x['y'] = x['y'] - alpha * x['phi']
    allA = np.concatenate([x['A'] for x in train] + [x['B'] for x in train])
    mu = allA.mean(0); sd = allA.std(0); sd = np.where(sd < 1e-2, 1., sd).astype(np.float32)
    d = allA.shape[1]
    net = torch.nn.Sequential(torch.nn.Linear(d, a.hidden), torch.nn.ReLU(), torch.nn.Linear(a.hidden, a.hidden),
                              torch.nn.ReLU(), torch.nn.Linear(a.hidden, 1))
    # flatten pairs
    def pairs(rs):
        I, J, Y, A, B = [], [], [], [], []
        off = 0
        for x in rs:
            k = len(x['y'])
            for i, j in combinations(range(k), 2):
                if CONF > 0 and not pair_ok(x, i, j):
                    continue
                I.append(off + i); J.append(off + j); Y.append(x['y'][i] - x['y'][j])
            A.append(x['A']); B.append(x['B']); off += k
        A = torch.tensor((np.concatenate(A) - mu) / sd); B = torch.tensor((np.concatenate(B) - mu) / sd)
        return A, B, torch.tensor(I), torch.tensor(J), torch.tensor(np.array(Y, np.float32))
    tr = pairs(train)
    va = pairs(va_roots)
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr, weight_decay=a.wd)
    best, best_state, best_step = 1e9, None, 0
    gen = torch.Generator().manual_seed(0)

    def loss_on(P, idx=None):
        A, B, I, J, Y = P
        v = (net(A) - net(B)).squeeze(1)
        if idx is not None:
            I, J, Y = I[idx], J[idx], Y[idx]
        return (((v[I] - v[J]) - Y) ** 2).mean()
    for step in range(a.steps):
        idx = torch.randint(0, len(tr[4]), (min(4096, len(tr[4])),), generator=gen)
        loss = loss_on(tr, idx)
        opt.zero_grad(); loss.backward(); opt.step()
        if (step + 1) % 50 == 0:
            with torch.no_grad():
                vl = float(loss_on(va))
            if vl < best:
                best, best_step = vl, step + 1
                best_state = {k: v.detach().clone() for k, v in net.state_dict().items()}
    net.load_state_dict(best_state); net.eval()
    with torch.no_grad():
        for x in roots:
            x['V'] = ((net(torch.tensor((x['A'] - mu) / sd)) - net(torch.tensor((x['B'] - mu) / sd))).squeeze(1)
                      .numpy())
    if a.residual:      # score = a*phi + V against the raw target
        for x in roots:
            x['y'] = x['y_raw']; x['V'] = alpha * x['phi'] + x['V']
    sv = np.median([np.std(x['V'] - alpha * x['phi']) for x in test]); sp = np.median([np.std(x['phi']) for x in test])
    king = [x for x in test if x['king']]
    res = dict(roots=len(roots), train_roots=len(train), test_roots=len(test), king_slice_test_roots=len(king),
               residual=bool(a.residual), alpha=round(alpha, 4),
               best_step=best_step, val_pair_mse=round(best, 6),
               heldout=dict(V=pair_acc(test, 'V'), phi=pair_acc(test, 'phi'), search_score=pair_acc(test, 'score')),
               king_slice=dict(V=pair_acc(king, 'V'), phi=pair_acc(king, 'phi'), search_score=pair_acc(king, 'score')),
               within_root_std=dict(V=round(float(sv), 5), phi=round(float(sp), 5)),
               kappa_max=round(float(.5 * sp / max(sv, 1e-9)), 4),
               by_own_deck={}, by_opponent={})
    for key, field in (('by_own_deck', 'own'), ('by_opponent', 'opp')):
        for g in sorted({x[field] for x in test}):
            rs = [x for x in test if x[field] == g]
            if len(rs) >= 30:
                res[key][g] = dict(roots=len(rs), V=pair_acc(rs, 'V')['acc'], phi=pair_acc(rs, 'phi')['acc'])
    a.out.mkdir(parents=True, exist_ok=True)
    export(a.out / 'sib.npz', 'mlp', net, mu, sd, len(BASE_NAMES), vocab, 1.0,
           dict(data=a.data, target='sibling d30 differences (paired branches)', extras=True, extra_names=EXTRA_NAMES,
                king_r=KING_R, kappa_max=res['kappa_max'], best_step=best_step))
    (a.out / 'fit.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True, help="comma list of sibling_gen out dirs (globs allowed)")
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--steps', type=int, default=4000)
    ap.add_argument('--hidden', type=int, default=128)
    ap.add_argument('--lr', type=float, default=1e-3)
    ap.add_argument('--wd', type=float, default=1e-3)
    ap.add_argument('--residual', action='store_true', help='learn the correction to alpha*phi (score = alpha*phi + V)')
    ap.add_argument('--target', default='d30', choices=['d30', 'mc'],
                    help="'d30': realized branch margin (sibling_gen); 'mc': mean continuation margin (mc_gen)")
    ap.add_argument('--confident', type=float, default=0., help='MC targets: train/score only pairs beyond k SE')
    a = ap.parse_args(argv)
    global CONF
    CONF = a.confident
    a.data = ','.join(d for p in a.data.split(',') for d in (sorted(glob.glob(p)) or [p]))
    fit(a)


if __name__ == '__main__':
    main()
