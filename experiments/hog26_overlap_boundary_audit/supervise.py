"""Audit reviewed overlap boundary components after fitting releases its lease."""

import fcntl
import json
import os
import signal
import subprocess
import time
from pathlib import Path

import psutil
from value_contract import ROOT, publish, sha


def main():
    os.chdir(ROOT)
    base = Path('/Users/sam/Library/Application Support/ClasherMonitor')
    lock = (base / 'comparison.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    log_path = ROOT / 'reports/hog26_overlap_boundary_audit_20260913.log'
    pin_path = ROOT / 'reports/hog26_overlap_boundary_audit_pin_20260913.json'
    with log_path.open('x') as log:
        process = subprocess.Popen(['/Users/sam/Desktop/code/clasher/.venv/bin/python', '-u',
                                    'experiments/hog26_overlap_boundary_audit/audit_boundaries.py'],
                                   env=dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1'),
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        status = {'stage': 'overlap-boundary-audit', 'pid': process.pid, 'supervisor_pid': os.getpid(),
                  'log': str(log_path), 'updated_at': time.time(), 'acceptance': False}
        path = base / 'comparison-status.json'
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(status, indent=2) + '\n')
        temporary.replace(path)
        peak, killed = 0, False
        try:
            while process.poll() is None:
                try:
                    live = psutil.Process(process.pid)
                    peak = max(peak, live.memory_info().rss + sum(child.memory_info().rss for child in live.children(recursive=True)))
                except psutil.NoSuchProcess:
                    pass
                if peak > 18 * 1024**3:
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
    result = {'exit_code': code, 'peak_rss_bytes': peak, 'memory_limit_terminated': killed, 'pin_sha256': sha(pin_path)}
    publish(ROOT / 'reports/hog26_overlap_boundary_audit_guard_20260913.json', result)
    status.update(stage='overlap-boundary-audit-failed' if code or killed else 'overlap-boundary-audit-complete',
                  updated_at=time.time(), **result)
    temporary.write_text(json.dumps(status, indent=2) + '\n')
    temporary.replace(path)
    if code or killed:
        raise SystemExit(code or 1)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
