"""b2-semantic-snapshot-v1: explicit applicability, independently observed speed/aim.

Source-bound proof: reports/cards/b2/SEMANTIC-SNAPSHOT-V1.md. Unknown classes/fields
remain strict. This is semantic equality, never complete serialized equality.
"""
import copy

VERSION = 'b2-semantic-snapshot-v1'
UNSET_TICKS = {'finish_tick', 'landed_tick', 'push_tick'}
TOWER_ARROW_FIELDS = {'age', 'attacked_current', 'lane', 'last_target', 'started'}
CACHE_INAPPLICABLE = {
    'Building': 'leaf.rs128 reads public_speed_base only for Troop; building descendants use fresh templates or remain projectiles',
    'Projectile': 'projectile flight reads stats.speed; source clones remain Projectile and materialized Troops use fresh templates',
    'SpawnProjectile': 'delivery_tick creates Troops from card.spawns templates, never from the live projectile object',
    'RollingProjectile': 'rolling_tick creates Troops from card.spawns templates; rolling_character_tick never retypes itself',
    'TimedExplosive': 'bomb_tick creates Troops through spawn_death_templates from bomb_children templates',
}


def norm(value):
    return round(value, 6) if isinstance(value, float) else value


def differences(expected, actual, path='state'):
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            if key not in expected or key not in actual:
                yield dict(field=f'{path}.{key}', python=expected.get(key), native=actual.get(key))
            else:
                yield from differences(expected[key], actual[key], f'{path}.{key}')
        return
    if isinstance(expected, list) and isinstance(actual, list):
        if path.endswith('.hit_ids'):
            if sorted(expected) != sorted(actual):
                yield dict(field=path, python=expected, native=actual)
            return
        if len(expected) != len(actual):
            yield dict(field=path, python=expected, native=actual)
            return
        for index, (left, right) in enumerate(zip(expected, actual)):
            yield from differences(left, right, f'{path}[{index}]')
        return
    if norm(expected) != norm(actual):
        yield dict(field=path, python=expected, native=actual)


def committed_projectile_aims(state, entities):
    for row in state['entities']:
        if row['class'] in ('Projectile', 'SpawnProjectile'):
            endpoint = entities[row['id']].target_position
            row['aim'] = [endpoint.x, endpoint.y]
    return state


def native_active_speed(row):
    cached = row.get('public_speed_base')
    return float(cached if cached is not None else row['stats'][
        'charge_speed' if row.get('charge', 0) >= 10000 else 'speed'])


def troop_speed_differences(battle, native_rows):
    for eid, row in native_rows.items():
        entity = battle.entities.get(int(eid))
        if row['class'] == 'Troop' and entity is not None:
            expected, actual = float(entity._unslowed_movement_speed()), native_active_speed(row)
            if norm(expected) != norm(actual):
                yield dict(field=f'state.entities.{eid}.effective_unslowed_speed', python=expected,
                           native=actual, entity_class='Troop', stats_name=row.get('stats', {}).get('name'))


def fresh_troop_templates(state):
    """Record/check every actual config/Clone Troop template before exempting live non-Troop caches."""
    found = []
    def walk(value, path):
        if isinstance(value, dict):
            if value.get('class') == 'Troop':
                cache = value.get('public_speed_base')
                if cache is not None:
                    raise AssertionError(f'non-fresh Troop template {path}: cache={cache}')
                found.append(path)
            for key, item in value.items():
                walk(item, f'{path}.{key}')
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f'{path}[{index}]')
    walk(state['config'], 'config')
    for row in state['entities']:
        if row.get('clone_template') is not None:
            walk(row['clone_template'], f'entities.{row["id"]}.clone_template')
    if not found:
        raise AssertionError('no fresh Troop templates observed')
    return found


def compare_states(expected, actual, entities):
    """Return semantic deltas, complete applicability records and raw deltas before cache applicability."""
    expected, actual = copy.deepcopy(expected), copy.deepcopy(actual)
    lefts = {str(r['id']): r for r in expected.pop('entities') if r.get('alive', True)}
    rights = {str(r['id']): r for r in actual.pop('entities') if r.get('alive', True)}
    expected.pop('config'); actual.pop('config')
    ledger = []
    def record(eid, row, field, py, rs, reason, disposition='inapplicable'):
        ledger.append(dict(field=f'state.entities.{eid}.{field}', entity_class=row['class'],
                           python=copy.deepcopy(py), native=copy.deepcopy(rs), reason=reason,
                           disposition=disposition))
    def exclude(eid, left, right, key, reason, stats=False):
        py, rs = (left['stats'], right['stats']) if stats else (left, right)
        record(eid, left, ('stats.' if stats else '') + key, py.get(key), rs.get(key), reason)
        py.pop(key, None); rs.pop(key, None)
    # Existing strict-r2 baseline exclusions retain precisely their documented class/path scope.
    for eid in sorted(lefts.keys() & rights.keys()):
        left, right, entity = lefts[eid], rights[eid], entities[int(eid)]
        if getattr(entity, '_native_object_birth_tick', None) is None:
            exclude(eid, left, right, 'birth', 'strict-r2 baseline: synthesized Python birth when no object birth is recorded')
        if left['class'] == 'Troop':
            exclude(eid, left, right, 'cooldown', 'strict-r2 baseline: troop projection; clock/force_due remain strict')
            exclude(eid, left, right, 'route_occupied', 'strict-r2 baseline: navigation occupancy-cache representation')
        if left['class'] == 'Projectile' and left.get('stats', {}).get('name') == 'Tower':
            for key in sorted(TOWER_ARROW_FIELDS):
                exclude(eid, left, right, key, 'strict-r2 baseline: Tower-arrow actor-clone representation')
            for key in ('max_hp', 'sight'):
                exclude(eid, left, right, key, 'strict-r2 baseline: Tower-arrow actor-clone stats representation', stats=True)
        for key in sorted(UNSET_TICKS):
            if left.get(key) in (-1, 0) and right.get(key) in (-1, 0):
                if left.get(key) != right.get(key):
                    record(eid, left, key, left.get(key), right.get(key),
                           'strict-r2 baseline: -1/0 encode the same unset tick', 'equivalent-representation')
                left[key] = right[key] = 0
    expected['entities'], actual['entities'] = lefts, rights
    raw = list(differences(expected, actual))
    for eid in sorted(lefts.keys() & rights.keys()):
        left, right, entity = lefts[eid], rights[eid], entities[int(eid)]
        if left['class'] != right['class']:
            continue  # Class drift must fail; it cannot acquire an exemption from either side.
        if left['class'] == 'Troop':
            py_speed, rs_speed = float(entity._unslowed_movement_speed()), native_active_speed(right)
            record(eid, left, 'public_speed_base', left.get('public_speed_base'), right.get('public_speed_base'),
                   'independent Python unslowed speed vs native actual historical cache, or exact fallback only at None',
                   'effective-value-compared')
            # Every non-null native value is retained. Only None selects the native leaf.rs fallback.
            left['public_speed_base'], right['public_speed_base'] = py_speed, rs_speed
        elif left['class'] in CACHE_INAPPLICABLE:
            exclude(eid, left, right, 'public_speed_base', CACHE_INAPPLICABLE[left['class']])
    out = []
    for delta in differences(expected, actual):
        parts = delta['field'].split('.')
        if len(parts) > 2 and parts[1] == 'entities':
            row = lefts.get(parts[2], rights.get(parts[2], {}))
            delta.update(entity_class=row.get('class'), spell_name=row.get('spell_name'),
                         stats_name=row.get('stats', {}).get('name'))
        out.append(delta)
    return out, ledger, raw
