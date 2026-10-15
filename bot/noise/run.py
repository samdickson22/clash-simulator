"""Noise-robust screens: bot.live.headline_wall (same HEADLINE cases, play_match, scoring, row schema, pinned core
groups, resumable) plus the NR-/CAP: names (bot/noise/player.py) and per-game decision stats in each row:

    python -m bot.noise.run --out DIR --cores 0-35 --group 1 --candidate PERC-emp:NR-c2i12m3v5:LIVE-fast-it5s2 \
        --opponents v1,R3a --games 300 [--base B] [--start 0]

Extra row fields: `dec` = the candidate LivePlayer's decisions (count, sources, wall_ms p50/p95/p99/max for decisions
that ran the search tier, default share), `nr` = the filter/fidelity counters, `timing` = play_match's per-seat
timing of the candidate seat (overrun_ticks counts late decisions).
"""
from __future__ import annotations

import argparse
import json
import os
import time
from multiprocessing import Process
from pathlib import Path

import numpy as np


def install():
    import bot.eval.headline as headline
    import bot.live.player as lp
    from bot.noise.player import make_player as noise_make
    orig = lp._HEADLINE_MAKE_PLAYER

    def fallback(rt, name):
        p = noise_make(rt, name, lp.make_live_player)
        return p if p is not None else orig(rt, name)
    lp._HEADLINE_MAKE_PLAYER = fallback
    headline.make_player = lp.make_live_player
    return lp.make_live_player


def dec_summary(player):
    from bot.live.player import LivePlayer
    from bot.noise.player import NoiseRobustPlayer, find
    out = {}
    live = find(player, LivePlayer)
    if live is not None and live.decisions:
        src = {}
        for d in live.decisions:
            src[d['source']] = src.get(d['source'], 0) + 1
        searched = [d['wall_ms'] for d in live.decisions if d['source'] == 'search' or d['source'].startswith('default')]
        out['dec'] = dict(n=len(live.decisions), src=src)
        if searched:
            w = np.asarray(searched)
            out['dec'].update(n_search=len(w), p50=round(float(np.percentile(w, 50)), 1),
                              p95=round(float(np.percentile(w, 95)), 1), p99=round(float(np.percentile(w, 99)), 1),
                              max=round(float(w.max()), 1),
                              default=sum(v for k, v in src.items() if k.startswith('default')))
    nr = find(player, NoiseRobustPlayer)
    if nr is not None:
        out['nr'] = nr.summary()
    from bot.noise.audit import AuditPlayer
    aud = find(player, AuditPlayer)
    if aud is not None:
        out['aud'] = aud.summary()
    from bot.noise.shadow import FanPlayer
    fan = find(player, FanPlayer)
    if fan is not None:
        out['fan'] = fan.summary()
    return out


def worker(wid, cores, jobs, out, base, engine):
    if cores:
        os.sched_setaffinity(0, cores)
    os.environ.setdefault('PYTHONHASHSEED', '0')
    import torch
    torch.set_num_threads(1)
    make_player = install()
    from bot.players.runtime import Runtime
    from bot.players.ours import play_match, x4s_setup
    from bot.players.variants import close_logged
    rt = Runtime()
    fh = open(out / f'games-{wid:03d}.jsonl', 'a')
    for cand, opp, i in jobs:
        case = x4s_setup(rt, i, base)
        t0 = time.time()
        try:
            players = {case['seat']: make_player(rt, cand), 1 - case['seat']: make_player(rt, opp)}
            res = play_match(rt, players, seed=case['seed'], decks=case['decks'])
            for pl in players.values():
                close_logged(pl)
            w = res['winner']
            score = 0.5 if w is None or w == -1 else (1.0 if w == case['seat'] else 0.0)
            row = dict(engine=engine, candidate=cand, opponent=opp, index=i, seat=case['seat'], seed=case['seed'],
                       score=score, winner=w, terminal=res['terminal'], ticks=res['ticks'], towers=res['towers'],
                       plays=res['plays'], accepted=res['accepted'], command_sha256=res['command_sha256'],
                       cpu_seconds=res['cpu_seconds'], wall_seconds=time.time() - t0,
                       timing=res['timing'][case['seat']], **dec_summary(players[case['seat']]))
        except Exception as ex:  # recorded, never silently dropped
            import traceback
            row = dict(candidate=cand, opponent=opp, index=i, seat=case['seat'], error=repr(ex)[:500],
                       tb=traceback.format_exc()[-1500:])
        fh.write(json.dumps(row) + '\n'); fh.flush()


def main():
    from bot.eval.headline import HEADLINE_BASE, done_keys, reap
    from bot.live.headline_wall import parse_cores
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--opponents', required=True)
    ap.add_argument('--games', type=int, default=300)
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--cores', help="physical cores to pin groups to, e.g. '0-35'")
    ap.add_argument('--workers', type=int, help='unpinned workers instead of --cores (loaded shared hosts)')
    ap.add_argument('--group', type=int, default=1)
    ap.add_argument('--base', type=int, default=HEADLINE_BASE)
    ap.add_argument('--order', default='index', choices=['index', 'candidate'])
    a = ap.parse_args()
    if a.workers:
        groups = [None]*a.workers
    else:
        cores = parse_cores(a.cores)
        groups = [cores[i:i+a.group] for i in range(0, len(cores) - a.group + 1, a.group)]
    a.out.mkdir(parents=True, exist_ok=True)
    done = done_keys(a.out)
    jobs = [(c, o, i) for i in range(a.start, a.start + a.games) for c in a.candidate.split(',')
            for o in a.opponents.split(',') if (c, o, i) not in done]
    shares = [jobs[w::len(groups)] for w in range(len(groups))]
    (a.out / 'launch.json').write_text(json.dumps(dict(
        args={k: str(v) for k, v in vars(a).items()}, groups=groups, jobs=len(jobs), started=time.time(),
        tool='bot.noise.run')))
    procs = [Process(target=worker, args=(w, g, s, a.out, a.base, 'ours'))
             for w, (g, s) in enumerate(zip(groups, shares)) if s]
    for p in procs:
        p.start()
    reap(procs)


if __name__ == '__main__':
    main()
