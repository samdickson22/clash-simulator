"""Guard the remaining fixed tree pairs and all exact reviews after replay parity."""

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
from continuation_contract import OUTPUT, PLAN, prepare, validate
from import_completed import import_completed
from value_contract import PLAN as ORIGINAL_PLAN
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


def run_job(arguments, log_path, stage):
    validate()
    environment = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1')
    peak, killed = 0, False
    with log_path.open('x') as log:
        process = subprocess.Popen(['/Users/sam/Desktop/code/clasher/.venv/bin/python', '-u', *arguments],
                                   env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        status(stage=stage, pid=process.pid, log=str(log_path), execution_plan_sha256=sha(PLAN), memory_limit_bytes=LIMIT)
        try:
            while process.poll() is None:
                try:
                    live = psutil.Process(process.pid)
                    peak = max(peak, live.memory_info().rss + sum(p.memory_info().rss for p in live.children(recursive=True)))
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
    result = {'exit_code': code, 'peak_rss_bytes': peak, 'memory_limit_terminated': killed, 'execution_plan_sha256': sha(PLAN)}
    publish(log_path.with_suffix('.receipt.json'), result)
    if code or killed:
        status(stage='threaded-expanded-value-job-failed', failed_stage=stage, **result)
        raise SystemExit(code or 1)
    validate()


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
    plan = validate()
    OUTPUT.mkdir(exist_ok=False)
    logs = OUTPUT / 'logs'
    logs.mkdir()
    publish(OUTPUT / 'manifest.json', {'original_model_plan_sha256': sha(ORIGINAL_PLAN), 'execution_plan_sha256': sha(PLAN),
            'execution_sources': plan['sources'], 'execution_resources': plan['resources'], 'acceptance': False})
    import_completed()
    for seed in plan['seeds']:
        for fold in range(4):
            if (seed, fold) == (1279501, 0):
                continue
            stem = f'trees-seed{seed}-fold{fold}'
            run_job(['experiments/hog26_threaded_value_fit/fit_tree.py', '--seed', str(seed), '--fold', str(fold)],
                    logs / f'{stem}.log', 'threaded-expanded-value-fit-' + stem)
    for kind in ('globals', 'trees'):
        for seed in plan['seeds']:
            stem = f'{kind}-seed{seed}-review'
            run_job(['experiments/hog26_threaded_value_fit/review_fits.py', '--kind', kind, '--seed', str(seed)],
                    logs / f'{stem}.log', 'threaded-expanded-value-' + stem)
    paths = [OUTPUT / kind / f'seed{seed}-review.json' for kind in ('globals', 'trees') for seed in plan['seeds']]
    for path in paths:
        review = json.loads(path.read_text())
        if review['status'] != 'complete-exact-expanded-fitting-review' or review['execution_plan_sha256'] != sha(PLAN):
            raise ValueError('all exact continuation reviews must complete')
    publish(OUTPUT / 'complete.json', {'status': 'complete-threaded-value-fitting-and-exact-review',
            'plan_sha256': sha(ORIGINAL_PLAN), 'execution_plan_sha256': sha(PLAN),
            'reviews': {str(path.relative_to(OUTPUT)): sha(path) for path in paths},
            'fold_bundles': 16, 'estimator_models': 24, 'additional_tree_estimator_fits': 14,
            'imported_estimator_models': 10, 'acceptance': False, 'opened_diagnostic_allowed': False})
    status(stage='threaded-expanded-value-complete-awaiting-scientific-review', output=str(OUTPUT), fitting_allowed=False)


if __name__ == '__main__':
    main()
