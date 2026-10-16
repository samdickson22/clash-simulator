"""`res` token check for the full-pool player (exploration).

    python -m bot.fullpool.res_check OUT.jsonl --names K4L-R-gs-mk1a1,K4L-R-gs-mk1a1-res --cases 0-9 --procs 8

Plays bank LIVE-AB1 cases (e16 vs Battle Log decks) for each name vs R3a and writes one row per (name, case):
command_sha256 and, when bot.search.reserve exists, how many reserve penalties were > 0 (the term fired).
Run the same names from two trees (before/after a change) and compare hashes per (name, case).
"""
from __future__ import annotations

import argparse
import json
from multiprocessing import Pool


def run(job):
    name, i = job
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
    fired = dict(calls=0, positive=0)
    try:
        from bot.search import reserve
        orig = reserve.apply
        if '_ORIG' not in globals():
            globals()['_ORIG'] = orig
        orig = globals()['_ORIG']

        def counting(core, scores, elixir):
            pen = getattr(core, 'reserve', None)
            if pen is not None:
                for a in scores:
                    fired['calls'] += 1
                    fired['positive'] += pen(a, elixir) > 0
            return orig(core, scores, elixir)
        import bot.search.lopp as lopp_mod
        import bot.search.lopp_fast as fast_mod
        for m in (lopp_mod, fast_mod):        # both bind `reserve_apply` at import time
            if hasattr(m, 'reserve_apply'):
                m.reserve_apply = counting
    except ImportError:
        fired = None
    c = case(rt, i, BANKS['LIVE-AB1']['base'], 'e16bl')
    players = {c['seat']: make_player(rt, name), 1 - c['seat']: make_player(rt, 'R3a')}
    res = play_match(rt, players, seed=c['seed'], decks=c['decks'])
    return dict(name=name, index=i, command_sha256=res['command_sha256'], winner=res['winner'], ticks=res['ticks'],
                reserve=fired)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--names', required=True)
    ap.add_argument('--cases', default='0-9')
    ap.add_argument('--procs', type=int, default=8)
    a = ap.parse_args(argv)
    lo, hi = map(int, a.cases.split('-'))
    jobs = [(n, i) for n in a.names.split(',') for i in range(lo, hi + 1)]
    with Pool(a.procs) as pool, open(a.out, 'a') as fh:
        for row in pool.imap_unordered(run, jobs):
            fh.write(json.dumps(row) + '\n'); fh.flush()
            print(json.dumps(row), flush=True)


if __name__ == '__main__':
    main()
