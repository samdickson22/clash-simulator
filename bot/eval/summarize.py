"""Summarize headline-style game logs.

    python -m bot.eval.summarize DIR [DIR ...] [--paired A,B]

Per (candidate, opponent): games, mean score (win 1 / draw 0.5), 95% CI (bootstrap over games, 4000 draws, seed 0),
W/D/L, seat split, mean plays. Pool mean = unweighted mean over opponents with a bootstrap that resamples games
within each opponent. --paired A,B: per-opponent paired difference of candidates A and B on the same case indices.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from statistics import median

REACTION_METRICS = ('reaction_p50_s', 'reaction_p90_s', 'enemy_plays', 'undefended_share')


def reaction_summary(rows, draws=4000, seed=0):
    """Median of per-game diagnostics, with a 95% bootstrap CI within opponent.

    Old rows lacking metrics and null latencies (no matched searched decisions)
    are excluded per metric; n/missing make that coverage explicit. Each game has
    equal weight in the median; this is separate from the equal-opponent score.
    """
    rows = [r for r in rows if 'error' not in r]
    out = {}
    for field in REACTION_METRICS:
        groups = defaultdict(list)
        for r in rows:
            if r.get(field) is not None:
                groups[r['opponent']].append(r[field])
        groups = [groups[o] for o in sorted(groups)]
        values = [x for g in groups for x in g]
        if not values:
            out[field] = dict(n=0, missing=len(rows), median=None, ci=None)
            continue
        rng = random.Random(seed)
        bs = sorted(median([rng.choice(g) for g in groups for _ in g]) for _ in range(draws))
        out[field] = dict(n=len(values), missing=len(rows) - len(values), median=median(values),
                          ci=(bs[int(.025 * draws)], bs[int(.975 * draws) - 1]))
    return out


def load(dirs):
    rows = {}
    for d in dirs:
        for p in sorted(Path(d).glob('games-*.jsonl')):
            for line in p.read_text().splitlines():
                r = json.loads(line)
                rows[(r['candidate'], r['opponent'], r['index'])] = r
    return list(rows.values())


def ci(xs, draws=4000, seed=0):
    rng = random.Random(seed)
    n = len(xs)
    bs = sorted(sum(xs[rng.randrange(n)] for _ in range(n)) / n for _ in range(draws))
    return bs[int(0.025 * draws)], bs[int(0.975 * draws) - 1]


def summarize(rows):
    by = defaultdict(list)
    errors = defaultdict(int)
    for r in rows:
        if 'error' in r:
            errors[(r['candidate'], r['opponent'])] += 1
        else:
            by[(r['candidate'], r['opponent'])].append(r)
    out = {}
    for (c, o), rs in sorted(by.items()):
        s = [r['score'] for r in rs]
        cand_plays = [r['plays'][str(r['seat'])] for r in rs]
        out[(c, o)] = dict(games=len(s), mean=sum(s) / len(s), ci=ci(s), wins=sum(x == 1 for x in s),
                           draws=sum(x == 0.5 for x in s), losses=sum(x == 0 for x in s),
                           seat0=sum(r['score'] for r in rs if r['seat'] == 0) / max(1, sum(r['seat'] == 0 for r in rs)),
                           seat1=sum(r['score'] for r in rs if r['seat'] == 1) / max(1, sum(r['seat'] == 1 for r in rs)),
                           plays=sum(cand_plays) / len(cand_plays), errors=errors[(c, o)],
                           cpu=sum(r['cpu_seconds'] for r in rs) / len(rs))
        out[(c, o)]['reaction'] = reaction_summary(rs)
    return out, by


def pool_mean(by, cand, opps, draws=4000, seed=0):
    rng = random.Random(seed)
    groups = [[r['score'] for r in by[(cand, o)]] for o in opps if by.get((cand, o))]
    point = sum(sum(g) / len(g) for g in groups) / len(groups)
    bs = []
    for _ in range(draws):
        bs.append(sum(sum(g[rng.randrange(len(g))] for _ in g) / len(g) for g in groups) / len(groups))
    bs.sort()
    return point, (bs[int(0.025 * draws)], bs[int(0.975 * draws) - 1]), len(groups)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--paired', default='')
    a = ap.parse_args()
    rows = load(a.dirs)
    out, by = summarize(rows)
    print('| candidate | opponent | games | score | 95% CI | W-D-L | seat0 / seat1 | cand plays/game | CPU s/game | errors |')
    print('|---|---|---:|---:|---|---|---|---:|---:|---:|')
    for (c, o), s in out.items():
        print(f"| {c} | {o} | {s['games']} | {s['mean']:.3f} | [{s['ci'][0]:.3f}, {s['ci'][1]:.3f}] | "
              f"{s['wins']}-{s['draws']}-{s['losses']} | {s['seat0']:.2f} / {s['seat1']:.2f} | {s['plays']:.1f} | {s['cpu']:.0f} | {s['errors']} |")
    for c in sorted({c for c, _ in out}):
        opps = sorted({o for cc, o in out if cc == c})
        p, (lo, hi), n = pool_mean(by, c, opps)
        print(f"POOL {c}: {p:.3f} [{lo:.3f}, {hi:.3f}] over {n} opponents ({', '.join(opps)})")
    print('\nPer-player medians of per-game diagnostics (95% bootstrap CI within opponent; n/missing):')
    for c in sorted({c for c, _ in out}):
        metrics = reaction_summary([r for (cc, _), rs in by.items() if cc == c for r in rs])
        for field, s in metrics.items():
            value = ('unavailable' if s['median'] is None else
                     f"{s['median']:.3f} [{s['ci'][0]:.3f}, {s['ci'][1]:.3f}]")
            print(f"DIAGNOSTIC {c} {field}: {value} (n={s['n']}, missing={s['missing']})")
    if a.paired:
        A, B = a.paired.split(',')
        for o in sorted({o for _, o in out}):
            ra = {r['index']: r['score'] for r in by.get((A, o), [])}
            rb = {r['index']: r['score'] for r in by.get((B, o), [])}
            common = sorted(set(ra) & set(rb))
            if not common:
                continue
            d = [rb[i] - ra[i] for i in common]
            lo, hi = ci(d)
            print(f"PAIRED {B} - {A} vs {o}: {sum(d)/len(d):+.3f} [{lo:+.3f}, {hi:+.3f}] over {len(d)} cases")


if __name__ == '__main__':
    main()
