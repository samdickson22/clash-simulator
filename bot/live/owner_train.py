"""Train the learned temporal owner (bot/live/owner_track.py) on owner_dataset rows; pick theta on training CV only;
export to the dependency-free trees format (bot/live/playdet/trees.py). Needs lightgbm (playdet venv).

theta: P(opponent) >= theta -> opponent. Chosen on 5-fold CV by run (exact labelled frames) as the value with the
fewest enemy->ours errors among those whose ours->enemy rate is no worse than the detector's own.

    python -m bot.live.owner_train --train train.npz [--val val.npz] [--test test.npz] --out owner-model.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

from bot.live.owner_track import NAMES
from bot.live.playdet.trees import Trees, from_lightgbm

PARAMS = dict(objective='binary', learning_rate=.05, num_leaves=15, max_depth=4, min_data_in_leaf=50,
              feature_fraction=.9, bagging_fraction=.9, bagging_freq=1, lambda_l2=1., verbose=-1, seed=0,
              deterministic=True, force_row_wise=True)


def weights(d, us_weight):
    tid = np.char.add(np.char.add(d['run'], d['battle'].astype(str)), d['track'].astype(str))
    c = Counter(tid)
    w = np.array([1./c[t] for t in tid])
    return w*np.where(d['y'] == 0, us_weight, 1.)


def confusion(y, pred):
    opp, us = y == 1, y == 0
    return dict(n=int(len(y)), opp=int(opp.sum()), us=int(us.sum()),
                enemy_as_ours=int((pred[opp] == 0).sum()), ours_as_enemy=int((pred[us] == 1).sum()),
                enemy_as_ours_rate=round(float((pred[opp] == 0).mean()), 4) if opp.any() else None,
                ours_as_enemy_rate=round(float((pred[us] == 1).mean()), 4) if us.any() else None,
                accuracy=round(float((pred == y).mean()), 4))


def main(argv=None):
    import lightgbm as lgb
    ap = argparse.ArgumentParser()
    ap.add_argument('--train', required=True)
    ap.add_argument('--val')
    ap.add_argument('--test')
    ap.add_argument('--out', required=True)
    ap.add_argument('--trees', type=int, default=200)
    ap.add_argument('--us-weight', type=float, default=2.)
    ap.add_argument('--threads', type=int, default=2)
    ap.add_argument('--own-penalty', type=float, default=0.,
                    help='>0: theta minimises enemy->ours + own_penalty * ours->enemy on CV (instead of the detector bound)')
    ap.add_argument('--constant-features', default='',
                    help='comma-separated features held constant in training (the model learns to ignore them)')
    a = ap.parse_args(argv)
    P = dict(PARAMS, num_threads=a.threads)
    tr = dict(np.load(a.train))
    assert list(tr['names']) == list(NAMES), 'dataset features differ from owner_track.NAMES'
    const = [c for c in a.constant_features.split(',') if c]
    for c in const:
        tr['X'] = tr['X'].copy()
        tr['X'][:, NAMES.index(c)] = 0.
    w = weights(tr, a.us_weight)
    runs = np.unique(tr['run'])
    pcv = np.zeros(len(tr['y']))
    for k in range(5):
        te = np.isin(tr['run'], runs[k::5])
        b = lgb.train(P, lgb.Dataset(tr['X'][~te], tr['y'][~te], weight=w[~te], feature_name=list(NAMES)),
                      num_boost_round=a.trees)
        pcv[te] = b.predict(tr['X'][te])
    ex = tr['exact']
    y, det = tr['y'][ex], tr['det'][ex]
    base = confusion(y, det)
    best = None
    for th in np.round(np.arange(.2, .96, .05), 2):
        c = confusion(y, (pcv[ex] >= th).astype(int))
        if a.own_penalty > 0:
            cost = c['enemy_as_ours'] + a.own_penalty*c['ours_as_enemy']
            if best is None or cost < best[2]:
                best = (float(th), c, cost)
        elif c['ours_as_enemy'] <= base['ours_as_enemy'] and (best is None or c['enemy_as_ours'] < best[1]['enemy_as_ours']):
            best = (float(th), c, 0.)
    if best is None:
        raise SystemExit('no theta keeps ours->enemy at the detector level on CV')
    theta = best[0]
    b = lgb.train(P, lgb.Dataset(tr['X'], tr['y'], weight=w, feature_name=list(NAMES)), num_boost_round=a.trees)
    model = from_lightgbm(b.dump_model(), NAMES)
    model['theta'] = theta
    Path(a.out).write_text(json.dumps(model))
    walker = Trees(model)
    out = dict(model=a.out, theta=theta, us_weight=a.us_weight, own_penalty=a.own_penalty, constant_features=const,
               trees=a.trees, train_rows=int(len(tr['y'])),
               cv=dict(detector=base, model=best[1]))
    for name, path in (('val', a.val), ('test', a.test)):
        if not path:
            continue
        d = np.load(path)
        e = d['exact']
        p = np.array([walker.prob(x) for x in d['X'][e]])
        out[name] = dict(detector=confusion(d['y'][e], d['det'][e]), model=confusion(d['y'][e], (p >= theta).astype(int)),
                         walker_vs_lgb=float(np.abs(p - b.predict(d['X'][e])).max()))
    g = b.feature_importance('gain')
    out['top_features'] = [(NAMES[i], round(float(g[i]))) for i in np.argsort(-g)[:12]]
    Path(a.out + '.report.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    sys.exit(main())
