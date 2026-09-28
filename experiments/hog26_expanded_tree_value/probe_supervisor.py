"""Exclusive synthetic memory probes, with immutable input source receipts."""

import fcntl
import hashlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[2]
MONITOR = Path('/Users/sam/Library/Application Support/ClasherMonitor')
LIMIT = 18 * 1024**3


def source_hashes():
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path(__file__).parent.glob('*.py'))}


def status(**fields):
    fields.update(updated_at=time.time(), supervisor_pid=os.getpid(), fitting_allowed=False)
    path = MONITOR / 'comparison-status.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(fields, indent=2) + '\n')
    temporary.replace(path)
    print(json.dumps(fields), flush=True)


def main():
    os.chdir(ROOT)
    lock = (MONITOR / 'comparison.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    review = json.loads((ROOT / 'reports/hog26_expanded_cache_review_20260913.json').read_text())
    if review['status'] != 'complete-expanded-cache-review' or review['games'] != 6144:
        raise ValueError('complete independent cache review required')
    hashes = source_hashes()
    output = ROOT / 'reports/hog26_expanded_tree_value_memory_20260913'
    output.mkdir(exist_ok=False)
    (output / 'source_pin.json').write_text(json.dumps(hashes, indent=2) + '\n')
    environment = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1')
    for kind in ('globals', 'trees'):
        report_path = output / f'{kind}.json'
        log_path = output / f'{kind}.log'
        command = ['/Users/sam/Desktop/code/clasher/.venv/bin/python', '-u',
                   'experiments/hog26_expanded_tree_value/memory_probe.py', '--kind', kind, '--output', str(report_path)]
        peak, killed = 0, False
        with log_path.open('x') as log:
            process = subprocess.Popen(command, env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            status(stage=f'expanded-value-memory-{kind}', pid=process.pid, log=str(log_path), memory_limit_bytes=LIMIT)
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
        receipt = {'exit_code': code, 'peak_rss_bytes': peak, 'memory_limit_terminated': killed,
                   'source_unchanged': source_hashes() == hashes}
        (output / f'{kind}-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        if code or killed or not receipt['source_unchanged'] or not report_path.is_file():
            status(stage='expanded-value-memory-failed', kind=kind, **receipt)
            raise SystemExit(code or 1)
    status(stage='expanded-value-memory-complete-awaiting-model-plan', output=str(output))


if __name__ == '__main__':
    main()
