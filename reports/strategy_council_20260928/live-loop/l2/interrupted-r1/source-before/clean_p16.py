"""Same P16 mixture candidates/leaf with the L2 cooperative wall cutoff."""
import time
import numpy as np
from tuning import Planner
from clasher.rl.public_action_mask import PublicActionMaskInput
class CleanP16(Planner):
    def decide(self,info,decision):
        deadline=time.perf_counter()+.2;r=self.resources
        self.belief.update(info.tick,info.history)
        mask=r.mask_builder.build(PublicActionMaskInput.from_confidence_observation(info.packet))
        top=self.policy_top(info,mask)
        if decision%2 or not np.any(mask[:2304]):self.previous=2304;return 2304,mask
        ranked=r.bot._ranked_actions(info.packet,all_plays=True);script=int(r.bot.decide(info.packet).action_id)
        candidates=list(dict.fromkeys(a for a in [script,2304]+[int(x.action_id) for x in ranked[:4]]+top if mask[a]))
        root,_=r.root(info,self.belief.sample(self.rng),self.rng)
        action=candidates[0];best=-float('inf');completed=0
        for a in candidates:
            score=0.;finished=True
            for style in ('balanced','pressure','defense'):
                if time.perf_counter()>=deadline:finished=False;break
                other=r.native.select_action(root,1-info.seat,style)
                score+=r.native.rollout(root,info.seat,a,other,'balanced',style,160,10,1.)[0]/3
            if not finished:break
            completed+=1
            if score>best+1e-9:best=score;action=a
        self.previous=action;self.last=dict(completed=completed,total=len(candidates));return action,mask
