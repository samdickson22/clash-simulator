"""Registered empirical gap schedules; no prediction or Phase A payload I/O."""
import argparse
import bisect
import hashlib
import gzip
import json
import math
from pathlib import Path
import random

import numpy as np


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Finite timestamp required')
    return float(value)


def decision_intervals(rows):
    """Diagnostic only: adjacent captures in a sparse decisions file.

    Use capture production epoch, never action submission or inferred simulation
    ticks. Missing/noncausal/duplicate records block instead of being discarded.
    Inter-file boundaries are never sampled as intervals.
    """
    if len(rows) < 2:
        raise ValueError('At least two decision captures required per source')
    stamps = [_finite(r['capture_produced_epoch']) for r in rows]
    frames = [r['frame_id'] for r in rows]
    if len(set(frames)) != len(frames):
        raise ValueError('Duplicate decision frame identity')
    gaps = [(b-a)*1000 for a, b in zip(stamps, stamps[1:])]
    if min(gaps) <= 0:
        raise ValueError('Nonchronological production timestamps')
    return gaps


def public_frame_intervals(rows):
    """Amendment 02: all chronological public frame intervals, in milliseconds."""
    if len(rows) < 2:
        raise ValueError('At least two public frames required per source')
    stamps = [_finite(r['timestamp_ms']) for r in rows]
    frames = [r['frame_id'] for r in rows]
    if len(set(frames)) != len(frames):
        raise ValueError('Duplicate public frame identity')
    gaps = [b-a for a, b in zip(stamps, stamps[1:])]
    if min(gaps) <= 0:
        raise ValueError('Nonchronological public frame timestamps')
    return gaps


def select_arrivals(times, arrivals):
    """Apply shared arrivals to one arm's frame grid without duplicates."""
    times = [_finite(x) for x in times]
    arrivals = [_finite(x) for x in arrivals]
    if not times or any(a >= b for a, b in zip(times, times[1:])):
        raise ValueError('Strictly increasing original frame timestamps required')
    if any(a >= b for a, b in zip(arrivals, arrivals[1:])):
        raise ValueError('Strictly increasing scheduled arrivals required')
    selected = []
    for due in arrivals:
        i = bisect.bisect_left(times, due)
        if i == len(times):
            break
        if not selected or i != selected[-1]['frame_index']:
            selected.append(dict(frame_index=i, timestamp_ms=times[i], scheduled_arrival_ms=due))
    return selected


def make_schedules(frame_times_by_episode, gaps_ms):
    """Label-independent seed-6109 arrivals, first frame at/after each arrival.

    Arrival times accumulate sampled empirical intervals from the episode's first
    frame. Multiple arrivals selecting the same frame are deduplicated. Episode
    order is canonical; timestamps stay unchanged. Freeze the returned indices
    and inputs before any model prediction. Reuse the recorded arrival sequences
    through select_arrivals for each compared arm's frame grid (20 vs 10 FPS).
    This pure helper does not authenticate split admission or create that seal.
    """
    gaps = [_finite(x) for x in gaps_ms]
    if not gaps or min(gaps) <= 0:
        raise ValueError('Positive empirical intervals required')
    if not frame_times_by_episode:
        raise ValueError('Episode population required')
    rng = random.Random(6109)
    result, arrivals_by_episode = {}, {}
    for episode, raw_times in sorted(frame_times_by_episode.items()):
        times = [_finite(x) for x in raw_times]
        if not times or any(a >= b for a, b in zip(times, times[1:])):
            raise ValueError('Strictly increasing original frame timestamps required')
        due = times[0]
        arrivals = []
        while due <= times[-1]:
            arrivals.append(due)
            next_due = due + rng.choice(gaps)
            if next_due <= due:
                raise ValueError('Interval below timestamp precision')
            due = next_due
        result[episode] = select_arrivals(times, arrivals)
        arrivals_by_episode[episode] = arrivals
    return dict(seed=6109, schedules=result, arrivals_ms=arrivals_by_episode,
                source='amendment02.public_frames.timestamp_ms',
                selection_seal=False)


def audit_sources(root):
    paths = sorted(root.glob('pair-*/public-frames.jsonl.gz'))
    if not paths:
        raise ValueError('Amendment 02 L2 public-frame sources absent; gap cell blocked')
    gaps, sources = [], {}
    for path in paths:
        raw = path.read_bytes()
        rows = [json.loads(line) for line in gzip.decompress(raw).splitlines()]
        intervals = public_frame_intervals(rows)
        gaps.extend(intervals)
        sources[str(path.relative_to(root))] = dict(sha256=hashlib.sha256(raw).hexdigest(),
                                                  frames=len(rows), intervals=len(intervals))
    return dict(schema='clasher.v4.empirical-gap-source.v1', source_files=sources,
                source_field='timestamp_ms', registration='PREREG-AMENDMENT-02.md', interval_count=len(gaps),
                p95_ms=float(np.quantile(gaps, .95)), minimum_ms=min(gaps), maximum_ms=max(gaps),
                intervals_ms=gaps, seed=6109, heldout_payloads_opened=False,
                selection_seal=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--l2', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit_sources(args.l2)
    with args.output.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('intervals_ms', 'source_files')}), flush=True)
