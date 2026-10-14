"""Search-scaling table: score, paired difference vs K4S-b64, and search cost per arm.

    python -m bot.search.report DIR [DIR ...] [--baseline K4S-b64] [--opponents R3a,v1]

Scores and CIs as bot.eval.summarize (bootstrap over games, 4000 draws, seed 0). The paired
difference is arm - baseline on the same case indices. 'both' = equal-weight mean over the
opponents, bootstrapped by resampling cases within each opponent. Cost columns are the
candidate's own search: CPU s per searched decision and per game (process time in act on
searched polls), and mean single-root rollouts per decision.
"""
from __future__ import annotations

import argparse
import random
from collections import defaultdict

from bot.eval.summarize import ci, load


def pooled(groups, draws=4000, seed=0):
    rng = random.Random(seed)
    point = sum(sum(g) / len(g) for g in groups) / len(groups)
    bs = sorted(sum(sum(g[rng.randrange(len(g))] for _ in g) / len(g) for g in groups) / len(groups)
                for _ in range(draws))
    return point, (bs[int(.025 * draws)], bs[int(.975 * draws) - 1])


def fmt(point, interval, signed=False):
    f = '{:+.3f}' if signed else '{:.3f}'
    return f"{f.format(point)} [{f.format(interval[0])}, {f.format(interval[1])}]"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--baseline', default='K4S-b64')
    ap.add_argument('--opponents', default='R3a,v1')
    a = ap.parse_args()
    opps = a.opponents.split(',')
    by = defaultdict(dict)
    errors = defaultdict(int)
    for r in load(a.dirs):
        if 'error' in r:
            errors[r['candidate']] += 1
        else:
            by[r['candidate'], r['opponent']][r['index']] = r
    arms = sorted({c for c, _ in by}, key=lambda c: (c != a.baseline, c))
    print('| arm | CPU s/decision | CPU s/game | rollouts/decision | '
          + ' | '.join(f'vs {o} (n)' for o in opps) + ' | '
          + ' | '.join(f'paired diff vs {a.baseline}, {o}' for o in opps) + ' | paired diff, both | errors |')
    print('|---' * (5 + 2 * len(opps) + 2) + '|')
    for arm in arms:
        rows = [r for o in opps for r in by.get((arm, o), {}).values()]
        timed = [r['search'] for r in rows if r.get('search')]
        if timed:
            per_dec = sum(s['decision_cpu'] for s in timed) / max(1, sum(s['searched'] for s in timed))
            per_game = sum(s['decision_cpu'] for s in timed) / len(timed)
            rollouts = sum(s['rollouts'] * s['searched'] for s in timed) / max(1, sum(s['searched'] for s in timed))
            cost = f'{per_dec:.3f} | {per_game:.0f} | {rollouts:.1f}'
        else:
            cost = '— | — | —'
        cells, diffs, groups = [], [], []
        for o in opps:
            got = by.get((arm, o), {})
            s = [r['score'] for r in got.values()]
            cells.append(f'{fmt(sum(s) / len(s), ci(s))} ({len(s)})' if s else '—')
            base = by.get((a.baseline, o), {})
            common = sorted(set(got) & set(base))
            if arm == a.baseline or not common:
                diffs.append('—')
                continue
            d = [got[i]['score'] - base[i]['score'] for i in common]
            groups.append(d)
            diffs.append(f'{fmt(sum(d) / len(d), ci(d), True)} ({len(d)})')
        both = fmt(*pooled(groups), True) if len(groups) == len(opps) else '—'
        print(f"| {arm} | {cost} | {' | '.join(cells)} | {' | '.join(diffs)} | {both} | {errors[arm]} |")


if __name__ == '__main__':
    main()
