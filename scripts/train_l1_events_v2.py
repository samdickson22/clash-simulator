"""Fit the causal three-frame event heatmap on frozen training episodes only."""
import argparse
from collections import defaultdict
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import random
import time

os.environ.setdefault('PYTORCH_MPS_HIGH_WATERMARK_RATIO','0.35')
os.environ.setdefault('PYTORCH_MPS_LOW_WATERMARK_RATIO','0.25')
import cv2
import numpy as np
import torch
from torch.utils.data import Dataset

from clasher.vision.l1_events_v2 import CARDS,EventNet,reduced,stack_pixels
from clasher.vision.l1_offline import offline_ml
from collect_l1_rendered import progress


class Windows(Dataset):
    def __init__(self, root, split, augment):
        self.root=root;self.augment=augment
        rows=[json.loads(l) for l in (root/'inputs.jsonl').read_text().splitlines()]
        self.rows=[r for r in rows if r['split']==split]
        self.lookup={(r['episode_id'],int(r['frame_id'])):r for r in self.rows}
        events=defaultdict(list)
        for l in (root/'evaluation_only/events.jsonl').read_text().splitlines():
            e=json.loads(l);events[e['episode_id']].append(e)
        self.examples=[]
        for r in self.rows:
            tick=int(r['frame_id']);ep=r['episode_id']
            for stride in ((1,2) if augment else (2,)):
                if (ep,tick-stride*2) not in self.lookup or (ep,tick-stride) not in self.lookup:continue
                recent=[e for e in events[ep] if 1<=tick-e['tick']<=9]
                self.examples.append((r,stride,recent))
        self.positive=[i for i,(_,_,es) in enumerate(self.examples) if es]
        self.negative=[i for i,(_,_,es) in enumerate(self.examples) if not es]

    @lru_cache(maxsize=96)
    def image(self, name):
        return reduced(cv2.imread(str(self.root/name)))

    def __len__(self):return len(self.examples)

    def __getitem__(self,index):
        row,stride,events=self.examples[index]
        tick=int(row['frame_id']);ep=row['episode_id']
        images=[self.image(self.lookup[ep,t]['image']) for t in (tick-stride*2,tick-stride,tick)]
        tensor=stack_pixels(images)
        target=np.zeros((32,100,68),np.float32)
        yy,xx=np.mgrid[:100,:68]
        for event in events:
            px,py=event['pixel'];x=px*68/540-.5;y=(py-200)/8-.5
            # One exact positive cell plus a local soft target for weak anchor labels.
            gx,gy=int(round(x)),int(round(y))
            if 0<=gx<68 and 0<=gy<100:
                cls=event['player_id']*16+CARDS.index(event['card'])
                heat=np.exp(-((xx-gx)**2+(yy-gy)**2)/(2*1.25**2))
                target[cls]=np.maximum(target[cls],heat)
        if self.augment:
            # Translate pixels and target together; never change seat/color semantics.
            dx=random.randrange(-8,9);dy=random.randrange(-8,9)
            tensor=np.roll(tensor,(dy*4,dx*4),axis=(1,2));target=np.roll(target,(dy,dx),axis=(1,2))
            if dx>0:tensor[:,:,:dx*4]=0;target[:,:,:dx]=0
            if dx<0:tensor[:,:,dx*4:]=0;target[:,:,dx:]=0
            if dy>0:tensor[:,:dy*4]=0;target[:,:dy]=0
            if dy<0:tensor[:,dy*4:]=0;target[:,dy:]=0
            tensor[:3]*=random.uniform(.85,1.15)
        return torch.from_numpy(tensor.copy()),torch.from_numpy(target)


def loss_fn(logits,target):
    p=logits.sigmoid().clamp(1e-5,1-1e-5)
    positive=target.eq(1)
    negative=~positive
    loss=-(p.log()*(1-p)**2*positive+(1-p).log()*p**2*(1-target)**4*negative)
    return loss.sum()/positive.sum().clamp(min=1)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--epochs',type=int,default=24)
    p.add_argument('--steps',type=int,default=160)
    a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    offline_ml(a.output/'offline')
    torch.set_num_threads(2);cv2.setNumThreads(1)
    random.seed(6106);np.random.seed(6106);torch.manual_seed(6106)
    manifest=json.loads((a.dataset/'manifest.json').read_text())
    completed={json.loads(l)['episode_id'] for l in (a.dataset/'episodes.jsonl').read_text().splitlines()}
    need={e['episode_id'] for e in manifest['matches'] if e['split']=='train'}
    if not need<=completed:raise ValueError('Training episodes incomplete')
    train=Windows(a.dataset,'train',True)
    if not train.positive or not train.negative:raise ValueError('Need positive and negative stacks')
    net=EventNet().to('mps');opt=torch.optim.AdamW(net.parameters(),lr=.001,weight_decay=.0001)
    meta=dict(seed=6106,epochs=a.epochs,steps_per_epoch=a.steps,training_episodes=sorted(need),
              positive_stacks=len(train.positive),negative_stacks=len(train.negative),
              event_target_age_ticks=[1,9],input='current RGB plus two causal frame differences',
              initial_weights='random; v1 body model is fused separately',heldout_opened=False)
    (a.output/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    for epoch in range(a.epochs):
        net.train();losses=[];started=time.time()
        for step in range(a.steps):
            indices=random.choices(train.positive,k=2)+random.choices(train.negative,k=2)
            batch=[train[i] for i in indices]
            x=torch.stack([b[0] for b in batch]).to('mps');y=torch.stack([b[1] for b in batch]).to('mps')
            opt.zero_grad(set_to_none=True);loss=loss_fn(net(x),y);loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(),10)
            opt.step();losses.append(float(loss.detach().cpu()))
            if step%25==0:torch.mps.empty_cache()
        record=dict(epoch=epoch+1,loss=float(np.mean(losses)),seconds=time.time()-started)
        with (a.output/'training.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
        torch.save(dict(model={k:v.cpu() for k,v in net.state_dict().items()},epoch=epoch+1),a.output/'last.pt')
        if epoch+1 in (8,16,24):
            torch.save(dict(model={k:v.cpu() for k,v in net.state_dict().items()},epoch=epoch+1),a.output/f'epoch-{epoch+1}.pt')
        torch.mps.empty_cache();print(record,flush=True)
    model_hash=hashlib.sha256((a.output/'last.pt').read_bytes()).hexdigest()
    (a.output/'complete.json').write_text(json.dumps(dict(epochs=a.epochs,sha256=model_hash))+'\n')
    progress(f'v2 temporal fit completed {a.epochs} epochs on {len(need)} training episodes; no heldout fitting.')


if __name__=='__main__':main()
