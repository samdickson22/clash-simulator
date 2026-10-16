"""Full-pool opponent belief: the frozen s1 Belief over decks from the full-pool sampler, open world (exploration).

The frozen belief (derived_public_state.DerivedPublicState via s1/belief.Belief) enumerates every prior deck x 1680
hand/queue orders and filters them by the opponent's public plays. Its prior is the C56 human deck catalog
(rt.PRIOR, 2925 decks of the 56 only), so the first non-C56 reveal raises 'no train deck/order...' (closed world).

Here the prior is N decks of the full-pool sampler (bot/fullpool/decks.py, the public card-frequency meta, never
the opponent's actual deck: fair information). When no prior deck is consistent with the public plays, the prior is
rebuilt as N sampler decks that CONTAIN every revealed card (rng keyed by the spec and the revealed set, so the
rebuild is deterministic), and the event history is replayed (as bot/live/player.py LiveBelief does with catalog
completions). Selection: rt.belief_prior or env BOT_BELIEF_PRIOR = 'fullpool:<seed>[...]' (any deck spec);
unset or 'c56' = rt.PRIOR and the frozen class, i.e. today's search bit for bit.
"""
from __future__ import annotations

import os
import time

N_DECKS = 400
_CACHE: dict = {}


def prior_decks(sampler, n=N_DECKS, require=()):
    """{'decks': [{'cards', 'frequency'}]} from n sampler draws (duplicates merged), sorted for determinism."""
    salt = 'belief|' + '|'.join(sorted(require))
    counts = {}
    for i in range(n):
        deck = tuple(sampler.deck(i, salt=salt, require=sorted(require)))
        counts[deck] = counts.get(deck, 0) + 1
    return dict(decks=[dict(cards=list(k), frequency=float(v)) for k, v in sorted(counts.items())])


def belief_spec(rt):
    spec = getattr(rt, 'belief_prior', None) or os.environ.get('BOT_BELIEF_PRIOR') or 'c56'
    return spec


def planner_belief(rt, base):
    """(prior, belief class) for fair_player.PublicPlanner(R, prior, seed); p.belief.__class__ = class."""
    spec = belief_spec(rt)
    if spec == 'c56':
        return rt.PRIOR, base
    key = (spec, base)
    if key not in _CACHE:
        from bot.fullpool.decks import Sampler
        sampler = Sampler.from_spec(spec)
        _CACHE[key] = (prior_decks(sampler), fullpool_belief_class(base, sampler))
    return _CACHE[key]


def fullpool_belief_class(base, sampler, n=N_DECKS):
    class FullPoolBelief(base):
        rebuilds = 0

        def update(self, tick, events, *, deadline=None, clock=time.monotonic):
            try:
                return super().update(tick, events, deadline=deadline, clock=clock)
            except ValueError as ex:
                if 'no train deck' not in str(ex):
                    raise
            self._pending = None
            revealed = list(dict.fromkeys(e.name for e in events if e.kind == 'card'))
            prior = prior_decks(sampler, n, require=revealed)
            rebuilds = self.rebuilds + 1
            frozen = next(c for c in base.__mro__ if c.__name__ == 'DerivedPublicState')
            frozen.__init__(self, prior, self.costs)
            self.rebuilds = rebuilds
            return super().update(tick, events)

    FullPoolBelief.sampler = sampler
    return FullPoolBelief
