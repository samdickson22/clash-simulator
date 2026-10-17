"""WINT-ACC1 readout (reports/bot/live-diag/WINT-ACC1-PREREG.md), read once all rows are in.

    python3 -m bot.livediag.wintacc1_report DIR [DIR ...] [--json OUT]

Per opponent: delta score(res-lb-wintp) - score(res-lb), paired by case index, bootstrap 95 % CI (10,000 resamples, seed 0);
per opponent x arm: score with CI, timed-wait interrupts per battle, and the mechanism look:
- responsive spend: elixir of our accepted plays within 3 s (60 ticks) after each accepted enemy play, per battle;
- final tower HP (ours, theirs), as the outcome of those exchanges.
An interrupt is a searched decision (stats present) before the end of the previous timed wait (tick + stats.timed_wait,
or wait_ticks for the plain arm, whose session blocks until then, so it has none by construction).
Reaction / undefended / elixir-at-cross come from bot.livediag.l16_report on the same dirs.
"""
from __future__ import annotations

import argparse
import glob
import json
import random

COST = dict(Valkyrie=4, Archers=3, Bats=2, Cannon=3, Fireball=4, Zap=2, MiniPekka=4, Giant=5)   # Sam's deck
B = 10000


def score(r):
    return .5 if r.get('draw') else float(r.get('win') or 0)


def boot(xs, seed=0):
    rng = random.Random(seed)
    m = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(B))
    return round(sum(xs) / len(xs), 4), [round(m[int(.025 * B)], 4), round(m[int(.975 * B) - 1], 4)]


def interrupts(r):
    n, until = 0, None
    for d in sorted(r['packet_dec'], key=lambda d: d['tick']):
        st = d.get('stats') or {}
        if not st:
            continue
        if until is not None and d['tick'] < until:
            n += 1
        tw = st.get('timed_wait') or d.get('wait_ticks')     # -wint: the wait is in stats (wait_ticks 0, kept by the facade)
        until = d['tick'] + tw if tw else None
    return n


def responsive_spend(r):
    seat, log = r['seat'], r['result']['play_log']
    ours = [(t, c) for t, c, _, ok in log[str(seat)] if ok]
    theirs = [t for t, _, _, ok in log[str(1 - seat)] if ok]
    used, spend = set(), 0
    for t in theirs:
        for i, (u, c) in enumerate(ours):
            if i not in used and t < u <= t + 60:
                used.add(i)
                spend += COST.get(c, 0)
    return spend


def towers(r):
    tw = r['result']['towers']
    return sum(tw[str(r['seat'])]), sum(tw[str(1 - r['seat'])])


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
            rows[(r['opponent'], r['index'], r['player'])] = r
    out = dict(unusable_rows=bad, issues=sum(bool(r.get('issues')) for r in rows.values()), opponents={})
    for opp in sorted({k[0] for k in rows}):
        res = {}
        for pl in ('res-lb', 'res-lb-wintp'):
            rs = [r for (o, _, p), r in rows.items() if o == opp and p == pl]
            if not rs:
                continue
            tw = [towers(r) for r in rs]
            res[pl] = dict(n=len(rs), score=boot([score(r) for r in rs]),
                           interrupts_per_battle=round(sum(interrupts(r) for r in rs) / len(rs), 2),
                           responsive_spend_per_battle=round(sum(responsive_spend(r) for r in rs) / len(rs), 2),
                           enemy_plays_per_battle=round(sum(sum(1 for *_, ok in r['result']['play_log'][str(1 - r['seat'])] if ok)
                                                            for r in rs) / len(rs), 2),
                           our_tower_hp_end=round(sum(t[0] for t in tw) / len(rs), 1),
                           their_tower_hp_end=round(sum(t[1] for t in tw) / len(rs), 1))
        a_ = {i: r for (o, i, p), r in rows.items() if o == opp and p == 'res-lb'}
        b_ = {i: r for (o, i, p), r in rows.items() if o == opp and p == 'res-lb-wintp'}
        k = sorted(set(a_) & set(b_))
        dlt = boot([score(b_[i]) - score(a_[i]) for i in k]) if k else None
        out['opponents'][opp] = dict(arms=res, paired_n=len(k), delta_wint_minus_res=dlt)
    p = out['opponents'].get('LIVE-K4CW-r16-fp', {}).get('delta_wint_minus_res')
    out['primary'] = dict(delta=p, wint_implicated=None if p is None else p[1][1] < 0)
    print(json.dumps(out, indent=1))
    if a.json:
        open(a.json, 'w').write(json.dumps(out, indent=1) + '\n')


if __name__ == '__main__':
    main()
