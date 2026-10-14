"""bot.search.run for the K4O opponent-model arms: same games and cost columns, plus opponent-model diagnostics.

    python -m bot.search.opp_run --out DIR --candidate K4O-min --opponents R3a,v1 --games 300 --workers 48

Extra per-game 'search' fields: changed (fraction of searched decisions where the frozen mean reduction would have
picked another action from the same rollouts; only when all 3 styles were rolled out), weights (mean style weights
over searched decisions, fixed/blend arms), opp_plays (the opponent's public play features [elixir before, depth],
used by the lo/hi blend).
"""
from __future__ import annotations

import bot.search.run as base

_summary = base.search_summary


def search_summary(player, timing):
    out = _summary(player, timing)
    ds = [d for d in getattr(player, 'decisions', []) if d]
    ch = [d['changed'] for d in ds if 'changed' in d]
    if ch:
        out['changed'] = sum(ch)/len(ch)
    ws = [d['weights'] for d in ds if d.get('weights')]
    if ws:
        out['weights'] = [sum(w[k] for w in ws)/len(ws) for k in range(len(ws[0]))]
    if hasattr(player, 'opp_plays'):
        out['opp_plays'] = [[round(v, 3) for v in x] for x in player.opp_plays]
    return out


base.search_summary = search_summary

if __name__ == '__main__':
    base.main()
