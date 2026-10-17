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

    overlaps = E.RollingProjectile._hitbox_overlaps_with_rolling_path
    def overlaps_wrapped(self, entity):
        result = overlaps(self, entity)
        if result:
            self.__dict__.setdefault('_probe_overlaps', set()).add(entity.id)
        return result
    E.RollingProjectile._hitbox_overlaps_with_rolling_path = overlaps_wrapped

    rolling = E.RollingProjectile._deal_rolling_damage
    def rolling_wrapped(self, battle_state):
        self.__dict__['_probe_overlaps'] = set()
        result = rolling(self, battle_state)
        for i in self.__dict__.pop('_probe_overlaps', set()):
            e = battle_state.entities.get(i)
            if e is None or i in self.hit_entities:
                continue
            underground = bool(getattr(e, '_underground_deployment', False))
            staggered_above = e.spawn_stagger_remaining > 1e-9 and UT.is_above_ground_surface(e)
            if underground or staggered_above:
                EVENTS.append(dict(kind='roll_skip', site='RollingProjectile._deal_rolling_damage', target=i,
                                   tick=battle_state.tick, underground=underground, staggered_above=staggered_above))
        return result
    E.RollingProjectile._deal_rolling_damage = rolling_wrapped

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
            # No player-state edits (elixir/hand are in the digest): the card must already be in hand.
            player = py.players[owner]
            assert card in player.hand, (card, player.hand, player.elixir)
            assert py.deploy_card(owner, card, Position(x, y)), (card, x, y, player.elixir)
            if native is not None:
                state = json.loads(native.snapshot())
                assert native.apply_action(owner, card, x, y), (card, x, y)
        return schedule
    return make


ME = lambda seat: seat
THEM = lambda seat: 1 - seat


def no_area_opt_in(b, ids, seat):
    """The predicate's own case: an invisible unit WITHOUT allowAreaDmgWhenInvisible. Ghost and Archer Queen
    (the only stealth sources in the data) both opt in, so the flag is cleared on this Ghost's stats; the
    export carries it to native (stats.area_while_invisible = false)."""
    for i in ids.get('Ghost', []):
        g = b.entities[i]
        g.card_stats.allow_area_damage_when_invisible = False


def fixture(units, ticks, places=(), extra=(), cast=None, pre=None, pre_steps=0, ghost=True):
    def make(seat):
        b, cfg, ids = setup(units, seat, extra)
        if ghost and 'Ghost' in ids:
            no_area_opt_in(b, ids, seat)
        for label, xy in places:
            b.entities[ids[label][0]].position = point(*xy, seat)
        for _ in range(pre_steps):
            b.step()
        if pre:
            pre(b, ids, seat)
        schedule = cast(seat, ids) if cast else None
        return b, cfg, ids, schedule, ticks
    return make


def search(make_base, k_range, apply, ok, post=None):
    """Python-only search over a forced boundary tick k (apply(b, ids, seat) at k); ok(events) accepts.
    `post(seat, ids)` is a schedule relative to the boundary (offset 0 = first lockstep tick)."""
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
            if post:
                shifted = post(seat, ids)
            else:
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


def place_near(label, anchor, dx, dy):
    """Explicit placement at a boundary: `label` next to `anchor` (seat-mirrored offset)."""
    def apply(b, ids, seat):
        a = b.entities.get(ids[anchor][0]); g = b.entities.get(ids[label][0])
        if a is None or g is None or not a.is_alive or not g.is_alive or a.deploy_delay_remaining > 0:
            return False
        sx = 1 if seat == 0 else -1
        g.position = Position(a.position.x + sx * dx, a.position.y + sx * dy)
        return True
    return apply


def kill_by_zap(label):
    """1 hp, then an enemy Zap inside the next tick (the death payload resolves in-tick in both engines)."""
    def make(seat, ids):
        return cast_on('Zap', THEM, label, 0)(seat, ids)
    return make


def place_beside_deploying(label, anchor, dx, dy):
    """Explicit placement while the anchor is still deploying (the Ghost has not attacked, so it is invisible)."""
    def apply(b, ids, seat):
        a = b.entities.get(ids[anchor][0]); g = b.entities.get(ids[label][0])
        if a is None or g is None or a.deploy_delay_remaining <= 0.05:
            return False
        sx = 1 if seat == 0 else -1
        g.position = Position(a.position.x + sx * dx, a.position.y + sx * dy)
        return True
    return apply


def bomb_about_to_explode(b, ids, seat):
    """Balloon killed by an enemy Zap (Python pre-phase); step until its death bomb is about to explode, then
    the invisible Ghost under it. The explosion happens in lockstep."""
    from clasher.entities import TimedExplosive
    bl = b.entities.get(ids['Balloon'][0])
    if bl is None or not bl.is_alive or bl.deploy_delay_remaining > 0:
        return False
    bl.hitpoints = 1
    if 'Zap' not in b.players[1 - seat].hand or not b.deploy_card(1 - seat, 'Zap', Position(bl.position.x, bl.position.y)):
        return False
    bomb = None
    for _ in range(200):
        b.step()
        bombs = [e for e in b.entities.values() if isinstance(e, TimedExplosive) and e.player_id == seat and e.is_alive]
        if bombs:
            bomb = bombs[0]
            probe = b.clone()
            alive = True
            for _ in range(3):
                probe.step()
                if not probe.entities.get(bomb.id) or not probe.entities[bomb.id].is_alive:
                    alive = False
                    break
            if not alive:
                break
    if bomb is None or not bomb.is_alive:
        return False
    g = b.entities.get(ids['Ghost'][0])
    if g is None or not g.is_alive or g._stealth_until <= 0:
        return False
    g.position = Position(bomb.position.x, bomb.position.y)
    return True


def low_hp(label):
    """A reachable state: the unit at 1 hp (it then dies inside a tick, to a real hit)."""
    def apply(b, ids, seat):
        e = b.entities.get(ids[label][0])
        if e is None or not e.is_alive or e.deploy_delay_remaining > 0:
            return False
        e.hitpoints = 1
        return True
    return apply


def zap_golem_at(at):
    return cast_on('Zap', THEM, 'IceGolem', at)


def golem_dead_tesla_hidden(b, ids, seat):
    """Golem at 1 hp killed by an enemy Zap inside a tick (Python only, before the boundary); then the Tesla
    at its hidden boundary while the death freeze area awaits its first update. The native arm starts here."""
    g = b.entities.get(ids['IceGolem'][0]); t = b.entities.get(ids['Tesla'][0])
    if g is None or t is None or not g.is_alive or g.deploy_delay_remaining > 0:
        return False
    g.hitpoints = 1
    owner = 1 - seat
    if 'Zap' not in b.players[owner].hand or not b.deploy_card(owner, 'Zap', Position(g.position.x, g.position.y)):
        return False
    for _ in range(3):
        b.step()
        if not g.is_alive:
            break
    if g.is_alive:
        return False
    tesla_phase(t, 0)
    return True


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
        seen = sorted({e['site'] for e in events if e['kind'] == kind and e['target'] in tids})
        return bool(hits) and differs, dict(rejections=len(hits), sites=sorted({e['site'] for e in hits}),
                                            all_sites=seen, counterfactual_differs_at=first,
                                            forced=ids.get('_forced'))
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


def stagger_fixture(seat):
    """An enemy Skeleton Army dropped on a deploying Mega Knight so its landing pushback meets members still
    in their spawn stagger (Python can_receive_effect false; no knockback). Searched over the drop tick."""
    for at in range(4, 20):
        b, cfg, ids = setup([('me', 'MegaKnight', 9, 12.5), ('them', 'Knight', 9, 28.5)], seat, ('SkeletonArmy',))
        mk = b.entities[ids['MegaKnight'][0]]
        owner = 1 - seat
        trial = b.clone()
        for _ in range(at):
            trial.step()
        before = set(trial.entities)
        if 'SkeletonArmy' not in trial.players[owner].hand:
            continue
        if not trial.deploy_card(owner, 'SkeletonArmy', Position(mk.position.x, mk.position.y + (1.2 if seat == 0 else -1.2))):
            continue
        mark = len(EVENTS)
        probe = trial.clone()
        for _ in range(40):
            probe.step()
        new_ids = sorted(set(trial.entities) - before)
        found = any(e['kind'] == 'knock_reject' and e['target'] in new_ids for e in EVENTS[mark:])
        del EVENTS[mark:]
        if found:
            ids['SkeletonArmyCast'] = new_ids
            ids['_forced'] = dict(drop_tick=at)
            return trial, cfg, ids, None, 40
    raise AssertionError('no drop tick met the landing pushback inside the spawn stagger')


def log_fixture(unit, unit_xy, cond, places=()):
    """A Log rolled over `unit` (the enemy's), searched over the cast tick and cast point, until Python's rolling
    query overlaps it in the state `cond` (underground / spawn-staggered above-surface) and leaves it unmarked."""
    def make(seat):
        for at in range(1, 60):
            for back in (2.0, 4.0, 6.0):
                b, cfg, ids = setup([('them', unit, *unit_xy)], seat, ('Log',))
                for label, xy in places:
                    b.entities[ids[label][0]].position = point(*xy, seat)
                schedule = cast_on('Log', ME, unit, at, (0.0, -back))(seat, ids)
                trial = b.clone()
                mark = len(EVENTS)
                try:
                    for t in range(at + 40):
                        schedule(t, trial, None)
                        trial.step()
                except AssertionError:
                    del EVENTS[mark:]
                    continue
                found = any(e['kind'] == 'roll_skip' and e['target'] in ids[unit] and e[cond] for e in EVENTS[mark:])
                del EVENTS[mark:]
                if found:
                    ids['_forced'] = dict(cast_tick=at, back=back)
                    return b, cfg, ids, schedule, at + 40
        raise AssertionError('no Log cast met the case')
    return make


def staggered_minions_fixture(seat):
    """A Log rolling through the enemy's freshly deployed Minions while members are still in their spawn stagger
    (air: Python neither hits nor marks them). Searched over the Minions' deploy tick; both casts in lockstep."""
    for d in range(0, 40):
        b, cfg, ids = setup([('them', 'Knight', 15.5, 28.5)], seat, ('Log', 'Minions'))
        owner = 1 - seat
        log_at, log_xy, minion_xy = 5, point(9, 14.0, seat), point(9, 18.0, seat)
        def schedule(t, py, native, d=d):
            for when, who, card, xy in ((log_at, seat, 'Log', log_xy), (log_at + d, owner, 'Minions', minion_xy)):
                if t == when:
                    assert card in py.players[who].hand, (card, py.players[who].hand)
                    before = set(py.entities)
                    assert py.deploy_card(who, card, xy), (card, xy)
                    if card == 'Minions':
                        ids['MinionsCast'] = sorted(set(py.entities) - before)
                    if native is not None:
                        assert native.apply_action(who, card, xy.x, xy.y), (card, xy)
        trial = b.clone()
        mark = len(EVENTS)
        try:
            for t in range(log_at + 60):
                schedule(t, trial, None)
                trial.step()
        except AssertionError:
            del EVENTS[mark:]
            continue
        found = any(e['kind'] == 'roll_skip' and e['target'] in ids.get('MinionsCast', []) and e['staggered_above']
                    for e in EVENTS[mark:])
        del EVENTS[mark:]
        if found:
            ids['_forced'] = dict(minion_delay=d)
            return b, cfg, ids, schedule, log_at + 60
    raise AssertionError('no Minions deploy tick met the rolling Log inside the spawn stagger')


GHOST_NEAR_KNIGHT = [('them', 'Knight', 9, 18.5), ('them', 'Ghost', 9.8, 18.5)]

ROWS = {
    # ---- invisibility at fresh area queries (can_receive_area_damage)
    'S1_valkyrie_melee_splash': (search(fixture([('me', 'Valkyrie', 9, 14.5), ('them', 'Knight', 9, 18.5),
                                                 ('them', 'Ghost', 15.5, 28.5)], 40),
                                         range(30, 160, 3), place_near('Ghost', 'Valkyrie', 0.0, 1.6),
                                         ok_stealth(['_snapshot_attack_area_targets_at'])),
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
    'S7_balloon_death_bomb': (search(fixture([('me', 'Balloon', 9, 14.5), ('them', 'Ghost', 9.0, 18.5)], 20,
                                             places=[('Ghost', (9.0, 17.2))], extra=('Zap',)),
                                     range(24, 60, 6), bomb_about_to_explode, ok_stealth(['_explode'])),
                              stealth_witness(['_explode'])),
    'S8_ice_golem_death_nova': (search(fixture([('me', 'IceGolem', 9, 14.5), ('them', 'Ghost', 9.6, 18.5)], 30,
                                               places=[('IceGolem', (9, 16.6)), ('Ghost', (9.6, 17.3))],
                                               extra=('Zap',)),
                                       range(20, 90, 1), low_hp('IceGolem'), ok_stealth(['on_death']),
                                       post=kill_by_zap('IceGolem')),
                                stealth_witness(['on_death'])),
    'S9_fireball_projectile_spell': (fixture([('them', 'Ghost', 9, 20.5)], 70, extra=('Fireball',),
                                             cast=cast_on('Fireball', ME, 'Ghost', 30)),
                                     stealth_witness(['_collect_splash_targets'])),
    'S10_zap_damage_vs_stun': (fixture([('them', 'Ghost', 9, 20.5)], 50, extra=('Zap',),
                                       cast=cast_on('Zap', ME, 'Ghost', 30)),
                               stealth_witness(['DirectDamageSpell.cast'])),
    'S11_log_rolling': (fixture([('them', 'Ghost', 9, 18.5)], 70, extra=('Log',), places=[('Ghost', (9, 12.5))],
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
    'S15_mega_knight_slam': (search(fixture([('me', 'MegaKnight', 9, 14.5), ('them', 'Ghost', 15.5, 28.5)], 30),
                                     range(2, 19), place_beside_deploying('Ghost', 'MegaKnight', 1.0, 0.8),
                                     ok_stealth(['_slam'])),
                              stealth_witness(['_slam'])),
    'S16_electro_wizard_spawn_zap': (fixture([('them', 'Ghost', 9, 18.5)], 40, extra=('ElectroWizard',),
                                             places=[('Ghost', (9, 11.5))],
                                             cast=cast_on('ElectroWizard', ME, 'Ghost', 30, (0.0, 1.0))),
                                     stealth_witness(['_apply_damage_tick', '_apply_continuous_effects'])),
    # ---- rolling spell (C56 Log): an underground Miner and a spawn-staggered flier are skipped, unmarked
    'L1_log_over_underground_miner': (log_fixture('Miner', (9, 11.5), 'underground'),
                                      event_witness('roll_skip', 'Miner', lambda e: e['underground'])),
    'L2_log_over_staggered_minions': (staggered_minions_fixture,
                                      event_witness('roll_skip', 'MinionsCast', lambda e: e['staggered_above'])),
    # ---- ground-surface gate: a Mega Knight mid-leap is above ground-only areas
    'G1_earthquake_vs_mega_knight_leap': (
        fixture([('them', 'MegaKnight', 9, 21.5), ('me', 'Knight', 9, 14.5)], 160, extra=('Earthquake',),
                cast=cast_on('Earthquake', ME, 'MegaKnight', 64)),
        stealth_witness(['_apply_damage_tick', '_apply_continuous_effects'], targets=mk_ids, flag='surface',
                        kind='surface_skip')),
    # ---- status / displacement writers
    'W1_ice_golem_death_slow_hidden_tesla': (
        search(fixture([('me', 'IceGolem', 9, 14.5), ('them', 'Tesla', 9, 19.0)], 30, extra=('Zap',),
                       places=[('IceGolem', (9, 17.2))]),
               range(20, 120, 2), golem_dead_tesla_hidden,
               lambda events, ids: any(e['kind'] == 'slow_on_hidden' and e['target'] in ids['Tesla'] for e in events)),
        event_witness('slow_on_hidden', 'Tesla')),
    'W2_freeze_hidden_tesla': (
        search(fixture([('them', 'Tesla', 9, 20.5)], 40, extra=('Freeze',),
                       cast=cast_on('Freeze', ME, 'Tesla', 0)),
               range(0, 1), hide_tesla(0),
               lambda events, ids: True),
        event_witness('stun_on_hidden', 'Tesla')),
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
