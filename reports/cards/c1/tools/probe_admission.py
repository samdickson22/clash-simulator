"""Batch C1 class audits: attacker eligibility (class A) and effect admission at delayed impact (class B).

Every row runs in both seats and compares Python and native every tick: the semantic full snapshot
(probe_snapshots.compare, no extra exclusions) and battle_digest. A row PASSES only if its witness occurred
(the exact event the row is about), so an equal run that never reached the case fails.

Class B rows need a target that becomes unable to receive effects after it was chosen. Those are explicit
continuations from a reachable forced state, chosen by a Python-only search, never a mid-tick edit:
  - Tesla: its HideWhenIdle phase set to `hide_delay - 50*m` at tick k (m ticks from the hidden boundary,
    target cleared when m == 0, exactly as HideWhenIdle.on_object_tick leaves it).
  - Bandit: dash travel launched toward a seen target (BanditDash._launch_dash, as probe_shared_troop).
The native arm starts from Python's export at that boundary. Witnesses are read-only method wrappers.

Usage (PYTHONPATH as probe_snapshots.py): probe_admission.py OUT.json [ROW ...]
"""
import json
import sys
import traceback

import differential as D
from differential import Position, battle_digest, clasher_core, config, snapshot
import probe_snapshots as S

FILL = ('Knight', 'Giant', 'Archers', 'Musketeer')
EVENTS = []


def point(x, y, seat):
    return Position(x if seat == 0 else 18 - x, y if seat == 0 else 32 - y)


def setup(units, seat, extra=()):
    """units: (owner 'me'|'them', card, x, y) in seat-0 coordinates; returns battle, cfg, {label: [ids]}."""
    names = [n for _, n, _, _ in units] + list(extra)
    cards = tuple(dict.fromkeys(names + list(FILL)))[:8]
    b = D.initial(7, cards=cards)
    owner = {'me': seat, 'them': 1 - seat}
    for p_index, player in enumerate(b.players):
        mine = list(dict.fromkeys([n for o, n, _, _ in units if owner[o] == p_index] + list(extra)))
        player.elixir = 10
        player.hand = (mine + [n for n in cards if n not in mine])[:4]
        player.cycle_queue.clear()
        player.cycle_queue.extend(n for n in cards if n not in player.hand)
    ids = {}
    for o, name, x, y in units:
        before = set(b.entities)
        b.players[owner[o]].elixir = 10
        if name not in b.players[owner[o]].hand:
            hand = b.players[owner[o]].hand
            b.players[owner[o]].cycle_queue.appendleft(hand[0]); hand[0] = name
        assert b.deploy_card(owner[o], name, point(x, y, seat)), (name, x, y)
        ids.setdefault(name, []).extend(sorted(set(b.entities) - before))
    return b, config(cards), ids


def ent(b, name, ids):
    return b.entities.get(ids[name][0])


# ---------------------------------------------------------------- read-only witness wrappers
def install_wrappers():
    from clasher import entities as E
    from clasher.cards.ronin import RoninCounter
    from clasher.cards.bandit import BanditDash
    from clasher.cards.electro_spirit import ElectroSpiritChain

    def battle_tick(obj):
        battle = getattr(obj, 'battle_state', None)
        return getattr(battle, 'tick', None)

    take = E.Entity.take_damage
    def take_wrapped(self, amount, **kw):
        if getattr(self, '_hidden_building', False) or kw.get('source_kind') == 'DarkMagic':
            EVENTS.append(dict(kind='take_damage', tick=battle_tick(self), target=self.id,
                               source=kw.get('source_kind'), **admission(self)))
        return take(self, amount, **kw)
    E.Entity.take_damage = take_wrapped

    resolve = E.Entity._resolve_attack_damage
    def resolve_wrapped(self, primary_target, damage, battle_state, **kw):
        EVENTS.append(dict(kind='direct_hit', tick=battle_state.tick, attacker=self.card_stats.name,
                           attacker_kind=self.entity_kind, target=primary_target.id,
                           target_name=getattr(primary_target.card_stats, 'name', None),
                           dash=kw.get('exclude_hit_mechanic') is not None, damage=float(damage),
                           hidden=bool(getattr(primary_target, '_hidden_building', False))))
        return resolve(self, primary_target, damage, battle_state, **kw)
    E.Entity._resolve_attack_damage = resolve_wrapped

    counter = RoninCounter.try_counter
    def counter_wrapped(self, ronin, attacker, amount, battle):
        result = counter(self, ronin, attacker, amount, battle)
        EVENTS.append(dict(kind='counter', tick=battle.tick, attacker=attacker.card_stats.name, result=result))
        return result
    RoninCounter.try_counter = counter_wrapped

    waited = E.ChainLightning._update_waited
    def waited_wrapped(self, battle_state):
        before, tid = self.remaining_bounces, self.current_target_id
        state = admission(battle_state.entities.get(tid))
        result = waited(self, battle_state)
        if self.remaining_bounces < before:
            EVENTS.append(dict(kind='chain_land', tick=battle_state.tick, target=tid, **state))
        return result
    E.ChainLightning._update_waited = waited_wrapped

    dash = BanditDash._update_dash
    def dash_wrapped(self, entity, battle):
        tid = entity._bandit_seen_target
        state = admission(battle.entities.get(tid))
        result = dash(self, entity, battle)
        if entity._bandit_state != 'travel':
            EVENTS.append(dict(kind='dash_end', tick=battle.tick, target=tid, **state))
        return result
    BanditDash._update_dash = dash_wrapped

    spirit = ElectroSpiritChain.on_movement_tick
    def spirit_wrapped(self, entity, dt_ms):
        active = getattr(entity, '_special_move_active', False)
        battle = getattr(entity, 'battle_state', None)
        target = battle.entities.get(getattr(entity, '_electro_spirit_jump_target_id', None)) if battle else None
        state = admission(target)
        result = spirit(self, entity, dt_ms)
        if active and not getattr(entity, '_special_move_active', False):
            EVENTS.append(dict(kind='spirit_land', tick=battle_tick(entity),
                               target=None if target is None else target.id, **state))
        return result
    ElectroSpiritChain.on_movement_tick = spirit_wrapped

    update = E.ChainLightning.update
    def chain_update_wrapped(self, dt, battle_state):
        waited = getattr(self, 'hop_wait_ticks', 0)
        tid = self.current_target_id
        state = admission(battle_state.entities.get(tid)) if tid is not None else None
        alive = self.is_alive
        result = update(self, dt, battle_state)
        if not waited and alive and not self.is_alive and state is not None:
            EVENTS.append(dict(kind='chain_cut', tick=battle_state.tick, target=tid, **state))
        return result
    E.ChainLightning.update = chain_update_wrapped

    deliver = RoninCounter.deliver
    def deliver_wrapped(ronin, battle):
        for due, attacker_id, amount in list(getattr(ronin, '_ronin_pending', [])):
            if due <= battle.tick:
                EVENTS.append(dict(kind='reflect', tick=battle.tick, target=attacker_id,
                                   **admission(battle.entities.get(attacker_id))))
        return deliver(ronin, battle)
    RoninCounter.deliver = staticmethod(deliver_wrapped)

    impact = E.Projectile._resolve_impact
    def impact_wrapped(self, *args, **kw):
        target = self.primary_target
        state = admission(target)
        EVENTS.append(dict(kind='projectile_impact', tick=battle_tick(self),
                           target=None if target is None else target.id, **state))
        return impact(self, *args, **kw)
    E.Projectile._resolve_impact = impact_wrapped


def admission(target):
    if target is None:
        return dict(alive=False, hidden=False, receives=False, travel=False)
    return dict(alive=bool(target.is_alive), hidden=bool(getattr(target, '_hidden_building', False)),
                receives=bool(target.can_receive_effect(getattr(target.card_stats, 'name', None))),
                travel=getattr(target, '_bandit_state', None) == 'travel', hp=float(target.hitpoints))


# ---------------------------------------------------------------- forced reachable states
def tesla_phase(tesla, m):
    """HideWhenIdle state m ticks before the hidden boundary (m == 0: at it, as on_object_tick leaves it)."""
    mech = next(x for x in tesla.mechanics if type(x).__name__ == 'HideWhenIdle')
    mech._phase_ms = float(mech.hide_delay_ms - 50 * m)
    hidden = m == 0
    tesla._hidden_building = hidden
    tesla._special_move_active = hidden
    if hidden:
        tesla.target_id = None


def launch_dash(bandit, target):
    mech = next(x for x in bandit.mechanics if type(x).__name__ == 'BanditDash')
    bandit._bandit_seen_target = target.id
    mech._launch_dash(bandit, target)


# ---------------------------------------------------------------- rows
def row_a(attacker, attacker_xy, ronin_xy=(9, 12.5), ticks=320, extra=(), ronin_place=None):
    def fixture(seat):
        b, cfg, ids = setup([('me', 'Ronin', *ronin_xy), ('them', attacker, *attacker_xy)], seat, extra)
        if ronin_place is not None:
            # Explicit placement during deployment (a point the Ronin can walk to), so contact happens.
            b.entities[ids['Ronin'][0]].position = point(*ronin_place, seat)
        return b, cfg, ids, None, ticks
    return fixture


def a_witness(attacker, expect_counter, dash=False):
    def check(events, ids, b):
        ronin = set(ids['Ronin'])
        hits = [e for e in events if e['kind'] == 'direct_hit' and e['target'] in ronin
                and e['attacker'].startswith(attacker) and e['dash'] == dash]
        counters = [e for e in events if e['kind'] == 'counter' and e['attacker'].startswith(attacker) and e['result']]
        if expect_counter:
            return bool(counters), dict(direct_hits=len(hits), counters=len(counters))
        if dash:
            # Only the dash blow itself is exempt; the Bandit's ordinary hits remain counterable.
            blow_ticks = {e['tick'] for e in hits}
            at_blow = [e for e in counters if e['tick'] in blow_ticks]
            return bool(hits) and not at_blow, dict(dash_blows=len(hits), counters_at_blow=len(at_blow),
                                                   counters_total=len(counters))
        return bool(hits) and not counters, dict(direct_hits=len(hits), counters=len(counters))
    return check


def projectile_ronin_witness(attacker):
    def check(events, ids, b):
        counters = [e for e in events if e['kind'] == 'counter' and e['attacker'] == attacker and e['result']]
        ronin = set(ids['Ronin'])
        impacts = [e for e in events if e['kind'] == 'projectile_impact' and e['target'] in ronin]
        return bool(impacts) and not counters, dict(impacts=len(impacts), counters=len(counters))
    return check


def place(label, xy):
    """Explicit placement during deployment (a point the unit can walk to)."""
    def pre(b, ids, seat):
        b.entities[ids[label][0]].position = point(*xy, seat)
    return pre


def cast_now(b, seat, card, xy):
    b.players[seat].elixir = 10
    hand = b.players[seat].hand
    if card not in hand:
        b.players[seat].cycle_queue.appendleft(hand[0]); hand[0] = card
    assert b.deploy_card(seat, card, point(*xy, seat)), (card, xy)


def advance(base, k, seat, lead_cast):
    """Clone and step k ticks; `lead_cast` = (card, xy, lead) casts `lead` ticks before the boundary."""
    b = base.clone()
    for t in range(k):
        if lead_cast and t == k - lead_cast[2]:
            cast_now(b, seat, lead_cast[0], lead_cast[1])
        b.step()
    return b


def search_tesla(units, kind, ticks, k_range, m_range, extra=(), pre=None, cast=None, lead_cast=None):
    """Python-only search for (k, m): Tesla forced m ticks before hiding at tick k; the delayed effect
    of `kind` must later land on that Tesla while it is hidden."""
    def fixture(seat):
        base, cfg, ids = setup(units, seat, extra)
        if pre:
            pre(base, ids, seat)
        tesla_id = ids['Tesla'][0]
        for k in k_range:
            for m in m_range:
                b = advance(base, k, seat, lead_cast)
                tesla = b.entities.get(tesla_id)
                if tesla is None or not tesla.is_alive:
                    continue
                tesla_phase(tesla, m)
                if cast:
                    b.players[seat].elixir = 10
                mark = len(EVENTS)
                if cast:
                    cast_now(b, seat, *cast)
                for _ in range(ticks):
                    b.step()
                found = [e for e in EVENTS[mark:] if e['kind'] == kind and e['target'] == tesla_id and e['hidden']
                         and e['alive']]
                del EVENTS[mark:]
                if found:
                    b = advance(base, k, seat, lead_cast)
                    tesla_phase(b.entities[tesla_id], m)
                    ids['_forced'] = dict(k=k, m=m)
                    schedule = None
                    if cast:
                        b.players[seat].elixir = 10
                        def schedule(offset, py, native, seat=seat):
                            if offset == 0:
                                hand = py.players[seat].hand
                                if cast[0] not in hand:
                                    py.players[seat].cycle_queue.appendleft(hand[0]); hand[0] = cast[0]
                                pos = point(*cast[1], seat)
                                assert py.deploy_card(seat, cast[0], pos)
                                assert native.apply_action(seat, cast[0], pos.x, pos.y)
                    return b, cfg, ids, schedule, ticks
        raise AssertionError('no reachable forced state produced the witness')
    return fixture


def dash_blow_witness(events, ids, b):
    """Review r2: the dash END alone is not a blow. Require an actual dash _resolve_attack_damage on the hidden
    Tesla (exclude_hit_mechanic set) at the tick that travel ended on it."""
    tesla = ids['Tesla'][0]
    ends = {e['tick'] for e in events if e['kind'] == 'dash_end' and e['target'] == tesla and e['hidden'] and e['alive']}
    blows = [e for e in events if e['kind'] == 'direct_hit' and e['dash'] and e['target'] == tesla and e['hidden']
             and e['tick'] in ends]
    return bool(blows), dict(dash_blows_on_hidden=len(blows), forced=ids.get('_forced'))


def tesla_witness(kind):
    def check(events, ids, b):
        tesla = ids['Tesla'][0]
        found = [e for e in events if e['kind'] == kind and e['target'] == tesla and e['hidden'] and e['alive']]
        return bool(found), dict(landings_on_hidden=len(found), forced=ids.get('_forced'),
                                 hp=[e.get('hp') for e in found][:3])
    return check


def chain_travel_fixture(seat):
    """A waited Electro Dragon hop whose chosen Bandit enters dash travel during the wait."""
    from clasher.entities import ChainLightning
    for bandit_xy in ((11.5, 22.5), (10.5, 22.5), (7.5, 22.5), (12.5, 21.5)):
        units = [('me', 'ElectroDragon', 9, 14.5), ('them', 'Cannon', 9, 20.5), ('them', 'Assassin', *bandit_xy),
                 ('me', 'Knight', 11, 14.5)]
        base, cfg, ids = setup(units, seat)
        place('ElectroDragon', (9, 17.2))(base, ids, seat)
        bandit_id, knight_id = ids['Assassin'][0], ids['Knight'][0]
        for k in range(0, 320):
            b = base.clone()
            for _ in range(k):
                b.step()
            bandit, knight = b.entities.get(bandit_id), b.entities.get(knight_id)
            chains = [e for e in b.entities.values() if isinstance(e, ChainLightning)
                      and getattr(e, 'current_target_id', None) == bandit_id and getattr(e, 'wait_remaining', 0) > 0]
            if not chains or bandit is None or knight is None or not bandit.is_alive or not knight.is_alive:
                continue
            if bandit._bandit_state != 'idle':
                continue
            launch_dash(bandit, knight)
            mark = len(EVENTS)
            probe = b.clone()
            for _ in range(8):
                probe.step()
            found = [e for e in EVENTS[mark:] if e['kind'] == 'chain_land' and e['target'] == bandit_id
                     and e['travel']]
            del EVENTS[mark:]
            if found:
                ids['_forced'] = dict(k=k, bandit_xy=bandit_xy)
                return b, cfg, ids, None, 40
    raise AssertionError('no waited hop onto a Bandit found')


def chain_travel_witness(events, ids, b):
    bandit = ids['Assassin'][0]
    found = [e for e in events if e['kind'] == 'chain_land' and e['target'] == bandit and e['travel']]
    return bool(found), dict(landings_on_travel=len(found), forced=ids.get('_forced'))


def reflect_travel_fixture(seat):
    """A Ronin reflect falling due while its attacker (a Bandit) is in dash travel."""
    base, cfg, ids = setup([('me', 'Ronin', 9, 12.5), ('them', 'Assassin', 9, 17.5), ('them', 'Knight', 12, 18.5)],
                           seat)
    ronin_id, bandit_id = ids['Ronin'][0], ids['Assassin'][0]
    for k in range(0, 240):
        b = base.clone()
        for _ in range(k):
            b.step()
        ronin, bandit = b.entities.get(ronin_id), b.entities.get(bandit_id)
        if ronin is None or bandit is None or not ronin.is_alive or not bandit.is_alive:
            continue
        due = [p for p in getattr(ronin, '_ronin_pending', []) if p[1] == bandit_id]
        if not due or bandit._bandit_state != 'idle':
            continue
        launch_dash(bandit, ronin)
        mark = len(EVENTS)
        probe = b.clone()
        for _ in range(10):
            probe.step()
        found = [e for e in EVENTS[mark:] if e['kind'] == 'reflect' and e['target'] == bandit_id and e['travel']]
        del EVENTS[mark:]
        if found:
            ids['_forced'] = dict(k=k)
            return b, cfg, ids, None, 40
    raise AssertionError('no reflect falling due during dash travel')


def reflect_travel_witness(events, ids, b):
    bandit = ids['Assassin'][0]
    found = [e for e in events if e['kind'] == 'reflect' and e['target'] == bandit and e['travel']]
    return bool(found), dict(reflects_in_travel=len(found), forced=ids.get('_forced'))


def chain_cut_witness(events, ids, b):
    tesla = ids['Tesla'][0]
    found = [e for e in events if e['kind'] == 'chain_cut' and e['target'] == tesla and e['hidden']]
    return bool(found), dict(cuts_on_hidden=len(found), forced=ids.get('_forced'))


def void_witness(events, ids, b):
    tesla = ids['Tesla'][0]
    found = [e for e in events if e['kind'] == 'take_damage' and e['target'] == tesla and e['hidden']
             and e['source'] == 'DarkMagic']
    return bool(found), dict(void_hits_on_hidden=len(found), forced=ids.get('_forced'))


ROWS = {
    # Class A: who may be countered (entities.py _resolve_attack_damage `counterable`).
    # The Ronin is placed at the river edge next to the trio so the bayonet (melee selector) engages it.
    'A1_three_musketeers_bayonet': (row_a('ThreeMusketeers', (9, 18.5), ronin_xy=(9, 14.5), ticks=300,
                                          ronin_place=(9, 16.8)),
                                    a_witness('ThreeMusketeer', False)),
    'A2_knight_melee_countered': (row_a('Knight', (9, 18.5)), a_witness('Knight', True)),
    'A3_bats_air_melee': (row_a('Bats', (9, 18.5)), a_witness('Bats', False)),
    'A4_inferno_tower_building': (row_a('InfernoTower', (9, 18.5)), a_witness('InfernoTower', False)),
    'A5_musketeer_projectile': (row_a('Musketeer', (9, 18.5)), projectile_ronin_witness('Musketeer')),
    'A6_bandit_dash_blow': (row_a('Assassin', (9, 17.5), ronin_xy=(9, 12.5)), a_witness('Assassin', False, dash=True)),
    # Class B: admission re-checked at a delayed impact on a target chosen earlier.
    'B1_dragon_waited_hop_hidden_tesla': (
        search_tesla([('me', 'ElectroDragon', 9, 14.5), ('them', 'Cannon', 9, 20.5), ('them', 'Tesla', 9, 24.0)],
                     'chain_land', 60, range(0, 120, 2), range(0, 6)), tesla_witness('chain_land')),
    'B2_electro_spirit_landing_hidden_tesla': (
        search_tesla([('me', 'ElectroSpirit', 9, 14.5), ('them', 'Tesla', 9, 20.5)],
                     'spirit_land', 40, range(0, 80), range(0, 8), pre=place('ElectroSpirit', (9, 17.0))),
        tesla_witness('spirit_land')),
    'B3_bandit_dash_blow_hidden_tesla': (
        search_tesla([('me', 'Assassin', 9, 13.5), ('them', 'Tesla', 9, 19.5)],
                     'dash_end', 40, range(0, 80), range(0, 8)), dash_blow_witness),
    'B3b_boss_bandit_dash_blow_hidden_tesla': (
        search_tesla([('me', 'BossBandit', 9, 13.5), ('them', 'Tesla', 9, 19.5)],
                     'dash_end', 40, range(0, 80), range(0, 8)), dash_blow_witness),
    'B4_projectile_impact_hidden_tesla': (
        search_tesla([('me', 'Musketeer', 9, 13.0), ('them', 'Tesla', 9, 19.0)],
                     'projectile_impact', 40, range(0, 80), range(0, 8)), tesla_witness('projectile_impact')),
    'B5_dragon_waited_hop_dash_travel': (chain_travel_fixture, chain_travel_witness),
    # Void pulses 1.5 s after the cast and lands its hits 0.1 s later: cast 28 ticks before the boundary.
    'B6_void_delayed_hit_hidden_tesla': (
        search_tesla([('them', 'Tesla', 9, 20.5)], 'take_damage', 40, range(28, 90, 2), range(0, 8),
                     extra=('DarkMagic', 'Knight'), lead_cast=('DarkMagic', (9, 20.5), 28)), void_witness),
    'B7_chain_hop_target_hides': (
        search_tesla([('me', 'ElectroSpirit', 9, 14.5), ('them', 'Knight', 9, 19.5), ('them', 'Tesla', 10.5, 22.0)],
                     'chain_cut', 40, range(0, 80), range(0, 8), pre=place('ElectroSpirit', (9, 17.0))),
        chain_cut_witness),
    'B8_ronin_reflect_dash_travel': (reflect_travel_fixture, reflect_travel_witness),
}


def run(name, seat):
    fixture, witness = ROWS[name]
    out = dict(row=name, seat=seat, classes={}, digest_first=None, error=None)
    try:
        del EVENTS[:]
        b, cfg, ids, schedule, ticks = fixture(seat)
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
        ok, info = witness(list(EVENTS), ids, b)
        out.update(witness=ok, info=info, ticks=ticks)
    except Exception:
        out['error'] = traceback.format_exc(limit=6)[-1500:]
    out['status'] = 'PASS' if (not out['error'] and out.get('witness') and not out['classes']
                               and out['digest_first'] is None) else 'FAIL'
    return out


def main():
    install_wrappers()
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
