"""Deck-constrained own-hand read (applied in drive.py before LiveSession.step).

Perception's HUD head scores all 56 cards per hand slot + next; the record keeps only the argmax. Our hand can only hold
our 8 deck cards, all distinct. With Sam's 10-16 deck the argmax broke the live loop: Cannon reads as GoblinBarrel and
Valkyrie at p .2-.5 (greyed / unaffordable cards are misread too), so LiveSession never saw an opening hand of 4 distinct
deck cards and sat out a whole battle (s14-m04: opening_hand_waits = 401, 0 decisions). Here the 4 slots + next get the
jointly most probable DISTINCT deck cards (max sum of log-probabilities over all 8P5 = 6720 assignments). A slot whose
'empty' class (index >= len(cards)) is more probable than every deck card stays empty (refill in progress).
"""
import itertools
import math
from numbers import Real
from collections.abc import Mapping

import numpy as np

_PERMS = {}


def _perms(k):
    if k not in _PERMS:
        _PERMS[k] = np.array(list(itertools.permutations(range(k), 5)), np.int64)
    return _PERMS[k]


def deck_constrained(logits, cards, deck, *, ui=None, costs=None):
    """logits: [5, C] HUD card logits (slots 0-3, next). -> dict(cards=[4], probs=[4], next, next_prob) restricted to the
    deck (distinct), plus 'raw' argmax names for the log. Optional ui+costs require one shared balance to explain
    coloured/greyed cards. Probabilities remain full-softmax, never boosted by the constraint; malformed or
    impossible UI/cost inputs return an explicitly unverified hand. No UI+costs is the unchanged legacy decoder."""
    lg = np.asarray(logits, np.float64)
    p = np.exp(lg - lg.max(-1, keepdims=True)); p /= p.sum(-1, keepdims=True)
    idx = [cards.index(c) for c in deck if c in cards]
    names = [c for c in deck if c in cards]
    raw = [cards[i] if i < len(cards) else None for i in p.argmax(-1)]
    if len(idx) < 5:
        return None
    sub = np.log(p[:, idx] + 1e-12)                       # [5, k]
    P = _perms(len(idx))
    score = sub[np.arange(5)[None, :], P].sum(1)
    constrained = ui is not None or costs is not None
    if constrained:
        # One client elixir balance must explain ALL visible affordability states. A coloured cost-4 card
        # cannot coexist with a greyed cost-4 card; empty/refilling slots and Next supply no cost evidence.
        valid = (isinstance(ui, (list, tuple)) and len(ui) == 4 and
                 all(u in ('coloured', 'greyed', 'empty') for u in ui) and isinstance(costs, Mapping))
        prices = [costs.get(n) for n in names] if valid else []
        valid = valid and all(isinstance(c, Real) and not isinstance(c, bool) and math.isfinite(c)
                              and 0 <= c <= 10 for c in prices)
        if valid:
            candidate_cost = np.asarray(prices, dtype=np.float64)[P[:, :4]]
            lower = np.max(np.where(np.asarray(ui) == 'coloured', candidate_cost, 0.), axis=1)
            upper = np.min(np.where(np.asarray(ui) == 'greyed', candidate_cost, np.inf), axis=1)
            eligible = lower < upper
        else:
            eligible = np.zeros(len(P), dtype=bool)
        if not eligible.any():
            return dict(cards=[None]*4, probs=[0.]*4, next=None, next_prob=0., raw=raw,
                        ui_consistent=False)
        score = np.where(eligible, score, -np.inf)
    best = P[int(score.argmax())]
    chosen = [names[j] for j in best]
    probs = [float(p[i, idx[j]]) for i, j in enumerate(best)]
    if lg.shape[1] > len(cards):                          # an 'empty' class: keep an obviously empty slot empty
        empty = p[:, len(cards):].sum(-1)
        for i in range(4):
            if empty[i] > max(probs[i], .5):
                chosen[i], probs[i] = None, float(empty[i])
    return dict(cards=chosen[:4], probs=[round(x, 4) for x in probs[:4]], next=chosen[4], next_prob=round(probs[4], 4),
                raw=raw, **({'ui_consistent': True} if constrained else {}))
