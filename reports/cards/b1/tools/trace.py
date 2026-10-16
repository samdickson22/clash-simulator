"""Side-by-side per-tick trace of one fidelity scenario (ours / RoyaleSim), for debugging.
Usage (08, env as run_fid.sh): trace.py CARD KIND SCENARIO FROM TO [NAME ...]
Prints, per tick in [FROM, TO), every side-0/1 non-tower unit (or only NAMEs): name side x y hp deploy target."""
import json, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import scenarios as S

card, kind, scen, lo, hi = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
names = set(sys.argv[6:])
seq, end = S.script(dict(name=card, kind=kind), scen)
n0 = [x[1] for x in seq if x[0] == 0]; n1 = [x[1] for x in seq if x[0] == 1]
_, _, Play = S.adapters()
eng = {}
for k in ('ours', 'rsim'):
    e, ids = S.make_engine(k, n0, n1, 'adapter')
    eng[k] = (e, ids, json.loads(e.b.unit_types_json()) if k == 'rsim' else None)
bytick = defaultdict(list)
for side, n, tile, t in seq:
    bytick[t].append((side, n, tile))
fmt = lambda u: f"{u['name'][:14]:14s}s{u['side']} ({u['x']:.3f},{u['y']:.3f}) hp{u['hp']} d{u['deploy']} t{u.get('target')}"
for t in range(min(hi, end)):
    rows = {}
    for k, (e, ids, types) in eng.items():
        for side, n, tile in bytick[t]:
            e.deploy(Play(side=side, card=n, card_id=ids[n], kind='card', tile=tile, exec_tick=S.START+t, command_tick=S.START+t, slot=-1))
        e.step()
        if t + 1 >= lo:
            rows[k] = sorted((u for u in S.snapshot(e, k, types) if u['tower'] is None and (not names or u['name'] in names)),
                             key=lambda u: (u['side'], u['name'], u['id']))
    if t + 1 >= lo:
        print(f'== {t+1}')
        a, b = rows['ours'], rows['rsim']
        for i in range(max(len(a), len(b))):
            print('  ', fmt(a[i]) if i < len(a) else ' ' * 60, ' | ', fmt(b[i]) if i < len(b) else '')
