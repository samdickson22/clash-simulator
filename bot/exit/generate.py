"""ExIt label generation: student-vs-pool games in our engine, K4S budget teacher labels the student seat(s).

    python -m bot.exit.generate --out DIR --student student:R/R3a.pt@0.5005528330802917 \
        --pool v1,R3a,self --games 1200 --workers 96 --budget 64 --base BASE

Game g (g = start..start+games-1) is case x4s_setup(g, BASE): student seat g%2, X-deck g%5 vs
X-deck (g//5)%5, shuffled by Random(BASE+g); opponent = pool[g % len(pool)]. 'self' = the same
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


def check_bank(base, start, games, reserved=((HEADLINE_BASE, 100_000),)):
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
    from bot.players.ours import play_match, x4s_setup
    from bot.players.search import SearchPlayer
    from .label import LabelingPlayer, seal_rows
    case = x4s_setup(rt, g, a.base)
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
            seal_rows(out / 'games' / f'game-{g:07d}-s{s}', p.rows, p.scores, receipt)
        shards[s] = dict(p.counts, outcome=outcome)
    score = 0.5 if w is None or w == -1 else (1.0 if w == seat else 0.0)
    return dict(game=g, seed=case['seed'], seat=seat, opponent=opp, score=score, winner=w,
                terminal=res['terminal'], ticks=res['ticks'], plays=res['plays'], shards=shards,
                command_sha256=res['command_sha256'], cpu_seconds=res['cpu_seconds'],
                wall_seconds=time.time() - t0)


def worker(wid, games, a, out: Path):
    os.environ.setdefault('PYTHONHASHSEED', '0')
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    rt = Runtime()
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
    ap.add_argument('--base', type=int, required=True)
    a = ap.parse_args(argv)
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
    for p in procs:
        p.join()


if __name__ == '__main__':
    main()
