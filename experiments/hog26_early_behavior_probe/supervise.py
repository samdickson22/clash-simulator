"""Run the fixed public-history information probe under the shared lease."""

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
from probe_contract import MEMORY, OUTPUT, PLAN, prepare, validate
from value_contract import ROOT, publish, sha

MONITOR = Path('/Users/sam/Library/Application Support/ClasherMonitor')
LIMIT = 18 * 1024**3


def status(**fields):
    fields.update(updated_at=time.time(), supervisor_pid=os.getpid(), outcome_fitting=False, acceptance=False)
    path = MONITOR / 'comparison-status.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(fields, indent=2) + '\n')
    temporary.replace(path)
    print(json.dumps(fields), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('pin', 'memory', 'fit', 'review'), required=True)
    args = parser.parse_args()
    os.chdir(ROOT)
    torch.set_num_threads(1)
    lock = (MONITOR / 'comparison.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if args.mode == 'pin':
        prepare()
        return
    validate(require_memory=args.mode != 'memory')
    script = {'memory': 'memory_probe.py', 'fit': 'fit_probe.py', 'review': 'review_probe.py'}[args.mode]
    log_path = ROOT / f'reports/hog26_early_behavior_probe_{args.mode}_20260913.log'
    environment = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1')
    peak, killed = 0, False
    with log_path.open('x') as log:
        process = subprocess.Popen(['/Users/sam/Desktop/code/clasher/.venv/bin/python', '-u',
                                    'experiments/hog26_early_behavior_probe/' + script],
                                   env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        status(stage='early-public-behavior-' + args.mode, pid=process.pid, log=str(log_path), plan_sha256=sha(PLAN))
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
    result = {'exit_code': code, 'peak_rss_bytes': peak, 'memory_limit_terminated': killed, 'limit_bytes': LIMIT, 'plan_sha256': sha(PLAN)}
    publish(ROOT / f'reports/hog26_early_behavior_probe_{args.mode}_guard_20260913.json', result)
    if code or killed:
        status(stage='early-public-behavior-' + args.mode + '-failed', **result)
        raise SystemExit(code or 1)
    if args.mode == 'memory':
        expected, path = 'complete-early-behavior-synthetic-memory', MEMORY
    elif args.mode == 'fit':
        expected, path = 'complete-fixed-early-behavior-fits', OUTPUT / 'complete.json'
    else:
        expected, path = 'complete-exact-early-behavior-information-review', ROOT / 'reports/hog26_early_behavior_probe_review_20260913.json'
    if json.loads(path.read_text())['status'] != expected:
        raise ValueError('auxiliary completion status differs')
    validate(require_memory=True)
    status(stage='early-public-behavior-' + args.mode + '-complete', **result)


if __name__ == '__main__':
    main()
