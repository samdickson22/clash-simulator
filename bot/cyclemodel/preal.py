"""P(real) for an opponent play that conflicts with the strict cycle (the live translator's cycle-conflict drops).

Input: the translator's LiveTranslator.drop_features(tick, name, x, y) dict (fields as in the labelled files
guardfix/cycle-labels/*.json): kind (troop / building / spawner_family), plays_between, spawner_same_family_dist (tiles,
99 = none), ticks_since_same, distinct_between, revealed, peak, cost.

v0 (default): the translator owner's sample 1 (simple random 40 of the 435 drops in s41-s60, Sol video verdicts: 27
real / 13 phantom), per stratum, smoothed towards the overall 27/40 with prior strength 2:
    building                                  2/3   -> 0.67
    spawner_family, same-family spawner <= 4   0/4   -> 0.23
    spawner_family, otherwise                  7/11  -> 0.64
    troop, plays_between >= 3                  7/7   -> 0.93
    troop, plays_between < 3                  11/15  -> 0.73
v1: a logistic model fitted on sample 1 + sample 2 (stratum-weighted) by `fit`; selected by env
BOT_CYCLE_PREAL=<model.json> (or the `model` argument). The belief takes p as soft evidence (bot/cyclemodel/belief.py).
"""
from __future__ import annotations

import json
import math
import os

PRIOR_REAL, PRIOR_N = 27 / 40, 2.0
V0 = {  # stratum -> (real, n) from sample 1
    'building': (2, 3), 'spawner_near': (0, 4), 'spawner_far': (7, 11), 'troop_3plus': (7, 7), 'troop_lt3': (11, 15)}
P_MIN, P_MAX = 0.02, 0.99
NEAR_TILES = 4.0


def stratum(f):
    kind = f.get('kind', 'troop')
    if kind == 'building':
        return 'building'
    if kind == 'spawner_family':
        return 'spawner_near' if float(f.get('spawner_same_family_dist', 99.)) <= NEAR_TILES else 'spawner_far'
    return 'troop_3plus' if int(f.get('plays_between', 0)) >= 3 else 'troop_lt3'


def p_v0(f):
    real, n = V0[stratum(f)]
    return (real + PRIOR_N * PRIOR_REAL) / (n + PRIOR_N)


def features_vector(f):
    """Logistic features (v1): kind one-hot, plays_between one-hot (0..3+), near-spawner flag, log ticks_since_same."""
    kind = f.get('kind', 'troop')
    pb = min(int(f.get('plays_between', 0)), 3)
    near = float(f.get('spawner_same_family_dist', 99.)) <= NEAR_TILES
    tss = f.get('ticks_since_same')
    tss = 10. ** 6 if tss is None else max(float(tss), 1.)        # None: no earlier accepted play of this card
    return [1., float(kind == 'building'), float(kind == 'spawner_family'), float(kind == 'spawner_family' and near),
            float(pb == 1), float(pb == 2), float(pb >= 3), math.log(tss / 400.)]


FEATURES = ('bias', 'building', 'spawner_family', 'spawner_near', 'pb1', 'pb2', 'pb3plus', 'log_tss_400')


def fit(rows, weights=None, l2=1.0, iters=2000, lr=0.1):
    """rows: dicts with the features + 'verdict' ('real'/'phantom'); weights: per-row population weights. Returns the
    model dict {'kind': 'logistic', 'features': [...], 'coef': [...], 'n': n}."""
    import numpy as np
    X = np.asarray([features_vector(r) for r in rows], dtype=np.float64)
    y = np.asarray([1. if r['verdict'] == 'real' else 0. for r in rows])
    w = np.ones(len(rows)) if weights is None else np.asarray(weights, dtype=np.float64)
    w = w * len(w) / w.sum()
    b = np.zeros(X.shape[1])
    reg = np.full(X.shape[1], l2); reg[0] = 0.
    for _ in range(iters):
        p = 1. / (1. + np.exp(-X @ b))
        g = X.T @ (w * (p - y)) / len(y) + reg * b / len(y)
        H = (X * (w * p * (1 - p))[:, None]).T @ X / len(y) + np.diag(reg) / len(y)
        step = np.linalg.solve(H + 1e-9 * np.eye(len(b)), g)
        b -= step
        if np.abs(step).max() < 1e-10:
            break
    return dict(kind='logistic', features=list(FEATURES), coef=[float(x) for x in b], n=len(rows))


_MODEL = {}


def load(path):
    if path not in _MODEL:
        _MODEL[path] = json.loads(open(path).read())
    return _MODEL[path]


def p_real(features, model=None):
    """P(the conflicting play is a real opponent deployment) in [P_MIN, P_MAX]."""
    model = model or os.environ.get('BOT_CYCLE_PREAL') or None
    if model is None or model == 'v0':
        p = p_v0(features)
    else:
        m = load(model) if isinstance(model, str) else model
        if m.get('kind') != 'logistic' or tuple(m['features']) != FEATURES:
            raise ValueError('unknown P(real) model')
        z = sum(c * x for c, x in zip(m['coef'], features_vector(features)))
        p = 1. / (1. + math.exp(-z)) if z >= 0 else math.exp(z) / (1. + math.exp(z))    # stable sigmoid
    return min(P_MAX, max(P_MIN, p))
