"""Batch B2 review r1: Clone slide settling (arena edge, river, building footprint), native==Python, both seats.

Each case: a level-11 Knight is placed (Python, before export) at a point, the owner casts Clone on it, both engines
step 30 ticks with digest + per-unit position comparison. Prints the final Knight positions (original, copy).
Usage (PYTHONPATH = native : engine-rs : src : engine-speed): probe_clone_bounds.py OUT.json
"""
import json, sys, traceback
from differential import config, initial, snapshot, battle_digest, clasher_core, Position

CARDS = ('Clone', 'Knight', 'Giant', 'Archers', 'Musketeer')
# case: (Knight point, Clone cast point)
CASES = {'back_edge': ((4.5, 0.5), (4.5, 2.5)), 'river_front': ((9.0, 14.6), (9.0, 14.6)),
         'own_tower': ((3.5, 8.6), (3.5, 8.6))}


def one(point, cast, seat):
    m = (lambda t: t) if seat == 0 else (lambda t: (18 - t[0], 32 - t[1]))
    cfg = config(CARDS)
    b = initial(7, cards=CARDS)
    p = b.players[seat]
    p.hand = ['Knight', 'Clone', 'Giant', 'Archers']; p.cycle_queue.clear(); p.cycle_queue.extend(['Musketeer'])
    p.elixir = 10.0
    assert b.deploy_card(seat, 'Knight', Position(*m((4.5, 8.5))))
    for _ in range(25):
        b.step()
    knight = next(e for e in b.entities.values() if e.player_id == seat and getattr(e.card_stats, 'name', '') == 'Knight')
    knight.position = Position(*m(point))
    p.elixir = 10.0
    native = clasher_core.BattleState(snapshot(b, cfg))
    out = dict(seat=seat, point=m(point), first=None)
    out['cast'] = [bool(b.deploy_card(seat, 'Clone', Position(*m(cast)))), bool(native.apply_action(seat, 'Clone', *m(cast)))]
    for t in range(30):
        b.step(); native.step(1)
        ns = {r['id']: r for r in json.loads(native.snapshot())['entities']}
        knights = [e for e in b.entities.values() if e.is_alive and getattr(e.card_stats, 'name', '') == 'Knight']
        pos = [(round(e.position.x, 3), round(e.position.y, 3)) for e in knights]
        rpos = [(round(ns[e.id]['x'], 3), round(ns[e.id]['y'], 3)) if e.id in ns else None for e in knights]
        if native.digest() != battle_digest(b) or pos != rpos:
            out['first'] = t
            out['py'], out['rs'] = pos, rpos
            break
        if t in (0, 10, 29):
            out[f'pos{t + 1}'] = pos
    return out


if __name__ == '__main__':
    res = []
    for name, (point, cast) in CASES.items():
        for seat in (0, 1):
            try:
                r = dict(case=name, **one(point, cast, seat))
            except BaseException:
                r = dict(case=name, seat=seat, error=traceback.format_exc(limit=4)[-600:])
            res.append(r)
            print(json.dumps(r), flush=True)
    json.dump(res, open(sys.argv[1], 'w'), indent=1)
