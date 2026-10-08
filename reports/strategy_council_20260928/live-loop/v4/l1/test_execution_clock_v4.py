"""Synthetic boundary/plateau/gap tests; no producer payload access."""
from copy import deepcopy
from execution_clock_v4 import ExecutionClock


def main():
    checks = 0
    def check(value):
        nonlocal checks
        assert value
        checks += 1
    def refuses(fn):
        nonlocal checks
        try:
            fn()
        except ValueError:
            checks += 1
        else:
            raise AssertionError('Expected timing refusal')
    frames = [dict(seq=i, produced_at=100+i*.05, tick_lo=2*i, tick_hi=2*i+1,
                   bracket_extrapolated=False) for i in range(6)]
    clock = ExecutionClock(frames)
    mapped = clock.map_tick(4)
    check(mapped['enclosing_source_seq'] == [1, 2])
    check(abs(mapped['execution_timestamp_ms']-75) < 1e-8)
    check(mapped['timing_certified'] is False)
    # An upper tick equal to execution is not a strict-before witness.
    check(clock.map_tick(3)['enclosing_source_seq'] == [0, 2])
    # Compare binary searches against an exhaustive independent enclosure oracle.
    for tick in range(2, 11):
        before = max(i for i, r in enumerate(frames) if r['tick_hi'] < tick)
        after = min(i for i, r in enumerate(frames) if r['tick_lo'] >= tick)
        check(clock.map_tick(tick)['enclosing_source_seq'] == [before, after])
    plateau = deepcopy(frames)
    plateau[2].update(tick_lo=2, tick_hi=3)
    check(ExecutionClock(plateau).map_tick(4)['enclosing_source_seq'] == [2, 3])
    gap = deepcopy(frames)
    for row in gap[3:]:
        row['produced_at'] += 1.
    check(ExecutionClock(gap).map_tick(6)['event_time_interval_ms'][1] > 1100)
    extrapolated = deepcopy(frames)
    extrapolated[1]['bracket_extrapolated'] = True
    check(ExecutionClock(extrapolated).map_tick(4)['enclosing_source_seq'] == [0, 2])
    for tick in (0, 1, 11, 100, -1, 4., True):
        refuses(lambda: clock.map_tick(tick))
    refuses(lambda: ExecutionClock([]))
    for key, value in (('seq', 0), ('produced_at', float('nan')), ('produced_at', 99.),
                       ('tick_lo', -1), ('tick_hi', 0), ('tick_hi', 2.5),
                       ('bracket_extrapolated', None)):
        bad = deepcopy(frames)
        bad[2][key] = value
        refuses(lambda: ExecutionClock(bad))
    for row in extrapolated:
        row['bracket_extrapolated'] = True
    refuses(lambda: ExecutionClock(extrapolated))
    tail = deepcopy(frames)
    tail.extend(dict(seq=i, produced_at=100+i*.05, tick_lo=11, tick_hi=11,
                     bracket_extrapolated=True) for i in (6, 7))
    mapped = ExecutionClock(tail).map_tick(11)
    check(mapped['enclosing_source_seq'] == [4, 6])
    check(mapped['enclosing_bound_sources'] == ['two_sided_frame', 'trailing_observed_lower_tick'])
    refuses(lambda: ExecutionClock(tail).map_tick(12))
    bad_tail = deepcopy(tail)
    bad_tail[-1]['tick_lo'] = bad_tail[-1]['tick_hi'] = 12
    refuses(lambda: ExecutionClock(bad_tail))
    leading = [dict(seq=0, produced_at=99.95, tick_lo=0, tick_hi=0, bracket_extrapolated=True)]
    leading += [dict(row, seq=row['seq']+1) for row in frames]
    mapped = ExecutionClock(leading).map_tick(1)
    check(mapped['enclosing_source_seq'] == [0, 2])
    check(mapped['enclosing_bound_sources'][0] == 'leading_observed_upper_tick')
    # A leading clamp cannot supply an observed lower bound for tick zero.
    refuses(lambda: ExecutionClock(leading).map_tick(0))
    # Several native samples can occur between the clamp and next screenshot;
    # monotone one-sided evidence need not equal the adjacent frame's ticks.
    skipped = deepcopy(leading)
    for row in skipped[1:]:
        row['tick_lo'] += 2
        row['tick_hi'] += 2
    check(ExecutionClock(skipped).map_tick(1)['enclosing_source_seq'] == [0, 1])
    skipped_tail = deepcopy(tail)
    for row in skipped_tail[-2:]:
        row['tick_lo'] = row['tick_hi'] = 13
    check(ExecutionClock(skipped_tail).map_tick(12)['enclosing_source_seq'] == [5, 6])
    print(dict(checks=checks, passed=True, scope='synthetic empirical timing mapping only'), flush=True)


if __name__ == '__main__':
    main()
