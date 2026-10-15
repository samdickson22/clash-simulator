"""Translator audit under PERC noise (bot lead, diagnostic only; reads the truth, never decides).

    'AUD:PERC-emp-sr1u50:<player>'     outermost: the view it receives is the TRUE view

Per game it records how the LIVE translator (bot/live/translate.py + resync.py, unmodified) turned unit/event noise
into the opponent's revealed card set and the board:
  * the perceived revealed set (translator plays[1], resync-injected plays included) vs the true one;
  * `wrong` cards (perceived, never truly played) and when the perceived set first held 8 cards with a wrong one
    (from then on the deck-rule board sanitizer drops every unit of the unrevealed true card, and
    'ninth_enemy_card_dropped' drops its plays);
  * board_dropped:1:<card> split by whether <card> is a true opponent card (real units dropped) or not;
  * the translator's stream/resync counters.
"""
from __future__ import annotations

from collections import Counter


class AuditPlayer:
    def __init__(self, inner):
        self.inner, self.name = inner, f'AUD:{inner.name}'
        self.deadline_seconds = inner.deadline_seconds

    @property
    def decisions(self):
        return getattr(self.inner, 'decisions', [])

    def start(self, ctx):
        self.ctx = ctx
        self.polls = Counter()
        self.timeline = []          # (tick, perceived revealed, true revealed so far) on change
        self.inner.start(ctx)

    def _perc(self):
        from bot.live.perc import PercPlayer
        from bot.noise.player import find
        return find(self.inner, PercPlayer)

    def act(self, view):
        d = self.inner.act(view)
        p = self._perc()
        tr = getattr(p, 'tr', None)
        if tr is None:
            return d
        opp = 1 - view.seat
        true_rev = frozenset(e['name'] for e in view.public_events if e.get('kind', 'card') == 'card' and e['seat'] == opp)
        perc_rev = frozenset(n for _, n in tr.plays[1])
        if not self.timeline or self.timeline[-1][1:] != (perc_rev, true_rev):
            self.timeline.append((view.tick, perc_rev, true_rev))
        self.polls['n'] += 1
        self.polls['perc8'] += len(perc_rev) >= 8
        return d

    def summary(self):
        p = self._perc()
        tr = getattr(p, 'tr', None)
        if tr is None or not self.timeline:
            return {}
        true_final = self.timeline[-1][2]
        perc_final = self.timeline[-1][1]
        wrong_final = perc_final - true_final
        first8 = first8w = None
        for t, pr, _ in self.timeline:
            if len(pr) >= 8 and first8 is None:
                first8 = t
            if len(pr) >= 8 and (pr - true_final) and first8w is None:
                first8w = t
        st = tr.stats
        drop_true = sum(v for k, v in st.items() if k.startswith('board_dropped:1:') and k.split(':', 2)[2] in true_final)
        drop_false = sum(v for k, v in st.items() if k.startswith('board_dropped:1:') and k.split(':', 2)[2] not in true_final)
        drop_true_cards = sorted({k.split(':', 2)[2] for k, v in st.items() if k.startswith('board_dropped:1:')
                                  and k.split(':', 2)[2] in true_final and v})
        keys = ('board_dropped', 'board_unrevealed_opp_kept', 'ninth_enemy_card_dropped', 'cycle_conflict_dropped:0',
                'cycle_conflict_dropped:1', 'resync', 'resync_injected', 'resync_failed', 'resync_skip_duplicate',
                'late_event_retimed', 'future_event_clamped')
        out = dict(true_rev=len(true_final), perc_rev=len(perc_final), wrong=sorted(wrong_final),
                   missing=sorted(true_final - perc_final), first8=first8, first8_wrong=first8w,
                   polls=self.polls['n'], drop_opp_truecard=drop_true, drop_opp_falsecard=drop_false,
                   drop_truecards=drop_true_cards,
                   drop_own=sum(v for k, v in st.items() if k.startswith('board_dropped:0:')),
                   restarts=getattr(tr, 'restarts', 0), perc_errors=getattr(p, 'errors', 0),
                   opp_plays_perc=len(tr.plays[1]),
                   opp_injected=sum(1 for r in tr.public_events if r['seat'] == 1 and r.get('injected')))
        out.update({k: st.get(k, 0) for k in keys})
        rs = getattr(tr, 'revealed', None)
        if rs is not None and hasattr(rs, 'board'):   # RevealedSet evidence at the end: card -> [plays, board, true?]
            cards = rs.members() | set(rs.rejected) | true_final
            out['rev_evidence'] = {c: [rs.plays(c), rs.board[c], int(c in true_final), int(c in rs.members())]
                                   for c in sorted(cards)}
        ev = {k[6:]: v for k, v in st.items() if k.startswith('evict:') and v}   # RevealedSet evictions W->X
        if ev or st.get('evict_refused') or st.get('evict_inconsistent'):
            out.update(evict=sum(ev.values()), evict_refused=st.get('evict_refused', 0),
                       evict_inconsistent=st.get('evict_inconsistent', 0), evictions=ev,
                       evict_wrong_out=sum(v for k, v in ev.items() if k.split('->')[0] not in true_final),
                       evict_true_in=sum(v for k, v in ev.items() if k.split('->')[1] in true_final))
        return out

    def close(self):
        self.inner.close()
