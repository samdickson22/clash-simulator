"""Own non-C56 hand under the widened R.bots: per hand slot, legal tiles in the Python v5 mask, in the native public
mask of R.root, and the scripted styles' ranked plays (Python R.bots and native select_action).

    CLASHER_BOT_RUNTIME=<root> CLASHER_BOT_RUNTIME_PINS=r1-cards1 python own_probe.py [DECK=M1]
"""
import json
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    from bot.players.runtime import Runtime
    rt = Runtime()
    from fair_player import observe
    from stage2_matches import battle
    from clasher.rl.public_action_mask import PublicActionMaskInput
    from noncore_matches import DECKS
    R = rt.R
    deck = DECKS[sys.argv[1] if len(sys.argv) > 1 else 'M1']
    other = list(rt.x4s_decks()[1])
    out = []
    for rot in range(2):                      # two hand orders: every M1 card is in hand once
        mine = deck[4 * rot:] + deck[:4 * rot]
        b = battle(dict(seed=7 + rot, decks=[mine, other]), R.builder.loader)
        for _ in range(100):
            b.step()
        b.players[0].elixir = 10.
        info = observe(b, R.builder, 0, [])
        mask = R.bots['balanced'].mask_builder.build(PublicActionMaskInput.from_confidence_observation(info.packet))
        opp = dict(elixir=b.players[1].elixir, hand=list(b.players[1].hand), cycle=list(b.players[1].cycle_queue),
                   refill=b.players[1].next_card_refill_cooldown_ms)
        root = R.root(info, opp, np.random.default_rng(1))
        nmask = list(R.native.public_mask(root, 0))
        ranked = {st: [(int(d.action_id), d.reason) for d in bot._ranked_actions(info.packet)[:3]]
                  for st, bot in R.bots.items()}
        native = {st: int(R.native.select_action(root.clone(), 0, st)) for st in ('balanced', 'pressure', 'defense')}
        hand = info.own['hand']
        for slot, card in enumerate(hand[:4]):
            out.append(dict(card=card, python_mask=int(mask[slot * 576:(slot + 1) * 576].sum()),
                            native_mask=int(sum(nmask[slot * 576:(slot + 1) * 576])),
                            scripted_top3=[st for st, r in ranked.items() if any(a < 2304 and a // 576 == slot for a, _ in r)],
                            native_pick=[st for st, a in native.items() if a < 2304 and a // 576 == slot]))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
