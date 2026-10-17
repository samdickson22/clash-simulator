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
- Rebuild under a decision deadline. With deadline=None the rebuild runs the same frozen operations as before (same
  arrays, same fixed-timing command hashes); the layer only adds its own fields (stale, dropped, rebuild_slices, the
  name map) and module caches (priors per revealed set, the order table). With a deadline, the rebuild is a
  resumable job in bounded steps (one sampler draw, one prior deck, one 4096-row block or one 16k-row cumulative-sum
  chunk per step; rows are compacted in place, never concatenated), run until ONE cutoff per update(): now + a share
  of the time left (BOT_BELIEF_REBUILD_SHARE in (0, 1], default 0.5; malformed / out-of-range values fall back to
  0.5), at least 20 ms, never past the deadline. ~92 ms of a Mac decision, where a rebuild costs ~75 ms; the whole
  rebuild at a 2 s replay deadline. A call returns within about one step of its cutoff. If the job is unfinished,
  the decision keeps the previous posterior (`stale` = True: the search samples it instead of falling back to the
  default) and the job resumes on the next decision. The finished job equals the synchronous rebuild
  (bot/fullpool/test_belief_robust.py).
"""
from __future__ import annotations

import copy
import itertools
import math
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
BLOCK_ROWS = 4096        # rows per rebuild work step (as s1's block_rows); cumulative sums use 4 blocks per step
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


def prior_work(sampler, n=N_DECKS, require=(), block=1):
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
    yield
    items = sorted(counts.items())
    decks = []
    for j in range(0, len(items), 50):
        yield
        decks.extend(dict(cards=list(k), frequency=float(v)) for k, v in items[j:j + 50])
    out = dict(decks=decks)
    _PRIORS[key] = out
    while len(_PRIORS) > _PRIOR_CACHE:
        _PRIORS.popitem(last=False)
    return out


def rebuild_share():
    """BOT_BELIEF_REBUILD_SHARE in (0, 1]; unset, malformed, non-finite or out of range -> REBUILD_SHARE."""
    raw = os.environ.get('BOT_BELIEF_REBUILD_SHARE')
    try:
        v = float(raw) if raw else REBUILD_SHARE
    except ValueError:
        return REBUILD_SHARE
    return v if math.isfinite(v) and 0. < v <= 1. else REBUILD_SHARE


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


def cumsum_work(w, rows=4 * BLOCK_ROWS, out=None):
    """np.cumsum(w) in bounded steps (into `out` if given); bit-identical: accumulate is sequential, and each step
    restarts from the carry."""
    out = np.empty_like(w) if out is None else out
    carry = None
    for s in range(0, len(w), rows):
        yield
        chunk = w[s:s + rows]
        c = np.cumsum(chunk) if carry is None else np.cumsum(np.concatenate(([carry], chunk)))[1:]
        out[s:s + len(chunk)] = c
        carry = c[-1]
    return out


def init_work(b, prior, costs, block=1):
    """Bounded-step twin of the frozen DerivedPublicState.__init__(b, prior, costs): identical arrays and fields, built
    deck by deck into preallocated arrays (no whole-array concatenation or cumsum in one step)."""
    b.names = tuple(sorted(costs))
    b.ids = {n: i + 1 for i, n in enumerate(b.names)}
    b.costs = costs
    if len(b.names) > 255:
        raise ValueError('C56 posterior supports at most255 cards')
    orders = _orders()
    m, decks = len(orders), prior['decks']
    yield
    states = np.zeros((len(decks) * m, 12), dtype=np.uint8)
    weights = np.empty(len(decks) * m, dtype=np.float64)
    for k, deck in enumerate(decks):
        if k % block == 0:
            yield
        cards = np.asarray(sorted(b.ids[n] for n in deck['cards']), dtype=np.uint8)
        if len(cards) != 8 or len(set(cards)) != 8:
            raise ValueError('prior must contain eight distinct cards')
        states[k * m:(k + 1) * m, :8] = cards[orders]
        weights[k * m:(k + 1) * m] = deck.get('frequency', deck.get('sampling_weight', 1.))
    b.states, b.weights = states, weights
    b.cumulative = yield from cumsum_work(weights)
    b.tick = 0; b.refill = 0; b.queue_len = 4; b.elixir = 6.0
    b.events = []; b._derived = None
    # the frozen __init__ also calls derived() here: left lazy (same value on first use; under a deadline
    # s1's sample() computes it in bounded blocks)


def _advance_fine(b, tick, block=BLOCK_ROWS):
    """s1 Belief._advance_work with the same arithmetic (yields every 64 ticks and every block of a refill)."""
    if tick < b.tick:
        raise ValueError('public time moved backwards')
    while b.tick < tick:
        b.tick += 1
        if b.tick % 64 == 0:
            yield
        rate = .93 if b.tick > 4800 else 1.4 if b.tick > 2400 else 2.8
        b.elixir = min(10., (round(b.elixir * 10000) + int(500 / rate)) / 10000) if b.elixir < 10. else b.elixir
        b.refill = max(0, b.refill - 50)
        if b.refill == 0 and b.queue_len > 4:
            S = b.states             # in place, block by block (rows are independent; the job owns its arrays)
            for start in range(0, len(S), block):
                yield
                part = S[start:start + block].copy()
                part[:, 0] = part[:, 4]; part[:, :4].sort(axis=1)
                part[:, 4:-1] = part[:, 5:]; part[:, -1] = 0
                S[start:start + len(part)] = part
            b.queue_len -= 1
            b.refill = 1000 if b.tick < 2400 else 500 if b.tick < 4800 else 350
            b._derived = None


def replay_work(b, tick, events, block=BLOCK_ROWS):
    """s1 Belief._update_work on a fresh rebuild, in bounded steps: a play's surviving rows are compacted block by block
    to the front of the job's own buffers and the cumulative weights summed in steps (s1 concatenates and sums the
    whole posterior in one step, and allocates / frees ~20 MB per play). Same operations per row, so identical values
    (tested against the frozen update); the posterior arrays are prefix views of the init buffers."""
    if list(events[:len(b.events)]) != b.events:
        raise ValueError('public events changed')
    for event in events[len(b.events):]:
        yield from _advance_fine(b, event.tick, block)
        if event.kind == 'card':
            card, n = b.ids[event.name], len(b.states)
            keeps, total = [], 0
            for start in range(0, n, block):
                yield
                k = np.any(b.states[start:start + block, :4] == card, axis=1)
                keeps.append(k)
                total += int(np.count_nonzero(k))
            yield
            if not total:
                raise ValueError('no train deck/order is consistent with public plays')
            S, W, C = b.states, b.weights, b.cumulative
            o = 0                    # write rows [o, o+m) only after reading block `start` (o <= start: safe in place)
            for j, start in enumerate(range(0, n, block)):
                yield
                k = keeps[j]
                part, wpart = S[start:start + block][k], W[start:start + block][k]
                m = len(part)
                if not m:
                    continue
                slot = (part[:, :4] == card).argmax(axis=1)
                part[np.arange(m), slot] = 0; part[:, :4].sort(axis=1)
                part[:, 4 + b.queue_len] = card
                S[o:o + m] = part
                W[o:o + m] = wpart
                o += m
            b.states, b.weights = S[:total], W[:total]
            b.cumulative = yield from cumsum_work(b.weights, out=C[:total])
            b.queue_len += 1
            b.elixir = max(0., b.elixir - b.costs[event.name]); b._derived = None
        elif event.kind == 'ability':
            b.elixir -= event.amount
            if b.elixir < 0:
                raise ValueError('public ability was unaffordable')
        elif event.kind == 'collector':
            b.elixir = min(10., b.elixir + event.amount)
        else:
            raise ValueError(f'unknown public event {event.kind}')
        b.events.append(event)
    yield from _advance_fine(b, tick, block)


def open_world_class(base, name, prior_fn, weights_fn, weights_work=None):
    """Subclass `name` of `base` (s1 Belief or a cyclemodel subclass; base stays __mro__[1]) that rebuilds its prior
    with prior_fn(self, revealed) -> work generator returning the prior, tolerates unknown card names and bounds the
    rebuild by the decision deadline. weights_fn(self) -> {card: weight} orders substitutes and the unknown cost;
    weights_work(self), if given, is a work generator that prepares (caches) those weights in bounded steps."""
    frozen = next(c for c in base.__mro__ if c.__name__ == 'DerivedPublicState')
    s1 = next((c for c in base.__mro__ if '_update_work' in c.__dict__), None)
    fine = s1 is not None and base.update is s1.update     # plain s1 update: bounded replay_work; else base's own
    _orders()

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
            cut = None               # one rebuild cutoff per update(), shared by every job it runs
            while True:
                if self._job is not None and cut is None:
                    now = clock()
                    left = max(0., deadline - now)
                    cut = now + min(left, max(REBUILD_MIN, left * rebuild_share()))
                if self._job is not None and not self._advance(events, cut, clock):
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
            if weights_work is not None and any(c not in self.costs for c in revealed):
                yield from weights_work(self)          # an unknown card's cost needs the (cached) card weights
            costs = self._costs_for(revealed)
            prior = yield from prior_fn(self, revealed)
            yield
            tx = copy.copy(self)
            tx._job, tx._pending, tx.stale = None, None, False
            yield from init_work(tx, prior, costs)
            if fine:
                yield from replay_work(tx, tick, list(history))
                return tx
            while True:              # base's chunked transaction: resumable across TimeoutError
                try:
                    base.update(tx, tick, list(history), deadline=self._cut[0], clock=self._cut[1])
                    return tx
                except TimeoutError:
                    yield

        def _advance(self, events, cut, clock):
            """Run the pending rebuild until `cut`; True (and installed) when it finished."""
            job = self._job
            if tuple(events[:len(job['history'])]) != job['history']:
                self._job = None
                raise ValueError('public events changed')
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
