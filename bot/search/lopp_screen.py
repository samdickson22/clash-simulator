"""Paired screen vs a multi-run reference (exploration).

    python -m bot.search.lopp_screen DIR [DIR ...] --refs K4L-R-gs,K4L-R-gs-rw-S1,K4L-R-gs-rw-S2 [--opponents R3a,v1]

A single reference run is one draw of the reference's luck on these cases: a reseeded copy of the same algorithm
(token S<j>) scored -0.027 against it on HEADLINE 0-299. Here each arm is paired against the MEAN score of several
equal-strength reference runs on the same case (cases where every reference run and the arm have a game), and
each reference run is also paired against the mean of the others (its own luck). Bootstrap over cases within each
opponent (4000 draws, seed 0); pooled = equal weight per opponent, as bot.search.report.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path


def load(dirs):
    by = defaultdict(dict)        # (candidate, opponent) -> {index: score}
    for d in dirs:
        for f in Path(d).glob('games-*.jsonl'):
            for line in open(f):
                r = json.loads(line)
                if 'score' in r:
                    by[r['candidate'], r['opponent']][r['index']] = r['score']
    return by


def pooled_diff(per_opp, draws=4000, seed=0):
    """per_opp: {opponent: [diff per case]} -> point, (lo, hi)."""
    rng = random.Random(seed)
    groups = [g for g in per_opp.values() if g]
    point = sum(sum(g) / len(g) for g in groups) / len(groups)
    bs = sorted(sum(sum(g[rng.randrange(len(g))] for _ in g) / len(g) for g in groups) / len(groups)
                for _ in range(draws))
    return point, (bs[int(.025 * draws)], bs[int(.975 * draws) - 1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--refs', required=True)
    ap.add_argument('--opponents', default='R3a,v1')
    a = ap.parse_args()
    by = load(a.dirs)
    refs, opps = a.refs.split(','), a.opponents.split(',')
    arms = sorted({c for c, _ in by})
    for arm in arms:
        per, n = {}, {}
        if not [r for r in refs if r != arm]:
            continue                  # the only reference run: nothing to pair it with
        for o in opps:
            others = [r for r in refs if r != arm]
            idx = set(by.get((arm, o), {}))
            for r in others:
                idx &= set(by.get((r, o), {}))
            per[o] = [by[arm, o][i] - sum(by[r, o][i] for r in others) / len(others) for i in sorted(idx)]
            n[o] = len(idx)
        if not all(per.values()):
            continue
        point, (lo, hi) = pooled_diff(per)
        each = ' '.join(f'{o} {sum(per[o]) / len(per[o]):+.3f} (n={n[o]})' for o in opps)
        tag = ' [reference run vs the other refs]' if arm in refs else ''
        print(f'{arm:34s} {point:+.3f} [{lo:+.3f}, {hi:+.3f}]  {each}{tag}')


if __name__ == '__main__':
    main()
