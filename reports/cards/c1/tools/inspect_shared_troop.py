"""Small stdlib source witness, not a native/engine continuation or reachability test.

Execute selected unmodified Python function ASTs with explicit minimal fixtures.
Read B2's retained first-failure records without importing its engine or changing
any comparator. Full roots and independently reviewed continuations are separate.
"""
import ast
import copy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace


ROOT = Path(__file__).resolve().parents[4]
ENGINE = ROOT / 'engine-cards'
B2 = ROOT.parent / 'clasher-cards-b2'


def function(path, name, namespace, owner=None):
    tree = ast.parse(path.read_text())
    body = tree.body
    if owner is not None:
        body = next(n.body for n in body if isinstance(n, ast.ClassDef) and n.name == owner)
    node = copy.deepcopy(next(n for n in body if isinstance(n, ast.FunctionDef) and n.name == name))
    # Postpone annotations only; the actual function body remains unchanged.
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), node], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(path), 'exec'), namespace)
    return namespace[name]


@dataclass
class Position:
    x: float
    y: float


def source_witnesses():
    py = ENGINE / 'py/src/clasher'
    ns = dict(math=math, Position=Position, LOGIC_UNITS_PER_TILE=1000, HALF_TILE_LOGIC_UNITS=500)
    for name in ('trunc_div', 'tiles_to_logic_units', 'logic_units_to_tiles', 'normalized_vector_logic_units'):
        function(py / 'kinematics.py', name, ns)
    face = function(py / 'entities.py', 'face_towards', ns, 'Entity')
    e = SimpleNamespace(position=Position(9, 17.5), _facing_x_units=0, _facing_y_units=-1000)
    face(e, Position(9, 17.5))
    assert (e._facing_x_units, e._facing_y_units) == (0, -1000)
    face(e, Position(9.001, 17.5))
    assert (e._facing_x_units, e._facing_y_units) == (1, 0)
    face(e, Position(9.0001, 17.5))  # quantized zero, not just exact float equality
    assert (e._facing_x_units, e._facing_y_units) == (1, 0)

    for name in ('_cell_center', '_set_native_route_direction', 'advance_native_ground_route'):
        function(py / 'pathfinding.py', name, ns)
    advance = ns['advance_native_ground_route']
    route = SimpleNamespace(position=Position(9, 10.5), _native_ground_route_cells=[(21, 23), (22, 24)],
                            _native_ground_route_direction=(181, 181))
    trace = []
    for y in (11, 11.5, 12, 12.5):
        previous = route.position
        route.position = Position(9, y)
        waypoint = ns['_cell_center'](route._native_ground_route_cells[0])
        face(route, waypoint)
        consumed = advance(route, waypoint, previous)
        trace.append(dict(y=y, facing=[route._facing_x_units, route._facing_y_units],
                          consumed=consumed, route=copy.deepcopy(route._native_ground_route_cells),
                          direction=route._native_ground_route_direction))
    assert [v['facing'][1] for v in trace] == [750, 250, -250, -750]
    assert [v['consumed'] for v in trace] == [False, False, False, True]
    assert trace[-1]['direction'] == (254, -28)
    # Threshold and one-node-per-call controls, using the actual reference routine.
    at = SimpleNamespace(position=Position(9, 10.75), _native_ground_route_cells=[(20, 21), (21, 21)],
                         _native_ground_route_direction=(256, 0))
    assert not advance(at, Position(10.25, 10.75), at.position)  # remainder1250 >=1001
    at.position = Position(10.25, 10.75)
    assert advance(at, Position(10.25, 10.75), at.position)
    assert at._native_ground_route_cells == [(21, 21)]

    class Troop:
        pass

    ns.update(Troop=Troop, __package__='c1_source_reference')
    # Supply the already-extracted real reference function at its relative import;
    # this does not import the engine or replace any actual runtime module.
    module_key = 'c1_source_reference.pathfinding'
    assert module_key not in sys.modules
    module = ModuleType(module_key)
    module.advance_native_ground_route = advance
    take = function(py / 'entities.py', 'take_pending_movement_vector', ns, 'Entity')
    finish = function(py / 'entities.py', 'finish_movement_tick', ns, 'Entity')
    clamp = function(py / 'native_tilemap.py', 'clamp_native_object_axis', ns)
    Troop.take_pending_movement_vector, Troop.face_towards = take, face

    def finalization(stunned=True, frozen=True, cells=((21, 23), (22, 24)), external=(0, 0)):
        obj = Troop()
        obj.position = Position(9, 12.5)  # post-transport boundary, not a simulated dash
        obj._native_ground_route_cells = list(cells)
        obj._native_ground_route_direction = (181, 181)
        obj._native_moving_when_frozen = frozen
        obj._facing_x_units, obj._facing_y_units = 0, 1250
        obj._pending_movement_consumed = False
        obj._pending_movement_x, obj._pending_movement_y = external
        obj.deploy_delay_remaining = 0
        obj.is_stunned = lambda: stunned
        battle = SimpleNamespace(arena=SimpleNamespace(width=18, height=32), sync_fast_target_entity=lambda _: None)
        finish(obj, battle)
        return obj

    sys.modules[module_key] = module
    try:
        after = finalization()
        assert (after._facing_x_units, after._facing_y_units) == (1750, -750)
        assert after._native_ground_route_cells == [(22, 24)]
        assert after._native_ground_route_direction == (254, -28)
        for options in (dict(stunned=False), dict(frozen=False), dict(cells=())):
            control = finalization(**options)
            assert (control._facing_x_units, control._facing_y_units) == (0, 1250)
        # Facing is taken before external movement, node advancement after it.
        after = finalization(external=(0.25, -0.5))
        assert (after.position.x, after.position.y) == (9.25, 12.0)
        assert (after._facing_x_units, after._facing_y_units) == (1750, -750)
        assert after._native_ground_route_cells == [(22, 24)]
    finally:
        del sys.modules[module_key]

    movement = function(py / 'cards/bandit.py', 'on_movement_tick', ns, 'BanditDash')
    launches, travels = [], []
    mechanism = SimpleNamespace(_launch_dash=lambda *args: launches.append(args),
                                _update_dash=lambda *args: travels.append(args))
    target = SimpleNamespace(id=2, is_alive=True)
    waiting = SimpleNamespace(battle_state=SimpleNamespace(entities={2: target}),
                              _bandit_state='standing', _bandit_wait=1, _bandit_seen_target=2,
                              target_id=2, _attack_windup_active=False, _attack_finish_elapsed_ms=0,
                              is_stunned=lambda: True)
    movement(mechanism, waiting, 50)
    assert not launches and waiting._bandit_wait == 1
    waiting.is_stunned = lambda: False
    movement(mechanism, waiting, 50)
    assert len(launches) == 1 and waiting._bandit_wait == 0
    waiting._bandit_state, waiting.is_stunned = 'travel', lambda: True
    movement(mechanism, waiting, 50)
    assert len(travels) == 1  # committed travel runs before the stun guard

    class BaseMechanic:
        def on_attack_start(self):
            pass
        def on_attack_committed(self):
            pass

    class IceSpiritFreeze(BaseMechanic):
        def on_attack_start(self):
            pass

    class AttackRecoil(BaseMechanic):
        pass

    supported = function(py / 'ordinary_combat_clock.py', 'supported',
                         dict(BaseMechanic=BaseMechanic, IceSpiritFreeze=IceSpiritFreeze, AttackRecoil=AttackRecoil))
    spirit = SimpleNamespace(card_stats=SimpleNamespace(name='IceSpirits', hit_speed=1000,
                             load_time=800, first_hit_time=200), entity_kind=0, mechanics=[IceSpiritFreeze()])
    assert supported(spirit)
    spirit.entity_kind = 2
    assert not supported(spirit)
    spirit.entity_kind = 0
    assert supported(spirit)
    entity_ast = ast.parse((ENGINE / 'differential.py').read_text())
    stats = next(n.value for n in ast.walk(entity_ast) if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'stats' for t in n.targets)
                 and isinstance(n.value, ast.Call))
    expr = next(k.value for k in stats.keywords if k.arg == 'projectile_slow_multiplier')
    code = compile(ast.Expression(expr), str(ENGINE / 'differential.py'), 'eval')
    spirit.slow_multiplier = 1.0
    values = []
    for kind, slow in ((0, 1.0), (2, 1.0), (2, 0.7), (0, 0.7)):
        spirit.entity_kind, spirit.slow_multiplier = kind, slow
        values.append(eval(code, dict(e=spirit, buff={'speedMultiplier': -100})))
    assert values == [0.0, 1.0, 0.7, 0.0]
    return dict(zero_heading_preserved=True, nonzero_and_quantized_zero_controls=True,
                retained_route_trace=trace, threshold_and_one_node_controls=True,
                actual_finalizer_controls=['post_transport', 'not_stunned', 'not_frozen_moving', 'empty_route',
                                           'facing_before_external_and_pop_after_external'],
                actual_dash_dispatch_controls=['stunned_stand_pauses', 'unstunned_stand_launches',
                                               'forced_stunned_travel_still_runs'],
                ice_ordinary_character_projectile_character=[True, False, True],
                projectile_slow_mode_controls=values,
                limitation='Source/explicit-state witness only; no native execution, captured root or normal gameplay proof.')


def retained_failures():
    result = {}
    for name in ('zap', 'electro-dragon', 'ice-spirit'):
        path = B2 / f'reports/cards/b2/evidence/semv1-first-{name}-blue.json'
        data = json.loads(path.read_text())
        first = data['first_bad']
        result[name] = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                            runs=data['runs'], mismatches=data['mismatches'], lead=first['lead'],
                            first=first['first'], first_field=first['field'], differences=first['differences'],
                            gate_queries=first['gate_queries'], captured_root_present='initial_root' in first,
                            cast=first['cast'])
    return result


if __name__ == '__main__':
    print(json.dumps(dict(kind='source-witness-not-engine-acceptance', source=source_witnesses(),
                          retained_failures=retained_failures()), indent=2, sort_keys=True))
