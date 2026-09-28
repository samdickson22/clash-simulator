"""Schedule four unchanged single-thread reviews under one combined memory guard."""

import json
import os
import signal
import subprocess
import time
from pathlib import Path

import psutil
import torch
from continuation_contract import OUTPUT, PLAN, validate
from value_contract import PLAN as ORIGINAL_PLAN
from value_contract import ROOT, publish, sha

PARENT = 30925
EXISTING = 53678
LIMIT = 18 * 1024**3
MONITOR = Path('/Users/sam/Library/Application Support/ClasherMonitor')
JOBS = (('globals', 1279501), ('globals', 1279502), ('trees', 1279501), ('trees', 1279502))


def status(**fields):
    fields.update(updated_at=time.time(), supervisor_pid=os.getpid(), acceptance=False)
    path = MONITOR / 'comparison-status.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(fields, indent=2) + '\n')
    temporary.replace(path)
    print(json.dumps(fields), flush=True)


def interrupted(signum, _frame):
    raise SystemExit(128 + signum)


def identity(process, *, parent_pid=None, suffix):
    if (process.cwd() != str(ROOT) or process.cmdline()[2:] != suffix
            or (parent_pid is not None and process.ppid() != parent_pid)):
        raise ValueError('owned review process identity differs')


def running(process):
    try:
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def retire_parent(parent):
    if parent.is_running():
        parent.terminate()
        parent.resume()
        parent.wait(timeout=15)


def main():
    os.chdir(ROOT)
    torch.set_num_threads(1)
    execution = validate()
    parent, existing = psutil.Process(PARENT), psutil.Process(EXISTING)
    identity(parent, suffix=['experiments/hog26_threaded_value_fit/supervisor.py', '--mode', 'run'])
    identity(existing, parent_pid=PARENT, suffix=['experiments/hog26_threaded_value_fit/review_fits.py', '--kind', 'globals', '--seed', '1279501'])
    if (OUTPUT / 'complete.json').exists():
        raise ValueError('preserve completed comparison')
    resources = {str(PLAN.relative_to(ROOT)): sha(PLAN)}
    for kind in ('globals', 'trees'):
        for seed in (1279501, 1279502):
            for fold in range(4):
                directory = OUTPUT / kind / f'seed{seed}-fold{fold}'
                path = directory / 'complete.json'
                result = json.loads(path.read_text())
                if (result['status'] != 'complete-expanded-value-fold' or result['kind'] != kind
                        or result['seed'] != seed or result['fold'] != fold or result['plan_sha256'] != sha(ORIGINAL_PLAN)):
                    raise ValueError('all sixteen fixed folds must be complete')
                resources[str(path.relative_to(ROOT))] = sha(path)
                for name, expected in result['artifacts'].items():
                    if sha(directory / name) != expected:
                        raise ValueError('completed fitting artifact changed')
    for kind, seed in JOBS[1:]:
        if any(path.exists() for path in (OUTPUT / 'logs' / f'{kind}-seed{seed}-review.log',
                                          OUTPUT / kind / f'seed{seed}-review.json', OUTPUT / kind / f'seed{seed}-oof.npz')):
            raise ValueError('parallel review destination already exists')
    pin_path = OUTPUT / 'review_schedule_plan.json'
    publish(pin_path, {'schema': 'clasher.hog26.parallel-exact-review-schedule.v1', 'source_sha256': sha(__file__),
                      'execution_plan_sha256': sha(PLAN), 'resources': resources,
                      'worker_source_sha256': execution['sources']['experiments/hog26_threaded_value_fit/review_fits.py'],
                      'jobs': [{'kind': kind, 'seed': seed} for kind, seed in JOBS], 'worker_threads': 1,
                      'aggregate_memory_limit_bytes': LIMIT, 'existing_worker_pid': EXISTING, 'original_parent_pid': PARENT,
                      'scope': 'Only scheduling changes. Every worker, seed, metric, bootstrap and output path remains unchanged. No model fitting or quality-based selection.',
                      'acceptance': False})
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    processes = {JOBS[0]: existing}
    children, logs, peaks, completed = {}, {}, {JOBS[0]: 0}, {}
    paused, success, aggregate_peak = False, False, 0
    try:
        if existing.memory_info().rss > LIMIT:
            raise ValueError('existing review already exceeds the shared limit')
        parent.suspend()
        paused = True
        environment = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1')
        for job in JOBS[1:]:
            kind, seed = job
            log = (OUTPUT / 'logs' / f'{kind}-seed{seed}-review.log').open('x')
            logs[job] = log
            child = subprocess.Popen(['/Users/sam/Desktop/code/clasher/.venv/bin/python', '-u',
                                      'experiments/hog26_threaded_value_fit/review_fits.py', '--kind', kind, '--seed', str(seed)],
                                     env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            children[job] = child
            processes[job] = psutil.Process(child.pid)
            peaks[job] = 0
        status(stage='parallel-expanded-value-exact-reviews', pids={f'{kind}-{seed}': process.pid for (kind, seed), process in processes.items()},
               original_supervisor_paused=PARENT, aggregate_limit_bytes=LIMIT, schedule_plan_sha256=sha(pin_path))
        while len(completed) != len(JOBS):
            total = 0
            for job, process in processes.items():
                if job in completed:
                    continue
                live = running(process)
                if live:
                    try:
                        rss = process.memory_info().rss + sum(p.memory_info().rss for p in process.children(recursive=True))
                    except psutil.NoSuchProcess:
                        continue
                    peaks[job] = max(peaks[job], rss)
                    total += rss
                    continue
                kind, seed = job
                code = children[job].wait() if job in children else None
                path = OUTPUT / kind / f'seed{seed}-review.json'
                result = json.loads(path.read_text())
                if (code not in (None, 0) or result['status'] != 'complete-exact-expanded-fitting-review'
                        or result['kind'] != kind or result['seed'] != seed or result['execution_plan_sha256'] != sha(PLAN)
                        or set(result['audited_folds']) != {'0', '1', '2', '3'}
                        or result['oof_sha256'] != sha(OUTPUT / kind / f'seed{seed}-oof.npz')):
                    raise ValueError('exact review did not complete successfully')
                completed[job] = sha(path)
                publish(OUTPUT / 'logs' / f'{kind}-seed{seed}-review.receipt.json',
                        {'exit_code': code, 'completion_artifact_verified': True, 'peak_rss_bytes': peaks[job],
                         'memory_scope': 'takeover interval; original guard covered earlier execution' if job == JOBS[0] else 'entire worker',
                         'schedule_plan_sha256': sha(pin_path), 'execution_plan_sha256': sha(PLAN), 'memory_limit_terminated': False})
                print(json.dumps({'kind': kind, 'seed': seed, 'status': 'exact-review-complete'}), flush=True)
            aggregate_peak = max(aggregate_peak, total)
            if aggregate_peak > LIMIT:
                raise ValueError('combined review memory limit exceeded')
            time.sleep(.5)
        validate()
        if sha(__file__) != json.loads(pin_path.read_text())['source_sha256']:
            raise ValueError('review scheduler source changed')
        for path, expected in resources.items():
            if sha(ROOT / path) != expected:
                raise ValueError('review input completion changed')
        retire_parent(parent)
        paused = False
        publish(OUTPUT / 'complete.json', {'status': 'complete-threaded-value-fitting-and-exact-review',
                'plan_sha256': sha(ORIGINAL_PLAN), 'execution_plan_sha256': sha(PLAN),
                'reviews': {f'{kind}/seed{seed}-review.json': completed[(kind, seed)] for kind, seed in JOBS},
                'fold_bundles': 16, 'estimator_models': 24, 'additional_tree_estimator_fits': 14, 'imported_estimator_models': 10,
                'review_schedule_plan_sha256': sha(pin_path), 'aggregate_review_peak_rss_bytes': aggregate_peak,
                'acceptance': False, 'opened_diagnostic_allowed': False})
        success = True
        status(stage='threaded-expanded-value-complete-awaiting-scientific-review', output=str(OUTPUT),
               aggregate_review_peak_rss_bytes=aggregate_peak, fitting_allowed=False)
    finally:
        if not success:
            for process in processes.values():
                if running(process):
                    try:
                        process.terminate()
                        process.wait(timeout=15)
                    except psutil.TimeoutExpired:
                        process.kill()
                    except psutil.NoSuchProcess:
                        pass
            if paused:
                retire_parent(parent)
                paused = False
            status(stage='parallel-expanded-value-review-failed-preserved', aggregate_review_peak_rss_bytes=aggregate_peak,
                   completed_jobs=[f'{kind}-{seed}' for kind, seed in completed], fitting_allowed=False)
        for log in logs.values():
            log.close()


if __name__ == '__main__':
    main()
