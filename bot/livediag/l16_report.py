"""Paired readout of deck-search L16 driver rows (l16_diag / l16_cadence: one JSON per case x arm under OUT/rows/).

    python3 -m bot.livediag.l16_report OUT [OUT ...] [--ref base:clean] [--json FILE]

An arm is (player, noise_arm). Rows pair on (index, opponent) across arms and across shard/host dirs of one bank.
Per arm and opponent: score (win 1, draw .5), reaction p50/p90 (enemy play -> our next play; truth play_log), Giant
reaction, enemy play -> our next searched decision, undefended Giant pushes and elixir at the Giant cross (bot.livediag.live_metrics.analyse on the packet
recorder rows), plays per battle, our decision CPU per decision and per game second, noise counts. Paired delta vs
--ref with a bootstrap 95% CI over cases (4000 draws, seed 0), per opponent and pooled (equal opponent weights).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

from bot.livediag.live_metrics import analyse


def q(xs, f):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(f * len(xs)))], 3) if xs else None


def load(dirs):
    rows = []
    for d in dirs:
        for p in sorted(Path(d, 'rows').glob('*.json')):
            r = json.loads(p.read_text())
            rows.append(r)
    return rows


def score(r):
    if r.get('draw'):
        return .5
    return float(r.get('win') or 0)


def reaction(r):
    seat = int(r['seat'])
    log = r['result'].get('play_log') or {}
    mine = sorted(t for t, c, a, ok in log.get(str(seat), []) if ok)
    out = []
    for t, c, a, ok in log.get(str(1 - seat), []):
        if not ok:
            continue
        nxt = next((x for x in mine if x >= t), None)
        if nxt is not None:
            out.append(((nxt - t) / 20, c))
    return out


def to_decision(r):
    """Enemy play -> our next searched decision (a packet-recorder row with stats), seconds."""
    seat = int(r['seat'])
    dec = sorted(d['tick'] for d in r.get('packet_dec') or [] if d.get('stats'))
    out = []
    for t, c, a, ok in (r['result'].get('play_log') or {}).get(str(1 - seat), []):
        nxt = next((x for x in dec if x >= t), None) if ok else None
        if nxt is not None:
            out.append((nxt - t) / 20)
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--ref', default='base:clean')
    ap.add_argument('--json', default=None)
    a = ap.parse_args(argv)
    rows = load(a.dirs)
    errs = [r for r in rows if r.get('error')]
    by = defaultdict(dict)
    for r in rows:
        if r.get('error') or 'result' not in r:
            continue
        by[(r['player'], r['noise_arm'])][(r['index'], r['opponent'])] = r
    out = dict(rows=len(rows), errors=len(errs), arms={}, paired={})
    for arm, cases in sorted(by.items()):
        per = defaultdict(list)
        react, greact, pushes, nodef, elx, plays, cpu, cpu_s, noise = [], [], 0, 0, [], [], [], [], Counter()
        todec, dps = [], []
        for (i, opp), r in cases.items():
            per[opp].append(score(r))
            rr = reaction(r)
            react += [x for x, _ in rr]
            greact += [x for x, c in rr if c == 'Giant']
            todec += to_decision(r)
            m = analyse(r.get('packet_perc') or [], r.get('packet_dec') or [], {})
            pushes += len(m['giant_pushes'])
            nodef += sum(p['no_def_before_contact'] for p in m['giant_pushes'])
            elx += [p['elixir_cross'] for p in m['giant_pushes'] if p['elixir_cross'] is not None]
            plays.append(sum(m['plays'].values()))
            t = (r['result'].get('timing') or {}).get(str(r['seat'])) or {}
            if t.get('decisions'):
                cpu.append(1000 * t['cpu'] / t['decisions'])
                cpu_s.append(t['cpu'] / max(1, r['result']['ticks'] / 20))
                dps.append(t['decisions'] / max(1, r['result']['ticks'] / 20))
            noise.update(r.get('noise_counts') or {})
        n = sum(len(v) for v in per.values())
        out['arms']['%s:%s' % arm] = dict(
            games=n, score={o: round(sum(v) / len(v), 3) for o, v in sorted(per.items())},
            reaction_p50_p90=[q(react, .5), q(react, .9)], giant_reaction_p50_p90=[q(greact, .5), q(greact, .9)],
            enemy_to_decision_p10_p50_p90=[q(todec, .1), q(todec, .5), q(todec, .9)],
            giant_pushes=pushes, undefended=round(nodef / max(1, pushes), 3), elixir_cross_p50=q(elx, .5),
            plays_per_battle=round(sum(plays) / max(1, len(plays)), 1),
            cpu_ms_per_decision=q(cpu, .5), cpu_s_per_game_s=q(cpu_s, .5), decisions_per_game_s=q(dps, .5),
            noise_per_game={k: round(v / max(1, n), 2) for k, v in noise.items()})
    ref = by.get(tuple(a.ref.split(':', 1)))
    if ref:
        for arm, cases in sorted(by.items()):
            if '%s:%s' % arm == a.ref:
                continue
            pairs = defaultdict(list)
            for k, r in cases.items():
                if k in ref:
                    pairs[k[1]].append(score(r) - score(ref[k]))
            if not pairs:
                continue
            rng = random.Random(0)
            opps = sorted(pairs)
            pt = sum(sum(v) / len(v) for v in pairs.values()) / len(opps)
            draws = sorted(sum(sum(v[rng.randrange(len(v))] for _ in v) / len(v) for v in pairs.values()) / len(opps)
                           for _ in range(4000))
            row = dict(n=sum(len(v) for v in pairs.values()), pooled=round(pt, 3),
                       ci=[round(draws[100], 3), round(draws[3900], 3)])
            for o, v in pairs.items():
                d = sorted(sum(v[rng.randrange(len(v))] for _ in v) / len(v) for _ in range(4000))
                row[o] = [round(sum(v) / len(v), 3), round(d[100], 3), round(d[3900], 3), len(v)]
            out['paired']['%s:%s' % arm] = row
    text = json.dumps(out, indent=1)
    if a.json:
        Path(a.json).write_text(text + '\n')
    print(text)


if __name__ == '__main__':
    main(sys.argv[1:])
