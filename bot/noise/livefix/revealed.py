"""Evidence-ranked opponent revealed set (LIVE translator; proposed bot/live/revealed.py).

Problem (bot lead translator audit, reports/bot/noise-robust/RESULTS.md section 5): the opponent's card set was
first-come, the first 8 distinct cards of accepted opponent plays. Under the deployed perception noise
(PERC-emp-sr1u50) a spurious or misread play event puts a card the opponent never had into that set in 85% of games,
and once 8 cards are known a real card is LOCKED OUT for the rest of the match: its plays are dropped (the belief
never holds it; mostly spells: Fireball, Arrows, Log, ...) and the board sanitizer drops its units.

RevealedSet is ONE object that answers "can the opponent have card c" for both play acceptance
(LiveTranslator.accept_events) and the board sanitizer (LiveTranslator.board_card_ok), so the two cannot disagree.
Members = cards of the accepted opponent plays (translator.plays[1], rewritten in place by resync/eviction) plus
cards admitted on board evidence alone. With `evict` off it is exactly the old first-come rule.

Eviction (evidence only from public perception: perceived play events and perceived board units, never engine truth;
unit scores are not used). Per opponent card:
  plays     accepted perceived plays (resync-inferred plays excluded) + plays rejected while the set was full
            (`dup_ticks` apart, so one play detected twice counts once);
  board     records in which the card met the persistence rule: perceived on >= k of the last n records. A real
            unit persists for seconds; false positives and per-frame card confusion rarely repeat on k of n.
A member W is WEAK if it is contradicted, i.e. a card that deploys units, last played >= `confirm_ticks` ago, with
no unit of it perceived on any record from 1 s before to `confirm_ticks` after any of its plays, and plays(W) <=
`contra_plays`; or if it deploys no units (a spell), plays(W) <= `weak_plays` and board(W) <= `weak_board`. A unit
card the board confirmed, or one played within `confirm_ticks`, is never weak. When the set is full, a non-member X
evicts the weakest W (contradicted first, then fewest plays, fewest board records, oldest last evidence: a real card
cycles back within about a minute) once X has `board_need` board records, or `events_need` plays (`contra_need` if W
is contradicted). A card the opponent really plays repeatedly or keeps on the board is never evicted. The translator
then re-runs its play acceptance (resync included) over the perceived opponent plays without W's and with X's
rejected ones, i.e. the history it would have built had W never been accepted, and sets `resynced`, so the player
rebuilds its D1/belief trackers from the corrected history (bot/live/resync.py).
W's removed plays become rejected evidence for W, so a real card evicted by mistake comes back on its next play.
"""
from __future__ import annotations

from bisect import bisect_left
from collections import Counter, deque


class RevealedSet:
    cap = 8

    def __init__(self, rows, plays=None, *, evict=False, persist=(3, 4), board_need=10, events_need=2, weak_plays=1,
                 weak_board=0, contra_need=1, contra_plays=2, dup_ticks=80, confirm_ticks=80, spawns=None,
                 stats=None):
        self.rows = rows                     # translator.public_events (D1 rows of both seats; rewritten in place)
        self.accepted = rows if plays is None else plays     # translator.plays[1]: accepted (tick, card) plays
        self.evict = evict
        self.persist_k, self.board_need, self.events_need = persist[0], board_need, events_need
        self.weak_plays, self.weak_board, self.dup_ticks = weak_plays, weak_board, dup_ticks
        self.confirm_ticks, self.contra_need, self.contra_plays = confirm_ticks, contra_need, contra_plays
        self.spawns = spawns or (lambda card: False)   # card -> deploys troop/building units (public card data)
        self.window = deque(maxlen=persist[1])
        self.admitted = []                   # cards admitted on board evidence (no accepted play needed)
        self.board = Counter()               # card -> records meeting the persistence rule
        self.seen = {}                       # card -> ticks of the records with >= 1 perceived unit of it
        self.rejected = {}                   # card -> [(tick, x, y)] plays not accepted while the set was full
        self.last = {}                       # card -> tick of its latest evidence
        self.stats = Counter() if stats is None else stats

    # -- membership (the one rule both callers use) ------------------------------------------------------------
    def _opp_rows(self):
        return [r for r in self.rows if r['seat'] == 1 and r.get('kind', 'card') == 'card']

    def members(self):
        if self.accepted is self.rows:
            return {r['name'] for r in self._opp_rows()} | set(self.admitted)
        return {n for _, n in self.accepted} | set(self.admitted)

    def allows(self, card):
        m = self.members()
        return card in m or len(m) < self.cap

    # -- evidence ----------------------------------------------------------------------------------------------
    def plays(self, card):
        return (sum(1 for r in self._opp_rows() if r['name'] == card and not r.get('injected'))
                + len(self.rejected.get(card, ())))

    def observe_board(self, tick, cards):
        """Once per record: the opponent cards perceived on the board (before the sanitizer). Returns the
        non-members whose board evidence now asks for a place in a full set."""
        cards = set(cards)
        self.window.append(cards)
        for c in cards:
            self.seen.setdefault(c, []).append(tick)
            if sum(c in w for w in self.window) >= self.persist_k:
                self.board[c] += 1
                self.last[c] = tick
        if not self.evict:
            return []
        m = self.members()
        return sorted(c for c in cards if c not in m and len(m) >= self.cap and self.board[c] >= self.board_need)

    def reject(self, card, tick, x, y):
        """A perceived play of a non-member while the set is full (kept as evidence, not accepted)."""
        got = self.rejected.setdefault(card, [])
        if not any(abs(tick - t) <= self.dup_ticks for t, _, _ in got):
            got.append((tick, x, y))
        self.last[card] = max(tick, self.last.get(card, tick))

    def _last(self, card):
        t = [r['tick'] for r in self._opp_rows() if r['name'] == card]
        return max(t + [self.last.get(card, -1)])

    def contradicted(self, card, tick):
        """A unit card none of whose plays the board confirmed (no unit of it perceived near any play time)."""
        t = [r['tick'] for r in self._opp_rows() if r['name'] == card and not r.get('injected')]
        if not t or not self.spawns(card) or tick - max(t) < self.confirm_ticks:
            return False
        seen = self.seen.get(card, ())
        for p in t:
            i = bisect_left(seen, p - 20)
            if i < len(seen) and seen[i] <= p + self.confirm_ticks:
                return False
        return True

    def victim(self, newcomer, tick):
        """The member to evict so `newcomer` can enter at `tick`, or None."""
        m = self.members()
        if not self.evict or newcomer in m or len(m) < self.cap:
            return None
        n_plays, n_board = self.plays(newcomer), self.board[newcomer]
        if n_plays < min(self.events_need, self.contra_need) and n_board < self.board_need:
            return None
        contra = {c for c in m if self.contradicted(c, tick) and self.plays(c) <= self.contra_plays}
        weak = contra | {c for c in m if not self.spawns(c) and self.plays(c) <= self.weak_plays
                         and self.board[c] <= self.weak_board}
        if not weak:
            self.stats['evict_refused'] += 1
            return None
        w = min(weak, key=lambda c: (c not in contra, self.plays(c), self.board[c], self._last(c), c))
        need = self.contra_need if w in contra else self.events_need
        return w if n_plays >= need or n_board >= self.board_need else None

    def evicted(self, w, x, removed, via_board):
        """Bookkeeping after the translator rewrote the history without `w`: removed = w's (tick, x, y) plays."""
        if w in self.admitted:
            self.admitted.remove(w)
        got = self.rejected.setdefault(w, [])
        for t, px, py in removed:
            if not any(abs(t - u) <= self.dup_ticks for u, _, _ in got):
                got.append((t, px, py))
        self.rejected.pop(x, None)           # x's rejected plays were re-inserted into the history (or are stale)
        if via_board and x not in self.admitted:
            self.admitted.append(x)
        self.stats['evict'] += 1
        self.stats[f'evict:{w}->{x}'] += 1
