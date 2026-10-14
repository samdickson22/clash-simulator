"""One results row per candidate: scores vs each opponent and paired deltas vs a reference candidate (exploration).

    python -m bot.exit.report --ref DIR:SUBSTR [--ref2 DIR:SUBSTR] CAND_DIR:SUBSTR [CAND_DIR:SUBSTR ...]

Scores: mean over HEADLINE cases with a 5,000-draw bootstrap 95% CI (seed 0). Opponents are matched by substring
(v1 and R3a exactly; 'h2h:<substr>' for student opponents). Paired deltas (cand - ref) use the cases both played.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def rows(spec):
    d, sub = spec.split(':', 1)
    out = {}
    for p in Path(d).glob('games-*.jsonl'):
        for line in p.read_text().splitlines():
            r = json.loads(line)
            if 'error' in r or sub not in r['candidate']:
                continue
            out.setdefault(r['opponent'], {})[r['index']] = r['score']
    return out


def boot(xs, draws=5000):
    rng = random.Random(0); n = len(xs)
    bs = sorted(sum(xs[rng.randrange(n)] for _ in range(n)) / n for _ in range(draws))
    return sum(xs) / n, bs[int(.025 * draws)], bs[int(.975 * draws) - 1]


def opp(table, key):
    if key in ('v1', 'R3a', 'rext-bc'):
        return table.get(key, {})
    hits = [v for k, v in table.items() if key in k and k not in ('v1', 'R3a')]
    return hits[0] if len(hits) == 1 else {}


def fmt(t):
    return f'{t[0]:.3f} [{t[1]:.3f}, {t[2]:.3f}]'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cands', nargs='+')
    ap.add_argument('--ref', required=True)
    ap.add_argument('--opps', default='v1,R3a,ckpt-it2D,Kall,it5s2')
    a = ap.parse_args()
    ref = rows(a.ref)
    for spec in a.cands:
        t = rows(spec)
        parts = [spec.split(':', 1)[1]]
        for o in a.opps.split(','):
            s = opp(t, o)
            if len(s) < 30:
                parts.append(f'{o}: n={len(s)}'); continue
            cell = f'{o}: {fmt(boot(list(s.values())))} n={len(s)}'
            r = opp(ref, o)
            common = sorted(set(s) & set(r))
            if o in ('v1', 'R3a', 'rext-bc') and len(common) >= 30:
                cell += f' | Δref {fmt(boot([s[i] - r[i] for i in common]))}'
            parts.append(cell)
        print(' ; '.join(parts))


if __name__ == '__main__':
    main()
