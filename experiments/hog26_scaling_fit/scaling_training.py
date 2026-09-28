"""Fixed-budget pilot fitting functions; callers audit full data and pin source first."""
import gc
import time

import numpy as np
import torch
from scalar_models import EntityHistoryOutcome, GlobalWDL
from scaling_dataset import public_batch
from torch.nn import functional as F


def fit_globals(games, fit_indices, per_game_weights, *, seed, epochs=30, batch_rows=512, log=None):
    torch.manual_seed(seed)
    model=GlobalWDL()
    optimizer=torch.optim.AdamW(model.parameters(),lr=3e-4,weight_decay=1e-4)
    x=torch.from_numpy(np.concatenate([games[i].public['global_features'] for i in fit_indices]))
    confidence=torch.from_numpy(np.concatenate([games[i].public['global_feature_confidence'] for i in fit_indices]))
    labels=torch.cat([torch.full((len(games[i].public['global_features']),),games[i].target_class,dtype=torch.long) for i in fit_indices])
    weights=torch.from_numpy(np.concatenate([per_game_weights[i] for i in fit_indices])).float()
    if not torch.isclose(weights.sum(),torch.tensor(1.),atol=1e-5):raise ValueError('fitting WDL weights must sum1')
    count=len(x); began=time.monotonic()
    for epoch in range(epochs):
        order=torch.randperm(count)
        for start in range(0,count,batch_rows):
            indices=order[start:start+batch_rows]
            optimizer.zero_grad(set_to_none=True)
            loss=(F.cross_entropy(model(x[indices],confidence[indices]),labels[indices],reduction='none')*weights[indices]).sum()*count/len(indices)
            if not torch.isfinite(loss):raise FloatingPointError('nonfinite global loss')
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.);optimizer.step()
        if log:log({'model':'globals','epoch':epoch+1,'elapsed_seconds':time.monotonic()-began})
    return model.eval()


def predict_globals(model,games):
    with torch.inference_mode():
        return [model(torch.from_numpy(g.public['global_features']),torch.from_numpy(g.public['global_feature_confidence'])).softmax(-1).numpy() for g in games]


def fit_entity(games,fit_indices,wdl_weights,margin_weights,*,vocabulary,seed,epochs=30,batch_games=2,log=None):
    torch.manual_seed(seed)
    model=EntityHistoryOutcome(len(vocabulary),princess_tower_token=vocabulary.index('tower:Tower'),king_tower_token=vocabulary.index('tower:KingTower'))
    optimizer=torch.optim.AdamW(model.parameters(),lr=3e-4,weight_decay=1e-4)
    if not np.isclose(sum(wdl_weights[i].sum() for i in fit_indices),1):raise ValueError('WDL weights not normalized')
    if not np.isclose(sum(margin_weights[i].sum() for i in fit_indices),1):raise ValueError('margin weights not normalized')
    count=len(fit_indices);began=time.monotonic()
    for epoch in range(epochs):
        order=torch.randperm(count).tolist()
        for start in range(0,count,batch_games):
            chosen=[fit_indices[i] for i in order[start:start+batch_games]]
            batch,lengths=public_batch([games[i] for i in chosen])
            optimizer.zero_grad(set_to_none=True)
            logits,predicted,_=model(batch,lengths)
            objective=logits.sum()*0
            for slot,index in enumerate(chosen):
                n=int(lengths[slot]);g=games[index]
                target=torch.full((n,),g.target_class,dtype=torch.long)
                w=torch.from_numpy(wdl_weights[index]).float();mw=torch.from_numpy(margin_weights[index]).float()
                objective=objective+(F.cross_entropy(logits[slot,:n],target,reduction='none')*w).sum()
                objective=objective+((predicted[slot,:n]-g.target_margin).abs()*mw).sum()
            objective=objective*count/len(chosen)
            if not torch.isfinite(objective):raise FloatingPointError('nonfinite entity loss')
            objective.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),1.);optimizer.step()
        if log:log({'model':'entity','epoch':epoch+1,'elapsed_seconds':time.monotonic()-began})
    return model.eval()


def predict_entity(model,games):
    probability,margin=[],[]
    with torch.inference_mode():
        for game in games:
            batch,lengths=public_batch([game]);logits,prediction,_=model(batch,lengths)
            probability.append(logits[0,:int(lengths[0])].softmax(-1).numpy())
            margin.append(prediction[0,:int(lengths[0])].numpy())
    return probability,margin


def release_fit():
    gc.collect()
