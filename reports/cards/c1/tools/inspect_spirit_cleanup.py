"""Source-only retained-clock risk control; no battle/native or gameplay witness."""
import json
import sys
from types import ModuleType, SimpleNamespace

from inspect_shared_troop import ENGINE, function


def main():
    py = ENGINE/'py/src/clasher'
    ns = dict(__package__='c1_cleanup_reference', GLOBAL_ATTACK_FINISH_TIME_MS=250)
    publish = function(py/'ordinary_combat_clock.py', 'publish', ns)
    callback = function(py/'entities.py', 'on_combat_target_removed', ns, 'Entity')

    class Clock(SimpleNamespace):
        pass

    Clock._refund = function(py/'attack_clock.py', '_refund', ns, 'OrdinaryAttackClock')
    Clock.stop_hit = function(py/'attack_clock.py', 'stop_hit', ns, 'OrdinaryAttackClock')
    key = 'c1_cleanup_reference.ordinary_combat_clock'
    assert key not in sys.modules
    module = ModuleType(key)
    module.publish = publish
    sys.modules[key] = module
    rows = []
    try:
        for initialized, timeline, started, pending, finish_allowed in (
            (False, 0, False, False, True), (False, 0, True, False, True),
            (True, 0, True, False, True), (True, 1000, False, False, True),
            (True, 1000, True, False, True), (True, 1000, True, True, True),
            (True, 1000, True, False, False),
        ):
            clock = Clock(hit_interval_ms=1000, load_time_ms=800, hit_timeline_ms=timeline,
                          load_remaining_ms=800, finish_elapsed_ms=0, refund_on_leave=0) if initialized else None
            e = SimpleNamespace(entity_kind=2, target_id=7, _movement_target_id=7,
                                _combat_target_pending_lethal=pending, _ordinary_clock=clock,
                                _ordinary_force_due=False, _attack_finish_elapsed_ms=0,
                                _attack_windup_active=started, _has_attacked_once=started,
                                card_stats=SimpleNamespace(hit_speed=1000, load_first_hit=not finish_allowed))
            callback(e, 7)
            expect = int(not pending and finish_allowed and (timeline > 0 if initialized else started))
            assert e._attack_finish_elapsed_ms == expect
            naive = int(not pending and finish_allowed and started)
            rows.append(dict(clock_initialized=initialized, timeline=timeline, started=started,
                             pending_lethal=pending, finish_allowed=finish_allowed,
                             actual_python_finish=e._attack_finish_elapsed_ms,
                             naive_ordinary_false_finish=naive, naive_differs=naive != expect,
                             remaining_clock_timeline=None if clock is None else clock.hit_timeline_ms))
        assert sum(row['naive_differs'] for row in rows) == 2
    finally:
        del sys.modules[key]
    print(json.dumps(dict(evidence_kind='unmodified-reference-AST-on-explicit-states', rows=rows,
                          limitation='No actual captured state, Rust execution, battle continuation or gameplay reachability proof. Two naive-mode-patch risks are retained, not accepted fixes.'), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
