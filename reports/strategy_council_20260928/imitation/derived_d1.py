"""Deck-free deductions from accepted, timestamped public events only.

No simulator, deck catalog or hidden state is imported here. Card names are the
engine's base card identities; token conversion belongs to the observation edge.
The full pending queue is retained, including cards awaiting hand refill.
"""
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class PublicEvent:
    tick: int
    kind: str
    name: str = ''
    amount: float = 0.0
    x: float = 0.0
    y: float = 0.0


class DerivedD1:
    def __init__(self, costs):
        self.costs = dict(costs)
        self.tick = 0
        self.elixir = 6.0
        self.refill = 0
        self.queue = deque([None] * 4)
        self.revealed = set()
        self.events = []
        self.plays = deque(maxlen=8)
        self.abilities = deque(maxlen=8)
        self.last_card = None

    @property
    def elixir_units(self):
        return round(self.elixir * 10000)

    def advance(self, tick):
        if tick < self.tick:
            raise ValueError('public time moved backwards')
        while self.tick < tick:
            self.tick += 1
            rate = .93 if self.tick > 4800 else 1.4 if self.tick > 2400 else 2.8
            if self.elixir < 10.:
                self.elixir = min(10., (self.elixir_units + int(500 / rate)) / 10000)
            self.refill = max(0, self.refill - 50)
            if not self.refill and len(self.queue) > 4:
                self.queue.popleft()
                self.refill = 1000 if self.tick < 2400 else 500 if self.tick < 4800 else 350

    def accept(self, event):
        self.advance(event.tick)
        if event.kind == 'card':
            if event.name not in self.costs:
                raise ValueError(f'unknown card cost: {event.name}')
            if event.name in self.queue or len(self.queue) >= 8:
                raise ValueError('public play inconsistent with ordinary cycle')
            cost = self.costs[event.name]
            if event.name == 'Mirror':
                if self.last_card is None:
                    raise ValueError('Mirror has no public predecessor')
                cost = self.costs[self.last_card] + 1
            else:
                self.last_card = event.name
            self.elixir = max(0., self.elixir - cost)
            self.queue.append(event.name)
            self.revealed.add(event.name)
            if len(self.revealed) > 8:
                raise ValueError('more than eight revealed deck cards')
            self.plays.append(event)
        elif event.kind == 'ability':
            self.elixir -= event.amount
            if self.elixir < 0:
                raise ValueError('public ability was unaffordable')
            self.abilities.append(event)
        elif event.kind == 'collector':
            self.elixir = min(10., self.elixir + event.amount)
        else:
            raise ValueError(f'unknown public event {event.kind}')
        self.events.append(event)

    def update(self, tick, events):
        if list(events[:len(self.events)]) != self.events:
            raise ValueError('public event prefix changed')
        for event in events[len(self.events):]:
            self.accept(event)
        self.advance(tick)

    def derived(self):
        hand = sorted(self.revealed - set(self.queue))
        if len(hand) > 8 - len(self.queue):
            raise ValueError('known hand exceeds occupied slots')
        queue = tuple(self.queue)
        return dict(hand_known=tuple(hand + [None] * (4 - len(hand))),
                    next_card=queue[0], cycle_positions=queue,
                    cycle_positions_known=tuple(n is not None for n in queue),
                    refill=self.refill, cards_revealed=len(self.revealed),
                    elixir=self.elixir, elixir_units=self.elixir_units)


# Shared name for existing tracker adapters.
DerivedPublicState = DerivedD1
