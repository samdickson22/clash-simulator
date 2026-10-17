"""Perfect-observation parity of the cycle model: command hashes with BOT_CYCLE_MODEL unset vs 'soft' (exploration).

    python -m bot.cyclemodel.parity OUT.jsonl --names K4L-R-gs-mk1a1,K4L-R-gs-rw-fc-t2-mk1a1 --cases 0-19 \
        --modes off,soft --procs 8

Plays bank LIVE-AB1 cases (e16 vs Battle Log decks, as bot/fullpool/res_check.py) for each (name, mode, case) vs R3a.
The mode is set in the worker before the players are made (planner_belief reads BOT_CYCLE_MODEL at start). One row
per job: command_sha256, winner, ticks, and the candidate belief's class and cycle_stats (expected: CycleFullPoolBelief
/ CycleBelief with 0 conflicts under 'soft'). Parity = identical command_sha256 per (name, case) across modes.
Summary: python -m bot.cyclemodel.parity --summary OUT.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from multiprocessing import Pool


def run(job):
    name, mode, i = job
    if mode == 'off':
        os.environ.pop('BOT_CYCLE_MODEL', None)
    else:
        os.environ['BOT_CYCLE_MODEL'] = mode
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    from bot.players.ours import play_match
    from bot.eval.headline import make_player
    from bot.fullpool.banks import BANKS, case, select
    from bot.fullpool.models import install_from_env
    global _RT
    if '_RT' not in globals():
        _RT = Runtime()
        install_from_env(_RT)
        select(_RT, 'e16bl')
    rt = _RT
    c = case(rt, i, BANKS['LIVE-AB1']['base'], 'e16bl')
    cand = make_player(rt, name)
    players = {c['seat']: cand, 1 - c['seat']: make_player(rt, 'R3a')}
    res = play_match(rt, players, seed=c['seed'], decks=c['decks'])
    bel = getattr(getattr(cand, 'p', None), 'belief', None)
    return dict(name=name, mode=mode, index=i, command_sha256=res['command_sha256'], winner=res['winner'],
                ticks=res['ticks'], belief=type(bel).__name__ if bel is not None else None,
                cycle_stats=getattr(bel, 'cycle_stats', None))


def summary(path):
    rows = [json.loads(l) for l in open(path)]
    by = defaultdict(dict)
    for r in rows:
        by[(r['name'], r['index'])][r['mode']] = r
    out = defaultdict(lambda: dict(cases=0, equal=0, differ=[], conflicts=0, classes=set()))
    for (name, i), m in sorted(by.items()):
        if 'off' not in m or len(m) < 2:
            continue
        for mode, r in m.items():
            if mode == 'off':
                continue
            o = out[(name, mode)]
            o['cases'] += 1
            same = r['command_sha256'] == m['off']['command_sha256']
            o['equal'] += same
            if not same:
                o['differ'].append(i)
            o['conflicts'] += (r.get('cycle_stats') or {}).get('conflicts', 0)
            o['classes'].add(r.get('belief'))
    for (name, mode), o in sorted(out.items()):
        print(f"{name} {mode}: {o['equal']}/{o['cases']} identical command hashes; differ {o['differ']}; "
              f"conflicts {o['conflicts']}; belief {sorted(map(str, o['classes']))}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--names', default='K4L-R-gs-mk1a1,K4L-R-gs-rw-fc-t2-mk1a1')
    ap.add_argument('--modes', default='off,soft')
    ap.add_argument('--cases', default='0-19')
    ap.add_argument('--procs', type=int, default=8)
    ap.add_argument('--summary', action='store_true')
    a = ap.parse_args(argv)
    if a.summary:
        summary(a.out)
        return
    lo, hi = map(int, a.cases.split('-'))
    done = set()
    if os.path.exists(a.out):
        done = {(r['name'], r['mode'], r['index']) for r in map(json.loads, open(a.out))}
    jobs = [(n, m, i) for i in range(lo, hi + 1) for n in a.names.split(',') for m in a.modes.split(',')
            if (n, m, i) not in done]
    # one mode per worker process would hide an env leak; maxtasksperchild=1 gives each job a fresh process
    with Pool(a.procs, maxtasksperchild=1) as pool, open(a.out, 'a') as fh:
        for row in pool.imap_unordered(run, jobs):
            fh.write(json.dumps(row) + '\n'); fh.flush()
            print(json.dumps(row), flush=True)


if __name__ == '__main__':
    main()
