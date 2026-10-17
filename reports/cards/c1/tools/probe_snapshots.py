"""Batch C1: compare combat state from complete snapshots, beyond the digest (lead note 2026-10-16: B2 found
digest-equal divergences). Lockstep like batchA/tools/probe_native_scen.py; after every tick each Python entity is
exported with live_snapshot.live_entity (the native import format) and compared field by field with the native
snapshot's entity (hit sets, buffs, slows, periodic, hastes, strike/shot targets, clocks, dash/leap/hook/axe/chain/
counter state, ...). CHECK/CLASS_FIELDS below explicitly select semantic fields and document baseline exclusions;
this is not a byte-for-byte comparison of every private/import-only field. Floats are rounded to 1e-6; None keys
are dropped on both sides; `stats` is compared once per non-projectile entity. Per scenario it records each
field's first divergence tick, count, and example.

Usage (PYTHONPATH = native : engine-rs : src : engine-speed : batchA tools : c1 tools):
  probe_snapshots.py OUT.json --scen CARD ... | --cases NAME ... (c1 probe_c1_cases names; 'all' = every case)
"""
import json, sys, traceback
from scenarios import script, scenarios
from differential import config, initial, snapshot, battle_digest, clasher_core, Position
from live_snapshot import live_entity
import probe_native_scen as P

STATIC = ('stats',)
# Semantic state compared on every entity: hit sets, buffs/slows/periodic/stun/freeze, strike and shot targets,
# hp/position/push, special-move states and every new C1 private field. Fields excluded on purpose: import-only
# defaults that the Python export fills for every entity (aim/birth/chain_*/temporary_*/piercing/spirit*/
# roll_direction/launch_delay/projectile_origin on non-projectiles) and the legacy private fields that already
# differ on a pure-C56 digest-equal control (Knight, Musketeer: cooldown, age, attacked_current, lane,
# last_target, started, public_speed_base, route_occupied, frozen_stop, facing, direction, nav_target,
# pending_ms, pending_lethal, tunnel_total, avoidance, finish_tick, landed_tick, push_tick, clock when either
# side has no initialized clock).
CHECK = ('alive', 'class', 'hp', 'x', 'y', 'target', 'move_target', 'hit_ids', 'area_slows', 'slow_ms', 'periodic',
         'hastes', 'stun', 'freeze_pause', 'freeze_expiry', 'shield', 'push', 'push_velocity', 'push_reset',
         'push_preserve', 'jump', 'dash', 'leap', 'hook', 'deploy', 'stagger', 'hidden', 'underground', 'scope',
         'production', 'death_immunity', 'stealth_until', 'charge', 'force_due', 'windup', 'moving', 'controlled_vector',
         'pp_t', 'pp_origin', 'pp_apex', 'pp_axe', 'chain_wait', 'counter_ready', 'counter_pending', 'ovl_load',
         'ovl_target', 'kamikaze_primed', 'effect_applied', 'damage_ticks', 'strikes_elapsed')
# Class-owned fields (elsewhere the Python export leaves them None and the native keeps its default). A homing
# Projectile's `aim` is excluded: Python exports the target's live position, native stores the last aim and
# re-aims from the target each update.
CLASS_FIELDS = {
    'Projectile': ('shot_target', 'launch_delay', 'projectile_origin'),
    'SpawnProjectile': ('shot_target', 'launch_delay', 'projectile_origin'),
    'RollingProjectile': ('aim', 'roll_direction'),
    'PingpongProjectile': ('aim',),
    'ChainLightning': ('aim', 'shot_target', 'chain_origin', 'chain_remaining', 'chain_time'),
}


def norm(v):
    if isinstance(v, float):
        return round(v, 6)
    if isinstance(v, (list, tuple)):
        return [norm(x) for x in v]
    if isinstance(v, dict):
        return {k: norm(x) for k, x in sorted(v.items()) if x is not None}
    return v


def _is_default(v):
    return v in (0, False, '', [], {}) or (isinstance(v, list) and all(x == 0 for x in v))


def strip_defaults(v):
    """Nested serialized entities (a scope's child/impact templates): native writes every serde-default
    field and skips some at their default, the Python export omits others; import fills a missing key with
    its default, so only a key whose value is its zero default is dropped. Any nonzero value stays compared."""
    if isinstance(v, dict):
        # public_identity/public_static are export-only observation metadata (differential.entity): the native
        # Entity has no such fields and serde ignores them on import.
        return {k: strip_defaults(x) for k, x in v.items()
                if not _is_default(x) and k not in ('public_identity', 'public_static')}
    if isinstance(v, list):
        return [strip_defaults(x) for x in v]
    return v


def resolve_reseed(e):
    """Apply a pending cooldown write exactly as lib.rs Entity.consume_clock_reseed does at the next combat
    update (clock.rs stop/refund_now included). Python defers a cooldown write to get_clock() and exports it as
    `clock_reseed`; native sometimes applies the same write at once. Both sides are resolved, so a real clock or
    due-latch difference after resolution is still reported."""
    remaining, clock, stats = e.get('clock_reseed'), e.get('clock'), e.get('stats') or {}
    if remaining is None or not isinstance(clock, dict):
        return e
    c = dict(clock)
    e = dict(e, clock=c, clock_reseed=None)
    if stats.get('ordinary'):
        e['clock_initialized'] = True
    finish = c.get('finish', 0)
    if c.get('refund', 0) and 0 < c.get('timeline', 0) < c['interval']:
        c['remaining'] = max(c['load'] - c['timeline'], 0)
    c['timeline'] = 0
    e['force_due'] = remaining == 0
    first = c['interval'] - c['load']
    if 0 < remaining < first:
        c['timeline'] = c['interval'] - remaining
        c['remaining'] = 0
    else:
        c['remaining'] = min(c['load'], max(remaining - first, 0))
    c['finish'] = finish
    return e


def normalize_owned_fields(p, r, keys):
    """Only proved C1 representations; see SNAPSHOT-DIAGNOSTICS.md and followup-final.json.

    Never alter the engine state, erase hit history, or normalize a nonzero phase.
    """
    keys = list(keys)
    if p.get('class') == r.get('class') == 'PingpongProjectile':
        p = dict(p, hit_ids=sorted(p.get('hit_ids', [])))
        r = dict(r, pp_t=r.get('pp_t', 0), hit_ids=sorted(r.get('hit_ids', [])))
        ps, rs = p.get('stats', {}), r.get('stats', {})
        pp_spec = ('pingpong_period', 'pingpong_start', 'pingpong_reach')
        spec_equal = ps.get('pingpong_period', 0) > 0 and all(
            k in ps and ps[k] == rs.get(k, 0) for k in pp_spec)
        endpoints_equal = all(isinstance(p.get(k), list) and len(p[k]) == 2 and p[k] == r.get(k)
                              for k in ('pp_origin', 'pp_apex'))
        phase_equal = p.get('pp_t') == r.get('pp_t') and isinstance(p.get('pp_t'), int)
        if spec_equal and endpoints_equal and phase_equal and 0 <= p['pp_t'] <= ps['pingpong_period']:
            # entities.py PingpongProjectile._pp_point/update never reads target_position;
            # projectiles.rs:31 reads only pp_origin/apex/t + pp spec. All remain compared.
            keys = [k for k in keys if k != 'aim']
    elif p.get('class') == r.get('class') == 'RollingProjectile' and p.get('spell_name') and r.get('spell_name'):
        # A spell roll (Log, Barbarian Barrel): lib.rs rolling_tick moves by owner direction, traveled range and
        # the spell radius and never reads `aim`; the Python export has no target for it. The character boulder
        # (empty spell_name, rolling_character_tick reads aim) stays strictly compared.
        keys = [k for k in keys if k != 'aim']
    elif p.get('class') == r.get('class') and p.get('class') in ('Projectile', 'SpawnProjectile'):
        # projectiles.rs projectile_children is the sole native origin reader and needs child damage and range
        # (entities.py reads launch_position for the same children). A shot that can spawn none on either
        # side has no reader; any child-capable shot keeps the origin strictly compared.
        ps, rs = p.get('stats', {}), r.get('stats', {})
        if all(s.get('child_damage', 0) <= 0 or s.get('child_range', 0) <= 0 for s in (ps, rs)):
            keys = [k for k in keys if k != 'projectile_origin']
    return p, r, keys


def compare(b, cfg, native, t, seen_static, classes):
    native_state = json.loads(native.snapshot())
    if norm(getattr(b, '_orphan_counter_pending', [])) != norm(native_state.get('orphan_counter_pending', [])):
        c = classes.setdefault('<orphan_counter_pending>', dict(first=t, count=0,
                              example=[getattr(b, '_orphan_counter_pending', []), native_state.get('orphan_counter_pending', [])]))
        c['count'] += 1
    py = {e.id: norm(live_entity(e, b, cfg)) for e in b.entities.values()}
    rs = {e['id']: norm(e) for e in native_state['entities']}
    if set(py) != set(rs):
        classes.setdefault('<ids>', dict(first=t, count=0, example=[sorted(set(py) - set(rs)), sorted(set(rs) - set(py))]))
        classes['<ids>']['count'] += 1
    for i in set(py) & set(rs):
        p, r = resolve_reseed(py[i]), resolve_reseed(rs[i])
        keys = list(CHECK) + list(CLASS_FIELDS.get(p.get('class'), ()))
        p, r, keys = normalize_owned_fields(p, r, keys)
        if p.get('push') is None and r.get('push') is None:
            # push_* are stale on the native after a push ends (also on C56 Firecracker); read only while set.
            keys = [k for k in keys if k not in ('push_velocity', 'push_reset', 'push_preserve')]
        if p.get('class') in CLASS_FIELDS:
            # A native shot is a clone of its shooter: its status fields copy the shooter's and are never read.
            # Production (Witch's spawner) ticks only in the character/building object branch (lib.rs).
            keys = [k for k in keys if k not in ('slow_ms', 'area_slows', 'hastes', 'stun', 'freeze_pause',
                                                 'freeze_expiry', 'periodic', 'shield', 'move_target', 'target',
                                                 'production')]
        if p.get('clock_initialized') and r.get('clock_initialized'):
            keys.append('clock')
        if (p.get('stun') or 0) > 0 and (r.get('stun') or 0) > 0:
            # move_target is per-tick scratch: native stun_target_mode clears it, Python apply_stun leaves it,
            # and both reset it first in the next combat component, before any reader (avoidance runs in movement;
            # the stun's own frozen_moving read happens only on the first stun, when both still agree).
            keys = [k for k in keys if k != 'move_target']
        if i not in seen_static and p.get('class') not in CLASS_FIELDS:
            # Native omits skip-serialized stats at their inert default; native shots clone the shooter's stats.
            ps, rsd = p.get('stats') or {}, r.get('stats') or {}
            for x in set(ps) | set(rsd):
                if x not in rsd and not ps.get(x):
                    rsd = dict(rsd, **{x: ps.get(x)})
            p, r = dict(p, stats=ps), dict(r, stats=rsd)
            keys += list(STATIC)
        if isinstance(p.get('scope'), dict) or isinstance(r.get('scope'), dict):
            p, r = dict(p, scope=strip_defaults(p.get('scope'))), dict(r, scope=strip_defaults(r.get('scope')))
        for k in keys:
            pv, rv = p.get(k), r.get(k)
            if k == 'hit_ids':
                # Membership only on both sides (Python sets; native contains/push/extend, never iterated or
                # digested): order is dropped, multiplicity kept.
                pv, rv = sorted(pv or []), sorted(rv or [])
            if (pv is None and _is_default(rv)) or (rv is None and _is_default(pv)):
                # One side omits a key at its serde default (e.g. native skips chain_wait 0).
                continue
            if pv != rv:
                if k == 'stats':
                    label = 'stats.' + ','.join(sorted(x for x in set(p[k]) | set(r[k]) if p[k].get(x) != r[k].get(x)))
                else:
                    label = k
                c = classes.setdefault(label, dict(first=t, count=0, example=[i, p.get('class'), str(p.get(k))[:160], str(r.get(k))[:160]]))
                c['count'] += 1
        seen_static.add(i)


def run(name, seq, end, setup=None):
    out = dict(name=name, ticks=end, classes={}, digest_first=None)
    try:
        names = list(dict.fromkeys([n for _, n, _, _ in seq] + list(P.FILL)))
        cards = tuple(names[:8]); cfg = config(cards); b = initial(7, cards=cards)
        for p in b.players:
            p.elixir = 10.0
        for side in (0, 1):
            mine = list(dict.fromkeys(n for s, n, _, _ in seq if s == side)); p = b.players[side]
            p.hand = (mine + [c for c in cards if c not in mine])[:4]
            p.cycle_queue.clear(); p.cycle_queue.extend(c for c in cards if c not in p.hand)
        native = clasher_core.BattleState(snapshot(b, cfg))
        bytick, seen = {}, set()
        for s, n, tile, t in seq:
            bytick.setdefault(t, []).append((s, n, tile))
        for t in range(end):
            for s, n, (x, y) in bytick.get(t, []):
                py_ok = b.deploy_card(s, n, Position(x, y))
                rs_ok = native.apply_action(s, n, x, y)
                assert py_ok and rs_ok, ('rejected deploy', t, s, n, py_ok, rs_ok)
            b.step(); native.step(1)
            if out['digest_first'] is None and native.digest() != battle_digest(b):
                out['digest_first'] = t
            compare(b, cfg, native, t, seen, out['classes'])
            if out['digest_first'] is not None:
                break
    except BaseException:
        out['error'] = traceback.format_exc(limit=4)[-800:]
    return out


if __name__ == '__main__':
    res = []
    mode, names = sys.argv[2], sys.argv[3:]
    if mode == '--cases':
        import probe_c1_cases as C
        names = list(C.CASES) if names == ['all'] else names
        jobs = [(n, *C.CASES[n]) for n in names]
    else:
        pool = {c['name']: c['kind'] for c in json.load(open(P.Path(P.__file__).parent / 'pool.json'))}
        pool.update({n: 'troop' for n in names if n not in pool})
        jobs = []
        for card in names:
            for sc in scenarios(dict(name=card, kind=pool[card])):
                seq, end = script(dict(name=card, kind=pool[card]), sc)
                jobs.append((f'{card}/{sc}', seq, end))
    for name, seq, end in jobs:
        r = run(name, seq, end); res.append(r)
        print(name, 'digest', r['digest_first'], 'fields', {k: (v['first'], v['count']) for k, v in sorted(r['classes'].items())},
              (r.get('error') or '').strip().splitlines()[-1:], flush=True)
        json.dump(res, open(sys.argv[1], 'w'), indent=1)
