"""Run four independent control collectors and a serial audit under one lease."""

import argparse
import fcntl
import json
import os
import signal
import subprocess
import time
from contextlib import ExitStack
from pathlib import Path

import psutil
import torch
from training_contract import OUTPUT, PIN, WORKERS, prepare, validate
from value_contract import ROOT, publish, sha


def run_stage(stage, commands, base):
    with ExitStack() as stack:
        processes = []
        for name, command in commands:
            log = stack.enter_context((ROOT / f'reports/hog26_scalar_mirror_training_{name}_20260913.log').open('x'))
            processes.append(subprocess.Popen(['/Users/sam/Desktop/code/clasher/.venv/bin/python', '-u', *command], cwd=ROOT,
                    env=dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1'),
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True))
        state = {'stage': 'scalar-mirror-training-' + stage, 'supervisor_pid': os.getpid(),
                 'pids': [p.pid for p in processes], 'updated_at': time.time(), 'policy_learning': False, 'acceptance': False}
        path = base / 'comparison-status.json'
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(state, indent=2))
        temporary.replace(path)
        peak, killed = 0, False
        try:
            while any(p.poll() is None for p in processes):
                if any(p.poll() not in (None, 0) for p in processes):
                    break
                rss = 0
                for process in processes:
                    try:
                        live = psutil.Process(process.pid)
                        rss += live.memory_info().rss + sum(p.memory_info().rss for p in live.children(recursive=True))
                    except psutil.NoSuchProcess:
                        pass
                peak = max(peak, rss)
                if peak > 18 * 1024**3:
                    killed = True
                    break
                time.sleep(.5)
        finally:
            for process in processes:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
            for process in processes:
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        result = {'exit_codes': [p.returncode for p in processes], 'peak_rss_bytes': peak,
                  'memory_limit_terminated': killed, 'pin_sha256': sha(PIN)}
        publish(ROOT / f'reports/hog26_scalar_mirror_training_{stage}_guard_20260913.json', result)
        if killed or any(result['exit_codes']):
            state.update(stage='scalar-mirror-training-failed', **result)
            temporary.write_text(json.dumps(state, indent=2))
            temporary.replace(path)
            raise SystemExit(1)
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('pin', 'run'), required=True)
    args = parser.parse_args()
    torch.set_num_threads(1)
    if args.mode == 'pin':
        prepare()
        print('training controls pinned', sha(PIN), flush=True)
        return
    base = Path('/Users/sam/Library/Application Support/ClasherMonitor')
    with (base / 'comparison.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        validate()
        if OUTPUT.exists():
            raise ValueError('preserve previous training-control collection')
        OUTPUT.mkdir()
        publish(OUTPUT / 'manifest.json', {'pin_sha256': sha(PIN), 'policy_learning': False, 'acceptance': False})
        fitting = run_stage('collection', [(f'worker{worker}', ['experiments/hog26_scalar_mirror_training/collect_training.py', '--worker', str(worker)]) for worker in range(WORKERS)], base)
        review = run_stage('review', [('review', ['experiments/hog26_scalar_mirror_training/review_training.py'])], base)
        validate()
        if json.loads((OUTPUT / 'complete.json').read_text())['status'] != 'complete-audited-scalar-mirror-training-controls':
            raise ValueError('audited completion required')
        path = base / 'comparison-status.json'
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'stage': 'scalar-mirror-training-complete', 'collection': fitting,
                                        'review': review, 'updated_at': time.time(), 'acceptance': False}, indent=2))
        temporary.replace(path)
        print('training-control collection and audit complete', flush=True)


if __name__ == '__main__':
    main()
