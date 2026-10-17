"""Default-off parity across package trees (cycle-model owner; fleet only, never on the Mac).
    python parity_tree.py OUT.jsonl --tree TREE --label L --mode off|soft --names A,B --cases 0-9 --procs N
Imports everything from TREE (sys.path[0]); plays bank LIVE-AB1 cases vs R3a exactly as bot/cyclemodel/parity.py and
bot/fullpool/res_check.py do; one row per (name, case): command_sha256, winner, ticks, belief class, cycle_stats."""
import argparse, json, os, sys
from multiprocessing import Pool

A = None


def run(job):
    name, i = job
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    from bot.players.ours import play_match
    from bot.eval.headline import make_player
    from bot.fullpool.banks import BANKS, case, select
    from bot.fullpool.models import install_from_env
    g = globals()
    if '_RT' not in g:
        g['_RT'] = Runtime(); install_from_env(g['_RT']); select(g['_RT'], 'e16bl')
    rt = g['_RT']
    c = case(rt, i, BANKS['LIVE-AB1']['base'], 'e16bl')
    cand = make_player(rt, name)
    res = play_match(rt, {c['seat']: cand, 1 - c['seat']: make_player(rt, 'R3a')}, seed=c['seed'], decks=c['decks'])
    bel = getattr(getattr(cand, 'p', None), 'belief', None)
    import bot.players.runtime as rtm
    return dict(label=A.label, tree=A.tree, mode=A.mode, name=name, index=i, command_sha256=res['command_sha256'],
                winner=res['winner'], ticks=res['ticks'], belief=type(bel).__name__ if bel is not None else None,
                mro=[k.__name__ for k in type(bel).__mro__][:4] if bel is not None else None,
                cycle_stats=getattr(bel, 'cycle_stats', None), runtime_file=rtm.__file__)


def main():
    global A
    ap = argparse.ArgumentParser()
    ap.add_argument('out'); ap.add_argument('--tree', required=True); ap.add_argument('--label', required=True)
    ap.add_argument('--mode', choices=('off', 'soft'), required=True); ap.add_argument('--names', required=True)
    ap.add_argument('--cases', default='0-9'); ap.add_argument('--procs', type=int, default=8)
    A = ap.parse_args()
    sys.path.insert(0, A.tree)
    os.environ.pop('BOT_CYCLE_MODEL', None)
    if A.mode == 'soft':
        os.environ['BOT_CYCLE_MODEL'] = 'soft'
    lo, hi = map(int, A.cases.split('-'))
    jobs = [(n, i) for i in range(lo, hi + 1) for n in A.names.split(',')]
    with Pool(A.procs, maxtasksperchild=1) as pool, open(A.out, 'a') as fh:
        for row in pool.imap_unordered(run, jobs):
            fh.write(json.dumps(row) + '\n'); fh.flush()


if __name__ == '__main__':
    main()
