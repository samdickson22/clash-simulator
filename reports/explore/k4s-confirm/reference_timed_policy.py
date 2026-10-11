"""Read-only extracted canonical R3 TimedPolicy class for qualification."""
import numpy as np
import torch
from imitation.model.inference import single_features
from proposals import outputs,rank_actions

class TimedPolicy:
    def __init__(self,policy,threshold,check):
        self.base=policy;self.model=policy.model;self.costs=policy.costs;self.threshold=threshold;self.check=check;self.cache=None
    def sample(self,packet,d1,generator=None):
        self.check('fallback',self.threshold is not None)
        if self.threshold is None:return self.base.sample(packet,d1,generator)
        with torch.inference_mode():
            b=single_features(packet,d1,self.costs);p,ranks=outputs(self.model,b)
        mask=packet['action_mask'];order=rank_actions(ranks[0].numpy(),mask)
        action=int(order[0]) if len(order) and float(p[0])>=self.threshold else 2304
        assert mask[action] and action<=2304
        self.cache=(d1,order,mask.copy());return action
    def propose(self,packet,d1,k=8):
        self.check('proposer',self.threshold is not None)
        if self.threshold is None:return self.base.propose(packet,d1,k)
        assert self.cache is not None and self.cache[0] is d1 and np.array_equal(self.cache[2],packet['action_mask'])
        return [dict(action=int(a),slot=int(a)//576,tile=int(a)%576,probability=None) for a in self.cache[1][:k]]
