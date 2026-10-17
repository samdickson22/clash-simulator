"""Sim A/B of the cycle model on live-diag's noisy opponent history (exploration).

    histnoise:raw:cyc-hard:<player>   live-diag's raw stream (spells unseen + phantoms, no guard; history_noise.py), then
                                      the deployed translator's guard (LiveTranslator._consistent: a DerivedD1 mirror;
                                      cycle conflicts and 9th distinct cards dropped) on BOTH the belief events and the D1
                                      rows. = today's live bot.
    histnoise:raw:cyc-soft:<player>   same raw stream and the same guard on the D1 rows, but a cycle conflict reaches the
                                      belief as PublicEvent(tick, 'card?', name, amount=P(real)) (bot/cyclemodel/preal.py
                                      on sim features); needs BOT_CYCLE_MODEL=soft. = the translator hand-off diff.
                                      9th distinct cards stay dropped.
The guard decision for each opponent card item is made once, in stream order, and shared by both streams (both are
prefix-stable). Per game, counts are added to live-diag's noise counts (ours_diag rows 'noise'): cyc_conflicts,
cyc_conflict_phantom (sim truth: the item is a phantom), cyc_p_real_sum / cyc_p_phantom_sum (calibration), cyc_ninth,
and the belief's cycle_stats (belief_*).

Sim features for P(real) (live uses LiveTranslator.drop_features): kind = building (a Building unit in the runtime
config) / spawner_family (a spawner output card, or a troop that spawns: history_noise.SPAWNS) / troop; plays_between
and ticks_since_same over the accepted opponent plays; spawner_same_family_dist = 0 if an accepted opponent play of a
spawner whose output is this card is within the last 600 ticks, else 99 (no positions in the event stream).

Runner (ours_diag with these names resolvable):
    BOT_CYCLE_MODEL=soft python -m bot.cyclemodel.ab --out DIR --candidate histnoise:raw:cyc-hard:X,histnoise:raw:cyc-soft:X \
        --opponents LIVE-K4CW-r16,R3a --games 100 --base B --decks e16bl --workers W
"""
from __future__ import annotations

from dataclasses import replace

SPAWNER_WINDOW = 600


class CycleGuardPlayer:
    def __init__(self, rt, inner, mode, name):
        if mode not in ('hard', 'soft'):
            raise ValueError(mode)
        self.rt, self.inner, self.mode, self.name = rt, inner, mode, name
        self.deadline_seconds = getattr(inner, 'deadline_seconds', None)

    def __getattr__(self, k):
        return getattr(self.inner, k)

    def start(self, ctx):
        from derived_d1 import DerivedD1
        from bot.livediag import history_noise
        self.seat = ctx.seat
        self.mirror = DerivedD1(self.rt.R.costs)
        self.dec, self.acc = [], []
        self.noise = history_noise._ACTIVE.get(ctx.seat)        # set by NoisyPlayer.start before inner.start
        self.counts = self.noise.counts if self.noise is not None else {}
        for k in ('cyc_conflicts', 'cyc_conflict_phantom', 'cyc_ninth', 'cyc_soft'):
            self.counts.setdefault(k, 0)
        for k in ('cyc_p_real_sum', 'cyc_p_phantom_sum'):
            self.counts.setdefault(k, 0.)
        self._kinds = {}
        self.inner.start(ctx)

    # -- guard ----------------------------------------------------------------------------------------------------
    def _kind(self, name):
        if name not in self._kinds:
            from bot.livediag.history_noise import SPAWNS
            c = self.rt.R.config['cards'].get(name, {})
            groups = [t for g in c.get('units', ()) for t in (g if isinstance(g, list) else [g])]
            if any(t.get('class') == 'Building' for t in groups):
                k = 'building'
            elif name in set(SPAWNS.values()) or name in SPAWNS:
                k = 'spawner_family'
            else:
                k = 'troop'
            self._kinds[name] = k
        return self._kinds[name]

    def _features(self, tick, name):
        from bot.livediag.history_noise import SPAWNS
        last = max((i for i, (_, n) in enumerate(self.acc) if n == name), default=None)
        near = any(SPAWNS.get(n) == name and tick - t <= SPAWNER_WINDOW for t, n in self.acc)
        return dict(kind=self._kind(name), card=name,
                    plays_between=0 if last is None else len(self.acc) - 1 - last,       # as drop_features
                    ticks_since_same=None if last is None else tick - self.acc[last][0],
                    spawner_same_family_dist=0. if near else 99., revealed=len(self.mirror.revealed))

    def _is_phantom(self, tick, name):
        if self.noise is None:
            return None
        return any(ph is not None and ph == (tick, name) for _, _, ph in self.noise._dec.values())

    def _decide(self, j, tick, name):
        if j < len(self.dec):
            if self.dec[j][0] != (tick, name):
                raise ValueError(f'cycle guard streams disagree at opponent item {j}')
            return self.dec[j][1:]
        if j != len(self.dec):
            raise ValueError('cycle guard items out of order')
        from derived_d1 import PublicEvent as D1Event
        m = self.mirror
        m.advance(tick)
        if len(m.revealed | {name}) > 8:
            d = ('ninth', None)
            self.counts['cyc_ninth'] += 1
        elif name in m.queue or len(m.queue) >= 8:
            from bot.cyclemodel.preal import p_real
            p = p_real(self._features(tick, name))
            d = ('conflict', p)
            self.counts['cyc_conflicts'] += 1
            ph = self._is_phantom(tick, name)
            if ph:
                self.counts['cyc_conflict_phantom'] += 1
                self.counts['cyc_p_phantom_sum'] += p
            else:
                self.counts['cyc_p_real_sum'] += p
            if self.mode == 'soft':
                self.counts['cyc_soft'] += 1
        else:
            m.accept(D1Event(tick, 'card', name, 0., 0., 0.))
            self.acc.append((tick, name))
            d = ('ok', None)
        self.dec.append(((tick, name),) + d)
        return d

    def act(self, view):
        events, j = [], 0
        for e in view.info.events:
            if getattr(e, 'kind', None) != 'card':
                events.append(e)
                continue
            d, p = self._decide(j, e.tick, e.name)
            j += 1
            if d == 'ok':
                events.append(e)
            elif d == 'conflict' and self.mode == 'soft':
                events.append(replace(e, kind='card?', amount=float(p)))
        rows, j = [], 0
        for r in view.public_events:
            if r.get('kind') == 'card' and r.get('seat') != self.seat:
                d, _ = self._decide(j, r['tick'], r['name'])
                j += 1
                if d != 'ok':
                    continue
            rows.append(r)
        info = replace(view.info, events=tuple(events))
        return self.inner.act(replace(view, info=info, public_events=rows))

    def close(self):
        bel = getattr(getattr(getattr(self.inner, 'search', None) or self.inner, 'p', None), 'belief', None)
        for k, v in (getattr(bel, 'cycle_stats', None) or {}).items():
            self.counts[f'belief_{k}'] = v
        self.inner.close()


def install():
    """Make 'cyc-<hard|soft>:<player>' resolvable by bot.eval.headline.make_player (ours_diag imports it per worker)."""
    import bot.eval.headline as headline
    if getattr(headline.make_player, '_cyc', False):
        return
    orig = headline.make_player

    def make_player(rt, name):
        if name.startswith('cyc-'):
            mode, _, inner = name[4:].partition(':')
            return CycleGuardPlayer(rt, make_player(rt, inner), mode, name)
        if name.startswith('LIVE-K4L-'):              # the wall-clock live player (bot/live/player.py names)
            from bot.live.player import make_live_player
            return make_live_player(rt, name)
        return orig(rt, name)
    make_player._cyc = True
    headline.make_player = make_player


def main():
    install()
    from bot.livediag import ours_diag
    ours_diag.main()


if __name__ == '__main__':
    main()
