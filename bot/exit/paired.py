"""Paired difference of two candidates' HEADLINE scores vs one opponent, across result dirs (names may differ).

    python -m bot.exit.paired --a DIR_A:CAND_SUBSTR --b DIR_B:CAND_SUBSTR --opponent v1

CAND_SUBSTR '=NAME' matches the candidate name exactly. Pairs games by case index; prints mean(b - a) with a 5,000-draw bootstrap 95% CI (seed 0).
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def load(spec, opponent):
    d, sub = spec.split(':', 1)
    out = {}
    for p in Path(d).glob('games-*.jsonl'):
        for line in p.read_text().splitlines():
            r = json.loads(line)
            match = r['candidate'] == sub[1:] if sub.startswith('=') else sub in r['candidate']
            if 'error' not in r and r['opponent'] == opponent and match:
                out[r['index']] = r['score']
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--a', required=True); ap.add_argument('--b', required=True)
    ap.add_argument('--opponent', default='v1'); ap.add_argument('--draws', type=int, default=5000)
    a = ap.parse_args()
    ra, rb = load(a.a, a.opponent), load(a.b, a.opponent)
    common = sorted(set(ra) & set(rb))
    d = [rb[i] - ra[i] for i in common]
    rng = random.Random(0); n = len(d)
    bs = sorted(sum(d[rng.randrange(n)] for _ in range(n)) / n for _ in range(a.draws))
    print(json.dumps(dict(opponent=a.opponent, cases=n, a_mean=sum(ra[i] for i in common) / n,
                          b_mean=sum(rb[i] for i in common) / n, diff=sum(d) / n,
                          ci=[bs[int(.025 * a.draws)], bs[int(.975 * a.draws) - 1]])))


if __name__ == '__main__':
    main()
