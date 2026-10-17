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


REQUIRED = {'candidate': str, 'opponent': str, 'index': int, 'seat': int, 'seed': int, 'score': (int, float),
            'terminal': bool, 'levels': str, 'plays': dict, 'cpu_seconds': (int, float)}


def validate(rows, cands, opps, start, games, base):
    fails, keys = [], {}
    for r in rows:
        if not isinstance(r, dict):
            fails.append(f'non-object row: {str(r)[:80]}')
            continue
        if 'error' in r:
            fails.append(f"error row: {r.get('candidate')} {r.get('opponent')} {r.get('index')}: {str(r['error'])[:200]}")
            continue
        bad = [f for f, t in REQUIRED.items() if not isinstance(r.get(f), t) or (t is int and isinstance(r.get(f), bool))]
        if bad:
            fails.append(f"row missing/mistyped {bad}: {r.get('candidate')} {r.get('opponent')} {r.get('index')}")
            continue
        cp = r['plays'].get(str(r['seat']))
        if isinstance(cp, bool) or not isinstance(cp, int) or cp < 0:
            fails.append(f"candidate plays not a nonnegative integer: {r['candidate']} {r['opponent']} {r['index']}: {cp!r}")
            continue
        if not math.isfinite(r['cpu_seconds']) or not math.isfinite(r['score']):
            fails.append(f"non-finite cpu_seconds/score: {r['candidate']} {r['opponent']} {r['index']}")
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
    cands, opps = a.candidates.split(','), a.opponents.split(',')
    if a.games < 1 or a.start < 0 or a.base < 0:
        ap.error('games >= 1, start >= 0, base >= 0')
    for lst in (cands, opps):
        if not all(lst) or len(set(lst)) != len(lst):
            ap.error('candidate/opponent lists must be non-empty and duplicate-free')
    if not Path(a.dir).is_dir():
        ap.error(f'no such directory {a.dir}')
    rows = load(a.dir)
    fails = validate(rows, cands, opps, a.start, a.games, a.base)
    report = dict(rows=len(rows), valid=not fails, failures=fails[:20])
    if not fails:                       # summarise only validated rows
        report['cells'] = summary(rows)
    print(json.dumps(report, indent=1))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
