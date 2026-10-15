"""Exactness + timing of lopp_fast's paths on real K4C-r16 roots (exploration).

    python -m bot.search.lopp_fast_check --cases 0,1 --decisions 40 --pool 4 --threads 4 [--model pool]

Plays K4C-r16 vs R3a on HEADLINE cases; at each of the first --decisions searched roots (all candidates except
2400, as lopp_check):
- snapshot: BattleState(root.snapshot()) has root's digest, and rollout_e1 gives the same value on it for every
  candidate and style; same for the root rebuilt with the deck-card-only config (lopp_fast.ConfigCache, what the
  pool workers use; its digest is reported, not required, since the config differs);
- scripted: for each of the 3 styles, rollout_e1 == batch_rollouts (serial) == rollout_e1 on --threads threads
  == the pool's chunked batch_rollouts (chunks as lopp_fast.chunk_keys) — bit for bit;
- learned (sampled gate, --model): pool chunks == the serial chunked twin (c<P>) bit for bit; also reports how
  often the unchunked 11-key batch (K4L-R-gs) differs from the chunked one (float32 batch composition), and wall
  ms per root of: serial unchunked, serial chunked, pool. With --rowwise (rw forward) the pool must also equal
  the unchunked serial batch.
"""
from __future__ import annotations

import argparse
import json
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cases', default='0,1')
    ap.add_argument('--decisions', type=int, default=40)
    ap.add_argument('--pool', type=int, default=4)
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--model', default='pool')
    ap.add_argument('--opponent', default='R3a')
    ap.add_argument('--rowwise', action='store_true', help='rw forward: pool chunks must equal the UNCHUNKED batch')
    a = ap.parse_args()
    import torch
    torch.set_num_threads(1)
    from bot.eval.headline import HEADLINE_BASE, make_player
    from bot.players.ours import play_match, x4s_setup
    from bot.players.runtime import Runtime
    from bot.search.lopp import Learned, batch_rollouts, load_model
    from bot.search.lopp_fast import ConfigCache, chunk_keys, get_executor, get_pool, split_snapshot
    from bot.search.oppmodel import STYLES
    rt = Runtime()
    model = load_model(a.model)
    pool = get_pool(a.pool, rt.R.native, a.model, rt.R.meta)   # fork before any thread pool exists
    print('pool start method', pool.method, flush=True)
    ex = get_executor(a.threads)
    st = dict(roots=0, rollouts=0, snapshot_mismatch=0, scripted_mismatch=0, learned_pool_mismatch=0,
              learned_values=0, unchunked_vs_chunked_differ=0, t_serial=0., t_chunked=0., t_pool=0.,
              t_snapshot=0., snapshot_bytes=0, cut_mismatch=0, cut_digest_differs=0, learned_pool_vs_unchunked=0)
    caches = {}

    class Stop(Exception):
        pass

    def pool_run(root, s, kw, opp, parts):
        pool.begin(root, s, kw, opp, None)
        for w, (cid, group) in enumerate(parts):
            pool.submit(w % a.pool, cid, group)
        res = pool.collect()
        out = {}
        for cid, group in parts:
            out.update(zip(group, res[cid]))
        return out

    for i in [int(c) for c in a.cases.split(',')]:
        case = x4s_setup(rt, i, HEADLINE_BASE)
        st['case_roots'] = 0
        seat = case['seat']
        cand = make_player(rt, 'K4C-r16')
        orig_start = cand.start

        def start(ctx, cand=cand, orig_start=orig_start):
            orig_start(ctx)
            core = cand.p.core
            inner = core.score_candidates

            def score(root, s, candidates, **kw):
                if st['case_roots'] >= a.decisions:
                    raise Stop
                st['case_roots'] += 1
                cfg = core.config
                acts = [c for c in candidates if c != 2400]
                kw2 = dict(delay=core.command_delay, opp_delay=core.opponent_delay, horizon=cfg.horizon,
                           interval=cfg.interval, elixir_weight=cfg.elixir_weight, tick0=int(core.info.tick))
                nat = lambda r, c, style: core.native.rollout_e1(r, s, c, style, core.command_delay,
                                                                 core.opponent_delay, cfg.horizon, cfg.interval,
                                                                 cfg.elixir_weight, 1e6)
                t0 = time.perf_counter()
                snap = root.snapshot()
                copy = type(root)(snap)
                st['t_snapshot'] += time.perf_counter() - t0
                st['snapshot_bytes'] += len(snap)
                st['snapshot_mismatch'] += copy.digest() != root.digest()
                head, cfg_text, tail = split_snapshot(snap)
                if cfg_text not in caches:
                    caches[cfg_text] = ConfigCache(cfg_text)
                cut = type(root)(caches[cfg_text].payload(head, tail))
                st['cut_digest_differs'] += cut.digest() != root.digest()
                parts = chunk_keys(acts, a.pool)
                for style in STYLES:
                    ref = [nat(root, c, style) for c in acts]
                    st['snapshot_mismatch'] += sum(x != y for x, y in zip(ref, [nat(copy, c, style) for c in acts]))
                    st['cut_mismatch'] += sum(x != y for x, y in zip(ref, [nat(cut, c, style) for c in acts]))
                    ser = batch_rollouts(core.native, root, s, acts, style, **kw2)
                    thr = list(ex.map(lambda c: nat(root.clone(), c, style), acts))
                    pl = pool_run(root, s, kw2, style, parts)
                    st['scripted_mismatch'] += sum(not (r == x == y == pl[c]) for c, r, x, y in zip(acts, ref, ser, thr))
                    st['rollouts'] += len(acts)
                seed = [case['seed'], int(core.info.tick)]
                mk = lambda: Learned(model, sample=True, interval=5, seed=seed, rowwise=a.rowwise)
                spec = dict(model=a.model, sample=True, switch=None, interval=5, seed=seed, rowwise=a.rowwise)
                t0 = time.perf_counter()
                full = dict(zip(acts, batch_rollouts(core.native, root, s, acts, mk(), **kw2)))
                t1 = time.perf_counter()
                chunked = {}
                for cid, group in parts:
                    chunked.update(zip(group, batch_rollouts(core.native, root, s, group, mk(), **kw2)))
                t2 = time.perf_counter()
                pl = pool_run(root, s, kw2, spec, parts)
                t3 = time.perf_counter()
                st['t_serial'] += t1 - t0
                st['t_chunked'] += t2 - t1
                st['t_pool'] += t3 - t2
                st['learned_values'] += len(acts)
                st['learned_pool_mismatch'] += sum(chunked[c] != pl[c] for c in acts)
                st['learned_pool_vs_unchunked'] += sum(full[c] != pl[c] for c in acts)
                st['unchunked_vs_chunked_differ'] += sum(chunked[c] != full[c] for c in acts)
                st['roots'] += 1
                return inner(root, s, candidates, **kw)
            core.score_candidates = score
        cand.start = start
        try:
            play_match(rt, {seat: cand, 1 - seat: make_player(rt, a.opponent)}, seed=case['seed'],
                       decks=case['decks'])
        except Stop:
            pass
    n = max(1, st['roots'])
    out = dict(st, keys_per_root=st['learned_values'] / n,
               ms_per_root=dict(serial_unchunked=1e3 * st['t_serial'] / n, serial_chunked=1e3 * st['t_chunked'] / n,
                                pool=1e3 * st['t_pool'] / n),
               snapshot_ms=1e3 * st['t_snapshot'] / n, snapshot_kb=st['snapshot_bytes'] / n / 1024,
               exact=st['snapshot_mismatch'] == st['scripted_mismatch'] == st['learned_pool_mismatch']
               == st['cut_mismatch'] == 0 and (not a.rowwise or st['learned_pool_vs_unchunked'] == 0))
    for k in ('t_serial', 't_chunked', 't_pool', 't_snapshot', 'snapshot_bytes', 'case_roots'):
        out.pop(k)
    print(json.dumps(out, indent=1))
    pool.close()


if __name__ == '__main__':
    main()
