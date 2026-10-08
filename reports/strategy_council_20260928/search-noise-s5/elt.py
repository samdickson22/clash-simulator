"""Event-ledger beam with exact finite deck/order support inside each branch.

Inputs contain public event candidates only. No battle, opponent state, or
simulator RNG is accepted. Array ownership is copy-on-write at branch updates.
"""
import bootstrap
import copy
import hashlib
import math
from dataclasses import dataclass
import numpy as np
from derived_public_state import DerivedPublicState, PublicEvent


@dataclass(frozen=True)
class Candidate:
    tick: int
    cards: tuple
    q: float
    sigma: int = 0
    kind: str = 'card'
    amount: float = 0.

    def __post_init__(self):
        if not 0 <= self.q <= 1 or self.tick < 0 or self.sigma < 0:
            raise ValueError('invalid event candidate')
        if not self.cards or any(p <= 0 for _, p in self.cards):
            raise ValueError('empty or invalid card distribution')
        if abs(sum(p for _, p in self.cards) - 1) > 1e-8:
            raise ValueError('card probabilities must sum to one')


@dataclass
class Hypothesis:
    state: object
    log_weight: float
    missed: int = 0


def clone(state):
    out = copy.copy(state)
    out.states = state.states.copy() if state.queue_len > 4 else state.states
    # weights/cumulative never mutate in-place in exact derivation.
    out.events = list(state.events)
    return out


def elixir_at(state, tick):
    if tick < state.tick:raise ValueError('public time moved backwards')
    if tick == state.tick:return state.elixir
    units=round(state.elixir*10000)
    start=state.tick
    for end,rate in ((2400,2.8),(4800,1.4),(tick,.93)):
        stop=min(tick,end)
        if stop>start:
            units=min(100000,units+(stop-start)*int(500/rate));start=stop
    return units/10000


def apply(state, event):
    cost = state.costs.get(event.name) if event.kind == 'card' else event.amount
    # Reject impossible spends before copying potentially millions of deck orders.
    if event.kind != 'collector' and (cost is None or elixir_at(state,event.tick) + 1e-9 < cost):
        return None
    out = clone(state)
    try:
        out.update(event.tick, out.events + [event])
    except (ValueError, KeyError, IndexError):
        return None
    return out


class ELT:
    def __init__(self, prior, costs, *, beam=128, missed_rate=.08010294255078579, initial=None):
        if beam < 1 or not 0 <= missed_rate <= 1:
            raise ValueError('invalid beam or missed rate')
        self.hypotheses = [Hypothesis(initial or DerivedPublicState(prior, costs), 0.)]
        self.beam = beam
        self.missed_rate = missed_rate
        self.tick = 0
        self.candidates = []
        self._projected = None

    def observe(self, candidate):
        if self.candidates and candidate.tick < self.candidates[-1].tick:
            raise ValueError('execution estimates must be monotonic')
        branches = []
        top = sorted(candidate.cards, key=lambda x: -x[1])[:2]
        top = [pair for i, pair in enumerate(top) if i == 0 or pair[1] >= .15]
        for h in self.hypotheses:
            if candidate.q < 1:
                branches.append(Hypothesis(h.state, h.log_weight + math.log1p(-candidate.q), h.missed))
            if candidate.q == 0:
                continue
            for name, probability in top:
                # Three-point timing quadrature within the supplied uncertainty.
                times = sorted({max(h.state.tick, candidate.tick + d) for d in
                                ((-candidate.sigma, 0, candidate.sigma) if candidate.sigma else (0,))})
                accepted = False
                for t in times:
                    likelihood = math.exp(-.5*((t-candidate.tick)/max(1, candidate.sigma))**2)
                    e = PublicEvent(t, candidate.kind, name, candidate.amount)
                    out = apply(h.state, e)
                    if out is not None:
                        branches.append(Hypothesis(out, h.log_weight + math.log(candidate.q*probability*likelihood/len(times)), h.missed))
                        accepted = True
                # A missed play can repair a cycle contradiction, never a resource deficit.
                # Try one latent play in the preceding public-event gap; no truth timing.
                affordable = candidate.kind == 'collector' or elixir_at(h.state,max(h.state.tick,candidate.tick)) + 1e-9 >= (h.state.costs.get(name,float('inf')) if candidate.kind=='card' else candidate.amount)
                in_deck = not accepted and affordable and (candidate.kind != 'card' or name in h.state.ids and np.any(h.state.states==h.state.ids[name]))
                if not accepted and affordable and in_deck and self.missed_rate > 0 and candidate.q < 1:
                    t = max(h.state.tick, candidate.tick - 20)
                    possible = sorted(set(int(x) for x in h.state.states[:, :4].ravel()) - {0})
                    for card in possible:
                        latent = apply(h.state, PublicEvent(t, 'card', h.state.names[card-1]))
                        if latent is None:
                            continue
                        out = apply(latent, PublicEvent(max(t, candidate.tick), candidate.kind, name, candidate.amount))
                        if out is not None:
                            branches.append(Hypothesis(out, h.log_weight + math.log(candidate.q*probability*self.missed_rate/max(1,len(possible))), h.missed+1))
        if not branches:
            raise ValueError('no possible event hypothesis')
        merged = {}
        for h in branches:
            s = h.state
            # Equal support, exact resource ledger and refill clock imply equal future state.
            key = (s.tick, round(s.elixir*10000), s.refill, s.queue_len,
                   hashlib.sha256(s.states).digest(), hashlib.sha256(s.weights).digest())
            if key in merged:
                merged[key].log_weight = float(np.logaddexp(merged[key].log_weight, h.log_weight))
            else:
                merged[key] = h
        self.hypotheses = sorted(merged.values(), key=lambda h: -h.log_weight)[:self.beam]
        z = float(np.logaddexp.reduce([h.log_weight for h in self.hypotheses]))
        for h in self.hypotheses:
            h.log_weight -= z
        self.candidates.append(candidate)
        self.tick = max(self.tick, candidate.tick)
        self._projected = None

    def advance(self, tick):
        if tick < self.tick:
            raise ValueError('public time moved backwards')
        self.tick = tick
        self._projected = None

    def projected(self):
        if self._projected is None:
            self._projected = []
            for h in self.hypotheses:
                s = clone(h.state)
                s.advance(max(self.tick, s.tick))
                self._projected.append(s)
        return self._projected

    @property
    def weights(self):
        return np.exp([h.log_weight for h in self.hypotheses])

    def distribution(self):
        states = self.projected()
        weights = self.weights
        values = np.array([s.elixir for s in states])
        order = np.argsort(values)
        cdf = np.cumsum(weights[order])
        quantile = lambda q: float(values[order[min(len(order)-1,int(np.searchsorted(cdf,q)))]] )
        known = [s.derived()['hand'] for s in states]
        hand = known[0] if known[0] is not None and all(x == known[0] for x in known) else None
        return dict(elixir_mean=float(weights@values), elixir_interval_90=[quantile(.05),quantile(.95)],
                    elixir_q90=quantile(.9), hand=hand, concentrated=bool(weights.max()>=.9),
                    hypotheses=len(states))

    def roots(self, rng, k=1, pessimistic=False):
        weights = self.weights
        states = self.projected()
        cdf = np.cumsum(weights)
        if weights.max() >= .9:
            indices = [int(np.argmax(weights))]*k
        else:
            indices = [min(len(states)-1,int(np.searchsorted(cdf,(j+rng.random())/k))) for j in range(k)]
        roots = [states[i].sample(rng) for i in indices]
        if pessimistic:
            order = np.argsort([s.elixir for s in states])
            i = int(order[min(len(order)-1,int(np.searchsorted(np.cumsum(weights[order]),.9)))])
            roots.append(states[i].sample(rng))
        return roots

    def marginals(self):
        """Weighted hand presence and ordered-cycle probabilities, on demand."""
        hand={};cycle={}
        for state,mass in zip(self.projected(),self.weights):
            weights=state.weights/state.weights.sum()*mass
            for card in np.unique(state.states):
                if card==0:continue
                name=state.names[int(card)-1]
                hand[name]=hand.get(name,0.)+float(weights@np.any(state.states[:,:4]==card,axis=1))
                for pos in range(state.queue_len):
                    key=(pos,name)
                    cycle[key]=cycle.get(key,0.)+float(weights@(state.states[:,4+pos]==card))
        return dict(hand=hand,cycle=cycle)

    def sample(self, rng):
        return self.roots(rng)[0]
