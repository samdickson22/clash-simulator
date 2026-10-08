"""Own cycle from the player's known opening order and accepted plays."""
from collections import deque


class OwnCycle:
    def __init__(self, ordered_deck):
        if len(ordered_deck) != 8 or len(set(ordered_deck)) != 8:
            raise ValueError('eight distinct own cards required')
        self.deck = tuple(ordered_deck)
        self.hand = list(ordered_deck[:4])
        self.queue = deque(ordered_deck[4:])
        self.tick = self.refill = 0

    def advance(self, tick):
        if tick < self.tick:
            raise ValueError('own time moved backwards')
        while self.tick < tick:
            self.tick += 1
            self.refill = max(0, self.refill - 50)
            if not self.refill and None in self.hand:
                self.hand[self.hand.index(None)] = self.queue.popleft()
                self.refill = 1000 if self.tick < 2400 else 500 if self.tick < 4800 else 350

    def play(self, tick, name):
        self.advance(tick)
        self.hand[self.hand.index(name)] = None
        self.queue.append(name)
