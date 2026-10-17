"""Pre-stop check for a live player package (bot lead live-diag): run on the Mac code tree BEFORE stopping the loop.

1. Every file in the package's MANIFEST-LINES.sha256 is installed in --code with exactly that sha256 (regular files).
2. Each --players name constructs through the deployed factory (bot.live.player.make_live_player) imported FROM --code
   (sys.path is set from --code; the origins of bot.live.player, bot.search.lopp_fast, bot.search.interrupt and
   bot.search.lopp are verified to lie inside --code), and the constructed config matches the name's tokens:
     -wint (last token)  <=> bot.search.interrupt.Interruptible wrapping a bot.live.player.LivePlayer, else a plain
                             LivePlayer (default-off);
     w<ms>               == the LivePlayer's deadline (ms/1000) and the search tier's deadline;
     K<n>                == the search arm's samples (default 1);
     res                 <=> the search arm's reserve flag;
     the player's name   == the full name.
No game, no taps, no writes outside --out. Supervised like fp_mac_bench (new session; pipe-EOF exit detection, the
leader is reaped only after the last group signal; handlers before start; child SIGALRM + supervisor watchdog).
Exit 0 only if every check passes; 1 = a check failed, 124 = deadline, 130 = signal.

    python -B fp_prestop_check.py --code $CODE --lines MANIFEST-LINES.sha256 --players NAME1,NAME2 --out check.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import select
import math
import subprocess
import threading
import sys
from pathlib import Path

CHILD_FLAG = '--_supervised-child'


# ---- supervision (loop owner Sol review r2: B1 PGID reuse, B2 signal gaps, B3 orphaned child) ----
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


def expect(name):
    toks = name.split('-')
    w = next((int(t[1:]) for t in toks if re.fullmatch(r'w\d+', t)), None)
    k = next((int(t[1:]) for t in toks if re.fullmatch(r'K\d+', t)), 1)
    return dict(wint=name.endswith('-wint'), deadline_s=None if w is None else w / 1000, samples=k, reserve='res' in toks)


def child_main(a):
    child_guard(a.deadline_s)
    code = Path(a.code).resolve()
    sys.path[:0] = [str(code), str(code / 'src'), str(code / 'live' / 'perception')]
    out, ok = dict(code=str(code), files={}, players={}), True
    for line in a.lines.read_text().splitlines():
        if not line.strip():
            continue
        want, rel = line.split(None, 1)
        f = code / rel.strip()
        got = hashlib.sha256(f.read_bytes()).hexdigest() if f.is_file() else None
        out['files'][rel.strip()] = dict(want=want, got=got, ok=got == want)
        ok &= got == want
    from bot.players.runtime import Runtime
    from bot.live.player import LivePlayer, make_live_player
    rt = Runtime()
    for name in a.players.split(','):
        try:
            e = expect(name)
            p = make_live_player(rt, name)
            wrapped = type(p).__name__ == 'Interruptible'
            live = p.live if wrapped else p
            arm = getattr(live.search, 'arm', None)
            arm = dict(arm) if isinstance(arm, dict) else {}
            got = dict(wint=wrapped and type(p).__module__ == 'bot.search.interrupt',
                       deadline_s=live.deadline_seconds, search_deadline_s=getattr(live.search, 'deadline_seconds', None),
                       samples=arm.get('samples', 1), reserve=bool(arm.get('reserve')))
            checks = dict(type=type(live) is LivePlayer, wint=got['wint'] == e['wint'] and wrapped == e['wint'],
                          deadline=e['deadline_s'] is not None and got['deadline_s'] is not None and
                          abs(got['deadline_s'] - e['deadline_s']) < 1e-9 and got['search_deadline_s'] is not None and
                          abs(got['search_deadline_s'] - e['deadline_s']) < 1e-9,
                          samples=got['samples'] == e['samples'], reserve=got['reserve'] == e['reserve'],
                          name=p.name == name)
            row = dict(type=f'{type(p).__module__}.{type(p).__name__}', expected=e, got=got, arm=arm, checks=checks,
                       ok=all(checks.values()))
        except Exception as ex:
            row = dict(error=repr(ex)[:400], ok=False)
        out['players'][name] = row
        ok &= row['ok']
    origins = {}
    for n in ('bot.live.player', 'bot.search.lopp_fast', 'bot.search.lopp', 'bot.search.interrupt', 'bot.players.runtime'):
        m = sys.modules.get(n)
        f = getattr(m, '__file__', None) if m else None
        if m is not None:
            origins[n] = dict(file=f, inside_code=bool(f) and Path(f).resolve().is_relative_to(code))
            ok &= origins[n]['inside_code']
    out['import_origins'] = origins
    out['ok'] = bool(ok)
    a.out.write_text(json.dumps(out, indent=1, default=str) + '\n')
    print(json.dumps(out, indent=1, default=str))
    return 0 if ok else 1


def parse(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--code', required=True, type=Path)
    ap.add_argument('--lines', required=True, type=Path, help='sha256sum-format lines: <sha256>  <path rel. to code>')
    ap.add_argument('--players', required=True)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--deadline-s', type=finite_positive, default=300)
    return ap.parse_args(argv)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == CHILD_FLAG:
        sys.exit(child_main(parse(argv[1:])))
    sys.exit(supervise(__file__, argv, parse(argv).deadline_s, CHILD_FLAG))


if __name__ == '__main__':
    main()
