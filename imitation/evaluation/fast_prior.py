"""Exact vectorized Stage 5 prior operations; unchanged row order and arithmetic.

Both gate arms use this CPU implementation. It replaces short row-wise NumPy
reductions/sorts with column operations, preserving every posterior state,
weight, cumulative sum, resource value, derived fact and sampled RNG outcome.
No engine or gamedata source is changed.
"""
import numpy as np
from .paths import setup
setup()
from derived_public_state import DerivedPublicState


class ExactFastPrior(DerivedPublicState):
    def advance(self, tick):
        if tick < self.tick:
            raise ValueError('public time moved backwards')
        while self.tick < tick:
            self.tick += 1
            rate = .93 if self.tick > 4800 else 1.4 if self.tick > 2400 else 2.8
            self.elixir = min(10., (round(self.elixir*10000)+int(500/rate))/10000) if self.elixir < 10. else self.elixir
            self.refill = max(0, self.refill-50)
            if self.refill == 0 and self.queue_len > 4:
                s = self.states
                # The other three hand entries are sorted. Insert queue front.
                carry = s[:, 4].copy()
                for col in (1, 2, 3):
                    old = s[:, col].copy()
                    s[:, col-1] = np.minimum(carry, old)
                    carry = np.maximum(carry, old)
                s[:, 3] = carry
                s[:, 4:-1] = s[:, 5:]
                s[:, -1] = 0
                self.queue_len -= 1
                self.refill = 1000 if self.tick < 2400 else 500 if self.tick < 4800 else 350
                self._derived = None

    def update(self, tick, events):
        if list(events[:len(self.events)]) != self.events:
            raise ValueError('public events changed')
        for event in events[len(self.events):]:
            self.advance(event.tick)
            if event.kind == 'card':
                card = self.ids[event.name]
                s = self.states
                keep = (s[:, 0] == card) | (s[:, 1] == card) | (s[:, 2] == card) | (s[:, 3] == card)
                self.states = s[keep]
                self.weights = self.weights[keep]
                if not len(self.states):
                    raise ValueError('no train deck/order is consistent with public plays')
                self.cumulative = np.cumsum(self.weights)
                s = self.states
                # Replace the unique played card with zero, preserving sorted order.
                # Right-to-left avoids overwriting a source column before its use.
                for col in (3, 2, 1):
                    s[:, col] = np.where(s[:, col] <= card, s[:, col-1], s[:, col])
                s[:, 0] = 0
                s[:, 4+self.queue_len] = card
                self.queue_len += 1
                self.elixir = max(0., self.elixir-self.costs[event.name])
                self._derived = None
            elif event.kind == 'ability':
                self.elixir -= event.amount
                if self.elixir < 0: raise ValueError('public ability was unaffordable')
            elif event.kind == 'collector':
                self.elixir = min(10., self.elixir+event.amount)
            else:
                raise ValueError(f'unknown public event {event.kind}')
            self.events.append(event)
        self.advance(tick)
