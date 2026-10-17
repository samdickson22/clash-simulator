"""Opponent cycle model in the search belief: unseen opponent plays and soft (P(real)) plays (exploration).

The frozen belief (derived_public_state.DerivedPublicState -> s1 belief.Belief) holds rows = deck x hand/queue order
(hand sorted, empty slot = 0 first; queue = states[:, 4:4+queue_len]) and keeps only rows that hold a played card in
hand. A play that no row has in hand empties it ('no train deck/order ...'), which is why the live translator drops
cycle conflicts. `cycle_belief_class(base)` returns a subclass of `base` (s1 Belief or any subclass below a rebuild
layer such as FullPoolBelief / LiveBelief) that explains such plays instead:

* hidden plays: when an observed play of C is in no row's hand, rows with C in the queue at index j need
  k = j - pending + 1 unseen plays (pending = refills already due, forced first as timing slack). Only rows with the
  minimal k* are kept. Each unseen play takes a hand card h to the queue end and refills at once, weighted by
  lam[h] = P(a play of h is unseen) (unseen_lambda: 1 for body-less cards, which births never sees; eps otherwise).
  Branches whose hidden cards + C cost more than the elixir ledger + `slack` are pruned. Equal rows merge exactly
  (a row holds all 8 cards and the order).
* soft plays: PublicEvent(tick, 'card?', name, amount=p) with p = P(real). Mixture: the real branch (mass p, minimal
  hidden plays, C played with an immediate refill so both branches share queue_len) and the phantom branch (mass
  1-p, unchanged). The ledger is charged p * (cost(C) + expected hidden cost). A soft play impossible under any
  explanation is a phantom.
* unseen evidence: PublicEvent(tick, 'unseen', '', amount=p): one hidden play with probability p at that tick.

A certain 'card' play with C in no row still raises 'no train deck ...' (the rebuild layer above widens the prior);
a certain play with no affordable explanation is ignored (state unchanged, counted 'rejected').

Perfect observation: a batch of certain events with no conflict runs the frozen per-event operations in the frozen
order (advance(e.tick) -> filter/append -> ... -> advance(tick)); with a deadline it is s1 Belief's chunked
transaction verbatim. So rows, weights and rng use are bit-identical to the frozen belief (bot/cyclemodel/parity.py).

Selection: env BOT_CYCLE_MODEL (or rt.cycle_model) = 'soft[:eps=<f>,slack=<f>,cap=<n>,floor=<f>]'; unset/'off' =
the frozen class (today's bot bit for bit). Hidden plays are derived state, never events: the event list stays the
caller's append-only list, and a prior rebuild replays them deterministically.
"""
from __future__ import annotations

import os
import time

import numpy as np

SOFT_KINDS = ('card?', 'unseen')
NO_DECK = 'no train deck/order is consistent with public plays'
DEFAULTS = dict(eps=0.1, slack=2.0, cap=400000, floor=1e-9)


def parse_spec(spec):
    """'soft[:eps=0.1,slack=2,cap=400000,floor=1e-9]' -> config dict; None/''/'off' -> None."""
    if not spec or spec == 'off':
        return None
    head, _, rest = spec.partition(':')
    if head != 'soft':
        raise ValueError(f'BOT_CYCLE_MODEL {spec!r}: expected soft[:k=v,...]')
    cfg = dict(DEFAULTS)
    for kv in filter(None, rest.split(',')):
        k, _, v = kv.partition('=')
        if k not in DEFAULTS:
            raise ValueError(f'BOT_CYCLE_MODEL: unknown key {k!r}')
        cfg[k] = type(DEFAULTS[k])(float(v)) if k == 'cap' else float(v)
    if cfg['cap'] < 1 or not 0. <= cfg['floor'] < 1. or cfg['eps'] < 0.:
        raise ValueError(f'BOT_CYCLE_MODEL {spec!r}: need cap >= 1, 0 <= floor < 1, eps >= 0')
    return cfg


def cycle_spec(rt=None):
    return getattr(rt, 'cycle_model', None) or os.environ.get('BOT_CYCLE_MODEL') or None


def enabled(rt=None):
    """True iff the planner installs the cycle model (the translator must emit 'card?'/'unseen' only then)."""
    return parse_spec(cycle_spec(rt)) is not None


def bodyless_cards(config):
    """Cards with no Troop/Building unit in the runtime config (spells: births never sees their plays)."""
    out = set()
    for card, c in config['cards'].items():
        if ':' in card:
            continue
        groups = [t for g in c.get('units', ()) for t in (g if isinstance(g, list) else [g])]
        if not any(t.get('class') in ('Troop', 'Building') for t in groups):
            out.add(card)
    return out


def unseen_lambda(costs, config, eps):
    """name -> P(a play of this card is unseen by births): 1 for body-less cards, eps for the rest."""
    bodyless = bodyless_cards(config) if config is not None else set()
    return {n: (1.0 if n in bodyless else float(eps)) for n in costs}


_CLASSES = {}


def cycle_belief_class(base, cfg, lam):
    """Subclass of `base` (s1 Belief or a subclass) with the cycle model. cfg = parse_spec(...); lam = name -> float."""
    key = (base, tuple(sorted(cfg.items())), tuple(sorted(lam.items())))
    if key in _CLASSES:
        return _CLASSES[key]
    frozen = next(c for c in base.__mro__ if c.__name__ == 'DerivedPublicState')

    class CycleBelief(base):
        cycle_cfg = dict(cfg)
        cycle_lam = dict(lam)

        # -- public API ------------------------------------------------------------------------------------------
        def update(self, tick, events, *, deadline=None, clock=time.monotonic):
            new = events[len(self.events):]
            special = any(e.kind in SOFT_KINDS for e in new)
            if deadline is not None:
                if not special:
                    try:
                        return super().update(tick, events, deadline=deadline, clock=clock)
                    except ValueError as ex:
                        if NO_DECK not in str(ex):
                            raise
                    self._pending = None        # the failed transaction never touched self
                if clock() >= deadline:
                    raise TimeoutError('K-v2 belief cutoff')
            self._pending = None
            if list(events[:len(self.events)]) != self.events:
                raise ValueError('public events changed')
            if not self.events:
                self._cycle_log = {}                  # fresh (or rebuilt) belief: no stale explanations
            for e in events[len(self.events):]:
                self._cycle_apply(e)
            frozen.advance(self, tick)

        @property
        def cycle_stats(self):
            log = getattr(self, '_cycle_log', None) or {}
            out = dict(conflicts=0, soft=0, unseen=0, hidden_plays=0.0, rejected=0, phantom_only=0, max_rows=0,
                       max_ms=0.0)
            for v in log.values():
                for k, x in v.items():
                    out[k] = max(out[k], x) if k in ('max_rows', 'max_ms') else out[k] + x
            return out

        # -- internals --------------------------------------------------------------------------------------------
        def _log(self, **kw):
            if getattr(self, '_cycle_log', None) is None:
                self._cycle_log = {}
            self._cycle_log[self._cycle_idx] = kw         # keyed by event index: a rebuild replay overwrites

        def _lam_cost(self):
            ids = getattr(self, '_lam_ids', None)
            if ids is not self.ids:
                n = len(self.names) + 1
                self._lam_arr = np.zeros(n)
                self._cost_arr = np.zeros(n)
                for name, i in self.ids.items():
                    self._lam_arr[i] = self.cycle_lam.get(name, self.cycle_cfg['eps'])
                    self._cost_arr[i] = self.costs[name]
                self._lam_ids = self.ids
            return self._lam_arr, self._cost_arr

        def _cycle_apply(self, e):
            self._cycle_idx = len(self.events)
            frozen.advance(self, e.tick)
            if e.kind == 'card':
                card = self.ids[e.name]
                if np.any(self.states[:, :4] == card):
                    return frozen.update(self, e.tick, self.events + [e])     # the frozen operation
            t0 = time.perf_counter()
            try:
                return self._cycle_special(e)
            finally:
                if self._cycle_idx in (getattr(self, '_cycle_log', None) or {}):
                    self._cycle_log[self._cycle_idx]['max_ms'] = 1000 * (time.perf_counter() - t0)

        def _cycle_special(self, e):
            if e.kind == 'card':
                return self._explain(e, 1.0)
            if e.kind == 'card?':
                p = float(e.amount)
                if not 0. < p <= 1.:
                    raise ValueError(f"'card?' amount must be P(real) in (0, 1], got {p}")
                return self._explain(e, p)
            if e.kind == 'unseen':
                return self._unseen(e, float(e.amount))
            return frozen.update(self, e.tick, self.events + [e])

        def _hidden_k(self, card):
            """Per-row unseen plays needed before `card` is in hand (refills already due count as free)."""
            q = self.states[:, 4:4+self.queue_len] == card
            pending = self.queue_len - 4
            k = np.where(q.any(axis=1), q.argmax(axis=1) - pending + 1, np.iinfo(np.int64).max)
            k = np.maximum(k, 0)
            k[np.any(self.states[:, :4] == card, axis=1)] = 0
            return k

        def _force_refills(self, states):
            """All refills already due happen now (timing slack); returns the new states (queue_len -> 4)."""
            s = states.copy()
            for _ in range(self.queue_len - 4):
                s[:, 0] = s[:, 4]
                s[:, :4].sort(axis=1)
                s[:, 4:-1] = s[:, 5:]
                s[:, -1] = 0
            return s

        def _hide(self, s, w, c, steps, budget):
            """`steps` unseen plays on every row (queue_len 4, full hands): each takes hand card h to the queue end
            and refills at once. Weights x lam[h]; c = accumulated hidden cost (weighted sum, merged with rows)."""
            lam, cost = self._lam_cost()
            for _ in range(steps):
                parts_s, parts_w, parts_c = [], [], []
                for slot in range(4):
                    h = s[:, slot]
                    ns = s.copy()
                    ns[:, slot] = ns[:, 4]
                    ns[:, :4].sort(axis=1)
                    ns[:, 4:7] = s[:, 5:8]
                    ns[:, 7] = h
                    nw = w * lam[h]
                    nc = c * lam[h] + nw * cost[h]           # weighted cost sum: avg cost = nc / nw
                    ok = (nw > 0) & (nc <= nw * budget + 1e-9)
                    parts_s.append(ns[ok]); parts_w.append(nw[ok]); parts_c.append(nc[ok])
                s, w, c = merge(np.concatenate(parts_s), np.concatenate(parts_w), np.concatenate(parts_c))
                if not len(s):
                    break
            return s, w, c

        def _real_branch(self, card, budget):
            """Rows after the minimal unseen plays that put `card` in hand: (states, weights, hidden cost sum, k*) or
            None if no row holds the card at all, or an empty branch if no explanation is affordable."""
            k = self._hidden_k(card)
            kstar = int(k.min())
            if kstar == np.iinfo(np.int64).max:
                return None
            if budget < 0:                            # C itself is not affordable (ledger + slack): no explanation
                return self.states[:0], self.weights[:0].astype(np.float64), np.zeros(0), kstar
            keep = k == kstar
            s = self._force_refills(self.states[keep])
            w = self.weights[keep].astype(np.float64)
            c = np.zeros(len(s))
            if kstar:
                s, w, c = self._hide(s, w, c, kstar, budget)
            if len(s):
                assert np.all(np.any(s[:, :4] == card, axis=1)), 'hidden plays did not bring the card into hand'
            return s, w, c, kstar

        def _set_rows(self, s, w, unique=False):
            """unique=True: rows are already distinct (_hide merges; a forced refill is injective within a deck)."""
            if not unique:
                s, w, _ = merge(s, w, np.zeros(len(s)))
            total = w.sum()
            keep = w >= self.cycle_cfg['floor'] * total
            keep[int(np.argmax(w))] = True            # never empty: the heaviest row always survives
            s, w = s[keep], w[keep]
            cap = int(self.cycle_cfg['cap'])
            if len(s) > cap:
                top = np.sort(np.argsort(-w, kind='stable')[:cap])
                s, w = s[top], w[top]
            self.states, self.weights = s, w
            self.cumulative = np.cumsum(self.weights)
            self.queue_len = 4
            # every caller refilled at least once now (forced, hidden or immediate): the frozen refill cooldown
            self.refill = 1000 if self.tick < 2400 else 500 if self.tick < 4800 else 350
            self._derived = None
            return len(s)

        def _explain(self, e, p):
            card = self.ids[e.name]
            cost_c = self.costs[e.name]
            budget = self.elixir + self.cycle_cfg['slack'] - cost_c
            branch = self._real_branch(card, budget)
            if branch is None:
                if e.kind == 'card':
                    raise ValueError(NO_DECK)                     # off-prior card: the rebuild layer widens the prior
                self._log(soft=1, phantom_only=1)
                self.events.append(e)
                return
            s, w, c, kstar = branch
            if not len(s):
                self._log(**({'soft': 1, 'phantom_only': 1} if e.kind != 'card' else {'conflicts': 1, 'rejected': 1}))
                self.events.append(e)
                return
            hidden_cost = float(c.sum() / w.sum())
            total = float(self.weights.sum())
            if e.kind == 'card':
                n = self._set_rows(s, w * (total / w.sum()), unique=True)
                self.elixir = max(0., self.elixir - hidden_cost)
                frozen.update(self, e.tick, self.events + [e])   # C now in hand in every row: the frozen play
                self._log(conflicts=1, hidden_plays=kstar, max_rows=n)
                return
            # real branch: play C with an immediate refill (queue_len stays 4); phantom branch: unchanged rows
            slot = (s[:, :4] == card).argmax(axis=1)
            s = s.copy()
            s[np.arange(len(s)), slot] = s[:, 4]
            s[:, :4].sort(axis=1)
            s[:, 4:7] = s[:, 5:8].copy()
            s[:, 7] = card
            if p < 1.:
                phantom = self._force_refills(self.states)
                n = self._set_rows(np.concatenate([s, phantom]),
                                   np.concatenate([w * (p * total / w.sum()), self.weights * (1. - p)]))
            else:
                n = self._set_rows(s, w * (total / w.sum()))
            self.elixir = max(0., self.elixir - p * (cost_c + hidden_cost))
            self.events.append(e)
            self._log(soft=1, hidden_plays=p * kstar, max_rows=n)

        def _unseen(self, e, p):
            if not 0. < p <= 1.:
                raise ValueError(f"'unseen' amount must be a probability in (0, 1], got {p}")
            base = self._force_refills(self.states)
            w0 = self.weights.astype(np.float64)
            s, w, c = self._hide(base, w0, np.zeros(len(base)), 1, self.elixir + self.cycle_cfg['slack'])
            if not len(s):
                self._log(unseen=1, phantom_only=1)
                self.events.append(e)
                return
            total = float(w0.sum())
            hidden_cost = float(c.sum() / w.sum())
            n = self._set_rows(np.concatenate([s, base]),
                               np.concatenate([w * (p * total / w.sum()), w0 * (1. - p)]))
            self.elixir = max(0., self.elixir - p * hidden_cost)
            self.events.append(e)
            self._log(unseen=1, hidden_plays=p, max_rows=n)

    CycleBelief.__name__ = CycleBelief.__qualname__ = f'Cycle{base.__name__}'
    _CLASSES[key] = CycleBelief
    return CycleBelief


def merge(s, w, c):
    """Merge equal rows (sum weights and weighted costs); rows come back in sorted byte order (deterministic)."""
    if not len(s):
        return s, w, c
    s = np.ascontiguousarray(s)
    if s.dtype == np.uint8 and s.shape[1] >= 8 and not s[:, 8:].any():
        keys = np.ascontiguousarray(s[:, :8]).view(np.uint64).ravel()   # queue_len 4: 8 cards = one uint64 key
    else:
        keys = s.view(np.dtype((np.void, s.dtype.itemsize * s.shape[1]))).ravel()
    uniq, first, inv = np.unique(keys, return_index=True, return_inverse=True)
    return s[first], np.bincount(inv, weights=w, minlength=len(uniq)), np.bincount(inv, weights=c, minlength=len(uniq))


def wrap(rt, base):
    """`base` with the cycle model if BOT_CYCLE_MODEL / rt.cycle_model selects it, else `base` itself."""
    cfg = parse_spec(cycle_spec(rt))
    if cfg is None:
        return base
    R = rt.R
    return cycle_belief_class(base, cfg, unseen_lambda(R.costs, getattr(R, 'config', None), cfg['eps']))
