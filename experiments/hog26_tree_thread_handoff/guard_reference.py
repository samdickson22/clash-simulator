"""Preserve the first complete serial tree bundle before a separately gated replay."""

import json
import os
import signal
import time
from pathlib import Path

import psutil
import torch
from value_contract import OUTPUT, PLAN, ROOT, load_plan, publish, sha

MONITOR = Path('/Users/sam/Library/Application Support/ClasherMonitor')
PARENT = 96292
CHILD = 6657
LIMIT = 18 * 1024**3


def status(**fields):
    fields.update(updated_at=time.time(), supervisor_pid=os.getpid(), acceptance=False,
                  original_supervisor_pid=PARENT, original_child_pid=CHILD)
    path = MONITOR / 'comparison-status.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(fields, indent=2) + '\n')
    temporary.replace(path)
    print(json.dumps(fields), flush=True)


def stop_requested(signum, _frame):
    raise SystemExit(128 + signum)


def main():
    os.chdir(ROOT)
    torch.set_num_threads(1)
    load_plan()
    parent, child = psutil.Process(PARENT), psutil.Process(CHILD)
    if ('experiments/hog26_expanded_value_fit/supervisor.py' not in parent.cmdline()
            or child.ppid() != PARENT or child.cwd() != str(ROOT)
            or child.cmdline()[2:] != ['experiments/hog26_expanded_value_fit/fit_one.py', '--kind', 'trees', '--seed', '1279501', '--fold', '0']):
        raise ValueError('owned serial process identities differ')
    existing = sorted((OUTPUT / 'globals').glob('seed*-fold*/complete.json'))
    if len(existing) != 8 or list((OUTPUT / 'trees').glob('seed*-fold*/complete.json')):
        raise ValueError('expected eight complete globals and the first active tree')
    for path in existing:
        result = json.loads(path.read_text())
        if result['status'] != 'complete-expanded-value-fold' or result['plan_sha256'] != sha(PLAN):
            raise ValueError('globals reference completion differs')
        for name, expected in result['artifacts'].items():
            if sha(path.parent / name) != expected:
                raise ValueError('globals artifact changed')
    probe = ROOT / 'reports/hog26_tree_thread_synthetic_probe_20260913.json'
    proof = json.loads(probe.read_text())
    receipt = json.loads(probe.with_suffix('.receipt.json').read_text())
    probe_pin = json.loads(probe.with_suffix('.pin.json').read_text())
    if (proof['status'] != 'complete-exact-synthetic-thread-probe' or receipt['exit_code'] != 0
            or receipt['memory_limit_terminated'] or not receipt['source_unchanged']
            or any(sha(path) != expected for path, expected in probe_pin['sources'].items())):
        raise ValueError('exact synthetic thread proof required')
    pin_path = ROOT / 'reports/hog26_tree_thread_handoff_pin_20260913.json'
    publish(pin_path, {'source_sha256': sha(__file__), 'original_plan_sha256': sha(PLAN),
                      'synthetic_proof_sha256': sha(probe), 'parent_pid': PARENT, 'child_pid': CHILD,
                      'scope': 'Pause only the owned serial supervisor while this guard covers its existing child. Preserve the first complete tree, then retire the serial supervisor. No parameter or thread change to the child.',
                      'limit_bytes': LIMIT, 'acceptance': False})
    signal.signal(signal.SIGTERM, stop_requested)
    signal.signal(signal.SIGINT, stop_requested)
    paused, retired, peak = False, False, 0
    try:
        rss = child.memory_info().rss
        if rss > LIMIT:
            raise ValueError('active child already exceeds the inherited limit')
        parent.suspend()
        paused = True
        status(stage='expanded-value-reference-tree-guard-takeover', pid=CHILD,
               log=str(OUTPUT / 'logs/trees-seed1279501-fold0.log'), pin_sha256=sha(pin_path),
               memory_limit_bytes=LIMIT, prior_guard_scope='Original supervisor covered the run until this takeover; its threshold was the same 18 GiB.')
        while child.is_running() and child.status() != psutil.STATUS_ZOMBIE:
            peak = max(peak, child.memory_info().rss + sum(p.memory_info().rss for p in child.children(recursive=True)))
            if peak > LIMIT:
                child.terminate()
                raise ValueError('inherited memory limit exceeded; original supervisor will resume and record failure')
            time.sleep(.5)
        complete_path = OUTPUT / 'trees/seed1279501-fold0/complete.json'
        complete = json.loads(complete_path.read_text())
        if complete['status'] != 'complete-expanded-value-fold' or complete['plan_sha256'] != sha(PLAN):
            raise ValueError('first reference tree did not complete')
        for name, expected in complete['artifacts'].items():
            if sha(complete_path.parent / name) != expected:
                raise ValueError('reference tree artifact changed')
        load_plan()
        parent.terminate()
        parent.resume()
        paused = False
        parent.wait(timeout=15)
        retired = True
        report = {'status': 'serial-reference-complete-supervisor-intentionally-retired',
                  'source_sha256': sha(__file__), 'pin_sha256': sha(pin_path), 'original_plan_sha256': sha(PLAN),
                  'complete_globals': {str(path.relative_to(ROOT)): sha(path) for path in existing},
                  'complete_tree': str(complete_path.relative_to(ROOT)), 'complete_tree_sha256': sha(complete_path),
                  'takeover_peak_rss_bytes': peak, 'memory_limit_bytes': LIMIT,
                  'memory_scope': 'Original 18 GiB guard before takeover; this 18 GiB guard thereafter. Peak covers the takeover interval only.',
                  'all_artifacts_preserved': True, 'remaining_fitting_allowed': False, 'full_thread_replay_required': True, 'acceptance': False}
        publish(ROOT / 'reports/hog26_tree_thread_serial_reference_20260913.json', report)
        status(stage='expanded-value-serial-reference-complete-awaiting-full-thread-replay',
               reference=str(complete_path), takeover_peak_rss_bytes=peak, fitting_allowed=False)
    finally:
        if paused and not retired and parent.is_running():
            parent.resume()
            status(stage='expanded-value-reference-takeover-aborted-original-supervisor-resumed', pid=CHILD)


if __name__ == '__main__':
    main()
