"""Pre-pilot gates of the level-aware search pilot (reports/bot/levels/DESIGN.md, "Gates").

    PYTHONHASHSEED=0 python -m bot.levels.gates [exports towers sides spell roots cut fair]  (default: all)

Each gate prints PASS/FAIL lines and a JSON summary; the process exits 1 on any FAIL.
Forced all-11 game parity is separate (bot/levels/run.py, see PROGRESS.md).
The cut gate starts one pool worker: reserve two CPU slots including this process.
Other gates start no child processes. Existing exports only: a cache miss must never start an exporter.
"""
from __future__ import annotations

import copy
import json
import sys

FAILS = []
COUNTS = dict(checks=0, passed=0)
STATS = {}
GATES = ('exports', 'towers', 'sides', 'spell', 'roots', 'cut', 'fair')


def check(name, ok, detail=''):
    COUNTS['checks'] += 1
    COUNTS['passed'] += int(bool(ok))
    print(('PASS ' if ok else 'FAIL ') + name + (f'  {detail}' if detail else ''), flush=True)
    if not ok:
        FAILS.append(name)


def require(name, ok, detail=''):
    """Stop an invalid fixture before its downstream comparisons can give misleading passes."""
    check(name, ok, detail)
    if not ok:
        raise ValueError(f'{name}: {detail}')


def _preload(rt, gates):
    from bot.levels.configs import base_cards
    from bot.levels.fixture_support import FrozenLevelConfigs, normalized_spells
    from bot.levels.profile import OpponentEstimate
    levels = {11}
    if set(gates) & {'sides', 'spell', 'roots', 'cut', 'fair'}:
        levels.update((4, 5, 6, 7, 9))
    if 'fair' in gates:
        estimate = OpponentEstimate(rt)
        levels.update(estimate(c) for c in base_cards(rt.R.config))
    # Strict existing-only support/raw/canonical/check11 validation before any roots;
    # no LevelConfigs.supported() fallback may rewrite the approved whitelist.
    lc = FrozenLevelConfigs(rt, levels)
    STATS['normalized_spells'] = normalized_spells(rt, lc)
    expected = set(base_cards(rt.R.config))
    for level in sorted(levels):
        data = lc.load(level)
        absent = expected - (set(data['cards']) | set(data.get('errors', {})))
        require(f'cache L{level} complete', data.get('level') == level and not absent,
                f'{lc.path(level)}; cards={len(data["cards"])} errors={data.get("errors", {})}; missing={sorted(absent)}')
    rt._level_configs = lc
    STATS['cache_levels'] = sorted(levels)
    STATS['cache_manifest'] = lc.manifest
    return lc


def gate_towers(rt):
    from clasher.tower_scaling import tower_stat as engine_stat
    from bot.levels.root import tower_stat
    for name, engine in (('KingTower', 'KingTower'), ('Tower', 'PrincessTower')):
        for field, efield in (('max_hp', 'hitpoints'), ('damage', 'damage')):
            for level in (10, 12):
                check(f'towers curve {name}.{field} L{level} == tower_scaling', tower_stat(name, field, level) ==
                      engine_stat(engine, efield, level), f'{tower_stat(name, field, level)}')
    # RoyaleSim 16.402 tower HP at the pilot's levels
    import royalesim as rs
    from bot.players.royalesim_vocab import rsim_battle
    from bot.players.royalesim_adapter import royalesim_card
    b = rsim_battle('16.402')
    cat = json.loads(b.catalogue_json())
    ids = {r[0]: i for i, r in enumerate(cat)}
    deck = [ids[royalesim_card(n)]
            for n in ('Knight', 'Archers', 'Giant', 'Musketeer', 'Fireball', 'Arrows', 'Minions', 'Valkyrie')]
    for level in (4, 5, 6, 7, 8):
        b.reset(seed=1, decks=[deck, deck], shuffle=0, start_tick=0, elixir_milli=[6000, 6000], tower_hp=None,
                spawns=[], tower_levels=[level, level])
        hp = json.loads(b.state_json())['players'][0]['tower_max_hp']
        ours = [tower_stat('KingTower', 'max_hp', level), tower_stat('Tower', 'max_hp', level),
                tower_stat('Tower', 'max_hp', level)]
        check(f'towers L{level} HP == RoyaleSim 16.402', hp == ours, f'rsim {hp} ours {ours}')
    del rs


def gate_exports(rt, lc):
    """Disk exports must match the native JSON, including tuple/list round trips."""
    good, bad = lc.check11()
    data = lc.load(11)
    from bot.levels.configs import base_cards
    expected = set(base_cards(rt.R.config))
    cached = set(data['cards'])
    check('L11 cache contains every expected card', cached == expected,
          f'expected={len(expected)} cached={len(cached)} missing={sorted(expected-cached)} extra={sorted(cached-expected)}')
    raw_equal = sum(e['card'] == rt.R.config['cards'].get(c) for c, e in data['cards'].items())
    print(f'export comparison: raw Python equality {raw_equal}/{len(data["cards"])}; '
          f'native JSON equality {len(good)}/{len(data["cards"])}', flush=True)
    check('all L11 cached exports == native config JSON', bool(expected) and set(good) == expected and not bad,
          f'good={len(good)}/{len(expected)} bad={bad}')
    STATS['exports'] = dict(expected=len(expected), cached=len(cached), raw_equal=raw_equal, canonical=len(good))
    # Coordinate tuples are one concrete schema-only mismatch in disk JSON.
    for card in ('Musketeer', 'Archers', 'Fireball'):
        raw = rt.R.config['cards'][card]['units'][0][0]['tunnel_origin']
        cached = data['cards'][card]['card']['units'][0][0]['tunnel_origin']
        print(f'{card}.units[0][0].tunnel_origin: runtime {type(raw).__name__} {raw!r}; '
              f'disk {type(cached).__name__} {cached!r}', flush=True)


def _state(rt, cfg, cards):
    """A level-11 Python start state (both decks = cards) as a native root on config `cfg`."""
    import clasher_core
    from differential import initial, snapshot
    b = initial(cards=cards)
    for p in b.players:
        p.elixir = 10.
    return clasher_core.BattleState(snapshot(b, cfg))


def _entities(n):
    return json.loads(n.snapshot())['entities']


def _native_deploy(rt, state, seat, card, x, y):
    """World tile coordinates -> current hand slot + own-frame tile, scripts.rs::apply_discrete."""
    before = json.loads(state.snapshot())['players'][seat]
    hand = before['hand']
    require(f'native fixture seat{seat} {card} in hand', card in hand, f'hand={hand}')
    require(f'native fixture seat{seat} target in arena',
            seat in (0, 1) and .5 <= x <= 17.5 and .5 <= y <= 31.5, f'world tiles=({x}, {y})')
    own_x, own_y = (x, y) if seat == 0 else (18-x, 32-y)
    col, row = int(own_x), int(own_y)
    slot = hand.index(card)
    action = slot*576 + row*18 + col
    center = (col+.5, row+.5) if seat == 0 else (18-(col+.5), 32-(row+.5))
    accepted = rt.R.native.apply_discrete(state, seat, action)
    detail = (f'card={card} slot={slot} action={action} own_tile=({col},{row}) '
              f'world request=({x},{y}) world center={center}; units=tiles, grid=18x32')
    if accepted:
        after = json.loads(state.snapshot())['players'][seat]
        require(f'native fixture seat{seat} {card} consumed requested slot',
                after['hand'][slot] is None and after['last_card'] == card and after['elixir'] < before['elixir'],
                detail)
    else:
        print('native fixture rejected: ' + detail, flush=True)
    return accepted


def _py_deploy(card, levels, positions, steps=0):
    """Python engine (the runtime's src): each seat deploys `card` at its level; entities after `steps` ticks."""
    from clasher.arena import Position
    from differential import initial
    b = initial(cards=(card, 'Knight', 'Archers', 'Giant'))
    for seat, level in enumerate(levels):
        b.players[seat].set_card_levels({card: level})
        b.players[seat].elixir = 10.
    for seat in (0, 1):
        assert b.deploy_card(seat, card, Position(*positions[seat]))
    for _ in range(steps):
        b.step()
    return b


def gate_sides(rt, lc):
    """Same card, different seats and levels, deployed in one native state."""
    pos = ((4.5, 10.5), (4.5, 21.5))
    for card, levels in (('Musketeer', (4, 7)), ('Archers', (7, 5)), ('Giant', (6, 11)), ('Minions', (5, 6)),
                         ('Cannon', (6, 4))):
        cfg, rep = lc.mixed(lambda s, c: levels[s] if c == card else 11)
        n = _state(rt, cfg, (card, 'Knight', 'Archers', 'Giant'))
        before = {e['id'] for e in _entities(n)}
        x0 = 9.5 if card == 'Cannon' else pos[0][0]
        ok = [_native_deploy(rt, n, 0, card, x0, 9.5 if card == 'Cannon' else pos[0][1]),
              _native_deploy(rt, n, 1, card, x0, 22.5 if card == 'Cannon' else pos[1][1])]
        new = [e for e in _entities(n) if e['id'] not in before]
        got = sorted((e['owner'], e['stats']['name'], e['stats']['max_hp'], e['stats']['damage'],
                      e['stats'].get('payload_key')) for e in new)
        b = _py_deploy(card, levels, ((x0, 9.5), (x0, 22.5)) if card == 'Cannon' else pos)
        want = sorted((e.player_id, e.card_stats.name, float(e.max_hitpoints), float(getattr(e, 'damage', 0)))
                      for e in b.entities.values() if e.card_stats.name not in ('KingTower', 'Tower', 'PrincessTower'))
        check(f'sides {card} L{levels} accepted', all(ok), str(ok))
        check(f'sides {card} L{levels} native == python', [g[:4] for g in got] == want,
              f'native {got[:4]} python {want[:4]}')


def gate_spell(rt, lc):
    """Fireball by each seat at its level onto a level-11 Musketeer and onto a crown tower."""
    import clasher_core
    from differential import initial, snapshot
    from clasher.arena import Position
    for levels in ((5, 7), (4, 9)):
        cfg, _ = lc.mixed(lambda s, c: levels[s] if c == 'Fireball' else 11)
        for seat in (0, 1):
            y = 21.5 if seat == 0 else 10.5
            q = initial(cards=('Fireball', 'Musketeer', 'Knight', 'Archers'))
            for p in q.players:
                p.elixir = 10.
            sim = clasher_core.BattleState(snapshot(q, cfg))
            require(f'spell seat{seat} target accepted', _native_deploy(rt, sim, 1 - seat, 'Musketeer', 4.5, y))
            sim.step(25)       # past the deploy time, before the Musketeer moves far
            hp0 = {e['id']: e['hp'] for e in _entities(sim) if e['stats']['name'] == 'Musketeer'}
            require(f'spell seat{seat} Fireball L{levels[seat]} accepted', _native_deploy(rt, sim, seat, 'Fireball', 4.5, y))
            sim.step(60)
            hit = [hp0[e['id']] - e['hp'] for e in _entities(sim) if e['id'] in hp0]
            want = lc.entry('Fireball', levels[seat])['card']['spell']['damage'] if levels[seat] != 11 else \
                rt.R.config['cards']['Fireball']['spell']['damage']
            # Python engine reference: the same cast at that level
            b = initial(cards=('Fireball', 'Musketeer', 'Knight', 'Archers'))
            b.players[seat].set_card_levels({'Fireball': levels[seat]})
            _, _, spell = b.resolve_card_play(seat, 'Fireball')
            check(f'spell Fireball seat{seat} L{levels[seat]} impact == level damage', hit == [want],
                  f'hit {hit} want {want} python {spell.damage}')
            check(f'spell Fireball seat{seat} L{levels[seat]} level damage == python', want == spell.damage)
            # crown tower: princess tower on the target side
            q = initial(cards=('Fireball', 'Musketeer', 'Knight', 'Archers'))
            for p in q.players:
                p.elixir = 10.
            sim = clasher_core.BattleState(snapshot(q, cfg))
            towers0 = {e['id']: e['hp'] for e in _entities(sim) if e['owner'] == 1 - seat and not e.get('king')
                       and e['stats']['name'] in ('Tower', 'PrincessTower')}
            tx = [e for e in _entities(sim) if e['id'] in towers0][0]
            require(f'spell seat{seat} crown cast accepted', _native_deploy(rt, sim, seat, 'Fireball', tx['x'], tx['y']))
            sim.step(60)
            dmg = [towers0[e['id']] - e['hp'] for e in _entities(sim) if e['id'] in towers0]
            crown = (lc.entry('Fireball', levels[seat])['card']['spell']['crown_tower_damage'])
            check(f'spell Fireball seat{seat} L{levels[seat]} crown damage', max(dmg) == crown,
                  f'tower dmg {dmg} want {crown} python {getattr(spell, "crown_tower_damage", None)}')
    del Position


def _template(rt, name, kind, *, spell=None):
    """Select a real public token/kind pair, without assuming token numbers or names."""
    matches = [(key, e) for key, e in rt.R.templates.items()
               if key[1] == kind and e['stats']['name'] == name
               and (spell is None or e.get('spell_name') == spell)]
    if not matches:
        raise ValueError(f'fixture needs public template {name}/{kind}, spell={spell!r}')
    return min(matches, key=lambda pair: pair[0])


def _export_unit(lc, card, level, seat=0):
    # Raw disk exports are the independent expected values, before root.py's delta/qualification code.
    return lc.load(level)['cards'][card]['card']['units'][seat][0]


def gate_roots(rt, lc):
    """ExactLevelRoot.payload on public rows only, with independently exported expected stats."""
    import numpy as np
    from types import SimpleNamespace
    from bot.levels.root import ExactLevelRoot
    from clasher.rl.contract_v5 import CHAMPION_COOLDOWN_GLOBAL, CHAMPION_DURATION_GLOBAL
    kinds = ('Troop', 'Building', 'Projectile', 'AreaEffect', 'Entity')
    # No Skeletons card: a visible Skeleton has the known producing card Tombstone.
    # Arrows and Fireball share an empty body stats name. The public spell
    # identity must select Fireball, rather than the first deck producer.
    deck = ('Musketeer', 'Fireball', 'Tombstone', 'Arrows')
    own = dict.fromkeys(deck, 4)
    total = 0
    for seat in (0, 1):
        root = ExactLevelRoot(rt, own, lambda c: 7, 6, 6, lc=lc)
        tokens, rows, expected = [], [], []
        for owner in (seat, 1-seat):
            level = 4 if owner == seat else 7
            musk = _export_unit(lc, 'Musketeer', level, owner)
            tomb = _export_unit(lc, 'Tombstone', level, owner)
            child = lc.load(level)['cards']['Tombstone']['tables']['production_children']['Tombstone']
            fire = _export_unit(lc, 'Fireball', level, owner)
            specs = [
                ('Musketeer', 'Troop', None, musk['stats'], .5, None),
                ('Musketeer', 'Projectile', '', dict(max_hp=1., damage=musk['stats']['damage'],
                                                    payload_key=musk['stats']['payload_key']), 1., None),
                ('Tower', 'Building', None, dict(max_hp=2030., damage=72.), .5, None),
                ('KingTower', 'Building', None, dict(max_hp=3312., damage=72.), .5, None),
                ('Tower', 'Projectile', '', dict(max_hp=1., damage=72.), 1., None),
                (fire['stats']['name'], 'Projectile', 'Fireball', fire['stats'], 1., f'level{level}:Fireball'),
                ('Tombstone', 'Building', None, tomb['stats'], .5, None),
                (child['stats']['name'], 'Troop', None, child['stats'], .5, None),
            ]
            for name, kind, spell, stats, fraction, qualified in specs:
                key, _ = _template(rt, name, kind, spell=spell)
                row = np.zeros(32, dtype=np.float32)
                row[0:2] = (.25, .25 if owner == seat else .75)
                row[2], row[3] = int(owner == seat), int(owner != seat)
                row[4 + kinds.index(kind)] = 1
                row[9], row[28] = fraction, 1 if owner == seat else -1
                tokens.append(key[0])
                rows.append(row)
                fields = {k: stats[k] for k in ('max_hp', 'damage', 'payload_key') if k in stats}
                expected.append((owner, name, kind, fraction, fields, qualified, level))
        glob = np.ones(max(32, CHAMPION_COOLDOWN_GLOBAL+1, CHAMPION_DURATION_GLOBAL+1), dtype=np.float32)
        glob[4] = 0
        obs = SimpleNamespace(entity_ids=np.asarray(tokens), entity_mask=np.ones(len(tokens), dtype=bool),
                              entity_features=np.stack(rows), global_features=glob)
        hud = dict(elixir=10., hand=list(deck), cycle=list(deck), refill=0)
        info = SimpleNamespace(seat=seat, tick=100, packet=SimpleNamespace(observation=obs), own=hud)
        payload = json.loads(root.payload(info, copy.deepcopy(hud), np.random.default_rng(123)))
        require(f'roots seat{seat} no skipped/unmapped bodies',
                len(payload['entities']) == len(expected) and root.stats['bodies'] == len(expected)
                and root.stats['unmapped'] == 0 and root.stats['roots'] == 1
                and root.stats['leveled'] == 10 and root.stats['towers'] == 6, str(root.stats))
        for i, (e, want) in enumerate(zip(payload['entities'], expected)):
            owner, name, kind, frac, fields, spell, level = want
            got = {k: e['stats'].get(k) for k in fields}
            check(f'roots seat{seat} row{i} {name}/{kind} owner{owner} L{level}',
                  e['owner'] == owner and e['stats']['name'] == name and got == fields
                  and e['hp'] == frac*fields['max_hp'],
                  f'got={got} hp={e["hp"]} expected={fields} hp={frac*fields["max_hp"]}')
            if spell:
                cfg = payload['config']['cards']
                raw_spell = lc.load(level)['cards']['Fireball']['card']['spell']
                check(f'roots seat{seat} owner{owner} qualified carrier and cut spell',
                      e.get('spell_name') == spell and spell in cfg and cfg[spell]['spell'] == raw_spell,
                      f'spell_name={e.get("spell_name")} needed={spell}')
        # Reconstruction must not lose these checks on native snapshot serialization.
        import clasher_core
        rebuilt = json.loads(clasher_core.BattleState(json.dumps(payload)).snapshot())
        diagnostic = _snapshot_physics(payload['entities'], rebuilt['entities'], f'roots seat{seat}')
        STATS.setdefault('root_snapshot_diagnostics', {})[str(seat)] = diagnostic
        check(f'roots seat{seat} native snapshot preserves body HP/stats/spell',
              diagnostic['normalized_equal'], diagnostic['normalized_difference'])
        total += len(expected)
    STATS['roots'] = dict(seats=2, public_bodies=total)


def _cut_fixture(rt, lc, profile):
    import clasher_core
    from bot.levels.configs import CutConfig
    from bot.search.lopp_fast import split_snapshot
    cfg, report = lc.mixed(lambda s, c: profile.get(c, 11))
    require(f'cut profile {profile} supported', not report['unsupported'], str(report['unsupported']))
    n = _state(rt, cfg, ('Musketeer', 'Fireball', 'Tombstone', 'Knight', 'Archers', 'Minions', 'Giant', 'Arrows'))
    for seat, card, x, y in ((0, 'Musketeer', 4.5, 10.5), (1, 'Tombstone', 4.5, 22.5)):
        require(f'cut fixture {card} accepted', _native_deploy(rt, n, seat, card, x, y))
    n.step(25)
    # Far target: capture the carrier before impact. The bounded loop accommodates deploy delay.
    require('cut fixture Fireball accepted', _native_deploy(rt, n, 0, 'Fireball', 13.5, 25.5))
    spell_key = f'level{profile["Fireball"]}:Fireball'
    for _ in range(31):
        if any(e.get('spell_name') == spell_key for e in _entities(n)):
            break
        n.step(1)
    snap = n.snapshot()
    obj = json.loads(snap)
    musks = [e for e in obj['entities'] if e['owner'] == 0 and e['stats']['name'] == 'Musketeer'
             and e['class'] == 'Troop']
    want = _export_unit(lc, 'Musketeer', profile['Musketeer'])['stats']
    require('cut exact Musketeer stats/payload present', len(musks) == 1 and all(
        musks[0]['stats'].get(k) == want[k] for k in ('max_hp', 'damage', 'payload_key')),
        f'expected hp/damage/key={[(k, want[k]) for k in ("max_hp", "damage", "payload_key")]}')
    require('cut qualified Fireball captured before impact', any(
        e.get('spell_name') == spell_key and e['class'] == 'Projectile' and e['alive'] for e in obj['entities']),
        f'needed {spell_key}; tick={obj["tick"]}')
    text = CutConfig(cfg).text(obj['players'], obj['entities'], obj.get('pending_casts', []))
    kept = json.loads(text)
    for card, level in profile.items():
        key = f'level{level}:{card}'
        require(f'cut retains needed qualified card {key}', key in kept['cards'],
                f'needed cards[{key}] for live body/carrier/producer')
    require('cut retains exact qualified Fireball spell', spell_key in kept['cards'] and
            kept['cards'][spell_key]['spell'] == lc.load(profile['Fireball'])['cards']['Fireball']['card']['spell'],
            f'needed cards[{spell_key}]')
    tomb_key = f'level{profile["Tombstone"]}:Tombstone'
    require('cut reachable Tombstone producer present', any(
        e['stats'].get('payload_key') == tomb_key and e['class'] == 'Building' for e in obj['entities']), tomb_key)
    # Explicit reachable-table closure: the live producer can both spawn and die after this snapshot.
    tables = lc.load(profile['Tombstone'])['cards']['Tombstone']['tables']
    for table in ('production_children', 'death_children'):
        require(f'cut retains exact reachable {table}[{tomb_key}]',
                kept.get(table, {}).get(tomb_key) == tables[table]['Tombstone'], tomb_key)
    parts = split_snapshot(snap)
    require('cut fixture snapshot splits', parts is not None)
    cut_root = clasher_core.BattleState(parts[0] + text + parts[2])
    rebuilt = clasher_core.BattleState(snap)
    check('cut/snapshot preserve live fixture entities', _entities(cut_root) == obj['entities'] == _entities(rebuilt))
    return n, cut_root, rebuilt, obj['tick']


def gate_cut(rt, lc):
    """Bounded scripted transport parity, one child, explicit profile A -> B -> A raw-fc reuse."""
    import hashlib
    import os
    import time
    from bot.levels.root import leaf_native, tower_stat
    from bot.search.lopp import batch_rollouts
    from bot.search.lopp_fast import LearnedPool, split_snapshot
    require('cut uses fork with exactly one child', sys.platform.startswith('linux') and
            os.environ.get('CLASHER_LOPP_POOL_START', 'fork') == 'fork',
            'run on reviewed Linux host with CLASHER_LOPP_POOL_START unset or fork; reserve 2 CPU slots')
    native = leaf_native(rt, 6, 6)
    meta = copy.deepcopy(rt.R.meta)
    for name in ('Tower', 'KingTower'):
        meta['bodies'][name]['hp'] = float(tower_stat(name, 'max_hp', 6))
    a = dict(Musketeer=4, Fireball=5, Tombstone=4)
    b = dict(Musketeer=7, Fireball=7, Tombstone=7)
    fixtures = [_cut_fixture(rt, lc, p) for p in (a, b)]
    # Two placements per slot, WAIT and a timed wait; 10 keys per profile, no random trials.
    actions = [slot*576 + tile for slot in range(4) for tile in (9*18+4, 12*18+13)] + [2304, 2401]
    keys, sizes = [], []
    compared = dict(cut=0, snapshot=0, pool=0)
    pool = LearnedPool(1, native, meta=json.dumps(meta))
    try:
        for trial, fixture in enumerate((fixtures[0], fixtures[1], fixtures[0])):
            full, cut, rebuilt, tick = fixture
            seat = trial % 2
            kw = dict(delay=27, opp_delay=27, horizon=80, interval=10, elixir_weight=1., tick0=tick)
            refs = batch_rollouts(native, full, seat, actions, 'balanced', **kw)
            for name, other in (('cut', cut), ('snapshot', rebuilt)):
                vals = batch_rollouts(native, other, seat, actions, 'balanced', **kw)
                check(f'cut profile {trial} {name} values == own uncut reference', vals == refs,
                      f'seat={seat} keys={actions}; reference={refs}; got={vals}')
                compared[name] += len(actions)
            # Exactly the production raw fc protocol; parent/child share B's native and matching metadata.
            parts = split_snapshot(cut.snapshot())
            require(f'cut profile {trial} raw snapshot splits', parts is not None)
            key = hashlib.sha1(parts[1].encode()).hexdigest() + 'r'
            keys.append(key)
            pool.begin(cut, seat, kw, 'balanced', None, base_cut=True)
            sizes.append(len(pool.shipped))
            require(f'cut profile {trial} raw content key shipped', key in pool.shipped,
                    f'key={key} shipped={list(pool.shipped)}')
            pool.submit(0, trial, actions)
            vals = pool.collect(time.monotonic() + 30).get(trial)
            require(f'cut profile {trial} pool completed', vals is not None and not pool.errors and not pool.pending,
                    f'errors={pool.errors}; pending={pool.pending}; values={vals}')
            check(f'cut profile {trial} pooled values == own uncut reference', vals == refs,
                  f'seat={seat} reference={refs}; got={vals}')
            compared['pool'] += len(vals)
        check('cut A -> B uses distinct content keys', keys[0] != keys[1], str(keys))
        check('cut final A reuses original content key', keys[2] == keys[0] and sizes == [1, 2, 2],
              f'keys={keys}; shipped sizes={sizes}')
    finally:
        pool.close()
    STATS['cut'] = dict(profiles=['A', 'B', 'A'], actions_per_profile=len(actions), values_compared=compared,
                        shipped_sizes=sizes, content_keys=keys, child_processes=1,
                        controller='balanced', tower_metadata_levels=[6, 6])


def _plain(value):
    """Canonical comparison of the complete public dataclass packet, including masks and HUD."""
    import dataclasses
    import numpy as np
    if dataclasses.is_dataclass(value):
        return {f.name: _plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(v) for v in value]
    return value


def _difference(a, b, path='public'):
    """First differing public field, for an actionable failure without dumping entire packets/configs."""
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            return f'{path}: different keys {sorted(set(a)^set(b))}'
        for k in a:
            found = _difference(a[k], b[k], f'{path}.{k}')
            if found:
                return found
        return ''
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return f'{path}: lengths {len(a)} != {len(b)}'
        for i, (x, y) in enumerate(zip(a, b)):
            found = _difference(x, y, f'{path}[{i}]')
            if found:
                return found
        return ''
    return '' if a == b else f'{path}: {a!r} ({type(a).__name__}) != {b!r} ({type(b).__name__})'


def _snapshot_physics(old, native, label):
    """Report every selected raw JSON difference before applying two serde String defaults."""
    def rows(entities):
        out = []
        for e in entities:
            row = {k: e[k] for k in ('id', 'owner', 'class', 'x', 'y', 'hp')}
            row.update({f'stats.{k}': e['stats'][k] for k in ('name', 'max_hp', 'damage')})
            if 'payload_key' in e['stats']:
                row['stats.payload_key'] = e['stats']['payload_key']
            if 'spell_name' in e:
                row['spell_name'] = e['spell_name']
            out.append(row)
        return out

    before, after = rows(old), rows(native)
    differences = []
    for i in range(max(len(before), len(after))):
        a = before[i] if i < len(before) else {}
        b = after[i] if i < len(after) else {}
        for field in dict.fromkeys([*a, *b]):
            if (field in a) == (field in b) and a.get(field) == b.get(field) and type(a.get(field)) is type(b.get(field)):
                continue
            def value(row):
                return dict(present=field in row, value=row.get(field),
                            type=type(row[field]).__name__ if field in row else 'missing')
            differences.append(dict(index=i, old_entity={k: a.get(k) for k in ('id', 'owner', 'class')},
                                    native_entity={k: b.get(k) for k in ('id', 'owner', 'class')},
                                    field=field, old=value(a), native=value(b)))

    def normalize(raw):
        out = copy.deepcopy(raw)
        for row in out:
            # Pinned lib.rs: Stats.payload_key and Entity.spell_name are String + serde(default).
            # Only absence becomes ''; explicit nulls and explicit qualified strings remain unchanged.
            row.setdefault('stats.payload_key', '')
            row.setdefault('spell_name', '')
        return out

    def ranges(raw):
        return {field: [min(row[field] for row in raw), max(row[field] for row in raw)] if raw else None
                for field in ('x', 'y', 'hp', 'stats.max_hp', 'stats.damage')}

    diagnostic = dict(raw_differences=differences, entity_counts=dict(old=len(before), native=len(after)),
                      units=dict(x_y='arena tiles; x in [0,18], y in [0,32]', hp_max_hp='hitpoints',
                                 damage='hitpoints per hit', snapshot='serde f64; no quantization/rescaling/tolerance',
                                 ordering='Vec<Entity> index and entity id retained exactly'),
                      ranges=dict(old=ranges(before), native=ranges(after)))
    print(label + ' raw snapshot physics: ' + json.dumps(diagnostic, sort_keys=True), flush=True)
    normalized_before, normalized_after = normalize(before), normalize(after)
    diagnostic.update(normalized_fields=['missing stats.payload_key -> empty string', 'missing spell_name -> empty string'],
                      normalized_equal=normalized_before == normalized_after,
                      normalized_difference=_difference(normalized_before, normalized_after, 'entities'))
    return diagnostic


def gate_fair(rt, lc):
    """Different hidden truth -> identical actual public info, B roots and B decisions, both seats."""
    import numpy as np
    from bot.levels.player import make_arm_player
    from bot.levels.profile import LIVE_DECK, OWN_LEVELS, true_profile
    from bot.players.base import MatchContext, PublicView
    from bot.players.royalesim_match import RsimMatch
    from bot.players.royalesim_vocab import load
    from bot.search.lopp import FAILURES
    vocab = load(rt)
    opp = ('Knight', 'Arrows', 'Fireball', 'Giant', 'MiniPekka', 'Musketeer', 'Archers', 'Minions')
    root_calls = decisions = 0
    for seat in (0, 1):
        decks = [None, None]
        decks[seat], decks[1-seat] = list(LIVE_DECK), list(opp)
        profiles = [true_profile(rt, decks, seat, dict.fromkeys(opp, lv)) for lv in (5, 7)]
        require(f'fair seat{seat} hidden profiles differ', profiles[0].cards[1-seat] != profiles[1].cards[1-seat])
        infos = []
        for profile in profiles:
            match = RsimMatch(rt, vocab, decks, 1701, client='16.402', levels=profile.cards, tower_levels=profile.towers)
            match.b.step([], 100)
            match.refresh()
            infos.append(match.information(seat))
        public = [_plain(info) for info in infos]
        require(f'fair seat{seat} complete public information identical', public[0] == public[1],
                _difference(*public))
        # The factory receives one fair view, no hidden profile, true opponent deck, or match object.
        view = dict(own_levels={c: OWN_LEVELS[c] for c in LIVE_DECK}, own_tower=6, opp_tower=6)
        roots, choices = [], []
        for i, info in enumerate(infos):
            player = make_arm_player(rt, 'B', view=view)
            try:
                require(f'fair seat{seat} B serial footprint', getattr(player, 'pool_size', 0) == 0 and
                        getattr(player, 'native_threads', 1) == 1)
                player.start(MatchContext(seat=seat, seed=1701, own_order=tuple(LIVE_DECK)))
                rng = np.random.default_rng(9876)
                belief = player.p.belief.sample(rng)
                roots.append(json.loads(player.level_root.root(info, belief, rng).snapshot()))
                before = player.level_root.stats['roots']
                failures = dict(FAILURES)
                decision = player.act(PublicView(info.tick, seat, info, info, [], (), True))
                calls = player.level_root.stats['roots'] - before
                require(f'fair seat{seat} profile{i} decision called B root', calls > 0,
                        f'root calls={calls}, decision={decision}')
                check(f'fair seat{seat} profile{i} no search failure', dict(FAILURES) == failures,
                      f'before={failures} after={dict(FAILURES)}')
                choices.append((decision.action, decision.wait_ticks))
                root_calls += calls
                decisions += 1
            finally:
                player.close()
        check(f'fair seat{seat} actual B root snapshots identical', roots[0] == roots[1], _difference(*roots))
        check(f'fair seat{seat} actual B decisions identical', choices[0] == choices[1], str(choices))
    STATS['fair'] = dict(seats=2, hidden_profiles_per_seat=2, decisions=decisions, decision_root_calls=root_calls)


def main():
    sys.path.insert(0, __file__.rsplit('/bot/', 1)[0])
    gates = sys.argv[1:] or list(GATES)
    FAILS.clear()
    COUNTS.update(checks=0, passed=0)
    STATS.clear()
    try:
        unknown = sorted(set(gates) - set(GATES))
        if unknown:
            raise ValueError(f'unknown gates {unknown}; choose from {GATES}')
        from bot.players.runtime import Runtime
        from bot.levels.scope import digest, install
        rt = Runtime()
        install(rt)  # ALL pilot arms must share this restricted prior before any player construction.
        excluded = {'Clone', 'Earthquake', 'Tornado'}
        require('scope restricted prior installed before players', hasattr(rt, 'levels_original_prior') and
                bool(rt.PRIOR['decks']) and all(not (set(row['cards']) & excluded) for row in rt.PRIOR['decks']))
        require('scope original/restricted digests match receipt',
                digest(rt.levels_original_prior) == rt.levels_scope['original_sha256'] and
                digest(rt.PRIOR) == rt.levels_scope['restricted_sha256'], str(rt.levels_scope))
        require('scope fixed excluded population', rt.levels_scope['original_decks'] == 2925 and
                rt.levels_scope['omitted_decks'] == 425 and rt.levels_scope['original_frequency'] == 69380 and
                rt.levels_scope['omitted_frequency'] == 15371, str(rt.levels_scope))
        receipt = copy.deepcopy(rt.levels_scope)
        require('scope install idempotent', install(rt) == receipt and rt.levels_scope == receipt)
        STATS['scope'] = rt.levels_scope
        lc = _preload(rt, gates)
        for g in gates:
            before = COUNTS['checks']
            try:
                lc.verify()
                if g == 'towers':
                    gate_towers(rt)
                else:
                    globals()[f'gate_{g}'](rt, lc)
            except Exception as ex:
                import traceback
                traceback.print_exc()
                check(f'{g} raised', False, repr(ex)[:500])
            finally:
                lc.verify()
            STATS.setdefault('gate_checks', {})[g] = COUNTS['checks'] - before
    except Exception as ex:
        import traceback
        traceback.print_exc()
        check('gate setup raised', False, repr(ex)[:500])
    print(json.dumps(dict(gates=gates, counts=COUNTS, fails=FAILS, stats=STATS), sort_keys=True), flush=True)
    sys.exit(1 if FAILS else 0)


if __name__ == '__main__':
    main()
