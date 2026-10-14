"""Probe: does rollout_commands reproduce rollout_e1's leaf? How fast is snapshot()? (exploration)

    bot/players/run.sh -m bot.value.probe --ticks 1200

Plays K4S-st vs R3a in our engine for --ticks ticks; on the first --roots searched roots
it re-runs every (action, style) of the frozen search with rollout_commands and reports
max |phi_e1 - phi_commands| per action class, plus snapshot()/parse timing.
"""
from __future__ import annotations

import argparse
import json
import time

from bot.players.base import WAIT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ticks', type=int, default=1200)
    ap.add_argument('--roots', type=int, default=6)
    ap.add_argument('--index', type=int, default=3)
    a = ap.parse_args()
    from bot.players.runtime import Runtime
    from bot.players.ours import play_match, x4s_setup
    from bot.eval.headline import make_player
    rt = Runtime()
    case = x4s_setup(rt, a.index, 777)
    cand = make_player(rt, 'K4S-st')
    captured = []
    orig_start = cand.start

    def start(ctx):
        orig_start(ctx)
        core = cand.p.core
        orig = core.score_candidates

        def score(root, seat, candidates, **kw):
            if len(captured) < a.roots:
                captured.append((root.clone(), seat, list(candidates), core.command_delay, core.opponent_delay,
                                 core.config.interval, core.config.elixir_weight, core.config.horizon))
            return orig(root, seat, candidates, **kw)
        core.score_candidates = score
    cand.start = start
    players = {case['seat']: cand, 1-case['seat']: make_player(rt, 'R3a')}
    play_match(rt, players, seed=case['seed'], decks=case['decks'], max_ticks=a.ticks)
    native = rt.R.native
    diffs, times = {}, dict(e1=[], commands=[], snapshot=[], parse=[], parts=[])
    for root, seat, cands, d, od, iv, ew, h in captured:
        for act in cands:
            if act == 2305:
                continue
            for style in ('balanced', 'pressure', 'defense'):
                t0 = time.perf_counter()
                v1 = native.rollout_e1(root, seat, act, style, d, od, h, iv, ew, 1e6)
                t1 = time.perf_counter()
                try:
                    v2, _, sim = native.rollout_commands(root, seat, act, [], style, d, od, 1, 1, h, iv, iv, ew,
                                                         True, False, False)
                except Exception as ex:
                    diffs.setdefault(f'err:{act if act >= WAIT else "play"}', repr(ex)[:120])
                    continue
                t2 = time.perf_counter()
                s = sim.snapshot()
                t3 = time.perf_counter()
                js = json.loads(s)
                t4 = time.perf_counter()
                parts = native.evaluation_parts(sim)
                t5 = time.perf_counter()
                v3 = native.evaluate(sim, seat, ew)
                key = act if act >= WAIT else 'play'
                diffs[key] = max(diffs.get(key, 0.), abs(v1-v2), abs(v1-v3))
                for k, x in zip(times, (t1-t0, t2-t1, t3-t2, t4-t3, t5-t4)):
                    times[k].append(x)
    print('roots', len(captured), 'max |diff| by action class', diffs)
    print('mean ms', {k: round(1e3*sum(v)/max(len(v), 1), 3) for k, v in times.items()})
    print('snapshot bytes', len(s), 'top keys', list(js)[:40])
    ents = js.get('entities') or []
    print('entities', len(ents))
    if ents:
        print('entity keys', sorted(ents[0])[:80])
    pl = js.get('players')
    if pl:
        print('player keys', sorted(pl[0]))
    print('parts', parts)
    for seat_ in (0, 1):
        t0 = time.perf_counter(); pv = native.public_view(sim, seat_); t1 = time.perf_counter()
        pj = json.loads(pv); t2 = time.perf_counter()
        print('public_view seat', seat_, 'bytes', len(pv), 'ms', round(1e3*(t1-t0), 3), round(1e3*(t2-t1), 3))
    print({k: (v if k != "bodies" else len(v)) for k, v in pj.items()})


if __name__ == '__main__':
    main()
