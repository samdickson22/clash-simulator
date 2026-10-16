"""Resync-capable opponent cycle tracking for imperfect play perception (LIVE integration).

Problem (measured on the 64 validation matches, reports/live/integration/RESULTS.md): the translator's stream guard
(LiveTranslator._consistent: mirrors of the frozen DerivedD1 trackers) drops an opponent play whose card the mirror
still holds in the cycle queue. With perceived plays, that is almost always a TRUE play arriving after earlier plays
were missed (302 of 330 drops): the misses left the mirror un-rotated. Dropping it loses ~22% of all opponent plays.

Resync. When a perceived opponent play of card X contradicts the mirrored cycle:
  1. a ninth distinct card, or X accepted again within `dup_ticks` (a duplicate detection; real repeats need four
     other plays and their refills first), is still dropped;
  2. otherwise the missed plays are inferred: the smallest number k (1..4) of plays of known hand cards (revealed and
     not in the queue; the longest-unplayed first) inserted between the last accepted opponent play and X that makes
     the whole opponent history, X included, consistent for a fresh DerivedD1 (several placements tried);
  3. the history is rewritten (public D1 rows, the enemy PublicEvent stream, plays, the mirror) and `resynced` is set.
     The frozen per-player trackers (D1Tracker, belief) cannot take a changed prefix, so the CALLER restarts the player
     (player.start(ctx)): it rebuilds them from the corrected public history on its next act. Hooks: LiveSession._poll
     (bot/live/translate.py, 3 lines), PercPlayer.act (bot/live/perc.py), real_replay arms.
Fair information: only the public plays and their times are used (inferred plays are hand cards the opponent has
publicly revealed); injected rows carry injected=True. An inferred play also charges its elixir cost, which the missed
play really cost.
"""
from __future__ import annotations

from bot.noise.livefix.translate import LiveTranslator


class ResyncMixin:
    dup_ticks = 80
    inject_xy = (9.0, 24.0)       # unknown placement of an inferred play: middle of the opponent's side (our frame)

    def _init_resync(self):
        self.resynced = False
        self.restarts = 0
        self.revealed.evict = True          # evidence-ranked revealed set (bot/live/revealed.py)

    def _admit(self, card, tick, x, y, via_board=False):
        """Evict the RevealedSet's weakest card W for `card`: the opponent history is rebuilt by re-running this
        translator's play acceptance (stream guard + resync planning) over the perceived opponent plays without W's
        and with `card`'s earlier rejected ones, i.e. the history it would hold had W never been accepted. A card
        admitted on board evidence alone (no perceived play) enters as an inferred play (RevealedSet.board_play),
        and the earlier board-admitted cards keep theirs, so the public deck constraints (mirror, events, the belief
        rebuilt from them) hold every member. Sets `resynced`, so the caller restarts the player and its D1/belief
        trackers rebuild from the new history."""
        w = self.revealed.victim(card, tick)
        if w is None:
            return False
        # The mirror must not run ahead of the stream guard: later events of this record may be earlier than the
        # record tick (lagged detections). Play path: this event's (floored) tick. Board path (assign runs before
        # accept_events): the previous record's tick, the floor of every event still to come.
        until = self._floor if via_board else tick
        perceived = [r for r in self.public_events if r['seat'] == 1 and not r.get('injected')]
        removed = [(r['tick'], r['x'], r['y']) for r in perceived if r['name'] == w]
        earlier = [dict(seat=1, tick=t, kind='card', name=card, amount=0., x=px, y=py)
                   for t, px, py in self.revealed.rejected.get(card, ()) if via_board or t != tick]
        inferred = {c: p for c, p in self.revealed.board_plays.items() if c != w}
        if via_board and not earlier:
            inferred[card] = self.revealed.board_play(card, until, self.inject_xy)
        board = [dict(seat=1, tick=t, kind='card', name=c, amount=0., x=px, y=py, injected=True, board=True)
                 for c, (t, px, py) in inferred.items()]
        self._rebuild([r for r in perceived if r['name'] != w] + earlier + board, until)
        self.revealed.evicted(w, card, removed, via_board, inferred)
        self.resynced = True
        return True

    def _rebuild(self, opp_rows, until):
        from derived_public_state import PublicEvent
        saved = dict(self.stats)
        self.public_events[:] = [r for r in self.public_events if r['seat'] != 1]
        self.plays[1][:], self.events[:] = [], []
        self._mirrors[1] = self._replay([])
        dropped = 0
        for r in sorted(opp_rows, key=lambda r: r['tick']):
            if not self._consistent(1, int(r['tick']), r['name'], float(r['x']), float(r['y'])):
                dropped += 1
                self.stats['evict_board_play_dropped'] += bool(r.get('board'))
                continue
            self.public_events.append(dict(seat=1, tick=int(r['tick']), kind='card', name=r['name'], amount=0.,
                                           x=float(r['x']), y=float(r['y']),
                                           **({'injected': True, 'board': True} if r.get('board') else {})))
        self.public_events.sort(key=lambda r: r['tick'])      # stable: same-tick order kept
        opp = [r for r in self.public_events if r['seat'] == 1]
        self.plays[1][:] = [(r['tick'], r['name']) for r in opp]
        self.events[:] = [PublicEvent(r['tick'], 'card', r['name']) for r in opp]
        self._mirrors[1].advance(until)
        self.stats.clear()                                     # a rebuild is not new live traffic
        self.stats.update(saved)
        self.stats['evict_rebuild_dropped'] += dropped

    def _consistent(self, seat, tick, name, x, y):
        if super()._consistent(seat, tick, name, x, y):
            return True
        if seat != 1:
            return False
        m = self._mirrors[1]
        if len(m.revealed | {name}) > 8:
            return False
        if any(r['seat'] == 1 and r['name'] == name and tick - r['tick'] <= self.dup_ticks for r in self.public_events):
            self.stats['resync_skip_duplicate'] += 1
            return False
        plan = self._plan(tick, name, x, y)
        if plan is None:
            self.stats['resync_failed'] += 1
            return False
        mirror, inserted = plan
        from imitation.evaluation.d1 import PublicEvent as D1Event
        mirror.accept(D1Event(tick, 'card', name, 0., x, y))     # as the base guard does on success
        self._apply(mirror, inserted)
        self.stats['resync'] += 1
        self.stats['resync_injected'] += len(inserted)
        self.resynced = True
        return True

    # -- planning ---------------------------------------------------------------------------------------------
    def _history(self):
        return [(int(r['tick']), r['name'], float(r['x']), float(r['y'])) for r in self.public_events
                if r['seat'] == 1 and r.get('kind', 'card') == 'card']

    def _replay(self, rows, until=None):
        from imitation.evaluation.d1 import PublicEvent as D1Event
        from derived_d1 import DerivedD1
        d = DerivedD1(self.costs)
        for t, n, x, y in sorted(rows, key=lambda r: r[0]):
            d.accept(D1Event(t, 'card', n, 0., x, y))
        if until is not None:
            d.advance(until)
        return d

    def _plan(self, tick, name, x, y):
        hist = self._history()
        try:
            now = self._replay(hist, tick)
        except ValueError:
            return None
        t_last = hist[-1][0] if hist else 0
        last_play = {}
        for t, n, _, _ in hist:
            last_play[n] = t
        hand = sorted(now.revealed - set(now.queue) - {name}, key=lambda c: last_play.get(c, -1))
        ix, iy = self.inject_xy
        for k in range(1, min(4, len(hand)) + 1):
            cards = hand[:k]
            span = tick - t_last
            refill = 20 if tick < 2400 else 10 if tick < 4800 else 7
            placements = [[t_last + (j + 1)*span//(k + 1) for j in range(k)],
                          [min(tick, t_last + 1 + j*refill) for j in range(k)]]
            for ticks in placements:
                ins = [(int(t), c, ix, iy) for t, c in zip(ticks, cards)]
                try:
                    d = self._replay(hist + ins, tick)
                    from imitation.evaluation.d1 import PublicEvent as D1Event
                    d.accept(D1Event(tick, 'card', name, 0., x, y))
                except ValueError:
                    continue
                return self._replay(hist + ins, tick), ins
        return None

    def _apply(self, mirror, inserted):
        from derived_public_state import PublicEvent
        rows = list(self.public_events) + [dict(seat=1, tick=t, kind='card', name=n, amount=0., x=x, y=y, injected=True)
                                           for t, n, x, y in inserted]
        rows.sort(key=lambda r: r['tick'])            # stable: same-tick order kept
        self.public_events[:] = rows
        opp = [r for r in rows if r['seat'] == 1]
        self.plays[1][:] = [(r['tick'], r['name']) for r in opp]
        self.events[:] = [PublicEvent(r['tick'], 'card', r['name']) for r in opp]
        self._mirrors[1] = mirror


class ResyncTranslator(ResyncMixin, LiveTranslator):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._init_resync()


def resync_both():
    from bot.live.real_replay import BothTranslator

    class BothResyncTranslator(ResyncMixin, BothTranslator):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self._init_resync()
    return BothResyncTranslator


def restart_if_resynced(tr, player, ctx):
    """Caller hook: restart the player after a history rewrite (its frozen trackers rebuild from the public history)."""
    if getattr(tr, 'resynced', False):
        tr.resynced = False
        tr.restarts = getattr(tr, 'restarts', 0) + 1
        player.start(ctx)
        return True
    return False
