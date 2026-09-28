"""Guard the frozen scientific closeout after all exact model reviews finish."""

import fcntl
import json
import os
from pathlib import Path

import torch
from continuation_contract import OUTPUT, PLAN, validate
from supervisor import run_job, status
from value_contract import ROOT, publish, sha


def main():
    os.chdir(ROOT)
    torch.set_num_threads(1)
    monitor = Path('/Users/sam/Library/Application Support/ClasherMonitor')
    lock = (monitor / 'comparison.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    validate()
    complete = json.loads((OUTPUT / 'complete.json').read_text())
    if complete['status'] != 'complete-threaded-value-fitting-and-exact-review' or len(complete['reviews']) != 4:
        raise ValueError('all four exact reviews must finish before scientific closeout')
    pin = ROOT / 'reports/hog26_threaded_value_scientific_review_pin_20260913.json'
    worker = ROOT / 'experiments/hog26_threaded_value_review/review_comparison.py'
    if json.loads(pin.read_text())['source_sha256'] != sha(worker):
        raise ValueError('scientific review worker differs from its frozen pin')
    publish(ROOT / 'reports/hog26_threaded_scientific_guard_plan_20260913.json',
            {'source_sha256': sha(__file__), 'worker_sha256': sha(worker), 'scientific_pin_sha256': sha(pin),
             'execution_plan_sha256': sha(PLAN), 'completion_sha256': sha(OUTPUT / 'complete.json'), 'acceptance': False})
    run_job(['experiments/hog26_threaded_value_review/review_comparison.py'],
            ROOT / 'reports/hog26_threaded_value_scientific_review_20260913.log', 'threaded-expanded-value-scientific-review')
    result_path = ROOT / 'reports/hog26_threaded_value_scientific_review_20260913.json'
    result = json.loads(result_path.read_text())
    if result['status'] != 'complete-threaded-value-scientific-review' or result['execution_plan_sha256'] != sha(PLAN):
        raise ValueError('scientific closeout completion differs')
    status(stage='threaded-expanded-value-scientific-review-complete', report=str(result_path), fitting_allowed=False)


if __name__ == '__main__':
    main()
