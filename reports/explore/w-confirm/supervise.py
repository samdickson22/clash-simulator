"""Detached task-only supervision, process ceilings and compact progress."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time


def census():
    rows = []
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            args = path.read_bytes().replace(b'\0', b' ').decode(errors='replace')
            comm = (path.parent/'comm').read_text().strip()
            if comm not in ('python', 'python3', 'python3.12', 'bash', 'cargo', 'rustc', 'time'):
                continue
            if '/clasher' not in args and 'clasher.analysis' not in args:
                continue
            pid = int(path.parent.name)
            rows.append(dict(pid=pid, own='w-confirm-20261009-r1' in args,
                             nice=os.getpriority(os.PRIO_PROCESS, pid),
                             scheduler=os.sched_getscheduler(pid), command=args[:240]))
        except (OSError, ProcessLookupError): pass
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--job', type=Path, required=True)
    p.add_argument('--smoke', action='store_true')
    a = p.parse_args()
    assert os.sched_getscheduler(0) == os.SCHED_IDLE and os.getpriority(os.PRIO_PROCESS, 0) >= 10
    out = a.job / ('smoke' if a.smoke else 'reporting')
    rows = census()
    if len(rows) + (4 if a.smoke else 51) > 100:
        raise RuntimeError('combined admission refused')
    cmd = [os.sys.executable, '-B', str(a.job/'repo/reports/explore/w-confirm/run.py'),
           '--config', str(a.job/'repo/reports/explore/w-confirm/config.json'),
           '--out', str(out), '--workers', '3' if a.smoke else '50']
    if a.smoke: cmd += ['--smoke', '--pairs', '2']
    env = dict(os.environ, CLASHER_DELAY_NATIVE_DIR=str(a.job/'native'),
               CLASHER_ROOT=str(a.job/'repo'), CUDA_VISIBLE_DEVICES='',
               PYTHONHASHSEED='0', PYTHONPYCACHEPREFIX=str(a.job/'cache/pycache'),
               XDG_CACHE_HOME=str(a.job/'cache'), OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
               MKL_NUM_THREADS='1', RAYON_NUM_THREADS='1', NUMBA_CACHE_DIR=str(a.job/'cache/numba'))
    out.mkdir(parents=True, exist_ok=True)
    (out/'admission.json').write_text(json.dumps(dict(before=rows, command=cmd, time=time.time()), indent=2)+'\n')
    with (out/'worker.log').open('a') as log:
        child = subprocess.Popen(cmd, cwd=a.job/'repo', env=env, stdout=log, stderr=log, start_new_session=True)
        (out/'pid.json').write_text(json.dumps(dict(supervisor=os.getpid(), child=child.pid))+'\n')
        stopping = False
        def stop(signum, frame):
            nonlocal stopping
            stopping = True
            os.killpg(child.pid, signal.SIGTERM)
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        with (out/'census.jsonl').open('a', buffering=1) as census_log:
            while child.poll() is None:
                rows = census()
                own = [r for r in rows if r['own']]
                census_log.write(json.dumps(dict(time=time.time(), combined=len(rows), own=len(own), rows=rows))+'\n')
                if len(rows) > 100 or len(own) > 56 or any(r['nice'] < 10 or r['scheduler'] != os.SCHED_IDLE for r in own):
                    os.killpg(child.pid, signal.SIGTERM)
                    stopping = True
                games = list((out/'games').glob('*.json'))
                (a.job/'progress.json').write_text(json.dumps(dict(time=time.time(), games=len(games),
                     target=6 if a.smoke else 1900, combined=len(rows), own=len(own), stopping=stopping))+'\n')
                time.sleep(15)
        (out/'exit.json').write_text(json.dumps(dict(returncode=child.returncode, stopping=stopping, time=time.time()))+'\n')
        raise SystemExit(child.returncode)


if __name__ == '__main__': main()
