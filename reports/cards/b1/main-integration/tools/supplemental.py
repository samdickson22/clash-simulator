"""Combat carry boundary and observable once-only container first-step witnesses."""
import json
from pathlib import Path
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'tools'))
import review_regressions as h


def require(ok, detail):
    if not ok:
        raise RuntimeError(detail)


def combat_carry(seat):
    py, cfg = h.fresh(('Tombstone', 'GoblinGiant', 'Knight', 'Zap'))
    pt = lambda x,y: (x,y) if seat == 0 else (18-x,32-y)
    py.players[seat].hand[0] = 'Tombstone'
    require(py.deploy_card(seat, 'Tombstone', h.Position(*pt(4.5,10.5))), 'deploy')
    for _ in range(25):
        py.step()
    tomb = next(e for e in py.entities.values() if getattr(e.card_stats,'name','') == 'Tombstone')
    tomb.hitpoints = 200
    giant = h.spawn(py, 'GoblinGiant', seat, *pt(5.5,10.5))
    attacker = h.spawn(py, 'Knight', 1-seat, *pt(4.5,12))
    attacker.hitpoints = 5000  # keep the controlled killer alive through rider shots
    native = h.clasher_core.BattleState(h.snapshot(py,cfg))
    emitted, at_carry, witnesses = {}, {}, []
    first = py._first_update_spawned
    mechanic = giant._rider_mechanic
    carry = mechanic.carry

    def observe(child, **kw):
        first(child, **kw)
        if kw.get('collide') is False:
            emitted[child.id] = py.tick

    def capture(mount, facing):
        carry(mount, facing)
        # Inside the combat/movement boundary, after synchronous callbacks.
        at_carry.clear()
        if not tomb.is_alive and emitted:
            for e in [giant, *mechanic.riders, *(py.entities[k] for k in emitted if k in py.entities)]:
                at_carry[e.id] = (e.position.x,e.position.y,e.hitpoints)

    py._first_update_spawned = observe
    mechanic.carry = capture
    for _ in range(180):
        py.step()
        phases = dict(json.loads(native.debug_step()))
        h.audited_state(py,native,cfg)
        if at_carry and any(t == py.tick for t in emitted.values()):
            rows = {e['id']:e for e in phases['combat']['entities']}
            for key, expected in at_carry.items():
                require(key in rows and (rows[key]['x'],rows[key]['y'],rows[key]['hp']) == expected,
                        ('combat carry boundary',py.tick,key,expected,rows.get(key)))
            require(all(rows[r.id].get('mount') == giant.id for r in mechanic.riders), 'combat mount links')
            witnesses.append(dict(tick=py.tick, emitted=dict(emitted), graph=list(at_carry)))
            break
    require(witnesses and not tomb.is_alive and giant.is_alive, 'no melee-death-before-carry witness')
    del py._first_update_spawned
    del mechanic.carry
    h.continuation(py,native,cfg,ticks=12)
    return witnesses


def once_only(seat):
    py,cfg = h.fresh(('SkeletonBalloon','GoblinGiant','Knight','Zap'))
    pt = lambda x,y: (x,y) if seat == 0 else (18-x,32-y)
    h.spawn(py,'GoblinGiant',seat,*pt(5.5,10.5))
    parent = h.spawn(py,'SkeletonBalloon',seat,*pt(4.5,10.5))
    parent.take_damage(parent.hitpoints)
    bomb = next(e for e in py.entities.values() if type(e).__name__ == 'TimedExplosive')
    # Scratch-only control removes both Freeze and deployment masking. The
    # first movement must be observable at birth, before the next normal tick.
    bomb.death_spawn_deploy_time = 0
    for row in cfg['bomb_children'][bomb.card_stats.name]:
        row['deploy'] = 0
    native = h.clasher_core.BattleState(h.snapshot(py,cfg))
    events = []
    first = py._first_update_spawned

    def observe(child,**kw):
        before=(child.position.x,child.position.y)
        first(child,**kw)
        events.append(dict(id=child.id,tick=py.tick,before=before,
                           after=(child.position.x,child.position.y),target=child.target_id))

    py._first_update_spawned=observe
    for _ in range(int((bomb.explosion_timer+.2)/py.dt)+4):
        py.step();native.step()
        actual=h.audited_state(py,native,cfg)
        rows={e['id']:e for e in actual['entities']}
        for e in events:
            if e['tick'] == py.tick:
                require((rows[e['id']]['x'],rows[e['id']]['y']) == e['after'],
                        ('native first step missing or repeated',e,rows[e['id']]))
    require(len(events)==bomb.death_spawn_count and len({e['id'] for e in events})==len(events),
            ('callback count',events))
    require(any(e['before'] != e['after'] and e['target'] is not None for e in events),
            ('no observable first-step movement/target witness',events))
    del py._first_update_spawned
    h.continuation(py,native,cfg,ticks=12)
    return events


results=[]
for seat in (0,1):
    for name,fn in (('melee-before-carry',combat_carry),('unfrozen-zero-deploy-once',once_only)):
        try:
            row=dict(name=name,seat=seat,ok=True,witness=fn(seat))
        except Exception:
            row=dict(name=name,seat=seat,ok=False,error=traceback.format_exc())
        results.append(row);print(json.dumps(row),flush=True)
report=dict(total=len(results),passed=sum(r['ok'] for r in results),tests=results,
            note='Explicit phase/first-step positions plus exact native restart equality; raw cross-engine state is not certified.')
with open(sys.argv[1],'x') as f:
    json.dump(report,f,indent=2)
require(report['passed']==report['total']==4,report)
