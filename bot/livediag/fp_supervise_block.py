# Shared supervision block for fp_mac_bench.py / fp_prestop_check.py (pasted verbatim into both: they must run as
# single standalone files on the Mac). Loop owner's Sol reviews: r2 B1 PGID reuse, B2 signal gaps, B3 orphaned child;
# r3 1 inherited SIGCHLD=SIG_IGN, 3 exceptions after Popen, 5 signal precedence over EOF.
import math
import os
import select
import signal
import subprocess
import sys
import threading


def _say(msg):
    try:
        print(msg, file=sys.stderr, flush=True)
    except Exception:                                     # logging must never skip cleanup (closed / broken stderr)
        pass


def supervise(script, argv, deadline_s, child_flag):
    """Run `script child_flag argv` as a child in a NEW SESSION and bound it by deadline_s.

    - SIGCHLD is reset to SIG_DFL before the child starts (an inherited SIG_IGN would auto-reap it: exit status lost,
      PGID reservation lost).
    - The child is never reaped before the last group signal: exit is detected as EOF on a pipe whose write end only
      the child (and processes it forks) holds; the final wait() reaps it last, so killpg never hits a reused PGID.
    - SIGTERM/SIGINT handlers are installed BEFORE the child starts and only set a flag; a signal takes precedence over
      a simultaneous EOF; cleanup runs with both signals ignored.
    - Everything after a successful Popen is in try/finally: TERM (if not finished) -> KILL -> wait always run.
    Returns the child's exit status, 124 on the deadline, 130 on a signal."""
    state = dict(sig=None)

    def on_signal(sig, frame):
        state['sig'] = sig
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    for s in (signal.SIGTERM, signal.SIGINT):
        signal.signal(s, on_signal)
    r, w = os.pipe()
    try:
        child = subprocess.Popen([sys.executable, '-B', os.path.abspath(script), child_flag, *argv],
                                 start_new_session=True, pass_fds=(w,),
                                 env=dict(os.environ, FP_SUPERVISOR_PID=str(os.getpid())))
    except BaseException:
        os.close(r)
        os.close(w)
        raise
    pgid, why, finished = child.pid, None, False

    def killpg(sig):
        try:
            os.killpg(pgid, sig)
        except (ProcessLookupError, PermissionError, OSError):
            pass

    def wait_eof(timeout):
        end = _now() + timeout
        while True:
            if state['sig'] is not None:
                return False
            left = end - _now()
            if left <= 0:
                return False
            try:
                ready, _, _ = select.select([r], [], [], min(0.5, left))
            except InterruptedError:
                continue
            if ready and os.read(r, 1) == b'':
                return state['sig'] is None                 # a signal in the same round wins over EOF
    try:
        os.close(w)
        _say(f'{os.path.basename(script)}: child session {pgid}')
        finished = wait_eof(deadline_s)
    except BaseException as ex:                           # anything unexpected: clean up as for a signal
        _say(f'{os.path.basename(script)}: supervisor error {ex!r}')
        why = 'error'
    finally:
        for s in (signal.SIGTERM, signal.SIGINT):         # cleanup is not interruptible
            signal.signal(s, signal.SIG_IGN)
        if state['sig'] is not None:                      # also catches a signal that raced the EOF / SIG_IGN switch
            finished, why = False, 'signal'
        elif not finished and why is None:
            why = 'deadline'
        try:
            if not finished:
                _say(f'{os.path.basename(script)}: {why}; terminating process group {pgid}')
                killpg(signal.SIGTERM)
                try:
                    wait_eof(5)
                except Exception:
                    pass
            killpg(signal.SIGKILL)                        # stragglers while the PGID is still reserved
        finally:
            rc = child.wait()                             # reap the leader LAST
            try:
                os.close(r)
            except OSError:
                pass
    if why == 'deadline':
        return 124
    if why in ('signal', 'error'):
        return 130
    return rc


def _now():
    import time
    return time.monotonic()


def child_guard(deadline_s):
    """In the child: the kernel kills it at deadline + 15 s even inside a stuck native call (SIGALRM, default action);
    a watchdog exits when the supervisor is gone (re-parented). Load workers have their own lock-free guards."""
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    signal.alarm(int(math.ceil(deadline_s)) + 15)
    sup = int(os.environ.get('FP_SUPERVISOR_PID', '0'))
    if os.environ.get('FP_TEST_NOWATCH') == '1':          # test hook: exercise the alarm fallback alone
        return

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
