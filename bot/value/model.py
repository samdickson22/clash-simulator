"""Numpy inference for bot.value.fit models (no torch on the search path)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from .features import encode

MODEL_DIR = Path(os.environ.get('BOT_VALUE_MODELS', '/mpac/sdicks02/jobs/clasher/bot-value-models'))


class ValueModel:
    def __init__(self, path):
        z = np.load(path, allow_pickle=False)
        self.kind = str(z['kind'])
        self.mu, self.sd, self.nbase = z['mu'], z['sd'], int(z['nbase'])
        self.vocab = {int(t): i for i, t in enumerate(z['vocab'])}
        self.k_phi = float(z['k_phi'])
        self.W = [z[f'W{i}'] for i in range(int(z['layers']))]
        self.b = [z[f'b{i}'] for i in range(int(z['layers']))]
        self.meta = json.loads(str(z['meta']))

    @classmethod
    def named(cls, name):
        return cls(MODEL_DIR / f'{name}.npz')

    def g(self, x):
        if self.kind == 'lin':
            x = x[..., :self.nbase]
        h = (x - self.mu)/self.sd
        for i, (W, b) in enumerate(zip(self.W, self.b)):
            h = h @ W.T + b
            if i < len(self.W) - 1:
                h = np.maximum(h, 0.)
        return h[..., 0]

    def logit(self, pv, parts0, seat, tick):
        a, b = encode(pv, parts0, seat, tick, self.vocab)
        return float(self.g(a) - self.g(b))

    def phi_units(self, pv, parts0, seat, tick):
        """Logit divided by the slope of the phi-only fit: V on phi's scale (keeps the WAIT bonus meaningful)."""
        return self.logit(pv, parts0, seat, tick)/self.k_phi
