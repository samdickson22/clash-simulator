"""C1 r1 regressions: semantic full state, Python/native snapshot continuation and live negative controls.

No host access or launches. Run with the same PYTHONPATH as probe_snapshots.py; pass output JSON.
"""
import json
import sys
from dataclasses import fields

import differential as D
import probe_snapshots as S
from clasher.ordinary_combat_clock import get_clock, publish


def make(side=0, attacker_first=True):
    cards = ('Knight', 'Ronin', 'Archers', 'Giant')
    b, cfg = D.initial(7, cards=cards), D.config(cards)
    for p in b.players:
        p.elixir = 10
    order = [(side, 'Knight', (3.5, 13.5)), (1-side, 'Ronin', (3.5, 18.5))]
    if not attacker_first:
        order.reverse()
    for owner, name, pos in order:
        if side:
            pos = (18-pos[0], 32-pos[1])
        assert b.deploy_card(owner, name, D.Position(*pos))
    for _ in range(21):
        b.step()
    a = next(e for e in b.entities.values() if e.card_stats.name == 'Knight')
    r = next(e for e in b.entities.values() if e.card_stats.name == 'Ronin')
    a.position = D.Position(14.5 if side else 3.5, 17.5 if side else 14.5)
    r.position = D.Position(14.5 if side else 3.5, 16.5 if side else 15.5)
    return b, cfg, a, r


def native(b, cfg):
    return D.clasher_core.BattleState(D.snapshot(b, cfg))


def state(n):
    return json.loads(n.snapshot())


def equal(b, cfg, n):
    classes = {}
    S.compare(b, cfg, n, b.tick, set(), classes)
    assert not classes, (b.tick, classes)
    assert n.digest() == D.battle_digest(b), b.tick
    assert S.norm(state(n).get('orphan_counter_pending', [])) == S.norm(b._orphan_counter_pending)


def advance(b, cfg, natives, ticks):
    for _ in range(ticks):
        b.step()
        for n in natives:
            n.step(1)
            equal(b, cfg, n)


def finish(side, attacker_first):
    b, cfg, a, r = make(side, attacker_first)
    a.target_id = r.id
    a._last_combat_target_id = r.id
    a._attack_windup_active = True
    c = get_clock(a)
    c.hit_timeline_ms, c.load_remaining_ms = c.hit_interval_ms-50, 0
    publish(a, c)
    r.target_id = r._last_combat_target_id = None
    r._attack_finish_elapsed_ms = 1
    c = get_clock(r)
    c.finish_elapsed_ms, c.hit_timeline_ms, c.load_remaining_ms = 1, 1000, 400
    publish(r, c)
    n = native(b, cfg)
    advance(b, cfg, [n], 1)
    assert r._ronin_pending and r._attack_finish_elapsed_ms == 51
    assert r._ordinary_clock.hit_timeline_ms == 0
    resumed = native(b, cfg)
    # Negative control models the rejected stop(): dropping finish admits a new target immediately.
    broken = state(n)
    next(e for e in broken['entities'] if e['id'] == r.id)['clock']['finish'] = 0
    mutant = D.clasher_core.BattleState(json.dumps(broken))
    b.step(); n.step(1); resumed.step(1); mutant.step(1)
    equal(b, cfg, n); equal(b, cfg, resumed)
    assert state(mutant) != state(n), 'finish negative control failed to detect lost recovery'
    advance(b, cfg, [n, resumed], 12)
    return dict(case='finish', side=side, attacker_first=attacker_first, ticks=14)


def reflect(side, mode):
    b, cfg, a, r = make(side)
    counter = next(m for m in r.mechanics if type(m).__name__ == 'RoninCounter')
    assert counter.try_counter(r, a, 100, b)
    due = b.tick + 6
    # Isolate scheduled damage from fresh ordinary hits; the stop buff also holds attacker movement.
    r.deploy_delay_remaining = 2.0
    r._native_natural_movement_active = False
    if mode in ('defender_dead', 'both_dead', 'multiple'):
        r.take_damage(r.hitpoints)
    if mode in ('target_dead', 'both_dead'):
        a.take_damage(a.hitpoints)
    if mode == 'multiple':
        r._ronin_pending.append((due, a.id, 30.0))
    if mode == 'dead_at_phase_boundary':
        r.take_damage(r.hitpoints)
        # Imported at the last frame before delivery, with death before combat eligibility.
        r._ronin_pending = [(b.tick+1, a.id, 200.0)]
        n = native(b, cfg)
        hp = a.hitpoints
        advance(b, cfg, [n], 1)
        assert a.hitpoints == hp-200 and not b._orphan_counter_pending
        advance(b, cfg, [n, native(b, cfg)], 3)
        return dict(case='reflect', side=side, mode=mode, ticks=4)
    if mode == 'dies_in_combat':
        # Attacker was created first, kills the defender before its eligible combat slot.
        r._ronin_pending = [(b.tick+1, a.id, 200.0)]
        r.hitpoints = 1
        a.target_id = a._last_combat_target_id = r.id
        a._attack_windup_active = True
        a.attack_cooldown = 0
        a._ordinary_force_due = True
        n = native(b, cfg)
        hp = a.hitpoints
        advance(b, cfg, [n], 1)
        assert not r.is_alive and a.hitpoints == hp-200
        assert not b._orphan_counter_pending, 'due reflect transferred instead of delivered'
        advance(b, cfg, [n, native(b, cfg)], 3)
        return dict(case='reflect', side=side, mode=mode, ticks=4)
    n = native(b, cfg)
    advance(b, cfg, [n], 1)
    assert (bool(b._orphan_counter_pending)) == (mode in ('defender_dead', 'both_dead', 'multiple'))
    resumed = native(b, cfg)  # after cleanup, only battle-owned work survives
    roundtrip = D.clasher_core.BattleState(n.snapshot())
    broken = state(n)
    broken.pop('orphan_counter_pending', None)
    for e in broken['entities']:
        e.pop('counter_pending', None)
    mutant = D.clasher_core.BattleState(json.dumps(broken))
    hp = a.hitpoints
    advance(b, cfg, [n, resumed, roundtrip], 4)
    assert b.tick == due-1
    if a.is_alive:
        assert a.hitpoints == hp, 'early reflect'
    advance(b, cfg, [n, resumed, roundtrip], 1)
    for _ in range(5):
        mutant.step(1)
    if a.is_alive:
        amount = 230 if mode == 'multiple' else 200
        assert a.hitpoints == hp-amount, (mode, hp, a.hitpoints)
        ma = next(e for e in state(mutant)['entities'] if e['id'] == a.id)
        assert ma['hp'] == hp, 'missing-queue negative control did not remain undamaged'
    assert not b._orphan_counter_pending
    assert not getattr(r, '_ronin_pending', []) or not r.is_alive
    advance(b, cfg, [n, resumed, roundtrip], 3)
    return dict(case='reflect', side=side, mode=mode, due=due, ticks=9)


def boulder(side):
    cards = ('Bowler', 'Knight', 'Archers', 'Giant')
    b, cfg = D.initial(7, cards=cards), D.config(cards)
    for p in b.players:
        p.elixir = 10
    for owner, name, x, y in [(side, 'Bowler', 3.5, 14.5), (1-side, 'Knight', 3.5, 17.5)]:
        assert b.deploy_card(owner, name, D.Position(18-x if side else x, 32-y if side else y))
    n = native(b, cfg)
    for _ in range(80):
        b.step(); n.step(1)
        shots = [e for e in b.entities.values() if type(e).__name__ == 'RollingProjectile']
        if shots:
            break
    assert shots, 'no boulder launched'
    equal(b, cfg, n)
    resumed = native(b, cfg)
    roundtrip = D.clasher_core.BattleState(n.snapshot())
    broken = json.loads(D.snapshot(b, cfg))
    shot = next(e for e in broken['entities'] if e['id'] == shots[0].id)
    assert tuple(shot['aim']) == (shots[0].straight_endpoint.x, shots[0].straight_endpoint.y)
    shot.pop('aim')
    mutant = D.clasher_core.BattleState(json.dumps(broken))
    advance(b, cfg, [n, resumed, roundtrip], 1)
    mutant.step(1)
    p = next(e for e in state(n)['entities'] if e['id'] == shots[0].id)
    q = next(e for e in state(mutant)['entities'] if e['id'] == shots[0].id)
    assert (p['x'], p['y']) != (q['x'], q['y']), 'endpoint negative control not sensitive'
    advance(b, cfg, [n, resumed, roundtrip], 20)
    return dict(case='boulder', side=side, ticks=21)


def idle_queue():
    b = D.initial(7)
    assert not next(f for f in fields(b) if f.name == '_orphan_counter_pending').init
    assert b.can_fast_forward_idle()
    cfg = D.config()
    assert 'orphan_counter_pending' not in json.loads(D.snapshot(b, cfg))
    assert 'orphan_counter_pending' not in state(native(b, cfg))
    b._orphan_counter_pending = [(b.tick+6, 99999, 200.0)]
    assert not b.can_fast_forward_idle()
    assert b.fast_forward_idle_ticks(10) == 0
    cloned = b.clone()
    cloned._orphan_counter_pending.clear()
    assert b._orphan_counter_pending, 'clone aliases pending counter queue'
    return dict(case='idle_queue_and_clone')


if __name__ == '__main__':
    results = []

    def record(result):
        results.append(result)
        with open(sys.argv[1], 'w') as out:
            json.dump(results, out, indent=2)
        print('PASS', result, flush=True)

    if sys.argv[2:] == ['--finish-only']:
        record(finish(0, True))
        sys.exit(0)
    record(idle_queue())
    if sys.argv[2:] == ['--extras']:
        for side in (0, 1):
            record(reflect(side, 'dies_in_combat'))
        print('PASS extras', len(results), flush=True)
        sys.exit(0)
    for side in (0, 1):
        for first in (True, False):
            record(finish(side, first))
        for mode in ('alive', 'defender_dead', 'target_dead', 'both_dead', 'multiple', 'dead_at_phase_boundary',
                     'dies_in_combat'):
            record(reflect(side, mode))
        record(boulder(side))
    print('PASS', len(results), 'cases; full state + continuations + negative controls', flush=True)
