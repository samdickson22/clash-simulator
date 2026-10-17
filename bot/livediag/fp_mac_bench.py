"""Decision-latency bench for full-pool live player names on recorded live battles (bot lead live-diag, exploration).

Primary number: poll_step_ms p95 = sess.step wall over poll rows (the driver's decisions.jsonl rows). SCOPE: sess.step
only. The live step_ms also includes the driver's per-frame prep before sess.step (hand classifier / decode), so the
bench also reads the live step_ms of the same battles and reports, per player,
    adjusted_poll_step_p95 = bench p95 + (live p95 of the deployed player - bench p95 of the FIRST --players name),
i.e. the first name must be the deployed player (res); the adjustment carries prep + perception load measured live.
Also: searched-step and the search's own wall_ms (decision_wall_ms, a different field), cutoff hits.

Replays RUN/perception.jsonl (the exact records the deployed driver handed to LiveSession.step, logged after its HUD
overrides and own-event dedupe) through the deployed driver's own construction: live/loop/drive.py make_session(rt,
make_live_player(rt, NAME), deck) with LL_HANDSYNC=1 as deployed (SyncSession + GuardedPlayer), clock anchored at the
run's match_start event. Players run one after another, each on the same battles. Nothing is tapped: the game does not
react to the replayed choices, so the states are the deployed bot's own, not the candidate's.

Safety (loop owner's Sol reviews r1/r2): the script re-executes itself as a supervised child in a NEW SESSION. The
parent installs its SIGTERM/SIGINT handlers first (flag only), detects the child's exit as EOF on a pipe only the child
holds (never reaping it before the last group signal, so the PGID cannot be reused), and on deadline / signal sends
SIGTERM, then SIGKILL, to the child's process group, then reaps. The child arms SIGALRM (default action) at deadline +
15 s, exits if the supervisor disappears, and its --load workers exit when the child does; it also stops them itself
(event -> terminate -> kill -> join). Imports come only from --code (sys.path from it; module origins verified).
Exit 0 only for a valid run (every player: polls > 0, searched > 0, no step/decision/close errors, player error and
panic counters 0); 2 = invalid run or wrong baseline, 3 = code-origin mismatch, 124 = deadline, 130 = signal.

--load N starts N busy-loop processes for the duration (a stand-in for perception's CPU).

    python -B fp_mac_bench.py --code $CODE --runs RUN1 RUN2 --players RES_NAME,NAME2 --out bench.json [--load 2]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import signal
import select
import math
import subprocess
import threading
import sys
import time
from pathlib import Path

CHILD_FLAG = '--_supervised-child'


# ---------------------------------------------------------------------------------------------------- supervision
# ---- supervision (loop owner Sol review r2: B1 PGID reuse, B2 signal gaps, B3 orphaned child) ----
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


def positive_int(text):
    v = int(text)
    if v < 1:
        raise ValueError(f'need an integer >= 1, got {text!r}')
    return v


def nonneg_int(text):
    v = int(text)
    if v < 0:
        raise ValueError(f'need an integer >= 0, got {text!r}')
    return v


def _spin(parent, deadline_s):
    """Load worker: exits when its parent (the bench child) is gone -- checked first, lock-free -- or at its own
    SIGALRM (default action) at deadline + 20 s; stop_load terminates / kills it."""
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    signal.alarm(int(math.ceil(deadline_s)) + 20)
    x = 0
    while os.getppid() == parent:
        for _ in range(100000):
            x += 1


def start_load(n, deadline_s):
    import multiprocessing as mp
    mp = mp.get_context(os.environ.get('FP_MP_START') or None)   # FP_MP_START=spawn: the macOS path, on Linux tests
    procs = []
    for _ in range(n):
        p = mp.Process(target=_spin, args=(os.getpid(), deadline_s), daemon=True)
        procs.append(p)
        p.start()
    return procs


def stop_load(procs):
    for p in procs:
        if p.is_alive():
            p.terminate()
    for p in procs:
        p.join(timeout=2)
    for p in procs:
        if p.is_alive():
            p.kill()
            p.join()


# ---------------------------------------------------------------------------------------------------- bench
def q(xs, f):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(f * len(xs)))], 2) if xs else None


def use_code(code):
    """Imports only from the code tree under test (no PYTHONPATH fallthrough to another tree)."""
    code = Path(code).resolve()
    roots = [code, code / 'src', code / 'live' / 'perception', code / 'live' / 'loop']
    sys.path[:0] = [str(r) for r in roots]
    return code


def check_origins(code, names):
    bad = {}
    for n in names:
        m = sys.modules.get(n)
        f = getattr(m, '__file__', None)
        if m is None or f is None or not Path(f).resolve().is_relative_to(code):
            bad[n] = f
    return bad


def load_drive(code, stubs=()):
    import types
    for m in stubs:                     # fleet only: modules drive.py imports at top level but the session never calls
        sys.modules.setdefault(m, types.ModuleType(m))
    p = Path(code) / 'live/loop/drive.py'
    spec = importlib.util.spec_from_file_location('drive', p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['drive'] = mod
    spec.loader.exec_module(mod)
    return mod


def live_poll_steps(run):
    return [d['step_ms'] for d in map(json.loads, open(run / 'decisions.jsonl')) if d.get('step_ms') is not None]


def bench_run(drive, rt, name, run, max_steps=None):
    from bot.live.player import make_live_player
    cfg = json.loads((run / 'session-config.json').read_text())
    events = [json.loads(l) for l in open(run / 'events.jsonl')]
    start = next((e['ts_ms'] for e in events if e.get('ev') == 'match_start'), None)
    sess = drive.make_session(rt, make_live_player(rt, name), cfg['deck'])
    steps, searched, errors = [], [], []
    try:
        if start is not None:
            sess.tr.clock.anchor(0, start)
        for i, line in enumerate(open(run / 'perception.jsonl')):
            if max_steps and i >= max_steps:
                break
            row = json.loads(line)
            if start is not None and row.get('ts_ms', row.get('timestamp_ms', 0)) < start:
                continue
            rec = {k: v for k, v in row.items() if k not in ('n', 'logged', 'tick', 'ts_ms')}
            w0, c0 = time.perf_counter(), time.process_time()
            try:
                d = sess.step(rec)
            except Exception as ex:
                errors.append(f'n={row.get("n")}: {type(ex).__name__}: {ex}'[:300])
                continue
            w, c = (time.perf_counter() - w0) * 1000, (time.process_time() - c0) * 1000
            st = (getattr(d, 'stats', None) or {}) if d is not None else {}
            if st.get('error') or str(st.get('source') or '').endswith('error') or st.get('fallback'):
                errors.append(f'n={row.get("n")}: decision {st.get("source")}: {st.get("error") or "fallback"}'[:300])
            steps.append(dict(wall=w, cpu=c, searched=st.get('source') == 'search', poll=d is not None))
            if st.get('source') == 'search':
                searched.append(dict(step=w, wall_ms=st.get('wall_ms'), hit=bool(st.get('hit')),
                                     rollouts=st.get('rollouts'), learned=st.get('learned_rollouts')))
        for field in ('errors', 'panics'):                   # the live player's own failure counters (via GuardedPlayer)
            v = getattr(sess.player, field, 0)
            if isinstance(v, (int, float)) and v:
                errors.append(f'player.{field} = {v}')
    finally:
        try:
            sess.close()
        except Exception as ex:          # e.g. a session that never started (no poll): recorded, makes the run invalid
            errors.append(f'close: {type(ex).__name__}: {ex}'[:300])
    return steps, searched, errors


def summary(steps, searched, errors, wall_s):
    sw = [s['wall'] for s in steps]
    pw = [s['wall'] for s in steps if s['poll']]
    ss = [s['step'] for s in searched]
    dw = [s['wall_ms'] for s in searched if s['wall_ms'] is not None]
    return dict(polls=len(pw), searched=len(searched), errors=len(errors), error_samples=errors[:5],
                bench_wall_s=round(wall_s, 1),
                poll_step_ms_p50_p95_p99=[q(pw, .5), q(pw, .95), q(pw, .99)],
                searched_step_ms_p50_p95_p99=[q(ss, .5), q(ss, .95), q(ss, .99)],
                decision_wall_ms_p50_p95_p99=[q(dw, .5), q(dw, .95), q(dw, .99)],
                cutoff_hits=sum(s['hit'] for s in searched),
                cutoff_hit=round(sum(s['hit'] for s in searched) / max(1, len(searched)), 4),
                frame_step_ms_p50_p95_p99=[q(sw, .5), q(sw, .95), q(sw, .99)],
                rollouts_mean=round(sum(s['rollouts'] or 0 for s in searched) / max(1, len(searched)), 1),
                learned_mean=round(sum(s['learned'] or 0 for s in searched) / max(1, len(searched)), 1),
                step_cpu_ms_mean=round(sum(s['cpu'] for s in steps) / max(1, len(steps)), 2))


def test_stall():
    """Test hook only (FP_TEST_STALL=1): ignore SIGTERM and sleep, a stand-in for a stuck native call."""
    if os.environ.get('FP_TEST_STALL') == '1':
        import time
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        while True:
            time.sleep(60)


def child_main(a):
    child_guard(a.deadline_s)
    names = a.players.split(',')
    if names[0] != a.baseline:
        print(f'first --players name must be the --baseline {a.baseline!r} (the deployed player); got {names[0]!r}',
              file=sys.stderr)
        return 2
    assert os.environ.get('PYTHONHASHSEED') == '0', 'PYTHONHASHSEED=0 (as the live launcher)'
    os.environ.setdefault('LL_HANDSYNC', '1')
    code = use_code(a.code)
    drive = load_drive(code, [m for m in a.stub_modules.split(',') if m])
    assert drive.HANDSYNC, 'LL_HANDSYNC=1 (deployed SyncSession)'
    from bot.players.runtime import Runtime
    import bot.live.player  # noqa: F401
    import bot.search.lopp_fast  # noqa: F401
    import bot.search.lopp  # noqa: F401
    rt = Runtime()
    out = dict(host=platform.node(), machine=platform.machine(), code=str(code), load=a.load,
               runs=[str(r) for r in a.runs], started=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               scope='sess.step only; adjusted_* adds (live - bench) p95 of the first player (prep + load)', players={})
    live = sorted(x for r in a.runs for x in live_poll_steps(r))
    out['live_poll_step_ms_p50_p95_p99'] = [q(live, .5), q(live, .95), q(live, .99)]
    procs = []
    valid = True
    try:
        procs = start_load(a.load, a.deadline_s)
        test_stall()
        for rep in range(a.repeat):
            for name in names:
                t0 = time.perf_counter()
                S, D, E, per_run = [], [], [], {}
                for run in a.runs:
                    s, d, e = bench_run(drive, rt, name, run, a.max_steps)
                    per_run[run.name] = summary(s, d, e, 0)
                    S += s; D += d; E += e
                key = name if a.repeat == 1 else f'{name}#{rep}'
                row = summary(S, D, E, time.perf_counter() - t0)
                row['per_run'] = per_run
                ok = row['polls'] > 0 and row['searched'] > 0 and not E
                row['valid'] = ok
                valid &= ok
                out['players'][key] = row
                print(key, json.dumps({k: v for k, v in row.items() if k != 'per_run'}), flush=True)
                a.out.write_text(json.dumps(out, indent=1) + '\n')
        bad = check_origins(code, ['bot.live.player', 'bot.search.lopp_fast', 'bot.search.lopp', 'bot.players.runtime', 'drive'] +
                            (['bot.search.interrupt'] if 'bot.search.interrupt' in sys.modules else []))
        out['import_origins_outside_code'] = bad
        first = next(iter(out['players'].values()), None)
        if first and first['poll_step_ms_p50_p95_p99'][1] is not None and out['live_poll_step_ms_p50_p95_p99'][1]:
            off = out['live_poll_step_ms_p50_p95_p99'][1] - first['poll_step_ms_p50_p95_p99'][1]
            out['adjustment_ms'] = round(off, 2)
            for row in out['players'].values():
                p95 = row['poll_step_ms_p50_p95_p99'][1]
                row['adjusted_poll_step_p95'] = None if p95 is None else round(p95 + off, 2)
    finally:
        stop_load(procs)
    out['valid'] = bool(valid)
    out['finished'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    a.out.write_text(json.dumps(out, indent=1) + '\n')
    if out.get('import_origins_outside_code'):
        print('import origins outside --code:', out['import_origins_outside_code'], file=sys.stderr)
        return 3
    return 0 if valid else 2


def parse(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--code', required=True, help='code tree under test (contains live/loop/drive.py)')
    ap.add_argument('--runs', nargs='+', required=True, type=Path)
    ap.add_argument('--players', required=True, help='comma-separated live player names; FIRST = the deployed player')
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--load', type=nonneg_int, default=0)
    ap.add_argument('--max-steps', type=int, default=None)
    ap.add_argument('--repeat', type=positive_int, default=1, help='repeat the player list (>= 1)')
    ap.add_argument('--baseline', default='LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res',
                    help='the deployed player; must be the FIRST --players name (the adjustment uses it)')
    ap.add_argument('--stub-modules', default='', help='fleet only, e.g. cv2: empty stand-ins for import (never on the Mac)')
    ap.add_argument('--deadline-s', type=finite_positive, default=1200, help='hard wall bound (finite, > 0)')
    return ap.parse_args(argv)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == CHILD_FLAG:
        sys.exit(child_main(parse(argv[1:])))
    a = parse(argv)
    sys.exit(supervise(__file__, argv, a.deadline_s, CHILD_FLAG))


if __name__ == '__main__':
    main()
