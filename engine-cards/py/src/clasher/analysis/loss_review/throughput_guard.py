"""Exploration-only throughput protection and clocks shared by sim runners."""
import json
import math
import os
import statistics
from pathlib import Path
import time


class PauseClock:
    """One writer, many readers; atomic snapshots include an ongoing pause."""
    def __init__(self, path):
        self.path = Path(path)

    def snapshot(self):
        try:
            return json.loads(self.path.read_text())
        except FileNotFoundError:
            return dict(paused_total_seconds=0., paused_since_monotonic=None)

    def now(self):
        current = time.perf_counter()
        state = self.snapshot()
        live = state['paused_since_monotonic']
        return current - state['paused_total_seconds'] - (max(0., current-live) if live is not None else 0.)

    def set_paused(self, paused):
        state = self.snapshot(); current = time.perf_counter()
        since = state['paused_since_monotonic']
        if paused and since is None:
            state['paused_since_monotonic'] = current
        elif not paused and since is not None:
            state['paused_total_seconds'] += max(0., current-since)
            state['paused_since_monotonic'] = None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name+'.tmp')
        temporary.write_text(json.dumps(state)+'\n')
        os.replace(temporary, self.path)


class ThroughputComparator:
    """A missing/stale metric cannot trigger a utilization-based fallback."""
    def __init__(self, baseline):
        self.baseline = float(baseline)
        if not math.isfinite(self.baseline) or self.baseline <= 0:
            raise ValueError('positive measured throughput baseline required')

    def should_pause(self, rate, gpu_job_present=True):
        return bool(gpu_job_present and rate is not None and math.isfinite(rate)
                    and 0 <= rate < .95*self.baseline)


def throughput_sample(job, max_age_seconds=120):
    """Read only an explicitly configured job log; never use cumulative rates."""
    path = Path(job['log_path']); field = job['field']
    if 'including_loader' in field or 'cumulative' in field:
        raise ValueError('guard requires an interval throughput metric')
    if time.time()-path.stat().st_mtime > max_age_seconds:
        return None
    with path.open('rb') as source:
        source.seek(max(0, path.stat().st_size-65536))
        lines = source.read().splitlines()
    window = int(job.get('window_steps', 1))
    if window < 1:
        raise ValueError('positive throughput window required')
    values = []; seen = set(); latest_step = None
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            continue
        if row.get('event') == job.get('event', 'step') and field in row:
            step = row.get('step')
            if step is not None and step in seen:
                continue
            seen.add(step)
            if not values:
                latest_step = step
            values.append(float(row[field]))
            if len(values) >= window:
                return dict(rate=statistics.median(values), step=latest_step, field=field)
    return None


def expand_smt_siblings(cpus, sys_root=Path('/sys/devices/system/cpu')):
    expanded = set(cpus)
    for cpu in cpus:
        try:
            groups = (sys_root/f'cpu{cpu}/topology/thread_siblings_list').read_text().strip().split(',')
            for group in groups:
                bounds = [int(n) for n in group.split('-')]
                expanded.update(range(bounds[0], bounds[-1]+1))
        except FileNotFoundError:
            pass
    return expanded


def gpu_task_cores(pids, previous=None, proc_root=Path('/proc')):
    """Current cores of active GPU-job threads, including direct CPU feeders."""
    previous = previous or {}; samples = {}; cores = set()
    pending = list(pids); seen = set()
    while pending:
        pid = pending.pop()
        if pid in seen:
            continue
        seen.add(pid)
        try:
            pending.extend(int(p) for p in (proc_root/str(pid)/'task'/str(pid)/'children').read_text().split())
            tasks = list((proc_root/str(pid)/'task').iterdir())
        except (FileNotFoundError, ProcessLookupError):
            continue
        for task in tasks:
            try:
                fields = (task/'stat').read_text().rsplit(')', 1)[1].split()
                ticks = int(fields[11])+int(fields[12]); core = int(fields[36])
                tid = int(task.name); samples[tid] = ticks
                # A first snapshot must not reserve every core on which an
                # inactive thread ran at some earlier point in training.
                if (tid in previous and ticks > previous[tid]) or (tid not in previous and fields[0] == 'R'):
                    cores.add(core)
            except (FileNotFoundError, ProcessLookupError):
                continue
    return cores, samples


def idle_and_pin(pids, excluded_cpus, allowed_cpus=None):
    """Modify only caller-owned PIDs; include SMT siblings in exclusions."""
    allowed = set(allowed_cpus if allowed_cpus is not None else os.sched_getaffinity(0))
    available = allowed-expand_smt_siblings(excluded_cpus)
    if not available:
        raise RuntimeError('no GPU-excluded CPU available')
    changed = []
    for pid in pids:
        try:
            os.sched_setscheduler(pid, os.SCHED_IDLE, os.sched_param(0))
            os.sched_setaffinity(pid, available)
            changed.append(pid)
        except ProcessLookupError:
            pass
    return dict(pids=changed, allowed_cpus=sorted(available), excluded_cpus=sorted(allowed-available), scheduler='SCHED_IDLE')
