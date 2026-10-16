"""One model forward per poll; same-packet proposal reuse, no cross-poll cache."""
import numpy as np
import torch
from imitation.model.inference import single_features
from proposals import outputs,rank_actions

class CachedPolicy:
    def __init__(self,base,threshold=None,check=None):
        self.base=base;self.model=base.model;self.costs=base.costs
        self.threshold=threshold;self.check=check;self.cache=None
        self.forward_calls=0;self.proposal_calls=0;self.fallback_calls=0
    @torch.inference_mode()
    def sample(self,packet,d1,generator=None):
        if self.check:self.check()
        self.cache=None;self.fallback_calls+=1
        b=single_features(packet,d1,self.costs);self.forward_calls+=1
        if self.threshold is None:
            lp=self.model.log_policy(b)
            gate=int(torch.multinomial(lp['gate'][0].exp(),1,generator=generator))
            if gate!=1:action=2304 if gate==0 else 2305
            else:
                slot=int(torch.multinomial(lp['card'][0].exp(),1,generator=generator))
                tile=int(torch.multinomial(lp['tile'][0,slot].exp(),1,generator=generator))
                action=slot*576+tile
            # Use exact torch.topk ordering, including ties, as frozen Policy.propose.
            count=min(8,int(b['action_mask'][0,:2304].sum()))
            joint=(lp['card'][:,:,None]+lp['tile']).flatten(1)[0]
            values,indices=torch.topk(joint,count)
            proposals=[dict(action=int(i),slot=int(i)//576,tile=int(i)%576,probability=float(v)) for i,v in zip(indices.tolist(),values.exp().tolist())]
        else:
            prob,ranks=outputs(self.model,b)
            order=rank_actions(ranks[0].numpy(),packet['action_mask'])
            action=int(order[0]) if len(order) and float(prob[0])>=self.threshold else 2304
            proposals=[dict(action=int(a),slot=int(a)//576,tile=int(a)%576,probability=None) for a in order[:8]]
        self.cache=(d1,packet['action_mask'].copy(),proposals)
        return action
    def propose(self,packet,d1,k=8):
        if self.check:self.check()
        assert k==8 and self.cache is not None
        assert self.cache[0] is d1 and np.array_equal(self.cache[1],packet['action_mask'])
        self.proposal_calls+=1
        return list(self.cache[2])
