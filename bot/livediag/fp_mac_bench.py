"""Decision-latency bench for full-pool live player names on recorded live battles (bot lead live-diag, exploration).

Replays RUN/perception.jsonl (the exact records the deployed driver handed to LiveSession.step, logged after its HUD
overrides and own-event dedupe) through the deployed driver's own construction: live/loop/drive.py make_session(rt,
make_live_player(rt, NAME), deck) with LL_HANDSYNC=1 as deployed (SyncSession + GuardedPlayer), clock anchored at the
run's match_start event. Every sess.step is timed (wall + process CPU); searched decisions report the player's own stats
(wall_ms, search_wall_ms, hit = incomplete at the cutoff, completed / candidates). Players run one after another in this
process, each on the same battles. Nothing is tapped: the game does not react to the replayed choices, so the states
are the deployed bot's own (representative of live), not the candidate's.

--load N starts N busy-loop processes for the duration (a crude stand-in for perception's CPU; the live loop's YOLO runs
mostly on the ANE/GPU, so N=0 is a lower bound and N=2..4 an upper-ish bracket). Quote results as bench numbers; confirm
on the first live battle (the live 'step' timing in decisions.jsonl / stepprof).

    # Mac (env exactly as loop/run-fullpool.sh, plus LL_HANDSYNC=1), from the code tree under test:
    python -B -m bot.livediag.fp_mac_bench --code $CODE --runs RUN1 RUN2 --players NAME1,NAME2 --out bench.json [--load 2]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import multiprocessing as mp
import os
import platform
import sys
import time
from pathlib import Path


def _spin(stop):
    x = 0
    while not stop.is_set():
        for _ in range(100000):
            x += 1


def q(xs, f):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(f * len(xs)))], 2) if xs else None


def load_drive(code, stubs=()):
    import types
    for m in stubs:                     # fleet only: modules drive.py imports at top level but the session never calls
        sys.modules.setdefault(m, types.ModuleType(m))
    p = Path(code) / 'live/loop/drive.py'
    sys.path.insert(0, str(p.parent))
    spec = importlib.util.spec_from_file_location('drive', p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def bench_run(drive, rt, name, run, max_steps=None):
    from bot.live.player import make_live_player
    cfg = json.loads((run / 'session-config.json').read_text())
    events = [json.loads(l) for l in open(run / 'events.jsonl')]
    start = next((e['ts_ms'] for e in events if e.get('ev') == 'match_start'), None)
    sess = drive.make_session(rt, make_live_player(rt, name), cfg['deck'])
    if start is not None:
        sess.tr.clock.anchor(0, start)
    steps, searched, errors = [], [], 0
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
        except Exception:
            errors += 1
            continue
        w, c = (time.perf_counter() - w0) * 1000, (time.process_time() - c0) * 1000
        st = (getattr(d, 'stats', None) or {}) if d is not None else {}
        steps.append(dict(wall=w, cpu=c, searched=st.get('source') == 'search'))
        if st.get('source') == 'search':
            searched.append(dict(step=w, wall_ms=st.get('wall_ms'), search_wall_ms=st.get('search_wall_ms'),
                                 hit=bool(st.get('hit')), completed=st.get('completed'), candidates=st.get('candidates'),
                                 rollouts=st.get('rollouts'), learned=st.get('learned_rollouts')))
    sess.close()
    return steps, searched, errors


def summary(steps, searched, errors, wall_s):
    sw = [s['wall'] for s in steps]
    ss = [s['step'] for s in searched]
    dw = [s['wall_ms'] for s in searched if s['wall_ms'] is not None]
    return dict(steps=len(steps), searched=len(searched), errors=errors, bench_wall_s=round(wall_s, 1),
                step_ms_p50_p95_p99=[q(sw, .5), q(sw, .95), q(sw, .99)],
                searched_step_ms_p50_p95_p99=[q(ss, .5), q(ss, .95), q(ss, .99)],
                decision_wall_ms_p50_p95_p99=[q(dw, .5), q(dw, .95), q(dw, .99)],
                cutoff_hit=round(sum(s['hit'] for s in searched) / max(1, len(searched)), 4),
                rollouts_mean=round(sum(s['rollouts'] or 0 for s in searched) / max(1, len(searched)), 1),
                learned_mean=round(sum(s['learned'] or 0 for s in searched) / max(1, len(searched)), 1),
                step_cpu_ms_mean=round(sum(s['cpu'] for s in steps) / max(1, len(steps)), 2))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--code', required=True, help='code tree under test (contains live/loop/drive.py)')
    ap.add_argument('--runs', nargs='+', required=True, type=Path)
    ap.add_argument('--players', required=True, help='comma-separated live player names, run in this order')
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--load', type=int, default=0)
    ap.add_argument('--max-steps', type=int, default=None)
    ap.add_argument('--repeat', type=int, default=1, help='repeat the player list (order effects / warm caches)')
    ap.add_argument('--stub-modules', default='', help='fleet only, e.g. cv2: empty stand-ins for import (never on the Mac)')
    a = ap.parse_args(argv)
    assert os.environ.get('PYTHONHASHSEED') == '0', 'PYTHONHASHSEED=0 (as the live launcher)'
    os.environ.setdefault('LL_HANDSYNC', '1')
    drive = load_drive(a.code, [m for m in a.stub_modules.split(',') if m])
    assert drive.HANDSYNC, 'LL_HANDSYNC=1 (deployed SyncSession)'
    from bot.players.runtime import Runtime
    rt = Runtime()
    stop, procs = mp.Event(), []
    for _ in range(a.load):
        p = mp.Process(target=_spin, args=(stop,), daemon=True)
        p.start()
        procs.append(p)
    out = dict(host=platform.node(), machine=platform.machine(), code=str(a.code), load=a.load,
               runs=[str(r) for r in a.runs], started=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), players={})
    try:
        for rep in range(a.repeat):
            for name in a.players.split(','):
                t0 = time.perf_counter()
                S, D, E = [], [], 0
                per_run = {}
                for run in a.runs:
                    s, d, e = bench_run(drive, rt, name, run, a.max_steps)
                    per_run[run.name] = summary(s, d, e, 0)
                    S += s; D += d; E += e
                key = name if a.repeat == 1 else f'{name}#{rep}'
                out['players'][key] = dict(summary(S, D, E, time.perf_counter() - t0), per_run=per_run)
                print(key, json.dumps({k: v for k, v in out['players'][key].items() if k != 'per_run'}), flush=True)
                a.out.write_text(json.dumps(out, indent=1) + '\n')
    finally:
        stop.set()
        for p in procs:
            p.join(timeout=5)
    out['finished'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    a.out.write_text(json.dumps(out, indent=1) + '\n')


if __name__ == '__main__':
    main()
