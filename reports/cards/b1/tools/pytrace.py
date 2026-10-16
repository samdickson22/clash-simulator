"""Ours-only per-tick dump of chosen attributes for units of NAME in a fidelity scenario.
Usage: pytrace.py CARD KIND SCENARIO FROM TO NAME attr1,attr2,..."""
import sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import scenarios as S
card, kind, scen, lo, hi, name, attrs = sys.argv[1:8]
lo, hi = int(lo), int(hi); attrs = attrs.split(',')
seq, end = S.script(dict(name=card, kind=kind), scen)
n0 = [x[1] for x in seq if x[0] == 0]; n1 = [x[1] for x in seq if x[0] == 1]
_, _, Play = S.adapters()
e, ids = S.make_engine('ours', n0, n1, 'adapter')
bytick = defaultdict(list)
for side, n, tile, t in seq: bytick[t].append((side, n, tile))
for t in range(min(hi, end)):
    for side, n, tile in bytick[t]:
        e.deploy(Play(side=side, card=n, card_id=ids[n], kind='card', tile=tile, exec_tick=S.START+t, command_tick=S.START+t, slot=-1))
    e.step()
    if t + 1 >= lo:
        for u in e.b.entities.values():
            if getattr(u.card_stats, 'name', '') == name or S.body_name(u) == name:
                vals = []
                for a in attrs:
                    v = getattr(u, a, '?')
                    if a == 'target_id' or a == 'position': v = v
                    vals.append(f"{a}={v if not isinstance(v, float) else round(v, 4)}")
                print(t + 1, u.id, ' '.join(vals))
