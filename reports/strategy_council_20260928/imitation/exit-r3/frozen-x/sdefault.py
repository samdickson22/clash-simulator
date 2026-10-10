"""S-default K1: only a cutoff without a complete play changes the default."""
import numpy as np
import torch
from imitation.model.inference import single_features
from imitation.evaluation.d1 import model_packet
WAIT=2304

@torch.inference_mode()
def student_choice(policy,packet,mask,d1):
    b=single_features(model_packet(packet,mask),d1,policy.costs)
    lp=policy.model.log_policy(b)
    joint=(lp['card'][0,:,None]+lp['tile'][0]).flatten()
    legal=np.flatnonzero(np.asarray(mask)[:WAIT])
    values=joint.detach().numpy()[legal]+float(lp['gate'][0,1])
    ordered=legal[np.lexsort((legal,-values))].tolist()
    choices=list(legal);scores=list(values)
    if mask[WAIT]:
        choices.append(WAIT);scores.append(float(lp['gate'][0,0]))
    assert choices,'No legal policy default'
    action=int(choices[int(np.argmax(scores))])
    assert mask[action] and action<=WAIT
    return action,tuple(int(a) for a in ordered)

def select_default(core,action,default,source,deadline):
    stats=core.deadline_stats
    complete=sum(a<WAIT and value is not None
                 for a,value in zip(core.last['candidates'],core.last['scores']))
    used=deadline is not None and stats['hit'] and complete==0
    stats.update(complete_play_scores=complete,default_used=used,default_source=source,
                 default_action=int(default))
    if used:
        assert 0<=default<=WAIT
        core.selected_wait_ticks=0
        return int(default)
    return action

def poll_before_search(owner,tick,packet,events,student,core,defaults,poll,latencies,clock):
    if student is not None:
        from clasher.rl.public_action_mask import PublicActionMaskInput
        d1=owner.student_tracker.update(tick,events)
        if tick%10==0:
            begin=clock()
            mask=owner.player.mask_builder.build(PublicActionMaskInput.from_confidence_observation(packet))
            action,order=student_choice(student,packet,mask,d1)
            defaults[owner.actor]=action
            core.coarse_order=order;core.refine_proposals=order[:8]
            latencies.append(clock()-begin)
    fallback=poll(tick,packet,events)
    if tick%10==0:
        if student is None:defaults[owner.actor]=fallback if fallback<2305 else WAIT
        return defaults[owner.actor]
    return fallback
