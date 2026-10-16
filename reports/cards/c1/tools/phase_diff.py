"""Localize a native!=Python divergence in one fidelity scenario: lockstep to tick T-1, then
diagnostics.phase_step (before/start/combat/movement/objects/cleanup) and print the field differences.
Usage (PYTHONPATH = native : engine-rs : src : engine-speed : batchA tools dir): phase_diff.py CARD SCENARIO T [N]"""
import sys, json
from scenarios import script
from differential import config, initial, snapshot, battle_digest, clasher_core, Position
from diagnostics import phase_step
import probe_native_scen as P

card, scen, T = sys.argv[1], sys.argv[2], int(sys.argv[3])
n = int(sys.argv[4]) if len(sys.argv) > 4 else 20
kind = json.load(open(P.Path(P.__file__).parent / 'pool.json'))
kind = {c['name']: c['kind'] for c in kind}[card]
seq, end = script(dict(name=card, kind=kind), scen)
names = list(dict.fromkeys([nm for _, nm, _, _ in seq] + list(P.FILL)))
cards = tuple(names[:8]); cfg = config(cards); b = initial(7, cards=cards)
for p in b.players:
    p.elixir = 10.0
for side in (0, 1):
    mine = list(dict.fromkeys(nm for s, nm, _, _ in seq if s == side))
    p = b.players[side]; p.hand = (mine + [c for c in cards if c not in mine])[:4]
    p.cycle_queue.clear(); p.cycle_queue.extend(c for c in cards if c not in p.hand)
native = clasher_core.BattleState(snapshot(b, cfg))
bytick = {}
for s, nm, tile, t in seq:
    bytick.setdefault(t, []).append((s, nm, tile))
for t in range(T + 1):
    for s, nm, (x, y) in bytick.get(t, []):
        assert bool(b.deploy_card(s, nm, Position(x, y))) == bool(native.apply_action(s, nm, x, y))
    if t == T:
        ph = phase_step(b, native)
        base = {json.dumps(d, sort_keys=True) for d in ph['before']['field_diff']}
        for label, data in ph.items():
            fd = [d for d in data['field_diff'] if json.dumps(d, sort_keys=True) not in base]
            print(label, len(fd), '(new vs before)')
            for d in fd[:n]:
                print('   ', d)
        break
    b.step(); native.step(1)
    assert native.digest() == battle_digest(b), f'earlier mismatch at {t}'
