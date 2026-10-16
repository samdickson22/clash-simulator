"""Equivalence check of the deployable `res` token (bot/search/reserve.py) against the sim-tested twin (live-diag).

Arms (each inside bot.live.player.LivePlayer with the rl5 fast tier, deterministic, RoyaleSim 15.535, sim_diag cases):
  A  LD-K4L-R-gs-rw-res                       (bot/livediag/variants.py: source insertion; the A/B'd arm)
  B  K4L-R-gs-rw-res                          (serial lopp.reduce_learned + token)
  C  K4L-R-gs-rw-fc-t4-p4-res                 (deployed reduction lopp_fast.reduce_fast, deterministic: no w)
  D  K4L-R-gs-rw-fc-t4-p4                     (deployed reduction without the token)
  E  LD-K4L-R-gs-rw                           (base twin)
  F  LD-K4L-R-gs-rw-res-rh                    (sim wrapper RecedingHorizon over the -res twin)
  G  K4L-R-gs-rw-fc-t4-p4-res-rh              (deployed reduction + tokens res, rh)
  H  LD-K4L-R-gs-rw-res-wint                  (sim wrapper bot/livediag/variants.Interruptible)
  I  bot/search/interrupt.Interruptible over the deployed reduction + res (the Mac -wint package)
Expected: command_sha256 A == B == C, D == E, F == G and H == I on every case (rw makes chunked/pooled values equal the serial ones).

    python -m bot.livediag.res_equiv --cases 0,1,2 --opponent R3a --base BASE
"""
from __future__ import annotations

import argparse
import json
import random


def _interrupt(rt, live):
    from bot.search.interrupt import Interruptible
    return Interruptible(rt, live)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cases', default='0,1,2')
    ap.add_argument('--opponent', default='R3a')
    ap.add_argument('--base', type=int, required=True)
    ap.add_argument('--arms', default='A,B,C,D,E')
    a = ap.parse_args()
    from bot.players.runtime import Runtime
    from bot.players.royalesim_match import play_match
    from bot.players.royalesim_vocab import load
    from bot.live.player import LivePlayer, FAST_DEFAULT, make_live_player
    from bot.eval.headline import make_player
    from bot.livediag.sim_diag import LIVE_DECK, giant_decks
    from bot.livediag.variants import TwinSearch, make_variant
    rt = Runtime()
    vocab, decks = load(rt), giant_decks(rt)

    def twin(body):
        live = LivePlayer(rt, tier='search', fast_spec=FAST_DEFAULT, cutoff_default='it5s2', name=body)
        live.search = TwinSearch(rt, make_player(rt, body))
        live.deadline_seconds = None
        return live
    arms = dict(A=lambda: make_variant(rt, 'LD-K4L-R-gs-rw-res'), B=lambda: twin('K4L-R-gs-rw-res'),
                C=lambda: twin('K4L-R-gs-rw-fc-t4-p4-res'), D=lambda: twin('K4L-R-gs-rw-fc-t4-p4'),
                E=lambda: make_variant(rt, 'LD-K4L-R-gs-rw'),
                F=lambda: make_variant(rt, 'LD-K4L-R-gs-rw-res-rh'), G=lambda: twin('K4L-R-gs-rw-fc-t4-p4-res-rh'),
                H=lambda: make_variant(rt, 'LD-K4L-R-gs-rw-res-wint'), I=lambda: _interrupt(rt, twin('K4L-R-gs-rw-fc-t4-p4-res')))
    out = {}
    for i in [int(x) for x in a.cases.split(',')]:
        seat = i % 2
        own, other = list(LIVE_DECK), list(decks[(i // 2) % len(decks)])
        rng = random.Random(a.base + i)
        rng.shuffle(own); rng.shuffle(other)
        for k in a.arms.split(','):
            res = play_match(rt, {seat: arms[k](), 1 - seat: make_live_player(rt, a.opponent)}, seed=a.base + i,
                             decks=[own, other] if seat == 0 else [other, own], vocab=vocab)
            out.setdefault(i, {})[k] = res['command_sha256'][:16]
        print(json.dumps({i: out[i]}), flush=True)
    ok = all(v.get('A') == v.get('B') == v.get('C') and v.get('D') == v.get('E') and v.get('F') == v.get('G')
             for v in out.values())
    print(json.dumps(dict(equivalent=ok)))


if __name__ == '__main__':
    main()
