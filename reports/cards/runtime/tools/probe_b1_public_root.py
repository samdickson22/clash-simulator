"""Scoped public graph/level regressions, run in B1's ONE admitted public phase.

Entrypoint: run(R, fair_player_module, output_path), reusing the same widened
cached Resources as public_emitted.run. Include Clone in the test card scope.
No startup, launcher, subprocess, private state input to production roots, or
outside writes. OUTPUT must be fresh; per-level caches remain beside it.
"""
from __future__ import annotations

import ast
import copy
from dataclasses import replace
import hashlib
import inspect
import json
import math
from pathlib import Path
import traceback
from types import SimpleNamespace

import numpy as np


def require(ok, detail):
    if not ok:
        raise AssertionError(detail)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def graph(state):
    entities = state['entities']
    byid = {e['id']: e for e in entities}
    require(len(byid) == len(entities), 'duplicate root IDs')
    used = set()
    for e in entities:
        if e['class'] != 'Troop' or e['stats']['name'] != 'SpearGoblinGiant':
            continue
        parent = byid.get(e.get('mount'))
        require(parent is not None and parent['class'] == 'Troop' and
                parent['stats']['name'] == 'GoblinGiant' and parent['owner'] == e['owner'],
                ('wrong/missing reconstructed parent', e['id'], e.get('mount')))
        # Rust serde omits rank zero; that documented default is a real rank,
        # while an absent mount still fails the independent parent checks.
        slot = (parent['id'], e.get('rider_rank', 0))
        require(slot[1] in (0, 1) and slot not in used, ('wrong/duplicate public rank', slot))
        used.add(slot)
    return used


def change_rows(info, order=None, remove_token=None):
    """Only public packet rows are changed; no ground-truth IDs enter a root."""
    obs = info.packet.observation
    ids, rows, mask = obs.entity_ids.copy(), obs.entity_features.copy(), obs.entity_mask.copy()
    active = np.flatnonzero(mask)
    if order is not None:
        order = active[np.asarray(order)]
        ids[active], rows[active] = ids[order], rows[order]
    if remove_token is not None:
        mask &= ids != remove_token
    obs = replace(obs, entity_ids=ids, entity_features=rows, entity_mask=mask)
    return replace(info, packet=replace(info.packet, observation=obs))


def fixture(seat, *, multiple=False, coincident=False):
    from differential import initial, Position
    cards = ('GoblinGiant', 'ThreeMusketeers', 'BattleHealer', 'Clone', 'Knight', 'Archers', 'Zap', 'Cannon')
    py = initial(seed=880610, cards=cards)
    def spawn(card, owner, x, y):
        if seat == 1:
            x, y = 18-x, 32-y
        first = py.next_entity_id
        py._spawn_unit_at_position(Position(x, y), owner, py.card_loader.get_card(card),
                                  deploy_delay_override=0., snap_to_valid=False)
        return py.entities[first]
    # Different source IDs, excluded from the public board. This proves no
    # accidental equality with cached isolated template IDs is required.
    dummy = spawn('Knight', seat, 14., 11.)
    del py.entities[dummy.id]
    parent = spawn('GoblinGiant', seat, 5.5, 10.5)
    if multiple:
        spawn('GoblinGiant', seat, 5.5 if coincident else 11.5, 10.5)
    for player in py.players:
        player.hand = ['GoblinGiant', 'Clone', 'Knight', 'Archers']
        player.cycle_queue.clear()
        player.cycle_queue.extend(['Zap', 'BattleHealer', 'ThreeMusketeers', 'Knight'])
        player.elixir = 10.
    return py, parent, spawn


def native_restart(root, ticks=4):
    import clasher_core
    a, b = root.clone(), clasher_core.BattleState(root.snapshot())
    for _ in range(ticks):
        a.step(); b.step()
        require(a.snapshot() == b.snapshot(), 'native full snapshot continuation/reload differs')
        graph(json.loads(a.snapshot()))


def projectile_motion(root):
    """Independent positive native movement, with a zero-speed control.

    Full native restart equality alone would also accept stationary shots.
    Require the actual reconstructed rework shot to travel one tile in50ms.
    """
    import clasher_core
    before = json.loads(root.snapshot())
    shots = [e for e in before['entities'] if e['class'] == 'Projectile' and
             e['stats']['name'] == 'ThreeMusketeer_Rework_Character_1']
    require(len(shots) == 1, 'missing actual rework projectile movement witness')
    shot = shots[0]
    require(shot['stats']['speed'] == shot['stats']['projectile_speed'] == 1000,
            'native rework movement speed is not normalized1000')
    moving = root.clone()
    moving.step()
    after = next((e for e in json.loads(moving.snapshot())['entities'] if e['id'] == shot['id']), None)
    require(after is not None, 'rework movement fixture shot disappeared before positive witness')
    distance = math.hypot(after['x']-shot['x'], after['y']-shot['y'])
    require(.99 < distance < 1.01, ('rework native shot did not move one tile/50ms', distance))
    zero_payload = copy.deepcopy(before)
    next(e for e in zero_payload['entities'] if e['id'] == shot['id'])['stats']['speed'] = 0
    zero = clasher_core.BattleState(json.dumps(zero_payload))
    zero.step()
    stopped = next(e for e in json.loads(zero.snapshot())['entities'] if e['id'] == shot['id'])
    zero_distance = math.hypot(stopped['x']-shot['x'], stopped['y']-shot['y'])
    require(zero_distance < .002, ('zero-speed negative control moved', zero_distance))
    return dict(speed=1000, distance=distance, zero_speed_distance=zero_distance,
                start=[shot['x'],shot['y']], finish=[after['x'],after['y']])


def graph_case(R, fair, seat, multiple=False, coincident=False, clone=False):
    from differential import Position
    py, parent, _ = fixture(seat, multiple=multiple, coincident=coincident)
    if clone:
        py.players[seat].hand[0] = 'Clone'
        require(py.deploy_card(seat, 'Clone', Position(parent.position.x, parent.position.y)), 'actual Clone failed')
    info = fair.observe(py, R.builder, seat, ())
    count = int(info.packet.observation.entity_mask.sum())
    outputs = []
    for order in (list(range(count)), list(reversed(range(count)))):
        changed = change_rows(info, order)
        root = R.root(changed, changed.own, np.random.default_rng(11))
        state = json.loads(root.snapshot())
        slots = graph(state)
        expected = (2 if multiple or clone else 1) * 2
        require(len(slots) == expected, ('graph lost/invented riders', len(slots), expected))
        # Row IDs vary on reorder; compare observable geometry/rank relations.
        byid = {e['id']: e for e in state['entities']}
        links = sorted((e['owner'], round(e['x'], 5), round(e['y'], 5),
                        round(byid[e['mount']]['x'], 5), round(byid[e['mount']]['y'], 5), e.get('rider_rank', 0))
                       for e in state['entities'] if e.get('mount') is not None)
        outputs.append(links)
        native_restart(root)
    require(outputs[0] == outputs[1], 'public geometry/rank result depends on distinguishable row order')
    # Parent truncation must not quietly reuse demo IDs or synthesize a mount.
    from public_root import PublicGraphError
    bad = change_rows(info, remove_token=R.builder.token_id('GoblinGiant', namespace='troop_body'))
    try:
        R.root(bad, bad.own, np.random.default_rng(11))
    except PublicGraphError as ex:
        require(ex.report['unsupported'], 'missing unsupported graph count')
    else:
        raise AssertionError('missing-parent negative control accepted')
    return dict(seat=seat, multiple=multiple, coincident=coincident, clone=clone,
                observed_riders=len(outputs[0]), reorder=True, missing_parent_rejected=True)


def boundary_case(R, fair, seat):
    from bot.levels.root import ExactLevelRoot
    points = ((.499,.499), (17.501,.499), (.499,31.501), (17.501,31.501),
              (.499,10.5), (17.501,10.5), (8.5,.499), (8.5,31.501))
    rt = SimpleNamespace(R=R, pins={})
    wrapper = ExactLevelRoot(rt, {}, lambda card: 11, 11, 11, force=True)
    witnesses = []
    for point in points:
        for carry in (False, True):
            py, old, spawn = fixture(seat)
            # Fresh source graph at an actual character-spawn clamp boundary;
            # remove the earlier graph rather than fabricating extra public rows.
            del py.entities[old.id]
            for rider in old._rider_mechanic.riders:
                del py.entities[rider.id]
            parent = spawn('GoblinGiant', seat, *point)
            if carry:
                # Actual engine hook may place riders outside arena limits;
                # the frozen sensor performs the documented public clipping.
                parent._rider_mechanic.carry(parent, parent.native_facing_units())
            info = fair.observe(py, R.builder, seat, ())
            for consumer in (R, wrapper):
                root = consumer.root(info, info.own, np.random.default_rng(15))
                require(len(graph(json.loads(root.snapshot()))) == 2, 'valid clamped graph rejected/lost')
                native_restart(root, ticks=2)
            witnesses.append(dict(point=point, carry=carry, boundary_report=dict(R.public_graph_report)))
    return dict(seat=seat, boundary_graphs=len(witnesses), plain_and_level=True, witnesses=witnesses)


def level_case(R, fair, output, seat, level):
    from bot.levels.configs import LevelConfigs
    from bot.levels.root import ExactLevelRoot
    from differential import Position
    cards = ('GoblinGiant', 'ThreeMusketeers', 'BattleHealer', 'Clone', 'Knight', 'Archers', 'Zap', 'Cannon')
    rt = SimpleNamespace(R=R, pins={})
    lc = LevelConfigs(rt, cache=Path(output).with_suffix('.level-cache'))
    for lv in sorted({11, level}):
        lc.build(lv, cards=cards)
    wrapper = ExactLevelRoot(rt, {c:level for c in cards}, lambda c: level if c in cards else 11,
                             11, 11, lc=lc, force=True)
    py, parent, spawn = fixture(seat)
    first = py.next_entity_id
    py.players[seat].hand[0] = 'ThreeMusketeers'
    require(py.deploy_card(seat, 'ThreeMusketeers', Position(12.5 if seat == 0 else 5.5,
                                                           10.5 if seat == 0 else 21.5)), '3M deployment')
    member = next(e for e in py.entities.values() if e.card_stats is not None and
                  e.card_stats.name == 'ThreeMusketeer_Rework_Character_1')
    member._create_projectile(None, py, target_position=Position(member.position.x,
                              member.position.y+(5 if seat == 0 else -5)))
    healer = spawn('BattleHealer', seat, 8.5, 10.5)
    on_hit = next(m for m in healer.mechanics if type(m).__name__ == 'AreaEffectOnHit')
    on_hit.on_attack_hit(healer, healer)
    py.players[seat].elixir = 10.
    py.players[seat].hand[0] = 'Cannon'
    building_id = py.next_entity_id
    require(py.deploy_card(seat, 'Cannon', Position(14.5 if seat == 0 else 3.5,
                                                   10.5 if seat == 0 else 21.5)), 'Cannon deployment')
    cannon = py.entities[building_id]
    cannon._create_projectile(None, py, target_position=Position(cannon.position.x,
                              cannon.position.y + (5 if seat == 0 else -5)))
    # Public own-HUD fixture for a future legal Clone, independent of the
    # nine-elixir deployment used to obtain actual rework observation rows.
    py.players[seat].elixir = 10.
    py.players[seat].hand = ['Clone', 'Knight', 'Archers', 'Zap']
    py.players[seat].next_card_refill_cooldown_ms = 0
    info = fair.observe(py, R.builder, seat, ())
    payload = json.loads(wrapper.payload(info, info.own, np.random.default_rng(12)))
    graph(payload)
    rework = [e for e in payload['entities'] if e['class'] == 'Troop' and
              e['stats']['name'].startswith('ThreeMusketeer_Rework_Character')]
    require(len(rework) == 3 and all(e['stats']['name'] == 'ThreeMusketeer_Rework_Character_1' and
            e['clock']['load'] == e['stats']['load'] == 700 and e['stats'].get('attack_select') for e in rework),
            'wrong explicit level public rework default')
    pulses = [e for e in payload['entities'] if e['class'] == 'HealPulse']
    require({e['spell_name'] for e in pulses} == {'BattleHealerSpawnHeal', 'BattleHealerHeal'},
            'level wrapper conflated healer public identities')
    for e in pulses:
        table = 'create_areas' if e['spell_name'] == 'BattleHealerSpawnHeal' else 'hit_areas'
        expected = lc.entry('BattleHealer', level)['tables'][table]
        expected = next(v for k,v in expected.items() if k.endswith('BattleHealer'))
        require(e['scope']['heal_per_tick'] == expected['scope']['heal_per_tick'] and
                e['scope']['buff_name'] == expected['scope']['buff_name'], 'wrong level pulse payload')
    shots = [e for e in payload['entities'] if e['class'] == 'Projectile' and e['stats']['name'] == 'Cannon']
    expected_cannon = lc.entry('Cannon', level)['card']['units'][seat][0]
    require(len(shots) == 1 and shots[0]['stats']['damage'] == expected_cannon['stats']['damage'] and
            shots[0]['stats']['max_hp'] == 1 and shots[0]['hp'] == 1,
            'Building-shot level fallback changed damage or projectile HP')
    giants = [e for e in payload['entities'] if e['stats']['name'] == 'GoblinGiant']
    prototype = giants[0]['clone_template']
    require(len(prototype['clone_children']) == 2 and all(e['mount'] == prototype['id']
            for e in prototype['clone_children']), 'level Clone prototype is not a closed static graph')
    require(prototype['stats']['damage'] == giants[0]['stats']['damage'] and
            prototype['stats']['payload_key'] == giants[0]['stats']['payload_key'],
            'Clone prototype retains old level damage/payload')
    import clasher_core
    root = clasher_core.BattleState(json.dumps(payload))
    motion = dict(level=projectile_motion(root), plain=projectile_motion(
                  R.root(info, info.own, np.random.default_rng(12))))
    native_restart(root)
    # Apply an actual future Clone to this public root and check newly allocated
    # links, with no private graph information passed from the fixture.
    require(root.apply_action(seat, 'Clone', giants[0]['x'], giants[0]['y']), 'public-root future Clone failed')
    state = json.loads(root.snapshot())
    require(len(graph(state)) == 4, 'future public Clone lost/doubled attached graph')
    native_restart(root)
    return dict(seat=seat, level=level, rework_bodies=len(rework), pulse_payloads=len(pulses),
                clone_graph=True, native_continuation=True, projectile_motion=motion, wrapper_stats=wrapper.stats)


def c56_unchanged(R, fair, seat):
    # Compile the current production root with just the new repair call removed.
    # This is a byte-level isolation control of the added graph policy, not a
    # substitute for B1's separate old-vs-new source C56 acceptance gate.
    import textwrap
    source = textwrap.dedent(inspect.getsource(fair.Resources.root))
    tree = ast.parse(source)
    tree.body[0].body = [n for n in tree.body[0].body if not (
        isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and
        isinstance(n.value.func, ast.Attribute) and n.value.func.attr == 'repair_public_graph')]
    namespace = dict(fair.Resources.root.__globals__)
    namespace['clasher_core'] = SimpleNamespace(BattleState=lambda payload: payload)
    exec(compile(tree, '<graph-policy-disabled-control>', 'exec'), namespace)
    disabled = namespace['root']
    enabled_ns = dict(namespace)
    exec(compile(ast.parse(source), '<production-root-payload>', 'exec'), enabled_ns)
    from differential import initial, Position
    py = initial(seed=880611, cards=('Knight', 'Archers', 'Fireball', 'Giant'))
    py.players[seat].elixir = 10.
    require(py.deploy_card(seat, 'Knight', Position(5.5, 10.5 if seat == 0 else 21.5)), 'C56 deployment')
    info = fair.observe(py, R.builder, seat, ())
    a = disabled(R, info, info.own, np.random.default_rng(13))
    b = enabled_ns['root'](R, info, info.own, np.random.default_rng(13))
    require(a == b, 'unrelated C56 public root payload bytes changed by graph repair')
    return dict(seat=seat, raw_payload_sha256=hashlib.sha256(a.encode()).hexdigest(), byte_equal=True)


def run(R, fair, output):
    """Reuse B1's widened Resources build; exclusive receipt + adjacent cache."""
    import public_root
    from bot.levels import root as level_root, configs
    required = {'GoblinGiant', 'ThreeMusketeers', 'BattleHealer', 'Clone'}
    require(required <= R.config['cards'].keys(), ('missing scoped test cards', required-R.config['cards'].keys()))
    paths = {m.__name__: Path(m.__file__).resolve() for m in (fair, public_root, level_root, configs)}
    before = {k:digest(v) for k,v in paths.items()}
    results = []
    tests = []
    for seat in (0, 1):
        for label, flags in (('single', {}), ('multiple', {'multiple':True}),
                             ('coincident', {'multiple':True, 'coincident':True}), ('cloned-rows', {'clone':True})):
            tests.append((f'{seat}/graph/{label}', lambda s=seat,f=flags: graph_case(R, fair, s, **f)))
        for level in (11, 9):
            tests.append((f'{seat}/level/{level}', lambda s=seat,l=level: level_case(R, fair, output, s, l)))
        tests.append((f'{seat}/boundaries', lambda s=seat: boundary_case(R, fair, s)))
        tests.append((f'{seat}/c56-bytes', lambda s=seat: c56_unchanged(R, fair, s)))
    for name, fn in tests:
        try:
            row = dict(name=name, ok=True, details=fn())
        except Exception:
            row = dict(name=name, ok=False, error=traceback.format_exc())
        results.append(row)
        print(json.dumps(row), flush=True)
    require(before == {k:digest(v) for k,v in paths.items()}, 'consumer source changed during public phase')
    report = dict(total=len(results), passed=sum(x['ok'] for x in results), tests=results,
                  consumer_files={k:str(v) for k,v in paths.items()}, consumer_sha256=before,
                  note='Public geometry/default model only; no hidden rank, clocks, targets, IDs or clone-state recovery. C56 graph-disabled byte control is separate from B1 full source gates.')
    with open(output, 'x') as stream:
        json.dump(report, stream, indent=2)
    require(report['passed'] == report['total'] == 16, report)
