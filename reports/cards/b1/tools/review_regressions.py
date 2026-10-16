"""B1 review regressions, single process; no network, subprocesses or runtime writes.

Compare every native snapshot field on native clone/reload continuations, plus
Python digest/RNG and all B1 selector/mount/buff state on live imports. Also audit
all Python/native snapshot fields, recording pre-existing representation gaps
rather than claiming the old digest certifies full-state equivalence.
"""
import collections
import json
import sys
import traceback
from differential import Position, battle_digest, clasher_core, config, initial, snapshot

RESULTS = []
RAW_DIFFS = collections.Counter()


def state(native):
    return json.loads(native.snapshot())


def spawn(b, name, seat, x, y):
    key = b.next_entity_id
    b._spawn_unit_at_position(Position(x, y), seat, b.card_loader.get_card(name),
                              deploy_delay_override=0, snap_to_valid=False)
    return b.entities[key]


def fresh(cards):
    b = initial(281, cards=cards)
    for p in b.players:
        p.elixir = 10
    return b, config(cards)


def full_diffs(a, b, path=''):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a-b) <= 1e-8:
        return
    if isinstance(a, dict) and isinstance(b, dict):
        for key in a.keys() | b.keys():
            yield from full_diffs(a.get(key), b.get(key), path+'/'+key)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            yield path+'/length'
        else:
            for x, y in zip(a, b):
                yield from full_diffs(x, y, path+'/*')
    elif a != b:
        yield path


def audited_state(b, native, cfg):
    actual = state(native)
    imported = clasher_core.BattleState(snapshot(b, cfg))
    expected = state(imported)
    RAW_DIFFS.update(full_diffs(expected, actual))
    assert native.digest() == battle_digest(b), ('digest', b.tick)
    words, index = native.rng_state()
    assert tuple(words)+(index,) == b.rng.getstate()[1]
    left = {e['id']: e for e in expected['entities']}
    right = {e['id']: e for e in actual['entities']}
    assert left.keys() == right.keys(), ('ids', b.tick, left.keys(), right.keys())
    # These fields were absent from battle_digest and caused the review misses.
    for id in left:
        for key in ('attack_choice', 'select_target', 'mount', 'rider_rank', 'clone_children', 'scope'):
            assert left[id].get(key) == right[id].get(key), (b.tick, id, key, left[id].get(key), right[id].get(key))
        assert left[id]['stats'].get('ignore_buffs') == right[id]['stats'].get('ignore_buffs')
    return actual


def continuation(b, native, cfg, ticks=12):
    """All native serialized fields survive clone/reload, no digest reduction."""
    saved = native.snapshot()
    copy, reload = native.clone(), clasher_core.BattleState(saved)
    assert state(copy) == state(reload) == state(native)
    py = b.clone()
    live_import = clasher_core.BattleState(snapshot(py, cfg))
    for _ in range(ticks):
        py.step(); copy.step(); reload.step(); live_import.step()
        assert state(copy) == state(reload), ('native full restart', py.tick)
        audited_state(py, live_import, cfg)
        assert copy.digest() == battle_digest(py), ('native continuation', py.tick)


def drive(b, native, cfg, ticks):
    for _ in range(ticks):
        b.step(); native.step()
        audited_state(b, native, cfg)


def test_clone(seat, card='GoblinGiant'):
    cards = (card, 'Clone', 'Zap', 'Knight')
    b, cfg = fresh(cards)
    parent = spawn(b, card, seat, 5.5, 11.5 if seat == 0 else 20.5)
    if card == 'GoblinGiant':
        proto = json.loads(snapshot(b, cfg))['entities'][6]['clone_template']
        assert proto['stats']['name'] == 'GoblinGiant'
        assert len(proto['clone_children']) == 2
        assert all(e['mount'] == proto['id'] for e in proto['clone_children'])
    native = clasher_core.BattleState(snapshot(b, cfg))
    assert b.deploy_card(seat, 'Clone', parent.position)
    assert native.apply_action(seat, 'Clone', parent.position.x, parent.position.y)
    audited_state(b, native, cfg)
    clones = [e for e in b.entities.values() if e.is_clone]
    assert len(clones) == (3 if card == 'GoblinGiant' else 1), len(clones)
    if card == 'GoblinGiant':
        giant = next(e for e in clones if e.card_stats.name == 'GoblinGiant')
        riders = [e for e in clones if getattr(e, '_rider_mount', None) is giant]
        assert len(riders) == 2 and all(e.hitpoints == 1 for e in clones)
    drive(b, native, cfg, 20)
    continuation(b, native, cfg)
    if card == 'GoblinGiant':
        # Spell death exercises remapped mounts and cloned dismount children.
        b.players[1-seat].elixir = 10
        native = clasher_core.BattleState(snapshot(b, cfg))
        pos = giant.position
        assert b.deploy_card(1-seat, 'Zap', pos)
        assert native.apply_action(1-seat, 'Zap', pos.x, pos.y)
        drive(b, native, cfg, 40)
        assert giant.id not in b.entities
        assert all(getattr(e, '_rider_mount', None) is not giant for e in b.entities.values())
        continuation(b, native, cfg)


def test_clone_boundaries(seat):
    cards = ('GoblinGiant', 'Clone', 'Zap', 'Knight')
    cfg = config(cards)
    # Both walls, both y bounds and all four corners; half-cell and real
    # deployment-anchor coordinates cover the review's .163/.149 repro too.
    positions = ((0.499, 11.5), (17.501, 20.5), (5.5, 0.25), (5.5, 31.75),
                 (0.25, 0.25), (0.25, 31.75), (17.75, 0.25), (17.75, 31.75))
    clamped = set()
    for x, y in positions:
        b = initial(281, cards=cards)
        for player in b.players:
            player.elixir = 10
        parent = spawn(b, 'GoblinGiant', seat, x, y)
        native = clasher_core.BattleState(snapshot(b, cfg))
        # A character may reach the quarter-cell boundary even where the
        # nearest public cast tile is blocked by arena geometry. Cast at the
        # nearest legal half-tile center, keeping the troop position intact.
        candidates = [((tx+0.5-x)**2+(ty+0.5-y)**2, tx+0.5, ty+0.5)
                      for ty in range(32) for tx in range(18)
                      if not cfg['blocked_tiles'][ty*18+tx]]
        distance2, tx, ty = min(candidates)
        assert distance2 <= cfg['cards']['Clone']['spell']['radius']**2
        tap = Position(tx, ty)
        assert b.deploy_card(seat, 'Clone', tap)
        assert native.apply_action(seat, 'Clone', tap.x, tap.y)
        audited_state(b, native, cfg)
        clones = [e for e in b.entities.values() if e.is_clone]
        giant = next(e for e in clones if e.card_stats.name == 'GoblinGiant')
        riders = [e for e in clones if getattr(e, '_rider_mount', None) is giant]
        assert len(clones) == 3 and len(riders) == 2
        for rider in riders:
            rx, ry = rider.position.x, rider.position.y
            assert 0.25 <= rx <= 17.75 and 0.25 <= ry <= 31.75
            if rx == 0.25: clamped.add('left')
            if rx == 17.75: clamped.add('right')
            if ry == 0.25: clamped.add('bottom')
            if ry == 31.75: clamped.add('top')
        continuation(b, native, cfg, ticks=6)
    assert {'left', 'right'} <= clamped, clamped
    # Fresh clones face their owner's forward axis, so their rear attachments
    # reach exactly the rear y boundary for that owner.
    assert ('bottom' if seat == 0 else 'top') in clamped, clamped


def test_mirror(seat):
    cards = ('BattleHealer', 'Mirror', 'Knight', 'Archers')
    b, cfg = fresh(cards)
    for table in ('create_areas', 'hit_areas'):
        assert {'BattleHealer', 'level12:BattleHealer'} <= cfg[table].keys()
        assert cfg[table]['level12:BattleHealer']['scope']['buff_name'] in ('BattleHealerAll', 'BattleHealerSpawnBuff')
    y = 11.5 if seat == 0 else 20.5
    knight = spawn(b, 'Knight', seat, 5.5, y+0.8)
    knight.hitpoints = 100
    knight.apply_stun(10)
    # Original caster is far away, and its creation pulse is removed before
    # either engine observes Mirror. Only the level12 pulse can heal this ally.
    assert b.deploy_card(seat, 'BattleHealer', Position(14.5, y))
    b.entities = {id:e for id,e in b.entities.items() if type(e).__name__ != 'HealPulse'}
    b.players[seat].elixir = 10
    native = clasher_core.BattleState(snapshot(b, cfg))
    assert b.deploy_card(seat, 'Mirror', Position(6.5, y))
    assert native.apply_action(seat, 'Mirror', 6.5, y)
    mirrored = [e for e in b.entities.values() if getattr(e.card_stats, 'name', '') == 'BattleHealer' and e.card_stats.level == 12]
    assert len(mirrored) == 1
    pulses = [e for e in b.entities.values() if type(e).__name__ == 'HealPulse']
    assert len(pulses) == 1 and pulses[0]._creation_source_id == mirrored[0].id
    spawn_pulse = pulses[0]
    amount = cfg['create_areas']['level12:BattleHealer']['scope']['heal_per_tick']
    assert spawn_pulse.heal_per_tick == amount
    assert spawn_pulse.buff_name == 'BattleHealerSpawnBuff'
    assert amount != cfg['create_areas']['BattleHealer']['scope']['heal_per_tick']
    for tick in range(1, 21):
        drive(b, native, cfg, 1)
        assert knight.hitpoints == 100 + (tick//5)*amount, (tick, knight.hitpoints, amount)
    continuation(b, native, cfg)
    assert not any(type(e).__name__ == 'HealPulse' for e in b.entities.values())
    # The enemy cannot attack. A committed mirrored hit must emit a new level12
    # on-hit pulse and heal the ally at its first 250ms deadline.
    enemy = spawn(b, 'Knight', 1-seat, mirrored[0].position.x,
                  mirrored[0].position.y + (0.7 if seat == 0 else -0.7))
    enemy.hitpoints = 50000
    enemy.apply_stun(10)
    knight.hitpoints = 100
    native = clasher_core.BattleState(snapshot(b, cfg))
    hit_pulse = None
    for _ in range(100):
        drive(b, native, cfg, 1)
        pulses = [e for e in b.entities.values() if type(e).__name__ == 'HealPulse'
                  and e.buff_name == 'BattleHealerAll']
        if pulses:
            hit_pulse = pulses[0]
            break
    assert hit_pulse is not None and hit_pulse._creation_source_id == mirrored[0].id
    assert enemy.hitpoints < 50000, 'no committed mirrored attack'
    hit_amount = cfg['hit_areas']['level12:BattleHealer']['scope']['heal_per_tick']
    assert hit_pulse.heal_per_tick == hit_amount
    assert hit_amount != cfg['hit_areas']['BattleHealer']['scope']['heal_per_tick']
    before = knight.hitpoints
    for _ in range(6):
        if hit_pulse.ticks_done > 0:
            break
        drive(b, native, cfg, 1)
    assert hit_pulse.ticks_done > 0, 'on-hit healing never reached its first deadline'
    assert knight.hitpoints == before + hit_amount, (before, knight.hitpoints, hit_amount)
    assert knight in hit_pulse.recipients
    continuation(b, native, cfg)


def test_immunity(buff_name, immune=True):
    from clasher.mechanics.shared.spawn_area import heal_area_pulse
    b, cfg = fresh(('BattleHealer', 'Knight', 'Archers', 'Heal'))
    healer = spawn(b, 'BattleHealer', 0, 6.5, 10.5)
    other = spawn(b, 'BattleHealer', 0, 7.5, 10.5)
    caster = spawn(b, 'Knight', 0, 6.5, 11.5)
    enemy = spawn(b, 'Knight', 1, 7.5, 11.5)
    # Remove their genuine creation pulses, isolating exactly one tested buff.
    b.entities = {id:e for id,e in b.entities.items() if type(e).__name__ != 'HealPulse'}
    for e in (healer, other, caster, enemy):
        e.hitpoints = 100
        e.apply_stun(10)
    if not immune:
        healer.card_stats.ignore_buffs = ()
        other.card_stats.ignore_buffs = ()
    area = {'name':'test-heal', 'radius':3000, 'buffTime':1000,
            'buffData':{'name':buff_name, 'healPerSecond':40, 'hitFrequency':250}}
    assert heal_area_pulse(caster, area)
    native = clasher_core.BattleState(snapshot(b, cfg))
    drive(b, native, cfg, 5)
    assert healer.hitpoints == (100 if immune else 125), healer.hitpoints
    assert other.hitpoints == (100 if immune else 125), other.hitpoints
    assert caster.hitpoints == 125, caster.hitpoints  # no caster exclusion
    assert enemy.hitpoints == 100
    continuation(b, native, cfg)


def test_selector(seat, card='ThreeMusketeers'):
    cards = (card, 'Minions', 'Knight', 'Archers')
    b, cfg = fresh(cards)
    y = 10.5 if seat == 0 else 21.5
    assert b.deploy_card(seat, card, Position(4.5, y))
    spawn(b, 'Minions', 1-seat, 4.5, 15 if seat == 0 else 17)
    native = clasher_core.BattleState(snapshot(b, cfg))
    witnessed = False
    for _ in range(140):
        b.step(); native.step()
        rows = audited_state(b, native, cfg)['entities']
        shots = [e for e in rows if e['class'] == 'Projectile' and e['owner'] == seat]
        if shots and not witnessed:
            assert all('attack_choice' not in e and 'select_target' not in e for e in shots)
            continuation(b, native, cfg)
            witnessed = True
    assert witnessed, 'no native projectile was observed'


def run(name, fn, *args):
    try:
        fn(*args)
        row = dict(name=name, ok=True)
    except Exception:
        row = dict(name=name, ok=False, error=traceback.format_exc())
    RESULTS.append(row)
    print(json.dumps(row), flush=True)


if __name__ == '__main__':
    for seat in (0, 1):
        run(f'clone-graph-seat{seat}', test_clone, seat)
        run(f'clone-boundaries-seat{seat}', test_clone_boundaries, seat)
        run(f'clone-knight-negative-seat{seat}', test_clone, seat, 'Knight')
        run(f'mirror-healer-seat{seat}', test_mirror, seat)
        run(f'selector-seat{seat}', test_selector, seat)
        run(f'projectile-musketeer-negative-seat{seat}', test_selector, seat, 'Musketeer')
    for buff in ('BattleHealerAll', 'BattleHealerSpawnBuff'):
        run('recipient-immunity-'+buff, test_immunity, buff)
        run('removed-immunity-negative-'+buff, test_immunity, buff, False)
    report = dict(tests=RESULTS, passed=sum(r['ok'] for r in RESULTS), total=len(RESULTS),
                  full_state_audit_diff_paths=dict(sorted(RAW_DIFFS.items())),
                  note='Native clone/reload equality is exact for every serialized field. Raw Python/native representation gaps are reported, not silently dropped.')
    with open(sys.argv[1], 'x') as f:
        json.dump(report, f, indent=2)
    if report['passed'] != report['total']:
        raise SystemExit(1)
