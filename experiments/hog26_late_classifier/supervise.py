"""Bound the late classifier fit and review under the shared lease."""

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
from late_contract import OUTPUT, PIN, prepare, validate
from value_contract import ROOT, publish, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('pin', 'run'), required=True)
    args = parser.parse_args()
    torch.set_num_threads(1)
    if args.mode == 'pin':
        prepare()
        print('late classifier pinned', sha(PIN), flush=True)
        return
    base = Path('/Users/sam/Library/Application Support/ClasherMonitor')
    with (base / 'comparison.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        validate()
        stages = {}
        state_path = base / 'comparison-status.json'
        for stage in ('fit', 'review'):
            log_path = ROOT / f'reports/hog26_late_classifier_{stage}_20260913.log'
            with log_path.open('x') as log:
                process = subprocess.Popen(['/Users/sam/Desktop/code/clasher/.venv/bin/python', '-u',
                    f'experiments/hog26_late_classifier/{stage}_late.py'], cwd=ROOT,
                    env=dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1'),
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                state = {'stage': 'late-classifier-' + stage, 'pid': process.pid, 'supervisor_pid': os.getpid(),
                         'log': str(log_path), 'updated_at': time.time(), 'acceptance': False}
                temporary = state_path.with_suffix('.tmp')
                temporary.write_text(json.dumps(state, indent=2))
                temporary.replace(state_path)
                peak, killed = 0, False
                try:
                    while process.poll() is None:
                        try:
                            live = psutil.Process(process.pid)
                            peak = max(peak, live.memory_info().rss + sum(p.memory_info().rss for p in live.children(recursive=True)))
                        except psutil.NoSuchProcess:
                            pass
                        if peak > 18 * 1024**3:
                            killed = True
                            break
                        time.sleep(.5)
                finally:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGTERM)
                        try:
                            process.wait(timeout=15)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL)
                code = process.wait()
            stages[stage] = {'exit_code': code, 'peak_rss_bytes': peak, 'memory_limit_terminated': killed}
            publish(ROOT / f'reports/hog26_late_classifier_{stage}_guard_20260913.json', {**stages[stage], 'pin_sha256': sha(PIN)})
            if code or killed:
                state.update(stage='late-classifier-failed', updated_at=time.time(), **stages[stage])
                temporary.write_text(json.dumps(state, indent=2))
                temporary.replace(state_path)
                raise SystemExit(code or 1)
        validate()
        if json.loads((OUTPUT / 'complete.json').read_text())['status'] != 'complete-late-classifier-fit-and-review':
            raise ValueError('complete exact review required')
        state.update(stage='late-classifier-complete', updated_at=time.time(), stages=stages)
        temporary.write_text(json.dumps(state, indent=2))
        temporary.replace(state_path)
        print(json.dumps(stages), flush=True)


if __name__ == '__main__':
    main()
