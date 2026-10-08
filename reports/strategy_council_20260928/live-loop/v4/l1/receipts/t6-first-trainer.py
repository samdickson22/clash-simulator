"""Fit temporal events on completed continuous training matches, never heldout."""
import argparse
from collections import defaultdict
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import random
import time

os.environ.setdefault('PYTORCH_MPS_HIGH_WATERMARK_RATIO','.35')
os.environ.setdefault('PYTORCH_MPS_LOW_WATERMARK_RATIO','.25')
import cv2
import numpy as np
import torch

from clasher.vision.l1 import Geometry,HAND,NEXT,crop
from clasher.vision.l1_events_v2 import reduced,stack_pixels,clock_markers,CARDS as OLD_CARDS
from clasher.vision.l1_events_v3 import StreamEventNet
from clasher.vision.l1_offline import offline_ml
from clasher.vision.l1_perception import art_vector
from collect_l1_rendered import REPORT,append,progress
from train_l1_events_v2 import loss_fn


def empty_cache(device):
    if device == 'mps': torch.mps.empty_cache()
    elif device == 'cuda': torch.cuda.empty_cache()


def read(path):return [json.loads(l) for l in path.read_text().splitlines()]


class StreamWindows:
    def __init__(self,dataset,audit,cards,split,cache_root):
        self.dataset=dataset;self.cards=cards;self.examples=[];self.positive=[];self.negative=[]
        self.geometry=Geometry(REPORT/'calibration.json');self.cache_root=cache_root
        cache_root.mkdir();self.needed=defaultdict(set)
        manifest=json.loads((dataset/'manifest.json').read_text())
        self.entries=[e for e in manifest['matches'] if e['split']==split]
        self.rows={};self.events={}
        for entry in self.entries:
            ep=entry['episode_id'];root=audit/ep
            if not (root/'complete.json').exists():raise ValueError('Incomplete audited training split')
            events=read(root/'events.jsonl');self.events[ep]=events
            self.rows[ep]=read(root/'frames.jsonl')
            for row in self.rows[ep]:
                if row['frame_index']<2:continue
                i=row['frame_index']
                if any(self.rows[ep][j]['timestamp_ms']-self.rows[ep][j-1]['timestamp_ms']>300 for j in (i-1,i)):
                    continue
                # Earlier capture protocol did not retain a complete terminal
                # cue window. Do not teach unlabelled terminal changes as negatives.
                if row['frame_index']>=len(self.rows[ep])-10:continue
                recent=[e for e in events if 1<=row['estimated_tick']-e['tick']<=8]
                if not recent and row['frame_index']%10:continue
                item=(ep,row['frame_index'],recent)
                self.examples.append(item)
                self.needed[ep].update(range(row['frame_index']-2,row['frame_index']+1))
                (self.positive if recent else self.negative).append(len(self.examples)-1)
        if not self.positive or not self.negative:raise ValueError('Need deployment and negative windows')

    @lru_cache(maxsize=192)
    def images(self,ep,index):
        images=[cv2.imread(str(self.cache_root/f'{ep}-{i}.jpg')) for i in range(index-2,index+1)]
        if any(image is None for image in images):raise ValueError('Missing cached training pixels')
        return images

    def sample(self,index):
        ep,i,events=self.examples[index]
        tensor=stack_pixels(self.images(ep,i))
        target=np.zeros((2*len(self.cards),100,68),np.float32)
        yy,xx=np.mgrid[:100,:68]
        for e in events:
            px,py=self.geometry.pixel(e['x_tiles'],e['y_tiles'])
            gx,gy=round(px*68/540-.5),round((py-200)/8-.5)
            if not (0<=gx<68 and 0<=gy<100):continue
            cls=e['player_id']*len(self.cards)+self.cards.index(e['card'])
            target[cls]=np.maximum(target[cls],np.exp(-((xx-gx)**2+(yy-gy)**2)/(2*1.25**2)))
        if random.random()<.5:
            tensor=tensor[:,:,::-1].copy();target=target[:,:,::-1].copy()
        tensor[:3]*=random.uniform(.9,1.1)
        return torch.from_numpy(tensor.copy()),torch.from_numpy(target.copy())

    def fit_hud(self,path):
        with np.load(REPORT/'v1/model/hud.npz',allow_pickle=False) as base:
            contents={k:base[k] for k in base.files}
        vectors=[];names=[];counts=defaultdict(int);cache_bytes=0;offsets=defaultdict(list)
        for entry in self.entries:
            ep=entry['episode_id'];events=self.events[ep]
            cap=cv2.VideoCapture(str(self.dataset/'videos'/f'{ep}.mp4'))
            for row in self.rows[ep]:
                ok,image=cap.read()
                if not ok:raise ValueError('Truncated HUD video')
                if row['frame_index'] in self.needed[ep]:
                    ok,jpg=cv2.imencode('.jpg',reduced(image),[cv2.IMWRITE_JPEG_QUALITY,55])
                    if not ok:raise ValueError('Thumbnail encoding failed')
                    cache_bytes+=len(jpg)
                    if cache_bytes>450*1024**2:raise RuntimeError('Training pixel cache exceeded 450 MiB reserve')
                    (self.cache_root/f"{ep}-{row['frame_index']}.jpg").write_bytes(jpg)
                if row['frame_index']%3==0:
                    active=[e for e in events if 1<=row['estimated_tick']-e['tick']<=8 and e['card_id']//1000000!=28]
                    markers=clock_markers(image) if active else []
                    for event in active:
                        px,py=self.geometry.pixel(event['x_tiles'],event['y_tiles'])
                        same=[m for m in markers if m['player_id']==event['player_id'] and np.hypot(m['px']-px,m['py']-py)<70]
                        if same:
                            m=min(same,key=lambda m:np.hypot(m['px']-px,m['py']-py))
                            offsets[f"{event['player_id']}:{event['card']}"].append([px-m['px'],py-m['py']])
                if row['frame_index']%10:continue
                t=row['estimated_tick']
                if any(e['player_id']==1 and abs(e['tick']-t)<30 for e in events):continue
                before=row['native_before']['players'][1];after=row['native_after']['players'][1]
                if before['hand']!=after['hand'] or before['cycle']!=after['cycle']:continue
                for name,box in zip([*before['hand'],before['cycle'][0]],[*HAND,NEXT]):
                    if name is None or counts[name]>=60:continue
                    vectors.append(art_vector(crop(image,box)));names.append(name);counts[name]+=1
            cap.release()
        if set(self.cards)-set(names):raise ValueError('Incomplete C56 own-HUD training coverage')
        contents['art']=np.stack(vectors);contents['names']=np.asarray(names)
        np.savez_compressed(path,**contents)
        self.marker_offsets={key:np.median(values,axis=0).tolist() for key,values in offsets.items() if len(values)>=10}
        (path.parent/'marker-offsets.json').write_text(json.dumps(dict(offsets=self.marker_offsets,
            samples={k:len(v) for k,v in offsets.items()},split='train'),indent=2)+'\n')
        return dict(counts)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',type=Path,required=True);p.add_argument('--audit',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--epochs',type=int,default=24)
    p.add_argument('--steps',type=int,default=400)
    p.add_argument('--device',default='mps',choices=['mps','cuda','cpu']);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);offline_ml(a.output/'offline')
    torch.set_num_threads(2);cv2.setNumThreads(1)
    random.seed(6107);np.random.seed(6107);torch.manual_seed(6107)
    manifest=json.loads((a.dataset/'manifest.json').read_text());cards=manifest['cards']
    train=StreamWindows(a.dataset,a.audit,cards,'train',a.output/'training-pixels')
    net=StreamEventNet(cards)
    old=torch.load(REPORT/'v2/model/last.pt',map_location='cpu',weights_only=True)['model']
    state=net.state_dict()
    for key in state:
        if key.startswith('body.'):state[key]=old[key]
    for side in (0,1):
        for i,name in enumerate(OLD_CARDS):
            for key in ('heatmap.weight','heatmap.bias'):
                state[key][side*len(cards)+cards.index(name)]=old[key][side*len(OLD_CARDS)+i]
    net.load_state_dict(state);net.to(a.device)
    optimizer=torch.optim.AdamW(net.parameters(),lr=.0005,weight_decay=.0001)
    meta=dict(device=a.device,seed=6107,training_episodes=[e['episode_id'] for e in train.entries],
        positive_windows=len(train.positive),negative_windows=len(train.negative),
        input='current pixels and two causal frame differences',timing='empirical intervals, not exact tick fences',
        heldout_pixels_or_labels_opened=False,cards=cards,hud_counts=train.fit_hud(a.output/'hud.npz'),
        versions=dict(torch=torch.__version__,numpy=np.__version__,opencv=cv2.__version__),
        dataset_manifest_sha256=hashlib.sha256((a.dataset/'manifest.json').read_bytes()).hexdigest(),
        audit_hashes={str(a.audit/e['episode_id']/name):hashlib.sha256((a.audit/e['episode_id']/name).read_bytes()).hexdigest()
            for e in train.entries for name in ('frames.jsonl','events.jsonl')})
    (a.output/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
    for epoch in range(a.epochs):
        net.train();losses=[];start=time.perf_counter()
        for step in range(a.steps):
            indices=random.choices(train.positive,k=3)+random.choices(train.negative,k=1)
            batch=[train.sample(i) for i in indices]
            x=torch.stack([b[0] for b in batch]).to(a.device);y=torch.stack([b[1] for b in batch]).to(a.device)
            optimizer.zero_grad(set_to_none=True);loss=loss_fn(net(x),y)
            if not bool(torch.isfinite(loss).item()):raise ValueError('Nonfinite training loss')
            loss.backward()
            torch.nn.utils.clip_grad_norm_(net.parameters(),10);optimizer.step()
            losses.append(float(loss.detach().cpu()))
            if step%25==0:empty_cache(a.device)
        record=dict(epoch=epoch+1,loss=float(np.mean(losses)),seconds=time.perf_counter()-start)
        append(a.output/'training.jsonl',record)
        payload=dict(model={k:v.cpu() for k,v in net.state_dict().items()},cards=cards,
            spells=[n for n in cards if manifest['ids'][n]//1000000==28],epoch=epoch+1,marker_offsets=train.marker_offsets)
        torch.save(payload,a.output/'last.pt')
        if epoch+1 in (8,16,24):torch.save(payload,a.output/f'epoch-{epoch+1}.pt')
        empty_cache(a.device);print(record,flush=True)
    (a.output/'complete.json').write_text(json.dumps(dict(epochs=a.epochs,
        sha256=hashlib.sha256((a.output/'last.pt').read_bytes()).hexdigest()))+'\n')
    progress(f'v3 fit complete: {a.epochs} epochs on continuous training windows; heldout unopened.')


if __name__=='__main__':main()
