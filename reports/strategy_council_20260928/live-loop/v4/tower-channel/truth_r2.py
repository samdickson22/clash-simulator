"""Training-only tower truth. Absence labels never enter the pixel runtime.

Native object snapshots are complete collections with a coherent observation
fence. A permanent princess disappearance after positive HP, corroborated by
subsequent ongoing snapshots and living Kings, is destruction. The interval
(last positive tick, first absent tick] bounds the otherwise unobserved death.
"""
import bisect
from extract import ANCHORS


def towers(row):
    found = {}
    fence = row.get('fence', {})
    if not fence.get('no_logic_step_during_observation'):
        return found
    for o in row['objects']:
        for s, (owner, x, y) in enumerate(ANCHORS):
            if (o.get('owner'), o.get('card_id'), o.get('x'), o.get('y'), o.get('max_hp')) != (
                    owner, -1, int(x*1000), int(y*1000), 4824 if s%3 == 0 else 3052):
                continue
            if s in found:
                raise ValueError('Duplicate tower anchor')
            if type(o.get('hp')) is int and o['hp'] > 0:
                found[s] = o
    return found


def derive(objects, rich, frames, terminal):
    if any(b['tick'] < a['tick'] for a, b in zip(objects, objects[1:])):
        raise ValueError('Backwards ordinary snapshots')
    unique = {}
    duplicates = 0
    for row in objects:
        if row['tick'] in unique:
            duplicates += 1
            old = towers(unique[row['tick']])
            new = towers(row)
            signature = lambda ts: {s:(o['native_id'],o['hp']) for s,o in ts.items()}
            if signature(old) != signature(new):
                raise ValueError('Conflicting same-tick tower snapshots')
        else:
            unique[row['tick']] = row
    objects = list(unique.values())
    snapshots = [towers(r) for r in objects]
    ticks = [r['tick'] for r in objects]
    events = []
    for s in (1, 2, 4, 5):
        seen = [i for i, ts in enumerate(snapshots) if s in ts]
        if not seen:
            continue  # A tower missing at capture start has no positive witness.
        j = seen[-1]+1
        if j+1 >= len(objects):
            continue
        previous, absent, later = objects[j-1], objects[j], objects[j+1]
        if absent['tick'] >= terminal['tick'] or later['tick'] >= terminal['tick']:
            continue  # Last-frame/global teardown cannot establish death.
        if not all(0 in snapshots[k] and 3 in snapshots[k] for k in (j, j+1)):
            continue
        if not all(objects[k].get('fence', {}).get('no_logic_step_during_observation') for k in (j, j+1)):
            continue
        if any(s in ts for ts in snapshots[j:]):
            raise ValueError('Disappeared tower reappeared')
        events.append(dict(slot=s, last_positive_tick=previous['tick'],
                           destruction_tick=absent['tick'], confirmed_absent_tick=later['tick'],
                           last_hp=snapshots[j-1][s]['hp'],
                           native_id=snapshots[j-1][s]['native_id']))
    rich_by_tick = {r['tick']: {o['nativeObjectId']: o for o in r['objects']} for r in rich}
    if len(rich_by_tick) != len(rich):
        raise ValueError('Repeated rich tick')
    labels = []
    damage_tick = {s:next((r['tick'] for r,ts in zip(objects,snapshots) if s in ts and ts[s]['hp'] < 4824),float('inf')) for s in (0,3)}
    for frame in frames:
        tick = (frame['tick_lo']+frame['tick_hi'])/2
        j = bisect.bisect_right(ticks, tick)-1
        states, hp, active = [None]*6, [None]*6, [None]*6
        if j >= 0 and tick < terminal['tick'] and tick-ticks[j] <= 5:
            ts = snapshots[j]
            for s, o in ts.items():
                states[s] = 'alive'
                r = rich_by_tick.get(ticks[j], {}).get(o['native_id'])
                if r and all(o.get(k) == r.get(v) for k,v in (
                        ('owner','owner'),('card_id','cardId'),('x','x'),('y','y'),('hp','hp'),('max_hp','maxHp'))) and r.get('visibilityState') == 'visible' and (r.get('phaseRuntime') or {}).get('deployRemainingMs') == 0:
                    hp[s] = o['hp']
            for e in events:
                if e['last_positive_tick'] < tick < e['destruction_tick']:
                    states[e['slot']] = None
                    hp[e['slot']] = None
                if tick >= e['destruction_tick']:
                    states[e['slot']] = 'destroyed'
                    hp[e['slot']] = 0
            for s in (0,3):
                if s not in ts:
                    continue
                # Wake rule is public. No wake label when the capture begins
                # mid-match unless positive HP loss / princess fall witnesses it.
                owner = s//3
                wake = any(e['slot']//3 == owner and e['destruction_tick'] <= tick for e in events)
                damaged = ticks[j] >= damage_tick[s]
                intact_at_start = all(q in snapshots[0] and snapshots[0][q]['hp'] == (4824 if q%3 == 0 else 3052) for q in range(s,s+3))
                active[s] = True if wake or damaged else (False if intact_at_start else None)
        labels.append(dict(tick=tick, states=states, hp=hp, active=active))
    return dict(events=events, labels=labels, duplicate_identical_ticks=duplicates,
                schema_keys=dict(ordinary=list(objects[0]), rich=list(rich[0]) if rich else []),
                crown_score_fields=[k for r in rich for p in r.get('players',[]) for k in p if any(t in k.lower() for t in ('crown','score','winner'))],
                terminal=terminal)
