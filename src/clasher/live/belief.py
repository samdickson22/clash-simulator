"""P2: frozen S5-adopted tracker v3 and a conservative own-command ledger."""
from dataclasses import replace
import math
from pathlib import Path
import time
from .contracts import Snapshot
from .loading import tracker_class


class OwnLedger:
    def __init__(self, deck):
        if len(deck) != 8 or len(set(deck)) != 8:
            raise ValueError('Declare eight distinct own deck cards before the match')
        self.deck = tuple(deck)
        self.revision = 0
        self.pending = None
        self.fence = -float('inf')
        self.confirmed_hud = None
        self.verified = []
        self.last_digit = None
        self.anchor_tick = None
        self.anchor_elixir = None
        self.last_tick = 0
        self.verification_serial = 0

    def feedback(self, value):
        if value.revision <= self.revision:
            return False
        self.revision = value.revision
        self.pending = value.pending
        if value.state in ('accepted', 'failed', 'blocked'):
            self.verification_serial += 1
            self.fence = max(self.fence, value.hud.produced_at if value.hud else value.emitted_at)
            self.last_digit = self.anchor_tick = self.anchor_elixir = None
        if value.state == 'accepted':
            self.verified.append(value.card)
            self.verified = self.verified[-8:]
            self.confirmed_hud = value.hud
        return True

    @staticmethod
    def regen(a, b):
        # Public gamedata engine lattice, matching frozen tracker_v3's dependency.
        return sum(max(0, min(b, end)-max(a, start))*rate/10000
                   for start, end, rate in ((0, 2400, 178), (2400, 4800, 357), (4800, 10**9, 537)))

    def state(self, public, produced_at, tick):
        hand = [c if c in self.deck else None for c in public.own_hand]
        nxt = public.own_next_card if public.own_next_card in self.deck else None
        elixir = float(public.own_elixir or 0.)
        if self.confirmed_hud and produced_at <= self.fence:
            hand, elixir = list(self.confirmed_hud.hand), self.confirmed_hud.elixir
            nxt = self.confirmed_hud.next_card
        digit = math.floor(elixir)
        if not self.pending and produced_at > self.fence:
            if self.last_digit is None or digit != self.last_digit:
                self.anchor_tick, self.anchor_elixir = tick, elixir
            elif self.anchor_tick is not None:
                elixir = min(10., digit+1., self.anchor_elixir+self.regen(self.anchor_tick, tick))
            self.last_digit = digit
        if self.pending:
            p = self.pending
            elixir = max(0., min(elixir, p['before_elixir']-p['cost']))
            hand = list(p['before_hand'])
            hand[p['slot']] = p['next_card']
            nxt = None
        # Maintain observed/verified order; remaining unseen order is explicitly
        # unknown. Deterministic completion is a root prior, never an observation.
        known = set(c for c in hand if c)
        queue = ([nxt] if nxt and nxt not in known else [])
        for card in self.verified:
            if card not in known and card not in queue:
                queue.append(card)
        observed_count = len(queue)
        queue.extend(c for c in self.deck if c not in known and c not in queue)
        self.last_tick = tick
        return dict(hand=hand, cycle=queue[:4], refill=0, elixir=elixir,
                    cycle_exact=observed_count >= 4, unresolved_cycle=max(0, 4-observed_count))


class StratifiedRng:
    """Stratify first (hand-hypothesis) draw and resource quantile in sample()."""
    def __init__(self, rng, stratum, k, concentrated=False):
        self.rng, self.stratum, self.k = rng, stratum, k
        self.first = True
        self.concentrated = concentrated

    def choice(self, n, p=None):
        import numpy as np
        if self.first and p is not None:
            self.first = False
            if self.concentrated:
                return int(np.argmax(p))
            u = (self.stratum+self.rng.random())/self.k
            return min(n-1, int(np.searchsorted(np.cumsum(p), u)))
        return self.rng.choice(n, p=p)

    def random(self):
        return (self.stratum+self.rng.random())/self.k

    def shuffle(self, values):
        self.rng.shuffle(values)


class Belief:
    def __init__(self, config):
        import json
        import numpy as np
        from clasher.vision.l1_derived_v3 import StreamPublicClock
        self.clock = StreamPublicClock()
        self.own = OwnLedger(config['own_deck'])
        self.rng = np.random.default_rng(config.get('seed', 6108))
        self.costs = config['costs']
        from .tracker import TrackerV3
        cls = tracker_class() if config.get('frozen_tracker', False) else TrackerV3
        self.tracker = cls(json.loads(Path(config['prior']).read_text()), self.costs,
                    recall=config.get('recall', .90), precision=config.get('precision', .90),
                    calibration=config.get('resource_calibration', 0.), body_cards=config.get('body_cards', {}))
        self.event_serial = 0
        self.seen = set()

    def update(self, observation):
        from types import SimpleNamespace
        frame, public = observation.frame, observation.public
        tick = self.clock.update(public.visible_clock_seconds, frame.timestamp_ms, observation.phase)
        events = []
        for row in observation.events:
            if row['side'] != 0 or row['card'] not in self.costs:
                continue
            key = row.get('event_id', (row['card'], row['execution_timestamp_ms'], row['x_tiles'], row['y_tiles']))
            if key in self.seen:
                continue
            self.seen.add(key)
            age_ticks = max(0, round((frame.timestamp_ms-row['execution_timestamp_ms'])/50))
            execution_tick = max(0, tick-age_ticks)
            # The frozen update_public API subtracts its historical 6-tick age
            # estimate. Add 6 ONLY here so v4's regressed execution time is used
            # once. Preserve S5's fixed calibrated event likelihood inside v3.
            events.append(SimpleNamespace(event_id=key, tick=execution_tick+6,
                                          name=row['card'], kind='card', amount=0.))
            if row['existence_q'] >= .5:
                self.event_serial += 1
        bodies = [(e.card, e.x_tiles, e.y_tiles) for e in public.entities if e.player_id == 0]
        self.tracker.update_public(tick, events, bodies)
        distribution = self.tracker.distribution()
        roots = tuple(self.tracker.sample(StratifiedRng(self.rng, i, 4, distribution['concentrated'])) for i in range(4))
        own = self.own.state(public, frame.produced_at, tick)
        tracked = replace(public, own_hand=tuple(c or '' for c in own['hand']), own_elixir=own['elixir'],
                          own_hand_confidence=tuple(q if c else 0. for c, q in zip(own['hand'], public.own_hand_confidence)))
        return Snapshot(frame.episode, frame.sequence, frame.produced_at, frame.received_at,
                        time.monotonic(), tick, tracked, own, roots, distribution,
                        self.own.revision, self.own.pending, self.event_serial, self.own.verification_serial)
