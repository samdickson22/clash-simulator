"""Phase-level native-vs-Python diff at the first mismatching tick of one fidelity scenario.
Usage (PYTHONPATH as probe_native_scen.py): phase_diff.py CARD KIND SCENARIO [MAXDIFFS]"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scenarios import script
from differential import config, initial, snapshot, battle_digest, clasher_core, Position
from diagnostics import phase_step
import probe_native_scen as P

sys.argv.pop(1)  # OUT placeholder from run_scen.sh
card, kind, scen = sys.argv[1:4]
maxd = int(sys.argv[4]) if len(sys.argv) > 4 else 40
seq, end = script(dict(name=card, kind=kind), scen)
names = list(dict.fromkeys([n for _, n, _, _ in seq] + list(P.FILL)))
cards = tuple(names[:8]); cfg = config(cards); b = initial(7, cards=cards)
for p in b.players: p.elixir = 10.0
for side in (0, 1):
    mine = list(dict.fromkeys(n for s, n, _, _ in seq if s == side))
    p = b.players[side]; p.hand = (mine + [c for c in cards if c not in mine])[:4]
    p.cycle_queue.clear(); p.cycle_queue.extend(c for c in cards if c not in p.hand)
native = clasher_core.BattleState(snapshot(b, cfg))
bytick = {}
for s, n, tile, t in seq: bytick.setdefault(t, []).append((s, n, tile))
for t in range(end):
    for s, n, (x, y) in bytick.get(t, []):
        b.deploy_card(s, n, Position(x, y)); native.apply_action(s, n, x, y)
    probe_b = None
    if native.digest() != battle_digest(b):
        print('pre-step mismatch at', t); break
    # step a copy-free way: run phase_step on the real objects only when the next step mismatches
    import copy
    state = native.snapshot()
    b2 = copy.deepcopy(b)
    b2.step(); native.step(1)
    if native.digest() != battle_digest(b2):
        print('first mismatch at step', t)
        native = clasher_core.BattleState(state) if False else native
        res = phase_step(b, clasher_core.BattleState(state))
        for label, r in res.items():
            print('==', label, len(r['field_diff']))
            for d in r['field_diff'][:maxd]:
                print('   ', d['field'], str(d['python'])[:150], '|', str(d['rust'])[:150])
            pass
        break
    b = b2
