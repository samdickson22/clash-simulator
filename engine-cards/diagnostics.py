"""Read-only Python state capture and first-transition subsystem replay."""
import dataclasses
import inspect
import json
import sys
from collections import deque


def plain(value, seen=None):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if seen is None:
        seen = set()
    if seen and hasattr(value, 'entity_kind'):
        return {'entity_id': value.id}
    if id(value) in seen:
        return '<reference>'
    seen = seen | {id(value)}
    if isinstance(value, dict):
        return {str(k): plain(v, seen) for k, v in value.items()}
    if isinstance(value, (list, tuple, deque, set, frozenset)):
        return [plain(v, seen) for v in value]
    if hasattr(value, 'tolist'):
        return value.tolist()
    if dataclasses.is_dataclass(value) or hasattr(value, '__dict__'):
        return {k: plain(v, seen) for k, v in vars(value).items()
                if k not in ('battle_state', 'rng', 'card_stats') and not callable(v)}
    return repr(value)


def python_state(b):
    from differential import public_fields
    data = public_fields(b)
    data['rng'] = dict(state=list(b.rng.getstate()[1][:-1]), index=b.rng.getstate()[1][-1])
    for p, raw in zip(data['players'], b.players):
        p['refill'] = raw.next_card_refill_cooldown_ms
    for e, raw in zip(data['entities'], b.entities.values()):
        clock = raw._ordinary_clock
        e.update(deploy=raw.deploy_delay_remaining, stagger=raw.spawn_stagger_remaining,
                 age=raw._native_deployed_elapsed_ms, cooldown=raw.attack_cooldown,
                 clock=dict(timeline=clock.hit_timeline_ms if clock else 0,
                            remaining=clock.load_remaining_ms if clock else 0,
                            finish=raw._attack_finish_elapsed_ms),
                 facing=[raw._facing_x_units, raw._facing_y_units],
                 move_target=getattr(raw, '_movement_target_id', None),
                 pending_ms=raw._pending_projectile_max_duration_ms,
                 pending_lethal=raw._combat_target_pending_lethal,
                 resume_pending=raw._resume_pending_hit,
                 attacked_current=raw._has_attacked_current_target,
                 shot_target=getattr(getattr(raw, 'primary_target', None), 'id', None))
    data['raw_entities'] = {str(e.id): plain(e) for e in b.entities.values()}
    data['battle'] = {k: plain(v) for k, v in vars(b).items()
                      if isinstance(v, (str, int, float, bool, type(None))) or k in ('_sudden_death_crowns', '_combat_phase_eligible_ids')}
    return data


def native_state(native):
    data = json.loads(native.snapshot()) if not isinstance(native, dict) else native.copy()
    data.pop('config', None)
    return data


def differences(a, b, path=''):
    """Compare common semantic fields; retain unprojected fields in raw snapshots."""
    if isinstance(a, dict) and isinstance(b, dict):
        return [d for k in sorted(a.keys() & b.keys()) for d in differences(a[k], b[k], f'{path}.{k}')]
    if isinstance(a, list) and isinstance(b, list):
        if path.endswith('.entities'):
            return differences({str(e['id']): e for e in a}, {str(e['id']): e for e in b}, path) + [
                dict(field=path+'.ids', python=[e['id'] for e in a], rust=[e['id'] for e in b])
                for _ in [0] if [e['id'] for e in a] != [e['id'] for e in b]]
        if len(a) != len(b):
            return [dict(field=path, python=a, rust=b)]
        return [d for i, (x,y) in enumerate(zip(a,b)) for d in differences(x,y,f'{path}[{i}]')]
    return [] if a == b else [dict(field=path, python=a, rust=b)]


def detail(b, native):
    p, r = python_state(b), native_state(native)
    return dict(field_diff=differences(p,r), python=p, rust=r)


def phase_step(b, native):
    """Capture real Python phase boundaries without changing engine methods."""
    fn = type(b)._step_logic_tick
    lines, start = inspect.getsourcelines(fn)
    points = {}
    movement = False
    for i, line in enumerate(lines):
        if '# Component type 1:' in line:
            movement = True
        if movement and 'for entity in entities_to_update:' in line:
            points[start+i] = 'combat'; movement = False
        for marker, label in [('entities_to_update =', 'start'), ('self._run_object_phase(', 'movement'),
                              ('self._cleanup_dead_entities()', 'objects'), ('self._check_win_conditions()', 'cleanup')]:
            if marker in line:
                points[start+i] = label
    snapshots = {'before': python_state(b)}
    rust_before = native_state(native)
    def trace(frame, event, arg):
        if frame.f_code is fn.__code__ and event == 'line' and frame.f_lineno in points:
            label = points[frame.f_lineno]
            if label not in snapshots:
                snapshots[label] = python_state(b)
        return trace if frame.f_code is fn.__code__ else None
    previous = sys.gettrace()
    try:
        sys.settrace(trace); b.step()
    finally:
        sys.settrace(previous)
    snapshots['complete'] = python_state(b)
    rust = [('before', rust_before)] + json.loads(native.debug_step())
    return {label: dict(field_diff=differences(snapshots[label], native_state(state)),
                        python=snapshots[label], rust=native_state(state)) for label, state in rust}
