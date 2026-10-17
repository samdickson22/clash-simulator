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

Safety (loop owner's Sol review): the script re-executes itself as a supervised child in its own session; the parent
enforces --deadline-s wall time and, on timeout / SIGTERM / SIGINT, sends SIGTERM then SIGKILL to the child's whole
process group (the child and its --load workers) and reaps it. The child also stops its load workers itself
(event -> terminate -> kill -> join) and the workers exit when their parent is gone. Imports come only from --code
(sys.path is set from it and module origins are verified). Exit 0 only for a valid run (every player: polls > 0,
searched > 0, no step errors); 2 = invalid run, 124 = deadline, 3 = code-origin mismatch.

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
import subprocess
import sys
import time
from pathlib import Path

CHILD_FLAG = '--_supervised-child'


# ---------------------------------------------------------------------------------------------------- supervision
def supervise(argv, deadline_s):
    """Run this script as a child in a new session; enforce the deadline; always TERM->KILL->reap its process group."""
    child = subprocess.Popen([sys.executable, '-B', os.path.abspath(__file__), CHILD_FLAG, *argv], start_new_session=True)
    state = dict(sig=None)

    def kill_group():
        for sig, wait in ((signal.SIGTERM, 5), (signal.SIGKILL, 5)):
            try:
                os.killpg(child.pid, sig)
            except ProcessLookupError:
                break
            try:
                child.wait(timeout=wait)
            except subprocess.TimeoutExpired:
                continue
        try:
            os.killpg(child.pid, signal.SIGKILL)      # stragglers (load workers) of the group, if any
        except ProcessLookupError:
            pass
        child.wait()

    def on_signal(sig, frame):
        state['sig'] = sig
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    try:
        rc = child.wait(timeout=deadline_s)
    except subprocess.TimeoutExpired:
        print(f'fp_mac_bench: deadline {deadline_s}s exceeded; killing process group {child.pid}', file=sys.stderr)
        kill_group()
        return 124
    except KeyboardInterrupt:
        print(f'fp_mac_bench: signal {state["sig"]}; killing process group {child.pid}', file=sys.stderr)
        kill_group()
        return 130
    try:                                               # the child exited: reap anything left in its group
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    return rc


def _spin(stop, parent):
    x = 0
    while not stop.is_set() and os.getppid() == parent:
        for _ in range(100000):
            x += 1


def start_load(n):
    import multiprocessing as mp
    stop, procs = mp.Event(), []
    for _ in range(n):
        p = mp.Process(target=_spin, args=(stop, os.getpid()), daemon=True)
        procs.append(p)
        p.start()
    return stop, procs


def stop_load(stop, procs):
    stop.set()
    for p in procs:
        p.join(timeout=2)
    for p in procs:
        if p.is_alive():
            p.terminate()
            p.join(timeout=2)
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
            steps.append(dict(wall=w, cpu=c, searched=st.get('source') == 'search', poll=d is not None))
            if st.get('source') == 'search':
                searched.append(dict(step=w, wall_ms=st.get('wall_ms'), hit=bool(st.get('hit')),
                                     rollouts=st.get('rollouts'), learned=st.get('learned_rollouts')))
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


def child_main(a):
    assert os.environ.get('PYTHONHASHSEED') == '0', 'PYTHONHASHSEED=0 (as the live launcher)'
    os.environ.setdefault('LL_HANDSYNC', '1')
    code = use_code(a.code)
    drive = load_drive(code, [m for m in a.stub_modules.split(',') if m])
    assert drive.HANDSYNC, 'LL_HANDSYNC=1 (deployed SyncSession)'
    from bot.players.runtime import Runtime
    import bot.live.player  # noqa: F401
    import bot.search.lopp_fast  # noqa: F401
    rt = Runtime()
    out = dict(host=platform.node(), machine=platform.machine(), code=str(code), load=a.load,
               runs=[str(r) for r in a.runs], started=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               scope='sess.step only; adjusted_* adds (live - bench) p95 of the first player (prep + load)', players={})
    live = sorted(x for r in a.runs for x in live_poll_steps(r))
    out['live_poll_step_ms_p50_p95_p99'] = [q(live, .5), q(live, .95), q(live, .99)]
    stop, procs = None, []
    valid = True
    try:
        stop, procs = start_load(a.load)
        names = a.players.split(',')
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
        bad = check_origins(code, ['bot.live.player', 'bot.search.lopp_fast', 'bot.players.runtime', 'drive'] +
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
        if stop is not None:
            stop_load(stop, procs)
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
    ap.add_argument('--load', type=int, default=0)
    ap.add_argument('--max-steps', type=int, default=None)
    ap.add_argument('--repeat', type=int, default=1, help='repeat the player list (order effects / warm caches)')
    ap.add_argument('--stub-modules', default='', help='fleet only, e.g. cv2: empty stand-ins for import (never on the Mac)')
    ap.add_argument('--deadline-s', type=float, default=1200, help='hard wall bound for the whole bench (supervisor)')
    return ap.parse_args(argv)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == CHILD_FLAG:
        sys.exit(child_main(parse(argv[1:])))
    a = parse(argv)
    sys.exit(supervise(argv, a.deadline_s))


if __name__ == '__main__':
    main()
