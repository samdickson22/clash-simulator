"""Prospective bounded full-state regressions; execute only on reviewed exact native.

These explicitly constructed robustness fixtures are NOT natural reachability
evidence. Old B2 captures remain immutable and are never translated into C1 dash
schema. Use the separately approved semantic-v1 comparator without new exemptions.
This module does not launch jobs, build, contact hosts, or alter input artifacts.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import traceback
from types import ModuleType

if sys.flags.optimize:
    raise RuntimeError('unoptimized Python is required for strict witness assertions')

import differential as D


CONTRACT_SHA = '8ca5826c87c22aa288065cdb2655f06436409fe05cae9d029684d1f89e3dd4e3'
FILL = ('Knight', 'Giant', 'Archers', 'Musketeer')


def load_contract(path):
    source = path.read_bytes()
    assert hashlib.sha256(source).hexdigest() == CONTRACT_SHA
    contract = ModuleType('shared_troop_frozen_contract')
    contract.__file__ = str(path)
    exec(compile(source,str(path),'exec'),contract.__dict__)
    assert contract.VERSION == 'b2-semantic-snapshot-v1'
    return contract


def point(x, y, seat):
    return D.Position(x if seat == 0 else 18-x, y if seat == 0 else 32-y)


def setup(names, seat):
    cards = tuple(dict.fromkeys(tuple(n for _, n, _, _ in names)+('Zap',)+FILL))[:8]
    b = D.initial(7, cards=cards)
    for owner, player in enumerate(b.players):
        wanted = list(dict.fromkeys(n for s, n, _, _ in names if s == owner))
        if owner == 1-seat:
            wanted.append('Zap')
        player.elixir = 10
        player.hand = (wanted+[n for n in cards if n not in wanted])[:4]
        player.cycle_queue.clear(); player.cycle_queue.extend(n for n in cards if n not in player.hand)
    identities = []
    for owner, name, x, y in names:
        before = set(b.entities)
        assert b.deploy_card(owner, name, point(x, y, seat))
        created = [e for i, e in b.entities.items() if i not in before and type(e).__name__ == 'Troop']
        assert len(created) == 1
        identities.append(created[0].id)
    for _ in range(20):
        b.step()
    return b, D.config(cards), identities


def snapshot(b, cfg, contract):
    return json.dumps(contract.committed_projectile_aims(json.loads(D.snapshot(b, cfg)), b.entities))


def compare(b, cfg, native, contract):
    expected = json.loads(D.clasher_core.BattleState(snapshot(b, cfg, contract)).snapshot())
    actual = json.loads(native.snapshot())
    differences, applicability, raw = contract.compare_states(expected, actual, b.entities)
    return differences, applicability, raw, native.digest() == D.battle_digest(b)


def continuation(name, b, cfg, contract, ticks, *, schedule=None, watched=None, record=None):
    """Compare every frame, uninterrupted, battle-cloned and reloaded native arms.

    A fresh Python battle clone runs independently too. All failures are retained;
    no family/field filtering converts a failed full-state result into a pass.
    """
    encoded = snapshot(b, cfg, contract)
    result = record if record is not None else {}
    result.update(case=name, fixture='explicit-current-source-robustness-v1',
                  initial=json.loads(encoded), first_context=None, differences=[], frames=[], errors=[])
    live = D.clasher_core.BattleState(encoded)
    arms = dict(uninterrupted=live, clone=live.clone(), reload=D.clasher_core.BattleState(live.snapshot()))
    python_clone = b.clone()
    for offset in range(ticks):
        if schedule:
            schedule(offset, b, python_clone, arms)
        before = dict(python=json.loads(snapshot(b, cfg, contract)),
                      native=json.loads(arms['uninterrupted'].snapshot()))
        result['last_before'] = before
        b.step(); python_clone.step()
        if D.battle_digest(python_clone) != D.battle_digest(b):
            result['errors'].append(dict(offset=offset,kind='python-clone-digest'))
        # Full exported states, including clocks/history, are compared between Python clones.
        clone_delta = list(contract.differences(json.loads(snapshot(b,cfg,contract)),
                                               json.loads(snapshot(python_clone,cfg,contract))))
        if clone_delta:
            result['errors'].append(dict(offset=offset,kind='python-clone-state',differences=clone_delta))
        for arm in arms.values():
            arm.step(1)
        outcomes = {}
        for label, arm in arms.items():
            delta, applicability, raw, equal = compare(b, cfg, arm, contract)
            outcomes[label] = dict(differences=delta, digest_equal=equal,
                                   applicability=applicability, raw_differences=raw)
            if delta or not equal:
                result['differences'].append(dict(offset=offset, arm=label, **outcomes[label]))
                if result['first_context'] is None:
                    result['first_context'] = dict(offset=offset, arm=label, before=before,
                        after=dict(python=json.loads(snapshot(b, cfg, contract)), native=json.loads(arm.snapshot())))
        state = json.loads(arms['uninterrupted'].snapshot())
        selected = [e for e in state['entities'] if e['id'] == watched]
        result['frames'].append(dict(offset=offset, tick=b.tick,
            actor=None if not selected else {k:selected[0].get(k) for k in
                ('id','x','y','alive','target','facing','direction','route','dash','stun','frozen_moving','entity_kind','spirit',
                 'shot_target','aim','clock','clock_initialized','started','windup','stats')},
            arms_equal=all(arm.snapshot() == arms['uninterrupted'].snapshot() for arm in arms.values())))
        if not result['frames'][-1]['arms_equal']:
            result['errors'].append(dict(offset=offset,kind='native-clone-reload-state',
                differences={label:list(contract.differences(state,json.loads(arm.snapshot())))
                             for label,arm in arms.items()}))
    result['ticks'] = ticks
    result['status'] = 'FOCUSED_FAIL' if result['differences'] or result['errors'] else 'FOCUSED_PASS'
    return result


def zap_fixture(seat, variant):
    b, cfg, ids = setup([(seat,'Bandit',9,10.5),(1-seat,'Knight',9,17.5)], seat)
    actor, target = (b.entities[i] for i in ids)
    actor.position = point(9,10.5,seat)
    target.position = point(9,17.5,seat)
    mechanic = next(m for m in actor.mechanics if type(m).__name__ == 'BanditDash')
    # Explicitly construct a CURRENT-schema forced state, not a translated old root.
    actor._bandit_seen_target = target.id
    actor.target_id = None
    mechanic._launch_dash(actor, target)
    actor._native_ground_route_cells = [(21,23),(22,24),(23,25)] if seat == 0 else [(21,40),(22,39),(23,38)]
    actor._native_ground_route_direction = (181,181 if seat == 0 else -181)
    actor._facing_x_units, actor._facing_y_units = 1750, 1250 if seat == 0 else -1250
    actor.stun_timer = 0.5 if variant != 'no_stun' else 0
    actor._native_moving_when_frozen = variant != 'not_frozen'
    if variant == 'empty_route':
        actor._native_ground_route_cells = []
    if variant == 'external':
        actor.accumulate_movement_vector_units(250,-500 if seat == 0 else 500,bypasses_cap=True)
    return b, cfg, actor.id


def heading_fixture(seat):
    b, cfg, ids = setup([(seat,'Knight',9,10.5),(1-seat,'ElectroDragon',9,17.5)],seat)
    target, actor = (b.entities[i] for i in ids)
    target.position = point(9,17.5,seat)
    actor.position = point(9,17.5,seat)
    actor.target_id = None
    actor._facing_x_units, actor._facing_y_units = 0, -1000 if seat == 0 else 1000
    return b, cfg, actor.id


def spirit_fixture(seat, variant):
    b, cfg, ids = setup([(seat,'Knight',9,10.5),(1-seat,'IceSpirit',9,17.5)],seat)
    target, actor = (b.entities[i] for i in ids)
    target.position = point(9,17.5,seat)
    actor.position = point(9,19.5,seat)
    actor.attack_cooldown = 0
    actor._ordinary_force_due = True
    if variant == 'uniform':
        actor.apply_slow(0.05,0.7)
    elif variant == 'overlap':
        actor.apply_slow(0.05,0.7)
        actor.apply_slow(0.2,0.333,attack_speed_multiplier=0.8,spawn_speed_multiplier=1)
    elif variant == 'above_one':
        actor.apply_slow(0.1,1.25,attack_speed_multiplier=0.5,spawn_speed_multiplier=1)
    elif variant == 'move_mode':
        actor.movement_mode_multiplier = 0
    elif variant == 'haste':
        actor.apply_haste(0.1,1.3,1.2,1.1)
    return b, cfg, actor.id


def cleanup_fixture(seat, variant):
    """Explicit retained-clock controls, followed by a real lethal Zap in flight."""
    b, cfg, identity = spirit_fixture(seat, 'plain')
    target = next(e for e in b.entities.values() if e.player_id == seat and type(e).__name__ == 'Troop')
    target.hitpoints = 1
    b.step()  # Real Python launch; this probe does not fake kind or flight payload.
    actor = b.entities[identity]
    assert actor._self_projectile_launched and actor.entity_kind == 2
    assert actor._ordinary_clock is not None
    if variant == 'no_clock':
        actor._ordinary_clock = None
        actor._attack_windup_active = actor._has_attacked_once = True
    else:
        from clasher.ordinary_combat_clock import publish
        actor._ordinary_clock.hit_timeline_ms = 0 if variant == 'zero_started' else 300
        started = variant != 'positive_not_started'
        actor._attack_windup_active = actor._has_attacked_once = started
        actor._combat_target_pending_lethal = variant == 'pending'
        publish(actor, actor._ordinary_clock)

    def kill_target(offset, live_python, cloned_python, natives):
        if offset != 0:
            return
        position = live_python.entities[target.id].position
        for python in (live_python, cloned_python):
            assert python.deploy_card(1-seat,'Zap',D.Position(position.x,position.y))
        for native in natives.values():
            assert native.apply_action(1-seat,'Zap',position.x,position.y)

    return b, cfg, identity, kill_target


def require_witness(name, seat, result):
    """An equal run that never exercised its intended transition must fail."""
    actors = [frame['actor'] for frame in result['frames']]
    live = [actor for actor in actors if actor is not None]
    if name.startswith('zap/'):
        if name in ('zap/frozen','zap/external'):
            assert any(a['stun']>0 and a['frozen_moving'] and a['route'] and
                       (a.get('dash') or {}).get('phase')=='travel' for a in live)
            assert any(len(a['route'])<3 for a in live if a['stun']>0), 'no frozen node consumption'
    elif name == 'heading/coincident':
        assert actors[0] is not None and actors[0]['target']==7
        assert actors[0]['facing']==[0,-1000 if seat==0 else 1000], 'zero-distance heading lost'
    elif name.startswith('spirit/'):
        expected = {'uniform':0.7,'overlap':0.333,'above_one':1.25}.get(name.split('/')[1],1.0)
        assert any(a['spirit'] and a['entity_kind']==2 for a in live), 'no actual Spirit launch'
        for actor in live:
            if actor['spirit']:
                assert actor['stats']['ordinary'] is False
                assert actor['stats']['projectile_slow_multiplier']==expected
        assert actors[-1] is None, 'carrier did not reach impact/removal'
    elif name.startswith('cleanup/'):
        expected = 1 if name in ('cleanup/positive_not_started','cleanup/no_clock') else 0
        assert actors[0] is not None and actors[0]['spirit']
        assert actors[0]['target'] is None, 'lethal target-removal callback not reached'
        assert actors[0]['clock']['finish']==expected, 'retained-clock cleanup predicate lost'
        assert actors[-1] is None, 'flight did not finish after target removal'
    result['required_witness_observed'] = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    parser.add_argument('--contract', required=True, type=Path)
    parser.add_argument('--native-sha256', required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'output must be fresh; preserve old failures'
    native_path = Path(D.clasher_core.__file__)
    actual_sha = hashlib.sha256(native_path.read_bytes()).hexdigest()
    assert actual_sha == args.native_sha256, 'wrong exact native'
    contract = load_contract(args.contract)
    results = []
    for seat in (0,1):
        cases = [('zap/'+v,zap_fixture,v,20) for v in ('frozen','no_stun','not_frozen','empty_route','external')]
        cases += [('heading/coincident',heading_fixture,None,3)]
        cases += [('spirit/'+v,spirit_fixture,v,12) for v in ('plain','uniform','overlap','above_one','move_mode','haste')]
        cases += [('cleanup/'+v,cleanup_fixture,v,10) for v in ('zero_started','positive_not_started','pending','no_clock')]
        for name, fixture, variant, ticks in cases:
            result = dict(case=name,seat=seat)
            try:
                prepared = fixture(seat) if variant is None else fixture(seat,variant)
                b,cfg,identity = prepared[:3]
                result = continuation(name,b,cfg,contract,ticks,watched=identity,
                                      schedule=prepared[3] if len(prepared)==4 else None,record=result)
                require_witness(name,seat,result)
                result['seat'] = seat
            except Exception:
                error = traceback.format_exc(limit=8)
                # The shared record retains constructor and all available
                # frames/deltas even when stepping or a witness assertion fails.
                result.update(seat=seat,status='ERROR',error=error)
            results.append(result)
            print(json.dumps({k:result.get(k) for k in ('case','seat','status','ticks','error')}),flush=True)
    report = dict(contract=contract.VERSION,contract_sha256=CONTRACT_SHA,native_path=str(native_path),
                  native_sha256=actual_sha,status='FOCUSED_PASS' if len(results)==32 and all(r['status']=='FOCUSED_PASS' for r in results) else 'FOCUSED_FAIL',
                  engine_acceptance='NOT_GRANTED',scope='32 explicit robustness continuations; not natural gameplay or full integrated coverage',results=results)
    if hashlib.sha256(native_path.read_bytes()).hexdigest() != actual_sha:
        report.update(status='FOCUSED_FAIL',provenance_error='native file changed during probe')
    with args.output.open('x') as output:
        json.dump(report,output,indent=1)
    raise SystemExit(0 if report['status']=='FOCUSED_PASS' else 1)


if __name__ == '__main__':
    main()
