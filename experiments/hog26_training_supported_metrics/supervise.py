"""Run a training-only natural-rule screen under the shared experiment lease."""

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
from screen_contract import PIN, RESULT, prepare, validate
from value_contract import ROOT, publish, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('pin', 'audit'), required=True)
    args = parser.parse_args()
    torch.set_num_threads(1)
    os.chdir(ROOT)
    if args.mode == 'pin':
        prepare()
        return
    base = Path('/Users/sam/Library/Application Support/ClasherMonitor')
    lock = (base / 'comparison.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    validate()
    log_path = ROOT / 'reports/hog26_training_supported_metrics_audit_20260913.log'
    with log_path.open('x') as log:
        process = subprocess.Popen(['/Users/sam/Desktop/code/clasher/.venv/bin/python', '-u',
                                    'experiments/hog26_training_supported_metrics/run_screen.py'],
                                   env=dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1'),
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        state = {'stage': 'training-supported-metrics', 'pid': process.pid, 'supervisor_pid': os.getpid(),
                 'log': str(log_path), 'updated_at': time.time(), 'fitting': False, 'acceptance': False}
        path = base / 'comparison-status.json'
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(state, indent=2) + '\n')
        temporary.replace(path)
        peak, killed = 0, False
        try:
            while process.poll() is None:
                try:
                    live = psutil.Process(process.pid)
                    peak = max(peak, live.memory_info().rss + sum(child.memory_info().rss for child in live.children(recursive=True)))
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
    result = {'exit_code': code, 'peak_rss_bytes': peak, 'memory_limit_terminated': killed, 'pin_sha256': sha(PIN)}
    publish(ROOT / 'reports/hog26_training_supported_metrics_guard_20260913.json', result)
    if not code and not killed:
        validate()
        if json.loads(RESULT.read_text())['status'] != 'complete-training-supported-metrics':
            raise ValueError('complete numerical rule screen required')
    state.update(stage='training-supported-metrics-failed' if code or killed else 'training-supported-metrics-complete',
                 updated_at=time.time(), **result)
    temporary.write_text(json.dumps(state, indent=2) + '\n')
    temporary.replace(path)
    if code or killed:
        raise SystemExit(code or 1)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
