"""Paired delta of candidate A minus B, per opponent and averaged over opponents per case (exploration).

    python -m bot.exit.mean_delta A_DIR:SUBSTR B_DIR:SUBSTR [--opps v1,R3a]

Per opponent: mean over cases both played of (a - b). Mean row: per case, the average over the listed opponents of
(a - b), over cases where both played every opponent; 5,000-draw bootstrap CI (seed 0; 95% unless --alpha), as bot.exit.report.
Also prints each side's plays per game (the candidate seat's plays) per opponent.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from bot.exit.report import fmt, opp


def boot(xs, draws=5000, alpha=.05):
    rng = random.Random(0); n = len(xs)
    bs = sorted(sum(xs[rng.randrange(n)] for _ in range(n)) / n for _ in range(draws))
    return sum(xs) / n, bs[int(alpha / 2 * draws)], bs[int((1 - alpha / 2) * draws) - 1]


def load(spec):
    d, sub = spec.split(':', 1)
    score, plays = {}, {}
    for p in Path(d).glob('games-*.jsonl'):
        for line in p.read_text().splitlines():
            r = json.loads(line)
            if 'error' in r or sub not in r['candidate']:
                continue
            score.setdefault(r['opponent'], {})[r['index']] = r['score']
            plays.setdefault(r['opponent'], {})[r['index']] = r['plays'][str(r['seat'])]
    return score, plays


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('a'); ap.add_argument('b')
    ap.add_argument('--opps', default='v1,R3a')
    ap.add_argument('--alpha', type=float, default=.05, help='two-sided CI level 1-alpha (Bonferroni: .05/k)')
    a = ap.parse_args()
    (sa, pa), (sb, pb) = load(a.a), load(a.b)
    opps = a.opps.split(',')
    per = {}
    for o in opps:
        ta, tb = opp(sa, o), opp(sb, o)
        common = sorted(set(ta) & set(tb))
        if len(common) < 30:
            print(f'{o}: n={len(common)}'); continue
        d = [ta[i] - tb[i] for i in common]
        qa, qb = opp(pa, o), opp(pb, o)
        print(f'{o}: A {sum(ta[i] for i in common) / len(common):.3f} B {sum(tb[i] for i in common) / len(common):.3f}'
              f' | A-B {fmt(boot(d, alpha=a.alpha))} n={len(common)} | plays/game A {sum(qa[i] for i in common) / len(common):.1f}'
              f' B {sum(qb[i] for i in common) / len(common):.1f}')
        for i, x in zip(common, d):
            per.setdefault(i, {})[o] = x
    xs = [sum(v.values()) / len(v) for v in per.values() if len(v) == len(opps)]
    if len(xs) >= 30:
        print(f'mean({",".join(opps)}): A-B {fmt(boot(xs, alpha=a.alpha))} n_cases={len(xs)}')


if __name__ == '__main__':
    main()
