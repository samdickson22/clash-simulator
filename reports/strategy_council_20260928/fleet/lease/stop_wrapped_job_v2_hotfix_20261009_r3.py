#!/usr/bin/env python3
"""Coordinator backstop: capture old wrapped jobs, then stop verified child trees.

Capture is read-only. Stop reads that host's captured manifest from stdin, sends
TERM to all child groups first, waits bounded grace, then KILLs survivors. The
old supervisors remain alive to reap children and write their own exit receipts.
"""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import sys
import time

source = Path(__file__).with_name('lease_watch_v2_hotfix_20261009_r3.py')
if not source.exists():
    source = Path(__file__).with_name('lease_watch_v2.py')
spec = importlib.util.spec_from_file_location('watch', source)
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)


def capture():
    rows = w.processes()
    registry = json.loads((w.BASE / 'jobs/aggregate-v2.json').read_text())
    jobs = []
    for key, job in registry['jobs'].items():
        if job['kind'] not in ('v1', 'v2'):
            continue
        sup = job['supervisor_pid']
        tick = job.get('supervisor_start', job['known'].get(str(sup)))
        if sup not in rows or rows[sup][1] != tick or rows[sup][3] == 'Z':
            continue
        argv = w.process_argv(sup)
        if job['kind'] == 'v2':
            label = key[3:]
        else:
            script = str(w.BASE / 'lease_watch.py').encode()
            if script not in argv:
                continue
            label = argv[argv.index(script) + 1].decode()
            if not label.startswith('t11-'):
                continue
        state = json.loads((w.BASE / 'jobs' / (label + '.state.json')).read_text())
        child = state['pid']
        child_tick = job['known'].get(str(child))
        if child in rows and rows[child][3] != 'Z' and (
                rows[child][1] != child_tick or rows[child][5:7] != (child, child)):
            raise ValueError('unverified child identity/session: ' + label)
        known = w.expand(rows, job['known'])
        known.pop(sup, None)
        if any(w.excluded_argv(w.process_argv(pid)) for pid in known):
            raise ValueError('excluded process in selected tree: ' + label)
        jobs.append(dict(key=key, label=label, supervisor_pid=sup, supervisor_start=tick,
                         child_pid=child, child_start=child_tick,
                         known={str(pid): start for pid, start in known.items()}))
    return dict(host=w.HOST, captured_utc=w.stamp(), jobs=jobs)


def stop(manifest, grace):
    if manifest['host'] != w.HOST:
        raise ValueError('manifest belongs to another host')
    # Retain captured PID/start pairs even if the direct child or supervisor
    # exits. Refresh via the verified supervisor to include later descendants.
    def survivors(job):
        roots = {**job['known'], str(job['supervisor_pid']): job['supervisor_start']}
        selected = w.expand(w.processes(), roots)
        selected.pop(job['supervisor_pid'], None)
        if any(w.excluded_argv(w.process_argv(pid)) for pid in selected):
            raise ValueError('excluded process in selected tree: ' + job['label'])
        job['known'] = {str(pid): tick for pid, tick in selected.items()}
        return selected

    # Validate all identities before signalling any job. Reused PIDs disappear
    # from expand(); no live verified anchor means no group signal is sent.
    for job in manifest['jobs']:
        current = survivors(job)
        child = job['child_pid']
        if child in current and current[child] != job['child_start']:
            raise ValueError('child identity changed')
    started = time.monotonic()
    for job in manifest['jobs']:
        w.send_job(survivors(job), job['child_pid'], signal.SIGTERM)
        print('TERM child tree:', job['label'], job['child_pid'], job['child_start'], flush=True)
    deadline = min(w.EXIT_BY.timestamp() - 60, time.time() + grace)
    remaining = manifest['jobs'][:]
    while remaining:
        remaining = [job for job in remaining if survivors(job)]
        if not remaining:
            break
        if time.monotonic() - started >= grace or time.time() >= deadline:
            for job in remaining:
                w.send_job(survivors(job), job['child_pid'], signal.SIGKILL)
            # SIGKILL needs scheduling/reaping time. Bound the operator command;
            # old supervisors retain reservations for any surviving PID.
            if time.monotonic() - started >= grace + 10:
                raise RuntimeError('survivors require inspection: ' + repr(remaining))
        time.sleep(.1)
    print('All captured child trees stopped; inspect wrapper receipts and accounting.', flush=True)


def main():
    os.nice(max(0, 10 - os.getpriority(os.PRIO_PROCESS, 0)))
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--capture', action='store_true')
    mode.add_argument('--stop', action='store_true')
    parser.add_argument('--grace-seconds', type=float, default=120)
    args = parser.parse_args()
    if not math.isfinite(args.grace_seconds) or args.grace_seconds < 0:
        parser.error('grace must be finite and nonnegative')
    if args.capture:
        print(json.dumps(capture(), indent=2))
    else:
        stop(json.load(sys.stdin), args.grace_seconds)


if __name__ == '__main__':
    main()
