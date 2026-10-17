"""Opponent-deck archetypes and per-archetype paired deltas (exploration; BOT LEAD 2026-10-17 wide-vocab -res bank).

    python -m bot.fullpool.archetype DIR [DIR ...] --a ARM_A --b ARM_B

classify(deck): the first matching rule, in order (engine names):
  siege       Xbow or Mortar
  royalgiant  RoyalGiant
  hog         HogRider (hog / cycle)
  air         Balloon, LavaHound or BabyDragon
  giant       Giant, GoblinGiant, Golem or ElectroGiant (beatdown)
  bait        GoblinBarrel or Princess
  other       anything else
The summary pairs rows by (opponent, case index) and reports, per opponent x archetype and pooled per archetype, the
paired B - A with a 95% bootstrap CI; cells with B - A < -0.10 at n >= 20 are flagged.
ARCH_CORES drive the synthetic 'arch1' deck spec of bot/fullpool/banks.py (a sampler deck that must hold the core).
"""
from __future__ import annotations

import argparse
import glob
import json
import random

RULES = (('siege', ('Xbow', 'Mortar')), ('royalgiant', ('RoyalGiant',)), ('hog', ('HogRider',)),
         ('air', ('Balloon', 'LavaHound', 'BabyDragon')), ('giant', ('Giant', 'GoblinGiant', 'Golem', 'ElectroGiant')),
         ('bait', ('GoblinBarrel', 'Princess')))
ARCH_CORES = (('hog', ('HogRider',)), ('royalgiant', ('RoyalGiant',)), ('air', ('Balloon',)), ('siege', ('Xbow',)),
              ('giant', ('Giant',)), ('bait', ('GoblinBarrel',)), ('air', ('LavaHound',)), ('siege', ('Mortar',)),
              ('air', ('BabyDragon',)))


def classify(deck):
    s = set(deck)
    for name, cards in RULES:
        if s & set(cards):
            return name
    return 'other'


def ci(d, n=10000):
    rng = random.Random(0)
    m = sum(d) / len(d)
    bs = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(n))
    return [round(m, 4), round(bs[int(.025 * n)], 4), round(bs[int(.975 * n) - 1], 4)]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--a', required=True)
    ap.add_argument('--b', required=True)
    a = ap.parse_args(argv)
    rows, err = {}, {}
    for d in a.dirs:
        for p in sorted(glob.glob(f'{d}/games-*.jsonl')):
            for line in open(p):
                r = json.loads(line)
                if 'error' in r:
                    err[r['candidate']] = err.get(r['candidate'], 0) + 1
                    continue
                r['arch'] = classify(r['deck_lists'][1 - r['seat']])
                rows.setdefault((r['candidate'], d, r['opponent'], r['index']), r)
    keys = sorted(k[1:] for k in rows if k[0] == a.a and (a.b,) + k[1:] in rows)
    print(json.dumps(dict(paired=len(keys), errors=err)))
    cells = {}
    for k in keys:
        arch = rows[(a.a,) + k]['arch']
        d = rows[(a.b,) + k]['score'] - rows[(a.a,) + k]['score']
        cells.setdefault((k[1], arch), []).append(d)
        cells.setdefault(('pooled', arch), []).append(d)
        cells.setdefault(('pooled', 'all'), []).append(d)
    for (opp, arch), d in sorted(cells.items()):
        c = ci(d)
        print(json.dumps(dict(opponent=opp, archetype=arch, n=len(d), B_minus_A=c,
                              FLAG=bool(c[0] < -0.10 and len(d) >= 20))))


if __name__ == '__main__':
    main()
