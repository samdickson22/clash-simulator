"""Proposed LIVE translator fix, measured in the harness only (bot lead, exploration). bot/live is NOT edited: the
fix is a subclass of the deployed ResyncTranslator, swapped in by a PercPlayer subclass with the same noise stream.

    'PERCX<tag>-<arm>:<player>'    bot/live/perc.py PercPlayer(<arm>), translator = EvictTranslator(<tag>)

Problem. The opponent's revealed card set is first-come: the first 8 distinct cards of accepted opponent plays. A
spurious or misread play event (deployed stats: 0.59 spurious events/min, drawn from a deck-independent card
distribution, plus card confusion) puts a card the opponent does not have into that set. Once it holds 8 cards, a
real unrevealed card is locked out for the rest of the match:
  * board_card_ok (deck-rule sanitizer) drops every on-board unit of it (the search never sees those troops);
  * its play events are dropped (mirror: ninth distinct card), so the belief never holds it in hand/cycle.

Fix (fair information: perceived plays and perceived board units only). Each opponent card keeps evidence:
plays = accepted play events (injected resync plays excluded), board = records with >= 1 perceived on-board unit of it.
When the revealed set is full and a 9th card X shows evidence -- `b<n>`: X on the board in >= n records, or `e<n>`:
the n-th rejected play event of X -- the weakest revealed card W (fewest plays, then fewest board records, then
oldest) is evicted iff its own evidence is weak: plays(W) <= `p<k>` (default 1) and board(W) <= `w<m>` records
(default 0). W's plays leave the public history (mirror, plays, belief events), the history is re-validated by a
fresh DerivedD1 replay (skipped if inconsistent), and `resynced` is set so the player rebuilds its trackers, exactly as
the resync tracker does after a history rewrite. X itself enters through its next play event, or at once as an
injected play at its first board sighting with `i` (unknown time -> first sighting; elixir charged).

Tag examples: 'b3e2' (default k=1, m=0), 'b3e2p1w2', 'b3e2i'.
"""
from __future__ import annotations

import re
from collections import Counter

from bot.live.resync import ResyncTranslator


def parse(tag):
    m = re.fullmatch(r'(?:b(\d+))?(?:e(\d+))?(?:p(\d+))?(?:w(\d+))?(i?)', tag)
    if m is None:
        raise ValueError(f'bad evict tag {tag!r}')
    return dict(board=int(m[1]) if m[1] else None, events=int(m[2]) if m[2] else None,
                plays=int(m[3]) if m[3] else 1, wboard=int(m[4]) if m[4] else 0, inject=bool(m[5]))


class EvictTranslator(ResyncTranslator):
    def __init__(self, *a, evict=None, **kw):
        super().__init__(*a, **kw)
        self.cfg = evict
        self.ev_board = Counter()      # opponent card -> records with >= 1 perceived board unit
        self.ev_rejected = Counter()   # opponent card -> play events rejected as a 9th card
        self.first_seen = {}
        self._board_tick = None
        self._board_seen = set()

    # -- evidence ---------------------------------------------------------------------------------------------
    def _plays_of(self, card):
        return sum(1 for r in self.public_events if r['seat'] == 1 and r['name'] == card and not r.get('injected'))

    def _revealed(self):
        return {n for _, n in self.plays[1]}

    def _weakest(self):
        last = {}
        for r in self.public_events:
            if r['seat'] == 1:
                last[r['name']] = r['tick']
        rev = self._revealed()
        if not rev:
            return None
        return min(rev, key=lambda c: (self._plays_of(c), self.ev_board[c], last.get(c, 0)))

    def _try_evict(self, newcomer, tick):
        if len(self._revealed()) < 8 or newcomer in self._revealed():
            return False
        w = self._weakest()
        if w is None or self._plays_of(w) > self.cfg['plays'] or self.ev_board[w] > self.cfg['wboard']:
            self.stats['evict_refused'] += 1
            return False
        rows = [r for r in self.public_events if not (r['seat'] == 1 and r['name'] == w)]
        hist = [(int(r['tick']), r['name'], float(r['x']), float(r['y'])) for r in rows
                if r['seat'] == 1 and r.get('kind', 'card') == 'card']
        try:
            mirror = self._replay(hist, max(tick, self.tick or 0))
        except ValueError:
            self.stats['evict_inconsistent'] += 1
            return False
        self.public_events[:] = rows
        self._apply(mirror, [])
        self.stats['evict'] += 1
        self.stats[f'evict:{w}->{newcomer}'] += 1
        self.resynced = True
        return True

    # -- hooks ------------------------------------------------------------------------------------------------
    def board_card_ok(self, card, owner):
        if owner == 1:
            if self._board_tick != self.tick:
                self._board_tick, self._board_seen = self.tick, set()
            if card not in self._board_seen:
                self._board_seen.add(card)
                self.ev_board[card] += 1
                self.first_seen.setdefault(card, self.tick)
            b = self.cfg['board']
            if b is not None and card not in self._revealed() and len(self._revealed()) >= 8 and \
                    self.ev_board[card] >= b and self._try_evict(card, self.tick):
                if self.cfg['inject']:
                    self._inject(card)
        return super().board_card_ok(card, owner)

    def _inject(self, card):
        t = int(self.first_seen.get(card, self.tick))
        floor = max(self._floor, self.public_events[-1]['tick'] if self.public_events else 0)
        t = max(t, floor)
        x, y = self.inject_xy
        if not super()._consistent(1, t, card, x, y):
            self.stats['evict_inject_failed'] += 1
            return
        from derived_public_state import PublicEvent
        self.plays[1].append((t, card))
        self.events.append(PublicEvent(t, 'card', card))
        self.public_events.append(dict(seat=1, tick=t, kind='card', name=card, amount=0., x=x, y=y, injected=True))
        self.stats['evict_injected'] += 1

    def _consistent(self, seat, tick, name, x, y):
        if seat == 1 and self.cfg['events'] is not None and name not in self._revealed() and len(self._revealed()) >= 8:
            self.ev_rejected[name] += 1
            if self.ev_rejected[name] >= self.cfg['events'] or (self.cfg['board'] is not None and
                                                                 self.ev_board[name] >= self.cfg['board']):
                self._try_evict(name, tick)
        return super()._consistent(seat, tick, name, x, y)


def make_percx(rt, name, fallback):
    """'PERCX<tag>-<arm>:<player>'."""
    from bot.live.perc import PercPlayer
    m = re.fullmatch(r'PERCX([a-z0-9]+)-([^:]+):(.+)', name)
    cfg, arm, inner = parse(m[1]), m[2], m[3]

    class Fixed(PercPlayer):
        def start(self, ctx):
            super().start(ctx)
            if self.noise is not None or self.plays_from != 'events':
                raise ValueError('PERCX: empirical events arms only')
            self.tr = EvictTranslator(self.rt, list(ctx.own_order), plays_from=self.plays_from, evict=cfg)
            self.tr.set_own_order(ctx.own_order)
    p = Fixed(rt, arm, fallback(rt, inner))
    p.name = name
    return p
