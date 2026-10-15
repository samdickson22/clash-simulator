"""Which calls of a learned-opponent rollout hold the GIL: 1 vs N threads, per call, on pinned cores (exploration).

    python -m bot.search.lopp_gil --cpus 60,61,62,63 --threads 4 --cases 0,3 --decisions 12 [--model pool]

Roots: K4C-r16 vs R3a on HEADLINE cases, the first --decisions searched roots per case (as lopp_check). The process
(and the pool it forks) is pinned to --cpus with sched_setaffinity before anything starts.

Each op is a list of equal work units (one per root, repeated --reps times). wall_1 = all units on 1 thread; wall_N =
the same units on an N-thread pool (ThreadPoolExecutor.map). speedup = wall_1 / wall_N (N = perfect GIL release,
~1 = serialised on the GIL). Units never share a mutable state: each mutating unit gets its own clones, made
outside the timed region. Ops: BattleState.clone / step; NativeScripts.select_action / apply_discrete /
public_view / public_mask / evaluate / rollout_e1; json.loads + featurize (Python); the opponent forward, one row
(numpy). Then a whole learned batch (rw, sampled gate) per root, three ways on the same keys: serial unchunked,
N in-process threads (chunks as lopp_fast.chunk_keys), and the P-process pool (lopp_fast p<P>); values must be
equal bit for bit (rw).
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor


def timed(fn, units, ex):
    t0, c0 = time.perf_counter(), time.process_time()
    for u in units:
        fn(u)
    w1 = time.perf_counter() - t0
    t0, c0 = time.perf_counter(), time.process_time()
    list(ex.map(fn, units))
    wn, cn = time.perf_counter() - t0, time.process_time() - c0
    return dict(wall_1_ms=round(1e3 * w1, 1), wall_n_ms=round(1e3 * wn, 1), cpu_n_ms=round(1e3 * cn, 1),
                speedup=round(w1 / wn, 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cpus', default='60,61,62,63')
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--pool', type=int, default=4)
    ap.add_argument('--cases', default='0,3')
    ap.add_argument('--decisions', type=int, default=12)
    ap.add_argument('--reps', type=int, default=20)
    ap.add_argument('--model', default='pool')
    ap.add_argument('--repeat', type=int, default=3, help='repeat every measurement, report the median speedup run')
    a = ap.parse_args()
    cpus = {int(c) for c in a.cpus.split(',')}
    os.sched_setaffinity(0, cpus)
    import numpy as np
    import torch
    torch.set_num_threads(1)
    from bot.eval.headline import HEADLINE_BASE, make_player
    from bot.players.ours import play_match, x4s_setup
    from bot.players.runtime import Runtime
    from bot.players.base import WAIT
    from bot.search.lopp import Learned, batch_rollouts, load_model
    from bot.search.lopp_fast import chunk_keys, get_pool
    from bot.search.lopp_feat import featurize
    rt = Runtime()
    native = rt.R.native
    model = load_model(a.model)
    pool = get_pool(a.pool, native, a.model, rt.R.meta, rt.R.config)   # fork before any thread exists
    ex = ThreadPoolExecutor(max_workers=a.threads)
    roots = []

    class Stop(Exception):
        pass

    for i in [int(c) for c in a.cases.split(',')]:
        case = x4s_setup(rt, i, HEADLINE_BASE)
        seat = case['seat']
        cand = make_player(rt, 'K4C-r16')
        orig_start, n = cand.start, [0]

        def start(ctx, cand=cand, orig_start=orig_start, n=n, seed=case['seed'], seat=seat):
            orig_start(ctx)
            core = cand.p.core
            inner = core.score_candidates

            def score(root, s, candidates, **kw):
                if n[0] >= a.decisions:
                    raise Stop
                n[0] += 1
                cfg = core.config
                kw2 = dict(delay=core.command_delay, opp_delay=core.opponent_delay, horizon=cfg.horizon,
                           interval=cfg.interval, elixir_weight=cfg.elixir_weight, tick0=int(core.info.tick))
                roots.append(dict(root=root.clone(), seat=s, keys=[c for c in candidates if c != 2400], kw=kw2,
                                  seed=[seed, int(core.info.tick)]))
                return inner(root, s, candidates, **kw)
            core.score_candidates = score
        cand.start = start
        try:
            play_match(rt, {seat: cand, 1 - seat: make_player(rt, 'R3a')}, seed=case['seed'], decks=case['decks'])
        except Stop:
            pass
    R = a.reps
    out = dict(cpus=sorted(cpus), threads=a.threads, roots=len(roots), reps=R, affinity=sorted(os.sched_getaffinity(0)),
               ops={})

    def run(name, fn, units):
        res = sorted((timed(fn, units, ex) for _ in range(a.repeat)), key=lambda d: d['speedup'])
        out['ops'][name] = res[len(res) // 2]
        print(name, out['ops'][name], flush=True)

    # per-call ops; every unit = one root x R calls
    run('clone', lambda r: [r['root'].clone() for _ in range(R)], roots)
    units = [dict(sims=[r['root'].clone() for _ in range(R)]) for r in roots]
    run('step(5)', lambda u: [s.step(5) for s in u['sims']], units)
    units = [dict(sim=r['root'].clone(), seat=r['seat']) for r in roots]
    run('select_action', lambda u: [native.select_action(u['sim'], 1 - u['seat'], 'balanced') for _ in range(R)], units)
    run('public_view', lambda u: [native.public_view(u['sim'], 1 - u['seat']) for _ in range(R)], units)
    run('public_mask', lambda u: [native.public_mask(u['sim'], 1 - u['seat']) for _ in range(R)], units)
    run('evaluate', lambda u: [native.evaluate(u['sim'], u['seat'], 1.0) for _ in range(R)], units)
    acts = []
    for r in roots:
        a_ = native.select_action(r['root'], r['seat'], 'balanced')
        acts.append(a_ if a_ != WAIT else r['keys'][0])

    def apply_units():
        return [dict(sims=[r['root'].clone() for _ in range(R)], seat=r['seat'], act=x) for r, x in zip(roots, acts)]
    out['ops']['apply_discrete'] = None
    res = []
    for _ in range(a.repeat):     # fresh clones per measurement (apply mutates)
        u1, un = apply_units(), apply_units()
        t0 = time.perf_counter()
        for u in u1:
            [native.apply_discrete(s, u['seat'], u['act']) for s in u['sims']]
        w1 = time.perf_counter() - t0
        t0 = time.perf_counter()
        list(ex.map(lambda u: [native.apply_discrete(s, u['seat'], u['act']) for s in u['sims']], un))
        wn = time.perf_counter() - t0
        res.append(dict(wall_1_ms=round(1e3 * w1, 1), wall_n_ms=round(1e3 * wn, 1), speedup=round(w1 / wn, 2)))
    out['ops']['apply_discrete'] = sorted(res, key=lambda d: d['speedup'])[len(res) // 2]
    print('apply_discrete', out['ops']['apply_discrete'], flush=True)
    run('rollout_e1(all keys)', lambda r: [native.rollout_e1(r['root'].clone(), r['seat'], k, 'balanced',
                                                             r['kw']['delay'], r['kw']['opp_delay'], 160, 10, 1.0, 1e6)
                                           for k in r['keys']], roots)
    views = [native.public_view(r['root'], 1 - r['seat']) for r in roots]
    units = [dict(view=v, tick=r['kw']['tick0']) for v, r in zip(views, roots)]
    run('json.loads+featurize', lambda u: [featurize(json.loads(u['view']), u['tick'], model.cost_of)
                                           for _ in range(R)], units)
    feats = [featurize(json.loads(v), r['kw']['tick0'], model.cost_of) for v, r in zip(views, roots)]
    units = [dict(X=x[None], C=np.asarray([[model.vocab.get(t, 0) for t in hand]])) for x, hand in feats]
    run('forward 1 row (trunk+heads)', lambda u: [model.heads(model.trunk(u['X'], u['C'])) for _ in range(R)], units)

    # whole learned batches: serial vs in-process threads vs process pool, same keys, rw
    def opp(r):
        return Learned(model, sample=True, interval=5, seed=r['seed'], rowwise=True)
    spec = lambda r: dict(model=a.model, sample=True, switch=None, interval=5, seed=r['seed'], rowwise=True)
    t_ser = t_thr = t_pool = 0.
    mism = n_vals = 0
    for r in roots:
        keys = r['keys']
        parts = chunk_keys(keys, a.threads)
        t0 = time.perf_counter()
        ser = dict(zip(keys, batch_rollouts(native, r['root'], r['seat'], keys, opp(r), **r['kw'])))
        t1 = time.perf_counter()
        res = list(ex.map(lambda p: batch_rollouts(native, r['root'], r['seat'], p[1], opp(r), **r['kw']), parts))
        t2 = time.perf_counter()
        thr = {k: v for (cid, g), vals in zip(parts, res) for k, v in zip(g, vals)}
        pool.begin(r['root'], r['seat'], r['kw'], spec(r), None)
        pparts = chunk_keys(keys, a.pool)
        for w, (cid, g) in enumerate(pparts):
            pool.submit(w % a.pool, cid, g)
        got = pool.collect()
        t3 = time.perf_counter()
        pl = {k: v for cid, g in pparts for k, v in zip(g, got[cid])}
        t_ser, t_thr, t_pool = t_ser + t1 - t0, t_thr + t2 - t1, t_pool + t3 - t2
        mism += sum(not (ser[k] == thr[k] == pl[k]) for k in keys)
        n_vals += len(keys)
    n = len(roots)
    out['learned_batch_ms_per_root'] = dict(keys_per_root=round(n_vals / n, 1), serial=round(1e3 * t_ser / n, 1),
                                            threads=round(1e3 * t_thr / n, 1), pool=round(1e3 * t_pool / n, 1),
                                            value_mismatches=mism, values=n_vals)
    print('learned batch', out['learned_batch_ms_per_root'], flush=True)
    print(json.dumps(out))
    pool.close()


if __name__ == '__main__':
    main()
