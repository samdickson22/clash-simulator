"""Synthetic perception records (schema clasher.live.perception-frame.v1): what a perfect or noisy perception would
emit from our engine's TRUE public view (LIVE track, exploration).

SynthPerception(rt).record(view) -> a perfect record for seat 0:
  units   every troop/building row of the true v5 packet (not towers, spells, projectiles, effects), labelled like the
          perception's dense labels: identity = the CARD that spawned the body (cls = card = that card). The spawning
          card is recovered on the truth side: a new body takes the card of the most recent same-owner play within
          5 tiles / 60 ticks that can spawn it, else a live same-owner spawner of a card that produces it, else a
          vanished same-owner body whose card has it as a death child, else the first card whose units include it.
  towers  six towers (alive, hp fraction) from the globals; hand {cards, next, probs}; elixir; clock_s/phase/
          timestamp_ms (collector.py:379 convention) and 'tick' (the replay aligns on it); events: the accepted public
          plays of both seats (tick, card, tile).
noisy(record, noise, rng, deck) applies Noise:
  recall      P(a true unit is detected)            precision  P(a detected unit has the right card); otherwise its
  jitter      position sd (tiles)                                card is replaced by a random other C56 card
  hp, tower   unit / tower hp-fraction sd           hand       P(a hand slot / next misread as another deck card)
  elixir      elixir sd                              events     'all' | 'own' (perception has no play events: the
  event_drop, event_delay (applied by EventChannel)              opponent's plays must come from unit births)
Detections are independent per frame (flicker), the pessimistic case for tracking.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import math

import numpy as np

TROOP, BUILDING = 0, 1


@dataclass(frozen=True)
class Noise:
    recall: float = 1.
    precision: float = 1.
    jitter: float = 0.
    hp: float = 0.
    tower: float = 0.
    hand: float = 0.
    elixir: float = 0.
    events: str = 'all'
    event_drop: float = 0.
    event_delay: int = 0

    def label(self):
        d = {k: v for k, v in asdict(self).items() if v != Noise.__dataclass_fields__[k].default}
        return 'perfect' if not d else ','.join(f'{k}={v}' for k, v in d.items())


PERFECT = Noise()


def hud_clock(tick):
    """collector.py:379 HUD convention: clock 180..0 then 120..0 (overtime); phase 1/2/3 by elixir rate."""
    clock = max(0, (180 if tick <= 3600 else 300) - max(0, (tick-1)//20))
    return clock, (1 if tick < 2400 else 2 if tick < 4800 else 3)


class SynthPerception:
    def __init__(self, rt):
        from bot.live.births import CardBodies
        self.rt, self.cb = rt, CardBodies(rt)
        self.names = rt.R.builder.token_names
        self.spawns = {}                                  # body -> cards whose main/children/death include it
        for card in self.cb.main:
            for b, _ in self.cb.main[card]:
                self.spawns.setdefault(b, []).append(('main', card))
            for b in self.cb.children[card]:
                self.spawns.setdefault(b, []).append(('child', card))
            for b in self.cb.death[card]:
                self.spawns.setdefault(b, []).append(('death', card))
        self.tracks, self.vanished = [], []                # truth tracks: [body, owner, x, y, card, last]
        self.stats = {}

    def _label(self, body, owner, x, y, tick, plays):
        opts = self.spawns.get(body, [])
        cards = {c for _, c in opts}
        best = None
        for e in plays:
            if e['seat'] == owner and e['name'] in cards and 0 <= tick - e['tick'] <= 60:
                ex, ey = e['x'], e['y']                    # absolute tiles = seat-0 frame = our frame
                d = math.hypot(ex - x, ey - y)
                if d <= 5 and (best is None or (tick - e['tick'], d) < best[0]):
                    best = ((tick - e['tick'], d), e['name'])
        if best:
            return best[1], 'play'
        child = {c for k, c in opts if k == 'child'}
        for t in self.tracks:
            if t[1] == owner and t[4] in child:
                return t[4], 'spawner'
        death = {c for k, c in opts if k == 'death'}
        for t in self.vanished:
            if t[1] == owner and t[4] in death and tick - t[5] <= 40 and math.hypot(t[2]-x, t[3]-y) <= 3:
                return t[4], 'death'
        mains = [c for k, c in opts if k == 'main']
        return (mains or sorted(cards) or [self.names[body[0]]])[0], 'fallback'

    def record(self, view):
        if view.seat != 0:
            raise ValueError('synthesise from the seat-0 view (our frame)')
        obs = view.info.packet.observation
        g = obs.global_features
        tick = int(view.tick)
        plays = [e for e in view.public_events if e.get('kind') == 'card']
        bodies = []
        for token, row in zip(obs.entity_ids[obs.entity_mask], obs.entity_features[obs.entity_mask]):
            kind = int(np.argmax(row[4:9]))
            if kind not in (TROOP, BUILDING) or self.names[int(token)] in ('KingTower', 'Tower'):
                continue
            bodies.append(((int(token), kind), 0 if row[2] > .5 else 1, float(row[0])*18, float(row[1])*32,
                           float(row[9])))
        # match to truth tracks (exact positions: nearest same body/owner within 1.5 tiles)
        free, units, new = list(self.tracks), [], []
        for body, owner, x, y, hp in bodies:
            cand = [t for t in free if t[0] == body and t[1] == owner and math.hypot(t[2]-x, t[3]-y) <= 1.5]
            t = min(cand, key=lambda t: math.hypot(t[2]-x, t[3]-y)) if cand else None
            if t is None:
                card, how = self._label(body, owner, x, y, tick, plays)
                self.stats[how] = self.stats.get(how, 0) + 1
                t = [body, owner, x, y, card, tick]
                new.append(t)
            else:
                free.remove(t)
                t[2], t[3], t[5] = x, y, tick
            units.append(dict(cls=t[4], card=t[4], owner=owner, x=x, y=y, hp_frac=hp, score=1.))
        self.vanished = [t for t in self.vanished + free if tick - t[5] <= 40]
        self.tracks = [t for t in self.tracks if t not in free] + new
        towers = []
        for owner, base in ((0, 8), (1, 11)):
            for side, i in (('left', 0), ('right', 1)):
                hp = float(g[base+i])
                towers.append(dict(owner=owner, kind='princess', side=side, hp_frac=hp, alive=hp > 0, score=1.))
            hp = float(g[base+2])
            alive = hp > 0 if owner == 0 else bool(g[17] > .5)
            towers.append(dict(owner=owner, kind='king', side='center', hp_frac=hp, alive=alive, score=1.))
        own = view.info.own
        clock, phase = hud_clock(tick)
        events = [dict(owner=int(e['seat']), card=e['name'], x=float(e['x']), y=float(e['y']), tick=int(e['tick']))
                  for e in plays]
        return dict(tick=tick, timestamp_ms=50*tick, clock_s=float(clock), phase=phase, units=units, towers=towers,
                    hand=dict(cards=list(own['hand']), probs=[1.]*4,
                              next=own['cycle'][0] if own['cycle'] else None, next_prob=1.),
                    elixir=float(own['elixir']), events=events, schema='clasher.live.perception-frame.v1',
                    hp_kind='fraction_of_max')


def noisy(record, noise, rng, deck, cards):
    """Perception noise on a perfect record (see module docstring). cards: the C56 card names."""
    if noise == PERFECT:
        return record
    units = []
    for u in record['units']:
        if noise.recall < 1 and rng.random() >= noise.recall:
            continue
        u = dict(u)
        if noise.precision < 1 and rng.random() >= noise.precision:
            u['cls'] = u['card'] = str(rng.choice([c for c in cards if c != u['card']]))
        if noise.jitter:
            u['x'] = min(18., max(0., u['x'] + rng.normal(0, noise.jitter)))
            u['y'] = min(32., max(0., u['y'] + rng.normal(0, noise.jitter)))
        if noise.hp:
            u['hp_frac'] = min(1., max(0., u['hp_frac'] + rng.normal(0, noise.hp)))
        units.append(u)
    towers = record['towers']
    if noise.tower:
        towers = [dict(t, hp_frac=min(1., max(.01, t['hp_frac'] + rng.normal(0, noise.tower)))) if t['alive'] else t
                  for t in towers]
    hand = dict(record['hand'])
    if noise.hand:
        hand['cards'] = [(str(rng.choice(deck)) if c is not None and rng.random() < noise.hand else c)
                         for c in hand['cards']]
        if hand['next'] is not None and rng.random() < noise.hand:
            hand['next'] = str(rng.choice(deck))
    elixir = record['elixir']
    if noise.elixir:
        elixir = min(10., max(0., elixir + rng.normal(0, noise.elixir)))
    events = record['events'] if noise.events == 'all' else [e for e in record['events'] if e['owner'] == 0]
    return dict(record, units=units, towers=towers, hand=hand, elixir=elixir, events=events)


class EventChannel:
    """Applies event drop/delay once per event (a dropped event stays dropped), cumulative over a match."""

    def __init__(self, noise, rng):
        self.noise, self.rng, self.fate = noise, rng, {}

    def __call__(self, record):
        if not (self.noise.event_drop or self.noise.event_delay):
            return record
        out = []
        for e in record['events']:
            key = (e['owner'], e['card'], e['tick'], e['x'], e['y'])
            if key not in self.fate:
                drop = bool(self.noise.event_drop) and self.rng.random() < self.noise.event_drop
                delay = int(self.rng.integers(0, self.noise.event_delay+1)) if self.noise.event_delay else 0
                self.fate[key] = None if drop else delay
            delay = self.fate[key]
            if delay is None or e['tick'] + delay > record['tick']:
                continue
            out.append(dict(e, tick=e['tick'] + delay) if delay else e)
        return dict(record, events=out)
