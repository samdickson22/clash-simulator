"""Run every fixed fold and exact review under one lease and an 18 GiB guard."""

import fcntl
import json
import os
import signal
import subprocess
import time

import psutil
import torch
from value_contract import OUTPUT, PLAN, ROOT, load_plan, publish, sha

MONITOR = ROOT.home() / 'Library/Application Support/ClasherMonitor'
LIMIT = 18 * 1024**3


def status(**fields):
    fields.update(updated_at=time.time(), supervisor_pid=os.getpid(), acceptance=False)
    path = MONITOR / 'comparison-status.json'
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(fields, indent=2) + '\n')
    temp.replace(path)
    print(json.dumps(fields), flush=True)


def run_job(arguments, log_path, stage):
    load_plan()
    peak, killed = 0, False
    environment = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1')
    with log_path.open('x') as log:
        process = subprocess.Popen(['/Users/sam/Desktop/code/clasher/.venv/bin/python', '-u', *arguments],
                                   env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        status(stage=stage, pid=process.pid, log=str(log_path), plan_sha256=sha(PLAN), memory_limit_bytes=LIMIT)
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
    receipt = {'exit_code': code, 'peak_rss_bytes': peak, 'memory_limit_terminated': killed, 'plan_sha256': sha(PLAN)}
    publish(log_path.with_suffix('.receipt.json'), receipt)
    if code or killed:
        status(stage='expanded-value-job-failed', failed_stage=stage, **receipt)
        raise SystemExit(code or 1)
    load_plan()


def main():
    os.chdir(ROOT)
    torch.set_num_threads(1)
    lock = (MONITOR / 'comparison.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    plan = load_plan()
    OUTPUT.mkdir(exist_ok=False)
    logs = OUTPUT / 'logs'
    logs.mkdir()
    publish(OUTPUT / 'manifest.json', {'plan_sha256': sha(PLAN), 'implementation': plan.implementation,
                                      'resources': plan.resources, 'acceptance': False})
    for kind in ('globals', 'trees'):
        for seed in plan.seeds:
            for fold in range(plan.folds):
                name = f'{kind}-seed{seed}-fold{fold}'
                run_job(['experiments/hog26_expanded_value_fit/fit_one.py', '--kind', kind, '--seed', str(seed), '--fold', str(fold)],
                        logs / (name + '.log'), 'expanded-value-fit-' + name)
    for kind in ('globals', 'trees'):
        for seed in plan.seeds:
            name = f'{kind}-seed{seed}-review'
            run_job(['experiments/hog26_expanded_value_fit/review_fits.py', '--kind', kind, '--seed', str(seed)],
                    logs / (name + '.log'), 'expanded-value-' + name)
    review_paths = [OUTPUT / kind / f'seed{seed}-review.json' for kind in ('globals', 'trees') for seed in plan.seeds]
    for path in review_paths:
        result = json.loads(path.read_text())
        if result['status'] != 'complete-exact-expanded-fitting-review' or result['plan_sha256'] != sha(PLAN):
            raise ValueError('exact fitting review incomplete')
    publish(OUTPUT / 'complete.json', {'status': 'complete-expanded-value-fitting-and-exact-review',
            'plan_sha256': sha(PLAN), 'reviews': {str(p.relative_to(OUTPUT)): sha(p) for p in review_paths},
            'fold_bundles': 16, 'estimator_fits': 24, 'acceptance': False, 'opened_diagnostic_allowed': False})
    status(stage='expanded-value-complete-awaiting-scientific-review', output=str(OUTPUT), fitting_allowed=False)


if __name__ == '__main__':
    main()
