"""Offline filter tuning on captured polls (bot/noise/player.py NR_DUMP: per poll the TRUE entity table and the raw
perceived one, recorded under an identity filter so the raw sequence does not depend on the filter).

    python -m bot.noise.tune DUMP_DIR TAG [TAG ...]

Per tag: unit (troop/building, towers excluded) recall, phantoms per poll, body accuracy among matches, and the
errors per poll split by owner (missed + phantom + wrong body), matching within `radius` tiles one-to-one.
"""
from __future__ import annotations

import math
import pickle
import sys
from collections import Counter
from pathlib import Path

import numpy as np

from bot.noise.filter import EntityFilter, parse_config, BOARD_W, BOARD_H


def units(ents, towers):
    return [(e[0], e[1][2] > .5, float(e[1][0])*BOARD_W, float(e[1][1])*BOARD_H) for e in ents
            if e[0] not in towers and int(np.argmax(e[1][4:9])) <= 1]


W = {}


def weight(tok):
    return W.get(tok, 1.)


def score(P, T, c, radius=1.0):
    cand = sorted((math.hypot(a[2]-b[2], a[3]-b[3]), i, j) for i, a in enumerate(P) for j, b in enumerate(T)
                  if a[1] == b[1])
    ui, uj = set(), set()
    for d, i, j in cand:
        if d > radius:
            break
        if i in ui or j in uj:
            continue
        ui.add(i); uj.add(j)
        side = 'own' if P[i][1] else 'opp'
        c[f'match_{side}'] += 1
        c[f'wrong_{side}'] += P[i][0] != T[j][0]
        c[f'wmatch_{side}'] += weight(T[j][0])
    for i, a in enumerate(P):
        if i not in ui:
            c[f'phantom_{"own" if a[1] else "opp"}'] += 1
            c[f'wphantom_{"own" if a[1] else "opp"}'] += weight(a[0])
    for j, b in enumerate(T):
        c[f'true_{"own" if b[1] else "opp"}'] += 1
        c[f'wtrue_{"own" if b[1] else "opp"}'] += weight(b[0])
        if j not in uj:
            c[f'missed_{"own" if b[1] else "opp"}'] += 1
            c[f'wmissed_{"own" if b[1] else "opp"}'] += weight(b[0])


def evaluate(games, tag, towers):
    c = Counter()
    for g in games:
        f = EntityFilter(parse_config(tag), towers)
        for tick, true, raw in g['polls']:
            out = raw if f.cfg.identity() else f.step(tick, raw)
            score(units(out, towers), units(true, towers), c)
            c['polls'] += 1
    return c


def report(tag, c):
    n = c['polls']
    tt = c['true_own'] + c['true_opp']
    m = c['match_own'] + c['match_opp']
    ph = c['phantom_own'] + c['phantom_opp']
    w = c['wrong_own'] + c['wrong_opp']
    err = {s: (c[f'missed_{s}'] + c[f'phantom_{s}'] + c[f'wrong_{s}'])/n for s in ('own', 'opp')}
    wm = {s: c[f'wmissed_{s}']/n for s in ('own', 'opp')}
    wp = {s: c[f'wphantom_{s}']/n for s in ('own', 'opp')}
    return (f'{tag:16s} rec {m/tt:.3f} ph/poll {ph/n:.3f} wrong {w/max(1, m):.3f} '
            f'miss/poll {(tt-m)/n:.3f} | W miss own {wm["own"]:.3f} opp {wm["opp"]:.3f} '
            f'W ph own {wp["own"]:.3f} opp {wp["opp"]:.3f} W total {sum(wm.values())+sum(wp.values()):.3f}')


def main():
    dump = Path(sys.argv[1])
    games = [pickle.loads(p.read_bytes()) for p in sorted(dump.glob('*.pkl'))]
    from bot.players.runtime import Runtime
    from bot.noise.player import tower_ids
    rt = Runtime()
    towers = set(tower_ids(rt))
    for (tok, kind), t in rt.R.templates.items():
        hp = float(t['stats'].get('max_hp') or 0)
        if kind in ('Troop', 'Building') and hp:
            W[int(tok)] = min(3., max(.05, hp/1000.))
    for tag in sys.argv[2:]:
        print(report(tag, evaluate(games, tag, towers)), flush=True)


if __name__ == '__main__':
    main()
