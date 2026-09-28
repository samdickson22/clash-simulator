"""Guard fixed overlapping fits and two concurrent exact reviews under one lease."""

import argparse
import fcntl
import json
import os
import signal
import subprocess
import time
from pathlib import Path

import psutil
import torch
from overlap_contract import MEMORY, OUTPUT, PLAN, SEEDS, prepare, validate
from value_contract import ROOT, publish, sha

MONITOR = Path('/Users/sam/Library/Application Support/ClasherMonitor')
LIMIT = 18 * 1024**3


def status(**fields):
    fields.update(updated_at=time.time(), supervisor_pid=os.getpid(), acceptance=False)
    path = MONITOR / 'comparison-status.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(fields, indent=2) + '\n')
    temporary.replace(path)
    print(json.dumps(fields), flush=True)


def interrupted(signum, _frame):
    raise SystemExit(128 + signum)


def run_group(name, jobs):
    children, logs, peaks = {}, {}, {}
    peak, killed, error = 0, False, None
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1')
    try:
        for label, arguments in jobs.items():
            log = (ROOT / f'reports/hog26_overlap_margin_{label}_20260913.log').open('x')
            logs[label] = log
            child = subprocess.Popen(['/Users/sam/Desktop/code/clasher/.venv/bin/python', '-u',
                                      'experiments/hog26_overlap_margin/' + arguments[0], *arguments[1:]],
                                     env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            children[label], peaks[label] = child, 0
        status(stage='overlap-margin-' + name, pids={label: child.pid for label, child in children.items()},
               aggregate_limit_bytes=LIMIT, plan_sha256=sha(PLAN))
        while any(child.poll() is None for child in children.values()):
            total = 0
            for label, child in children.items():
                code = child.poll()
                if code is not None:
                    if code:
                        raise RuntimeError(f'worker {label} exited{code}')
                    continue
                try:
                    live = psutil.Process(child.pid)
                    rss = live.memory_info().rss + sum(p.memory_info().rss for p in live.children(recursive=True))
                except psutil.NoSuchProcess:
                    continue
                peaks[label] = max(peaks[label], rss)
                total += rss
            peak = max(peak, total)
            if peak > LIMIT:
                killed = True
                raise MemoryError('combined overlap worker memory limit exceeded')
            time.sleep(.5)
    except BaseException as exc:  # noqa: BLE001 - record cleanup, then re-raise the original failure
        error = exc
    finally:
        for child in children.values():
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
        codes = {label: child.wait() for label, child in children.items()}
        for log in logs.values():
            log.close()
    code = next((value for value in codes.values() if value), 0)
    result = {'exit_code': code, 'worker_exit_codes': codes, 'peak_rss_bytes': peak, 'worker_peak_rss_bytes': peaks,
              'memory_limit_terminated': killed, 'limit_bytes': LIMIT, 'plan_sha256': sha(PLAN),
              'execution_exception': type(error).__name__ if error is not None else None}
    publish(ROOT / f'reports/hog26_overlap_margin_{name}_guard_20260913.json', result)
    if error is not None or code or killed:
        status(stage='overlap-margin-' + name + '-failed-preserved', **result)
        if error is not None:
            raise error
        raise SystemExit(code or 1)
    status(stage='overlap-margin-' + name + '-complete', **result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('pin', 'memory', 'run'), required=True)
    args = parser.parse_args()
    os.chdir(ROOT)
    torch.set_num_threads(1)
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    lock = (MONITOR / 'comparison.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if args.mode == 'pin':
        prepare()
        return
    validate(memory=args.mode == 'run')
    if args.mode == 'memory':
        run_group('memory', {'memory': ['memory_probe.py']})
        validate(memory=True)
        if json.loads(MEMORY.read_text())['status'] != 'complete-overlap-margin-synthetic-memory':
            raise ValueError('complete overlap memory proof required')
        return
    OUTPUT.mkdir(exist_ok=False)
    publish(OUTPUT / 'manifest.json', {'plan_sha256': sha(PLAN), 'regressor_fits': 24,
                                      'review_worker_threads': 1, 'concurrent_reviews': 2, 'acceptance': False})
    guards = {}
    for seed in SEEDS:
        for fold in range(4):
            name = f'seed{seed}-fold{fold}'
            guards[name] = run_group(name, {name: ['fit_overlap.py', '--seed', str(seed), '--fold', str(fold)]})
            result = json.loads((OUTPUT / name / 'complete.json').read_text())
            if result['status'] != 'complete-overlap-margin-fold' or result['seed'] != seed or result['fold'] != fold:
                raise ValueError('complete overlapping fold required')
    guards['reviews'] = run_group('reviews', {f'review-seed{seed}': ['review_overlap.py', '--seed', str(seed)] for seed in SEEDS})
    guards['science'] = run_group('science', {'science': ['overlap_science.py']})
    science_path = OUTPUT / 'scientific-review.json'
    if json.loads(science_path.read_text())['status'] != 'complete-overlap-margin-scientific-review':
        raise ValueError('complete overlap scientific review required')
    validate(memory=True)
    publish(OUTPUT / 'complete.json', {'status': 'complete-overlap-margin-comparison', 'plan_sha256': sha(PLAN),
            'scientific_review_sha256': sha(science_path), 'regressor_fits': 24, 'unchanged_global_references': 8,
            'guards': guards, 'concurrent_exact_reviews': 2, 'acceptance': False})
    status(stage='overlap-margin-comparison-complete', output=str(OUTPUT), plan_sha256=sha(PLAN))


if __name__ == '__main__':
    main()
