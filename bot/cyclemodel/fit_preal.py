"""Fit P(real) v1 (bot/cyclemodel/preal.py logistic) on the translator owner's labelled cycle-conflict drops.

    python -m bot.cyclemodel.fit_preal OUT.json --labels sample1-labels-with-features.json CYCLE-DROPS-SAMPLE2.json

Rows with verdict real/phantom; numeric fields may be strings (sample 2). Duplicate (run, tick, card) rows keep the
first. Sample 2 is stratified by kind, a model feature, so the unweighted fit of P(real | features) is unbiased; rates
per stratum are reported with population weights only for the descriptive table. Reports leave-one-out log loss and
Brier for v0 vs v1 and writes the v1 model (select with BOT_CYCLE_PREAL=OUT.json).
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict

from bot.cyclemodel.preal import fit, p_real, p_v0, stratum

NUM = ('plays_between', 'ticks_since_same', 'spawner_same_family_dist', 'distinct_between', 'revealed', 'cost')


def clean(r):
    r = dict(r)
    for k in NUM:
        v = r.get(k)
        if isinstance(v, str):
            r[k] = None if v in ('', 'None', 'null') else float(v)
    if r.get('plays_between') is not None:
        r['plays_between'] = int(r['plays_between'])
    return r


def scores(rows, ps):
    ll = -sum(math.log(p if r['verdict'] == 'real' else 1 - p) for r, p in zip(rows, ps)) / len(rows)
    br = sum(((1. if r['verdict'] == 'real' else 0.) - p) ** 2 for r, p in zip(rows, ps)) / len(rows)
    return round(ll, 4), round(br, 4)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--labels', nargs='+', required=True)
    ap.add_argument('--l2', type=float, default=1.0)
    a = ap.parse_args(argv)
    rows, seen = [], set()
    for path in a.labels:
        for r in json.load(open(path)):
            if r.get('verdict') not in ('real', 'phantom'):
                continue
            key = (r['run'], int(float(r['tick'])), r['card'])
            if key in seen:
                continue
            seen.add(key)
            rows.append(clean(r))
    model = fit(rows, l2=a.l2)
    loo = []
    for i in range(len(rows)):
        m = fit(rows[:i] + rows[i + 1:], l2=a.l2)
        loo.append(p_real(rows[i], model=m))
    v0 = [p_real(r, model='v0') for r in rows]
    by = defaultdict(Counter)
    for r in rows:
        by[stratum(r)][r['verdict']] += 1
    pb = defaultdict(Counter)
    for r in rows:
        if r.get('kind') == 'troop':
            pb[min(int(r.get('plays_between') or 0), 3)][r['verdict']] += 1
    rep = dict(n=len(rows), verdicts=dict(Counter(r['verdict'] for r in rows)), l2=a.l2,
               loo_logloss_brier=dict(v0=scores(rows, v0), v1=scores(rows, loo)),
               strata={k: dict(v, p_v0=round(p_v0({'kind': 'troop', 'plays_between': 3} if k == 'troop_3plus' else
                                                  {'kind': 'troop', 'plays_between': 0} if k == 'troop_lt3' else
                                                  {'kind': 'building'} if k == 'building' else
                                                  {'kind': 'spawner_family', 'spawner_same_family_dist':
                                                   0. if k == 'spawner_near' else 99.}), 3))
                       for k, v in sorted(by.items())},
               troop_by_plays_between={k: dict(v) for k, v in sorted(pb.items())}, model=model)
    json.dump(model, open(a.out, 'w'), indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == '__main__':
    main()
