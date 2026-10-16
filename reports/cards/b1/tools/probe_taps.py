"""Native-vs-Python lockstep for one card played at several taps by both seats (extends probe_native_scen.py).
Usage (PYTHONPATH as probe_native_scen.py): probe_taps.py OUT.json CARD x,y[,side] ...   (each tap = one game,
the card deployed at tick 0 by that side, an enemy Knight at the mirrored lane tile; 400 ticks, digest every tick)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe_native_scen as P

out, card, taps = sys.argv[1], sys.argv[2], sys.argv[3:]
res = []
for tap in taps:
    parts = tap.split(',')
    x, y = float(parts[0]), float(parts[1]); side = int(parts[2]) if len(parts) > 2 else 0
    other = 1 - side
    ky = 17.5 if other == 1 else 14.5
    import os
    enemy = os.environ.get('ENEMY', 'Knight')
    if enemy in ('Fireball', 'Zap', 'Arrows', 'Log', 'Poison', 'Lightning', 'Rocket', 'Freeze', 'Tornado', 'Earthquake'):
        # cast on the played unit once it is out of deployment and walking
        seq = [(side, card, (x, y), 0), (other, enemy, (x, y + (2.0 if side == 0 else -2.0)), int(os.environ.get('ENEMY_TICK', 40)))]
    else:
        seq = [(side, card, (x, y), 0), (other, enemy, (x, ky), 5)]
    P.script = lambda c, s, seq=seq: (seq, 400)
    r = P.one(card, 'troop', tap); res.append(r)
    print(card, tap, r.get('native'), r.get('first_mismatch'), [d for d in r.get('deploys', []) if not d[3] or not d[4]], (r.get('error') or '').strip().splitlines()[-1:], flush=True)
json.dump(res, open(out, 'w'), indent=1)
