# Shared supervision block for fp_mac_bench.py / fp_prestop_check.py (pasted verbatim into both: they must run as
# single standalone files on the Mac). Loop owner's Sol review r2: B1 PGID reuse, B2 signal gaps, B3 orphaned child.
import math
import os
import select
import signal
import subprocess
import sys
import threading


def supervise(script, argv, deadline_s, child_flag):
    """Run `script child_flag argv` as a child in a NEW SESSION and bound it by deadline_s.

    B1: the child is never reaped before the last group signal: exit is detected as EOF on a pipe whose write end only
        the child (and processes it forks) holds, so the leader's PID (= the PGID) stays reserved while killpg runs; the
        final wait() reaps it last.
    B2: SIGTERM/SIGINT handlers are installed BEFORE the child starts and only set a flag (no exception), so repeated
        signals cannot skip the KILL/reap steps.
    Returns the child's exit status, 124 on the deadline, 130 on a signal."""
    state = dict(sig=None)

    def on_signal(sig, frame):
        state['sig'] = sig
    for s in (signal.SIGTERM, signal.SIGINT):
        signal.signal(s, on_signal)
    r, w = os.pipe()
    child = subprocess.Popen([sys.executable, '-B', os.path.abspath(script), child_flag, *argv],
                             start_new_session=True, pass_fds=(w,), env=dict(os.environ, FP_SUPERVISOR_FD=str(w),
                                                                             FP_SUPERVISOR_PID=str(os.getpid())))
    os.close(w)
    pgid = child.pid
    print(f'{os.path.basename(script)}: child session {pgid}', file=sys.stderr, flush=True)

    def wait_eof(timeout):
        end = None if timeout is None else _now() + timeout
        while True:
            left = None if end is None else max(0., end - _now())
            if left == 0. or state['sig'] is not None:
                return False
            try:
                ready, _, _ = select.select([r], [], [], min(0.5, left) if left is not None else 0.5)
            except InterruptedError:
                continue
            if ready and os.read(r, 1) == b'':
                return True

    def killpg(sig):
        try:
            os.killpg(pgid, sig)
        except (ProcessLookupError, PermissionError):
            pass

    finished = wait_eof(deadline_s)
    why = None if finished else ('signal' if state['sig'] is not None else 'deadline')
    for s in (signal.SIGTERM, signal.SIGINT):             # cleanup is not interruptible
        signal.signal(s, signal.SIG_IGN)
    if why is not None:
        print(f'{os.path.basename(script)}: {why}; terminating process group {pgid}', file=sys.stderr)
        killpg(signal.SIGTERM)
        state['sig'] = None
        wait_eof(5)
    killpg(signal.SIGKILL)                                # stragglers (load workers) while the PGID is still reserved
    rc = child.wait()                                     # reap the leader LAST
    os.close(r)
    if why == 'deadline':
        return 124
    if why == 'signal':
        return 130
    return rc


def _now():
    import time
    return time.monotonic()


def child_guard(deadline_s):
    """B3, in the child: the kernel kills it at deadline + 15 s even inside a stuck native call (SIGALRM, default
    action), and a watchdog exits when the supervisor is gone (re-parented). Load workers exit when the child does."""
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    signal.alarm(int(math.ceil(deadline_s)) + 15)
    sup = int(os.environ.get('FP_SUPERVISOR_PID', '0'))

    def watch():
        import time
        while True:
            if sup and os.getppid() != sup:
                os._exit(125)
            time.sleep(1)
    threading.Thread(target=watch, daemon=True).start()


def finite_positive(text):
    v = float(text)
    if not math.isfinite(v) or v <= 0:
        raise ValueError(f'need a finite value > 0, got {text!r}')
    return v
