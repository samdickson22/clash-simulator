"""Supervise synthetic memory proof,24classifier fits, exact reviews and science."""

import argparse
import fcntl
import json
import os
import signal
import subprocess
import time
from contextlib import ExitStack
from pathlib import Path

import psutil
import torch
from three_class_contract import OUTPUT, PIN, SEEDS, prepare, validate
from value_contract import ROOT, publish, sha


def run_stage(stage, commands, base):
    with ExitStack() as stack:
        processes = []
        for name, command in commands:
            log = stack.enter_context((ROOT / f'reports/hog26_three_class_phase_{name}_20260913.log').open('x'))
            processes.append(subprocess.Popen(['/Users/sam/Desktop/code/clasher/.venv/bin/python', '-u', *command], cwd=ROOT,
                    env=dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1'),
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True))
        state = {'stage': 'three-class-phase-' + stage, 'supervisor_pid': os.getpid(),
                 'pids': [p.pid for p in processes], 'updated_at': time.time(), 'policy_learning': False, 'acceptance': False}
        path = base / 'comparison-status.json'
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(state, indent=2))
        temporary.replace(path)
        peak, killed = 0, False
        try:
            while any(p.poll() is None for p in processes):
                if any(p.poll() not in (None, 0) for p in processes):
                    break
                rss = 0
                for process in processes:
                    try:
                        live = psutil.Process(process.pid)
                        rss += live.memory_info().rss + sum(p.memory_info().rss for p in live.children(recursive=True))
                    except psutil.NoSuchProcess:
                        pass
                peak = max(peak, rss)
                if peak > 18 * 1024**3:
                    killed = True
                    break
                time.sleep(.5)
        finally:
            for process in processes:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
            for process in processes:
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
        result = {'exit_codes': [p.returncode for p in processes], 'peak_rss_bytes': peak,
                  'memory_limit_terminated': killed, 'pin_sha256': sha(PIN)}
        publish(ROOT / f'reports/hog26_three_class_phase_{stage}_guard_20260913.json', result)
        if killed or any(result['exit_codes']):
            state.update(stage='three-class-phase-failed', **result)
            temporary.write_text(json.dumps(state, indent=2))
            temporary.replace(path)
            raise SystemExit(1)
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=('pin', 'memory', 'run'), required=True)
    args = parser.parse_args()
    torch.set_num_threads(1)
    if args.mode == 'pin':
        prepare()
        print('three-class phase pinned', sha(PIN), flush=True)
        return
    base = Path('/Users/sam/Library/Application Support/ClasherMonitor')
    with (base / 'comparison.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        validate()
        if args.mode == 'memory':
            result = run_stage('memory', [('memory', ['experiments/hog26_three_class_phase/memory_probe.py'])], base)
            validate(memory=True)
            stage = {'stage': 'three-class-phase-memory-complete', 'guard': result, 'updated_at': time.time(), 'acceptance': False}
        else:
            validate(memory=True)
            if OUTPUT.exists():
                raise ValueError('preserve previous three-class phase campaign')
            OUTPUT.mkdir()
            publish(OUTPUT / 'manifest.json', {'pin_sha256': sha(PIN), 'acceptance': False})
            stages = {}
            for seed in SEEDS:
                for fold in range(4):
                    name = f'fit-seed{seed}-fold{fold}'
                    stages[name] = run_stage(name, [(name, ['experiments/hog26_three_class_phase/fit_fold.py', '--seed', str(seed), '--fold', str(fold)])], base)
                    completed = OUTPUT / f'seed{seed}-fold{fold}' / 'complete.json'
                    if json.loads(completed.read_text())['status'] != 'complete-three-class-phase-fold':
                        raise ValueError('complete fitted fold required')
            stages['reviews'] = run_stage('reviews', [(f'review-seed{seed}', ['experiments/hog26_three_class_phase/review_seed.py', '--seed', str(seed)]) for seed in SEEDS], base)
            stages['science'] = run_stage('science', [('science', ['experiments/hog26_three_class_phase/scientific_review.py'])], base)
            validate(memory=True)
            science = OUTPUT / 'scientific-review.json'
            if json.loads(science.read_text())['status'] != 'complete-three-class-phase-scientific-review':
                raise ValueError('complete scientific comparison required')
            publish(OUTPUT / 'complete.json', {'status': 'complete-three-class-phase-comparison', 'pin_sha256': sha(PIN),
                    'scientific_review_sha256': sha(science), 'review_hashes': {str(seed): sha(OUTPUT / f'seed{seed}-review.json') for seed in SEEDS},
                    'stages': stages, 'acceptance': False})
            stage = {'stage': 'three-class-phase-complete', 'stages': stages, 'updated_at': time.time(), 'acceptance': False}
        path = base / 'comparison-status.json'
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(stage, indent=2))
        temporary.replace(path)
        print(json.dumps(stage), flush=True)


if __name__ == '__main__':
    main()
