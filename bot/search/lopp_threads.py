"""Does the pinned native release the GIL, and how do K4L-R-gs's learned rollouts scale with threads? (exploration)

    python -m bot.search.lopp_threads --roots 8 --threads 4

Takes the first --roots searched roots of a K4C-r16 vs R3a HEADLINE game; on each, times (wall and process CPU)
the 11-ish work-set keys under (a) native rollout_e1 sequential vs a thread pool, (b) the learned-opponent
lockstep batch sequential vs split into thread chunks. Values must be identical across modes.
"""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--roots', type=int, default=8)
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--model', default='pool')
    a = ap.parse_args()
    import torch
    torch.set_num_threads(1)
    from bot.eval.headline import HEADLINE_BASE, make_player
    from bot.players.ours import play_match, x4s_setup
    from bot.players.runtime import Runtime
    from bot.search.lopp import Learned, batch_rollouts, load_model
    rt = Runtime()
    model = load_model(a.model)
    acc = {}

    def add(k, wall, cpu):
        s = acc.setdefault(k, [0., 0.])
        s[0] += wall; s[1] += cpu

    class Stop(Exception):
        pass

    case = x4s_setup(rt, 0, HEADLINE_BASE)
    seat = case['seat']
    cand = make_player(rt, 'K4C-r16')
    orig_start = cand.start
    n = [0]
    same = [True]

    def start(ctx):
        orig_start(ctx)
        core = cand.p.core
        inner = core.score_candidates

        def score(root, s, candidates, **kw):
            if n[0] >= a.roots:
                raise Stop
            n[0] += 1
            cfg = core.config
            keys = [c for c in candidates if c != 2400][:11]
            kw2 = dict(delay=core.command_delay, opp_delay=core.opponent_delay, horizon=cfg.horizon,
                       interval=cfg.interval, elixir_weight=cfg.elixir_weight, tick0=int(core.info.tick))
            nat = lambda c: core.native.rollout_e1(root, s, c, 'balanced', core.command_delay, core.opponent_delay,
                                                   cfg.horizon, cfg.interval, cfg.elixir_weight, 1e6)
            w0, c0 = time.perf_counter(), time.process_time()
            v_seq = [nat(c) for c in keys]
            add('native_seq', time.perf_counter() - w0, time.process_time() - c0)
            w0, c0 = time.perf_counter(), time.process_time()
            with ThreadPoolExecutor(a.threads) as ex:
                v_par = list(ex.map(nat, keys))
            add('native_threads', time.perf_counter() - w0, time.process_time() - c0)
            mk = lambda: Learned(model, sample=True, interval=5, seed=[0, int(core.info.tick)])
            w0, c0 = time.perf_counter(), time.process_time()
            l_seq = batch_rollouts(core.native, root, s, keys, mk(), **kw2)
            add('learned_seq', time.perf_counter() - w0, time.process_time() - c0)
            chunks = [keys[i::a.threads] for i in range(a.threads)]
            w0, c0 = time.perf_counter(), time.process_time()
            with ThreadPoolExecutor(a.threads) as ex:
                parts = list(ex.map(lambda ch: batch_rollouts(core.native, root, s, ch, mk(), **kw2), chunks))
            add('learned_threads', time.perf_counter() - w0, time.process_time() - c0)
            l_par = {}
            for ch, vals in zip(chunks, parts):
                l_par.update(zip(ch, vals))
            same[0] &= v_seq == v_par and l_seq == [l_par[c] for c in keys]
            acc.setdefault('keys', [0])[0] += len(keys)
            return inner(root, s, candidates, **kw)
        core.score_candidates = score
    cand.start = start
    try:
        play_match(rt, {seat: cand, 1 - seat: make_player(rt, 'R3a')}, seed=case['seed'], decks=case['decks'])
    except Stop:
        pass
    out = {k: dict(wall_ms_per_root=1e3 * v[0] / n[0], cpu_ms_per_root=1e3 * v[1] / n[0])
           for k, v in acc.items() if k != 'keys'}
    out.update(roots=n[0], keys_per_root=acc['keys'][0] / n[0], threads=a.threads, identical=same[0])
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
