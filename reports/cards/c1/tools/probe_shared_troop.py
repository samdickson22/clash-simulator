"""Prospective bounded full-state regressions; execute only on reviewed exact native.

These explicitly constructed robustness fixtures are NOT natural reachability
evidence. Old B2 captures remain immutable and are never translated into C1 dash
schema. Use the separately approved semantic-v1 comparator without new exemptions.
This module does not launch jobs, build, contact hosts, or alter input artifacts.
"""
import argparse
import hashlib
import json
import math
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


def validate_templates(result, contract, label, state, offset):
    """The frozen comparator's cache exclusions require this separate proof."""
    check = dict(arm=label, offset=offset)
    result.setdefault('template_checks', []).append(check)
    try:
        check.update(paths=contract.fresh_troop_templates(state), valid=True)
    except Exception:
        check.update(valid=False, error=traceback.format_exc(limit=4), root=state)
        raise


def watched_row(state, watched):
    return next((row for row in state['entities'] if row['id'] == watched), None)


def movement_observation(actor):
    """Read-only evidence at the actual post-dash/pre-external finalizer boundary."""
    return dict(position=[round(actor.position.x*1000), round(actor.position.y*1000)],
        route=[list(cell) for cell in (actor._native_ground_route_cells or [])],
        direction=list(actor._native_ground_route_direction or (0,0)),
        facing=[actor._facing_x_units, actor._facing_y_units],
        phase=actor._bandit_state, stun=actor.stun_timer,
        frozen_moving=actor._native_moving_when_frozen,
        external=[0,0] if actor._pending_movement_consumed else
            [round(actor._pending_movement_x*1000), round(actor._pending_movement_y*1000)])


def observe_finalization(actor, events):
    # Install after battle.clone(), separately on each Python arm. The closure
    # calls that arm's original bound method once and never changes engine state.
    original = actor.finish_movement_tick
    def observed(battle):
        event = dict(before=movement_observation(actor))
        events.append(event)
        try:
            return original(battle)
        finally:
            event['after'] = movement_observation(actor)
    actor.finish_movement_tick = observed


def continuation(name, b, cfg, contract, ticks, *, schedule=None, watched=None, record=None):
    """Compare every frame, uninterrupted, battle-cloned and reloaded native arms.

    A fresh Python battle clone runs independently too. All failures are retained;
    no family/field filtering converts a failed full-state result into a pass.
    """
    encoded = snapshot(b, cfg, contract)
    result = record if record is not None else {}
    result.update(case=name, fixture='explicit-current-source-robustness-v1',
                  watched=watched, initial=json.loads(encoded), first_context=None,
                  differences=[], frames=[], errors=[], template_checks=[], zap_transition_roots=[])
    validate_templates(result,contract,'python/initial',result['initial'],-1)
    live = D.clasher_core.BattleState(encoded)
    arms = dict(uninterrupted=live, clone=live.clone(), reload=D.clasher_core.BattleState(live.snapshot()))
    python_clone = b.clone()
    for label, arm in arms.items():
        validate_templates(result,contract,label+'/initial',json.loads(arm.snapshot()),-1)
    validate_templates(result,contract,'python_clone/initial',json.loads(snapshot(python_clone,cfg,contract)),-1)
    movement_events = dict(python=[],python_clone=[])
    if name.startswith('zap/'):
        observe_finalization(b.entities[watched],movement_events['python'])
        observe_finalization(python_clone.entities[watched],movement_events['python_clone'])
    for offset in range(ticks):
        if schedule:
            schedule(offset, b, python_clone, arms)
        before = dict(python=json.loads(snapshot(b, cfg, contract)),
                      natives={label:json.loads(arm.snapshot()) for label,arm in arms.items()})
        before['native'] = before['natives']['uninterrupted']
        result['last_before'] = before
        starts = {label:len(events) for label,events in movement_events.items()}
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
        after = dict(python=json.loads(snapshot(b,cfg,contract)),
                     natives={label:json.loads(arm.snapshot()) for label,arm in arms.items()})
        for label,state in dict(python=after['python'],
                python_clone=json.loads(snapshot(python_clone,cfg,contract)),**after['natives']).items():
            validate_templates(result,contract,label,state,offset)
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
        state = after['natives']['uninterrupted']
        selected = [e for e in state['entities'] if e['id'] == watched]
        result['frames'].append(dict(offset=offset, tick=b.tick,
            actor=None if not selected else {k:selected[0].get(k) for k in
                ('id','x','y','alive','target','facing','direction','route','dash','stun','frozen_moving','entity_kind','spirit',
                 'shot_target','aim','clock','clock_initialized','started','windup','stats')},
            arms_equal=all(arm.snapshot() == arms['uninterrupted'].snapshot() for arm in arms.values())))
        if name.startswith('zap/'):
            frame = result['frames'][-1]
            frame['movement'] = {label:events[starts[label]:] for label,events in movement_events.items()}
            frame['transition'] = dict(
                python=dict(before=watched_row(before['python'],watched),after=watched_row(after['python'],watched)),
                natives={label:dict(before=watched_row(before['natives'][label],watched),after=watched_row(root,watched))
                         for label,root in after['natives'].items()})
            pre,post = frame['transition']['python']['before'],frame['transition']['python']['after']
            if offset == 0 or (pre is not None and post is not None and
                    (pre.get('dash') or {}).get('phase')=='travel' and pre['route'] != post['route']):
                result['zap_transition_roots'].append(dict(offset=offset,before=before,after=after))
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
        # Cross the reached-node threshold on the first transport frame. The
        # pre-external and post-external projections must disagree in the witness.
        actor.accumulate_movement_vector_units(250,1000 if seat == 0 else -1000,bypasses_cap=True)
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


def trunc_div(value, divisor):
    return (-1 if value < 0 else 1)*(abs(value)//divisor)


def projected_remaining(head, position, direction):
    return sum(trunc_div(d*(c*500+250-p),256) for c,p,d in zip(head,position,direction))


def require_zap_witness(name, seat, result):
    variant = name.split('/')[1]
    assert variant in ('frozen','external','no_stun','not_frozen','empty_route')
    initial = watched_row(result['initial'],result['watched'])
    assert initial is not None and initial['alive'], 'missing constructor actor'
    route = [] if variant=='empty_route' else ([[21,23],[22,24],[23,25]] if seat==0 else [[21,40],[22,39],[23,38]])
    frozen = variant!='not_frozen'
    assert (initial.get('dash') or {}).get('phase')=='travel'
    assert initial['route']==route and initial['direction']==[181,181 if seat==0 else -181]
    assert initial['frozen_moving'] is frozen
    assert (initial['stun']==0 if variant=='no_stun' else initial['stun']>0)
    assert result['frames'] and all(frame['actor'] is not None for frame in result['frames']), 'missing continuation actor'
    pops = []
    for index, frame in enumerate(result['frames']):
        transition = frame['transition']
        before,after = transition['python']['before'],transition['python']['after']
        assert before is not None and after is not None
        if (before.get('dash') or {}).get('phase')!='travel':
            continue
        events = frame['movement']['python']
        assert len(events)==1 and frame['movement']['python_clone']==events, 'missing/unequal finalizer observations'
        pre,post = events[0]['before'],events[0]['after']
        # Prove ownership at the finalizer boundary, not a later ordinary walk.
        if pre['phase']!='travel':
            assert index!=0, 'first frame did not retain travel'
            continue
        assert pre['position'] != [round(before['x']*1000),round(before['y']*1000)], 'no dash transport'
        assert pre['route']==before['route'] and pre['direction']==before['direction']
        assert post['phase']=='travel'
        if index==0:
            assert pre['route']==route and pre['frozen_moving'] is frozen
            assert (pre['stun']==0 if variant=='no_stun' else pre['stun']>0)
            if variant!='external':
                assert pre['external']==[0,0], 'unexpected vector in isolated guard control'
        expected_position = [max(0,min(limit,p+v)) for p,v,limit in zip(pre['position'],pre['external'],(17999,31999))]
        assert post['position']==expected_position, 'external displacement not consumed at finalization'
        active = pre['stun']>0 and pre['frozen_moving'] and pre['route']
        expected_route,expected_direction,expected_facing = pre['route'],pre['direction'],pre['facing']
        if active:
            head = pre['route'][0]
            vector = [c*500+250-p for c,p in zip(head,pre['position'])]
            if vector != [0,0]:
                expected_facing = vector
            if projected_remaining(head,post['position'],pre['direction']) < 1001:
                expected_route = pre['route'][1:]
                delta = [c*500+250-p for c,p in zip(expected_route[0],post['position'])] if expected_route else [0,0]
                length = max(1,math.isqrt(sum(d*d for d in delta)))
                expected_direction = [trunc_div(d*256,length) for d in delta]
                pops.append(frame['offset'])
        assert post['facing']==expected_facing, 'heading used post-external position'
        assert post['route']==expected_route, 'wrong threshold or excessive node consumption'
        assert post['direction']==expected_direction, 'retained/new route direction lost'
        for pair in [transition['python'],*transition['natives'].values()]:
            assert pair['before'] is not None and pair['after'] is not None
            assert (pair['before'].get('dash') or {}).get('phase')=='travel'
            assert pair['before']['route']==before['route'] and pair['before']['direction']==before['direction']
            assert [pair['before'][key] for key in ('x','y','stun','frozen_moving','facing')]==[before[key] for key in ('x','y','stun','frozen_moving','facing')]
            row = pair['after']
            assert (row.get('dash') or {}).get('phase')=='travel'
            assert [round(row['x']*1000),round(row['y']*1000)]==post['position']
            assert row['facing']==expected_facing and row['route']==expected_route and row['direction']==expected_direction
        if variant=='external' and index==0:
            assert pre['external']==[250,1000 if seat==0 else -1000], 'external control not reached'
            assert active and projected_remaining(head,pre['position'],pre['direction'])>=1001
            assert projected_remaining(head,post['position'],pre['direction'])<1001, 'external vector did not distinguish advancement order'
            assert expected_facing != [c*500+250-p for c,p in zip(head,post['position'])]
    assert (result['frames'][0]['transition']['python']['before'].get('dash') or {}).get('phase')=='travel'
    if variant in ('frozen','external'):
        assert pops, 'no node consumption while dash still owns travel'
    roots = {pair['offset']:pair for pair in result['zap_transition_roots']}
    assert {0,*pops} <= roots.keys(), 'missing exact paired transition roots'
    for offset in {0,*pops}:
        frame = next(frame for frame in result['frames'] if frame['offset']==offset)
        for boundary in ('before','after'):
            assert watched_row(roots[offset][boundary]['python'],result['watched'])==frame['transition']['python'][boundary]
            for label,pair in frame['transition']['natives'].items():
                assert watched_row(roots[offset][boundary]['natives'][label],result['watched'])==pair[boundary]
    result['zap_witness_offsets'] = sorted({0,*pops})


def require_witness(name, seat, result):
    """An equal run that never exercised its intended transition must fail."""
    actors = [frame['actor'] for frame in result['frames']]
    live = [actor for actor in actors if actor is not None]
    if name.startswith('zap/'):
        require_zap_witness(name,seat,result)
    elif name == 'heading/coincident':
        assert actors[0] is not None and actors[0]['target']==7
        assert actors[0]['facing']==[0,-1000 if seat==0 else 1000], 'zero-distance heading lost'
    elif name.startswith('spirit/'):
        assert any(a['spirit'] and a['entity_kind']==2 for a in live), 'no actual Spirit launch'
        # The carrier keeps its character template stats through launch (troop.rs launch_spirit;
        # differential.entity exports the same), whatever the slow/haste/mode axes; the full-state
        # comparison against Python every tick covers the rest.
        # Native's own import of the pre-step state (the native stats representation).
        initial = watched_row(json.loads(D.clasher_core.BattleState(json.dumps(result['initial'])).snapshot()),
                              result['watched'])
        template = initial['stats']
        assert not initial['spirit'] and template['ordinary'] is True
        for actor in live:
            assert actor['stats']==template, 'carrier stats changed at launch'
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
