"""Read-only logits capture around the unchanged production Session, with no second network pass."""
import math

import torch

from . import featurize as F


class PolicyTrace:
    def __init__(self, model):
        self.original = model
        self.clear()

    def __getattr__(self, name):
        return getattr(self.original, name)

    def clear(self):
        self._gate_logits = self._tile_logits = None

    def gate_logits(self, *args, **kwargs):
        z = self.original.gate_logits(*args, **kwargs)
        self._gate_logits = z.detach()
        return z

    def tile_logits(self, *args, **kwargs):
        z = self.original.tile_logits(*args, **kwargs)
        self._tile_logits = z.detach()
        return z

    def log_probability(self, decision, *, gap=F.POLL, temperature=1.):
        if gap != F.POLL or temperature != 1.:
            raise ValueError('RL trace requires the registered five-tick, temperature-one distribution')
        if decision.status == 'stale':
            raise ValueError('a declined stale decision is not a sampled RL action')
        if self._gate_logits is None:
            raise RuntimeError('no Session decision was captured')
        if decision.status == 'forced':
            return 0.
        p = torch.softmax(self._gate_logits[0], -1).cpu().double().numpy()
        if decision.p_wait5 != float(p[0]) or decision.p_wait != decision.p_wait5:
            raise ValueError('captured distribution and Session survival probability disagree')
        if decision.status == 'wait':
            probability = float(p[0])
        elif decision.status == 'play':
            if self._tile_logits is None:
                raise RuntimeError('played action has no captured tile distribution')
            t = torch.softmax(self._tile_logits[0], -1).cpu().double().numpy()
            # Match Session's Bernoulli followed by independently normalized slot/tile conditionals, including
            # the same float32-softmax -> float64 sampling normalization. No surrogate argmax likelihood.
            probability = (1-float(p[0]))*float(p[decision.slot+1]/p[1:].sum())*float(t[decision.tile]/t.sum())
        else:
            raise ValueError(f'unknown sampled decision status {decision.status!r}')
        if not 0 < probability <= 1:
            raise ValueError('sampled action has zero or nonfinite captured probability')
        return math.log(probability)
