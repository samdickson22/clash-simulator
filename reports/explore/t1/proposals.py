"""One-pass final-EMA inference: calibrated timing and legal R3 proposal ranking."""
import numpy as np
import torch
from imitation.model.inference import Policy,single_features
from imitation.evaluation.d1 import model_packet
from exit_r3.network import ModelConfig,SetPolicy,AdvantagePolicy,masked_log_softmax


def load_student(path, threshold=None):
    ck=torch.load(path,map_location='cpu',weights_only=True);state=ck['ema']
    cls=AdvantagePolicy if ck['args'].get('advantage_weight',0)>0 else SetPolicy
    model=cls(ModelConfig(**ck['config']),state['descriptors'],state['tile_features'],state['costs'])
    model.load_state_dict(state)
    model.temperatures.fill_(1.)
    policy=Policy(model);policy.r3_threshold=threshold
    return policy


@torch.inference_mode()
def outputs(model,b):
    raw=model(b,torch.empty(0,dtype=torch.long,device=b['ids'].device))
    gate=masked_log_softmax(raw['gate'],raw['gate_mask']).exp()[:,1]
    if 'advantage_play' in raw:
        ranks=raw['advantage_play'].float().flatten(1)
    else:
        card=masked_log_softmax(raw['card'],raw['card_mask'])
        tile=masked_log_softmax(raw['tile'],raw['tile_mask'])
        ranks=(card[:,:,None]+tile).flatten(1)
    return gate,ranks


def calibrate(probabilities, legal_play, target=.346):
    p=np.asarray(probabilities,dtype=np.float64);legal=np.asarray(legal_play,dtype=bool)
    values=np.unique(p[legal])[::-1]
    # Thresholds sit between distinct probabilities, so ties stay together.
    thresholds=[np.nextafter(values[0],np.inf)] if len(values) else [1.]
    thresholds.extend(float((values[i]+values[i+1])/2) for i in range(len(values)-1))
    if len(values):thresholds.append(float(np.nextafter(values[-1],-np.inf)))
    best=min(thresholds,key=lambda t:(abs(np.count_nonzero(legal&(p>=t))/len(p)-target),t))
    return float(best)


def rank_actions(scores,mask):
    legal=np.flatnonzero(np.asarray(mask)[:2304])
    return legal[np.lexsort((legal,-np.asarray(scores)[legal]))]


@torch.inference_mode()
def student_choice(policy,packet,mask,d1):
    assert policy.r3_threshold is not None,'calibration required before deployment'
    b=single_features(model_packet(packet,mask),d1,policy.costs)
    prob,ranks=outputs(policy.model,b)
    order=rank_actions(ranks[0].numpy(),mask)
    action=int(order[0]) if len(order) and float(prob[0])>=policy.r3_threshold else 2304
    assert mask[action] and action<=2304
    return action,tuple(map(int,order))
