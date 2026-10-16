"""B1+B2 merge: target acquisition around stun / freeze expiry, native == Python, both seats.

A victim (side V) stands with an enemy target in reach; a stun/freeze source from the enemy side hits it at tick
CAST; both engines step END ticks and every tick compare battle_digest plus every alive entity's `target` and `hp`
(Python live export vs native snapshot). Usage (PYTHONPATH = native : engine-rs : src : engine-speed):
probe_stun_target.py OUT.json
"""
import json, sys, traceback
from differential import config, initial, snapshot, battle_digest, clasher_core, Position
from live_snapshot import live_entity

VICTIMS = ['Knight', 'Musketeer', 'Giant', 'Cannon']
SOURCES = ['Zap', 'IceSpirit', 'ElectroSpirit', 'Freeze', 'Vines', 'Lightning', 'ElectroWizard', 'Snowball']
FILL = ('Archers', 'Minions')
END = 160


def one(victim, source, seat, cast):
    m = (lambda t: t) if seat == 0 else (lambda t: (18 - t[0], 32 - t[1]))
    cards = tuple(dict.fromkeys((victim, source, 'Knight') + FILL))[:8]
    cfg = config(cards)
    b = initial(7, cards=cards)
    for s in (0, 1):
        p = b.players[s]
        want = [victim] if s == seat else [source, 'Knight']
        p.hand = (want + [c for c in cards if c not in want])[:4]
        p.cycle_queue.clear(); p.cycle_queue.extend(c for c in cards if c not in p.hand)
        p.elixir = 10.0
    vt = (4.5, 9.5) if victim == 'Cannon' else (4.5, 12.5)
    assert b.deploy_card(seat, victim, Position(*m(vt)))
    for _ in range(25):
        b.step()
    for p in b.players:
        p.elixir = 10.0
    native = clasher_core.BattleState(snapshot(b, cfg))
    out = dict(victim=victim, source=source, seat=seat, cast=cast, first=None)
    # an enemy Knight walks in; the source lands on the victim at tick `cast`
    for t in range(END):
        if t == 0:
            ok = (b.deploy_card(1 - seat, 'Knight', Position(*m((4.5, 17.5)))),
                  native.apply_action(1 - seat, 'Knight', *m((4.5, 17.5))))
            out['knight'] = ok
        if t == cast:
            v = next((e for e in b.entities.values() if e.player_id == seat and e.is_alive
                      and getattr(e.card_stats, 'name', '') == victim), None)
            tile = (v.position.x, v.position.y) if v is not None else m(vt)
            if source in ('IceSpirit', 'ElectroSpirit', 'ElectroWizard'):
                tile = (tile[0], tile[1] + (3.0 if seat == 0 else -3.0))
                tile = (tile[0], max(17.5, tile[1]) if seat == 0 else min(14.5, tile[1]))
            out['cast_ok'] = (bool(b.deploy_card(1 - seat, source, Position(*tile))),
                              bool(native.apply_action(1 - seat, source, *tile)))
        b.step(); native.step(1)
        if native.digest() != battle_digest(b):
            out['first'], out['field'] = t, 'digest'
            break
        rows = {r['id']: r for r in json.loads(native.snapshot())['entities']}
        for e in b.entities.values():
            if not e.is_alive or e.id not in rows:
                continue
            pe = live_entity(e, b, cfg)
            for k in ('target', 'hp', 'stun'):
                if pe.get(k) is not None and pe.get(k) != rows[e.id].get(k) and not (
                        isinstance(pe.get(k), float) and abs(pe[k] - rows[e.id].get(k, 0)) < 1e-9):
                    out['first'], out['field'] = t, f'e{e.id}:{getattr(e.card_stats, "name", "")}.{k} py={pe.get(k)} rs={rows[e.id].get(k)}'
                    break
            if out['first'] is not None:
                break
        if out['first'] is not None:
            break
    return out


if __name__ == '__main__':
    res = []
    for victim in VICTIMS:
        for source in SOURCES:
            for seat in (0, 1):
                for cast in (20, 33, 47):
                    try:
                        r = one(victim, source, seat, cast)
                    except BaseException:
                        r = dict(victim=victim, source=source, seat=seat, cast=cast, error=traceback.format_exc(limit=3)[-400:])
                    res.append(r)
                    if r.get('first') is not None or 'error' in r:
                        print(json.dumps(r)[:400], flush=True)
    bad = [r for r in res if r.get('first') is not None or 'error' in r]
    print(json.dumps(dict(runs=len(res), bad=len(bad))), flush=True)
    json.dump(res, open(sys.argv[1], 'w'), indent=1)
