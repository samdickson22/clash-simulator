"""PERC-<arm>:<player>: a player that sees the game ONLY through synthetic perception at a noise level (LIVE track).

    'PERC-p42:LIVE-fast-it5s2', 'PERC-births:K4C-r16', 'PERC-p70:LIVE-K4CW-r16-w150-t4', ...

Each poll: the true seat view -> SynthPerception record (schema v1, card-level) -> replay.NOISE_GRID[arm] noise ->
LiveTranslator (plays from births unless the arm is 'events') -> a PublicView with the same pending reservation
(rebuilt with CommandQueue.own_packet) -> the inner player. The harness executes the inner player's action on the
true game, so bot.eval.headline measures the WIN RATE cost of a perception level, not just decision agreement.
The synthesiser reads our engine's view of the acting seat; seat 1 views are rotated by the builder already, and the
record is in that seat's own frame (owner 0 = the acting seat), exactly what perception produces for 'us'.
"""
from __future__ import annotations

import numpy as np

from bot.players.base import Decision, PublicView, WAIT


class PercPlayer:
    def __init__(self, rt, arm, inner):
        from bot.live.replay import NOISE_GRID, PLAYS_FROM
        if arm not in NOISE_GRID:
            raise ValueError(f'unknown perception arm {arm!r}; known {sorted(NOISE_GRID)}')
        self.rt, self.arm, self.inner = rt, arm, inner
        self.noise, self.plays_from = NOISE_GRID[arm], PLAYS_FROM.get(arm, 'births')
        self.name = f'PERC-{arm}:{inner.name}'
        self.deadline_seconds = inner.deadline_seconds
        self.errors = 0

    def start(self, ctx):
        from bot.live.synth import SynthPerception
        from bot.live.translate import LiveTranslator
        from clasher.analysis.loss_review.delay_fixes import CommandQueue
        self.ctx = ctx
        self.synth = SynthPerception(self.rt)
        self.tr = LiveTranslator(self.rt, list(ctx.own_order), plays_from=self.plays_from)
        self.tr.set_own_order(ctx.own_order)
        self.cards = [c for c in sorted(self.rt.R.costs) if self.synth.cb.main.get(c)]
        self.rng = np.random.default_rng([ctx.seed, ctx.seat, 0x9e4c])
        self.queue = CommandQueue(ctx.command_delay, 1)
        self.inner.start(ctx)

    def act(self, view: PublicView) -> Decision:
        from bot.live.synth import noisy
        own_view = view if view.seat == 0 else _as_seat0(view)
        record = noisy(self.synth.record(own_view), self.noise, self.rng, list(self.ctx.own_order), self.cards)
        try:
            info = self.tr.information(record)
            info = _with_seat(info, view.seat)
            self.queue.pending[:] = list(view.pending)
            try:
                reserved = self.queue.own_packet(info, self.rt.R.builder)
            except ValueError:
                reserved = info
            pv = PublicView(view.tick, view.seat, info, reserved, _public_rows(self.tr, view.seat), view.pending,
                            view.can_act)
        except Exception:
            self.errors += 1
            return Decision(WAIT, stats=None if not view.can_act else {'perc_error': 1})
        d = self.inner.act(pv)
        if view.can_act and d.action < WAIT:
            # The live client ignores a tap it cannot honour (slot empty/reserved, not enough elixir): check the
            # action against the TRUE state on a scratch queue; a misread slot still plays the real slot's card.
            scratch = type(self.queue)(self.ctx.command_delay, 1)
            scratch.pending[:] = list(view.pending)
            try:
                scratch.submit(view.info, int(d.action), self.rt.R.costs, self.rt.R.builder)
            except ValueError:
                self.rejected = getattr(self, 'rejected', 0) + 1
                return Decision(WAIT, 0, dict(d.stats or {}, rejected_tap=True))
        return d

    def close(self):
        self.inner.close()


def _as_seat0(view):
    """The builder already rotates seat 1's packet into its own frame; the synthesiser only needs seat == 0 and the
    public plays rotated into that frame with seats swapped (owner 0 = us)."""
    rows = [dict(e, seat=1 - e['seat'], x=18 - e['x'], y=32 - e['y']) for e in view.public_events]
    return PublicView(view.tick, 0, view.info, view.reserved, rows, view.pending, view.can_act)


def _with_seat(info, seat):
    if seat == 0:
        return info
    from dataclasses import replace
    return replace(info, seat=seat)


def _public_rows(tr, seat):
    """Translator D1 rows are in our frame with owner 0 = us; the players expect absolute seats/coordinates."""
    if seat == 0:
        return tr.public_events
    return [dict(e, seat=1 - e['seat'], x=18 - e['x'], y=32 - e['y']) for e in tr.public_events]
