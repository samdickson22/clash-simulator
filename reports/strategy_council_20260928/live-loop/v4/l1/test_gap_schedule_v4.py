"""Synthetic causal schedule and source-clock regressions."""
import json
from gap_schedule_v4 import decision_intervals, public_frame_intervals, make_schedules, select_arrivals


def rejected(fn):
    try:
        fn()
    except (KeyError, ValueError):
        return
    raise AssertionError('Invalid gap input accepted')


def main():
    rows = [dict(frame_id=str(i), capture_produced_epoch=t,
                 action_submit_epoch=1000-i, capture_received_mono=100+i) for i, t in enumerate([10, 10.5, 11.25])]
    assert decision_intervals(rows) == [500., 750.]
    checks = 1
    public = [dict(frame_id=str(i), timestamp_ms=t) for i, t in enumerate([0, 50, 150, 760])]
    assert public_frame_intervals(public) == [50, 100, 610]
    checks += 1
    schedules = make_schedules({'b': [0, 100, 200, 300, 400], 'a': [0, 100, 200, 300, 400]}, [150])
    assert schedules['schedules']['a'] == [dict(frame_index=0, timestamp_ms=0., scheduled_arrival_ms=0.),
        dict(frame_index=2, timestamp_ms=200., scheduled_arrival_ms=150.),
        dict(frame_index=3, timestamp_ms=300., scheduled_arrival_ms=300.)]
    checks += 1
    shared = [0, 75, 150]
    assert [r['timestamp_ms'] for r in select_arrivals([0, 50, 100, 150, 200], shared)] == [0, 100, 150]
    assert [r['timestamp_ms'] for r in select_arrivals([0, 100, 200], shared)] == [0, 100, 200]
    assert select_arrivals([0], [1]) == []
    checks += 1
    selected = make_schedules({'a': [0, 100, 200]}, [10])['schedules']['a']
    assert [r['frame_index'] for r in selected] == [0, 1, 2]
    assert [r['timestamp_ms'] for r in selected] == [0, 100, 200]
    checks += 1
    frames = {'b': list(range(0, 10001, 50)), 'a': list(range(0, 10001, 100))}
    first = make_schedules(frames, [100, 300, 610])
    second = make_schedules(dict(reversed(list(frames.items()))), [100, 300, 610])
    assert first == second
    for values in first['schedules'].values():
        assert len(set(r['frame_index'] for r in values)) == len(values)
        assert all(r['timestamp_ms'] >= r['scheduled_arrival_ms'] for r in values)
    checks += 1
    for call in (
        lambda: decision_intervals([]),
        lambda: decision_intervals([rows[0], rows[0]]),
        lambda: decision_intervals(list(reversed(rows))),
        lambda: decision_intervals([dict(rows[0], capture_produced_epoch=None), rows[1]]),
        lambda: decision_intervals([dict(rows[0], capture_produced_epoch=float('nan')), rows[1]]),
        lambda: make_schedules({'a': [0, 1]}, []),
        lambda: make_schedules({'a': [0, 1]}, [0]),
        lambda: make_schedules({'a': [0, 1]}, [-1]),
        lambda: make_schedules({'a': [0, 1]}, [True]),
        lambda: make_schedules({'a': [1, 0]}, [1]),
        lambda: make_schedules({'a': [0, 0]}, [1]),
        lambda: make_schedules({'a': []}, [1]),
        lambda: make_schedules({}, [1]),
        lambda: select_arrivals([0, 100], [50, 50]),
        lambda: public_frame_intervals([]),
        lambda: public_frame_intervals([public[0], public[0]]),
        lambda: public_frame_intervals(list(reversed(public))),
        lambda: public_frame_intervals([dict(public[0], timestamp_ms=None), public[1]]),
    ):
        rejected(call)
        checks += 1
    print(json.dumps(dict(pass_=True, checks=checks, synthetic_only=True, heldout_payloads_opened=False)), flush=True)


if __name__ == '__main__':
    main()
