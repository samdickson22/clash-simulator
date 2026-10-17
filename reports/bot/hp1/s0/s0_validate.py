"""HP1 S0 validation + summary. Runs on 127x05 only, on rows copied back from 04 (never on a fleet host).

    python3 s0_validate.py DIR --candidates C1,C2 --opponents O1,O2 --start S --games N --base B

Validity gate (all must hold, else exit 1 and print the failures; failed rows are never dropped):
exactly the expected (candidate, opponent, index) keys, each once; no 'error' rows; terminal; levels card16-tower16;
seed == base + index; seat == index % 2; score in {0, .5, 1}. Prints per-cell n, score, plays/game (mean, se).
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path


def load(d):
    rows = []
    for p in sorted(Path(d).glob('games-*.jsonl')):
        for i, line in enumerate(p.read_text().splitlines()):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                rows.append(dict(error=f'partial line {p.name}:{i}'))
    return rows


def validate(rows, cands, opps, start, games, base):
    fails, keys = [], {}
    for r in rows:
        if 'error' in r:
            fails.append(f"error row: {r.get('candidate')} {r.get('opponent')} {r.get('index')}: {str(r['error'])[:200]}")
            continue
        k = (r['candidate'], r['opponent'], r['index'])
        keys[k] = keys.get(k, 0) + 1
        if not r.get('terminal'):
            fails.append(f'nonterminal {k}')
        if r.get('levels') != 'card16-tower16':
            fails.append(f"levels {r.get('levels')} {k}")
        if r['seed'] != base + r['index'] or r['seat'] != r['index'] % 2:
            fails.append(f'seed/seat {k}')
        if r['score'] not in (0, .5, 1):
            fails.append(f'score {k}')
    expected = {(c, o, i) for c in cands for o in opps for i in range(start, start + games)}
    missing, extra = expected - set(keys), set(keys) - expected
    dup = [k for k, n in keys.items() if n > 1]
    if missing: fails.append(f'missing {len(missing)} e.g. {sorted(missing)[:3]}')
    if extra: fails.append(f'unexpected {len(extra)} e.g. {sorted(extra)[:3]}')
    if dup: fails.append(f'duplicates {len(dup)} e.g. {dup[:3]}')
    return fails


def boot(xs, draws=4000):
    rng = random.Random(0); n = len(xs)
    means = sorted(sum(xs[rng.randrange(n)] for _ in range(n)) / n for _ in range(draws))
    return means[100], means[3899]


def summary(rows):
    cells = {}
    for r in rows:
        cells.setdefault((r['candidate'], r['opponent']), []).append(r)
    out = []
    for (c, o), rs in sorted(cells.items()):
        sc = [r['score'] for r in rs]; pl = [r['plays'][str(r['seat'])] for r in rs]
        m = sum(pl) / len(pl); se = (sum((x - m) ** 2 for x in pl) / max(1, len(pl) - 1)) ** .5 / math.sqrt(len(pl))
        lo, hi = boot(sc)
        out.append(dict(candidate=c, opponent=o, n=len(rs), score=sum(sc) / len(sc), ci=[lo, hi],
                        plays_per_game=m, plays_se=se, cpu_s_mean=sum(r['cpu_seconds'] for r in rs) / len(rs)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir'); ap.add_argument('--candidates', required=True); ap.add_argument('--opponents', required=True)
    ap.add_argument('--start', type=int, required=True); ap.add_argument('--games', type=int, required=True)
    ap.add_argument('--base', type=int, required=True)
    a = ap.parse_args()
    rows = load(a.dir)
    fails = validate(rows, a.candidates.split(','), a.opponents.split(','), a.start, a.games, a.base)
    print(json.dumps(dict(rows=len(rows), valid=not fails, failures=fails[:20], cells=summary([r for r in rows if 'error' not in r])), indent=1))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
