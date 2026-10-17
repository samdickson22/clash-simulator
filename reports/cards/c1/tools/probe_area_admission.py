"""Admission class r2: area admission (invisibility), ground-surface gate, status/displacement writers.

Every row runs in both seats and compares Python and native every tick: the semantic full snapshot
(probe_snapshots.compare) and battle_digest, from the row's start state (Python's export). A row PASSES only
with no difference AND its witness:

- `stealth` rows: Python's can_receive_area_damage rejected an invisible target at the named site, and a
  Python counterfactual from the same start, where only that admission ignores invisibility (targeting is
  untouched), changes that target's hp/status. So the exclusion really decided the outcome at that site.
- `surface` rows: the same with is_above_ground_surface ignoring a Mega Knight mid-leap.
- `event` rows: the named Python call on the named target state happened (hidden Tesla status writers,
  mounted-rider knockback, dash blow on a hidden Tesla).

Start states are Python setups, plus explicit pre-run placements or a reachable forced state (a Tesla's hide
phase, a lethal hit at a chosen tick), chosen by a Python-only search for the witness; never a mid-tick edit.
Usage (PYTHONPATH as probe_snapshots.py): probe_area_admission.py OUT.json [ROW ...]
"""
import json
import sys
import traceback

import differential as D
from differential import Position, battle_digest, clasher_core, config, snapshot
import probe_snapshots as S
from probe_admission import setup, point, tesla_phase, launch_dash

EVENTS = []
CF = dict(stealth=False, surface=False)


def frame_site(depth=2):
    f = sys._getframe(depth)
    return getattr(f.f_code, 'co_qualname', f.f_code.co_name)


def install():
    from clasher import entities as E
    from clasher import spells as SP
    from clasher.cards import mega_knight as MK
    from clasher.mechanics.shared import knockback as KB
    from clasher import unit_traits as UT

    crad = E.Entity.can_receive_area_damage
    def crad_wrapped(self, source_kind=None, *, affects_hidden=False, source_entity=None):
        battle = getattr(self, 'battle_state', None)
        now = round(getattr(battle, 'time', 0.0) * 1000)
        stealthy = (int(getattr(self, '_stealth_until', 0) or 0) > now and not bool(
            getattr(getattr(self, 'card_stats', None), 'allow_area_damage_when_invisible', False)))
        if CF['stealth'] and stealthy:
            saved = self._stealth_until
            self._stealth_until = 0
            try:
                return crad(self, source_kind, affects_hidden=affects_hidden, source_entity=source_entity)
            finally:
                self._stealth_until = saved
        result = crad(self, source_kind, affects_hidden=affects_hidden, source_entity=source_entity)
        if stealthy and not result:
            EVENTS.append(dict(kind='stealth_reject', site=frame_site(), target=self.id,
                               tick=getattr(battle, 'tick', None)))
        return result
    E.Entity.can_receive_area_damage = crad_wrapped

    surface = UT.is_above_ground_surface
    def surface_wrapped(entity):
        result = surface(entity)
        if result and getattr(entity, '_mk_leap_phase', None) == 'airborne' and not getattr(entity, 'is_air_unit', False):
            if CF['surface']:
                return False
            EVENTS.append(dict(kind='surface_skip', site=frame_site(), target=entity.id,
                               tick=getattr(getattr(entity, 'battle_state', None), 'tick', None)))
        return result
    for module in (E, SP, MK, UT):
        if getattr(module, 'is_above_ground_surface', None) is surface:
            module.is_above_ground_surface = surface_wrapped

    slow = E.Entity.apply_slow
    def slow_wrapped(self, *args, **kw):
        if getattr(self, '_hidden_building', False):
            EVENTS.append(dict(kind='slow_on_hidden', site=frame_site(), target=self.id,
                               tick=getattr(getattr(self, 'battle_state', None), 'tick', None)))
        return slow(self, *args, **kw)
    E.Entity.apply_slow = slow_wrapped

    stun = E.Entity.apply_stun
    def stun_wrapped(self, *args, **kw):
        if getattr(self, '_hidden_building', False):
            EVENTS.append(dict(kind='stun_on_hidden', site=frame_site(), target=self.id,
                               tick=getattr(getattr(self, 'battle_state', None), 'tick', None)))
        return stun(self, *args, **kw)
    E.Entity.apply_stun = stun_wrapped

    knock = KB.apply_directional_knockback
    def knock_wrapped(target, battle_state, *args, **kw):
        result = knock(target, battle_state, *args, **kw)
        mount = getattr(target, '_rider_mount', None)
        if not result and ((mount is not None and mount.is_alive) or target.spawn_stagger_remaining > 1e-9):
            EVENTS.append(dict(kind='knock_reject', site=frame_site(), target=target.id, tick=battle_state.tick,
                               mounted=mount is not None and mount.is_alive))
        return result
    KB.apply_directional_knockback = knock_wrapped

    resolve = E.Entity._resolve_attack_damage
    def resolve_wrapped(self, primary_target, damage, battle_state, **kw):
        EVENTS.append(dict(kind='direct_hit', tick=battle_state.tick, attacker=self.card_stats.name,
                           target=primary_target.id, dash=kw.get('exclude_hit_mechanic') is not None,
                           hidden=bool(getattr(primary_target, '_hidden_building', False))))
        return resolve(self, primary_target, damage, battle_state, **kw)
    E.Entity._resolve_attack_damage = resolve_wrapped


def observable(b, ids):
    out = []
    for i in ids:
        e = b.entities.get(i)
        out.append(None if e is None else (round(e.hitpoints, 3), e.is_alive, round(e.stun_timer, 3),
                   round(getattr(e, 'slow_multiplier', 1.0), 3), len(getattr(e, '_slow_effects', []) or []),
                   round(e.position.x, 3), round(e.position.y, 3)))
    return out


def py_run(b0, schedule, ticks, ids, flag=None):
    b = b0.clone()
    if flag:
        CF[flag] = True
    mark = len(EVENTS)
    trace = []
    try:
        for t in range(ticks):
            if schedule:
                schedule(t, b, None)
            b.step()
            trace.append(observable(b, ids))
    finally:
        if flag:
            CF[flag] = False
    events = EVENTS[mark:]
    del EVENTS[mark:]
    return trace, events


# ---------------------------------------------------------------- fixtures
def cast_on(card, seat_of, label, at, offset_xy=(0.0, 0.0)):
    """Cast `card` for `seat_of(seat)` at tick offset `at`, on the labelled unit's current point (both engines)."""
    def make(seat, ids):
        def schedule(t, py, native):
            if t != at:
                return
            owner = seat_of(seat)
            target = py.entities.get(ids[label][0])
            if target is None:
                return
            x = target.position.x + (offset_xy[0] if seat == 0 else -offset_xy[0])
            y = target.position.y + (offset_xy[1] if seat == 0 else -offset_xy[1])
            player = py.players[owner]
            player.elixir = 10
            if card not in player.hand:
                player.cycle_queue.appendleft(player.hand[0]); player.hand[0] = card
            assert py.deploy_card(owner, card, Position(x, y)), (card, x, y)
            if native is not None:
                state = json.loads(native.snapshot())
                assert native.apply_action(owner, card, x, y), (card, x, y)
        return schedule
    return make


ME = lambda seat: seat
THEM = lambda seat: 1 - seat


def fixture(units, ticks, places=(), extra=(), cast=None, pre=None, pre_steps=0):
    def make(seat):
        b, cfg, ids = setup(units, seat, extra)
        for label, xy in places:
            b.entities[ids[label][0]].position = point(*xy, seat)
        for _ in range(pre_steps):
            b.step()
        if pre:
            pre(b, ids, seat)
        schedule = cast(seat, ids) if cast else None
        return b, cfg, ids, schedule, ticks
    return make


def search(make_base, k_range, apply, ok):
    """Python-only search over a forced boundary tick k (apply(b, ids, seat) at k); ok(events) accepts."""
    def make(seat):
        b0, cfg, ids, schedule, ticks = make_base(seat)
        for k in k_range:
            b = b0.clone()
            for t in range(k):
                if schedule:
                    schedule(t, b, None)
                b.step()
            if not apply(b, ids, seat):
                continue
            shifted = (lambda t, py, native, s=schedule, k=k: s(t + k, py, native)) if schedule else None
            mark = len(EVENTS)
            probe = b.clone()
            for t in range(ticks):
                if shifted:
                    shifted(t, probe, None)
                probe.step()
            found = ok(EVENTS[mark:], ids)
            del EVENTS[mark:]
            if found:
                ids['_forced'] = dict(k=k)
                return b, cfg, ids, shifted, ticks
        raise AssertionError('no forced boundary produced the witness')
    return make


def kill(label):
    def apply(b, ids, seat):
        e = b.entities.get(ids[label][0])
        if e is None or not e.is_alive or e.deploy_delay_remaining > 0:
            return False
        e.take_damage(e.hitpoints + 1e6)
        return not e.is_alive
    return apply


def hide_tesla(m):
    def apply(b, ids, seat):
        t = b.entities.get(ids['Tesla'][0])
        if t is None or not t.is_alive:
            return False
        tesla_phase(t, m)
        return True
    return apply


def ghost_ids(ids, b):
    return list(ids.get('Ghost', []))


def mk_ids(ids, b):
    return list(ids.get('MegaKnight', []))


def stealth_witness(sites, targets=ghost_ids, flag='stealth', kind='stealth_reject'):
    def check(b0, schedule, ticks, ids):
        tids = targets(ids, b0)
        real, events = py_run(b0, schedule, ticks, tids)
        cf, _ = py_run(b0, schedule, ticks, tids, flag=flag)
        hits = [e for e in events if e['kind'] == kind and e['target'] in tids
                and any(s in (e['site'] or '') for s in sites)]
        differs = real != cf
        first = next((t for t, (x, y) in enumerate(zip(real, cf)) if x != y), None)
        return bool(hits) and differs, dict(rejections=len(hits), sites=sorted({e['site'] for e in hits}),
                                            counterfactual_differs_at=first, forced=ids.get('_forced'))
    return check


def event_witness(kind, label, cond=lambda e: True):
    def check(b0, schedule, ticks, ids):
        tids = list(ids[label])
        _, events = py_run(b0, schedule, ticks, tids)
        hits = [e for e in events if e['kind'] == kind and e['target'] in tids and cond(e)]
        return bool(hits), dict(events=len(hits), sites=sorted({e.get('site') or '' for e in hits}),
                                forced=ids.get('_forced'))
    return check


def ok_stealth(sites, label='Ghost'):
    return lambda events, ids: any(e['kind'] == 'stealth_reject' and e['target'] in ids[label]
                                   and any(s in (e['site'] or '') for s in sites) for e in events)


GHOST_NEAR_KNIGHT = [('them', 'Knight', 9, 18.5), ('them', 'Ghost', 9.8, 18.5)]

ROWS = {
    # ---- invisibility at fresh area queries (can_receive_area_damage)
    'S1_valkyrie_melee_splash': (fixture([('me', 'Valkyrie', 9, 14.5)] + GHOST_NEAR_KNIGHT, 260),
                                 stealth_witness(['_snapshot_attack_area_targets_at'])),
    'S2_wizard_projectile_splash': (fixture([('me', 'Wizard', 9, 12.5)] + GHOST_NEAR_KNIGHT, 260),
                                    stealth_witness(['_collect_splash_targets'])),
    'S3_ice_wizard_splash_status': (fixture([('me', 'IceWizard', 9, 12.5)] + GHOST_NEAR_KNIGHT, 260),
                                    stealth_witness(['_apply_splash_statuses', '_collect_splash_targets'])),
    'S4_hunter_piercing_pellets': (fixture([('me', 'Hunter', 9, 13.5)] + GHOST_NEAR_KNIGHT, 260),
                                   stealth_witness(['_damage_piercing_targets_at'])),
    'S5_fire_spirits_splash': (fixture([('me', 'FireSpirits', 9, 14.5)] + GHOST_NEAR_KNIGHT, 120,
                                       places=[('FireSpirits', (9, 16.8))]),
                               stealth_witness(['_freeze'])),
    'S6_ice_spirit_freeze_splash': (fixture([('me', 'IceSpirit', 9, 14.5)] + GHOST_NEAR_KNIGHT, 120,
                                            places=[('IceSpirit', (9, 16.8))]),
                                    stealth_witness(['_freeze'])),
    'S7_giant_skeleton_bomb': (search(fixture([('me', 'GiantSkeleton', 9, 14.5), ('them', 'Ghost', 9.6, 15.2)], 120,
                                              places=[('GiantSkeleton', (9, 16.6))]),
                                      range(20, 90, 3), kill('GiantSkeleton'), ok_stealth(['_explode'])),
                               stealth_witness(['_explode'])),
    'S8_ice_golem_death_nova': (search(fixture([('me', 'IceGolem', 9, 14.5), ('them', 'Ghost', 9.6, 15.2)], 30,
                                               places=[('IceGolem', (9, 16.6))]),
                                       range(20, 90, 3), kill('IceGolem'), ok_stealth(['on_death'])),
                                stealth_witness(['on_death'])),
    'S9_fireball_direct_spell': (fixture([('them', 'Ghost', 9, 20.5)], 70, extra=('Fireball',),
                                         cast=cast_on('Fireball', ME, 'Ghost', 30)),
                                 stealth_witness(['DirectDamageSpell.cast'])),
    'S10_zap_damage_vs_stun': (fixture([('them', 'Ghost', 9, 20.5)], 50, extra=('Zap',),
                                       cast=cast_on('Zap', ME, 'Ghost', 30)),
                               stealth_witness(['DirectDamageSpell.cast'])),
    'S11_log_rolling': (fixture([('them', 'Ghost', 9, 20.5)], 70, extra=('Log',),
                                cast=cast_on('Log', ME, 'Ghost', 30, (0.0, -2.0))),
                        stealth_witness(['_deal_rolling_damage'])),
    'S12_poison_area_ticks': (fixture([('them', 'Ghost', 9, 20.5)], 120, extra=('Poison',),
                                      cast=cast_on('Poison', ME, 'Ghost', 30)),
                              stealth_witness(['_apply_damage_tick', '_apply_continuous_effects'])),
    'S13_lightning_ranked_strike': (fixture([('them', 'Ghost', 9, 20.5)], 80, extra=('Lightning',),
                                            cast=cast_on('Lightning', ME, 'Ghost', 30)),
                                    stealth_witness(['RankedStrikeArea.update'])),
    'S14_void_scope_tier': (fixture([('them', 'Ghost', 9, 20.5), ('them', 'Knight', 9.8, 20.5)], 120,
                                    extra=('DarkMagic',), cast=cast_on('DarkMagic', ME, 'Ghost', 30)),
                            stealth_witness(['_enemy_characters_in_area'])),
    'S15_mega_knight_slam': (fixture([('me', 'MegaKnight', 9, 14.5)] + GHOST_NEAR_KNIGHT, 260),
                             stealth_witness(['_slam'])),
    'S16_electro_wizard_spawn_zap': (fixture([('them', 'Ghost', 9, 18.5)], 40, extra=('ElectroWizard',),
                                             cast=cast_on('ElectroWizard', ME, 'Ghost', 30, (0.0, -1.2))),
                                     stealth_witness(['_apply_damage_tick', '_apply_continuous_effects'])),
    # ---- ground-surface gate: a Mega Knight mid-leap is above ground-only areas
    'G1_earthquake_vs_mega_knight_leap': (
        fixture([('them', 'MegaKnight', 9, 21.5), ('me', 'Knight', 9, 14.5)], 160, extra=('Earthquake',),
                cast=cast_on('Earthquake', ME, 'MegaKnight', 64)),
        stealth_witness(['_apply_damage_tick', '_apply_continuous_effects'], targets=mk_ids, flag='surface',
                        kind='surface_skip')),
    # ---- status / displacement writers
    'W1_ice_golem_death_slow_hidden_tesla': (
        search(fixture([('me', 'IceGolem', 9, 14.5), ('them', 'Tesla', 9, 19.0)], 30,
                       places=[('IceGolem', (9, 17.2))]),
               range(20, 120, 2), lambda b, ids, seat: hide_tesla(0)(b, ids, seat) and kill('IceGolem')(b, ids, seat),
               lambda events, ids: any(e['kind'] == 'slow_on_hidden' and e['target'] in ids['Tesla'] for e in events)),
        event_witness('slow_on_hidden', 'Tesla')),
    'W2_freeze_hidden_tesla': (
        search(fixture([('them', 'Tesla', 9, 20.5)], 40, extra=('Freeze',),
                       cast=cast_on('Freeze', ME, 'Tesla', 0)),
               range(0, 1), hide_tesla(0),
               lambda events, ids: True),
        event_witness('stun_on_hidden', 'Tesla')),
    'W3_fireball_knockback_mounted_riders': (
        fixture([('them', 'GoblinGiant', 9, 21.5)], 80, extra=('Fireball',),
                cast=cast_on('Fireball', ME, 'GoblinGiant', 40)),
        event_witness('knock_reject', 'GoblinGiant', lambda e: True)),
    # ---- dash blow on a hidden Tesla (review r2 item 4): an actual dash _resolve_attack_damage on it
    'D1_bandit_dash_blow_hidden_tesla': (
        search(fixture([('me', 'Assassin', 9, 13.5), ('them', 'Tesla', 9, 19.5)], 40),
               range(0, 90), hide_tesla(0),
               lambda events, ids: any(e['kind'] == 'direct_hit' and e['dash'] and e['hidden']
                                       and e['target'] in ids['Tesla'] for e in events)),
        event_witness('direct_hit', 'Tesla', lambda e: e['dash'] and e['hidden'])),
    'D2_boss_bandit_dash_blow_hidden_tesla': (
        search(fixture([('me', 'BossBandit', 9, 13.5), ('them', 'Tesla', 9, 19.5)], 40),
               range(0, 90), hide_tesla(0),
               lambda events, ids: any(e['kind'] == 'direct_hit' and e['dash'] and e['hidden']
                                       and e['target'] in ids['Tesla'] for e in events)),
        event_witness('direct_hit', 'Tesla', lambda e: e['dash'] and e['hidden'])),
}


def run(name, seat):
    make, witness = ROWS[name]
    out = dict(row=name, seat=seat, classes={}, digest_first=None, error=None)
    try:
        del EVENTS[:]
        b, cfg, ids, schedule, ticks = make(seat)
        if 'GoblinGiant' in ids:
            # The witness also accepts the mount's riders (they share the card's deploy).
            pass
        b0 = b.clone()
        ok, info = witness(b0, schedule, ticks, ids)
        del EVENTS[:]
        native = clasher_core.BattleState(snapshot(b, cfg))
        seen = set()
        S.compare(b, cfg, native, -1, seen, out['classes'])
        for t in range(ticks):
            if schedule:
                schedule(t, b, native)
            b.step()
            native.step(1)
            if out['digest_first'] is None and native.digest() != battle_digest(b):
                out['digest_first'] = t
            S.compare(b, cfg, native, t, seen, out['classes'])
        out.update(witness=ok, info=info, ticks=ticks)
    except Exception:
        out['error'] = traceback.format_exc(limit=6)[-1500:]
    out['status'] = 'PASS' if (not out['error'] and out.get('witness') and not out['classes']
                               and out['digest_first'] is None) else 'FAIL'
    return out


def main():
    install()
    names = sys.argv[2:] or list(ROWS)
    res = []
    for name in names:
        for seat in (0, 1):
            r = run(name, seat)
            res.append(r)
            print(json.dumps({k: r.get(k) for k in ('row', 'seat', 'status', 'witness', 'digest_first', 'info')}),
                  {k: (v['first'], v['count']) for k, v in r['classes'].items()},
                  (r['error'] or '').strip().splitlines()[-1:], flush=True)
            json.dump(dict(native=clasher_core.__file__, rows=res), open(sys.argv[1], 'w'), indent=1, default=str)
    raise SystemExit(0 if all(r['status'] == 'PASS' for r in res) else 1)


if __name__ == '__main__':
    main()
