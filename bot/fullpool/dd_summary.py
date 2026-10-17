"""Deck-diverse gate row summary (bank DD1, decks 'dd1'; BOT LEAD 2026-10-17 requirement for leaf/value gates).

    python -m bot.fullpool.dd_summary DIR [DIR ...] --a ARM_A --b ARM_B [--opponent LIVE-K4CW-r16]

DIRs hold bot.eval.headline games-*.jsonl rows (run with --bank DD1 --levels max and BOT_PLAYLOG=1). Rows are paired
by case index. Per OUR deck (bot.fullpool.banks.dd1_own order: s62, e16, Inferno pick, Battle Log 1/28/30/64/76) and
pooled: each arm's mean score, the paired B - A with a 95% bootstrap CI (10,000 resamples, seed 0), and per-battle
accepted plays of Zap, Fireball, Arrows and Bats (our seat), the small-spell / swarm-air usage the row exists to watch.
"""
from __future__ import annotations

import argparse
import glob
import json
import random

from bot.fullpool.banks import dd1_own

NAMES = ('s62', 'e16', 'inferno', 'bl1', 'bl28', 'bl30', 'bl64', 'bl76')
WATCH = ('Zap', 'Fireball', 'Arrows', 'Bats')


def load(dirs, opponent=None):
    owns = [sorted(d) for d in dd1_own()]
    rows, errors = {}, {}
    for d in dirs:
        for p in sorted(glob.glob(f'{d}/games-*.jsonl')):
            for line in open(p):
                if not line.strip():
                    continue
                r = json.loads(line)
                if opponent and r['opponent'] != opponent:
                    continue
                if 'error' in r:
                    errors[r['candidate']] = errors.get(r['candidate'], 0) + 1
                    continue
                own = sorted(r['deck_lists'][r['seat']])
                r['own_deck'] = NAMES[owns.index(own)] if own in owns else 'other'
                log = (r.get('play_log') or {}).get(str(r['seat']), [])
                r['watch'] = {c: sum(1 for x in log if x[1] == c and x[3]) for c in WATCH}
                rows.setdefault((r['candidate'], r['index']), r)
    return rows, errors


def ci(d, n=10000):
    if not d:
        return None
    rng = random.Random(0)
    m = sum(d) / len(d)
    bs = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(n))
    return [round(m, 4), round(bs[int(.025 * n)], 4), round(bs[int(.975 * n) - 1], 4)]


def summarize(rows, a, b):
    out = []
    for deck in NAMES + ('pooled',):
        idx = sorted(i for (c, i) in rows if c == a and (b, i) in rows and (deck == 'pooled' or rows[(a, i)]['own_deck'] == deck))
        if not idx:
            continue
        ra, rb = [rows[(a, i)] for i in idx], [rows[(b, i)] for i in idx]
        mean = lambda rs: round(sum(r['score'] for r in rs) / len(rs), 4)
        watch = lambda rs: {c: round(sum(r['watch'][c] for r in rs) / len(rs), 2) for c in WATCH}
        out.append(dict(own_deck=deck, n=len(idx), A=mean(ra), B=mean(rb),
                        B_minus_A=ci([y['score'] - x['score'] for x, y in zip(ra, rb)]),
                        plays_per_battle_A=watch(ra), plays_per_battle_B=watch(rb)))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--a', required=True)
    ap.add_argument('--b', required=True)
    ap.add_argument('--opponent', default=None)
    a = ap.parse_args(argv)
    rows, errors = load(a.dirs, a.opponent)
    print(json.dumps(dict(rows=len(rows), errors=errors)))
    for r in summarize(rows, a.a, a.b):
        print(json.dumps(r))


if __name__ == '__main__':
    main()
