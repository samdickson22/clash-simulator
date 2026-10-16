"""ExIt label generation: student-vs-pool games in our engine, K4S budget teacher labels the student seat(s).

    python -m bot.exit.generate --out DIR --student student:R/R3a.pt@0.5005528330802917 \
        --pool v1,R3a,self --games 1200 --workers 96 --budget 64 --base BASE

Game g (g = start..start+games-1) is case x4s_setup(g, BASE): student seat g%2, X-deck g%5 vs
X-deck (g//5)%5, shuffled by Random(BASE+g); opponent = pool[g % len(pool)]. --decks fullpool:<seed>[:own=c56]
(or --bank FP-TRAIN1) draws both decks from the full-pool sampler instead (bot/fullpool/banks.py); own=c56 keeps the
student seat's deck C56, which the K4S teacher needs while R.bots is C56. 'self' = the same
student in the other seat, and then BOTH seats are labelled (two shards). Any HEADLINE player
name is a valid pool entry (v1, R3a, scripted-*, student:...).

BASE must be a fresh bank, disjoint from the HEADLINE bank (checked). Output:
  DIR/games/game-<g:07d>-s<seat>/   sealed teacher-v6 shard (rows.seal)
  DIR/games-<worker>.jsonl          one line per finished game (resume key = g)
  DIR/STOP                          if present, workers stop after their current game
"""
from __future__ import annotations

import argparse
import json
import os
import time
from multiprocessing import Process
from pathlib import Path

from bot.eval.headline import HEADLINE_BASE

GAMES_PER_BANK_GUARD = 1 << 20


def check_bank(base, start, games, reserved=None):
    if reserved is None:   # HEADLINE plus every eval bank of bot/fullpool/banks.py
        from bot.fullpool.banks import reserved_eval_banks
        reserved = ((HEADLINE_BASE, 100_000),) + reserved_eval_banks()
    lo, hi = base + start, base + start + games
    for rb, span in reserved:
        if lo < rb + span and rb < hi:
            raise ValueError(f'training bank [{lo},{hi}) overlaps reserved bank {rb}+[0,{span})')


def done_games(out: Path):
    keys = set()
    for p in out.glob('games-*.jsonl'):
        for line in p.read_text().splitlines():
            try:
                r = json.loads(line)
                if 'error' not in r:
                    keys.add(r['game'])
            except Exception:
                pass
    return keys


def make_any(rt, name):
    from bot.eval.headline import make_player
    return make_player(rt, name)


def play_one(rt, g, a, out: Path):
    from bot.players.ours import play_match
    from bot.players.search import SearchPlayer
    from bot.fullpool.banks import case as make_case
    from .label import LabelingPlayer, seal_rows
    case = make_case(rt, g, a.base, a.decks)   # decks='x4s' -> x4s_setup
    seat = case['seat']
    opp = a.pool[g % len(a.pool)]

    def labeller():
        teacher = (SearchPlayer(rt, mode='budget', budget=a.budget, default='R3a') if a.teacher is None
                   else make_any(rt, a.teacher))
        return LabelingPlayer(rt, make_any(rt, a.student), teacher, beta=a.beta)
    players = {seat: labeller()}
    players[1 - seat] = labeller() if opp == 'self' else make_any(rt, opp)
    t0 = time.time()
    res = play_match(rt, players, seed=case['seed'], decks=case['decks'])
    w = res['winner']
    shards = {}
    for s, p in players.items():
        if not hasattr(p, 'rows'):
            continue
        outcome = 0. if w is None or w == -1 else (1. if w == s else -1.)
        if p.rows:
            receipt = dict(seed=case['seed'], game=g, seat=s, opponent=opp, student=a.student,
                           teacher=p.teacher.name, beta=a.beta, base=a.base, outcome=outcome, winner=w,
                           ticks=res['ticks'], rows=len(p.rows), counts=p.counts,
                           command_sha256=res['command_sha256'])
            if a.decks != 'x4s':
                receipt.update(decks=a.decks, deck_lists=case['decks'])
            seal_rows(out / 'games' / f'game-{g:07d}-s{s}', p.rows, p.scores, receipt)
        shards[s] = dict(p.counts, outcome=outcome)
    score = 0.5 if w is None or w == -1 else (1.0 if w == seat else 0.0)
    row = dict(game=g, seed=case['seed'], seat=seat, opponent=opp, score=score, winner=w,
               terminal=res['terminal'], ticks=res['ticks'], plays=res['plays'], shards=shards,
               command_sha256=res['command_sha256'], cpu_seconds=res['cpu_seconds'],
               wall_seconds=time.time() - t0)
    if a.decks != 'x4s':
        row.update(decks=a.decks, deck_lists=case['decks'])
    return row


def worker(wid, games, a, out: Path):
    os.environ.setdefault('PYTHONHASHSEED', '0')
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    from bot.fullpool.banks import check_scope, select
    from bot.fullpool.models import install_from_env
    rt = Runtime()
    install_from_env(rt)              # BOT_FULLPOOL_POLICIES (extended v1/R3a); unset = no-op
    select(rt, a.decks, a.belief_prior)
    check_scope(rt, a.decks, len(games), min(games, default=0), a.base)
    with open(out / f'games-{wid:03d}.jsonl', 'a') as fh:
        for g in games:
            if (out / 'STOP').exists():
                break
            try:
                row = play_one(rt, g, a, out)
            except Exception as ex:  # recorded, never silently dropped
                import traceback
                row = dict(game=g, error=repr(ex)[:500], trace=traceback.format_exc()[-2000:])
            fh.write(json.dumps(row) + '\n'); fh.flush()



def reap(procs):
    """Join workers as they exit (not in list order), so finished workers never linger as zombies."""
    from multiprocessing.connection import wait
    live = {p.sentinel: p for p in procs}
    while live:
        for sentinel in wait(list(live)):
            live.pop(sentinel).join()

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--student', required=True, help="behavior player, e.g. 'student:PATH@THR' or 'R3a'")
    ap.add_argument('--pool', default='v1,R3a,self')
    ap.add_argument('--games', type=int, required=True)
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--budget', type=int, default=64)
    ap.add_argument('--beta', type=float, default=0.0)
    ap.add_argument('--teacher', help="search player name (default K4S-b<budget>), e.g. 'K4SP4-b64'")
    ap.add_argument('--base', type=int, help='seed bank (fresh, disjoint from every eval bank: checked)')
    ap.add_argument('--decks', default='x4s', help="'x4s' (default, X-decks) or a full-pool deck spec "
                    "'fullpool:<seed>[:own=c56]' (bot/fullpool/banks.py; needs pins r1-cards1)")
    ap.add_argument('--belief-prior', default=None, help="teacher belief prior: 'c56' or a deck spec (default: --decks)")
    ap.add_argument('--bank', default=None, help='named bank of bot/fullpool/banks.py (sets --base and --decks)')
    a = ap.parse_args(argv)
    if a.bank:
        from bot.fullpool.banks import BANKS
        a.base, a.decks = BANKS[a.bank]['base'], BANKS[a.bank]['decks']
    if a.base is None:
        ap.error('--base or --bank is required')
    a.pool = a.pool.split(',')
    check_bank(a.base, a.start, a.games)
    if a.workers > 96:
        raise ValueError('<=96 worker processes per host')
    (a.out / 'games').mkdir(parents=True, exist_ok=True)
    done = done_games(a.out)
    todo = [g for g in range(a.start, a.start + a.games) if g not in done]
    shares = [todo[w::a.workers] for w in range(a.workers)]
    (a.out / f'launch-{int(time.time())}.json').write_text(json.dumps(dict(
        args={k: (v if isinstance(v, (int, float, list)) else str(v)) for k, v in vars(a).items()},
        todo=len(todo), started=time.time())))
    procs = [Process(target=worker, args=(w, s, a, a.out)) for w, s in enumerate(shares) if s]
    for p in procs:
        p.start()
    reap(procs)


if __name__ == '__main__':
    main()
