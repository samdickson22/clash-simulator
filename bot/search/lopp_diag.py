"""How often a K4L arm picks another action than K4C-r16's frozen reduction on the same roots (exploration).

    python -m bot.search.lopp_diag --arm K4L-R-gs --cases 0,1,2,3 --opponents R3a,v1 --decisions 60

Plays the arm on HEADLINE cases; at each searched root also runs the frozen 3-style mean reduction
(oppmodel.reduce_scores, weights=None == K4C-r16) and records whether the pre-S-default choice differs,
and whether either picked a play or a wait.
"""
from __future__ import annotations

import argparse
import json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', default='K4L-R-gs')
    ap.add_argument('--cases', default='0,1,2,3')
    ap.add_argument('--opponents', default='R3a,v1')
    ap.add_argument('--decisions', type=int, default=60)
    a = ap.parse_args()
    import torch
    torch.set_num_threads(1)
    from bot.eval.headline import HEADLINE_BASE, make_player
    from bot.players.ours import play_match, x4s_setup
    from bot.players.runtime import Runtime
    from bot.search import lopp
    from bot.search.oppmodel import reduce_scores
    rt = Runtime()
    out = {}

    class Stop(Exception):
        pass

    for opp in a.opponents.split(','):
        st = out.setdefault(opp, dict(roots=0, changed=0, arm_play=0, base_play=0))
        for i in [int(c) for c in a.cases.split(',')]:
            case = x4s_setup(rt, i, HEADLINE_BASE)
            seat = case['seat']
            cand = make_player(rt, a.arm)
            n = [0]
            orig = lopp.reduce_learned

            def wrapped(core, root, s, candidates, arm, **kw):
                if n[0] >= a.decisions:
                    raise Stop
                n[0] += 1
                best, info = orig(core, root, s, candidates, arm, **kw)
                last, stats = core.last, core.deadline_stats
                base, _ = reduce_scores(core, root, s, candidates, None, coarse_order=kw.get('coarse_order', ()),
                                        refine_proposals=kw.get('refine_proposals', ()))
                core.last, core.deadline_stats = last, stats
                st['roots'] += 1
                st['changed'] += int(base != best)
                st['arm_play'] += int(best is not None and best < 2304)
                st['base_play'] += int(base is not None and base < 2304)
                return best, info
            lopp.reduce_learned = wrapped
            try:
                play_match(rt, {seat: cand, 1 - seat: make_player(rt, opp)}, seed=case['seed'], decks=case['decks'])
            except Stop:
                pass
            finally:
                lopp.reduce_learned = orig
    print(json.dumps(out))


if __name__ == '__main__':
    main()
