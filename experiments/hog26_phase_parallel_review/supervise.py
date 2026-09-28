"""Run two unchanged phase reviews concurrently after all fixed fits complete."""

import fcntl
import json
import os
import runpy
import signal
import subprocess
import time
from pathlib import Path

import psutil
import torch
from phase_contract import OUTPUT, PLAN, SEEDS, validate
from value_contract import ROOT, publish, sha

PARENT = 32596
LIMIT = 18 * 1024**3
MONITOR = Path('/Users/sam/Library/Application Support/ClasherMonitor')
PIN = ROOT / 'reports/hog26_phase_parallel_review_plan_20260913.json'


def identity(process, suffix, *, parent_pid=None):
    if (process.cwd() != str(ROOT) or process.cmdline()[-len(suffix):] != suffix
            or (parent_pid is not None and process.ppid() != parent_pid)):
        raise ValueError('owned phase process identity differs')


def running(process):
    try:
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def status(**fields):
    fields.update(updated_at=time.time(), supervisor_pid=os.getpid(), acceptance=False)
    path = MONITOR / 'comparison-status.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(fields, indent=2) + '\n')
    temporary.replace(path)
    print(json.dumps(fields), flush=True)


def retire_parent(parent):
    if running(parent):
        parent.terminate()
        parent.resume()
        parent.wait(timeout=15)


def interrupted(signum, _frame):
    raise SystemExit(128 + signum)


def main():
    os.chdir(ROOT)
    torch.set_num_threads(1)
    source_sha = sha(__file__)
    plan = validate(memory=True)
    parent = psutil.Process(PARENT)
    identity(parent, ['experiments/hog26_phase_margin/supervise.py', '--mode', 'run'])
    print(json.dumps({'stage': 'waiting-for-all-phase-fits-and-first-review', 'original_parent_pid': PARENT,
                      'source_sha256': source_sha}), flush=True)
    while True:
        if not running(parent):
            raise ValueError('original phase supervisor exited before review handoff')
        state = json.loads((MONITOR / 'comparison-status.json').read_text())
        if state.get('stage') == 'phase-margin-review-seed1279501' and state.get('supervisor_pid') == PARENT:
            existing = psutil.Process(state['pid'])
            break
        time.sleep(1)
    identity(existing, ['experiments/hog26_phase_margin/review_phase.py', '--seed', '1279501'], parent_pid=PARENT)
    if not running(existing) or (OUTPUT / 'complete.json').exists():
        raise ValueError('active first review and incomplete root required')
    resources, guards = {str(PLAN.relative_to(ROOT)): sha(PLAN)}, {}
    for seed in SEEDS:
        for fold in range(4):
            name = f'seed{seed}-fold{fold}'
            directory = OUTPUT / name
            path = directory / 'complete.json'
            complete = json.loads(path.read_text())
            if (complete['status'] != 'complete-phase-margin-fold' or complete['seed'] != seed
                    or complete['fold'] != fold or complete['plan_sha256'] != sha(PLAN)):
                raise ValueError('all eight fixed phase bundles must be complete')
            resources[str(path.relative_to(ROOT))] = sha(path)
            for artifact, expected in complete['artifacts'].items():
                if sha(directory / artifact) != expected:
                    raise ValueError('completed phase artifact changed')
            guard_path = ROOT / f'reports/hog26_phase_margin_{name}_guard_20260913.json'
            guard = json.loads(guard_path.read_text())
            if guard['exit_code'] != 0 or guard['memory_limit_terminated'] or guard['plan_sha256'] != sha(PLAN):
                raise ValueError('successful original fitting guard required')
            guards[name] = guard
            resources[str(guard_path.relative_to(ROOT))] = sha(guard_path)
    second_log = ROOT / 'reports/hog26_phase_margin_review-seed1279502_20260913.log'
    if any(path.exists() for path in (second_log, OUTPUT / 'seed1279502-review.json', OUTPUT / 'seed1279502-oof.npz')):
        raise ValueError('second phase review already started')
    if sha(__file__) != source_sha:
        raise ValueError('waiting scheduler source changed')
    publish(PIN, {'schema': 'clasher.hog26.phase-parallel-review.v1', 'source_sha256': source_sha,
                  'phase_plan_sha256': sha(PLAN), 'resources': resources, 'seeds': list(SEEDS),
                  'worker_source_sha256': plan['sources']['experiments/hog26_phase_margin/review_phase.py'],
                  'worker_threads': 1, 'aggregate_memory_limit_bytes': LIMIT,
                  'original_parent_pid': PARENT, 'existing_review_pid': existing.pid,
                  'scope': 'Scheduling only. Both exact reviewers and scientific closeout use unchanged frozen source, model artifacts, metrics, bootstrap seeds and output paths. No fitting or quality-based selection.',
                  'acceptance': False})
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    processes = {SEEDS[0]: existing}
    children, logs, peaks, completed = {}, {}, {SEEDS[0]: 0}, {}
    aggregate_peak, paused, success, lease = 0, False, False, None
    try:
        identity(parent, ['experiments/hog26_phase_margin/supervise.py', '--mode', 'run'])
        identity(existing, ['experiments/hog26_phase_margin/review_phase.py', '--seed', '1279501'], parent_pid=PARENT)
        parent.suspend()
        paused = True
        log = second_log.open('x')
        logs[SEEDS[1]] = log
        child = subprocess.Popen(['/Users/sam/Desktop/code/clasher/.venv/bin/python', '-u',
                                  'experiments/hog26_phase_margin/review_phase.py', '--seed', str(SEEDS[1])],
                                 env=dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1'),
                                 stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        children[SEEDS[1]], processes[SEEDS[1]], peaks[SEEDS[1]] = child, psutil.Process(child.pid), 0
        status(stage='parallel-phase-exact-reviews', pids={str(seed): process.pid for seed, process in processes.items()},
               original_supervisor_paused=PARENT, aggregate_limit_bytes=LIMIT, schedule_plan_sha256=sha(PIN))
        while len(completed) != 2:
            total = 0
            for seed, process in processes.items():
                if seed in completed:
                    continue
                if running(process):
                    try:
                        rss = process.memory_info().rss + sum(p.memory_info().rss for p in process.children(recursive=True))
                    except psutil.NoSuchProcess:
                        continue
                    peaks[seed] = max(peaks[seed], rss)
                    total += rss
                    continue
                code = children[seed].wait() if seed in children else None
                path = OUTPUT / f'seed{seed}-review.json'
                result = json.loads(path.read_text())
                if (code not in (None, 0) or result['status'] != 'complete-exact-phase-margin-review'
                        or result['seed'] != seed or result['plan_sha256'] != sha(PLAN)
                        or set(result['audited_folds']) != {'0', '1', '2', '3'}
                        or result['oof_sha256'] != sha(OUTPUT / f'seed{seed}-oof.npz')):
                    raise ValueError('exact phase review did not complete successfully')
                completed[seed] = sha(path)
                receipt = {'exit_code': code, 'completion_artifact_verified': True, 'peak_rss_bytes': peaks[seed],
                           'memory_scope': 'takeover interval; original guard covered earlier execution' if seed == SEEDS[0] else 'entire worker',
                           'memory_limit_terminated': False, 'plan_sha256': sha(PLAN), 'schedule_plan_sha256': sha(PIN)}
                publish(ROOT / f'reports/hog26_phase_margin_review-seed{seed}_guard_20260913.json', receipt)
                guards[f'review-seed{seed}'] = receipt
                print(json.dumps({'seed': seed, 'status': 'phase-exact-review-complete'}), flush=True)
            aggregate_peak = max(aggregate_peak, total)
            if aggregate_peak > LIMIT:
                raise ValueError('combined phase review memory limit exceeded')
            time.sleep(.5)
        validate(memory=True)
        if sha(__file__) != source_sha:
            raise ValueError('phase review scheduler source changed')
        for path, expected in resources.items():
            if sha(ROOT / path) != expected:
                raise ValueError('phase review source completion changed')
        retire_parent(parent)
        paused = False
        lease = (MONITOR / 'comparison.lock').open('a')
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        functions = runpy.run_path(str(ROOT / 'experiments/hog26_phase_margin/supervise.py'), run_name='phase_supervisor_functions')
        guards['science'] = functions['worker']('science', 'phase_science.py')
        science_path = OUTPUT / 'scientific-review.json'
        if json.loads(science_path.read_text())['status'] != 'complete-phase-margin-scientific-review':
            raise ValueError('unchanged scientific review must finish')
        validate(memory=True)
        publish(OUTPUT / 'complete.json', {'status': 'complete-phase-margin-comparison', 'plan_sha256': sha(PLAN),
                'scientific_review_sha256': sha(science_path), 'regressor_fits': 24, 'unchanged_global_references': 8,
                'guards': guards, 'review_schedule_plan_sha256': sha(PIN), 'aggregate_review_peak_rss_bytes': aggregate_peak,
                'acceptance': False})
        success = True
        status(stage='phase-margin-comparison-complete', output=str(OUTPUT), schedule_plan_sha256=sha(PIN),
               aggregate_review_peak_rss_bytes=aggregate_peak)
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
            status(stage='parallel-phase-review-failed-preserved', aggregate_review_peak_rss_bytes=aggregate_peak,
                   completed_seeds=list(completed))
        for log in logs.values():
            log.close()
        if lease is not None:
            lease.close()


if __name__ == '__main__':
    main()
