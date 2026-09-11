"""One public-mask choice for one bound opponent seat per decision."""

from __future__ import annotations

import random

import numpy as np


class ScalarPublicRandomOpponent:
    """Uniform legal action IDs, with an owned CPython RNG stream.

    No BattleState, hidden state, policy logits, or global RNG is consulted.
    The unused learner mask never causes a draw and need not contain an action.
    """

    def __init__(self, *, seed: int, opponent_seat: int, num_actions: int = 2306):
        if type(seed) is not int:
            raise TypeError("opponent seed must be an integer")
        if seed < 0:
            raise ValueError("opponent seed must be nonnegative")
        if type(opponent_seat) is not int or opponent_seat not in (0, 1):
            raise ValueError("opponent seat must be zero or one")
        if type(num_actions) is not int or num_actions < 1:
            raise ValueError("action count must be a positive integer")
        self.opponent_seat = opponent_seat
        self.num_actions = num_actions
        self._rng = random.Random(seed)

    def sample(self, public_masks) -> int:
        """Select uniformly from true IDs on the one actual opponent mask.

        Includes no-op or ability IDs whenever the public mask admits them.
        Validation completes before the owned RNG changes. CPU NumPy arrays
        and CPU tensors exposing an array are accepted; no device transfer or
        simulator legality query is hidden in this function.
        """
        masks = np.asarray(public_masks)
        if masks.shape != (2, self.num_actions) or masks.dtype != np.bool_:
            raise ValueError("public masks must be bool [2, num_actions]")
        legal = np.flatnonzero(masks[self.opponent_seat])
        if legal.size == 0:
            raise ValueError("actual opponent public mask has no allowed action")
        return int(legal[self._rng.randrange(int(legal.size))])

    def getstate(self):
        return self._rng.getstate()

    def setstate(self, state):
        # Validate before replacing this object's live stream.
        candidate = random.Random(0)
        candidate.setstate(state)
        self._rng.setstate(candidate.getstate())
