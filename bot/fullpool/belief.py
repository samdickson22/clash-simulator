"""Full-pool opponent belief: the frozen s1 Belief over decks from the full-pool sampler, open world (exploration).

The frozen belief (derived_public_state.DerivedPublicState via s1/belief.Belief) enumerates every prior deck x 1680
hand/queue orders and filters them by the opponent's public plays. Its prior is the C56 human deck catalog
(rt.PRIOR, 2925 decks of the 56 only), so the first non-C56 reveal raises 'no train deck/order...' (closed world).

Here the prior is N decks of the full-pool sampler (bot/fullpool/decks.py, the public card-frequency meta, never
the opponent's actual deck: fair information). When no prior deck is consistent with the public plays, the prior is
rebuilt as N sampler decks that CONTAIN every revealed card (rng keyed by the spec and the revealed set, so the
rebuild is deterministic), and the event history is replayed (as bot/live/player.py LiveBelief does with catalog
completions). Selection: rt.belief_prior or env BOT_BELIEF_PRIOR = 'fullpool:<seed>[...]' (any deck spec);
'c56' (explicit, beats the env var) or unset = rt.PRIOR and the frozen class, i.e. today's search bit for bit.

Open-world layer (`open_world_class`, shared by FullPoolBelief and the C56 LiveBelief; cards/belief-robust):
- Card names. A play whose name the belief cannot encode (not in its costs) is resolved to a known card when an
  alias exists (bot/fullpool/cards.engine_name: display / vocab / Battle Log spellings, evolution and hero names);
  otherwise it becomes a revealed UNKNOWN '~<name>' that occupies one deck slot and cycles like any card, at the
  meta's weighted mean elixir cost. The search never sees '~' names: sample() substitutes, per sampled row, the
  most frequent known non-champion card of the nearest cost that the row does not hold. A certain play that cannot
  be in one deck with the cards already revealed (a 9th distinct card, a 2nd champion) is dropped from the belief's
  stream (perception noise; counted in `dropped`). The mapping depends only on earlier events, so the canonical
  stream stays append-only. Streams of known names within those limits pass through unchanged (same object).
- Rebuild under a decision deadline. With deadline=None the rebuild is today's synchronous code (fixed-timing
  command hashes unchanged). With a deadline, the rebuild is a resumable job (prior draws, state construction and
  history replay in small chunks; priors cached per revealed set) that may use a share of the time left to the
  deadline (BOT_BELIEF_REBUILD_SHARE, default 0.5: ~96 ms of a 192 ms Mac decision, where a rebuild costs ~75 ms;
  the whole rebuild at a 2 s replay deadline; at least 20 ms, never past the deadline). If it is unfinished, the
  decision keeps the previous posterior (`stale` = True: the search samples it instead of falling back to the
  default) and the job resumes on the next decision. The finished job equals the synchronous rebuild (bot/fullpool/test_belief_robust.py).
"""
from __future__ import annotations

import copy
import itertools
import os
import time
from collections import OrderedDict
from dataclasses import replace

import numpy as np

N_DECKS = 400
NO_DECK = 'no train deck'
UNKNOWN = '~'            # prefix of unknown-card names: sorts after every engine name, so known card ids never move
VARIANTS = ('evolution', 'evolved', 'evo', 'hero')    # evolution / hero spellings of a base card
REBUILD_SHARE = 0.5      # default share of the time left to the decision deadline a rebuild may use
REBUILD_MIN = 0.02       # floor (s, capped by the deadline): a rebuild finishes in a few decisions even on tiny shares
_CACHE: dict = {}
_PRIORS: OrderedDict = OrderedDict()
_PRIOR_CACHE = 16
_ORDERS = []


def _run(gen):
    """Run a work generator to completion; its return value."""
    while True:
        try:
            next(gen)
        except StopIteration as stop:
            return stop.value


def prior_work(sampler, n=N_DECKS, require=(), block=8):
    """Generator form of prior_decks (yields every `block` draws); cached per (sampler, n, revealed set)."""
    key = (sampler, n, tuple(sorted(require)))
    if key in _PRIORS:
        _PRIORS.move_to_end(key)
        return _PRIORS[key]
    salt = 'belief|' + '|'.join(sorted(require))
    counts = {}
    for i in range(n):
        if i % block == 0:
            yield
        deck = tuple(sampler.deck(i, salt=salt, require=sorted(require)))
        counts[deck] = counts.get(deck, 0) + 1
    out = dict(decks=[dict(cards=list(k), frequency=float(v)) for k, v in sorted(counts.items())])
    _PRIORS[key] = out
    while len(_PRIORS) > _PRIOR_CACHE:
        _PRIORS.popitem(last=False)
    return out


def prior_decks(sampler, n=N_DECKS, require=()):
    """{'decks': [{'cards', 'frequency'}]} from n sampler draws (duplicates merged), sorted for determinism."""
    return _run(prior_work(sampler, n, require))


def belief_spec(rt):
    spec = getattr(rt, 'belief_prior', None) or os.environ.get('BOT_BELIEF_PRIOR') or 'c56'
    return spec


def planner_belief(rt, base):
    """(prior, belief class) for fair_player.PublicPlanner(R, prior, seed); p.belief.__class__ = class."""
    try:
        from bot.cyclemodel.belief import wrap
    except ImportError:        # trees without bot/cyclemodel (the live Mac tree): today's class
        wrap = None
    if wrap is not None:
        base = wrap(rt, base)  # BOT_CYCLE_MODEL (bot/cyclemodel): unset = `base` itself, today's class
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
    cls = open_world_class(base, 'FullPoolBelief', lambda self, revealed: prior_work(sampler, n, revealed),
                           lambda self: sampler.w)
    cls.sampler = sampler
    return cls


# -- open-world layer --------------------------------------------------------------------------------------------
def _norm(name):
    return ''.join(ch for ch in str(name).casefold() if ch.isalnum())


def resolve_name(name, known):
    """A play's name -> a name in `known` (itself, an alias, or the base card of an evolution / hero name), else
    the unknown placeholder '~<normalised name>'."""
    if name in known:
        return name
    from bot.fullpool.cards import engine_name
    hit = engine_name(name, strict=False)
    if hit in known:
        return hit
    n = _norm(name)
    for v in VARIANTS:
        for rest in ((n[len(v):],) if n.startswith(v) else ()) + ((n[:-len(v)],) if n.endswith(v) else ()):
            hit = engine_name(rest, strict=False) if rest else None
            if hit in known:
                return hit
    return UNKNOWN + (n or 'unknown')


def _orders():
    if not _ORDERS:      # the frozen DerivedPublicState.__init__ order table, built the same way
        orders = []
        for hand in itertools.combinations(range(8), 4):
            for queue in itertools.permutations(i for i in range(8) if i not in hand):
                orders.append((*hand, *queue))
        _ORDERS.append(np.asarray(orders, dtype=np.uint8))
    return _ORDERS[0]


def init_work(b, prior, costs, block=8):
    """Chunked twin of the frozen DerivedPublicState.__init__(b, prior, costs) (identical arrays and fields)."""
    b.names = tuple(sorted(costs))
    b.ids = {n: i + 1 for i, n in enumerate(b.names)}
    b.costs = costs
    if len(b.names) > 255:
        raise ValueError('C56 posterior supports at most255 cards')
    orders = _orders()
    states, weights = [], []
    for k, deck in enumerate(prior['decks']):
        if k % block == 0:
            yield
        cards = np.asarray(sorted(b.ids[n] for n in deck['cards']), dtype=np.uint8)
        if len(cards) != 8 or len(set(cards)) != 8:
            raise ValueError('prior must contain eight distinct cards')
        a = np.zeros((len(orders), 12), dtype=np.uint8)
        a[:, :8] = cards[orders]
        states.append(a)
        weights.append(np.full(len(orders), deck.get('frequency', deck.get('sampling_weight', 1.)), dtype=np.float64))
    yield
    b.states = np.concatenate(states)
    yield
    b.weights = np.concatenate(weights)
    b.cumulative = np.cumsum(b.weights)
    b.tick = 0; b.refill = 0; b.queue_len = 4; b.elixir = 6.0
    b.events = []; b._derived = None
    # the frozen __init__ also calls derived() here: left lazy (same value on first use; under a deadline
    # s1's sample() computes it in bounded blocks)
    yield


def open_world_class(base, name, prior_fn, weights_fn):
    """Subclass `name` of `base` (s1 Belief or a cyclemodel subclass; base stays __mro__[1]) that rebuilds its prior
    with prior_fn(self, revealed) -> work generator returning the prior, tolerates unknown card names and bounds the
    rebuild by the decision deadline. weights_fn(self) -> {card: weight} orders substitutes and the unknown cost."""
    frozen = next(c for c in base.__mro__ if c.__name__ == 'DerivedPublicState')

    class OpenWorldBelief(base):
        rebuilds = 0
        dropped = 0              # certain plays outside one legal deck with the earlier reveals
        rebuild_slices = 0       # decisions that ended with the rebuild unfinished (stale posterior used)
        stale = False            # the last update kept the previous posterior (rebuild pending)
        _job = None

        # -- names --------------------------------------------------------------------------------------------
        def _known(self):
            k = self.__dict__.get('_known0')
            if k is None:
                k = self._known0 = frozenset(n for n in self.costs if not n.startswith(UNKNOWN))
                self._resolved = {}
            return k

        def _resolve(self, raw):
            known = self._known()
            hit = self._resolved.get(raw)
            if hit is None:
                hit = self._resolved[raw] = resolve_name(raw, known)
            return hit

        def canonical(self, events):
            """The belief's view of an event list (prefix-stable; `events` itself when nothing changes)."""
            from bot.fullpool.cards import CHAMPIONS
            ids, out, seen, champ, drops = self.ids, None, set(), False, 0
            for i, e in enumerate(events):
                kind = e.kind
                if kind != 'card' and kind != 'card?':
                    if out is not None:
                        out.append(e)
                    continue
                c = e.name if e.name in ids else self._resolve(e.name)
                keep = True
                if kind == 'card':
                    if c not in seen:
                        if len(seen) >= 8 or (c in CHAMPIONS and champ):
                            keep = False
                        else:
                            seen.add(c)
                            champ = champ or c in CHAMPIONS
                elif c.startswith(UNKNOWN):      # a soft play of an unknown card cannot be explained: drop it
                    keep = False
                if (not keep or c != e.name) and out is None:
                    out = list(events[:i])
                if out is not None:
                    if keep:
                        out.append(e if c == e.name else replace(e, name=c))
                    else:
                        drops += 1
            if out is None:
                return events
            self.dropped = max(self.dropped, drops)
            return out

        def _encodable(self, events):
            ids = self.ids
            return all(e.name in ids for e in events[len(self.events):] if e.kind in ('card', 'card?'))

        def _costs_for(self, revealed):
            missing = [c for c in revealed if c not in self.costs]
            if not missing:
                return self.costs
            w = weights_fn(self)
            known = [c for c in w if c in self.costs and not c.startswith(UNKNOWN)]
            z = sum(w[c] for c in known)
            cost = float(round(sum(w[c] * self.costs[c] for c in known) / z)) if z else 4.
            return dict(self.costs, **{c: cost for c in missing})

        def sample(self, rng, **kw):
            out = super().sample(rng, **kw)
            if self.names and self.names[-1].startswith(UNKNOWN):
                out = self._substitute(out)
            return out

        def _substitute(self, s):
            from bot.fullpool.cards import CHAMPIONS
            w = weights_fn(self)
            row = {c for c in list(s['hand']) + list(s['cycle']) if c}
            cands = [c for c in w if c in self.costs and not c.startswith(UNKNOWN) and c not in CHAMPIONS]
            sub = {}
            for c in sorted(c for c in row if c.startswith(UNKNOWN)):
                cost = self.costs[c]
                pick = min((x for x in cands if x not in row and x not in sub.values()),
                           key=lambda x: (abs(self.costs[x] - cost), -w[x], x))
                sub[c] = pick
            f = lambda xs: [sub.get(x, x) for x in xs]
            return dict(s, hand=f(s['hand']), cycle=f(s['cycle']))

        # -- update / rebuild ---------------------------------------------------------------------------------
        def update(self, tick, events, *, deadline=None, clock=time.monotonic):
            events = self.canonical(events)
            self.stale = False
            if deadline is None:
                self._job = None
                if self._encodable(events):
                    try:
                        return super().update(tick, events, deadline=deadline, clock=clock)
                    except ValueError as ex:
                        if NO_DECK not in str(ex):
                            raise
                self._pending = None
                revealed = list(dict.fromkeys(e.name for e in events if e.kind == 'card'))
                prior = _run(prior_fn(self, revealed))
                rebuilds = self.rebuilds + 1
                frozen.__init__(self, prior, self._costs_for(revealed))
                self.rebuilds = rebuilds
                return super().update(tick, events)
            while True:
                if self._job is not None and not self._advance(events, deadline, clock):
                    self.stale = True
                    self.rebuild_slices += 1
                    return None
                if self._encodable(events):
                    try:
                        return super().update(tick, events, deadline=deadline, clock=clock)
                    except ValueError as ex:
                        if NO_DECK not in str(ex):
                            raise
                self._pending = None
                self._job = self._start(tick, events, clock)

        def _start(self, tick, events, clock):
            revealed = list(dict.fromkeys(e.name for e in events if e.kind == 'card'))
            history = tuple(events)
            return dict(history=history, t0=clock(), work=self._work(tick, history, revealed))

        def _work(self, tick, history, revealed):
            costs = self._costs_for(revealed)
            prior = yield from prior_fn(self, revealed)
            tx = copy.copy(self)
            tx._job, tx._pending, tx.stale = None, None, False
            yield from init_work(tx, prior, costs)
            while True:              # base's chunked transaction: resumable across TimeoutError
                try:
                    base.update(tx, tick, list(history), deadline=self._cut[0], clock=self._cut[1])
                    return tx
                except TimeoutError:
                    yield

        def _advance(self, events, deadline, clock):
            """Run the pending rebuild until the slice ends; True (and installed) when it finished."""
            job = self._job
            if tuple(events[:len(job['history'])]) != job['history']:
                self._job = None
                raise ValueError('public events changed')
            now = clock()
            share = float(os.environ.get('BOT_BELIEF_REBUILD_SHARE') or REBUILD_SHARE)
            left = max(0., deadline - now)
            cut = now + min(left, max(REBUILD_MIN, left * min(1., max(0., share))))
            self._cut = (cut, clock)
            try:
                while clock() < cut:
                    try:
                        next(job['work'])
                    except StopIteration as stop:
                        tx = stop.value
                        keep = dict(rebuilds=self.rebuilds + 1, dropped=self.dropped,
                                    rebuild_slices=self.rebuild_slices)
                        self.__dict__.clear()
                        self.__dict__.update(tx.__dict__)
                        self.__dict__.update(keep)
                        self._job = None
                        return True
            except BaseException:
                self._job = None
                raise
            return False

    OpenWorldBelief.__name__ = OpenWorldBelief.__qualname__ = name
    return OpenWorldBelief
