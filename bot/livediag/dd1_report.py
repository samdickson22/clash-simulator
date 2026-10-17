"""DD1 deck-diverse readout for l16_cadence --decks dd1 rows (bot lead live-diag).

    python3 -m bot.livediag.dd1_report DIR [DIR ...] --ref res --arms res-K2,res-wint,res-K2-wint [--json OUT]

Pairs rows on (index, opponent) across dirs (same DD1 base => same cases). Per arm vs --ref: pooled paired delta with a
bootstrap 95% CI (4000 draws, seed 0, resampling cases), the same per own deck (own_index 0..7: s62, e16, Inferno pick,
Battle Log decks 1/28/30/64/76), and the BOT LEAD ship rule (CI lower bound > -0.02 and point > 0; wint arms also
'qualifies on reaction' at point >= 0, no CI condition). Mechanism per arm: score, enemy->decision p50 (s), undefended share, decisions
and CPU-s per game-second.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

from bot.livediag.l16_report import analyse, load, q, score, to_decision

OWN = ['s62', 'e16', 'inferno', 'bl1', 'bl28', 'bl30', 'bl64', 'bl76']


def boot(xs, seed=0):
    rng = random.Random(seed)
    d = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(4000))
    return round(sum(xs) / len(xs), 4), [round(d[100], 4), round(d[3900], 4)]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--ref', default='res')
    ap.add_argument('--arms', default='res-K2,res-wint,res-K2-wint')
    ap.add_argument('--json')
    a = ap.parse_args(argv)
    by = defaultdict(dict)
    rows = load(a.dirs)
    for r in rows:
        if r.get('error') or 'result' not in r:
            continue
        by[r['player']][(r['index'], r['opponent'])] = r
    out = dict(rows=len(rows), errors=sum(1 for r in rows if r.get('error')), n_per_player={k: len(v) for k, v in by.items()},
               arms={}, mechanism={})
    for p, cases in by.items():
        todec, nodef, pushes, cpu, dps = [], 0, 0, [], []
        for r in cases.values():
            todec += to_decision(r)
            m = analyse(r.get('packet_perc') or [], r.get('packet_dec') or [], {})
            pushes += len(m['giant_pushes']); nodef += sum(x['no_def_before_contact'] for x in m['giant_pushes'])
            t = (r['result'].get('timing') or {}).get(str(r['seat'])) or {}
            s = r['result']['ticks'] / 20
            if t.get('decisions'):
                cpu.append(t['cpu'] / s); dps.append(t['decisions'] / s)
        out['mechanism'][p] = dict(n=len(cases), score=round(sum(score(r) for r in cases.values()) / len(cases), 3),
                                   enemy_to_decision_p50=q(todec, .5), undefended=round(nodef / max(1, pushes), 3),
                                   decisions_per_game_s=q(dps, .5), cpu_s_per_game_s=q(cpu, .5))
    ref = by.get(a.ref, {})
    for arm in a.arms.split(','):
        cases = by.get(arm, {})
        keys = sorted(set(cases) & set(ref))
        if not keys:
            continue
        d = [score(cases[k]) - score(ref[k]) for k in keys]
        pt, ci = boot(d)
        per = {}
        for oi, name in enumerate(OWN):
            dd = [score(cases[k]) - score(ref[k]) for k in keys if cases[k].get('own_index', k[0] % 8) == oi]
            if dd:
                per[name] = [*boot(dd), len(dd)]
        ship = ci[0] > -0.02 and pt > 0
        out['arms'][arm] = dict(n=len(keys), delta=pt, ci=ci, ship_rule=ship,
                                ship_rule_wint_reaction=(arm.endswith('wint') and pt >= 0),
                                per_own_deck=per)
    text = json.dumps(out, indent=1)
    if a.json:
        Path(a.json).write_text(text + '\n')
    print(text)


if __name__ == '__main__':
    main(sys.argv[1:])
