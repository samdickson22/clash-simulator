"""Bounded C1 follow-up: one AxeMan/knight lifecycle and the exact mk_target_dies shot.

Pure simulation probe; no host access or launches. Uses an existing native. No broad sweeps.
"""
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

import differential as D
import probe_snapshots as S
import probe_c1_cases as C
from scenarios import script
from live_snapshot import live_entity


def setup(seq):
    cards = tuple(dict.fromkeys([n for _, n, _, _ in seq] + list(S.P.FILL)))[:8]
    b, cfg = D.initial(7, cards=cards), D.config(cards)
    for side, p in enumerate(b.players):
        p.elixir = 10
        mine = list(dict.fromkeys(n for s, n, _, _ in seq if s == side))
        p.hand = (mine + [c for c in cards if c not in mine])[:4]
        p.cycle_queue.clear(); p.cycle_queue.extend(c for c in cards if c not in p.hand)
    by = {}
    for s, name, tile, t in seq:
        by.setdefault(t, []).append((s, name, tile))
    return b, cfg, D.clasher_core.BattleState(D.snapshot(b, cfg)), by


def state(n):
    return json.loads(n.snapshot())


def step(b, natives, by, t):
    for s, name, (x, y) in by.get(t, []):
        assert b.deploy_card(s, name, D.Position(x, y))
        for n in natives:
            assert n.apply_action(s, name, x, y)
    b.step()
    for n in natives:
        n.step(1)
        assert n.digest() == D.battle_digest(b), (t, 'digest')


def canonical(n, target, field):
    out = state(n)
    for e in out['entities']:
        if e['id'] == target:
            e.pop(field, None)
    return out


def semantic(b, cfg, n, target, allowed):
    classes = {}
    S.compare(b, cfg, n, b.tick, set(), classes)
    for k, v in classes.items():
        assert k in allowed and v['example'][0] == target, (b.tick, k, v)


def field_diff(p, q):
    p, q = S.norm(p), S.norm(q)
    keys = list(S.CHECK) + list(S.CLASS_FIELDS.get(p['class'], ()))
    p, q, keys = S.normalize_owned_fields(p, q, keys)
    return {k for k in keys if p.get(k) != q.get(k)}


def axe_controls(p, q):
    assert not field_diff(p, q), field_diff(p, q)
    for key, value in (('pp_t', 7), ('pp_origin', [0, 0]), ('pp_apex', [0, 0]), ('hit_ids', [8])):
        changed = deepcopy(q); changed[key] = value
        assert key in field_diff(p, changed), ('masked', key)
    a, z = deepcopy(p), deepcopy(q)
    a['hit_ids'], z['hit_ids'] = [7, 7, 8], [8, 7, 7]
    assert 'hit_ids' not in field_diff(a, z)
    z['hit_ids'] = [8, 7]
    assert 'hit_ids' in field_diff(a, z), 'multiplicity discarded'


def axe():
    seq, _ = script(dict(name='AxeMan', kind='troop'), 'knight')
    b, cfg, n, by = setup(seq)
    for t in range(80):
        step(b, [n], by, t)
        shots = [e for e in b.entities.values() if type(e).__name__ == 'PingpongProjectile']
        if shots:
            break
    assert shots and t == 29
    a = shots[0]; i = a.id
    assert i == 9 and a.pp_t == 0 and a.pp_period == 30
    ns = state(n); shot = next(e for e in ns['entities'] if e['id'] == i)
    p = live_entity(a, b, cfg)
    axe_controls(p, shot)
    info = dict(case='AxeMan/knight', first=t, id=i, period=a.pp_period,
                python_aim=p.get('aim'), native_aim=shot.get('aim'),
                python_target_position=[a.target_position.x, a.target_position.y],
                pp_origin=p['pp_origin'], pp_apex=p['pp_apex'], trajectory=[])
    resumed = D.clasher_core.BattleState(D.snapshot(b, cfg))
    roundtrip = D.clasher_core.BattleState(n.snapshot())
    changed = state(n)
    next(e for e in changed['entities'] if e['id'] == i)['aim'] = [-99, 99]
    changed_aim = D.clasher_core.BattleState(json.dumps(changed))
    changed = state(n)
    next(e for e in changed['entities'] if e['id'] == i)['pp_t'] = 7
    meaningful = D.clasher_core.BattleState(json.dumps(changed))
    # Python's actual target_position is likewise absent from _pp_point/update. Perturb a clone at birth.
    altered_py = b.clone()
    altered_py.entities[i].target_position = D.Position(-99, 99)
    for age in range(32):
        semantic(b, cfg, n, i, set())
        semantic(b, cfg, resumed, i, set())
        assert canonical(n, i, 'aim') == canonical(roundtrip, i, 'aim')
        assert canonical(n, i, 'aim') == canonical(changed_aim, i, 'aim')
        assert D.battle_digest(altered_py) == D.battle_digest(b)
        if i in b.entities:
            a = b.entities[i]
            pa = altered_py.entities[i]
            assert (a.pp_t, a.position, a.hit_entity_ids) == (pa.pp_t, pa.position, pa.hit_entity_ids)
            info['trajectory'].append([a.pp_t, a.position.x, a.position.y, sorted(a.hit_entity_ids)])
        else:
            assert age == 31, (age, 'wrong expiry')
            break
        step(b, [n, resumed, roundtrip, changed_aim], {}, t+age+1)
        altered_py.step()
        if age == 0:
            meaningful.step(1)
            assert canonical(meaningful, i, 'aim') != canonical(n, i, 'aim'), 'nonzero pp_t control not live'
    assert i not in b.entities and i not in altered_py.entities
    assert any(x[0] == 16 for x in info['trajectory']), 'return leg not covered'
    info.update(expired=True, python_target_perturbation_equal=True, native_aim_perturbation_equal=True,
                native_snapshot_roundtrip_equal=True, nonzero_pp_t_control_detected=True)
    info['comparator_controls'] = ['nonzero_pp_t', 'changed_pp_origin', 'changed_pp_apex', 'changed_hit_ids',
                                   'hit_id_permutation_equal', 'hit_id_multiplicity_retained']
    return info


def shot_origin():
    seq, _ = C.CASES['mk_target_dies']
    b, cfg, n, by = setup(seq)
    for t in range(81):
        step(b, [n], by, t)
    p = live_entity(b.entities[11], b, cfg)
    q = next(e for e in state(n)['entities'] if e['id'] == 11)
    assert t == 80 and p['class'] == q['class'] == 'Projectile'
    assert p['projectile_origin'] != q['projectile_origin']
    keys = ('name', 'child_count', 'child_damage', 'child_range', 'child_speed', 'child_radius', 'homing')
    info = dict(case='mk_target_dies', first=t, id=11, python_origin=p['projectile_origin'],
                native_origin=q['projectile_origin'], python_stats={k:p['stats'].get(k, 0) for k in keys},
                native_stats={k:q['stats'].get(k, 0) for k in keys},
                shot_target=q.get('shot_target'), aim=q['aim'], source_character=q['source_character'])
    info.update(python_spell_name=p.get('spell_name'), native_spell_name=q.get('spell_name'),
                python_piercing=p.get('piercing'), native_piercing=q.get('piercing'))
    # An active child reader is not normalized away: this bounded case must take its immediate guard.
    assert q['stats'].get('child_damage', 0) <= 0 or q['stats'].get('child_range', 0) <= 0, info
    assert p.get('spell_name') == q.get('spell_name') == 'Arrows', info
    assert 'projectile_origin' not in field_diff(p, q), field_diff(p, q)
    for key, value in (('child_count', 1), ('child_damage', 100), ('child_range', 1000)):
        altered = deepcopy(q); altered['stats'][key] = value
        assert 'projectile_origin' in field_diff(p, altered), ('masked origin with changed spec', key)
    altered = deepcopy(q)
    altered['stats'].update(child_count=1, child_damage=100, child_range=1000)
    assert 'projectile_origin' in field_diff(p, altered), 'child-capable origin masked'
    altered = deepcopy(q); altered.pop('spell_name', None)
    assert 'projectile_origin' in field_diff(p, altered), 'unproven path masked'
    resumed = D.clasher_core.BattleState(D.snapshot(b, cfg))
    roundtrip = D.clasher_core.BattleState(n.snapshot())
    changed = state(n)
    next(e for e in changed['entities'] if e['id'] == 11)['projectile_origin'] = [-99, 99]
    changed_origin = D.clasher_core.BattleState(json.dumps(changed))
    info['trace'] = []
    for j in range(40):
        assert canonical(n, 11, 'projectile_origin') == canonical(roundtrip, 11, 'projectile_origin')
        assert canonical(n, 11, 'projectile_origin') == canonical(changed_origin, 11, 'projectile_origin')
        # Focus the export continuation on its full shot state plus positions/HP of every recipient.
        for other in (resumed, roundtrip, changed_origin):
            assert other.digest() == n.digest()
        qs = next((e for e in state(n)['entities'] if e['id'] == 11), None)
        rs = next((e for e in state(resumed)['entities'] if e['id'] == 11), None)
        if qs is None:
            assert rs is None
            info['expired_after'] = j
            break
        assert rs is not None
        # Homing aim is re-read next update: export uses live target position, native retains last aim.
        keys_to_check = ('x', 'y', 'hp', 'shot_target', 'alive', 'hit_ids') + (('aim',) if j else ())
        for k in keys_to_check:
            assert S.norm(qs.get(k)) == S.norm(rs.get(k)), (k, qs.get(k), rs.get(k))
        info['trace'].append([b.tick, qs['x'], qs['y'], qs['aim'], qs.get('shot_target')])
        step(b, [n, resumed, roundtrip, changed_origin], by, 81+j)
    assert 'expired_after' in info, 'shot failed to expire in bounded follow-up'
    info.update(child_reader_guarded=True, python_snapshot_continuation_equal=True,
                native_origin_perturbation_equal=True,
                comparator_controls=['changed_child_count', 'changed_child_damage', 'changed_child_range',
                                     'child_capable_origin', 'unproven_spell_identity'])
    return info


if __name__ == '__main__':
    out = dict(native_sha256=hashlib.sha256(Path(D.clasher_core.__file__).read_bytes()).hexdigest(), cases=[])
    for probe in (axe, shot_origin):
        out['cases'].append(probe())
        Path(sys.argv[1]).write_text(json.dumps(out, indent=2))
        print('PASS', out['cases'][-1]['case'], flush=True)
    print('PASS 2 bounded continuation cases; no sweep/build', flush=True)
