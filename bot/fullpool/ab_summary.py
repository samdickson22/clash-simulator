"""Summary of the live full-pool switch gate (bank LIVE-AB1): arm B vs arm A, paired by (opponent, case index).

    python -m bot.fullpool.ab_summary DIR [DIR ...] [--a aliased:K4L-R-gs-mpool] [--b K4L-R-gs-mk1a1]

DIRs hold bot.eval.headline games-*.jsonl rows (any hosts' copies merged; duplicates keep the first ok row).
Reports, per opponent and pooled: arm means with n, the paired difference B - A with a 95% bootstrap CI over cases
(10,000 resamples, seed 0), and the same split by the opponent deck: C56-only vs containing off-vocab cards.
Errors are counted per arm; a case enters the paired set only when both arms finished it.
"""
from __future__ import annotations

import argparse
import glob
import json
import random

from bot.fullpool.cards import C56


def load(dirs):
    rows, errors = {}, {}
    for d in dirs:
        for p in sorted(glob.glob(f'{d}/games-*.jsonl')):
            for line in open(p):
                if not line.strip():
                    continue
                r = json.loads(line)
                k = (r['candidate'], r['opponent'], r['index'])
                if 'error' in r:
                    errors.setdefault(r['candidate'], []).append(r['error'][:160])
                    continue
                rows.setdefault(k, r)
    return rows, errors


def ci(d, n=10000):
    if not d:
        return None, None, None
    rng = random.Random(0)
    m = sum(d) / len(d)
    bs = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(n))
    return m, bs[int(.025 * n)], bs[int(.975 * n) - 1]


def opp_deck(r):
    return r['deck_lists'][1 - r['seat']]


def summarize(rows, a, b, opponents=None):
    opps = opponents or sorted({k[1] for k in rows})
    out = []

    def block(label, keys):
        da = [rows[(a, o, i)]['score'] for o, i in keys]
        db = [rows[(b, o, i)]['score'] for o, i in keys]
        m, lo, hi = ci([y - x for x, y in zip(da, db)])
        out.append(dict(row=label, n=len(keys), A=round(sum(da) / len(da), 4) if da else None,
                        B=round(sum(db) / len(db), 4) if db else None,
                        B_minus_A=None if m is None else round(m, 4),
                        ci95=None if m is None else [round(lo, 4), round(hi, 4)]))

    paired = sorted((o, i) for (c, o, i) in rows if c == a and (b, o, i) in rows)
    for o in opps:
        keys = [k for k in paired if k[0] == o]
        block(o, keys)
        c56 = [k for k in keys if all(x in C56 for x in opp_deck(rows[(a,) + k]))]
        off = [k for k in keys if k not in set(c56)]
        block(f'{o} | C56-only decks', c56)
        block(f'{o} | off-vocab decks', off)
    weak = [k for k in paired if k[0] in ('R3a', 'v1')]
    if weak:
        block('pooled R3a+v1', weak)
    block('pooled all', paired)
    c56 = [k for k in paired if all(x in C56 for x in opp_deck(rows[(a,) + k]))]
    block('pooled all | C56-only decks', c56)
    block('pooled all | off-vocab decks', [k for k in paired if k not in set(c56)])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--a', default='aliased:K4L-R-gs-mpool')
    ap.add_argument('--b', default='K4L-R-gs-mk1a1')
    a = ap.parse_args(argv)
    rows, errors = load(a.dirs)
    print(json.dumps(dict(rows=len(rows), errors={k: len(v) for k, v in errors.items()},
                          error_samples={k: v[:2] for k, v in errors.items()}), indent=1))
    for r in summarize(rows, a.a, a.b):
        print(json.dumps(r))


if __name__ == '__main__':
    main()
