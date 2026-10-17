"""SCALE1 search compute-scaling readout (BOT LEAD 2026-10-17; pre-registered in reports/bot/fullpool/PROGRESS.md).

    python3 -m bot.fullpool.scale_report DIR [DIR ...] [--ref res-wint] [--arms res-K2-wint,...] [--cpu-exclude 127x01]

Rows of bot.livediag.l16_cadence --decks dd1 (same base on every host). Duplicate (index, opponent, player) rows from
hosts that ran the same case are checked for identical command events + outcome (the games are deterministic) and
counted once. Per arm: score, paired delta vs --ref with a bootstrap 95% CI (4000 draws, seed 0, resampling cases)
pooled and per opponent; paired K4-K2 and T16-vs-K2 contrasts (the pre-registered K8 gate: K4-K2 > 0 vs LIVE-K4CW-r16);
enemy play -> our next searched decision p50/p90 (s); enemy play -> our next play p50/p90 (s); undefended Giant-push
share (bot.livediag.l16_report.analyse); CPU-ms per searched decision (our seat, median over games and pooled), from
hosts not in --cpu-exclude (127x01 was thermally throttled, ~720-1500 MHz vs ~2500 on 04/08).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import defaultdict

from bot.livediag.l16_report import analyse, load, q, reaction, score, to_decision


def boot(xs, seed=0):
    if not xs:
        return None, None
    rng = random.Random(seed)
    d = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(4000))
    return round(sum(xs) / len(xs), 4), [round(d[100], 4), round(d[3900], 4)]


def fingerprint(r):
    return hashlib.sha256(json.dumps([r['result'].get('command_events'), r.get('win'), r.get('draw')],
                                     sort_keys=True).encode()).hexdigest()


def contrast(by, a, b, opp=None):
    keys = sorted(k for k in set(by.get(a, {})) & set(by.get(b, {})) if opp is None or k[1] == opp)
    d = [score(by[a][k]) - score(by[b][k]) for k in keys]
    pt, ci = boot(d)
    return dict(n=len(keys), delta=pt, ci=ci)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--ref', default='res-wint')
    ap.add_argument('--arms', default='res-K2-wint,res-K4-wint,res-K2-T16-wint')
    ap.add_argument('--k2', default='res-K2-wint')
    ap.add_argument('--k4', default='res-K4-wint')
    ap.add_argument('--t2', default='res-K2-T16-wint')
    ap.add_argument('--gate-opponent', default='LIVE-K4CW-r16')
    ap.add_argument('--cpu-exclude', default='127x01')
    ap.add_argument('--json')
    a = ap.parse_args(argv)
    excl = {h for h in a.cpu_exclude.split(',') if h}
    by, cpu_rows = defaultdict(dict), defaultdict(dict)
    rows = load(a.dirs)
    dup = same = errors = 0
    for r in rows:
        if r.get('error') or 'result' not in r:
            errors += 1
            continue
        k = (r['index'], r['opponent'])
        old = by[r['player']].get(k)
        if old is not None:
            dup += 1
            same += fingerprint(old) == fingerprint(r)
        else:
            by[r['player']][k] = r
        if r.get('host', '').split('.')[0] not in excl:
            cpu_rows[r['player']][k] = r
    if dup != same:
        raise SystemExit(f'{dup - same} of {dup} duplicate rows differ in command events / outcome')
    opps = sorted({k[1] for v in by.values() for k in v})
    out = dict(rows=len(rows), errors=errors, duplicates=dup, duplicates_identical=same,
               n_per_player={p: len(v) for p, v in sorted(by.items())}, opponents=opps, arms={}, mechanism={})
    for p, cases in sorted(by.items()):
        todec, react, nodef, pushes = [], [], 0, 0
        for r in cases.values():
            todec += to_decision(r)
            react += [t for t, _ in reaction(r)]
            m = analyse(r.get('packet_perc') or [], r.get('packet_dec') or [], {})
            pushes += len(m['giant_pushes']); nodef += sum(x['no_def_before_contact'] for x in m['giant_pushes'])
        per_game, cpu_tot, dec_tot = [], 0., 0
        for r in cpu_rows.get(p, {}).values():
            t = (r['result'].get('timing') or {}).get(str(r['seat'])) or {}
            if t.get('decisions'):
                per_game.append(1000 * t['cpu'] / t['decisions']); cpu_tot += t['cpu']; dec_tot += t['decisions']
        out['mechanism'][p] = dict(
            n=len(cases), score=round(sum(score(r) for r in cases.values()) / len(cases), 3),
            score_by_opponent={o: round(sum(score(r) for k, r in cases.items() if k[1] == o)
                                        / max(1, sum(1 for k in cases if k[1] == o)), 3) for o in opps},
            enemy_to_decision_p50=q(todec, .5), enemy_to_decision_p90=q(todec, .9),
            enemy_to_our_play_p50=q(react, .5), enemy_to_our_play_p90=q(react, .9),
            undefended=round(nodef / max(1, pushes), 3), giant_pushes=pushes,
            cpu_ms_per_decision_median=q(per_game, .5),
            cpu_ms_per_decision_pooled=round(1000 * cpu_tot / dec_tot, 1) if dec_tot else None,
            cpu_games=len(per_game), decisions_per_game=round(dec_tot / max(1, len(per_game)), 1))
    for arm in a.arms.split(','):
        out['arms'][arm] = dict(pooled=contrast(by, arm, a.ref),
                                **{o: contrast(by, arm, a.ref, o) for o in opps})
    out['contrasts'] = {
        'K4-K2': dict(pooled=contrast(by, a.k4, a.k2), **{o: contrast(by, a.k4, a.k2, o) for o in opps}),
        'K2T16-K2': dict(pooled=contrast(by, a.t2, a.k2), **{o: contrast(by, a.t2, a.k2, o) for o in opps})}
    g = out['contrasts']['K4-K2'].get(a.gate_opponent, {})
    out['k8_gate'] = dict(rule=f'K4-K2 > 0 vs {a.gate_opponent}', delta=g.get('delta'),
                          run_k8=bool(g.get('delta') is not None and g['delta'] > 0))
    text = json.dumps(out, indent=1)
    if a.json:
        open(a.json, 'w').write(text + '\n')
    print(text)


if __name__ == '__main__':
    main(sys.argv[1:])
