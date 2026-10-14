"""HEADLINE-v1 games for search-compute variants, with per-decision cost (exploration).

    python -m bot.search.run --out DIR --candidate K4S-m4 --opponents R3a,v1 --games 300 --workers 48

Same cases, match loop and score as bot.eval.headline (rows are summarize-compatible), plus
the candidate's search cost: decisions, CPU s in decisions (process time inside act on
searched polls), mean rollouts per decision (single-root rollouts at the arm's horizon),
and the variant diagnostics from bot/search/players.py.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from multiprocessing import Process
from pathlib import Path

from bot.eval.headline import HEADLINE_BASE, done_keys, make_player


def search_summary(player, timing):
    ds = [d for d in getattr(player, 'decisions', []) if d]
    mean = lambda k: (sum(d[k] for d in ds if d.get(k) is not None) /
                      max(1, sum(d.get(k) is not None for d in ds)))
    out = dict(decisions=timing['decisions'], decision_cpu=timing['cpu'], decision_wall=timing['wall'],
               searched=len(ds), rollouts=mean('rollouts'), candidates=mean('candidates'),
               hits=sum(bool(d.get('hit')) for d in ds), resolved=mean('resolved'))
    if any('root_disagree' in d for d in ds):
        out.update(root_disagree=mean('root_disagree'), min_disagree=mean('min_disagree'),
                   chosen_sd=mean('chosen_sd'))
    return out


def worker(wid, jobs, out: Path, base: int):
    os.environ.setdefault('PYTHONHASHSEED', '0')
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    from bot.players.ours import play_match, x4s_setup
    rt = Runtime()
    fh = open(out / f'games-{wid:03d}.jsonl', 'a')
    for cand, opp, i in jobs:
        case = x4s_setup(rt, i, base)
        t0 = time.time()
        try:
            seat = case['seat']
            players = {seat: make_player(rt, cand), 1 - seat: make_player(rt, opp)}
            res = play_match(rt, players, seed=case['seed'], decks=case['decks'])
            w = res['winner']
            score = 0.5 if w is None or w == -1 else (1.0 if w == seat else 0.0)
            row = dict(engine='ours', candidate=cand, opponent=opp, index=i, seat=seat, seed=case['seed'],
                       score=score, winner=w, terminal=res['terminal'], ticks=res['ticks'], towers=res['towers'],
                       plays=res['plays'], accepted=res['accepted'], command_sha256=res['command_sha256'],
                       cpu_seconds=res['cpu_seconds'], wall_seconds=time.time() - t0,
                       search=search_summary(players[seat], res['timing'][seat]))
        except Exception as ex:  # recorded, never silently dropped
            import traceback
            row = dict(candidate=cand, opponent=opp, index=i, seat=case['seat'], error=repr(ex)[:500],
                       trace=traceback.format_exc()[-2000:])
        fh.write(json.dumps(row) + '\n'); fh.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--candidate', required=True, help='comma list allowed')
    ap.add_argument('--opponents', default='R3a,v1')
    ap.add_argument('--games', type=int, default=300)
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--indices', default='', help='explicit comma list of case indices (overrides start/games)')
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--base', type=int, default=HEADLINE_BASE)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    done = done_keys(a.out)
    indices = ([int(x) for x in a.indices.split(',')] if a.indices else range(a.start, a.start + a.games))
    jobs = [(c, o, i) for c in a.candidate.split(',') for o in a.opponents.split(',')
            for i in indices if (c, o, i) not in done]
    shares = [jobs[w::a.workers] for w in range(a.workers)]
    (a.out / f'launch-{int(time.time())}.json').write_text(json.dumps(dict(
        args={k: str(v) for k, v in vars(a).items()}, jobs=len(jobs), started=time.time())))
    procs = [Process(target=worker, args=(w, s, a.out, a.base)) for w, s in enumerate(shares) if s]
    for p in procs:
        p.start()
    for p in procs:
        p.join()


if __name__ == '__main__':
    main()
