"""Paired HEADLINE diffs of value-search arms vs a baseline candidate, by case (exploration).

    python -m bot.value.report --base-dirs D1,D2 --base K4S-st --dirs D3,D4 [--opponents R3a,v1]

For every candidate found in --dirs: score per opponent, paired diff vs the baseline on the same
(opponent, index), "both" = equal-weight mean over opponents (cases resampled within opponent,
4,000 bootstrap draws, 95% percentile CI), plus cost (CPU s per searched decision, rollouts per
decision, both from bot.search.run rows when present) and the V diagnostics (changed rate).
"""
from __future__ import annotations

import argparse
import glob
import json
import random
from collections import defaultdict


def rows(dirs):
    out = defaultdict(dict)
    for d in dirs.split(','):
        for p in glob.glob(d + '/games-*.jsonl'):
            for line in open(p):
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if 'error' in r:
                    continue
                out[r['candidate']][(r['opponent'], r['index'])] = r
    return out


def boot(diffs_by_opp, n=4000, seed=0):
    rng = random.Random(seed)
    opps = list(diffs_by_opp)
    draws = []
    for _ in range(n):
        draws.append(sum(sum(rng.choice(d) for _ in d)/len(d) for d in diffs_by_opp.values())/len(opps))
    draws.sort()
    return draws[int(.025*n)], draws[int(.975*n)-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base-dirs', required=True)
    ap.add_argument('--base', default='K4S-st')
    ap.add_argument('--dirs', required=True)
    ap.add_argument('--opponents', default='R3a,v1')
    ap.add_argument('--md', action='store_true')
    a = ap.parse_args()
    base = rows(a.base_dirs)[a.base]
    opps = a.opponents.split(',')
    for cand, rs in sorted(rows(a.dirs).items()):
        if cand == a.base:
            continue
        line, by = [cand], {}
        for o in opps:
            keys = [k for k in rs if k[0] == o and k in base]
            if not keys:
                continue
            d = [rs[k]['score'] - base[k]['score'] for k in keys]
            by[o] = d
            lo, hi = boot({o: d})
            line.append(f'{o}: {sum(rs[k]["score"] for k in keys)/len(keys):.3f} vs {sum(base[k]["score"] for k in keys)/len(keys):.3f}'
                        f' diff {sum(d)/len(d):+.3f} [{lo:+.3f}, {hi:+.3f}] n={len(d)}')
        if len(by) > 1:
            lo, hi = boot(by)
            m = sum(sum(d)/len(d) for d in by.values())/len(by)
            line.append(f'both: {m:+.3f} [{lo:+.3f}, {hi:+.3f}]')
        ss = [r['search'] for r in rs.values() if 'search' in r and r['search'].get('searched')]
        if ss:
            dec = sum(s['searched'] for s in ss)
            cpu = sum(s['decision_cpu'] for s in ss)/dec
            roll = sum(s['rollouts']*s['searched'] for s in ss)/dec
            extra = f'cpu/dec {cpu:.3f}s rollouts/dec {roll:.1f}'
            if 'changed' in ss[0]:
                extra += f' changed {sum(s["changed"]*s["searched"] for s in ss)/dec:.3f}'
            line.append(extra)
        print(' | '.join(line))
    bs = [r['search'] for r in base.values() if 'search' in r and r['search'].get('searched')]
    if bs:
        dec = sum(s['searched'] for s in bs)
        print(f'{a.base} (baseline): cpu/dec {sum(s["decision_cpu"] for s in bs)/dec:.3f}s '
              f'rollouts/dec {sum(s["rollouts"]*s["searched"] for s in bs)/dec:.1f} (measured at its own run\'s load)')


if __name__ == '__main__':
    main()
