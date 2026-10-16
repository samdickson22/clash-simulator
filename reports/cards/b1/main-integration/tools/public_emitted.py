"""Actual emitted B1 carriers -> frozen sensor -> registered public root.

Single process, output-only receipt. Run only through the independently reviewed
owned staging/launcher. Public roots use documented model defaults; engine
continuations and public-root native restarts are different checks.
"""
import copy
import hashlib
import inspect
import importlib.util
import json
import os
from pathlib import Path
import sys
import traceback
from types import SimpleNamespace

import numpy as np
import review_regressions as h
from differential import entity
from clasher.rl.contract_v5 import TOKEN_FILE, load_pinned_tokens
from clasher.stat_scaling import scale_stat


def require(ok, detail):
    if not ok:
        raise RuntimeError(detail)


def point(seat, x, y):
    return (x, y) if seat == 0 else (18-x, 32-y)


def fixture(cards):
    return h.fresh(tuple(dict.fromkeys((*cards, 'Knight', 'Archers', 'Zap'))))


def native_identity(output):
    actual = Path(h.clasher_core.__file__).resolve()
    expected = Path(output).resolve().parent/'out/clasher_core.abi3.so'
    digest = hashlib.sha256(actual.read_bytes()).hexdigest()
    require(actual == expected.resolve() and digest ==
            '6737c140a4ab2792df22e53190001c58208f4ea27b9fd4d0cb0862e0e2f8161d',
            ('wrong actual imported native', str(actual), digest))
    return dict(file=str(actual), sha256=digest)


def deploy(py, card, seat, x=5.5, y=10.5):
    py.players[seat].hand[0] = card
    py.players[seat].elixir = 10
    first = py.next_entity_id
    require(py.deploy_card(seat, card, h.Position(*point(seat, x, y))), ('deploy', card))
    return [e for k, e in py.entities.items() if k >= first]


def witness(R, fair, py, obj, seat, expected_name, expected_class):
    """Require a known exact identity in a real actor row and a correct root."""
    builder = R.builder
    token, row = builder._entity_row(obj, seat)
    require(row.shape == (32,), ('public entity tensor width changed', row.shape))
    require(token > 1 and builder.token_names[token] == expected_name,
            ('wrong frozen runtime identity', type(obj).__name__, token,
             builder.token_names[token], expected_name))
    require(token == builder.token_id(expected_name), ('wrong token index', token))
    exported = entity(obj)
    require(exported['class'] == expected_class, ('wrong emitted class', exported['class']))
    resolved = []
    for ns, names in exported['public_identity']:
        known = next((builder.token_id(n, namespace=ns) for n in names
                      if builder.token_id(n, namespace=ns) > 1), 1)
        resolved.append(known)
    require(next((t for t in resolved if t > 1), 1) == token,
            ('exporter/sensor identity mismatch', exported['public_identity'], token))
    info = fair.observe(py, builder, seat, ())
    obs = info.packet.observation
    rows = list(zip(obs.entity_ids[obs.entity_mask], obs.entity_features[obs.entity_mask]))
    require(any(int(t) == token and np.allclose(r[:9], row[:9], atol=1e-7, rtol=0)
                for t, r in rows), ('actual actor row missing', obj.id, token))
    kind = ('Troop', 'Building', 'Projectile', 'AreaEffect', 'Entity')[obj.entity_kind]
    template = R.templates.get((token, kind))
    require(template is not None and template['class'] == expected_class,
            ('wrong registered class', expected_name, kind, template))
    root = R.root(info, info.own, np.random.default_rng(914))
    state = json.loads(root.snapshot())
    found = [e for e in state['entities'] if e['owner'] == obj.player_id
             and e['class'] == expected_class
             and abs(e['x']-obj.position.x) < 1e-5
             and abs(e['y']-obj.position.y) < 1e-5]
    require(found, ('wrong reconstructed carrier', obj.id, expected_name))
    for actual in found:
        for key in ('name', 'damage', 'speed', 'range', 'interval', 'load',
                    'attack_select', 'projectile_speed', 'projectile_range'):
            require(actual['stats'].get(key) == template['stats'].get(key),
                    ('root changed canonical mechanics', expected_name, key, actual['stats'].get(key)))
        require(actual['clock']['load'] == template['stats']['load'],
                ('root clock load differs', expected_name, actual['clock']))
        if expected_class == 'HealPulse':
            for key in ('kind', 'heal_per_tick', 'heal_interval', 'buff_name'):
                require(actual['scope'].get(key) == template['scope'].get(key),
                        ('wrong root heal payload', expected_name, key))
        if expected_class == 'TimedExplosive':
            for key in ('bomb_timer', 'bomb_damage', 'bomb_radius', 'freeze_carrier'):
                require(actual.get(key) == template.get(key), ('wrong root bomb payload', expected_name, key))
        if expected_class == 'Projectile':
            speed = round(obj.travel_speed*50)
            require(speed > 0 and template['stats']['speed'] == actual['stats']['speed'] == speed,
                    ('incorrect public projectile native speed', expected_name, speed, actual['stats']['speed']))
            if expected_name == 'ThreeMusketeers':
                require(speed == 1000, 'incorrect independent rework native shot speed')
    clone, reload = root.clone(), h.clasher_core.BattleState(root.snapshot())
    initial_positions = {e['id']:(e['x'],e['y']) for e in found}
    moved = set()
    terminal = set()
    for _ in range(max(3, int(template.get('launch_delay', 0)/.05)+2)):
        clone.step(); reload.step()
        require(json.loads(clone.snapshot()) == json.loads(reload.snapshot()),
                ('public-root native full restart', expected_name))
        if expected_class == 'Projectile':
            after = json.loads(clone.snapshot())['entities']
            remaining = {e['id'] for e in after}
            for e in after:
                if e['id'] in initial_positions and (e['x'],e['y']) != initial_positions[e['id']]:
                    moved.add(e['id'])
            terminal.update(set(initial_positions) - remaining)
    if expected_class == 'Projectile':
        if expected_name == 'MusketeerProjectile':
            # The unchanged C56 template has range=projectile_range=0, so its
            # documented public endpoint is one tile away. Native consumes a
            # one-tile/1000-speed shot in its first object update without moving
            # its stored center first. Prove that positive terminal behavior
            # against zero-speed roots instead of changing the C56 template.
            require(template['stats']['range'] == template['stats']['projectile_range'] == 0,
                    'ordinary shot terminal control no longer uses C56 one-tile default')
            require(set(initial_positions) <= terminal, 'ordinary public shot never reached coarse endpoint')
            stopped_state = copy.deepcopy(state)
            for e in stopped_state['entities']:
                if e['id'] in initial_positions:
                    require(e['shot_target'] is None and e['stats']['speed'] == 1000,
                            'ordinary terminal witness not an untargeted1000-speed shot')
                    distance = ((e['aim'][0]-e['x'])**2+(e['aim'][1]-e['y'])**2)**.5
                    require(abs(distance-1.) < 1e-5, 'ordinary public endpoint not one tile')
                    e['stats']['speed'] = 0
            stopped = h.clasher_core.BattleState(json.dumps(stopped_state))
            for _ in range(max(3, int(template.get('launch_delay', 0)/.05)+2)):
                stopped.step()
            stationary = {e['id']:(e['x'],e['y']) for e in json.loads(stopped.snapshot())['entities']
                          if e['id'] in initial_positions}
            require(stationary == initial_positions, 'zero-speed ordinary control disappeared or moved')
        else:
            require(set(initial_positions) <= moved, ('projected projectile never moved after launch delay', expected_name))
    return dict(id=obj.id, token=int(token), public_name=expected_name, kind=kind,
                emitted_class=expected_class, mechanical_name=exported['stats']['name'],
                selected_name=template['stats']['name'], engine_load=exported['stats']['load'],
                model_load=template['stats']['load'], scope=exported.get('scope'),
                root_ids=[e['id'] for e in found], projected_movement=sorted(moved),
                terminal_projectiles=sorted(terminal)), exported, template, state


def musketeers(R, fair, seat):
    py, cfg = fixture(('ThreeMusketeers', 'Musketeer', 'Minions'))
    bodies = [e for e in deploy(py, 'ThreeMusketeers', seat) if e.entity_kind == 0]
    names = ['ThreeMusketeer_Rework_Character_'+str(i) for i in (1, 2, 3)]
    require([e.card_stats.name for e in bodies] == names, 'formation names/order')
    results = []
    for obj, load in zip(bodies, (700, 650, 700)):
        row, exported, template, _ = witness(R, fair, py, obj, seat, 'ThreeMusketeers', 'Troop')
        require(exported['stats']['load'] == load, ('engine rank load changed', row))
        require(template['stats']['load'] == 700 and
                template['stats']['name'] == names[0], ('noncanonical public default', row))
        require(template['stats'].get('attack_select') == exported['stats'].get('attack_select')
                and template['stats'].get('attack_select'), 'wrong rework body selector')
        require(template['stats']['attack_select'] ==
                dict(range=1.6, damage=float(scale_stat(123, 11)), ground_only=True),
                'incorrect independent rework selector')
        results.append(row)
    # An air target forces actual ranged attacks, so ground bayonet selection
    # cannot accidentally satisfy this projectile witness.
    target = h.spawn(py, 'Minions', 1-seat, *point(seat, 5.5, 15))
    target.hitpoints = 100000
    target.apply_stun(20)
    witnessed = set()
    for _ in range(180):
        py.step()
        for shot in list(py.entities.values()):
            if type(shot).__name__ != 'Projectile' or shot.source_name not in names:
                continue
            if shot.source_name in witnessed:
                continue
            row, exported, template, _ = witness(R, fair, py, shot, seat, 'ThreeMusketeers', 'Projectile')
            require(template['stats']['name'] == names[0], ('wrong rework projectile', row))
            for key in ('damage', 'projectile_speed', 'projectile_range'):
                require(template['stats'][key] == exported['stats'][key], ('projectile stat', key))
            require(template['stats']['damage'] == float(scale_stat(80, 11)) and
                    template['stats']['projectile_speed'] == 1000,
                    'incorrect independent rework shot values')
            require('attack_choice' not in exported and 'select_target' not in exported,
                    'attacker selector leaked to projectile')
            witnessed.add(shot.source_name); results.append(row)
        if len(witnessed) == 3:
            break
    require(witnessed == set(names), ('missing actual rank shots', witnessed))
    # Ordinary Musketeer remains its own identity/template, independent of
    # registration/demo order. Existing B1 selector tests also cover its shots.
    ordinary = h.spawn(py, 'Musketeer', seat, *point(seat, 14.5, 10.5))
    row, _, template, _ = witness(R, fair, py, ordinary, seat, 'Musketeer', 'Troop')
    require(template['stats']['name'] == 'Musketeer' and not template['stats'].get('attack_select'),
            'ordinary Musketeer template changed')
    results.append(row)
    ordinary_target = h.spawn(py, 'Minions', 1-seat, *point(seat, 14.5, 15))
    ordinary_target.hitpoints = 100000; ordinary_target.apply_stun(20)
    for _ in range(160):
        py.step()
        shots = [e for e in py.entities.values() if type(e).__name__ == 'Projectile'
                 and e.source_name == 'Musketeer']
        if shots:
            row, _, template, _ = witness(R, fair, py, shots[0], seat, 'MusketeerProjectile', 'Projectile')
            require(template['stats']['name'] == 'Musketeer', 'ordinary shot template replaced')
            results.append(row); break
    else:
        raise RuntimeError('ordinary projectile negative control unexercised')
    return results


def giant_graph(R, fair, seat):
    py, cfg = fixture(('GoblinGiant',))
    # Burn an ID before deploying: a template's old engine-ID reference cannot
    # accidentally be accepted as a fresh reconstructed parent.
    dummy = h.spawn(py, 'Knight', seat, *point(seat, 14.5, 10.5))
    del py.entities[dummy.id]
    parent = h.spawn(py, 'GoblinGiant', seat, *point(seat, 5.5, 10.5))
    riders = list(parent._rider_mechanic.riders)
    require(len(riders) == 2, 'missing attached graph')
    results = []
    for obj in riders:
        row, _, _, state = witness(R, fair, py, obj, seat, 'SpearGoblinGiant', 'Troop')
        roots = [e for e in state['entities'] if e['owner'] == seat]
        mounts = {e['id']: e for e in roots if e['stats']['name'] == 'GoblinGiant'}
        attached = [e for e in roots if e['stats']['name'] == 'SpearGoblinGiant']
        require(len(mounts) == 1 and len(attached) == 2, 'root graph cardinality')
        require(all(e.get('mount') in mounts for e in attached), 'stale/incompatible root mount')
        require({e.get('rider_rank', 0) for e in attached} == {0, 1}, 'missing distinct root rider ranks')
        row['root_graph'] = [(e['id'], e['mount'], e.get('rider_rank', 0)) for e in attached]
        results.append(row)
    target = h.spawn(py, 'Knight', 1-seat, *point(seat, 5.5, 14.5))
    target.hitpoints = 100000; target.apply_stun(20)
    for _ in range(160):
        py.step()
        shots = [e for e in py.entities.values() if type(e).__name__ == 'Projectile'
                 and e.source_name == 'SpearGoblinGiant']
        if shots:
            results.append(witness(R, fair, py, shots[0], seat,
                                   'SpearGoblinGiantProjectile', 'Projectile')[0])
            break
    else:
        raise RuntimeError('no actual attached rider shot')
    first = py.next_entity_id
    parent.take_damage(parent.hitpoints)
    released = [e for k, e in py.entities.items() if k >= first and e.entity_kind == 0]
    require(len(released) == 2, ('dismount count', len(released)))
    for obj in released:
        row, _, template, _ = witness(R, fair, py, obj, seat, 'SpearGoblin', 'Troop')
        require(not template.get('mount'), 'released child retains template mount')
        results.append(row)
    return results


def healer(R, fair, seat, mirrored=False):
    py, cfg = fixture(('BattleHealer', 'Mirror'))
    if mirrored:
        deploy(py, 'BattleHealer', seat, x=14.5)
        py.entities = {k:e for k,e in py.entities.items() if type(e).__name__ != 'HealPulse'}
        spawned = deploy(py, 'Mirror', seat)
    else:
        spawned = deploy(py, 'BattleHealer', seat)
    caster = next(e for e in spawned if e.entity_kind == 0)
    require(caster.card_stats.level == (12 if mirrored else 11), 'wrong emitted healer level')
    engine_key = 'level12:BattleHealer' if mirrored else 'BattleHealer'
    pulse = next(e for e in spawned if type(e).__name__ == 'HealPulse')
    results = []
    for obj, name, buff, table in ((pulse, 'BattleHealerSpawnHeal', 'BattleHealerSpawnBuff', 'create_areas'),):
        row, exported, template, _ = witness(R, fair, py, obj, seat, name, 'HealPulse')
        require(exported['scope']['buff_name'] == template['scope']['buff_name'] == buff, 'wrong heal buff')
        require(exported['scope']['heal_per_tick'] == cfg[table][engine_key]['scope']['heal_per_tick'],
                'wrong emitted spawn heal payload')
        require(template['scope']['heal_per_tick'] == cfg[table]['BattleHealer']['scope']['heal_per_tick'],
                'wrong plain-root level11 spawn default')
        row.update(engine_level=caster.card_stats.level,
                   engine_heal=exported['scope']['heal_per_tick'], model_heal=template['scope']['heal_per_tick'])
        results.append(row)
    target = h.spawn(py, 'Knight', 1-seat, *point(seat, 5.5, 11.2))
    target.hitpoints = 100000; target.apply_stun(20)
    for _ in range(160):
        py.step()
        hits = [e for e in py.entities.values() if type(e).__name__ == 'HealPulse'
                and getattr(e, 'spell_name', '') == 'BattleHealerHeal']
        if hits:
            require(target.hitpoints < 100000, 'no committed healer hit')
            pulse = next(e for e in hits if e._creation_source_id == caster.id)
            row, exported, template, _ = witness(R, fair, py, pulse, seat, 'BattleHealerHeal', 'HealPulse')
            require(exported['scope']['buff_name'] == template['scope']['buff_name'] == 'BattleHealerAll', 'wrong hit buff')
            require(exported['scope']['heal_per_tick'] == cfg['hit_areas'][engine_key]['scope']['heal_per_tick'],
                    'wrong emitted hit heal payload')
            require(template['scope']['heal_per_tick'] == cfg['hit_areas']['BattleHealer']['scope']['heal_per_tick'],
                    'wrong plain-root level11 hit default')
            row.update(engine_level=caster.card_stats.level,
                       engine_heal=exported['scope']['heal_per_tick'], model_heal=template['scope']['heal_per_tick'])
            results.append(row); break
    else:
        raise RuntimeError('no actual committed on-hit pulse')
    return results


def bomb(R, fair, seat, card):
    from clasher.entities import Building
    py, cfg = fixture((card, 'Cannon'))
    parent = h.spawn(py, card, seat, *point(seat, 5.5, 10.5))
    target = py._spawn_entity(Building, h.Position(*point(seat, 5.5, 11)),
                              1-seat, py.card_loader.get_card('Cannon'))
    require(type(target).__name__ == 'Building' and target.entity_kind == 1,
            'bomb target must be an actual stationary building')
    target.hitpoints = 100000
    parent.take_damage(parent.hitpoints)
    carriers = [e for e in py.entities.values() if type(e).__name__ == 'TimedExplosive']
    require(len(carriers) == 1, ('real death bomb count', card))
    obj = carriers[0]
    row, exported, template, _ = witness(R, fair, py, obj, seat, card, 'TimedExplosive')
    for key in ('bomb_timer', 'bomb_damage', 'bomb_radius', 'freeze_carrier'):
        require(template[key] == exported[key], ('wrong bomb payload', card, key))
    require(template['stats']['name'] == card, ('wrong bomb source', card))
    if card == 'SkeletonBalloon':
        require(obj.death_spawn_count > 0 and card in R.config['bomb_children'], 'missing container children')
    else:
        require(not obj.death_spawn_count and exported['bomb_damage'] > 0, 'wrong explosion semantics')
    native = h.clasher_core.BattleState(h.snapshot(py, cfg))
    py_control = py.clone()
    del py_control.entities[obj.id]
    info = fair.observe(py, R.builder, seat, ())
    model = R.root(info, info.own, np.random.default_rng(915))
    model_start = json.loads(model.snapshot())
    model_bomb = next(e for e in model_start['entities'] if e['class'] == 'TimedExplosive')
    model_target = next(e for e in model_start['entities'] if e['owner'] == 1-seat
                        and e['stats']['name'] == 'Cannon')
    control_start = copy.deepcopy(model_start)
    control_start['entities'] = [e for e in control_start['entities'] if e['id'] != model_bomb['id']]
    model_control = h.clasher_core.BattleState(json.dumps(control_start))
    expected_children = obj.death_spawn_count
    model_children = cfg.get('bomb_children', {}).get(card, [])
    require(len(model_children) == expected_children, 'container child payload count')
    before_ids = set(py.entities)
    before_model_ids = {e['id'] for e in model_start['entities']}
    ticks = int((max(obj.explosion_timer, model_bomb['bomb_timer'])+.6)/py.dt)+5
    for elapsed in range(ticks):
        py.step(); native.step(); py_control.step(); model.step(); model_control.step()
        h.audited_state(py, native, cfg)
        actual = json.loads(model.snapshot())
        live_done = obj.id not in py.entities or not py.entities[obj.id].is_alive
        model_done = not any(e['id'] == model_bomb['id'] and e['alive'] for e in actual['entities'])
        if live_done and model_done:
            break
    require(live_done and model_done, ('timed carrier never executed/removed', card))
    live_children = [e for k,e in py.entities.items() if k not in before_ids and e.entity_kind == 0]
    children = [e for e in actual['entities'] if e['id'] not in before_model_ids and e['entity_kind'] == 0]
    require(len(live_children) == len(children) == expected_children,
            ('actual container release count', card, len(live_children), len(children), expected_children))
    if expected_children:
        expected = model_children[0]['stats']
        require(all(e['stats']['name'] == expected['name'] and
                    e['stats']['max_hp'] == expected['max_hp'] and e['stats']['damage'] == expected['damage']
                    for e in children), 'wrong released child mechanics')
    # A container releases children with deployment delay; its own bomb has
    # zero damage. First assert the birth payload above, then require their
    # actual post-deploy damage against the same no-container control.
    impact_tick = 0
    for impact_tick in range(81):
        after_target = next((e['hp'] for e in actual['entities'] if e['id'] == model_target['id']), 0)
        control_hp = next((e['hp'] for e in json.loads(model_control.snapshot())['entities']
                           if e['id'] == model_target['id']), 0)
        if py_control.entities[target.id].hitpoints > target.hitpoints+1 and control_hp > after_target+1:
            break
        if not expected_children or impact_tick == 80:
            raise RuntimeError(('live/public bomb payload damage absent against no-bomb controls', card))
        py.step(); native.step(); py_control.step(); model.step(); model_control.step()
        h.audited_state(py, native, cfg)
        actual = json.loads(model.snapshot())
    h.continuation(py, native, cfg, ticks=6)
    row.update(execution_tick=elapsed+1, actual_children=len(live_children), model_children=len(children),
               payload_damage_ticks=impact_tick, model_damage_delta=control_hp-after_target)
    return row


def rejected_controls(R, fair, seat):
    py, _ = fixture(('ThreeMusketeers',))
    body = next(e for e in deploy(py, 'ThreeMusketeers', seat) if e.entity_kind == 0)

    def rejected(fn, expected):
        try:
            fn()
        except RuntimeError as exc:
            require(expected in str(exc), ('control failed for unrelated reason', expected, str(exc)))
            return str(exc)
        raise RuntimeError(('invalid public pipeline was accepted', expected))

    raw = copy.deepcopy(body.card_stats._raw_entry)
    raw['summonCharacterData'].pop('publicIdentity', None)
    bad = copy.copy(body)
    bad.card_stats = SimpleNamespace(name=body.card_stats.name, _raw_entry=raw,
                                    summon_character_data=raw['summonCharacterData'])
    wrong_token = rejected(lambda: witness(R, fair, py, bad, seat, 'ThreeMusketeers', 'Troop'),
                           'wrong frozen runtime identity')
    key = (R.builder.token_id('ThreeMusketeers'), 'Troop')
    saved = R.templates[key]
    try:
        R.templates[key] = R.templates[(R.builder.token_id('Musketeer'), 'Troop')]
        wrong_template = rejected(lambda: musketeers(R, fair, seat), 'noncanonical public default')
    finally:
        R.templates[key] = saved
    projectile_key = (R.builder.token_id('ThreeMusketeers'), 'Projectile')
    saved_shot = R.templates[projectile_key]
    try:
        broken_shot = copy.deepcopy(saved_shot)
        broken_shot['stats']['speed'] = 0
        R.templates[projectile_key] = broken_shot
        zero_speed = rejected(lambda: musketeers(R, fair, seat), 'incorrect public projectile native speed')
    finally:
        R.templates[projectile_key] = saved_shot
    had_root = 'root' in vars(R)
    saved_root = R.root

    def corrupted_root(*args, **kwargs):
        state = json.loads(saved_root(*args, **kwargs).snapshot())
        for e in state['entities']:
            if e['stats']['name'].startswith('ThreeMusketeer_Rework_Character_'):
                e['stats']['load'] = 650
                e['clock']['load'] = 650
        return h.clasher_core.BattleState(json.dumps(state))

    try:
        R.root = corrupted_root
        wrong_root = rejected(lambda: witness(R, fair, py, body, seat, 'ThreeMusketeers', 'Troop'),
                              'root changed canonical mechanics')
    finally:
        if had_root:
            R.root = saved_root
        else:
            del R.root
    return dict(wrong_token=wrong_token, wrong_template=wrong_template, zero_speed=zero_speed, wrong_root=wrong_root)


def run(R, fair, output):
    imported_native = native_identity(output)
    frozen_bytes = Path(TOKEN_FILE).read_bytes()
    pinned = load_pinned_tokens()
    require(hashlib.sha256(frozen_bytes).hexdigest() ==
            '5e20ce085662869fb4f0b56fee7851007b4c146d32e56b97da05a3058cf1b4f0',
            'frozen vocabulary bytes changed')
    require(tuple(R.builder.token_names) == pinned.tokens, 'actual runtime vocabulary differs')
    require(len(pinned.tokens) == 360 and R.builder.token_id('ThreeMusketeers') == 326,
            'frozen token IDs/count changed')
    require(R.builder.card_stat_features.shape == (360, 57), 'frozen card tensor dimensions changed')
    from bot.players.runtime import PINS
    runtime = Path(os.environ['CLASHER_ROOT'])
    model_paths = {'v1': runtime/'main02.pt', 'r3a': runtime/'R3a.pt'}
    model_hashes = {key: hashlib.sha256(path.read_bytes()).hexdigest() for key,path in model_paths.items()}
    require(model_hashes == {key:PINS[key+'_sha256'] for key in model_paths}, 'frozen model bytes changed')
    # An explicit alias applies only in its declared public namespace, and the
    # new path must not turn arbitrary unnamed payloads into a known card.
    unknown = SimpleNamespace(card_stats=SimpleNamespace(
        name='B1UnregisteredControl', _raw_entry={}))
    require(R.builder._runtime_entity_token_id(unknown, 'troop_body') == 1,
            'unknown negative control acquired an identity')
    isolated = SimpleNamespace(card_stats=SimpleNamespace(
        name='B1UnregisteredControl', _raw_entry={
            'summonCharacterData': {'publicIdentity': {'troop_body': 'ThreeMusketeers'}}}))
    require(R.builder._runtime_entity_token_id(isolated, 'troop_body') == 326 and
            R.builder._runtime_entity_token_id(isolated, 'projectile') == 1,
            'public alias leaked across namespaces')
    results = []
    for seat in (0, 1):
        for name, fn in (('rework-bodies-shots', musketeers), ('attached-rider-graph', giant_graph),
                         ('spawn-hit-heal', healer),
                         ('mirrored-spawn-hit-heal', lambda r,f,s: healer(r,f,s,True)),
                         ('giant-skeleton-bomb', lambda r,f,s: bomb(r,f,s,'GiantSkeleton')),
                         ('skeleton-balloon-container', lambda r,f,s: bomb(r,f,s,'SkeletonBalloon')),
                         ('wrong-token-template-root-controls', rejected_controls)):
            try:
                row = dict(name=name, seat=seat, ok=True, witnesses=fn(R, fair, seat))
            except Exception:
                row = dict(name=name, seat=seat, ok=False, error=traceback.format_exc())
            results.append(row); print(json.dumps(row), flush=True)
    require(Path(TOKEN_FILE).read_bytes() == frozen_bytes, 'vocabulary mutated')
    require(model_hashes == {key:hashlib.sha256(path.read_bytes()).hexdigest() for key,path in model_paths.items()},
            'model bytes mutated during public phase')
    require(native_identity(output) == imported_native, 'actual imported native changed during public phase')
    builder_path = Path(inspect.getfile(type(R.builder))).resolve()
    report = dict(total=len(results), passed=sum(r['ok'] for r in results), tests=results,
                  builder_type=type(R.builder).__module__+'.'+type(R.builder).__qualname__,
                  builder_file=str(builder_path), builder_sha256=hashlib.sha256(builder_path.read_bytes()).hexdigest(),
                  vocabulary_file=str(TOKEN_FILE), vocabulary_file_sha256=hashlib.sha256(frozen_bytes).hexdigest(),
                  vocabulary_sha256=pinned.sha256, vocabulary_count=len(pinned.tokens),
                  card_feature_shape=list(R.builder.card_stat_features.shape),
                  model_input_files={key:str(path.resolve()) for key,path in model_paths.items()},
                  model_input_sha256=model_hashes,
                  imported_native=imported_native,
                  fair_player_file=str(Path(fair.__file__).resolve()),
                  note='Actual emitted identity/template/public-root witnesses; 700ms coarse rework load default. Public roots do not reconstruct private clocks/targets or exact live rank identity.')
    with open(output, 'x') as f:
        json.dump(report, f, indent=2)
    require(report['passed'] == report['total'] == 14, report)


if __name__ == '__main__':
    native_identity(sys.argv[1])
    import c56_controller
    import fair_player
    from bot.cards.scope import _widened
    from quickwin_resources import cached_resources
    cards = tuple(sorted(set(c56_controller.CARDS) | {
        'ThreeMusketeers', 'Musketeer', 'GoblinGiant', 'BattleHealer', 'Mirror', 'Clone',
        'GiantSkeleton', 'SkeletonBalloon'}))
    with _widened(cards):
        resources = cached_resources(fair_player.Resources)()
    failures = []
    try:
        run(resources, fair_player, sys.argv[1])
    except Exception:
        failures.append(traceback.format_exc())
    owner_path = Path(__file__).with_name('probe_b1_public_root.py')
    spec = importlib.util.spec_from_file_location('b1_public_root_owner', owner_path)
    owner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owner)
    try:
        owner.run(resources, fair_player, Path(sys.argv[1]).with_name('public-owner.json'))
    except Exception:
        failures.append(traceback.format_exc())
    if failures:
        raise SystemExit('\n'.join(failures))
