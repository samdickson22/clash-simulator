"""Freeze and audit the complete public-history cache under the shared lease."""

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
from history_contract import OUTPUT, PLAN, prepare, validate
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('pin', 'run'), required=True)
    args = parser.parse_args()
    os.chdir(ROOT)
    torch.set_num_threads(1)
    lock = (MONITOR / 'comparison.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if args.mode == 'pin':
        prepare()
        return
    validate()
    log_path = ROOT / 'reports/hog26_public_history_cache_20260913.log'
    environment = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1')
    peak, killed = 0, False
    with log_path.open('x') as log:
        process = subprocess.Popen(['/Users/sam/Desktop/code/clasher/.venv/bin/python', '-u',
                                    'experiments/hog26_history_cache/build_history_cache.py'],
                                   env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        status(stage='public-history-cache-audit', pid=process.pid, log=str(log_path), plan_sha256=sha(PLAN))
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
    publish(ROOT / 'reports/hog26_public_history_cache_guard_20260913.json', result)
    if code or killed:
        status(stage='public-history-cache-failed', **result)
        raise SystemExit(code or 1)
    validate()
    complete = json.loads((OUTPUT / 'complete.json').read_text())
    if complete['status'] != 'complete-audited-public-history-cache' or complete['prefix_checks'] != 6144:
        raise ValueError('complete history audit required')
    status(stage='public-history-cache-complete-awaiting-review', output=str(OUTPUT), **result)


if __name__ == '__main__':
    main()
