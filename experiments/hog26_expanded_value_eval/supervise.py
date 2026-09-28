"""Inference-only opened diagnostic under the shared lease and memory limit."""

import argparse
import fcntl
import json
import os
import signal
import subprocess
import time

import psutil
import torch
from evaluation_authority import PIN, validate_pin
from value_contract import ROOT, publish, sha

MONITOR = ROOT.home() / 'Library/Application Support/ClasherMonitor'
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
    parser.add_argument('--mode', choices=('evaluate', 'review'), required=True)
    args = parser.parse_args()
    torch.set_num_threads(1)
    os.chdir(ROOT)
    lock = (MONITOR / 'comparison.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    pin = validate_pin(json.loads(PIN.read_text()))
    suffix = '' if args.mode == 'evaluate' else '_review'
    log_path = ROOT / f'reports/hog26_expanded_value_diagnostic{suffix}_20260913.log'
    script_args = (['experiments/hog26_expanded_value_eval/evaluate.py', '--mode', 'evaluate']
                   if args.mode == 'evaluate' else ['experiments/hog26_expanded_value_eval/review_diagnostic.py'])
    peak, killed = 0, False
    environment = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1')
    with log_path.open('x') as log:
        process = subprocess.Popen(['/Users/sam/Desktop/code/clasher/.venv/bin/python', '-u',
                                    *script_args],
                                   env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        status(stage='expanded-value-opened-diagnostic-' + args.mode, pid=process.pid, log=str(log_path), pin_sha256=sha(PIN))
        try:
            while process.poll() is None:
                try:
                    live = psutil.Process(process.pid)
                    peak = max(peak, live.memory_info().rss + sum(c.memory_info().rss for c in live.children(recursive=True)))
                except psutil.NoSuchProcess:
                    pass
                if peak > LIMIT:
                    killed = True
                    break
                time.sleep(1)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
        code = process.wait()
    result = {'exit_code': code, 'peak_rss_bytes': peak, 'memory_limit_terminated': killed, 'pin_sha256': sha(PIN)}
    publish(ROOT / f'reports/hog26_expanded_value_diagnostic{suffix}_guard_20260913.json', result)
    if code or killed:
        status(stage='expanded-value-diagnostic-failed', **result)
        raise SystemExit(code or 1)
    validate_pin(pin)
    complete = json.loads((ROOT / 'reports/hog26_expanded_value_seed_transfer_20260913/complete.json').read_text())
    if complete['status'] != 'complete-expanded-value-diagnostic' or complete['fits'] != 16:
        raise ValueError('complete sixteen-model diagnostic required')
    if args.mode == 'review':
        reviewed = json.loads((ROOT / 'reports/hog26_expanded_value_diagnostic_review_20260913.json').read_text())
        if reviewed['status'] != 'complete-expanded-value-diagnostic-review' or reviewed['fits'] != 16:
            raise ValueError('complete exact diagnostic review required')
    status(stage='expanded-value-diagnostic-' + args.mode + '-complete', **result)


if __name__ == '__main__':
    main()
