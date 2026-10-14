"""Head to head of two RoyaleLearn/RoyaleImitate policies with royalegym.evaluate (learnvenv, CPU).

Same environment as rext_eval (rext_envs.build_env: X4S decks, level 11, 15.535.29, delay 27/27),
half the games per seat, sampled policies. One process per seed block:

    learnvenv/bin/python -m bot.players.rext_imitate_h2h --a MODEL_A --b MODEL_B --games 50 --seed 1 --out OUT.json
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--a', required=True)
    ap.add_argument('--b', required=True)
    ap.add_argument('--games', type=int, default=50)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    import torch
    torch.set_num_threads(1)
    from royalegym import CallableOpponent, evaluate
    from royalelearn.learner import Bot
    from bot.players.rext_envs import build_env
    bot_a, bot_b = Bot.load(a.a), Bot.load(a.b)
    t0 = time.time()
    res = evaluate(CallableOpponent(lambda obs, mask: bot_a(obs)), CallableOpponent(lambda obs, mask: bot_b(obs)),
                   build_env, games=a.games, seed=a.seed, names=('a', 'b'))
    row = dict(a=a.a, b=a.b, games=a.games, seed=a.seed, wins=res.wins, losses=res.losses, draws=res.draws,
               score=(res.wins + 0.5*res.draws)/max(1, res.wins+res.losses+res.draws), summary=res.summary(),
               seconds=time.time()-t0)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(row, indent=1))
    print(row['summary'])


if __name__ == '__main__':
    main()
