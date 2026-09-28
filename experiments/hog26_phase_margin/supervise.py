"""One leased, memory-guarded phase comparison with exclusive artifacts."""

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
from phase_contract import MEMORY, OUTPUT, PLAN, SEEDS, prepare, validate
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


def worker(name, script, arguments=()):
    log_path = ROOT / f'reports/hog26_phase_margin_{name}_20260913.log'
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1')
    peak, killed = 0, False
    with log_path.open('x') as log:
        process = subprocess.Popen(['/Users/sam/Desktop/code/clasher/.venv/bin/python', '-u',
                                    'experiments/hog26_phase_margin/' + script, *arguments],
                                   env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        status(stage='phase-margin-' + name, pid=process.pid, log=str(log_path), plan_sha256=sha(PLAN))
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
    publish(ROOT / f'reports/hog26_phase_margin_{name}_guard_20260913.json', result)
    if code or killed:
        status(stage='phase-margin-' + name + '-failed', **result)
        raise SystemExit(code or 1)
    status(stage='phase-margin-' + name + '-complete', **result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('pin', 'memory', 'run'), required=True)
    args = parser.parse_args()
    os.chdir(ROOT)
    torch.set_num_threads(1)
    lock = (MONITOR / 'comparison.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if args.mode == 'pin':
        prepare()
        return
    validate(memory=args.mode == 'run')
    if args.mode == 'memory':
        worker('memory', 'memory_probe.py')
        validate(memory=True)
        if json.loads(MEMORY.read_text())['status'] != 'complete-phase-margin-synthetic-memory':
            raise ValueError('phase memory completion required')
        return
    OUTPUT.mkdir(exist_ok=False)
    publish(OUTPUT / 'manifest.json', {'plan_sha256': sha(PLAN), 'regressor_fits': 24, 'acceptance': False})
    guards = {}
    for seed in SEEDS:
        for fold in range(4):
            name = f'seed{seed}-fold{fold}'
            guards[name] = worker(name, 'fit_phase.py', ('--seed', str(seed), '--fold', str(fold)))
            if json.loads((OUTPUT / name / 'complete.json').read_text())['status'] != 'complete-phase-margin-fold':
                raise ValueError('complete phase fold required')
    for seed in SEEDS:
        guards[f'review-seed{seed}'] = worker(f'review-seed{seed}', 'review_phase.py', ('--seed', str(seed)))
    guards['science'] = worker('science', 'phase_science.py')
    science = json.loads((OUTPUT / 'scientific-review.json').read_text())
    if science['status'] != 'complete-phase-margin-scientific-review':
        raise ValueError('complete phase scientific review required')
    validate(memory=True)
    publish(OUTPUT / 'complete.json', {'status': 'complete-phase-margin-comparison', 'plan_sha256': sha(PLAN),
            'scientific_review_sha256': sha(OUTPUT / 'scientific-review.json'), 'regressor_fits': 24,
            'unchanged_global_references': 8, 'guards': guards, 'acceptance': False})
    status(stage='phase-margin-comparison-complete', plan_sha256=sha(PLAN), output=str(OUTPUT))


if __name__ == '__main__':
    main()
