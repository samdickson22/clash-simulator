"""Single-process combined-source probes; writes only the requested JSON receipt.

Inputs sit in RUN/tools/{batchA,b1}; no subprocesses or source mutation.
Native restart comparisons cover every serialized field; cross-engine checks
retain the B1 audit's disclosed representation limitations.
"""
import importlib.util
import json
from pathlib import Path
import sys
import traceback

TOOLS = Path(__file__).resolve().parent


def load(name, path):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


b1 = load('b1_review', TOOLS / 'review_regressions.py')
paths = load('first_update_paths', TOOLS / 'first_update_paths.py')
a = load('a_scen', TOOLS / 'batchA/probe_native_scen.py')
# Each module must resolve its own scenario helpers (their names are identical).
sys.modules.pop('scenarios', None)
b = load('b_scen', TOOLS / 'b1/probe_native_scen.py')
RESULTS = []


def require(ok, detail):
    if not ok:
        raise RuntimeError(detail)


def record(name, fn):
    try:
        detail = fn()
        row = dict(name=name, ok=True, detail=detail)
    except Exception:
        row = dict(name=name, ok=False, error=traceback.format_exc())
    RESULTS.append(row)
    print(json.dumps(row), flush=True)


def path_case(name, case):
    row = paths.one(name, case)
    require(row.get('native') == 'ok' and row.get('first_mismatch') is None, row)
    require(all(x[3] and x[4] for x in row['actions']), row)
    require(row.get('victim_death') is not None, ('missing death witness', row))
    side = case['victim'][0]
    ctl = dict(case, script=[], setup=[op for op in case['setup']
               if not (op[0] in ('deploy', 'move', 'hp') and op[1] != side)])
    # A script-created victim must also exist in the decay-only control.
    for _, owner, card, tile in case['script']:
        if (owner, card) == case['victim']:
            ctl['setup'] = ctl['setup'] + [('deploy', owner, card, tile), ('step', 25)]
    if name == 'tower_shot_drill':
        ctl['disable_towers'] = True
    control = paths.one(name + '/control', ctl, control=True)
    require(control.get('native') == 'ok', control)
    require(control.get('victim_death') is None or control['victim_death'] > row['victim_death'],
            ('effect did not precede decay-only control', row, control))
    row['control_death'] = control.get('victim_death')
    return row


def lockstep(module, card, kind, scenario):
    row = module.one(card, kind, scenario)
    require(row.get('native') == 'ok' and row.get('first_mismatch') is None, row)
    require(all(x[3] and x[4] for x in row['deploys']), row)
    return row


def nested(seat, periodic):
    """Real Witch waves / frozen Tombstone death beside a live GG graph.

    Observe inside Python's synchronous callback, then check the new native
    child and every rider position/link at the tick boundary and restart there.
    Mounted children stay attack-capable but absent from movement/body queries.
    """
    cards = ('GoblinGiant', 'Tombstone', 'Witch', 'Freeze', 'Rocket', 'Knight')
    py, cfg = b1.fresh(cards)
    point = lambda x, y: (x, y) if seat == 0 else (18-x, 32-y)
    victim_name = 'Witch' if periodic else 'Tombstone'
    if periodic:
        py.players[seat].hand[0] = 'Witch'
        require(py.deploy_card(seat, 'Witch', b1.Position(*point(.5, 1.5))), 'Witch deploy')
        for _ in range(37):
            py.step()
        victim = next(e for e in py.entities.values() if getattr(e.card_stats, 'name', '') == 'Witch')
        victim.position = b1.Position(*point(.5, .5))
        giant = b1.spawn(py, 'GoblinGiant', seat, *point(1.5, 1.5))
    else:
        py.players[seat].hand[0] = 'Tombstone'
        require(py.deploy_card(seat, 'Tombstone', b1.Position(*point(4.5, 10.5))), 'Tombstone deploy')
        for _ in range(25):
            py.step()
        victim = next(e for e in py.entities.values() if getattr(e.card_stats, 'name', '') == 'Tombstone')
        giant = b1.spawn(py, 'GoblinGiant', seat, *point(5.5, 10.5))
        # Freeze affects the parent before Rocket's damage callback emits children.
        for side, card in ((1-seat, 'Freeze'), (1-seat, 'Rocket')):
            py.players[side].hand[0] = card
            py.players[side].elixir = 10
            require(py.deploy_card(side, card, victim.position), (card, 'deploy'))
    native = b1.clasher_core.BattleState(b1.snapshot(py, cfg))
    events = []
    original = py._first_update_spawned

    def observe(child, **kw):
        riders = [e for e in py.entities.values() if getattr(e, '_rider_mount', None) is giant and e.is_alive]
        require(giant.is_alive and len(riders) == 2, 'GG graph missing at nested callback')
        before = (child.position.x, child.position.y)
        freeze = float(getattr(child, '_freeze_target_pause_remaining', 0))
        original(child, **kw)
        events.append(dict(tick=py.tick, id=child.id, before=before,
                           after=(child.position.x, child.position.y), freeze=freeze,
                           hidden=sorted(kw.get('hidden', ())), collide=kw.get('collide', True),
                           riders=[e.id for e in riders]))

    py._first_update_spawned = observe
    restarted = False
    for _ in range(160 if not periodic else 12):
        py.step(); native.step()
        actual = b1.audited_state(py, native, cfg)
        # Digest includes x/y; require explicit attached-graph positions too.
        rows = {e['id']: e for e in actual['entities']}
        for rider in giant._rider_mechanic.riders:
            require(rows[rider.id].get('mount') == giant.id, ('mount link', rider.id))
            require((rows[rider.id]['x'], rows[rider.id]['y']) ==
                    (rider.position.x, rider.position.y), ('rider carry position', rider.id))
        if events and not restarted:
            # Remove the observer closure before cloning Python; the continuation
            # must have its own battle-bound callback and no test closure state.
            del py._first_update_spawned
            b1.continuation(py, native, cfg, ticks=12)
            py._first_update_spawned = observe
            restarted = True
    require(events and restarted, 'no synchronous emission/restart witness')
    if periodic:
        require(any(len(e['hidden']) == 2 for e in events), ('missing sibling hiding', events))
    else:
        require(not victim.is_alive and any(not e['collide'] for e in events), ('no death first update', events))
        require(any(e['freeze'] > 0 and e['before'] == e['after'] for e in events),
                ('missing inherited Freeze before first move', events))
    return dict(seat=seat, periodic=periodic, events=events)


def public_export():
    from clasher.rl.structured_obs import StructuredObservationBuilder
    from types import SimpleNamespace
    cards = ('BattleHealer', 'Mirror', 'GoblinGiant', 'ThreeMusketeers', 'GiantSkeleton', 'Vines', 'Rocket', 'Knight')
    py, cfg = b1.fresh(cards)
    for card in cards:
        if card not in ('Mirror', 'Vines', 'Rocket'):
            b1.spawn(py, card, 0, 5.5, 10.5)
    skeleton = next(e for e in py.entities.values() if getattr(e.card_stats, 'name', '') == 'GiantSkeleton')
    skeleton.take_damage(skeleton.hitpoints)
    native = b1.clasher_core.BattleState(b1.snapshot(py, cfg))
    data = json.loads(b1.snapshot(py, cfg))
    # Public metadata is exporter/template input; Rust intentionally ignores
    # these extra JSON fields so old C56 serialized defaults stay unchanged.
    holder = SimpleNamespace(loader=py.card_loader, _payload_name=StructuredObservationBuilder._payload_name)
    byid = {e.id: e for e in py.entities.values()}
    for row in data['entities']:
        require(bool(row.get('public_identity')) and bool(row.get('public_static')), ('missing public fields', row['id']))
        for ns, names in row['public_identity']:
            require(list(names) == list(StructuredObservationBuilder._typed_identity_candidates(holder, byid[row['id']], ns)),
                    ('public identity differs', row['id'], ns))
    for table in ('create_areas', 'hit_areas'):
        require('level12:BattleHealer' in cfg[table], (table, 'missing mirrored healer'))
    b1.continuation(py, native, cfg, ticks=6)
    return dict(entities=len(data['entities']), config_tables=sorted(cfg), public_fields=True)


def container_release(seat, zero_deploy):
    py, cfg = b1.fresh(('SkeletonBalloon', 'GoblinGiant', 'Knight', 'Freeze'))
    point = lambda x, y: (x, y) if seat == 0 else (18-x, 32-y)
    giant = b1.spawn(py, 'GoblinGiant', seat, *point(5.5, 10.5))
    parent = b1.spawn(py, 'SkeletonBalloon', seat, *point(4.5, 10.5))
    parent.inherit_freeze_until(py.time + 4, py.time)
    parent.take_damage(parent.hitpoints)
    bombs = [e for e in py.entities.values() if type(e).__name__ == 'TimedExplosive']
    require(len(bombs) == 1, 'no real container death payload')
    bomb = bombs[0]
    require(bomb.carries_freeze_to_children and bomb.freeze_expiry_time > py.time, 'missing Freeze carrier')
    if zero_deploy:
        # Scratch-only boundary control: make before-vs-after Freeze ordering
        # observable without the normal 500ms deploy masking the first move.
        bomb.death_spawn_deploy_time = 0
        for row in cfg['bomb_children'][bomb.card_stats.name]:
            row['deploy'] = 0
    native = b1.clasher_core.BattleState(b1.snapshot(py, cfg))
    events = []
    original = py._first_update_spawned

    def observe(child, **kw):
        require(child.freeze_expiry_time == bomb.freeze_expiry_time and child.stun_timer > 0,
                ('first update preceded inherited Freeze', child.id))
        before = (child.position.x, child.position.y)
        original(child, **kw)
        require(before == (child.position.x, child.position.y), 'frozen container child moved')
        require(kw.get('collide') is False, 'container collision pass')
        events.append(dict(id=child.id, tick=py.tick, freeze=child.stun_timer,
                           position=before, deploy=child.deploy_delay_remaining))

    py._first_update_spawned = observe
    for _ in range(int((bomb.explosion_timer + .2) / py.dt) + 4):
        py.step(); native.step()
        b1.audited_state(py, native, cfg)
    require(len(events) == bomb.death_spawn_count and len({e['id'] for e in events}) == len(events),
            ('container first update count', events, bomb.death_spawn_count))
    require(len({e['tick'] for e in events}) == 1 and not bomb.is_alive, 'release/fuse boundary')
    require(giant.is_alive and len(giant._rider_mechanic.riders) == 2, 'missing adjacent graph')
    del py._first_update_spawned
    b1.continuation(py, native, cfg, ticks=12)
    return dict(seat=seat, zero_deploy=zero_deploy, events=events)


if __name__ == '__main__':
    for name, case in paths.CASES.items():
        for seat, current in ((0, case), (1, paths.mirror(case))):
            record(f'first-update/{name}/{seat}', lambda n=name, c=current: path_case(n, c))
    for name in a.CASES:
        record('batchA-case/'+name, lambda n=name: lockstep(a, n, 'case', n))
    for seat in (0, 1):
        for periodic in (False, True):
            record(f'nested-riders/{seat}/{periodic}', lambda s=seat, p=periodic: nested(s, p))
        for zero in (False, True):
            record(f'container-release/{seat}/zero-deploy={zero}', lambda s=seat, z=zero: container_release(s,z))
    for module, family, cards in ((a, 'batchA', ('Tombstone', 'BarbarianHut', 'Witch')),
                                  (b, 'b1', ('RoyalRecruits', 'ThreeMusketeers', 'GiantSkeleton', 'SkeletonBalloon',
                                             'Hunter', 'MiniSparkys', 'RoyalGiant', 'BattleHealer', 'GoblinGiant', 'GiantBuffer'))):
        pool = {r['name']: r['kind'] for r in json.loads((TOOLS/family/'pool.json').read_text())}
        for card in cards:
            for scenario in module.scenarios(dict(name=card, kind=pool[card])):
                record(f'{family}/{card}/{scenario}', lambda m=module, c=card, k=pool[card], s=scenario: lockstep(m,c,k,s))
    record('public-template-export-config', public_export)
    report = dict(total=len(RESULTS), passed=sum(r['ok'] for r in RESULTS), tests=RESULTS,
                  raw_state_diff_paths=dict(b1.RAW_DIFFS),
                  note='Digests and explicit B1 metadata/positions do not certify raw cross-engine snapshot equality.')
    with open(sys.argv[1], 'x') as f:
        json.dump(report, f, indent=2)
    require(report['passed'] == report['total'], ('failed combined probes', report['passed'], report['total']))
