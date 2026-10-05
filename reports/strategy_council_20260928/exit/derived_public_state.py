"""Exact quantities derivable from the P16 public play stream.

P16 has no Elixir Collector, Mirror, or resource-producing effects. Unknown card
names fail closed. Starting elixir, frame regeneration and public card costs are
known exactly; no estimate fallback is used. All uncertainty is a finite posterior
over unrevealed identities and possible initial orders, filtered by public plays.
"""
import itertools
import numpy as np

class DerivedPublicState:
    """Exact finite posterior over deck/order given public accepted card plays.

    Slots matter during delayed refill, so retain all 8! orders, including all
    initial hand-slot permutations. Unknown actions supply no negative evidence.
    """
    def __init__(self, prior, costs):
        self.names = sorted(costs)
        self.ids = {n: i+1 for i, n in enumerate(self.names)}
        self.costs = costs
        perms = np.asarray(list(itertools.permutations(range(8))), dtype=np.int16)
        states, weights = [], []
        for deck in prior['decks']:
            cards = np.asarray([self.ids[n] for n in deck['cards']], dtype=np.int16)
            a = np.zeros((len(perms), 12), dtype=np.int16)
            a[:, :8] = cards[perms]
            states.append(a)
            weights.append(np.full(len(perms), deck.get('sampling_weight', 1.0)))
        self.states = np.concatenate(states)
        self.weights = np.concatenate(weights)
        self.cumulative = np.cumsum(self.weights)
        self.tick = 0
        self.refill = 0
        self.queue_len = 4
        self.elixir_units = 60000
        self.history = []
        self._derived = None
        self.derived()  # Prior-only work belongs to game initialization.

    def advance(self, tick):
        if tick < self.tick:
            raise ValueError('public time moved backwards')
        while self.tick < tick:
            self.tick += 1
            rate = 0.93 if self.tick > 4800 else 1.4 if self.tick > 2400 else 2.8
            self.elixir_units = min(100000, self.elixir_units + int(500 / rate))
            self.refill = max(0, self.refill - 50)
            if self.refill == 0 and self.queue_len > 4:
                empty = (self.states[:, :4] == 0).argmax(axis=1)
                self.states[np.arange(len(self.states)), empty] = self.states[:, 4]
                self.states[:, 4:-1] = self.states[:, 5:]
                self.states[:, -1] = 0
                self.queue_len -= 1
                self._derived = None
                self.refill = 1000 if self.tick < 2400 else 500 if self.tick < 4800 else 350

    def update(self, tick, history):
        if tuple(history[:len(self.history)]) != tuple(self.history):
            raise ValueError('public play history changed')
        for t, name in history[len(self.history):]:
            self.advance(t)
            card = self.ids[name]
            keep = np.any(self.states[:, :4] == card, axis=1)
            self.states = self.states[keep]
            self.weights = self.weights[keep]
            self.cumulative = np.cumsum(self.weights)
            if not len(self.states):
                raise ValueError('no deck/order consistent with public plays')
            slot = (self.states[:, :4] == card).argmax(axis=1)
            self.states[np.arange(len(self.states)), slot] = 0
            self.states[:, 4+self.queue_len] = card
            self.queue_len += 1
            self.elixir_units = max(0, self.elixir_units - round(self.costs[name]*10000))
            self.history.append((t, name))
            self._derived = None
        self.advance(tick)

    def derived(self):
        """Known hand is a multiset; opponent UI slot order is not a public fact.

        Every candidate order has already satisfied every accepted play and refill.
        Certainty therefore follows from agreement of ALL remaining possibilities,
        not a heuristic count of revealed cards. This can resolve before eight cards.
        """
        if self._derived is None:
            hand_rows = np.sort(self.states[:, :4], axis=1)
            first = self.states[0]
            hand_known = bool(np.all(hand_rows == hand_rows[0]))
            queue_known = np.all(self.states[:, 4:4+self.queue_len] == first[4:4+self.queue_len], axis=0)
            slots_known = np.all(self.states[:, :4] == first[:4], axis=0)
            names = lambda a: tuple(self.names[int(x)-1] if x else None for x in a)
            self._derived = dict(
                hand=names(hand_rows[0]) if hand_known else None,
                cycle=names(first[4:4+self.queue_len]) if bool(np.all(queue_known)) else None,
                next_card=self.names[int(first[4])-1] if queue_known[0] else None,
                hand_slots=names(first[:4]), hand_slots_known=tuple(bool(x) for x in slots_known),
                cycle_positions=names(first[4:4+self.queue_len]),
                cycle_positions_known=tuple(bool(x) for x in queue_known))
        return self._derived

    def sample(self, rng):
        derived = self.derived()
        # Resolved game hand and cycle are exact, with no identity/order sampling.
        # Hidden UI slot permutations use the first consistent representative;
        # we do not claim the private UI arrangement has become observable.
        if derived['hand'] is not None and derived['cycle'] is not None:
            i = 0
        else:
            i = int(np.searchsorted(self.cumulative, rng.random()*self.cumulative[-1], side='right'))
        row = self.states[i]
        names = lambda a: [self.names[int(x)-1] if x else None for x in a]
        return dict(elixir=self.elixir_units/10000, hand=names(row[:4]),
                    cycle=names(row[4:4+self.queue_len]), refill=self.refill)
