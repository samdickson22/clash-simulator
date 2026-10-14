"""Summarise royalesim_run JSONL: A's win/loss/draw per (engine, A, B), and the RoyaleSim-vs-ours
difference paired by game index when both engines played the same indices.

    .venv/bin/python -m bot.players.royalesim_summary OUT/*.jsonl
"""
from __future__ import annotations

import json
import math
import random
import sys
from collections import defaultdict


def wilson(k, n, z=1.96):
    if not n:
        return (float('nan'), float('nan'))
    p = k/n
    d = 1 + z*z/n
    c = (p + z*z/(2*n))/d
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return (100*(c-h), 100*(c+h))


def main(paths):
    games = {}
    for path in paths:
        for line in open(path):
            r = json.loads(line)
            if r.get('repeat', 0):
                continue
            games[(r['engine_arm'], r['a'], r['b'], r['index'])] = r
    arms = defaultdict(dict)
    for (engine, a, b, index), r in games.items():
        arms[(engine, a, b)][index] = r['a_outcome']
    out = {}
    for (engine, a, b), res in sorted(arms.items()):
        n = len(res)
        loss, win = sum(v == 'loss' for v in res.values()), sum(v == 'win' for v in res.values())
        out[f'{engine} | {a} vs {b}'] = dict(n=n, loss_pct=round(100*loss/n, 2), loss_ci95=[round(x, 2) for x in wilson(loss, n)],
                                             win_pct=round(100*win/n, 2), draws=n-loss-win)
    rsim = [k for k in arms if k[0].startswith('rsim')]
    for key in rsim:
        other = ('ours', key[1], key[2])
        if other not in arms:
            continue
        common = sorted(set(arms[key]) & set(arms[other]))
        if not common:
            continue
        d = [float(arms[key][i] == 'loss') - float(arms[other][i] == 'loss') for i in common]
        rng = random.Random(0)
        boots = sorted(sum(rng.choice(d) for _ in d)/len(d) for _ in range(5000))
        out[f'paired loss {key[0]} - ours | {key[1]} vs {key[2]}'] = dict(
            n=len(common), diff_pp=round(100*sum(d)/len(d), 2),
            ci95_pp=[round(100*boots[124], 2), round(100*boots[4874], 2)],
            agree=sum(arms[key][i] == arms[other][i] for i in common))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main(sys.argv[1:])
