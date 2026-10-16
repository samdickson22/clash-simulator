"""Semantic-v1 non-Troop-cache applicability witnesses, both seats.

Seed only the native delivery/rolling source's private cache with a sentinel.
Continue actual child Troops for 20 ticks, compare independent actual base speed,
retain all snapshot differences and poison a child cache to prove applicability
changes at materialization. No source/child cache is exempted once class=Troop.
"""
import copy
import json
import sys
import traceback
from differential import config, initial, clasher_core, Position, battle_digest
from probe_dash_semantic_v1 import probe_snapshot, full_compare
from snapshot_contract_v1 import VERSION, fresh_troop_templates, troop_speed_differences

CASES = {'barblog': ('BarbLog', 'RollingProjectile'), 'royal_delivery': ('RoyalDelivery', 'SpawnProjectile')}
SENTINEL = 137.0
FILL = ('Knight', 'Archers', 'Giant', 'Musketeer')


def one(name, seat):
    card, source_class = CASES[name]
    cards = tuple(dict.fromkeys((card,) + FILL))
    cfg = config(cards)
    b = initial(7, cards=cards)
    p = b.players[seat]
    p.hand = list(cards[:4]); p.cycle_queue.clear(); p.cycle_queue.extend(cards[4:]); p.elixir = 10.0
    point = (4.5, 10.5)
    if seat:
        point = (18 - point[0], 32 - point[1])
    assert b.deploy_card(seat, card, Position(*point)), ('required witness cast rejected', name, seat)
    for _ in range(30):
        sources = [e for e in b.entities.values() if e.is_alive and e.player_id == seat and type(e).__name__ == source_class]
        if sources:
            break
        b.step()
    assert len(sources) == 1, ('source object not found', name, source_class)
    source_id = sources[0].id
    state = json.loads(probe_snapshot(b, cfg))
    row = next(r for r in state['entities'] if r['id'] == source_id)
    row['public_speed_base'] = SENTINEL
    native = clasher_core.BattleState(json.dumps(state))
    templates = fresh_troop_templates(json.loads(native.snapshot()))
    initial_ids = set(b.entities)
    child_ids = set()
    checks = []
    first = None
    semantic_failures = []
    applicability_records = {}
    raw_first = None
    raw_differences = []
    poisoned_child_detected = False
    continuation = 0
    for tick in range(200):
        b.step(); native.step(1)
        ns = json.loads(native.snapshot())
        rows = {str(r['id']): r for r in ns['entities'] if r.get('alive', True)}
        children = [e for e in b.entities.values() if e.is_alive and e.id not in initial_ids and
                    e.player_id == seat and type(e).__name__ == 'Troop']
        for child in children:
            child_ids.add(child.id)
            actual = rows[str(child.id)]
            assert actual['class'] == 'Troop', ('child class mismatch', actual['class'])
            assert actual.get('public_speed_base') != SENTINEL, ('source cache leaked into Troop', child.id)
            speed_deltas = list(troop_speed_differences(b, {str(child.id): actual}))
            assert not speed_deltas, speed_deltas
            checks.append(dict(tick=tick, child=child.id, python_base=child._unslowed_movement_speed(),
                               native_cache=actual.get('public_speed_base'), native_fallback=actual['stats']['speed']))
            # A bad cache in a now-meaningful Troop must fail independently of unchanged positions/digest.
            poisoned = copy.deepcopy(actual); poisoned['public_speed_base'] = SENTINEL
            assert list(troop_speed_differences(b, {str(child.id): poisoned})), 'poisoned child escaped speed comparison'
            poisoned_child_detected = True
        delta, applicability, raw = full_compare(b, native, cfg)
        for item in applicability:
            key = json.dumps(item, sort_keys=True)
            if key not in applicability_records:
                applicability_records[key] = dict(item, ticks=[])
            applicability_records[key]['ticks'].append(tick)
        if raw and raw_first is None:
            raw_first, raw_differences = tick, raw
        if delta:
            if first is None:
                first = tick
            semantic_failures.extend(dict(d, tick=tick) for d in delta)
        digest_equal = native.digest() == battle_digest(b)
        assert digest_equal, ('witness continuation diverged', name, seat, tick)
        if child_ids:
            continuation += 1
        if continuation >= 20:
            break
    assert child_ids and continuation >= 20 and checks, 'no materialized Troop continuation'
    assert poisoned_child_detected, 'missing descendant negative control'
    return dict(contract=VERSION, case=name, seat=seat, source_class=source_class, source_id=source_id,
                sentinel=SENTINEL, child_ids=sorted(child_ids), continuation=continuation,
                poisoned_child_detected=poisoned_child_detected, speed_checks=checks,
                fresh_troop_templates=templates, first=first, differences=semantic_failures,
                applicability=list(applicability_records.values()), raw_first=raw_first, raw_differences=raw_differences,
                ok=first is None)


if __name__ == '__main__':
    rows = []
    for name in CASES:
        for seat in (0, 1):
            try:
                result = one(name, seat)
            except Exception:
                result = dict(contract=VERSION, case=name, seat=seat, ok=False,
                              error=traceback.format_exc(limit=5))
            rows.append(result)
            print(json.dumps({k: v for k, v in result.items() if k not in ('speed_checks','fresh_troop_templates','differences','applicability','raw_differences')}), flush=True)
    with open(sys.argv[1], 'w') as out:
        json.dump(rows, out, indent=1)
    # Collector returns process success on complete evidence; strict validator judges the outcomes.
