"""Interruptible timed waits for the live player (suffix `-wint`; bot lead live-diag, exploration tier).

LIVE-K4L-...-wint wraps the LivePlayer: a timed wait the search chooses is NOT handed to the session (wait_ticks 0);
the wrapper itself skips decisions until the wait ends, polling the player exactly as the session does during a real
wait (the same view with can_act False, so both tiers keep their tracking), unless
  (a) the number of enemy troops/buildings on our half (contract-v5 rows: enemy flag, troop/building kind, y < 16,
      towers excluded) exceeds its count at the wait's start, or
  (b) a new enemy card event (public_events row of the other seat, kind 'card') arrived;
then it decides at the next search tick (10-tick multiple). Without the suffix nothing here runs.
Sim twin: bot/livediag/variants.py Interruptible (LD-...-wint), RESULTS §5d.
"""
from __future__ import annotations

from dataclasses import replace

from bot.players.base import Decision, SEARCH_INTERVAL, WAIT


def enemy_count(rt, packet):
    obs, names = packet.observation, rt.R.builder.token_names
    n = 0
    for i in [int(j) for j in obs.entity_mask.nonzero()[0]]:
        f, tok = obs.entity_features[i], int(obs.entity_ids[i])
        if f[3] > .5 and (f[4] > .5 or f[5] > .5) and f[1] * 32 < 16 and \
                not (0 <= tok < len(names) and names[tok] in ('Tower', 'KingTower')):
            n += 1
    return n


class Interruptible:
    def __init__(self, rt, live):
        self.rt, self.live = rt, live
        self.name = live.name
        self.deadline_seconds = live.deadline_seconds
        self.interrupts = 0

    def __getattr__(self, name):
        return getattr(self.live, name)

    @property
    def search_disabled(self):              # the live loop's stall guard sets this on the session's player
        return self.live.search_disabled

    @search_disabled.setter
    def search_disabled(self, value):
        self.live.search_disabled = value

    def start(self, ctx):
        self.live.start(ctx)
        self.until, self.n0, self.ev0, self.seat = None, 0, 0, ctx.seat

    def _enemy_events(self, view):
        return sum(1 for e in view.public_events if e.get('seat') != self.seat and e.get('kind') == 'card')

    def _blocked(self, view):
        self.live.act(replace(view, can_act=False))
        return Decision(WAIT, 0, None)

    def act(self, view):
        if self.until is not None and view.tick < self.until:
            grew = enemy_count(self.rt, view.info.packet) > self.n0 or self._enemy_events(view) > self.ev0
            if not grew:
                return self._blocked(view)
            self.until = None
            self.interrupts += 1
            if view.tick % SEARCH_INTERVAL:
                return self._blocked(view)
        elif self.until is not None:
            self.until = None
        d = self.live.act(view)
        if d.wait_ticks and view.can_act:
            self.until = view.tick + d.wait_ticks
            self.n0, self.ev0 = enemy_count(self.rt, view.info.packet), self._enemy_events(view)
            if d.stats is not None:
                d.stats = dict(d.stats, timed_wait=d.wait_ticks, interrupts=self.interrupts)
            d = Decision(d.action, 0, d.stats)
        return d

    decide = act

    def close(self):
        self.live.close()
