"""Batch B2 review r1: native==Python for every effect path that meets a Bandit in dash travel (both seats).

For each case (an effect source) and each offset L in LEADS (ticks from the cast to the forced dash launch):
  * L > 0: Python casts, steps L ticks, then the Bandit is put back on P and launched (BanditDash._launch_dash toward
    the enemy King Tower), and the state is exported to native;
  * L <= 0: the Bandit is launched and exported first, and both engines cast on lockstep tick -L.
Both engines then step END ticks; every tick compares battle_digest, the Bandit's status (hp, position, stun timer,
slow and periodic-buff counts, hastes, freeze expiry, shield) and every scope area's exported state. `overlap` counts ticks where the
Python Bandit was in dash travel within 4 tiles of the cast while a spell object (area/projectile/strike) was alive
or on the lockstep cast tick itself,
i.e. the path was exercised. Usage (PYTHONPATH = native : engine-rs : src : engine-speed):
probe_dash_paths.py OUT.json [CASE ...]
"""
import json, sys, traceback
from differential import config, initial, snapshot, battle_digest, clasher_core, Position, entity
from scope_snapshot import effect_state

P = (9.0, 10.5)  # the Bandit's point (blue seat)
FILL = ('Knight', 'Giant', 'Archers', 'Musketeer')
LEADS = list(range(-4, 36))
END = 45
ENEMY, OWN = 'enemy', 'own'
CASES = {
    'zap': ('Zap', ENEMY, P), 'fireball': ('Fireball', ENEMY, P), 'arrows': ('Arrows', ENEMY, P),
    'rocket': ('Rocket', ENEMY, P), 'lightning': ('Lightning', ENEMY, P), 'log': ('Log', ENEMY, (9.0, 13.5)),
    'barblog': ('BarbLog', ENEMY, (9.0, 13.5)), 'snowball': ('Snowball', ENEMY, P),
    'earthquake': ('Earthquake', ENEMY, P), 'poison': ('Poison', ENEMY, P), 'freeze': ('Freeze', ENEMY, P),
    'tornado': ('Tornado', ENEMY, P), 'goblin_curse': ('GoblinCurse', ENEMY, P), 'vines': ('Vines', ENEMY, P),
    'void': ('DarkMagic', ENEMY, P), 'electro_spirit': ('ElectroSpirit', ENEMY, (9.0, 13.5)),
    'ice_spirit': ('IceSpirit', ENEMY, (9.0, 13.5)),
    'rage': ('Rage', OWN, P), 'heal': ('Heal', OWN, P), 'clone': ('Clone', OWN, P),
}
FIELDS = ('hp', 'x', 'y', 'stun', 'periodic', 'slows', 'hastes', 'freeze_expiry', 'shield')


def norm(v):
    if isinstance(v, float):
        return round(v, 6)
    if isinstance(v, (list, tuple)):
        return [norm(x) for x in v]
    if isinstance(v, dict):  # None-valued keys dropped: native omits fields skip-serialized at None
        return {k: norm(x) for k, x in sorted(v.items()) if x is not None}
    return v


def py_state(e):
    row = entity(e)
    return norm(dict(hp=float(e.hitpoints), x=row['x'], y=row['y'], stun=float(e.stun_timer),
                     periodic=len(e._periodic_damage_effects), slows=len(e._slow_effects), hastes=row.get('hastes'),
                     freeze_expiry=row.get('freeze_expiry'), shield=row.get('shield')))


def rs_state(r):
    return norm(dict(hp=float(r['hp']), x=r['x'], y=r['y'], stun=float(r.get('stun', 0.0)),
                     periodic=len(r.get('periodic', [])), slows=len(r.get('area_slows', [])) + int(r.get('slow_ms', 0) > 0),
                     hastes=r.get('hastes'), freeze_expiry=r.get('freeze_expiry'), shield=r.get('shield')))


def mirror(t, seat):
    return t if seat == 0 else (18 - t[0], 32 - t[1])


def one(card, side_kind, tile, lead, seat, cfg, cards):
    bs = seat                      # the Bandit's side
    cs = bs if side_kind == OWN else 1 - bs
    b = initial(7, cards=cards)
    for s in (0, 1):
        want = ['Bandit'] if s == bs else []
        if s == cs:
            want.append(card)
        p = b.players[s]
        p.elixir = 10.0
        p.hand = (want + [c for c in cards if c not in want])[:4]
        p.cycle_queue.clear(); p.cycle_queue.extend(c for c in cards if c not in p.hand)
    assert b.deploy_card(bs, 'Bandit', Position(*mirror(P, seat)))
    for _ in range(25):
        b.step()
    for p in b.players:
        p.elixir = 10.0
    bandit = next(e for e in b.entities.values() if e.player_id == bs and e.is_alive
                  and any(type(m).__name__ == 'BanditDash' for m in getattr(e, 'mechanics', [])))
    king = next(e for e in b.entities.values() if e.player_id == 1 - bs and getattr(e, '_crown_tower_slot', None) == 'king')
    dash = next(m for m in bandit.mechanics if type(m).__name__ == 'BanditDash')
    q = mirror(tile, seat)
    out = dict(lead=lead, first=None, field=None, overlap=0, cast=None)
    if lead > 0:
        bandit.position = Position(*mirror(P, seat))
        out['cast'] = [bool(b.deploy_card(cs, card, Position(*q))), None]
        for _ in range(lead):
            b.step()
    bandit.position = Position(*mirror(P, seat))
    bandit._bandit_charging = False
    dash._launch_dash(bandit, king)
    native = clasher_core.BattleState(snapshot(b, cfg))
    bid = bandit.id
    for t in range(END):
        if lead <= 0 and t == -lead:
            out['cast'] = [bool(b.deploy_card(cs, card, Position(*q))), bool(native.apply_action(cs, card, *q))]
        b.step(); native.step(1)
        if getattr(bandit, '_bandit_dashing', False) and bandit.is_alive and (
                (bandit.position.x - q[0]) ** 2 + (bandit.position.y - q[1]) ** 2 <= 16) and (
                (lead <= 0 and t == -lead) or any(
                e.is_alive and type(e).__name__ not in ('Troop', 'Building') for e in b.entities.values())):
            out['overlap'] += 1
        if native.digest() != battle_digest(b):
            out['first'], out['field'] = t, 'digest'
            break
        ns = json.loads(native.snapshot())
        nrows = {r['id']: r for r in ns['entities']}
        if bandit.is_alive and bid in nrows:
            pa, na = py_state(bandit), rs_state(nrows[bid])
            bad = [k for k in FIELDS if pa[k] != na[k]]
            if bad:
                out['first'], out['field'] = t, f'bandit:{bad[0]} py={pa[bad[0]]} rs={na[bad[0]]}'
                break
        for e in b.entities.values():
            st = effect_state(e) if e.is_alive else None
            # nested `child` / `impact` are static payload templates (native omits default-valued fields), not state
            strip = lambda d: {k: v for k, v in (d or {}).items() if k not in ('child', 'impact')}
            if st is not None and e.id in nrows and norm(strip(st)) != norm(strip(nrows[e.id].get('scope'))):
                out['first'], out['field'] = t, f'scope:{e.id}'
                break
        if out['first'] is not None:
            break
    return out


if __name__ == '__main__':
    names = sys.argv[2:] or list(CASES)
    res = []
    for n in names:
        card, kind, tile = CASES[n]
        cards = tuple(dict.fromkeys(('Bandit', card) + FILL))[:8]
        cfg = config(cards)
        for seat in (0, 1):
            rows = []
            for lead in LEADS:
                try:
                    rows.append(one(card, kind, tile, lead, seat, cfg, cards))
                except BaseException:
                    rows.append(dict(lead=lead, error=traceback.format_exc(limit=4)[-600:]))
            bad = [r for r in rows if r.get('first') is not None or 'error' in r]
            rec = dict(case=n, seat=('blue', 'red')[seat], runs=len(rows), mismatches=len(bad),
                       exercised=sum(1 for r in rows if r.get('overlap')), overlap_ticks=sum(r.get('overlap', 0) for r in rows),
                       first_bad=bad[0] if bad else None)
            res.append(rec)
            print(json.dumps(rec)[:400], flush=True)
    json.dump(res, open(sys.argv[1], 'w'), indent=1)
