"""rlfp1 snapshot-eval summary: paired delta of each candidate vs a reference (v0) over bot.eval.headline result dirs.

    python3 -m bot.fullpool.rl_evalsum DIR [DIR ...] [--ref policy-00000] [--json OUT]

Rows pair on (opponent, case index) across dirs (one bank, index ranges split over hosts). Per candidate: mean score
per opponent, delta vs --ref per opponent and pooled (each unit one (opponent, index) case) with a 4,000-draw bootstrap
95% CI (seed 0). 'promotion_candidate' = pooled CI lower bound > 0 (BOT LEAD 10-17 rule: CI-clear gain vs v0 on a fresh
bank; live use as the fast tier still needs an L16 search-level A/B). Rows with 'error' are counted and skipped.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path


def boot(xs, seed=0):
    if not xs:
        return None, None
    rng = random.Random(seed)
    d = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(4000))
    return round(sum(xs) / len(xs), 4), [round(d[100], 4), round(d[3900], 4)]


def short(cand):
    return Path(cand.split(':', 1)[-1].split('@')[0]).stem


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--ref', default='policy-00000')
    ap.add_argument('--json')
    a = ap.parse_args(argv)
    sc, errors, banks = defaultdict(dict), 0, set()
    for d in a.dirs:
        launch = Path(d, 'launch.json')
        if launch.exists():
            banks.add(json.loads(launch.read_text())['args']['base'])
        for p in sorted(Path(d).glob('games-*.jsonl')):
            for line in p.read_text().splitlines():
                r = json.loads(line)
                if 'error' in r:
                    errors += 1
                    continue
                sc[short(r['candidate'])][(r['opponent'], r['index'])] = r['score']
    if len(banks) > 1:
        raise SystemExit(f'dirs mix banks {sorted(banks)}')
    ref = sc.get(a.ref)
    if not ref:
        raise SystemExit(f'no rows for ref {a.ref}; candidates {sorted(sc)}')
    opps = sorted({o for o, _ in ref})
    out = dict(bank=next(iter(banks), None), errors=errors, ref=a.ref, games={c: len(v) for c, v in sorted(sc.items())},
               score={c: {o: round(sum(s for (oo, _), s in v.items() if oo == o) / max(1, sum(1 for oo, _ in v if oo == o)), 3)
                          for o in opps} for c, v in sorted(sc.items())},
               delta={})
    for c, v in sorted(sc.items()):
        if c == a.ref:
            continue
        keys = sorted(set(v) & set(ref))
        row = {o: dict(zip(('delta', 'ci'), boot([v[k] - ref[k] for k in keys if k[0] == o])),
                       n=sum(1 for k in keys if k[0] == o)) for o in opps}
        pt, ci = boot([v[k] - ref[k] for k in keys])
        row['pooled'] = dict(delta=pt, ci=ci, n=len(keys))
        row['promotion_candidate'] = bool(ci and ci[0] > 0)
        out['delta'][c] = row
    text = json.dumps(out, indent=1)
    if a.json:
        Path(a.json).write_text(text + '\n')
    print(text)


if __name__ == '__main__':
    main(sys.argv[1:])
