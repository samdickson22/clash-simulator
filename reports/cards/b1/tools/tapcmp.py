"""Ours vs RoyaleSim: unit positions one tick after CARD is played at each tap by side 0 (harness adapters).
Usage (08, env as run_fid.sh): tapcmp.py CARD x,y ..."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import scenarios as S
card = sys.argv[1]
_, _, Play = S.adapters()
for tap in sys.argv[2:]:
    x, y = map(float, tap.split(','))
    rows = {}
    for k in ('ours', 'rsim'):
        e, ids = S.make_engine(k, [card], ['Knight'], 'adapter')
        types = __import__('json').loads(e.b.unit_types_json()) if k == 'rsim' else None
        ok = e.deploy(Play(side=0, card=card, card_id=ids[card], kind='card', tile=(x, y), exec_tick=S.START, command_tick=S.START, slot=-1))
        e.step()
        rows[k] = (ok, sorted((round(u['x'], 3), round(u['y'], 3)) for u in S.snapshot(e, k, types) if u['tower'] is None and u['side'] == 0))
    same = rows['ours'] == rows['rsim']
    print(tap, 'SAME' if same else 'DIFF', '' if same else rows)
