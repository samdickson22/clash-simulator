#!/usr/bin/env python3
"""Per-tick unit trace of one fidelity scenario in both engines (debugging aid, Batch B2).

Usage (from b2/fid, env as run_fid.sh): trace.py CARD SCENARIO [--names Knight,Minion] [--from T] [--to T] [--table adapter]
Prints, per relative tick, every non-tower unit (name, side, x, y, hp, deploy) in ours and RoyaleSim, matched by
(side, name, birth order); flags the first tick where position (>0.001 tile) or hp differ for each pair.
Uses the harness's own script()/snapshot()/make_engine(); RoyaleSim (MIT) only through its Python binding.
"""
import argparse, json, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import scenarios as S

ap = argparse.ArgumentParser()
ap.add_argument('card'); ap.add_argument('scenario')
ap.add_argument('--names', default=''); ap.add_argument('--from', dest='t0', type=int, default=0)
ap.add_argument('--to', dest='t1', type=int, default=10**9); ap.add_argument('--table', default='adapter')
ap.add_argument('--all', action='store_true', help='print every tick, not only diverging ones')
ap.add_argument('--towers', action='store_true')
a = ap.parse_args()
pool = {c['name']: c for c in json.load(open(Path(__file__).resolve().parent / 'pool.json'))}
card = pool.get(a.card) or dict(name=a.card, kind='spell')
names = set(filter(None, a.names.split(',')))
ALIAS = {'GoblinCurseGoblin': 'Goblin', 'Graveyard_rework_Skeleton': 'Skeleton'}  # RoyaleSim body names -> ours


def run(kind):
    seq, end = S.script(card, a.scenario)
    e, ids = S.make_engine(kind, [x[1] for x in seq if x[0] == 0], [x[1] for x in seq if x[0] == 1], a.table)
    _, _, Play = S.adapters()
    types = json.loads(e.b.unit_types_json()) if kind == 'rsim' else None
    bytick = defaultdict(list)
    for side, n, tile, t in seq:
        bytick[t].append((side, n, tile))
    order, frames = {}, []
    for t in range(end):
        for side, n, tile in bytick[t]:
            e.deploy(Play(side=side, card=n, card_id=ids[n], kind='card', tile=tile, exec_tick=S.START+t,
                          command_tick=S.START+t, slot=-1))
        e.step()
        fr = {}
        for u in S.snapshot(e, kind, types):
            if u['tower'] is not None and not a.towers:
                continue
            nm = ALIAS.get(u['name'], u['name']) if u['tower'] is None else f"T{u['tower']}"
            if names and nm not in names:
                continue
            key = (u['side'], nm)
            if (key, u['id']) not in order:
                order[(key, u['id'])] = sum(1 for k in order if k[0] == key)
            fr[(u['side'], nm, order[(key, u['id'])])] = (round(u['x'], 4), round(u['y'], 4), u['hp'], u['deploy'])
        frames.append(fr)
    return frames


ours, rs = run('ours'), run('rsim')
first = {}
for t, (fo, fr) in enumerate(zip(ours, rs), start=1):
    if t < a.t0 or t > a.t1:
        continue
    keys = sorted(set(fo) | set(fr), key=str)
    rows = []
    for k in keys:
        o, r = fo.get(k), fr.get(k)
        bad = (o is None) != (r is None) or (o and r and (abs(o[0]-r[0]) > 1e-3 or abs(o[1]-r[1]) > 1e-3 or o[2] != r[2]))
        if bad and k not in first:
            first[k] = t
        if a.all or bad:
            rows.append(f"  {k}: ours={o} rs={r}{'  <<' if bad else ''}")
    if rows:
        print(f"t={t}"); print('\n'.join(rows))
print('first divergence per unit:', {str(k): v for k, v in sorted(first.items(), key=lambda kv: kv[1])})
