"""Gate (b): K4L vs R3a / v1 under live16402 against the current pin, on the same HEADLINE case indices.

    python -m ... eval_compare.py --l16 DIR --cur FILE_OR_DIR [--cur ...] [--cases 200]

Per opponent and arm: games, mean score (win 1 / draw 0.5) with the bot track's bootstrap 95% CI
(bot.eval.summarize.ci), W/D/L; then the paired difference live16402 - current over shared cases (bootstrap over
cases) and how many games replay the identical command stream (command_sha256). The candidate name may differ
between arms (K4L-R-gs-rw-fc vs K4L-R-gs: same command hashes, reports/bot/learned-opponent/RESULTS.md).
"""
import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from bot.eval.summarize import ci  # noqa: E402


def rows(paths):
    out = {}
    for p in paths:
        p = Path(p)
        files = sorted(p.glob('games-*.jsonl')) if p.is_dir() else [p]
        for f in files:
            for line in f.read_text().splitlines():
                r = json.loads(line)
                if r.get('candidate', '').startswith('K4L-R-gs'):
                    out[(r['opponent'], r['index'])] = r
    return out


def paired(diffs, draws=4000, seed=0):
    rng = random.Random(seed)
    n = len(diffs)
    means = sorted(sum(rng.choice(diffs) for _ in range(n)) / n for _ in range(draws))
    return sum(diffs) / n, means[int(0.025 * draws)], means[int(0.975 * draws) - 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--l16', nargs='+', required=True)
    ap.add_argument('--cur', nargs='+', required=True)
    ap.add_argument('--cases', type=int, default=200)
    a = ap.parse_args()
    L, C = rows(a.l16), rows(a.cur)
    out = {}
    for opp in ('R3a', 'v1'):
        keys = [(opp, i) for i in range(a.cases) if (opp, i) in L and (opp, i) in C]
        res = {}
        for arm, R in (('live16402', L), ('current', C)):
            s = [R[k]['score'] for k in keys]
            m = sum(s) / len(s) if s else None
            lo, hi = ci(s) if s else (None, None)
            res[arm] = dict(games=len(s), mean=m, ci95=[lo, hi], wins=s.count(1.0), draws=s.count(0.5),
                            losses=s.count(0.0))
        d = [L[k]['score'] - C[k]['score'] for k in keys]
        res['paired_diff'] = dict(zip(('mean', 'lo', 'hi'), paired(d))) if d else None
        res['identical_command_streams'] = sum(L[k]['command_sha256'] == C[k]['command_sha256'] for k in keys)
        out[opp] = res
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
