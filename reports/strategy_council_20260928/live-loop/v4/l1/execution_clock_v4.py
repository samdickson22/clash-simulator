"""Evaluator-only tick-to-production mapping; no file I/O or inference inputs.

An exact executeTick does not imply an exact wall-clock execution timestamp.
Use the last frame with a supported upper tick strictly before execution and
the first with a supported lower tick at/after it. The midpoint is the point
estimate; preserve the full empirical interval for conservative scoring.
Leading/trailing clamped frames support only the observed upper/lower bound,
respectively. Never extrapolate time or omit an event that cannot be enclosed.
"""
import bisect
import math


class ExecutionClock:
    def __init__(self, frames):
        if not frames:
            raise ValueError('Frame ledger required')
        self.origin = frames[0]['produced_at']
        self.rows = []
        previous = None
        for i, row in enumerate(frames):
            stamp = row['produced_at']
            lo, hi = row['tick_lo'], row['tick_hi']
            if (type(row['seq']) is not int or row['seq'] != i
                    or isinstance(stamp, bool) or not isinstance(stamp, (int, float))
                    or not math.isfinite(stamp) or type(lo) is not int or type(hi) is not int
                    or lo < 0 or hi < lo or type(row.get('bracket_extrapolated')) is not bool):
                raise ValueError('Invalid frame production/tick ledger')
            if previous and (stamp <= previous[0] or lo < previous[1] or hi < previous[2]):
                raise ValueError('Nonmonotonic production/tick ledger')
            previous = stamp, lo, hi
            if not row['bracket_extrapolated']:
                self.rows.append((lo, hi, (stamp-self.origin)*1000, i))
        self.lower_ticks = [r[0] for r in self.rows]
        self.upper_ticks = [r[1] for r in self.rows]
        if not self.rows:
            raise ValueError('No non-extrapolated frame brackets')
        # Collector uses searchsorted(sample_times, produced_mono): before the
        # first sample both fields clamp to that sample; after the last they
        # clamp to the final sample. The leading UPPER and trailing LOWER tick
        # remain observed one-sided bounds. The opposite side is unsupported.
        first, last = self.rows[0][3], self.rows[-1][3]
        leading, trailing = [], []
        for row in frames[:first]:
            if (row['tick_lo'] != row['tick_hi'] or row['tick_hi'] > self.rows[0][0]
                    or row['tick_hi'] != frames[0]['tick_hi']):
                raise ValueError('Leading clamp is inconsistent with observed ticks')
            leading.append((row['tick_lo'], row['tick_hi'], (row['produced_at']-self.origin)*1000, row['seq']))
        for row in frames[last+1:]:
            if (row['tick_lo'] != row['tick_hi'] or row['tick_lo'] < self.rows[-1][1]
                    or row['tick_lo'] != frames[-1]['tick_lo']):
                raise ValueError('Trailing clamp is inconsistent with observed ticks')
            trailing.append((row['tick_lo'], row['tick_hi'], (row['produced_at']-self.origin)*1000, row['seq']))
        self.before_rows = leading+self.rows
        self.after_rows = self.rows+trailing
        self.upper_ticks = [r[1] for r in self.before_rows]
        self.lower_ticks = [r[0] for r in self.after_rows]
        self.first_two_sided, self.last_two_sided = first, last

    def map_tick(self, tick):
        if type(tick) is not int or tick < 0:
            raise ValueError('Exact nonnegative integer execution tick required')
        before = bisect.bisect_left(self.upper_ticks, tick)-1
        after = bisect.bisect_left(self.lower_ticks, tick)
        if before < 0 or after == len(self.after_rows):
            raise ValueError('Execution tick is not enclosed; timing endpoint remains blocked')
        low, high = self.before_rows[before], self.after_rows[after]
        if low[3] >= high[3] or not low[2] < high[2]:
            raise ValueError('Inconsistent enclosing frame brackets')
        return dict(exec_tick=tick, execution_timestamp_ms=(low[2]+high[2])/2,
                    event_time_interval_ms=[low[2], high[2]],
                    enclosing_source_seq=[low[3], high[3]],
                    enclosing_bound_sources=[
                        'leading_observed_upper_tick' if low[3] < self.first_two_sided else 'two_sided_frame',
                        'trailing_observed_lower_tick' if high[3] > self.last_two_sided else 'two_sided_frame'],
                    timing_method='midpoint_of_empirical_enclosing_frame_interval',
                    timing_certified=False)
