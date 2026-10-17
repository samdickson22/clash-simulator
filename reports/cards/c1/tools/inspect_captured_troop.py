"""Read-only JSON observations from B2's separately reviewed bounded capture.

Usage: inspect_captured_troop.py RAW.json EXPECTED_SHA256
The expected hash must come from the owning B2 receipt, not this tool's output.
No simulation, normalization, fixture-validity decision or acceptance verdict.
"""
import hashlib
import json
from pathlib import Path
import sys


CONTRACT = 'b2-semantic-snapshot-v1'
END = 45  # frozen legacy collector's comparison window
CASES = {'zap': (1, 7, 0), 'electro_dragon': (6, 8, 14), 'ice_spirit': (0, 8, 23)}
FIELDS = ('id', 'class', 'entity_kind', 'x', 'y', 'alive', 'target', 'move_target', 'nav_target',
          'facing', 'direction', 'route', 'stun', 'freeze_pause', 'frozen_moving', 'moving',
          'dash', 'spirit', 'spirit_launch', 'shot_target', 'aim', 'clock', 'clock_initialized',
          'started', 'windup', 'finish_tick', 'pending_ms', 'pending_lethal', 'attacked_current',
          'resume_pending', 'slow_ms', 'area_slows', 'move_mode', 'attack_mode', 'hastes')
STATS = ('name', 'payload_key', 'ordinary', 'projectile_slow_multiplier', 'projectile_slow_duration',
         'projectile_stun', 'spirit_speed', 'spirit_stun', 'spirit_radius', 'electro_chain',
         'damage', 'finish_allowed', 'interval', 'load', 'child_count', 'child_damage', 'child_range')


def integer(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(f'expected nonnegative integer {name}')
    return value


def result_projection(result):
    # Preserve all outcome/error/difference keys AND their presence. Only the
    # imported template table is kept in the hash-bound raw capture instead.
    return {k: v for k, v in result.items() if k != 'fresh_troop_templates'}


def entity(state, identity):
    matches = [row for row in state['entities'] if row['id'] == identity]
    if len(matches) != 1:
        raise ValueError(f'expected exactly one entity {identity}, got {len(matches)}')
    return matches[0]


def selected(row):
    # Report absence explicitly rather than silently treating it as a default.
    return dict(fields={k: row[k] if k in row else '<absent>' for k in FIELDS},
                stats={k: row['stats'][k] if k in row['stats'] else '<absent>' for k in STATS})


def frame(pair, identity, *, allow_unborn=False):
    if set(pair) != {'python', 'native'}:
        raise ValueError('expected Python/native pair')
    for state in pair.values():
        integer(state['tick'], 'frame tick')
    if pair['python']['tick'] != pair['native']['tick']:
        raise ValueError('unequal paired tick boundary')
    result = dict(tick=pair['python']['tick'])
    for arm, state in pair.items():
        ids = [e['id'] for e in state['entities']]
        if len(ids) != len(set(ids)):
            raise ValueError('duplicate entity IDs in root')
        if allow_unborn and identity not in ids:
            result[arm] = dict(actor=None, actor_presence='absent', target=None)
            continue
        actor = entity(state, identity)
        target_id = actor.get('target')
        targets = [e for e in state['entities'] if e['id'] == target_id]
        result[arm] = dict(actor=selected(actor), actor_presence='present',
                           target=selected(targets[0]) if targets else None)
        if targets:
            result[arm]['target_displacement_units'] = [round((targets[0][axis]-actor[axis])*1000)
                                                        for axis in ('x', 'y')]
    return result


def observation(row):
    case = row['case']
    lead, identity, first_tick = CASES[case]
    if row['contract'] != CONTRACT or row['lead'] != lead or type(row['seat']) is not int or row['seat'] not in (0, 1):
        raise ValueError('wrong case/lead/seat/contract')
    if 'error' in row or 'error' in row['result']:
        raise ValueError('capture contains an execution error')
    # IceSpirit lead0 is cast in the first loop iteration AFTER construction.
    # It need not exist in that initial root; it must exist at its t23 mismatch.
    result = dict(case=case, seat=row['seat'], lead=lead,
                  initial=frame(row['initial_root'], identity, allow_unborn=case == 'ice_spirit'),
                  original_source_sha256=row['source_sha256'],
                  retained_result=result_projection(row['result']),
                  omitted_result_fields=['fresh_troop_templates'] if 'fresh_troop_templates' in row['result'] else [],
                  evidence_kind='captured-boundary-observations-not-causal-proof')
    context = row['first_context']
    if context is None:
        if row['seat'] == 0 or row['result']['first'] is not None:
            raise ValueError('required blue legacy mismatch was not captured')
        result['first_context'] = None
        return result
    before, after = frame(context['before'], identity), frame(context['after'], identity)
    relative = integer(context['relative_tick'], 'relative comparison tick')
    first = integer(row['result']['first'], 'first comparison tick')
    if relative >= END:
        raise ValueError('relative comparison outside frozen legacy window')
    for owner in (row, row['result']):
        if 'compared_ticks' in owner:
            count = integer(owner['compared_ticks'], 'comparison count')
            if not relative < count <= END:
                raise ValueError('mismatch outside recorded comparison count')
    if (before['tick'] != result['initial']['tick']+relative
            or after['tick'] != before['tick']+1 or relative != first):
        raise ValueError('incoherent first-mismatch boundaries')
    if row['seat'] == 0 and context['relative_tick'] != first_tick:
        raise ValueError('blue legacy first mismatch did not reproduce')
    result.update(relative_tick=context['relative_tick'], before=before, after=after,
                  differences=context['differences'], digest_equal=context['digest_equal'])
    if case == 'electro_dragon':
        # Boundary coincidence is a recorded fact only. Component instrumentation
        # or a source-grounded proof must still exclude intervening position/lock changes.
        result['zero_displacement_at_before_boundary'] = {
            arm: before[arm].get('target_displacement_units') == [0, 0] for arm in ('python', 'native')}
    elif case == 'ice_spirit':
        result['configuration'] = {}
        for arm, state in context['after'].items():
            actor = entity(state, identity)
            stats = actor['stats']
            key = stats.get('payload_key') or stats['name']
            config = state['config']
            area = config.get('spirit_areas', {}).get(key)
            card = config['cards'].get(key)
            chain = None if card is None else card.get('chain')
            result['configuration'][arm] = dict(payload_key=key, spirit_area=None if area is None else selected(area),
                                                chain=None if chain is None else selected(chain))
    return result


def inspect(path, expected_sha256):
    raw = Path(path).read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if len(expected_sha256) != 64 or actual != expected_sha256:
        raise ValueError('capture hash differs from owner receipt')
    data = json.loads(raw)
    if data['contract'] != CONTRACT or data['collection_status'] != 'COMPLETE':
        raise ValueError('collection not complete under required contract')
    expected = {(case, seat) for case in CASES for seat in (0, 1)}
    if len(data['legacy']) != 6 or {(r['case'], r['seat']) for r in data['legacy']} != expected:
        raise ValueError('missing or duplicated legacy capture')
    return dict(capture_path=str(Path(path).resolve()), capture_sha256=actual,
                collection_status=data['collection_status'], original_status=data['status'],
                owner_outcomes={k: v for k, v in data.items() if k not in ('legacy', 'rows')},
                natural_outcomes=[{k: v for k, v in row.items()
                                   if k not in ('initial_root', 'first_context', 'fresh_troop_templates')}
                                  for row in data.get('rows', [])],
                raw_capture_blocks_retained=['legacy.*.result.fresh_troop_templates',
                                             'rows.*.initial_root', 'rows.*.first_context',
                                             'rows.*.fresh_troop_templates'],
                engine_acceptance='NOT_EVALUATED',
                rows=[observation(row) for row in data['legacy']],
                limitation='No source/native provenance authentication beyond supplied owner hash; no phase replay, cause/reachability or fixture-validity verdict.')


if __name__ == '__main__':
    print(json.dumps(inspect(*sys.argv[1:]), sort_keys=True, indent=2))
