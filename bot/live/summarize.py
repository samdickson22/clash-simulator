"""Tables for reports/live/bot/RESULTS.md from bot.live.replay outputs.

    python -m bot.live.summarize agreement DIR [DIR...]      # per noise arm: agreement, play recall/precision
    python -m bot.live.summarize latency DIR [DIR...]        # per tier/config: decision wall ms p50/p95/p99
"""
import json
import random
import sys
from collections import defaultdict
from pathlib import Path


def rows(dirs, name):
    for d in dirs:
        p = Path(d) / name
        if p.exists():
            for line in p.read_text().splitlines():
                yield json.loads(line)


def ci(xs, n=2000):
    if not xs:
        return (float('nan'),)*2
    rng = random.Random(0)
    m = sorted(sum(rng.choice(xs) for _ in xs)/len(xs) for _ in range(n))
    return m[int(.025*n)], m[int(.975*n)]


def close(a, b, tiles=2):
    """Same card slot and target within `tiles` (Chebyshev) - plays only."""
    if a >= 2304 or b >= 2304 or a // 576 != b // 576:
        return False
    (ra, ca), (rb, cb) = divmod(a % 576, 18), divmod(b % 576, 18)
    return max(abs(ra-rb), abs(ca-cb)) <= tiles


def agreement(dirs):
    by = defaultdict(list)
    for r in rows(dirs, 'agreement.jsonl'):
        by[r['shadow']].append(r)
    games = {(r.get('game'), r.get('episode')) for v in by.values() for r in v}
    print('| arm | decisions | exact | 95% CI | play/wait same | truth plays: exact | same card | card+<=2 tiles | '
          'truth WAITs kept | shadow plays when truth waits | errors |')
    print('|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|')
    for k, v in by.items():
        a = [float(r['agree']) for r in v]
        plays = [r for r in v if r['truth_play']]
        waits = [r for r in v if not r['truth_play']]
        lo, hi = ci(a)
        n = max(1, len(plays))
        print(f"| {k} | {len(v)} | {sum(a)/len(a):.3f} | [{lo:.3f}, {hi:.3f}] | "
              f"{sum(r['truth_play'] == r['shadow_play'] for r in v)/len(v):.3f} | "
              f"{sum(r['agree'] for r in plays)/n:.3f} (n={len(plays)}) | "
              f"{sum(r['shadow_play'] and r['action']//576 == r['truth']//576 for r in plays)/n:.3f} | "
              f"{sum(close(r['truth'], r['action']) for r in plays)/n:.3f} | "
              f"{sum(not r['shadow_play'] for r in waits)/max(1, len(waits)):.3f} | "
              f"{sum(r['shadow_play'] for r in waits)} | "
              f"{sum(bool(r.get('error')) for r in v)} |")
    print(f'\n{len(games)} games/matches')


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs)-1, int(p*len(xs)))] if xs else float('nan')


def latency(dirs):
    print('| run | tier | decisions | wall p50 ms | p95 | p99 | max | cpu p50 ms | search-defaulted | errors |')
    print('|---|---|---:|---:|---:|---:|---:|---:|---:|---:|')
    for d in dirs:
        ds = list(rows([d], 'decisions.jsonl'))
        if not ds:   # t1 source: agreement rows of the reference arm carry wall_ms/source
            allr = list(rows([d], 'agreement.jsonl'))
            ref = allr[0]['shadow'] if allr else None
            ds = [r for r in allr if r['shadow'] == ref and r.get('wall_ms') is not None]
        searched = [x for x in ds if x.get('source', '').startswith(('search', 'default'))] or ds
        w = [x['wall_ms'] for x in searched]
        c = [x['cpu_ms'] for x in searched if 'cpu_ms' in x]
        dflt = sum(str(x.get('source', '')).startswith('default') for x in searched)
        err = sum('error' in str(x.get('source', '')) or bool(x.get('error')) for x in ds)
        tier = ds[0].get('tier') if ds else '?'
        print(f'| {Path(d).name} | {tier} | {len(w)} | {q(w, .5):.1f} | {q(w, .95):.1f} | {q(w, .99):.1f} | '
              f'{max(w) if w else float("nan"):.1f} | {q(c, .5):.1f} | {dflt} | {err} |')


if __name__ == '__main__':
    {'agreement': agreement, 'latency': latency}[sys.argv[1]](sys.argv[2:])
