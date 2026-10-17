"""PF1 readout (reports/bot/live-diag/PF1-PREREG.md), read once all rows are in.

    python3 -m bot.livediag.pf1_report DIR [DIR ...] [--json OUT]

Per opponent: (fast-rl5v10fp - res-lb-wintp) and (fast-f1a2 - res-lb-wintp), paired by case index, bootstrap 95 % CI
(10,000 resamples, seed 0). Per opponent x arm:
- score with CI;
- plays per minute (our accepted plays / game minutes);
- reaction p50 / p90 (public_diagnostics reaction_s);
- undefended share (undefended_before_contact / giant pushes, l16 definition);
- idle-play share: our submitted TROOP plays (spells and buildings excluded) with no enemy unit within 6 tiles of the play's
  target tile. Measured on the bot's own packet record (packet_perc) at the submitting decision's tick.
Elixir at the enemy's cross comes from bot.livediag.l16_report on the same dirs.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import random

ARMS = ('res-lb-wintp', 'fast-rl5v10fp', 'fast-f1a2')
NON_TROOP = {'Fireball', 'Zap', 'Cannon', 'Arrows', 'Log', 'Rocket', 'Poison', 'Tombstone', 'InfernoTower', 'BombTower',
             'GoblinCage', 'Tesla', 'XBow', 'Mortar', 'GoblinHut', 'Furnace', 'BarbarianHut', 'ElixirCollector'}
B = 10000


def score(r):
    return .5 if r.get('draw') else float(r.get('win') or 0)


def boot(xs, seed=0):
    rng = random.Random(seed)
    m = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(B))
    return round(sum(xs) / len(xs), 4), [round(m[int(.025 * B)], 4), round(m[int(.975 * B) - 1], 4)]


def q(xs, f):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(f * len(xs)))], 2) if xs else None


def idle(r):
    """(idle troop plays, troop plays) from packet_dec (submitted plays) + packet_perc (units at that tick)."""
    perc = {}
    for p in r.get('packet_perc') or []:
        perc[p['tick']] = p.get('units') or []
    ticks = sorted(perc)
    n = idle_n = 0
    for d in r.get('packet_dec') or []:
        a, card = d.get('action'), d.get('card')
        if not d.get('submitted') or a is None or a >= 2304 or not card or card in NON_TROOP:
            continue
        t = int(a) % 576
        x, y = t % 18 + .5, t // 18 + .5
        prior = [k for k in ticks if k <= d['tick']]
        units = perc[prior[-1]] if prior else []
        n += 1
        if not any(u.get('owner') == 1 and math.hypot(u['x'] - x, u['y'] - y) <= 6 for u in units):
            idle_n += 1
    return idle_n, n


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--json', default=None)
    a = ap.parse_args(argv)
    rows, bad = {}, 0
    for d in a.dirs:
        for p in glob.glob(d + '/rows/*.json'):
            r = json.load(open(p))
            if r.get('error') or 'result' not in r:
                bad += 1
                continue
            rows.setdefault((r['opponent'], r['index'], r['player']), r)
    out = dict(unusable_rows=bad, issues=sum(bool(r.get('issues')) for r in rows.values()), opponents={})
    for opp in sorted({k[0] for k in rows}):
        res = {}
        for pl in ARMS:
            rs = [r for (o, _, p), r in rows.items() if o == opp and p == pl]
            if not rs:
                continue
            seat = lambda r: str(r['seat'])
            plays = sum(sum(1 for *_, ok in r['result']['play_log'][seat(r)] if ok) for r in rs)
            minutes = sum(r['result']['ticks'] for r in rs) / 20 / 60
            react = [x for r in rs for x in r['result']['public_diagnostics'][seat(r)]['reaction_s']]
            pushes = sum(r['result']['public_diagnostics'][seat(r)]['giant_pushes'] for r in rs)
            und = sum(r['result']['public_diagnostics'][seat(r)]['undefended_before_contact'] for r in rs)
            idl = [idle(r) for r in rs]
            res[pl] = dict(n=len(rs), score=boot([score(r) for r in rs]), plays_per_min=round(plays / minutes, 2),
                           reaction_p50_p90=[q(react, .5), q(react, .9)],
                           undefended_share=None if not pushes else round(und / pushes, 3),
                           idle_play_share=round(sum(i for i, _ in idl) / max(1, sum(n for _, n in idl)), 3),
                           troop_plays_per_battle=round(sum(n for _, n in idl) / len(rs), 2))
        base = {i: r for (o, i, p), r in rows.items() if o == opp and p == 'res-lb-wintp'}
        deltas = {}
        for pl in ARMS[1:]:
            oth = {i: r for (o, i, p), r in rows.items() if o == opp and p == pl}
            k = sorted(set(base) & set(oth))
            deltas[f'{pl} - res-lb-wintp'] = dict(n=len(k), **dict(zip(('mean', 'ci'), boot([score(oth[i]) - score(base[i]) for i in k])))) if k else None
        out['opponents'][opp] = dict(arms=res, deltas=deltas)
    print(json.dumps(out, indent=1))
    if a.json:
        open(a.json, 'w').write(json.dumps(out, indent=1) + '\n')


if __name__ == '__main__':
    main()
