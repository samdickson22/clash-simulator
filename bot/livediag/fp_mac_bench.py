"""Decision-latency bench for full-pool live player names on recorded live battles (bot lead live-diag, exploration).

Primary number: poll_step_ms p95 = sess.step wall over poll rows (the driver's decisions.jsonl rows). SCOPE: sess.step
only. The live step_ms also includes the driver's per-frame prep before sess.step (hand classifier / decode), so the
bench also reads the live step_ms of the same battles and reports, per player,
    adjusted_poll_step_p95 = bench p95 + (live p95 of the deployed player - bench p95 of the FIRST --players name),
i.e. the first name must be the deployed player (res); the adjustment carries prep + perception load measured live.
Also: searched-step and the search's own wall_ms (decision_wall_ms, a different field), cutoff hits, and per battle the
worst game-minute (1200 ticks, >= 20 polls) poll-step p95, bench / live / adjusted (LIVE LEAD: s74-m05's tail).

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
                if os.environ.get('FP_TEST_SIG_AT_EOF') == '1':   # test hook: a signal lands in the EOF round
                    os.kill(os.getpid(), signal.SIGTERM)
                return state['sig'] is None                 # a signal in the same round wins over EOF
    try:
        os.close(w)
        _say(f'{os.path.basename(script)}: child session {pgid}')
        _test_hooks_after_popen(pgid)
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


def _test_hooks_after_popen(pgid):
    """Test hooks only (inert unless set): FP_TEST_SESSFILE=<path> records the child session id (for tests with a
    closed stderr); FP_TEST_SUP_RAISE=1 raises in the supervisor right after Popen (cleanup must still run)."""
    f = os.environ.get('FP_TEST_SESSFILE')
    if f:
        with open(f, 'w') as fh:
            fh.write(str(pgid))
    if os.environ.get('FP_TEST_SUP_RAISE') == '1':
        raise RuntimeError('FP_TEST_SUP_RAISE')


def _now():
    import time
    return time.monotonic()


def child_guard(deadline_s):
    """In the child: the kernel kills it at deadline + 15 s even inside a stuck native call (SIGALRM, default action);
    a watchdog exits when the supervisor is gone (re-parented). Load workers have their own lock-free guards."""
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    if os.environ.get('FP_TEST_NOCHILDALARM') != '1':     # test hook: show the load workers' own alarms firing
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


def _test_injections(live):
    """Test hooks only (inert unless set; the launcher unsets them all). Injected INSIDE the bench's observation
    proxies, i.e. where a real failure would arise:
      FP_TEST_FAST_RAISE=K    the K-th fast-tier poll raises (player.py:290 swallows it)
      FP_TEST_SEARCH_RAISE=K  the K-th OFF-CADENCE search poll (tick % 10 != 0) raises after running (player.py:311 swallows it)
      FP_TEST_BELIEF_TIMEOUT=K the K-th decision-tick belief update raises TimeoutError (player.py:126 -> cutoff default)
      FP_TEST_POOL_ERR=K      the K-th learned-pool collect reports a worker error (lopp_fast native_pool -> note_failure)
      FP_TEST_HIT=K           the K-th searched decision reports hit=True, fallback=False (completed, past the cutoff)
      FP_TEST_BELIEF_REBUILD=K the K-th decision-tick belief update hits 'no train deck' -> FullPoolBelief rebuild
      FP_TEST_BELIEF_REBUILD_SLEEP_MS=N  that injected rebuild first sleeps N ms (a rebuild that blows the deadline)"""
    env = os.environ
    k = int(env.get('FP_TEST_FAST_RAISE') or 0)
    if k:
        orig, n = live.fast.act, [0]

        def fast_act(view, _o=orig):
            n[0] += 1
            if n[0] == k:
                raise RuntimeError('FP_TEST_FAST_RAISE')
            return _o(view)
        live.fast.act = fast_act
    k2 = int(env.get('FP_TEST_SEARCH_RAISE') or 0)
    k3 = int(env.get('FP_TEST_BELIEF_TIMEOUT') or 0)
    k5 = int(env.get('FP_TEST_HIT') or 0)
    k6 = int(env.get('FP_TEST_BELIEF_REBUILD') or 0)
    if k2 or k3 or k5 or k6:
        orig_s, n2, n3, n5, n6 = live.search.act, [0], [0], [0], [0]

        def search_act(view, *a, _o=orig_s, **kw):
            if k2 and view.tick % 10:
                n2[0] += 1
                if n2[0] == k2:                           # after the poll ran (its 5-tick gates advanced), as an
                    _o(view, *a, **kw)                    # exception escaping late would: nothing else can notice it
                    raise RuntimeError('FP_TEST_SEARCH_RAISE (off-cadence)')
            if k3 and view.can_act and not view.tick % 10:
                n3[0] += 1
                if n3[0] == k3:
                    b = live.search.p.belief
                    ou = b.update

                    def once(*x, _ou=ou, **y):
                        b.update = _ou
                        raise TimeoutError('FP_TEST_BELIEF_TIMEOUT')
                    b.update = once
            if k6 and view.can_act and not view.tick % 10:
                n6[0] += 1
                if n6[0] == k6:                               # the base update FullPoolBelief.update calls raises the
                    base = type(live.search.p.belief).__mro__[1]   # 'no train deck' ValueError once -> its rebuild path
                    ob = base.update

                    slow = float(env.get('FP_TEST_BELIEF_REBUILD_SLEEP_MS') or 0) / 1000

                    def once_base(self, *x, _ob=ob, **y):
                        base.update = _ob
                        if slow:                              # FP_TEST_BELIEF_REBUILD_SLEEP_MS: a rebuild past the deadline
                            time.sleep(slow)
                        raise ValueError('no train deck (FP_TEST_BELIEF_REBUILD)')
                    base.update = once_base
            d = _o(view, *a, **kw)
            if k5 and getattr(d, 'stats', None) is not None:
                n5[0] += 1
                if n5[0] == k5:                               # a completed search that hit the cutoff (lopp_fast:619)
                    d.stats = dict(d.stats, hit=True, fallback=False)
            return d
        live.search.act = search_act
    k4 = int(env.get('FP_TEST_POOL_ERR') or 0)
    if k4:
        from bot.search import lopp_fast as lf
        cls = lf.LearnedPool                               # pool.errors is checked right after collect (native_pool)
        if not getattr(cls, '_fp_test', False):
            oc, n4 = cls.collect, [0]

            def collect(self, *a, _oc=oc, **kw):
                out = _oc(self, *a, **kw)
                n4[0] += 1
                if n4[0] == k4:
                    self.errors.append('FP_TEST_POOL_ERR')
                return out
            cls.collect, cls._fp_test = collect, True


def decision_problems(st):
    """Why a decision's stats make the run invalid ([] = clean). Covers the deployed LivePlayer's fields
    (bot/live/player.py): an error, a source other than plain 'search'/'fast' (e.g. 'default-it5s2' = cutoff fallback,
    'fast-error', 'stall-fast'), native_failure (this decision), native_failures (per-match counter > 0),
    search_failures (per-decision delta), fallback, student_default, any cutoff (hit / preparation_cutoff, also with a
    usable completed choice). Belief rebuilds are NOT here: they occur in every live battle and are reported (r8b)."""
    out = []
    src = str(st.get('source') or '')
    if st.get('error'):
        out.append(f'error {st.get("error")}'[:200])
    if src and src not in ('search', 'fast'):
        out.append(f'source {src}')
    if st.get('native_failure') is not None:
        out.append(f'native_failure {st.get("native_failure")}')
    if (st.get('native_failures') or 0) > 0:
        out.append(f'native_failures {st.get("native_failures")}')
    sf = st.get('search_failures')
    if sf and (not isinstance(sf, dict) or any(sf.values())):
        out.append(f'search_failures {sf}')
    for k in ('fallback', 'student_default'):
        if st.get(k):
            out.append(k)
    if st.get('hit') or 'preparation_cutoff' in st:          # r8: any cutoff, even a usable completed choice
        out.append(f'cutoff hit={st.get("hit")} preparation_cutoff={st.get("preparation_cutoff")}')
    return out


WINDOW_TICKS, WINDOW_MIN_POLLS = 1200, 20                   # one game minute; a window needs >= 20 polls


def worst_window(pairs):
    """[(tick, step_ms)] -> (max over 1-minute windows of the window's p95, window start tick, polls in it)."""
    by = {}
    for t, v in pairs:
        if t is not None:
            by.setdefault(int(t) // WINDOW_TICKS, []).append(v)
    best = None
    for k, vs in by.items():
        if len(vs) >= WINDOW_MIN_POLLS:
            p95 = q(vs, .95)
            if best is None or p95 > best[0]:
                best = (p95, k * WINDOW_TICKS, len(vs))
    return list(best) if best else None


def live_poll_steps_ticks(run):
    return [(d.get('tick'), d['step_ms']) for d in map(json.loads, open(run / 'decisions.jsonl')) if d.get('step_ms') is not None]


def live_poll_steps(run):
    return [d['step_ms'] for d in map(json.loads, open(run / 'decisions.jsonl')) if d.get('step_ms') is not None]


def bench_run(drive, rt, name, run, max_steps=None):
    from bot.live.player import make_live_player
    cfg = json.loads((run / 'session-config.json').read_text())
    events = [json.loads(l) for l in open(run / 'events.jsonl')]
    start = next((e['ts_ms'] for e in events if e.get('ev') == 'match_start'), None)
    player = make_live_player(rt, name)
    live = getattr(player, 'live', player)                 # Interruptible -> its LivePlayer
    obs = dict(fast_exc=[], search_exc=[])               # exceptions observed AT THE SOURCE (re-raised unchanged)
    mut = set(filter(None, os.environ.get('FP_TEST_MUTATE', '').split(',')))   # test only: disable an observation
    _test_injections(live)                                # test only (inert unless FP_TEST_* set)

    def observed(fn, key):
        def call(*a, **k):
            try:
                return fn(*a, **k)
            except BaseException as ex:                   # the deployed player swallows these (player.py:290, :311,
                if key not in mut:                        # incl. off-cadence polls): record, then behave identically
                    obs[key].append(f'{type(ex).__name__}: {ex}'[:200])
                raise
        return call
    live.fast.act = observed(live.fast.act, 'fast_exc')
    live.search.act = observed(live.search.act, 'search_exc')
    from bot.search import lopp as _lopp
    failures0 = sum(_lopp.FAILURES.values())             # process-wide note_failure counter (every lopp/lopp_fast site)
    sess = drive.make_session(rt, player, cfg['deck'])
    steps, searched, errors = [], [], []
    peak = dict(errors=0, panics=0, fast_errors=0)        # the player's own counters, sampled after EVERY step
    cutoffs, rebuilds, rebuilt_at = 0, 0, []
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
            for field in peak:                                # errors resets on success: keep the max over the run
                v = getattr(live, field, 0)
                if isinstance(v, (int, float)) and v > peak[field]:
                    peak[field] = v
            b = getattr(getattr(getattr(live, 'search', None), 'p', None), 'belief', None)
            rb = getattr(b, 'rebuilds', 0) if b is not None else 0
            if isinstance(rb, (int, float)) and rb > rebuilds:  # FullPoolBelief / LiveBelief prior rebuild (belief.py:58):
                rebuilt_at.append(dict(n=row.get('n'), step_ms=round(w, 2), searched=st.get('source') == 'search'))
                rebuilds = rb                                 # REPORTED (r8b), not an error; a slow one becomes a cutoff
            if st and (st.get('hit') or 'preparation_cutoff' in st or str(st.get('source') or '').startswith('default')):
                cutoffs += 1                                  # every cutoff, whatever the source (not only 'search')
            bad = decision_problems(st) if st and 'classifier' not in mut else []
            if bad:
                errors.append(f'n={row.get("n")}: decision: {"; ".join(bad)}'[:300])
            steps.append(dict(wall=w, cpu=c, searched=st.get('source') == 'search', poll=d is not None,
                              tick=row.get('tick')))
            if st.get('source') == 'search':
                searched.append(dict(step=w, wall_ms=st.get('wall_ms'), hit=bool(st.get('hit') or st.get('preparation_cutoff')),
                                     rollouts=st.get('rollouts'), learned=st.get('learned_rollouts')))
        if 'counters' not in mut:
            for field, v in peak.items():                   # failed polls the player absorbed (fast_errors: a broken
                if v:                                         # fast poller substituted by WAIT; errors: search failures)
                    errors.append(f'player.{field} = {v}')
        for key, xs in obs.items():
            if xs:
                errors.append(f'{key} x{len(xs)}: {xs[0]}')
        if cutoffs and 'cutoffs' not in mut:                # r8: the bench measures clean latency: no cutoff at all
            errors.append(f'cutoffs {cutoffs}')
        dfail = sum(_lopp.FAILURES.values()) - failures0
        if dfail and 'failures' not in mut:
            errors.append(f'lopp.FAILURES +{dfail}: {dict(_lopp.FAILURES)}')
        tr_stats = {k: v for k, v in getattr(sess.tr, 'stats', {}).items() if v}
    finally:
        try:
            sess.close()
        except Exception as ex:          # e.g. a session that never started (no poll): recorded, makes the run invalid
            errors.append(f'close: {type(ex).__name__}: {ex}'[:300])
    return steps, searched, errors, cutoffs, dict(locals().get('tr_stats', {}), _belief_rebuilds=rebuilds,
                                                   _rebuilt_at=rebuilt_at)


def summary(steps, searched, errors, wall_s, cutoffs=None):
    sw = [s['wall'] for s in steps]
    pw = [s['wall'] for s in steps if s['poll']]
    ss = [s['step'] for s in searched]
    dw = [s['wall_ms'] for s in searched if s['wall_ms'] is not None]
    kinds = {}
    for e in errors:                                    # e.g. 'source default-it5s2' (cutoff fallback) vs a failure
        k = e.split(': ', 2)[-1].split(';')[0].strip()[:60] if 'decision:' in e else e.split(':')[0][:60]
        kinds[k] = kinds.get(k, 0) + 1
    ww = worst_window([(s['tick'], s['wall']) for s in steps if s['poll']])
    return dict(polls=len(pw), searched=len(searched), errors=len(errors), error_kinds=kinds, error_samples=errors[:5],
                worst_minute_poll_p95_start_polls=ww,
                bench_wall_s=round(wall_s, 1),
                poll_step_ms_p50_p95_p99=[q(pw, .5), q(pw, .95), q(pw, .99)],
                searched_step_ms_p50_p95_p99=[q(ss, .5), q(ss, .95), q(ss, .99)],
                decision_wall_ms_p50_p95_p99=[q(dw, .5), q(dw, .95), q(dw, .99)],
                cutoff_hits=sum(s['hit'] for s in searched) if cutoffs is None else cutoffs,
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
        if os.environ.get('FP_TEST_MARK'):
            open(os.environ['FP_TEST_MARK'], 'w').write(str(os.getpid()))
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
    out['live_per_run'] = {r.name: dict(poll_step_ms_p95=q([v for _, v in live_poll_steps_ticks(r)], .95),
                                        worst_minute_poll_p95_start_polls=worst_window(live_poll_steps_ticks(r)))
                           for r in a.runs}
    procs = []
    valid = True
    try:
        procs = start_load(a.load, a.deadline_s)
        test_stall()
        for rep in range(a.repeat):
            for name in names:
                t0 = time.perf_counter()
                S, D, E, C, per_run = [], [], [], 0, {}
                for run in a.runs:
                    s, d, e, c, trs = bench_run(drive, rt, name, run, a.max_steps)
                    rb, rba = trs.pop('_belief_rebuilds', 0), trs.pop('_rebuilt_at', [])
                    per_run[run.name] = dict(summary(s, d, e, 0, c), translator_stats=trs, belief_rebuilds=rb,
                                             belief_rebuilt_at=rba)
                    S += s; D += d; E += e; C += c
                key = name if a.repeat == 1 else f'{name}#{rep}'
                row = summary(S, D, E, time.perf_counter() - t0, C)
                # W1 aggregate (Sol r8b): ticks restart in every battle, so a window over the pooled steps would merge
                # different battles' minutes; the player value is the worst per-run W1 instead (+ the run it came from).
                wws = [(pr['worst_minute_poll_p95_start_polls'], rn) for rn, pr in per_run.items()
                       if pr.get('worst_minute_poll_p95_start_polls')]
                worst = max(wws, key=lambda x: x[0][0]) if wws else None
                row['worst_minute_poll_p95_start_polls'] = worst[0] if worst else None
                row['worst_minute_run'] = worst[1] if worst else None
                tsum = {}
                for pr in per_run.values():                   # r8: translator behaviour per player (not a failure,
                    for kk, vv in pr.get('translator_stats', {}).items():   # but must not hide a difference between arms)
                        if isinstance(vv, (int, float)):
                            tsum[kk] = tsum.get(kk, 0) + vv
                row['translator_stats'] = tsum
                row['submit_refused'] = tsum.get('submit_refused', 0)
                row['own_cycle_dropped'] = sum(v for kk, v in tsum.items() if kk.startswith('cycle_conflict_dropped:0'))
                row['belief_rebuilds'] = sum(pr.get('belief_rebuilds', 0) for pr in per_run.values())   # r8b: reported
                row['belief_rebuilt_at'] = {rn: pr.get('belief_rebuilt_at', []) for rn, pr in per_run.items()}
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
        if bad:
            valid = False
        first = next(iter(out['players'].values()), None)
        if first and first['poll_step_ms_p50_p95_p99'][1] is not None and out['live_poll_step_ms_p50_p95_p99'][1]:
            off = out['live_poll_step_ms_p50_p95_p99'][1] - first['poll_step_ms_p50_p95_p99'][1]
            out['adjustment_ms'] = round(off, 2)
            for row in out['players'].values():
                p95 = row['poll_step_ms_p50_p95_p99'][1]
                row['adjusted_poll_step_p95'] = None if p95 is None else round(p95 + off, 2)
        if first:                                       # per battle: worst game-minute p95, adjusted by THAT battle's
            for rn, lv in out['live_per_run'].items():  # (live - bench) baseline offset on the whole battle
                b0 = first['per_run'].get(rn, {})
                b0p = b0.get('poll_step_ms_p50_p95_p99', [None, None])[1]
                offr = None if (b0p is None or lv['poll_step_ms_p95'] is None) else lv['poll_step_ms_p95'] - b0p
                for row in out['players'].values():
                    pr = row['per_run'].get(rn, {})
                    ww = pr.get('worst_minute_poll_p95_start_polls')
                    pr['adjustment_ms'] = None if offr is None else round(offr, 2)
                    pr['adjusted_poll_step_p95'] = (None if offr is None or pr.get('poll_step_ms_p50_p95_p99', [None, None])[1] is None
                                                    else round(pr['poll_step_ms_p50_p95_p99'][1] + offr, 2))
                    pr['adjusted_worst_minute_p95'] = None if (offr is None or not ww) else round(ww[0] + offr, 2)
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
