"""Own hand kept in sync with what the client SHOWS: slot UI state, reliable-read reconciliation, a tap guard.

Measured on s17-s22 against video ground truth (slot_audit.py; 102k frame-slot reads): the HUD head's read of a
COLOURED (affordable) slot is right 95-99.8% of the time at p >= .1 (the deck-constrained assignment), but a GREYED
slot is right only 59-96% (greyed Archers 18%, Cannon 52%: confidently read as another card). The tracker
(bot/live/translate.OwnTracker) trusts its own history and re-anchors only on a whole 5-card HUD state repeated on 4
polls, which greyed-slot noise prevents, so one wrong opening read or wrong play kept a slot mislabelled for the rest of
the match. The hash-checked historical baseline scored 42 wrong of 542 actions. MEASURE-mode sync replay scored
4 raw wrong of 517, all four guard-flagged; 25 baseline actions were omitted. Zero measured residual is not an
enforced recovery result.

- handui.slot_ui(frame): 'empty' (the blue crown placeholder) / 'coloured' / 'greyed' per hand slot, from pixel
  saturation. A UI property of the client, not a perception rule; drive.py logs it in rec['hand']['ui'].
- ReconcilingOwnTracker: before the usual tracking, a COLOURED slot read (p >= coloured_p) or a confident Next read
  (p >= next_p) that disagrees with the tracked state on `sync_polls` distinct captured frames moves that card into that
  place in every hypothesis (a swap, so hand + queue stay a permutation of the deck). Greyed reads are never used:
  the base tracker gets every other slot (greyed, empty, p < coloured_p, a pending command's) as unread, because the deck-constrained hand is always a 'valid' state
  and its whole-state re-anchor fired on 4 polls of greyed noise (s22-m03 n314/373: Valkyrie <-> Minions).
  The slot of a pending command is left alone (the command channel owns it until it completes), and nothing syncs
  while a card slides into an empty slot (the HUD animates: coloured misreads, the preview already shows the
  following card).
- SyncSession(LiveSession): waits for four reliable coloured cards on 2 distinct stable frames before
  taking the opening order, and guards every tap: a play is not submitted on a slot that is empty, greyed (the bot
  only plays affordable cards, so a greyed slot means the tracked card is wrong or the frame is stale) or coloured with
  a HUD read of another card or without reliable identity. guard='measure' only counts (replay); 'enforce' refuses.
  Opening uncertainty/refusals latch hold_reason after 24 frames/refusals or 6 seconds; the driver must handle
  that explicit fail-closed status. Reliable hand cards may start with unknown queue order if Next is noisy.
Without rec['hand']['ui'] everything falls back to the base behaviour.
"""
from collections import Counter
from dataclasses import replace
import math
from numbers import Real

from bot.live.translate import LiveSession, LiveTranslator, OwnTracker


def confident(p, threshold):
    return (isinstance(p, Real) and not isinstance(p, bool) and math.isfinite(p)
            and threshold <= p <= 1.)


class ReconcilingOwnTracker(OwnTracker):
    sync_polls = 2
    coloured_p = .1
    next_p = .9

    def __init__(self, deck, stats=None, order=None, known=5):
        self.ui, self.busy, self._sync = None, set(), {}
        self.frame_ts = self._last_sync_frame = None
        self._hud_receipt = self._applying_hud = None
        super().__init__(deck, stats=stats, order=order, known=known)

    def play(self, tick, card):
        super().play(tick, card)
        receipt = self._applying_hud
        if (receipt is not None and receipt is self._hud_receipt and
                receipt['poll'] == tick and receipt['command'].card == card):
            receipt['applied'] = True            # only after the exact event's tracker mutation returns

    def _reset_from(self, *a, **kw):
        super()._reset_from(*a, **kw)
        self._sync = {}

    def own(self, tick, elixir, hand, next_card, probs=None, next_prob=None):
        if self.ui is not None:
            for h in self.hyps:
                h.advance(tick)
            frame = self.frame_ts if self.frame_ts is not None else tick
            fresh = frame != self._last_sync_frame
            if fresh:
                self._last_sync_frame = frame
                self._reconcile(list(hand)[:4], next_card, list(probs or [])[:4], next_prob)
            # the base tracker sees only the reads the sync trusts (coloured, p >= coloured_p, not a pending slot):
            # its hypothesis scoring and its whole-state re-anchor (4 polls of a 'valid' state, which the
            # deck-constrained hand always is) fired on greyed noise (s22-m03 n314/373)
            pr = list(probs or [])[:4] + [None]*4
            hand = [c if (fresh and i < len(self.ui) and self.ui[i] == 'coloured' and i not in self.busy
                          and confident(pr[i], self.coloured_p)) else None
                    for i, c in enumerate(list(hand)[:4])]
            probs = [p if confident(p, self.coloured_p) else 0. for p in pr[:4]]
            if not fresh or not confident(next_prob, self.next_p):
                next_card, next_prob = None, 0.
            # Reconciliation owns visual corrections. The inherited re-anchor bypasses BUSY protection.
            self._streak, self._last_valid = 0, None
        return super().own(tick, elixir, hand, next_card, probs, next_prob)

    def _reconcile(self, raw, next_card, probs, next_prob):
        raw = raw + [None]*(4 - len(raw)); probs = probs + [None]*(4 - len(probs))
        b = self.hyps[self.best]
        seen = {}
        if any(None in h.hand for h in self.hyps) or len(self.ui) != 4 or 'empty' in self.ui:
            # a card is sliding into an empty slot: the HUD animates (coloured misreads, the preview already shows
            # the following card), so no sync until the hand is full again (s19-m04 n1007)
            self._sync = {}
            return
        for i in range(4):
            c, p = raw[i], probs[i]
            if (self.ui[i] == 'coloured' and c in self.deck and confident(p, self.coloured_p)
                    and c not in self.played[-4:] and i not in self.busy and b.hand[i] is not None and b.hand[i] != c):
                seen[('slot', i)] = c
        # the next read only reorders the queue: a card the tracker holds in hand is moved by a coloured slot read,
        # never by the preview (that would put a guessed card into a slot nobody can see; s19-m02 n1233)
        if (next_card in self.deck and confident(next_prob, self.next_p) and b.queue
                and next_card not in self.played[-3:] and b.queue[0] != next_card and next_card in b.queue):
            seen[('next', 0)] = next_card
        self._sync = {k: (c, self._sync[k][1] + 1 if k in self._sync and self._sync[k][0] == c else 1)
                      for k, c in seen.items()}
        for (kind, i), (c, k) in list(self._sync.items()):
            if k < self.sync_polls:
                continue
            if kind == 'slot' and any(i in self.busy or
                    (c in h.hand and h.hand.index(c) in self.busy) for h in self.hyps):
                continue
            for h in self.hyps:
                self._swap(h, kind, i, c)
            self.stats[f'own_sync:{kind}'] += 1
            del self._sync[(kind, i)]

    def _swap(self, h, kind, i, c):
        if kind == 'slot':
            if c in self.played[-4:] or i in self.busy or (c in h.hand and h.hand.index(c) in self.busy):
                return
            t = h.hand[i]
            if t is None or t == c:
                return
            if c in h.hand:
                j = h.hand.index(c); h.hand[i], h.hand[j] = c, t
            elif c in h.queue:
                q = h.queue.index(c); h.hand[i], h.queue[q] = c, t
        elif c not in self.played[-3:] and h.queue and h.queue[0] != c and c in h.queue:
            q = h.queue.index(c); h.queue[0], h.queue[q] = c, h.queue[0]


class SyncTranslator(LiveTranslator):
    def __init__(self, rt, own_deck, **kw):
        super().__init__(rt, own_deck, **kw)
        self.own_tracker = ReconcilingOwnTracker(own_deck, stats=self.stats)

    def accept_events(self, record):
        # Keep the inherited public acceptance rules, but bind a physical acknowledgment to its exact event.
        from ownplay import WINDOW
        for event in sorted(record.get('events', ()), key=lambda e: int(e['tick'])):
            physical = getattr(self, '_physical_plays', {}).get(str(event.get('card')))
            if (event.get('_hud_receipt') is None and int(event.get('owner', 1)) == 0 and
                    physical is not None and 0 <= record['tick'] - physical <= WINDOW):
                self.stats['own_event_dup_dropped'] += 1
                continue                        # same existing duplicate window, including non-public physical plays
            self.own_tracker._applying_hud = event.get('_hud_receipt')
            try:
                super().accept_events(dict(record, events=[event]))
            finally:
                self.own_tracker._applying_hud = None

    def hud(self, record):
        h = record.get('hand') or {}
        self.own_tracker.ui = h.get('ui') if isinstance(h, dict) else None
        self.own_tracker.frame_ts = record.get('ts_ms')
        return super().hud(record)


class _GuardedPlayer:
    def __init__(self, inner, sess):
        self.inner, self.sess = inner, sess

    def __getattr__(self, k):                # search_disabled etc. reach the real player
        return getattr(self.inner, k)

    def __setattr__(self, k, v):
        if k in ('inner', 'sess'):
            object.__setattr__(self, k, v)
        else:
            setattr(self.inner, k, v)

    def start(self, ctx):
        return self.inner.start(ctx)

    def close(self):
        return self.inner.close()

    def act(self, view):
        from bot.players.base import Decision, WAIT
        if self.sess.guard == 'enforce' and self.sess.hold_reason:
            return Decision(WAIT, stats=dict(handsync_hold=self.sess.hold_reason))
        h = (self.sess._rec or {}).get('hand') or {}
        ui = h.get('ui') if isinstance(h, dict) else None
        unavailable = (self.sess.guard == 'enforce' and view.can_act and
                       isinstance(ui, (list, tuple)) and len(ui) == 4 and
                       all(u in ('empty', 'greyed') for u in ui))
        # The spending animation can leave the old pink bar visible after a command completes.
        # Positive UI unavailability denies new policy actions, but both pollers must still advance.
        policy_view = self.sess._slot_permission_view(view)
        policy_view = replace(policy_view, can_act=False) if unavailable else policy_view
        d = self.inner.act(policy_view)
        if unavailable:
            self.sess.tr.stats['handsync_no_playable_hand'] += 1
            d.stats = dict(d.stats or {}, handsync_no_action='all_slots_unavailable')
        # Keep the ORIGINAL channel permission: a player ignoring the denied view must still hit the guard.
        if view.can_act and d.action < WAIT:
            why = self.sess.tap_guard(int(d.action))
            if why:
                self.sess.tr.stats[f'tap_guard:{why}'] += 1
                self.sess.guarded.append((int(view.tick), int(d.action), why))
                if self.sess.guard == 'enforce':
                    self.sess._refusals += 1
                    if self.sess._refusal_since is None:
                        self.sess._refusal_since = self.sess._frame_ms
                    age = self.sess._frame_ms - self.sess._refusal_since
                    if self.sess._refusals >= self.sess.refusal_limit or age >= self.sess.hold_ms:
                        self.sess._hold('tap_guard:' + why)
                    d.stats = dict(d.stats or {}, tap_guard=why)
                    if self.sess.hold_reason:
                        d.stats['handsync_hold'] = self.sess.hold_reason
                    d.action = WAIT
            else:
                self.sess._refusals, self.sess._refusal_since = 0, None
        return d


class SyncSession(LiveSession):
    """LiveSession with the SyncTranslator, a dealt-opening wait and the tap guard (module doc)."""
    guard_p = .1
    hold_ms = 6000
    opening_limit = refusal_limit = 24

    def __init__(self, rt, player, own_deck, *, guard='enforce', slot_permission_mode='legacy', **kw):
        if slot_permission_mode not in ('legacy', 'required'):
            raise ValueError('invalid slot permission mode')
        self._permission_session_id = None
        if slot_permission_mode == 'required':
            from uuid import uuid4
            self._permission_session_id = uuid4().hex
            from clasher.rl.public_observation import ConfidenceAwareActorObservation, SlotPermission
            from dataclasses import fields
            required = {'slot_permission', 'slot_permission_capture_id',
                        'slot_permission_poll_tick', 'slot_permission_mode'}
            if not required <= {f.name for f in fields(ConfidenceAwareActorObservation)}:
                raise ValueError('slot permission backend unavailable')
            if getattr(player, 'slot_permission_mode', None) != 'required':
                raise ValueError('required slot permission player must be constructor-pinned')
        self.slot_permission_mode = slot_permission_mode
        self.last_slot_permission = None
        self._permission_serial = 0
        self._permission_last_actable_frame = None
        kw.setdefault('translator', SyncTranslator(rt, own_deck))
        super().__init__(rt, player, own_deck, **kw)
        self.player = _GuardedPlayer(player, self)
        self.guard, self.guarded, self._rec, self._open = guard, [], None, None
        self.hold_reason = None
        self._opening_since = self._refusal_since = None
        self._opening_frames = self._refusals = 0
        self._opening_frame = None
        self._frame_ms = 0.
        self._confirm_frame = None
        self._confirm_command = self._confirm_observation = None
        self._hud_confirmation = None

    def _hold(self, reason):
        """Latched fail-closed status. Driver must report/recover by replacing the session, never force a tap."""
        if self.hold_reason is None:
            self.hold_reason = reason
            self.tr.stats['handsync_hold:' + reason] += 1

    def _poll(self, record, poll, catch_up=False):
        # Catch-up reuses this capture but strips its buffered/current external events. Confirm only in the
        # actual poll, where the complete event batch can suppress duplicate HUD synthesis.
        self._confirm_catch_up = catch_up
        try:
            return super()._poll(record, poll, catch_up=catch_up)
        except Exception:
            if getattr(self, '_hud_confirmation', None) is not None:
                self._hold('hud_confirmation_transaction')
            raise
        finally:
            self._confirm_catch_up = False
            self._hud_confirmation = None
            self.tr.own_tracker._hud_receipt = None

    def _confirm_pending(self, record, poll):
        h = record.get('hand') or {}
        if isinstance(h, dict) and h.get('ui') is not None and getattr(self, '_confirm_catch_up', False):
            return
        if not isinstance(h, dict) or h.get('ui') is None:
            return super()._confirm_pending(record, poll)
        command = self.ch.pending[0] if self.ch.pending else None
        if command is not getattr(self, '_confirm_command', None):
            self._confirm_command = command
            self._confirm_frame = self._confirm_observation = None
            self._evidence = 0
            self._hud_confirmation = None
        if command is None:
            self._evidence = 0
            return
        frame = record.get('ts_ms')
        if frame == self._confirm_frame:
            return
        self._confirm_frame = frame
        if any(t >= command.submitted and c == command.card for t, c in self.tr.plays[0]):
            return
        if any(e.get('owner') == 0 and e.get('card') == command.card for e in record.get('events', ())):
            self._evidence, self._confirm_observation = 0, None
            return                              # the external event will advance tracking in this same poll
        # A pending action is not an accepted play. Only positive empty UI or a reliable, stable coloured
        # replacement can confirm it; greyed/unverified identity noise must never create an own-play event.
        slot = command.action // 576
        ui, cards, probs = h.get('ui') or [], h.get('cards') or [], h.get('probs') or []
        observation = None
        if slot < len(ui) and ui[slot] == 'empty':
            observation = ('empty',)
        elif (slot < min(len(ui), len(cards), len(probs)) and ui[slot] == 'coloured'
              and confident(probs[slot], self.guard_p) and cards[slot] in self.own_deck
              and cards[slot] != command.card):
            held = [c for i, c in enumerate(self.tr.own_tracker.hand) if i != slot and c is not None]
            if cards[slot] not in held:
                observation = ('coloured', cards[slot])
        previous = getattr(self, '_confirm_observation', None)
        self._evidence = (self._evidence + 1 if observation == previous else 1) if observation is not None else 0
        self._confirm_observation = observation
        if self._evidence >= self.confirm_polls:
            self._evidence = 0
            self._confirm_observation = None
            # Physical completion and public stream acceptance are separate: an unknown opening queue can
            # make the public cycle guard reject a real, HUD-confirmed deployment. Commit only after this
            # exact command's synthesized play was applied once by the own tracker; never infer from a slot swap.
            receipt = dict(command=command, poll=poll, applied=False)
            self._hud_confirmation = self.tr.own_tracker._hud_receipt = receipt
            row, col = divmod(command.action % 576, 18)
            record['events'] = list(record.get('events') or ()) + [dict(owner=0, card=command.card,
                                                                      x=col+.5, y=row+.5, tick=poll,
                                                                      _hud_receipt=receipt)]
            self.tr.stats['own_play_confirmed_by_hud'] += 1

    def _reconcile(self, info):
        # With visual corrections enabled, tracked slot changes alone cannot acknowledge execution.
        if self.tr.own_tracker.ui is None:
            return super()._reconcile(info)
        if self.ch.pending:
            c = self.ch.pending[0]
            public = any(t >= c.submitted and n == c.card for t, n in self.tr.plays[0])
            receipt = getattr(self, '_hud_confirmation', None)
            hud = (receipt is not None and receipt['command'] is c and receipt['poll'] == info.tick
                   and receipt['applied'])
            if public or hud:
                self.ch.finish(True)
                if hud:
                    if not hasattr(self.tr, '_physical_plays'):
                        self.tr._physical_plays = {}
                    self.tr._physical_plays[c.card] = info.tick
                    self.tr.stats['own_command_completed_by_hud'] += 1
                    if not public:
                        self.tr.stats['own_command_hud_public_dropped'] += 1
                self._hud_confirmation = None
            elif receipt is not None:
                self._hold('hud_confirmation_unapplied')
            elif info.tick - c.submitted > self.expire:
                self.ch.finish(False)

    def step(self, record):
        # Capture identity survives LiveSession's rewritten catch-up ticks. Legacy records use their input tick.
        record = dict(record)
        if record.get('ts_ms') is None:
            capture_ms = record.get('timestamp_ms')  # native LivePerception schema
            if isinstance(capture_ms, Real) and math.isfinite(capture_ms):
                record['ts_ms'] = float(capture_ms)
            else:
                tick = record.get('tick')
                if tick is None:
                    tick = self.tr.tick_of(record)
                    record['tick'] = tick
                record['ts_ms'] = float(tick)*50
        self._frame_ms = float(record['ts_ms'])
        h = record.get('hand') or {}
        ui = h.get('ui') if isinstance(h, dict) else None
        if self.started and self.tr.own_tracker.ui is not None and ui is None:
            self._evidence = 0
            self._hud_confirmation = self.tr.own_tracker._hud_receipt = None
            self._hold('missing_hand_ui')
        if self.guard == 'enforce' and self.hold_reason:
            return None
        if not self.started and ui is not None:
            cards, probs = tuple(h.get('cards') or ()), list(h.get('probs') or ())
            reliable = (len(cards) == len(probs) == len(ui) == 4 and all(u == 'coloured' for u in ui)
                        and len(set(cards)) == 4 and set(cards) <= set(self.own_deck)
                        and all(confident(p, self.guard_p) for p in probs))
            fresh = self._opening_frame != self._frame_ms
            if self._opening_since is None:
                self._opening_since = self._frame_ms
            previous = self._open
            stable = fresh and reliable and previous is not None and previous[0] == cards
            if fresh:
                self._opening_frame = self._frame_ms
                self._opening_frames += 1
                nxt = h.get('next') if confident(h.get('next_prob'), self.tr.own_tracker.next_p) else None
                self._open = (cards, nxt) if reliable else None
            if not stable:
                self.tr.stats['opening_hand_waits'] += 1
                if (self._opening_frames >= self.opening_limit or
                        self._frame_ms - self._opening_since >= self.hold_ms):
                    self._hold('opening_unreliable')
                return None
            # Four stable reliable cards suffice; noisy Next leaves all four queue positions unknown.
            if not (confident(h.get('next_prob'), self.tr.own_tracker.next_p)
                    and previous[1] == h.get('next')):
                record['hand'] = dict(h, next=None, next_prob=0.)
        self._rec = record
        self.tr.own_tracker.busy = {c.action // 576 for c in self.ch.pending}
        return super().step(record)

    def _slot_permission_view(self, view):
        """Private explicit control metadata; all model arrays/own state and reservations retain identity.

        Backend independently binds the actual poll and intersects eligibility only AFTER model features.
        Legacy callers take the original path. This does not replace final tap_guard enforcement.
        """
        if getattr(self, 'slot_permission_mode', 'legacy') == 'legacy':
            return view
        from clasher.rl.public_observation import SlotPermission
        record = self._rec or {}
        frame = record.get('ts_ms')
        captured = record.get('timestamp_ms', frame)
        scope = getattr(self, '_permission_session_id', None)
        scope_valid = type(scope) is str and 0 < len(scope) <= 64
        frame_identifiable = (isinstance(frame, Real) and not isinstance(frame, bool) and math.isfinite(frame)
                              and float(frame) == self._frame_ms)
        capture_valid = (scope_valid and frame_identifiable
                         and isinstance(captured, Real) and not isinstance(captured, bool) and math.isfinite(captured)
                         and float(frame) == float(captured))
        valid = capture_valid
        h = record.get('hand') or {}
        ui = h.get('ui') if isinstance(h, dict) else None
        valid = valid and isinstance(ui, (list, tuple)) and len(ui) == 4 and all(
            u in ('empty', 'greyed', 'coloured') for u in ui)
        cards, probs = (h.get('cards'), h.get('probs')) if isinstance(h, dict) else (None, None)
        valid = valid and isinstance(cards, (list, tuple)) and len(cards) == 4
        valid = valid and isinstance(probs, (list, tuple)) and len(probs) == 4
        # A reused capture may advance catch-up pollers but may not enable a second current decision.
        previous = getattr(self, '_permission_last_actable_frame', None)
        if view.can_act and previous is not None and (not valid or float(frame) <= previous):
            valid = False
        if valid:
            reasons = tuple(self.tap_guard(i*576) or 'eligible' for i in range(4))
            allowed = tuple(r == 'eligible' for r in reasons)
        else:
            reasons, allowed = ('invalid_or_stale_observation',)*4, (False,)*4
        capture_id = scope + ':' + float(frame).hex() if scope_valid and isinstance(frame, Real) and math.isfinite(frame) else 'invalid'
        # Separate packet-side current capture binding is not taken from the permission object.
        current_id = scope + ':' + float(captured).hex() if scope_valid and isinstance(captured, Real) and math.isfinite(captured) else 'missing'
        poll = int(view.tick)
        if float(view.tick) != poll or poll < 0:
            raise ValueError('invalid permission poll')
        permission = SlotPermission(allowed=allowed, capture_id=capture_id, poll_tick=poll, reasons=reasons)
        packet = replace(view.reserved.packet, slot_permission=permission,
                         slot_permission_capture_id=current_id, slot_permission_poll_tick=None,
                         slot_permission_mode='required')
        # Consume the primary capture even when its independent binding/UI was denied.
        # Correcting metadata alone cannot authorize the same image at a later poll.
        if view.can_act and frame_identifiable:
            self._permission_last_actable_frame = max(float(frame), previous) if previous is not None else float(frame)
        self._permission_serial = getattr(self, '_permission_serial', 0) + 1
        self.last_slot_permission = dict(allowed=list(allowed), capture_id=capture_id,
                                        current_capture_id=current_id, poll_tick=poll,
                                        reasons=list(reasons), mode='required')
        return replace(view, reserved=replace(view.reserved, packet=packet))

    def tap_guard(self, action):
        """None if the tap may go, else why not: the slot is empty / greyed / coloured with another card read."""
        h = (self._rec or {}).get('hand') or {}
        ui = h.get('ui') if isinstance(h, dict) else None
        if ui is None:
            return None
        slot = action // 576
        card = self.tr.own_tracker.hand[slot]
        if ui[slot] in ('empty', 'greyed'):
            return ui[slot]
        read, p = (h.get('cards') or [None]*4)[slot], (h.get('probs') or [0]*4)[slot]
        if read is None or not confident(p, self.guard_p):
            return 'coloured_unverified'
        if read != card:
            return 'coloured_mismatch'
        return None


def counts(stats):
    return {k: v for k, v in Counter(stats).items() if k.startswith(('own_sync', 'own_command', 'tap_guard', 'opening_hand', 'submit_refused', 'handsync_hold', 'handsync_no_'))}
