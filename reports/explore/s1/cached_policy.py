"""One model forward per poll; same-packet proposal reuse, no cross-poll cache."""
import numpy as np
import torch
from imitation.model.inference import single_features
from proposals import outputs,rank_actions
from clasher.rl.slot_permission import eligibility_mask

class CachedPolicy:
    def __init__(self,base,threshold=None,check=None):
        self.base=base;self.model=base.model;self.costs=base.costs
        self.threshold=threshold;self.check=check;self.cache=None
        self.forward_calls=0;self.proposal_calls=0;self.fallback_calls=0
    @torch.inference_mode()
    def sample(self,packet,d1,generator=None):
        if self.check:self.check()
        self.original_action=None
        self.cache=None;self.fallback_calls+=1
        b=single_features(packet,d1,self.costs);self.forward_calls+=1
        eligible=eligibility_mask(packet)
        if self.threshold is None:
            lp=self.model.log_policy(b)
            if 'eligibility_mask' in packet:
                lp=dict(lp)
                em=torch.from_numpy(eligible[:2304].reshape(4,576))
                cm=em.any(-1)
                lp['card']=lp['card'].masked_fill(~cm[None],-torch.inf)
                lp['tile']=lp['tile'].masked_fill(~em[None],-torch.inf)
            gate=int(torch.multinomial(lp['gate'][0].exp(),1,generator=generator))
            if gate!=1:action=2304 if gate==0 or not eligible[2305] else 2305
            elif not eligible[:2304].any():action=2304
            else:
                slot=int(torch.multinomial(lp['card'][0].exp(),1,generator=generator))
                tile=int(torch.multinomial(lp['tile'][0,slot].exp(),1,generator=generator))
                action=slot*576+tile
            # Use exact torch.topk ordering, including ties, as frozen Policy.propose.
            count=min(8,int(eligible[:2304].sum()))
            joint=(lp['card'][:,:,None]+lp['tile']).flatten(1)[0]
            values,indices=torch.topk(joint,count)
            proposals=[dict(action=int(i),slot=int(i)//576,tile=int(i)%576,probability=float(v)) for i,v in zip(indices.tolist(),values.exp().tolist())]
        else:
            prob,ranks=outputs(self.model,b)
            order=rank_actions(ranks[0].numpy(),eligible)
            if 'eligibility_mask' in packet:
                original=rank_actions(ranks[0].numpy(),packet['action_mask'])
                self.original_action=int(original[0]) if len(original) and float(prob[0])>=self.threshold else 2304
            action=int(order[0]) if len(order) and float(prob[0])>=self.threshold else 2304
            proposals=[dict(action=int(a),slot=int(a)//576,tile=int(a)%576,probability=None) for a in order[:8]]
        self.cache=(d1,packet['action_mask'].copy(),proposals,eligible.copy())
        return action
    def propose(self,packet,d1,k=8):
        if self.check:self.check()
        assert k==8 and self.cache is not None
        assert self.cache[0] is d1 and np.array_equal(self.cache[1],packet['action_mask'])
        assert np.array_equal(self.cache[3],eligibility_mask(packet))
        self.proposal_calls+=1
        return list(self.cache[2])
