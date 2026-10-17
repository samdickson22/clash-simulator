"""Planner-levels re-test on our engine (bot/levels/match.py; BOT LEAD queue 2026-10-17). Exploration.

    python -m bot.fullpool.levels_ab --out DIR --base BASE --games 100 --workers 24 [--opponents K4C-r16,R3a]
    python -m bot.fullpool.levels_ab --summary DIR

Question: does the live player plan better at the TRUE levels than at the all-L11 assumption, when the game is
played at the true levels?
- Truth: our engine at per-seat levels. Ours = the account collection (COLLECTION, deck worker's collection-final.json,
  sha256 264def71...; read once, copied into the row), opponent = bot.levels.profile.sample_opponent (Battle Log level
  prior, drawn per case with Random(seed ^ 0x1e7e1), so both arms see the same opponent levels), King towers 7 both.
- Cases: banks.case 'e16bl' (our e16 deck, all of whose cards are in the collection, vs a LIVE Battle Log deck; seat
  i % 2), fresh BASE (check_bank); opponents K4C-r16 and R3a, the same case indices for both arms.
- Arms: our player PLAYER (default K4L-R-gs-mk1a1, the bundle's serial twin) with planner 'l11' vs 'exact'. The
  opponent's planner is fixed at L11 in both arms (install_planner is limited to our seat), so only ours changes.
Rows: games-<w>.jsonl (arm, opponent, index, seat, score, ticks, towers, levels tag, planners, command_sha256).
Summary: per opponent and pooled, mean score per arm and paired exact - l11 with a 95% bootstrap CI.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import time
from multiprocessing import Process
from pathlib import Path

COLLECTION = Path(os.environ.get('BOT_COLLECTION', '/mpac/sdicks02/jobs/clasher/bot-deckopt2/collection-final.json'))
PLAYER = os.environ.get('LEVELS_AB_PLAYER', 'K4L-R-gs-mk1a1')
KING = 7


def own_levels():
    d = json.loads(COLLECTION.read_text())
    return {k: int(v['level']) for k, v in d.items() if k != '_account'}


def worker(wid, jobs, out, base):
    os.environ.setdefault('PYTHONHASHSEED', '0')
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    from bot.players.ours import play_match
    from bot.eval.headline import make_player
    from bot.fullpool.banks import case as make_case, select
    from bot.fullpool.models import install_from_env
    from bot.levels.profile import sample_opponent
    import bot.levels.match as lm
    rt = Runtime()
    install_from_env(rt)
    select(rt, 'e16bl')
    mine = own_levels()
    orig_install = lm.install_planner
    fh = open(out / f'games-{wid:03d}.jsonl', 'a')
    for arm, opp, i in jobs:
        c = make_case(rt, i, base, 'e16bl')
        seat = c['seat']
        t0 = time.time()
        try:
            own_deck, opp_deck = c['decks'][seat], c['decks'][1 - seat]
            opp_lv = sample_opponent(rt, opp_deck, random.Random(c['seed'] ^ 0x1e7e1))
            levels = dict(cards={seat: {k: mine[k] for k in own_deck}, 1 - seat: opp_lv}, towers={0: KING, 1: KING},
                          planner=arm)
            lm.install_planner = (lambda rt_, player, s, spec, _seat=seat:
                                  orig_install(rt_, player, s, spec) if s == _seat else 'l11 (opponent fixed)')
            players = {seat: make_player(rt, PLAYER), 1 - seat: make_player(rt, opp)}
            res = play_match(rt, players, seed=c['seed'], decks=c['decks'], levels=levels)
            w = res['winner']
            score = 0.5 if w is None or w == -1 else (1.0 if w == seat else 0.0)
            row = dict(arm=arm, player=PLAYER, opponent=opp, index=i, seat=seat, seed=c['seed'], score=score, winner=w,
                       ticks=res['ticks'], towers=res['towers'], levels=res['levels']['tag'],
                       planners=res['levels']['planners'], own_levels=levels['cards'][seat], opp_levels=opp_lv,
                       command_sha256=res['command_sha256'], wall_seconds=round(time.time() - t0, 1))
        except Exception as ex:
            import traceback
            row = dict(arm=arm, opponent=opp, index=i, seat=seat, error=repr(ex)[:400], tb=traceback.format_exc()[-1200:])
        finally:
            lm.install_planner = orig_install
        fh.write(json.dumps(row) + '\n'); fh.flush()


def summary(out):
    import glob
    rows = {}
    for p in glob.glob(f'{out}/games-*.jsonl'):
        for line in open(p):
            r = json.loads(line)
            if 'error' not in r:
                rows[(r['arm'], r['opponent'], r['index'])] = r['score']

    def ci(d, n=10000):
        rng = random.Random(0); m = sum(d) / len(d)
        bs = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(n))
        return [round(m, 4), round(bs[250], 4), round(bs[9749], 4)]
    opps = sorted({k[1] for k in rows})
    for o in opps + ['pooled']:
        keys = [(op, i) for (a, op, i) in rows if a == 'l11' and ('exact', op, i) in rows and (o == 'pooled' or op == o)]
        if not keys:
            continue
        d = [rows[('exact',) + k] - rows[('l11',) + k] for k in keys]
        print(json.dumps(dict(opponent=o, n=len(keys), l11=round(sum(rows[('l11',) + k] for k in keys) / len(keys), 4),
                              exact=round(sum(rows[('exact',) + k] for k in keys) / len(keys), 4),
                              exact_minus_l11=ci(d))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path)
    ap.add_argument('--base', type=int)
    ap.add_argument('--games', type=int, default=100)
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--workers', type=int, default=24)
    ap.add_argument('--opponents', default='K4C-r16,R3a')
    ap.add_argument('--summary', type=Path)
    a = ap.parse_args()
    if a.summary:
        return summary(a.summary)
    from bot.exit.generate import check_bank
    check_bank(a.base, a.start, a.games)
    a.out.mkdir(parents=True, exist_ok=True)
    done = set()
    for p in a.out.glob('games-*.jsonl'):
        for line in p.read_text().splitlines():
            try:
                r = json.loads(line)
                if 'error' not in r:
                    done.add((r['arm'], r['opponent'], r['index']))
            except ValueError:
                pass
    jobs = [(arm, o, i) for o in a.opponents.split(',') for i in range(a.start, a.start + a.games)
            for arm in ('l11', 'exact') if (arm, o, i) not in done]
    (a.out / 'launch.json').write_text(json.dumps(dict(args={k: str(v) for k, v in vars(a).items()}, player=PLAYER,
                                                       collection=str(COLLECTION), jobs=len(jobs))))
    procs = [Process(target=worker, args=(w, jobs[w::a.workers], a.out, a.base)) for w in range(a.workers)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    bad = [p.exitcode for p in procs if p.exitcode]
    if bad:
        raise SystemExit(f'{len(bad)} worker process(es) failed, exit codes {bad[:8]}')


if __name__ == '__main__':
    main()
