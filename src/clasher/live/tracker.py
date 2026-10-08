"""Output-identical acceleration of the frozen S4/S5 tracker.

The frozen source is never patched. Dense resource transitions deliberately keep
NumPy's original operation/reduction order: uniform contamination gives every
lattice cell positive mass, so pruning to sparse support would change semantics.
"""
from collections import deque
from functools import lru_cache
import math
import itertools
import sys
import numpy as np
from .loading import tracker_class
from .lattice import mix

FrozenTrackerV3 = tracker_class()
DerivedD1 = sys.modules['clasher_live_d1'].DerivedD1
VALUES = sys.modules['clasher_live_tracker_v2'].VALUES
N = len(VALUES)
regen = sys.modules['clasher_live_tracker_v2'].regen
shift = sys.modules['clasher_live_tracker_v2'].shift


def add_shift(target, p, units, scale):
    """target += scale*shift(p, units), with identical element operations.

    Zero tails need no addition; capped boundary sums use the original NumPy
    slice reduction and addition order. No sparse probability approximation.
    """
    if units >= N-1:
        target[-1] += scale*p.sum()
    elif units <= -N+1:
        target[0] += scale*p.sum()
    elif units > 0:
        target[units:-1] += scale*p[:-units-1]
        target[-1] += scale*(p[-units-1]+p[-units:].sum())
    elif units < 0:
        k = -units
        target[1:-k] += scale*p[k+1:]
        target[0] += scale*(p[k]+p[:k].sum())
    else:
        target += scale*p


class FastHand(DerivedD1):
    def advance(self, tick):
        if tick < self.tick:
            raise ValueError('public time moved backwards')
        if tick == self.tick:
            return
        # After the first round, every step is an integer lattice operation.
        # Integers <=100000 round-trip through /10000 then *10000 with error
        # <0.5. Keep the original first round and final division exactly.
        if self.elixir < 10.:
            units = self.elixir_units
            for start, end, rate in ((0, 2400, 178), (2400, 4800, 357), (4800, tick, 537)):
                steps = max(0, min(tick, end)-max(self.tick, start))
                units = min(100000, units+steps*rate)
            self.elixir = units/10000.
        cursor = self.tick
        while len(self.queue) > 4 and cursor < tick:
            steps = max(1, (self.refill+49)//50)
            if cursor+steps > tick:
                break
            cursor += steps
            self.queue.popleft()
            self.refill = 1000 if cursor < 2400 else 500 if cursor < 4800 else 350
        self.refill = max(0, self.refill-50*(tick-cursor))
        self.tick = tick


class TrackerV3(FrozenTrackerV3):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._deck_indices = {}
        for i, (deck, _) in enumerate(self.decks):
            for card in deck:
                self._deck_indices.setdefault(card, set()).add(i)
        # Per-instance caches avoid different live episodes evicting each other.
        self.support = lru_cache(maxsize=65536)(self.support)
        self.presence = lru_cache(maxsize=65536)(FrozenTrackerV3.presence.__wrapped__.__get__(self))
        self._eight_card_decks = all(len(deck) == 8 for deck, _ in self.decks)
        self.resolved_options = lru_cache(maxsize=65536)(self.resolved_options)
        # The broad initial/restart hypotheses repeatedly ask about zero, one,
        # two, and three reveals. Warm this finite prior-only work before capture.
        reveals = {()}
        for deck, _ in self.decks:
            cards = sorted(deck)
            reveals.update(itertools.combinations(cards, 1))
            reveals.update(itertools.combinations(cards, 2))
            reveals.update(itertools.combinations(cards, 3))
        for revealed in sorted(reveals, key=lambda r: (len(r), r)):
            self.presence(revealed)
        self._cycle_cache = {}
        self._cdf_p = None
        self._cdf = None
        self._weight_hands = None
        self._weights = None

    def support(self, revealed):
        if not revealed:
            decks = self.decks
        else:
            sets = [self._deck_indices.get(card, set()) for card in revealed]
            indices = set.intersection(*sets)
            # Original deck iteration order is essential for bit-exact sums.
            decks = [self.decks[i] for i in sorted(indices)]
        z = sum(w for _, w in decks)
        return tuple((d, w/z) for d, w in decks) if z else ()

    def resolved_options(self, queue, revealed):
        unknown = queue.count(None)
        # Every compatible deck contains all reveals. The frozen loop rejects
        # every deck when this cardinality cannot match; avoid enumerating it.
        if self._eight_card_decks and unknown and unknown != 8-len(set(revealed)):
            return ()
        return FrozenTrackerV3.resolved_options.__wrapped__(self, queue, revealed)

    def accept_cycle(self, d, name, tick):
        x = d
        if tick > d.tick:
            x = self._clone_hand(d)
            x.advance(tick)
        p = self.availability(x, name)
        if not p:
            return None, 0.
        if x is d:
            x = self._clone_hand(d)
        x.elixir = 10.
        try:
            x.accept(sys.modules['clasher_live_d1'].PublicEvent(x.tick, 'card', name))
        except (ValueError, KeyError):
            return None, 0.
        return x, p

    def _transition(self, p, a, b):
        if b <= a:
            return p
        out = shift(p, regen(a, b))
        play_rate = (self.n_events+4)/max(20., b/20.*max(.1, self.recall))
        hazard = min(.25, play_rate*self.miss*.25*(b-a)/20.)
        reset = 1-math.exp(-.0005*(b-a)/20.)
        if hazard:
            native = mix(out, [(-cost, prob) for cost, prob in self.cost_prior.items()],
                         1-hazard, hazard, 1-reset, reset/N)
            if native is not None:
                return native
            latent = np.zeros(N)
            for cost, prob in self.cost_prior.items():
                add_shift(latent, out, -cost, prob)
            out = (1-hazard)*out+hazard*latent
        reset = 1-math.exp(-.0005*(b-a)/20.)
        return (1-reset)*out+reset/N

    def _resource_event(self, p, e):
        p = .998*p+.002/N
        components = []
        for name, prob in e.cards:
            cost = round((self.costs.get(name, 0.) if e.kind == 'card' else e.amount)*10000)
            if e.kind == 'collector':
                components.append((cost, prob))
            elif 0 <= cost < N:
                jitter = regen(e.tick, e.tick+4)
                for delta, weight in ((-jitter, .25), (0, .5), (jitter, .25)):
                    effective = max(0, cost-delta)
                    if effective >= N:
                        continue
                    components.append((-effective, prob*weight))
        out = mix(p, components, 1-e.q, e.q)
        if out is None:
            accepted = np.zeros(N)
            for units, weight in components:
                add_shift(accepted, p, units, weight)
            out = (1-e.q)*p+e.q*accepted
        total = out.sum()
        if total <= 0:
            return np.full(N, 1/N)
        return out/total

    def _clone_hand(self, d):
        x = FastHand.__new__(FastHand)
        x.__dict__ = d.__dict__.copy()
        x.queue = deque(d.queue)
        x.revealed = set(d.revealed)
        x.events = []
        x.plays = deque(d.plays, maxlen=8)
        x.abilities = deque(d.abilities, maxlen=8)
        return x

    def _hands_event(self, hands, e):
        # Fixed-lag replay repeatedly applies an identical cue to identical
        # hypotheses. Include mutable cue contents and event-count hazard.
        key = (id(hands), self.n_events, e.tick, tuple((n, p) for n, p in e.cards), e.q, e.kind, e.amount)
        cached = self._cycle_cache.get(key)
        if cached is not None:
            return cached[1]
        result = super()._hands_event(hands, e)
        if len(self._cycle_cache) >= 128:
            self._cycle_cache.clear()
        # Retain input identity, preventing id reuse; consumers only clone it.
        self._cycle_cache[key] = (hands, result)
        return result

    def resource_cdf(self):
        if self._cdf_p is not self._p:
            self._cdf_p = self._p
            self._cdf = np.cumsum(self._p)
        return self._cdf

    def distribution(self):
        if self.perfect:
            return super().distribution()
        if self._distribution is not None:
            return self._distribution
        p = self._p
        cdf = self.resource_cdf()
        def q(x):
            return min(N-1, int(np.searchsorted(cdf, x)))/10000.
        lo, hi = max(0., q(.05)-self.calibration), min(10., q(.95)+self.calibration)
        # V3 overwrites V2's hand summaries, so omit only that dead computation.
        masses = self.hand_masses()
        best, raw = max(masses.items(), key=lambda x: x[1], default=(None, 0.))
        last = max((x.tick for x, _ in self._hands), default=0)
        rate = (self.n_events+4)/max(20., self.tick/20.*max(.1, self.recall))
        mass = raw*math.exp(-rate*self.miss*max(0, self.tick-last)/20.)
        if self.hand_calibration:
            edges = self.hand_calibration['edges']
            values = self.hand_calibration['values']
            mass = float(values[min(len(values)-1, int(np.searchsorted(edges, mass, side='right')))])
        self._distribution = dict(elixir_mean=float(np.dot(p, VALUES)), elixir_interval_90=[lo, hi],
            elixir_q90=q(.9), hand=best if mass >= .9 else None, hand90=best if mass >= .9 else None,
            hand90_mass=mass, concentrated=mass >= .9, hypotheses=len(self._hands),
            fallback_mass=float(self._hands[-1][1]), resource_support=int(np.count_nonzero(p)),
            best_hand=best, raw_hand_mass=raw)
        return self._distribution

    def sample(self, rng):
        if self.perfect:
            return super().sample(rng)
        if self._weight_hands is not self._hands:
            self._weight_hands = self._hands
            self._weights = np.array([w for _, w in self._hands])
            self._weights /= self._weights.sum()
        weights = self._weights
        d = self._clone_hand(self._hands[int(rng.choice(len(weights), p=weights))][0])
        d.advance(self.tick)
        support = self.support(tuple(sorted(d.revealed)))
        if not support:
            d = FastHand(self.costs)
            d.advance(self.tick)
            support = self.support(())
        deck, prob = support[int(rng.choice(len(support), p=[w for _, w in support]))]
        unknown = sorted(deck-d.revealed)
        rng.shuffle(unknown)
        queue = [n if n is not None else unknown.pop() for n in d.queue]
        hand = sorted(deck-set(queue))+[None]*(len(queue)-4)
        elixir = min(N-1, int(np.searchsorted(self.resource_cdf(), rng.random())))/10000.
        return dict(hand=hand, cycle=queue, refill=d.refill, elixir=elixir)
