"""Diagnostic: how much do the M determinizations differ, per decision? (exploration)

    python -m bot.search.diag_roots --index 0 --opponent R3a --roots 8 --ticks 2400 --out FILE.json

Plays case `index` with K4S-m<roots> and records, per searched decision: the sampled opponent
hands/cycles of every root, the per-root score of every fully scored candidate, the gap between
the best and second-best mean score, and the across-root SD of each candidate's score.
"""
from __future__ import annotations

import argparse
import json

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--index', type=int, default=0)
    ap.add_argument('--opponent', default='R3a')
    ap.add_argument('--roots', type=int, default=8)
    ap.add_argument('--ticks', type=int, default=2400)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    from bot.players.runtime import Runtime
    from bot.players.ours import play_match, x4s_setup
    from bot.eval.headline import HEADLINE_BASE, make_player
    from bot.search import players as sp
    rt = Runtime()
    case = x4s_setup(rt, a.index, HEADLINE_BASE)
    me = make_player(rt, f'K4S-m{a.roots}')
    rows = []
    original = sp.MultiSearchPlayer.act

    def act(self, view):
        R = rt.R
        hands = []
        real_root = R.root

        def spy(info, opponent, rng):
            hands.append(dict(hand=opponent['hand'], cycle=opponent['cycle'], elixir=opponent['elixir']))
            return real_root(info, opponent, rng)
        R.root = spy
        core = getattr(self, 'p', None) and self.p.core
        captured = {}
        if core is not None:
            real_diag = core._diagnostics

            def diag(values, m, chosen):
                captured['values'] = {f'{k[0]}/{k[1]}': v for k, v in values.items()}
                return real_diag(values, m, chosen)
            core._diagnostics = diag
        try:
            d = original(self, view)
        finally:
            R.root = real_root
            if core is not None:
                core._diagnostics = real_diag
        if d.stats and 'values' in captured:
            v = captured['values']
            full = {}
            for key in {k.split('/')[0] for k in v}:
                styles = [v.get(f'{key}/{s}') for s in sp.STYLES]
                if all(styles):
                    full[key] = [sum(x)/3 for x in zip(*styles)]
            means = sorted((np.mean(x) for x in full.values()), reverse=True)
            rows.append(dict(tick=view.tick, chosen=d.action, hands=hands, scores=full,
                             gap=float(means[0]-means[1]) if len(means) > 1 else None,
                             sd_mean=float(np.mean([np.std(x) for x in full.values()])),
                             distinct_hands=len({tuple(sorted(h['hand'])) for h in hands}),
                             distinct_states=len({(tuple(sorted(h['hand'])), tuple(h['cycle'])) for h in hands})))
        return d
    sp.MultiSearchPlayer.act = act
    players = {case['seat']: me, 1-case['seat']: make_player(rt, a.opponent)}
    res = play_match(rt, players, seed=case['seed'], decks=case['decks'], max_ticks=a.ticks)
    summary = dict(decisions=len(rows),
                   median_gap=float(np.median([r['gap'] for r in rows if r['gap'] is not None])),
                   median_sd=float(np.median([r['sd_mean'] for r in rows])),
                   mean_distinct_hands=float(np.mean([r['distinct_hands'] for r in rows])),
                   mean_distinct_states=float(np.mean([r['distinct_states'] for r in rows])),
                   frac_sd_over_gap=float(np.mean([r['sd_mean'] > r['gap'] for r in rows if r['gap'] is not None])),
                   opponent_deck=case['decks'][1-case['seat']], ticks=res['ticks'])
    print(json.dumps(summary, indent=1))
    with open(a.out, 'w') as fh:
        json.dump(dict(summary=summary, rows=rows), fh)


if __name__ == '__main__':
    main()
