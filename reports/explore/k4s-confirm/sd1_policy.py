"""PREREG-K4S SD1 seat poll: T1's CachedPolicy (threshold mode) plus a record of SD1 P(play).

T1 cached_policy.py is kept byte-identical. This subclass repeats only its calibrated-threshold
branch (one forward per poll, same-packet proposal reuse) and keeps the gate probability of that
same forward, so the per-decision record can carry `sd1_p_play` (r3 §3.6) at no extra inference.
Qualification checks action, proposals and forward counts against CachedPolicy on 125 states.
"""
import numpy as np
import torch
from imitation.model.inference import single_features
from cached_policy import CachedPolicy
from proposals import outputs, rank_actions


class SD1Policy(CachedPolicy):
    def __init__(self, base, threshold, check=None):
        assert threshold is not None, 'SD1 requires its frozen calibrated threshold'
        super().__init__(base, threshold, check)
        self.last_p_play = None
        self.last_default = None

    @torch.inference_mode()
    def sample(self, packet, d1, generator=None):
        if self.check: self.check()
        self.cache = None; self.fallback_calls += 1
        self.last_p_play = None; self.last_default = None
        b = single_features(packet, d1, self.costs); self.forward_calls += 1
        prob, ranks = outputs(self.model, b)
        order = rank_actions(ranks[0].numpy(), packet['action_mask'])
        p_play = float(prob[0])
        action = int(order[0]) if len(order) and p_play >= self.threshold else 2304
        proposals = [dict(action=int(a), slot=int(a)//576, tile=int(a)%576, probability=None) for a in order[:8]]
        self.cache = (d1, packet['action_mask'].copy(), proposals)
        self.last_p_play = p_play; self.last_default = action
        return action
