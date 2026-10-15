"""Exactness + cost of the Python-driven rollout loop vs native rollout_e1 on real K4C-r16 roots (exploration).

    python -m bot.search.lopp_check --cases 0,1 --decisions 40 [--model pool]

Plays K4C-r16 vs R3a on HEADLINE cases; at each of the first --decisions searched roots, scores every candidate
(plays, WAIT, timed waits) with rollout_e1 and with lopp.batch_rollouts for the 3 scripted styles and reports
max |difference| and CPU per rollout; with --model also times learned-opponent rollouts on the same roots.
--model specs: name[:gs][:b<+-x>] (sampled gate; gate logit bias x), comma separated; reports plays per 160-tick
rollout and elixir at play (the in-rollout calibration of the opponent net). --no-exact skips the scripted check.
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cases', default='0,1')
    ap.add_argument('--decisions', type=int, default=40)
    ap.add_argument('--model', default=None)
    ap.add_argument('--opponent', default='R3a')
    ap.add_argument('--no-exact', action='store_true')
    a = ap.parse_args()
    import torch
    torch.set_num_threads(1)
    from bot.eval.headline import HEADLINE_BASE, make_player
    from bot.players.ours import play_match, x4s_setup
    from bot.players.runtime import Runtime
    from bot.search.lopp import Learned, batch_rollouts, load_model
    from bot.search.oppmodel import STYLES
    rt = Runtime()
    stats = dict(roots=0, rollouts=0, maxdiff=0., mismatches=0, t_native=0., t_python=0.)
    specs = [m for m in (a.model or '').split(',') if m]
    def parse(spec):
        parts = spec.split(':')
        bias = sum(float(x[1:]) for x in parts[1:] if x.startswith('b'))
        return spec, load_model(parts[0]), 'gs' in parts[1:], bias
    models = [parse(spec) for spec in specs]

    class Stop(Exception):
        pass

    for i in [int(c) for c in a.cases.split(',')]:
        case = x4s_setup(rt, i, HEADLINE_BASE)
        stats['case_roots'] = 0
        seat = case['seat']
        cand = make_player(rt, 'K4C-r16')
        players = {seat: cand, 1 - seat: make_player(rt, a.opponent)}
        orig_start = cand.start

        def start(ctx, cand=cand, orig_start=orig_start):
            orig_start(ctx)
            core = cand.p.core
            inner = core.score_candidates

            def score(root, s, candidates, **kw):
                if stats['case_roots'] >= a.decisions:
                    raise Stop
                stats['case_roots'] += 1
                cfg = core.config
                acts = [c for c in candidates if c != 2400]
                kw2 = dict(delay=core.command_delay, opp_delay=core.opponent_delay, horizon=cfg.horizon,
                           interval=cfg.interval, elixir_weight=cfg.elixir_weight, tick0=int(core.info.tick))
                for style in ([] if a.no_exact else STYLES):
                    t0 = time.process_time()
                    ref = [core.native.rollout_e1(root, s, c, style, core.command_delay, core.opponent_delay,
                                                  cfg.horizon, cfg.interval, cfg.elixir_weight, 1e6) for c in acts]
                    t1 = time.process_time()
                    got = batch_rollouts(core.native, root, s, acts, style, **kw2)
                    t2 = time.process_time()
                    d = np.abs(np.asarray(ref) - np.asarray(got))
                    stats['maxdiff'] = max(stats['maxdiff'], float(d.max()))
                    stats['mismatches'] += int((d > 0).sum())
                    stats['rollouts'] += len(acts)
                    stats['t_native'] += t1 - t0
                    stats['t_python'] += t2 - t1
                for spec, model, sample, bias in models:
                    opp = Learned(model, sample=sample, interval=5, seed=[0, int(core.info.tick)], rowwise=True,
                                  bias=bias)
                    t0 = time.process_time()
                    batch_rollouts(core.native, root, s, acts, opp, **kw2)
                    st = stats.setdefault(spec, dict(t=0., n=0, plays=0, calls=0, elixir=0.))
                    st['t'] += time.process_time() - t0
                    st['n'] += len(acts)
                    st['plays'] += opp.plays
                    st['calls'] += opp.calls
                    st['elixir'] += opp.elixir_at_play
                stats['roots'] += 1
                return inner(root, s, candidates, **kw)
            core.score_candidates = score
        cand.start = start
        try:
            play_match(rt, players, seed=case['seed'], decks=case['decks'])
        except Stop:
            pass
    out = dict(stats)
    out['ms_native_per_rollout'] = 1e3 * stats['t_native'] / max(1, stats['rollouts'])
    out['ms_python_per_rollout'] = 1e3 * stats['t_python'] / max(1, stats['rollouts'])
    for spec, *_ in models:
        st = stats[spec]
        out[spec] = dict(ms_per_rollout=1e3 * st['t'] / max(1, st['n']), play_rate=st['plays'] / max(1, st['calls']),
                         elixir_at_play=st['elixir'] / max(1, st['plays']), plays_per_rollout=st['plays'] / max(1, st['n']))
    print(json.dumps(out))


if __name__ == '__main__':
    main()
