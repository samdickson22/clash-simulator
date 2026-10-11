"""PREREG-K4S STOP test on a qualification host: a running game must drain within 5 minutes of the owned
STOP file, leaving no owned process. Writes out/stoptest.json. The STOP file is removed afterwards only if this
test created it.

  runtime.sh reports/explore/k4s-confirm/stop_test.py --job J --stop /mpac/.../k4s-prep-20261011/STOP --cores 5,6,7,8,9
"""
import argparse, json, os, signal, subprocess, sys, time
from pathlib import Path
from common import utc


def alive(pgid):
    try:
        os.killpg(pgid, 0); return True
    except ProcessLookupError:
        return False


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--job', type=Path, required=True); ap.add_argument('--stop', type=Path, required=True)
    ap.add_argument('--cores', required=True); ap.add_argument('--warmup', type=float, default=30.); a = ap.parse_args()
    assert not a.stop.exists(), 'STOP already present; refuse to run (and never remove a STOP we did not create)'
    assert (a.job/'STOP').resolve() == a.stop.resolve() or (a.job/'STOP') == a.stop, 'job STOP must be (or link to) the owned STOP'
    out = a.job/'out'/'stoptest'; log = a.job/'out'/'stoptest.log'
    cmd = ['taskset', '-c', a.cores, 'bash', str(a.job/'repo/reports/explore/k4s-confirm/runtime.sh'), 'reports/explore/k4s-confirm/qualify_games.py',
           '--runtime', 'k4s', '--cores', a.cores, '--mode', 'charged', '--population', 'primary', '--index', '6', '--arms', 'K4S-140', 'K4-200', '--out', str(out)]
    child = subprocess.Popen(cmd, stdout=log.open('w'), stderr=subprocess.STDOUT, start_new_session=True, cwd=a.job/'repo', env=dict(os.environ, K4S_JOB=str(a.job)))
    time.sleep(a.warmup)
    assert child.poll() is None, 'game ended before STOP; extend warm-up'
    touched_utc = utc(); t0 = time.monotonic(); token = touched_utc+' stop test pid %d\n' % os.getpid(); a.stop.write_text(token)
    while child.poll() is None and time.monotonic()-t0 < 300:
        time.sleep(.05)
    drain = time.monotonic()-t0; drained = child.poll() is not None
    while alive(child.pid) and time.monotonic()-t0 < 300:
        time.sleep(.05)
    left = alive(child.pid)
    if left: os.killpg(child.pid, signal.SIGKILL)
    # Remove only the STOP this test wrote; an externally replaced STOP is preserved.
    ours = a.stop.exists() and a.stop.read_text() == token
    if ours: a.stop.unlink()
    tail = log.read_text().strip().splitlines()[-1:] if log.exists() else []
    text = log.read_text() if log.exists() else ''
    interrupted = 'InterruptedError: owned K4S stop' in text and child.returncode not in (0, None)
    r = dict(utc=utc(), stop_touched_utc=touched_utc, game_running_at_touch=True, drained=drained, drain_seconds=drain, returncode=child.returncode,
             owned_processes_after=int(left), interrupted_by_owned_stop=interrupted, log_tail=tail, stop_removed_by_test=ours,
             external_stop_preserved=a.stop.exists() and not ours)
    (a.job/'out'/'stoptest.json').write_text(json.dumps(r, indent=2)+'\n')
    print(json.dumps(r)); sys.exit(0 if drained and not left and drain <= 300 and interrupted else 1)


if __name__ == '__main__':
    main()
