"""Executable student adapter: fixed-step mixed fine tuning, atomic resumable state."""
import argparse
from contextlib import nullcontext
from dataclasses import asdict
import json
import os
from pathlib import Path
import random
import signal
import numpy as np
import torch
from imitation.model import train as human_trainer
from imitation.model.store import PackedStore
from imitation.model.batching import build_batch
from .student import RootTeacherStore as TeacherStore, initialize_root as initialize, mixed_indices, teacher_loss, teacher_targets, advantage_loss
from .rows import sha, write_json


def human_batch(store,ix):
    b,y=build_batch(store,ix)
    s122=(torch.from_numpy(np.asarray(store.arrays['corpus_s122'][ix])) if 'corpus_s122' in store.arrays
          else torch.zeros(len(ix),dtype=torch.bool))
    y['weight']=y['weight'].float()*torch.where(y['action']==2304,torch.where(s122,2.,4.),1.)
    return b,y


def eligible(store,epoch,seed):
    from imitation.model.store import epoch_indices,hash64
    if 'corpus_s122' not in store.arrays: return epoch_indices(store,epoch,seed)
    parts=[]
    for start in range(0,len(store),1048576):
        sl=slice(start,min(len(store),start+1048576))
        ids=store.arrays['row_ids'][sl].astype(np.uint64)
        h=hash64(ids^np.uint64(seed)^np.uint64((epoch+1)*0x9e3779b9))>>np.uint64(32)
        limit=np.where(store.arrays['corpus_s122'][sl],2**31,2**30).astype(np.uint64)
        keep=store.arrays['expert_action_supervision_valid'][sl].astype(bool)
        keep &= (store.arrays['expert_actions'][sl]!=2304)|(h<limit)
        parts.append(np.flatnonzero(keep)+start)
    result=np.concatenate(parts)
    np.random.default_rng(np.random.SeedSequence([seed,epoch])).shuffle(result)
    return result


def step(model,opt,human,teacher,ratio,microbatch,device,temperature,play_weight,value_weight,score_zscore=False,advantage_weight=0.):
    if ratio==0:
        return human_trainer.optimizer_step(model,opt,*human,microbatch,device)
    opt.zero_grad(set_to_none=True)
    total=0.
    # Each corpus uses its own conditional denominators, matching human loss
    # and preserving rare plays. Weight each source once, independent of counts.
    if ratio<1:
        b,y=human
        den=human_trainer.move(human_trainer.denominators(b,y),device)
        for start in range(0,len(y['action']),microbatch):
            bb=human_trainer.move({k:v[start:start+microbatch] for k,v in b.items()},device)
            yy=human_trainer.move({k:v[start:start+microbatch] for k,v in y.items()},device)
            with torch.autocast('cuda',dtype=torch.bfloat16) if device.type=='cuda' else nullcontext():
                slots=(yy['action']//576).clamp(0,3).long()
                o=model(bb,slots)
                loss=(1-ratio)*human_trainer.total_loss(human_trainer.loss_parts(o,yy),den)['loss']
            loss.backward();total+=float(loss.detach())
    b,y=teacher
    w=y['weight'].float()*y['supervised'].float()*torch.where(y['action']<2304,play_weight,1.)
    q=teacher_targets(y,temperature,score_zscore)
    gate_den=float(w.sum());play_den=float((w*(q*(y['root_actions']<2304)).sum(-1)).sum())
    advantage_den=float((y["root_valid"].float()*w[:,None]).sum())
    # Teacher all-card tiles need a smaller microbatch than hard human forcing.
    for start in range(0,len(y['action']),min(microbatch,128)):
        end=start+min(microbatch,128)
        bb=human_trainer.move({k:v[start:end] for k,v in b.items()},device)
        yy=human_trainer.move({k:v[start:end] for k,v in y.items()},device)
        with torch.autocast('cuda',dtype=torch.bfloat16) if device.type=='cuda' else nullcontext():
            o=model(bb,torch.empty(0,dtype=torch.long,device=device))
            loss=ratio*teacher_loss(o,yy,temperature,play_weight,value_weight,
                                    denominators=(gate_den,play_den),score_zscore=score_zscore)
            if advantage_weight:
                loss += advantage_weight*advantage_loss(o,yy,advantage_den)
        loss.backward();total+=float(loss.detach())
    grad=torch.nn.utils.clip_grad_norm_(model.parameters(),1.,error_if_nonfinite=True)
    opt.step()
    return dict(loss=total,grad_norm=float(grad))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--init-checkpoint',required=True,help='Selected v2, or released v1 until v2 is selected')
    p.add_argument('--human-store',required=True);p.add_argument('--assets',required=True)
    p.add_argument('--teacher-root');p.add_argument('--teacher-ratio',type=float,default=.5)
    p.add_argument('--value-weight',type=float,default=0.)
    p.add_argument('--advantage-weight',type=float,default=0.)
    p.add_argument('--extra-teacher-root',action='append',default=[])
    p.add_argument('--temperature',type=float,default=.1);p.add_argument('--play-weight',type=float,default=4.)
    p.add_argument('--score-zscore',action='store_true',help='Population z-score completed candidates per root before temperature')
    p.add_argument('--steps',type=int,default=4883);p.add_argument('--batch-size',type=int,default=8192)
    p.add_argument('--warmup',type=int,default=2000)
    p.add_argument('--microbatch',type=int,default=7168);p.add_argument('--seed',type=int,default=2026100901)
    p.add_argument('--device',default='cuda');p.add_argument('--output',required=True)
    p.add_argument('--checkpoint-every',type=int,default=1000);p.add_argument('--resume');p.add_argument('--stop')
    a=p.parse_args()
    if not 0<=a.teacher_ratio<=1 or a.value_weight<0 or a.temperature<=0 or a.play_weight<1:
        p.error('invalid mixture/loss controls')
    if a.teacher_ratio==0 and a.value_weight: p.error('human-only control has no value loss')
    if a.teacher_ratio!=1 or a.temperature not in (.003,.01) or a.play_weight!=1 or a.value_weight or a.score_zscore or a.advantage_weight not in (0.,1.):
        p.error("R3 round2 requires roots-only T=.003/.01 play1 value0 advantage0/1")
    out=Path(a.output)
    if out.exists() and any(out.iterdir()) and not a.resume: raise ValueError('use a fresh output or resume')
    out.mkdir(parents=True,exist_ok=True)
    torch.set_num_threads(1);torch.manual_seed(a.seed);random.seed(a.seed);np.random.seed(a.seed)
    device=torch.device(a.device)
    model,c=initialize(a.init_checkpoint,a.advantage_weight>0);model=model.to(device)
    human=PackedStore(a.human_store,'train',a.assets)
    for key,buffer in (('costs','costs'),('descriptors','descriptors'),('tiles','tile_features')):
        if not torch.equal(getattr(model,buffer).detach().cpu(),torch.from_numpy(human.assets[key])):
            raise ValueError('initial checkpoint and human public assets differ: '+key)
    human_ix=eligible(human,0,a.seed)
    shards=[]
    if a.teacher_ratio:
        if not a.teacher_root:p.error('teacher mixture requires teacher-root')
        root=Path(a.teacher_root)
        # Pack the fleet first: opening tens of thousands of games exhausts FDs.
        paths=[root] if (root/'manifest.json').exists() else [f.parent for f in sorted(root.glob('game-*/manifest.json'))]
        if len(paths)>64:raise ValueError('pack teacher games first with imitation.exit_r1.pack')
        paths.extend(Path(f) for f in a.extra_teacher_root)
        shards=[TeacherStore(f,a.assets) for f in paths]
        if not shards:raise ValueError('no sealed teacher shards')
    ends=np.cumsum([len(s) for s in shards]); nteacher=int(ends[-1]) if shards else 0
    pins=dict(init_checkpoint=sha(a.init_checkpoint),assets=sha(a.assets),human_manifest=sha(Path(a.human_store)/'manifest.json'),
              teacher_manifests=[sha(s.root.parent/'manifest.json') for s in shards])
    code_paths=[p for directory in (Path(__file__).parent,Path(human_trainer.__file__).parent)
                for p in directory.glob('*.py')]
    pins['source_files']={str(p.resolve()):sha(p) for p in sorted(code_paths)}
    # Immutable pre-fit evidence exists even if the first optimizer step fails.
    inputs=dict(pins=pins,config=asdict(c),recipe={k:v for k,v in vars(a).items() if k!='resume'})
    input_path=out/'inputs.json'
    if a.resume:
        previous=json.loads(input_path.read_text())
        if previous['pins']!=pins:raise ValueError('resume source/input pins changed')
    else:write_json(input_path,inputs)
    opt=torch.optim.AdamW(model.parameters(),lr=3e-4,weight_decay=.05)
    sched=torch.optim.lr_scheduler.LambdaLR(opt,lambda s:human_trainer.lr_factor(s,a.steps,a.warmup))
    ema={k:v.detach().clone() for k,v in model.state_dict().items()}
    cursor=0
    if a.resume:
        ck=torch.load(a.resume,map_location=device,weights_only=True)
        if ck['hashes']!=pins or ck['config']!=asdict(c):raise ValueError('resume inputs changed')
        for k in ('teacher_ratio','value_weight','temperature','play_weight','steps','batch_size','microbatch','seed','warmup','advantage_weight','extra_teacher_root'):
            if ck['args'][k]!=vars(a)[k]:raise ValueError('resume recipe changed: '+k)
        if ck['args'].get('score_zscore',False)!=a.score_zscore:raise ValueError('resume recipe changed: score_zscore')
        model.load_state_dict(ck['model']);ema=ck['ema'];opt.load_state_dict(ck['optimizer']);sched.load_state_dict(ck['scheduler'])
        cursor=ck['state']['step'];torch.set_rng_state(ck['torch_rng'].cpu())
        random.setstate(ck['python_rng'])
        nr=ck['numpy_rng'];np.random.set_state((nr['name'],np.array(nr['keys'],np.uint32),nr['pos'],nr['has_gauss'],nr['cached']))
        if device.type=='cuda':torch.cuda.set_rng_state_all([x.cpu() for x in ck['cuda_rng']])
    stop=[False]
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:stop.__setitem__(0,True))
    model.train()
    with (out/'train.jsonl').open('a',buffering=1) as log:
        for s in range(cursor,a.steps):
            if stop[0] or a.stop and Path(a.stop).exists():break
            hi,ti=mixed_indices(len(human_ix),nteacher,a.batch_size,a.teacher_ratio,a.seed,s)
            hb=human_batch(human,human_ix[hi]) if len(hi) else None
            tb=None
            if len(ti):
                # Uniform global rows; group by shard then collate scalar rows
                # with ragged score padding across shards.
                from .teacher_batch import combined_batch
                tb=combined_batch(shards,ends,ti)
            result=step(model,opt,hb,tb,a.teacher_ratio,a.microbatch,device,a.temperature,a.play_weight,a.value_weight,a.score_zscore,a.advantage_weight)
            sched.step();human_trainer.update_ema(ema,model);cursor=s+1
            record=dict(step=cursor,rows=cursor*a.batch_size,teacher_ratio=a.teacher_ratio,**result)
            log.write(json.dumps(record)+'\n');print(json.dumps(record),flush=True)
            if cursor%a.checkpoint_every==0:
                human_trainer.save_checkpoint(out/f'step-{cursor:08d}.pt',model,ema,opt,sched,c,record,pins,a)
    human_trainer.save_checkpoint(out/f'step-{cursor:08d}.pt',model,ema,opt,sched,c,dict(step=cursor),pins,a)
    write_json(out/'complete.json',dict(step=cursor,stopped=cursor<a.steps,pins=pins))


if __name__=='__main__':main()
