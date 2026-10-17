"""Fit the learned hold-back term from option-2 paired roots (bot/livediag/dumpbank_gen.py; bot lead live-diag).

    python3 -m bot.livediag.dumpbank_fit ROOTS_DIR [ROOTS_DIR ...] --out MODEL.json [--player LD-K4L-R-gs-rw-rh]

Rows: one per picked root with a binding reserve window (reserve_branch.overrides > 0; without an override the two
branches are the same game). Target y = (score_free - score_reserve) + 0.25 * (margin_free - margin_reserve), where
margin = (own - enemy crowns)/3 + (own - enemy summed tower HP)/15000 at the end (most games are wins, so the score
difference alone is sparse). y > 0: spending freely was better than holding a reserve from this root.
Features (fair: the root's public view and own hand only; the opponent's identity is NOT a feature):
  elixir, elixir after the best play, cost of the best play, enemy elixir estimate, enemy units on board, time
  (progress, double, overtime), tower fractions (own L/R/K, enemy L/R/K), Giant / Fireball in hand, cheap (<=3)
  ground answers in hand, the search's own score gap (best play - best wait).
Model: ridge regression (standardised features, lambda by 5-fold CV over GAMES), reported with held-out-game
correlation and a sign-agreement rate; coefficients are written in raw feature units for the player-side term.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

COST = dict(Valkyrie=4, Archers=3, Minions=3, Cannon=3, Fireball=4, Giant=5, MiniPekka=4, Musketeer=4)
CHEAP_GROUND = ('Archers', 'Cannon', 'Minions')
NAMES = ('elixir', 'elixir_after', 'play_cost', 'opp_elixir', 'enemy_units', 'progress', 'double', 'overtime',
         'own_l', 'own_r', 'own_k', 'opp_l', 'opp_r', 'opp_k', 'giant_in_hand', 'fireball_in_hand', 'cheap_answers',
         'score_gap')


V2 = ('below_reserve', 'opp_can_push', 'elixir_x_double')


def v2_extra(f, reserve=3.):
    """lc v2 features from the v1 dict: shortfall below the reserve after the play, the enemy can afford a 5-cost push,
    and elixir in double elixir (spending is cheaper to refill there)."""
    return dict(below_reserve=max(0., reserve - f['elixir_after']), opp_can_push=float(f['opp_elixir'] >= 5),
                elixir_x_double=f['elixir'] * f['double'])


def features(root):
    gf, hand = root['gf'], root['hand']
    elixir = gf[5] * 10
    cost = COST.get(root['dump_card'], 4)
    opp = root.get('opp_elixir')
    return [elixir, elixir - cost, cost, opp if opp is not None else 5., root.get('n_enemy_units', 0), gf[0], gf[2],
            gf[4], gf[8], gf[9], gf[10], gf[11], gf[12], gf[13], float('Giant' in hand), float('Fireball' in hand),
            float(sum(1 for c in hand if c in CHEAP_GROUND)),
            root['dump_score'] - max(root['wait_score'], root.get('timed_wait_score') or -9)]


def margin(res, seat):
    """(own - enemy crowns)/3 + (own - enemy summed tower HP)/15000 at the end (RoyaleSim tower_hp, level 11)."""
    t, c = res['towers'], res.get('crowns') or {}
    get = lambda d, k: d[str(k)] if str(k) in d else d[k]
    hp = sum(get(t, seat)) - sum(get(t, 1 - seat))
    cr = (get(c, seat) - get(c, 1 - seat)) if c else 0
    return cr / 3 + hp / 15000


def margin_at(series, tick):
    """Margin at the last series point <= tick (None without a series)."""
    pts = [x for x in series or () if x[0] <= tick]
    if not pts:
        return None
    _, own, opp, c0, c1, _ = pts[-1]
    return (c0 - c1) / 3 + (sum(own) - sum(opp)) / 15000


def load(dirs, player=None, target='final'):
    rows = []
    for d in dirs:
        for p in Path(d).glob('roots-*.jsonl'):
            for line in p.read_text().splitlines():
                g = json.loads(line)
                if 'error' in g or (player and g.get('player', 'LD-K4L-R-gs-rw') != player):
                    continue
                for r in g['roots']:
                    if not r.get('replay_ok') or not r['reserve_branch'].get('overrides'):
                        continue
                    seat = r['seat']
                    if target == 'final':
                        y = (r['free']['score'] - r['reserve']['score']) + 0.25 * (
                            margin(r['free'], seat) - margin(r['reserve'], seat))
                    else:                   # h<T>: short-horizon margin T ticks after the root (lower variance)
                        t = r['root']['tick'] + int(target[1:])
                        a, b = margin_at(r['free'].get('series'), t), margin_at(r['reserve'].get('series'), t)
                        if a is None or b is None:
                            continue
                        y = a - b
                    rows.append(dict(game=(g['base'], g['index']), x=features(r['root']), y=y,
                                     dscore=r['free']['score'] - r['reserve']['score'], opponent=r['opponent']))
    return rows


def ridge(X, y, lam, wt=None):
    import numpy as np
    X, y = np.asarray(X), np.asarray(y)
    wt = np.ones(len(y)) if wt is None else np.asarray(wt)
    mu, sd = np.average(X, 0, wt), np.sqrt(np.average((X - np.average(X, 0, wt)) ** 2, 0, wt)) + 1e-9
    Z = (X - mu) / sd
    Z1 = np.hstack([Z, np.ones((len(Z), 1))])
    reg = lam * np.eye(Z1.shape[1]); reg[-1, -1] = 0
    W = Z1 * wt[:, None]
    w = np.linalg.solve(W.T @ Z1 + reg, W.T @ y)
    return mu, sd, w


def predict(model, X):
    import numpy as np
    mu, sd, w = model
    Z = (np.asarray(X) - mu) / sd
    return Z @ w[:-1] + w[-1]


def main():
    import numpy as np
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--out', required=True)
    ap.add_argument('--player', default=None)
    ap.add_argument('--v2', action='store_true', help='append the lc v2 features (V2)')
    ap.add_argument('--drop', default='', help='comma list of features to drop (deployed term: score_gap)')
    ap.add_argument('--target', default='final', help="'final' (game outcome + margin) or 'h<T>' (margin T ticks after the root)")
    ap.add_argument('--strong-weight', type=float, default=3.,
                    help='row weight of LIVE-K4CW-r16 games (bot lead: do not learn "rext-bc says spend")')
    a = ap.parse_args()
    rows = load(a.dirs, a.player, a.target)
    games = sorted({r['game'] for r in rows})
    rng = random.Random(0)
    rng.shuffle(games)
    fold = {g: i % 5 for i, g in enumerate(games)}
    if a.v2:
        for r in rows:
            f = dict(zip(NAMES, r['x']))
            e = v2_extra(f)
            r['x'] = list(r['x']) + [e[k] for k in V2]
    allnames = list(NAMES) + (list(V2) if a.v2 else [])
    keep = [i for i, n in enumerate(allnames) if n not in a.drop.split(',')]
    names = [allnames[i] for i in keep]
    X = np.array([[r['x'][i] for i in keep] for r in rows]); y = np.array([r['y'] for r in rows])
    wt = np.array([a.strong_weight if r['opponent'] == 'LIVE-K4CW-r16' else 1. for r in rows])
    best = None
    for lam in (0.1, 1, 10, 100, 1000):
        pred = np.zeros(len(rows))
        for k in range(5):
            tr = np.array([fold[r['game']] != k for r in rows]); te = ~tr
            if tr.sum() < 20 or te.sum() == 0:
                continue
            pred[te] = predict(ridge(X[tr], y[tr], lam, wt[tr]), X[te])
        corr = float(np.corrcoef(pred, y)[0, 1]) if y.std() > 0 else 0.
        strong = np.array([r['opponent'] == 'LIVE-K4CW-r16' for r in rows])
        corr_strong = float(np.corrcoef(pred[strong], y[strong])[0, 1]) if strong.sum() > 5 and y[strong].std() > 0 else None
        if best is None or corr > best[1]:
            best = (lam, corr, pred.copy(), corr_strong)
    lam, corr, pred, corr_strong = best
    nz = y != 0
    sign = float(np.mean(np.sign(pred[nz]) == np.sign(y[nz]))) if nz.any() else None
    mu, sd, w = ridge(X, y, lam, wt)
    raw = (w[:-1] / sd).tolist()
    intercept = float(w[-1] - (w[:-1] / sd) @ mu)
    out = dict(rows=len(rows), games=len(games), nonzero=int(nz.sum()), y_mean=float(y.mean()),
               dscore_mean=float(np.mean([r['dscore'] for r in rows])),
               by_opponent={o: dict(n=sum(1 for r in rows if r['opponent'] == o),
                                    y_mean=float(np.mean([r['y'] for r in rows if r['opponent'] == o])))
                            for o in sorted({r['opponent'] for r in rows})},
               target=a.target, lam=lam, cv_corr=corr, cv_corr_strong=corr_strong, cv_sign_agreement=sign, strong_weight=a.strong_weight, features=names,
               coef_raw=dict(zip(names, raw)), intercept=intercept,
               coef_std=dict(zip(names, w[:-1].tolist())))
    Path(a.out).write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps({k: v for k, v in out.items() if k not in ('coef_raw',)}, indent=1))


if __name__ == '__main__':
    main()
