"""Sequential inference and exact review under one leased memory guard."""

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
from phase_eval_contract import DESTINATION, PIN, REVIEW, prepare_pin, validate_pin
from value_contract import ROOT, publish, sha

MONITOR = Path('/Users/sam/Library/Application Support/ClasherMonitor')
LIMIT = 18 * 1024**3


def status(**fields):
    fields.update(updated_at=time.time(), supervisor_pid=os.getpid(), fitting=False, acceptance=False)
    path = MONITOR / 'comparison-status.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(fields, indent=2) + '\n')
    temporary.replace(path)
    print(json.dumps(fields), flush=True)


def worker(mode, script):
    log_path = ROOT / f'reports/hog26_phase_margin_diagnostic_{mode}_20260913.log'
    peak, killed = 0, False
    with log_path.open('x') as log:
        process = subprocess.Popen(['/Users/sam/Desktop/code/clasher/.venv/bin/python', '-u',
                                    'experiments/hog26_phase_value_eval/' + script],
                                   env=dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1'),
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        status(stage='phase-margin-diagnostic-' + mode, pid=process.pid, log=str(log_path), pin_sha256=sha(PIN))
        try:
            while process.poll() is None:
                try:
                    live = psutil.Process(process.pid)
                    peak = max(peak, live.memory_info().rss + sum(child.memory_info().rss for child in live.children(recursive=True)))
                except psutil.NoSuchProcess:
                    pass
                if peak > LIMIT:
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
    publish(ROOT / f'reports/hog26_phase_margin_diagnostic_{mode}_guard_20260913.json', result)
    if code or killed:
        status(stage='phase-margin-diagnostic-' + mode + '-failed', **result)
        raise SystemExit(code or 1)
    validate_pin()
    path = DESTINATION / 'complete.json' if mode == 'evaluate' else REVIEW
    expected = 'complete-phase-margin-diagnostic' if mode == 'evaluate' else 'complete-exact-phase-margin-diagnostic-review'
    if json.loads(path.read_text())['status'] != expected:
        raise ValueError('phase diagnostic completion required')
    status(stage='phase-margin-diagnostic-' + mode + '-complete', **result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('pin', 'run'), required=True)
    args = parser.parse_args()
    os.chdir(ROOT)
    torch.set_num_threads(1)
    lock = (MONITOR / 'comparison.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if args.mode == 'pin':
        prepare_pin()
        return
    validate_pin()
    worker('evaluate', 'evaluate_phase.py')
    worker('review', 'review_phase_diagnostic.py')


if __name__ == '__main__':
    main()
