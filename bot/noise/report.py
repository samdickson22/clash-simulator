"""Paired summary of bot/noise/run.py screens.

    python -m bot.noise.report DIR[,DIR...] --ref 'PERC-emp:LIVED-K4L-R-gs-rw-fc' [--perfect NAME] [--min 0]

Per opponent and arm: n, mean score, paired delta vs --ref on the common (opponent, index) keys with a 95% bootstrap
CI (4000 resamples, seed 0, as bot/eval/pair_by_name.py), and vs --perfect if given; decision timing (pooled wall_ms
percentiles of the per-game p50/p95/p99 are not poolable, so the median of per-game p50/p95/p99 and the default share
over all decisions) and filter counters per game.
"""
from __future__ import annotations

import argparse
import glob
import json
import random
from collections import defaultdict

import numpy as np


def load(dirs):
    rows, errors = {}, defaultdict(int)
    for d in dirs.split(','):
        for p in sorted(glob.glob(d + '/games-*.jsonl')):
            for line in open(p):
                r = json.loads(line)
                if 'error' in r:
                    errors[r['candidate']] += 1
                    continue
                rows[(r['candidate'], r['opponent'], r['index'])] = r
    return rows, errors


def paired(rows, a, b, opp):
    keys = [k[2] for k in rows if k[0] == a and k[1] == opp and (b, opp, k[2]) in rows]
    d = [rows[(a, opp, i)]['score'] - rows[(b, opp, i)]['score'] for i in keys]
    if not d:
        return None
    rng = random.Random(0)
    bs = sorted(sum(rng.choice(d) for _ in d)/len(d) for _ in range(4000))
    return sum(d)/len(d), bs[100], bs[3899], len(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs')
    ap.add_argument('--ref', required=True)
    ap.add_argument('--perfect')
    ap.add_argument('--json')
    a = ap.parse_args()
    rows, errors = load(a.dirs)
    arms = sorted({k[0] for k in rows})
    opps = sorted({k[1] for k in rows})
    out = []
    for opp in opps:
        print(f'== vs {opp}')
        for arm in arms:
            sc = [r['score'] for k, r in rows.items() if k[0] == arm and k[1] == opp]
            if not sc:
                continue
            line = f'{arm:62s} n={len(sc):3d} mean {np.mean(sc):.3f}'
            rec = dict(arm=arm, opponent=opp, n=len(sc), mean=float(np.mean(sc)))
            for tag, ref in (('ref', a.ref), ('perfect', a.perfect)):
                if ref and ref != arm:
                    p = paired(rows, arm, ref, opp)
                    if p:
                        line += f' | d{tag} {p[0]:+.3f} [{p[1]:+.3f}, {p[2]:+.3f}] n={p[3]}'
                        rec[f'd_{tag}'] = p
            decs = [r['dec'] for k, r in rows.items() if k[0] == arm and k[1] == opp and r.get('dec', {}).get('n_search')]
            if decs:
                n = sum(d['n_search'] for d in decs)
                dflt = sum(d.get('default', 0) for d in decs)
                line += (f' | p50/95/99 {np.median([d["p50"] for d in decs]):.0f}/{np.median([d["p95"] for d in decs]):.0f}/'
                         f'{np.median([d["p99"] for d in decs]):.0f} ms default {dflt/max(1, n):.3%}')
                rec.update(default_share=dflt/max(1, n), p50=float(np.median([d['p50'] for d in decs])),
                           p95=float(np.median([d['p95'] for d in decs])), p99=float(np.median([d['p99'] for d in decs])))
            if errors.get(arm):
                line += f' | ERRORS {errors[arm]}'
            print(line)
            out.append(rec)
    if a.json:
        open(a.json, 'w').write(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
