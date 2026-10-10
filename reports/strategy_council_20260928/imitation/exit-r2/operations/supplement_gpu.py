"""Float32 CUDA inference; original CPU reductions and bootstrap unchanged."""
import numpy as np
import torch
from supplement import clustered

@torch.inference_mode()
def teacher_gpu(policy,store,root_only,guard=lambda:None):
    keep=store.arrays['expert_action_supervision_valid'] & (store.arrays['teacher_wait_kind']!=3)
    if root_only:keep &= store.arrays['teacher_root']
    ix=np.flatnonzero(keep);rows=[]
    for begin in range(0,len(ix),64):
        guard();take=ix[begin:begin+64];b,y=store.batch(take);device=next(policy.model.parameters()).device
        b={k:v.to(device) for k,v in b.items()};lp=policy.model.log_policy(b)
        lp={k:v.cpu() for k,v in lp.items()}
        gate=lp['gate'].exp().numpy();actions=y['action'].numpy();positive=actions<2304
        joint=(lp['card'][:,:,None]+lp['tile']).flatten(1)
        top8=(joint.topk(8,dim=1).indices.numpy()==actions[:,None]).any(1)&positive
        predicted=np.where(lp['gate'].argmax(1).numpy()==1,joint.argmax(1).numpy(),2304)
        ep=store.arrays['episode_ids'][take]
        rows.append(np.column_stack((ep,np.ones(len(take)),positive,actions==2304,
            gate[:,1],gate[:,0],gate[:,1]*positive,top8,predicted==actions)))
    a=np.concatenate(rows);units=np.unique(a[:,0]);assert len(units)==64
    sums=[a[a[:,0]==u,1:].sum(0) for u in units]
    names=['rows','teacher_play','teacher_wait','student_play','student_wait','recall','top8','hard']
    ratios={'teacher_play_rate':('teacher_play','rows'),'teacher_wait_rate':('teacher_wait','rows'),
        'student_play_rate':('student_play','rows'),'student_wait_rate':('student_wait','rows'),
        'play_recall':('recall','teacher_play'),'play_prevalence_ratio':('student_play','teacher_play'),
        'top8_action_recall':('top8','teacher_play'),'hard_action_agreement':('hard','rows')}
    return dict(games=64,rows=len(a),scope='teacher roots' if root_only else 'eligible poll rows',
        metrics=clustered(sums,names,ratios),teacher_self_recall=1.0)
