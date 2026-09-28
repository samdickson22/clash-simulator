"""Guard the actual-loss synthetic memory check with explicit source pins."""

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
FILES = ('experiments/hog26_expanded_value_fit/value_models.py',
         'experiments/hog26_expanded_value_fit/value_storage.py',
         'experiments/hog26_expanded_value_fit/actual_memory.py',
         'experiments/hog26_expanded_value_fit/test_value_models.py',
         'experiments/hog26_expanded_value_fit/test_column_layout.py',
         'experiments/hog26_expanded_tree_value/health_features.py',
         'experiments/hog26_expanded_value_memory/supervise.py')


def hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES}


def status(**fields):
    fields.update(updated_at=time.time(), supervisor_pid=os.getpid(), fitting_allowed=False)
    path = MONITOR / 'comparison-status.json'
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(fields, indent=2) + '\n')
    temp.replace(path)
    print(json.dumps(fields), flush=True)


def main():
    os.chdir(ROOT)
    lock = (MONITOR / 'comparison.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    prefix = ROOT / 'reports/hog26_expanded_value_actual_memory_20260913'
    pin = prefix.with_suffix('.pin.json')
    with pin.open('x') as stream:
        json.dump(hashes(), stream, indent=2)
        stream.write('\n')
    original = hashes()
    environment = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1')
    peak, killed = 0, False
    with prefix.with_suffix('.log').open('x') as log:
        process = subprocess.Popen(['/Users/sam/Desktop/code/clasher/.venv/bin/python', '-u',
                                    'experiments/hog26_expanded_value_fit/actual_memory.py'],
                                   env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        status(stage='expanded-value-actual-loss-memory', pid=process.pid, log=str(prefix.with_suffix('.log')))
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
    passed = code == 0 and not killed and hashes() == original and prefix.with_suffix('.json').is_file()
    result = {'status': 'passed' if passed else 'failed', 'exit_code': code, 'peak_rss_bytes': peak,
              'limit_bytes': LIMIT, 'memory_limit_terminated': killed, 'source_unchanged': hashes() == original,
              'source_pin': str(pin), 'fitting_allowed': False}
    with prefix.with_suffix('.receipt.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    status(stage='expanded-value-actual-memory-' + result['status'], **result)
    if not passed:
        raise SystemExit(code or 1)


if __name__ == '__main__':
    main()
