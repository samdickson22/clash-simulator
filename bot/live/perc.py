"""PERC-<arm>:<player>: a player that sees the game ONLY through synthetic perception at a noise level (LIVE track).

    'PERC-p42:LIVE-fast-it5s2', 'PERC-births:K4C-r16', 'PERC-p70:LIVE-K4CW-r16-w150-t4', 'PERC-emp:LIVE-fast-it5s2', ...

Empirical arms (LIVE integration, bot/live/empirical.py; noise measured on the 64 validation matches with the
deployed body-fused event tracker, stats in bot/live/empirical-val.json): 'emp' (opponent plays from the play-event
stream), 'emp-births' (from unit births only), 'emp-both' (events + births, de-duplicated: real_replay.BothTranslator).
Detections are Markov-correlated per true unit, as measured (not independent flicker). Empirical arms use the
resync-capable cycle tracking (bot/live/resync.py) and restart the inner player after a history rewrite.

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


EMPIRICAL = {'emp': 'events', 'emp-births': 'births', 'emp-both': 'both'}   # arm -> opponent-play source


def parse_empirical(arm):
    """'emp[-r<N>][-births|-both][-x<part>...]' -> (opponent-play source, stats file, ablated parts) or None.

    -r<N>     noise fitted on perception round N (bot/live/empirical-val-r<N>.json; plain 'emp' = round 1,
              empirical-val.json). 'PERC-emp-r2:LIVE-fast-it5s2' = round-2 perception.
    -s<name>  any fitted variant, bot/live/empirical-val-<name>.json (e.g. a unit-threshold variant 'emp-sr1u50').
    -x<part>  ablation: that noise component is removed (EmpiricalNoise.PARTS), e.g. 'emp-xspell' = round-1 noise
              with perfect opponent spell events. Diagnostic arms for 'which perception error costs win rate'."""
    from bot.live.empirical import STATS, PARTS
    toks = arm.split('-')
    if toks[0] != 'emp':
        return None
    source, stats, ablate = 'events', STATS, []
    for t in toks[1:]:
        if t in ('births', 'both'):
            source = t
        elif t[:1] == 'r' and t[1:].isdigit():
            stats = STATS.with_name(f'empirical-val-r{int(t[1:])}.json')
        elif t[:1] == 's' and t[1:].isalnum():      # any fitted variant: bot/live/empirical-val-<name>.json
            stats = STATS.with_name(f'empirical-val-{t[1:]}.json')
        elif t[:1] == 'x' and t[1:] in PARTS:
            ablate.append(t[1:])
        else:
            raise ValueError(f'unknown empirical arm token {t!r} in {arm!r}')
    return source, stats, frozenset(ablate)


class PercPlayer:
    def __init__(self, rt, arm, inner):
        from bot.live.replay import NOISE_GRID, PLAYS_FROM
        emp = parse_empirical(arm)
        if arm not in NOISE_GRID and emp is None:
            raise ValueError(f'unknown perception arm {arm!r}; known {sorted(NOISE_GRID) + sorted(EMPIRICAL)} + emp-r<N>/-x<part>')
        self.rt, self.arm, self.inner = rt, arm, inner
        if emp is not None:
            import json
            self.noise, self.plays_from = None, emp[0]
            self.stats, self.ablate = json.loads(emp[1].read_text()), emp[2]
        else:
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
        if self.noise is None:          # empirical arms: resync-capable cycle tracking (the deployable stack)
            from bot.live.resync import ResyncTranslator, resync_both
            self.tr = (resync_both()(self.rt, list(ctx.own_order)) if self.plays_from == 'both' else
                       ResyncTranslator(self.rt, list(ctx.own_order), plays_from=self.plays_from))
        else:
            self.tr = LiveTranslator(self.rt, list(ctx.own_order), plays_from=self.plays_from)
        self.tr.set_own_order(ctx.own_order)
        self.cards = [c for c in sorted(self.rt.R.costs) if self.synth.cb.main.get(c)]
        self.rng = np.random.default_rng([ctx.seed, ctx.seat, 0x9e4c])
        if self.noise is None:
            from bot.live.empirical import EmpiricalNoise
            self.channel = EmpiricalNoise(self.stats, self.rng, list(ctx.own_order), ablate=self.ablate)
        self.queue = CommandQueue(ctx.command_delay, 1)
        self.inner.start(ctx)

    def act(self, view: PublicView) -> Decision:
        from bot.live.synth import noisy
        own_view = view if view.seat == 0 else _as_seat0(view)
        if self.noise is None:
            record = self.channel(self.synth.record(own_view))
        else:
            record = noisy(self.synth.record(own_view), self.noise, self.rng, list(self.ctx.own_order), self.cards)
        try:
            info = self.tr.information(record)
            if getattr(self.tr, 'resynced', False):
                from bot.live.resync import restart_if_resynced
                restart_if_resynced(self.tr, self.inner, self.ctx)
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
