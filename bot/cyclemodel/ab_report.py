"""Paired readout of the cycle-model sim A/B (bot/cyclemodel/ab.py rows, ours_diag schema).

    python -m bot.cyclemodel.ab_report clean=DIR hard=DIR soft=DIR [--json OUT]

Pairs games by (opponent, index) across arms; win rate = mean score (draw 0.5). Paired differences B - A with a normal
95% CI on the per-pair differences (pooled and per opponent). Noise counts per game from the rows' 'noise' (live-diag's
history noise + cyc_* guard counts + belief_* cycle stats), and the sim calibration of P(real): mean p on real vs
phantom conflicts.
"""
from __future__ import annotations

import glob
import json
import math
import sys
from collections import defaultdict


def load(d):
    rows = {}
    for path in sorted(glob.glob(f'{d}/games-*.jsonl')):
        for line in open(path):
            r = json.loads(line)
            if 'error' in r:
                rows.setdefault(('error', r['opponent'], r['index']), r)
                continue
            rows[(r['opponent'], r['index'])] = r
    return rows


def paired(a, b, keys):
    diffs = [b[k]['score'] - a[k]['score'] for k in keys]
    n = len(diffs)
    if not n:
        return None
    m = sum(diffs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in diffs) / max(n - 1, 1))
    h = 1.96 * sd / math.sqrt(n)
    return dict(n=n, a=round(sum(a[k]['score'] for k in keys) / n, 3), b=round(sum(b[k]['score'] for k in keys) / n, 3),
                diff=round(m, 3), lo=round(m - h, 3), hi=round(m + h, 3))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    out = None
    if '--json' in argv:
        i = argv.index('--json')
        out = argv[i + 1]
        del argv[i:i + 2]
    arms = dict(a.split('=', 1) for a in argv)
    data = {k: load(v) for k, v in arms.items()}
    errors = {k: sum(1 for key in v if key[0] == 'error') for k, v in data.items()}
    games = {k: {key: r for key, r in v.items() if key[0] != 'error'} for k, v in data.items()}
    rep = dict(games={k: len(v) for k, v in games.items()}, errors=errors, pairs={})
    names = list(games)
    for i, x in enumerate(names):
        for y in names[i + 1:]:
            keys = sorted(set(games[x]) & set(games[y]))
            res = dict(pooled=paired(games[x], games[y], keys))
            for opp in sorted({k[0] for k in keys}):
                res[opp] = paired(games[x], games[y], [k for k in keys if k[0] == opp])
            rep['pairs'][f'{y}-{x}'] = res
    for k, v in games.items():
        tot = defaultdict(float)
        for r in v.values():
            for nk, nv in (r.get('noise') or {}).items():
                if isinstance(nv, (int, float)):
                    tot[nk] += nv
        n = max(len(v), 1)
        per = {nk: round(nv / n, 3) for nk, nv in sorted(tot.items())}
        real = tot.get('cyc_conflicts', 0) - tot.get('cyc_conflict_phantom', 0)
        if tot.get('cyc_conflicts'):
            per['calib_mean_p_real'] = round(tot['cyc_p_real_sum'] / max(real, 1), 3)
            per['calib_mean_p_phantom'] = round(tot['cyc_p_phantom_sum'] / max(tot['cyc_conflict_phantom'], 1), 3)
            per['conflict_real_share'] = round(real / tot['cyc_conflicts'], 3)
        rep.setdefault('noise_per_game', {})[k] = per
    print(json.dumps(rep, indent=1))
    if out:
        json.dump(rep, open(out, 'w'), indent=1)


if __name__ == '__main__':
    main()
