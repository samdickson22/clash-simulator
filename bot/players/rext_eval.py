"""RoyaleGym's own evaluation of a RoyaleLearn policy vs RoyaleGym's scripted ladder (learnvenv).

royalegym.evaluate(bot, opponent, rext_envs.build_env, games, seed): the training environment
(X4S decks, level 11, 15.535.29 arms, engine delay 27/27), half the games in each seat, the same
seeds both ways round. The bot is RoyaleLearn's Learner.load_policy loader (sampled, as trained).
One opponent per process (--opponent), CPU, one torch thread:

    learnvenv/bin/python -m bot.players.rext_eval --model CKPT --opponent patient --games 60 --out OUT.json
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--opponent', required=True, help='noop|random|first-affordable|defend|push|patient')
    ap.add_argument('--games', type=int, default=60)
    ap.add_argument('--seed', type=int, default=777)
    ap.add_argument('--greedy', action='store_true')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    import torch
    torch.set_num_threads(1)
    from royalegym import CallableOpponent, evaluate, ladder
    from royalelearn.learner import Bot
    from bot.players.rext_envs import build_env
    bot = Bot.load(a.model, greedy=a.greedy)
    opp = dict(ladder())[a.opponent]
    t0 = time.time()
    res = evaluate(CallableOpponent(lambda obs, mask: bot(obs)), opp, build_env, games=a.games, seed=a.seed,
                   names=('rlppo', a.opponent))
    seats = [dict(seat=s.seat, wins=s.wins, losses=s.losses, draws=s.draws, undecided=s.undecided) for s in res.by_seat]
    wins, losses, draws = res.wins, res.losses, res.draws
    row = dict(model=a.model, opponent=a.opponent, games=a.games, seed=a.seed, greedy=a.greedy, seats=seats,
               wins=wins, losses=losses, draws=draws, score=(wins + 0.5*draws)/max(1, wins+losses+draws),
               undecided=res.undecided, mean_ticks=res.mean_ticks, mean_crown_margin=res.mean_crown_margin,
               summary=res.summary(), seconds=time.time()-t0)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(row, indent=1))
    print(row['summary'])


if __name__ == '__main__':
    main()
