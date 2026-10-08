"""Training-label adapter. This module is never imported by pixel inference."""
import bisect
from collections import OrderedDict
import gzip
import hashlib
import json
from pathlib import Path
import random

import cv2
import numpy as np
import torch
from torch.nn import functional as F

from clasher.vision.l1 import Geometry, HAND, NEXT, CLOCK, ELIXIR_DIGIT, ELIXIR, crop

ROOT=Path(__file__).resolve().parents[5]
CALIBRATION=ROOT/'reports/strategy_council_20260928/live-loop/l1/calibration.json'


def read(path):return [json.loads(x) for x in path.read_text().splitlines()]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(source, split_file, split):
    if split not in ('train','validation'):raise ValueError('Heldout forbidden in shakedown/training loader')
    frozen=json.loads(split_file.read_text());members={r['seed']:r for r in frozen['matches']};rows=[]
    for path in sorted(source.glob('*/receipt.json')):
        r=json.loads(path.read_text())
        if r.get('split')!=split:continue
        m=members[r['seed']]
        if m['split']!=split or m['decks']!=r['decks']:raise ValueError('Frozen split mismatch')
        rows.append(dict(path=str(path.parent),receipt_sha256=sha(path),**r))
    return rows,frozen['cards']


from clasher.vision.l1_v4 import prepare_pixels as pixels


def normalized_body(name):
    name=(name or '').lower().replace('_','')
    return {'goblinstab':'goblin','goblinsspear':'speargoblin','goblins':'goblin',
            'skeletons':'skeleton','tower':'princesstower','minions':'minion',
            'archers':'archer','icespirit':'icespirits'}.get(name,name)


def trusted_body(o):
    # Some rich native catalog names disagree with the card-derived body hint.
    # Do not turn those contradictions or projectile metadata into body labels.
    return (o.get('max_hp') is not None and o['max_hp']>0 and o.get('body_name')
            and normalized_body(o['body_name'])==normalized_body(o.get('body_name_hint')))


class Windows:
    def __init__(self, source, split_file, output, *, split='train', max_matches=0, windows_per_match=32, seed=6108):
        self.output=Path(output);self.output.mkdir(parents=True,exist_ok=True)
        self.augment=split=='train';self.rng=random.Random(seed)
        inv=self.output/'inventory.json'
        if inv.exists():
            saved=json.loads(inv.read_text());self.receipts=saved['matches'];self.cards=saved['cards']
            if saved['split']!=split:raise ValueError('Cache split mismatch')
        else:
            self.receipts,self.cards=inventory(source,split_file,split)
            if max_matches:self.receipts=self.receipts[:max_matches]
            inv.write_text(json.dumps(dict(split=split,cards=self.cards,matches=self.receipts,split_sha256=sha(split_file)),indent=2)+'\n')
        self.frames={};self.hud={};self.events={};self.objects={};self.examples=[];self.cache=OrderedDict()
        bodies=set();self.geo=Geometry(CALIBRATION)
        for r in self.receipts:
            if r['split']!=split or split not in ('train','validation'):raise ValueError('Split isolation failure')
            root=Path(r['path']);ep=r['episode']
            if sha(root/'receipt.json')!=r['receipt_sha256']:raise ValueError('Changed receipt')
            # Validate only files actually consumed, after split admission.
            for name in ('frames.jsonl','hud.jsonl','events.jsonl','objects.jsonl.gz','video.mp4'):
                if sha(root/name)!=r['files'][name]:raise ValueError(f'Bad payload: {name}')
            self.frames[ep]=read(root/'frames.jsonl');self.hud[ep]={h['seq']:h for h in read(root/'hud.jsonl')}
            self.events[ep]=[e for e in read(root/'events.jsonl') if e['accepted'] and e['kind']!='champion ability']
            with gzip.open(root/'objects.jsonl.gz','rt') as f:rows=[json.loads(x) for x in f]
            self.objects[ep]=rows
            bodies.update(o['body_name'] for row in rows for o in row['objects'] if trusted_body(o))
            # Fixed endpoints, half event-proximal and half uniform negatives/scene windows.
            frames=self.frames[ep];ticks=[(f['tick_lo']+f['tick_hi'])/2 for f in frames]
            positive=[bisect.bisect_left(ticks,e['exec_tick']+self.rng.randrange(1,21)) for e in self.events[ep]]
            positive=[i for i in positive if 2<=i<len(frames)]
            chosen=self.rng.sample(positive,min(len(positive),windows_per_match//2))
            body_ends=[bisect.bisect_left(ticks,r['tick']) for r in rows if any(trusted_body(o) and o.get('visible_hint')=='visible' and o.get('deploying') is False for o in r['objects'])]
            body_ends=sorted(set(i for i in body_ends if 2<=i<len(frames)))
            chosen+=self.rng.sample(body_ends,min(len(body_ends),windows_per_match//4))
            chosen+=self.rng.sample(range(2,len(frames)),min(len(frames)-2,windows_per_match-len(chosen)))
            self.examples.extend((ep,i) for i in sorted(set(chosen)))
        vocab=self.output/'bodies.json'
        if vocab.exists():self.bodies=json.loads(vocab.read_text())
        else:self.bodies=sorted(bodies);vocab.write_text(json.dumps(self.bodies)+'\n')
        self.paths={r['episode']:Path(r['path'])/'video.mp4' for r in self.receipts}
        if not self.examples:raise ValueError('No training windows')
        objects=[o for rows in self.objects.values() for row in rows for o in row['objects']]
        audit=dict(object_rows=len(objects),trusted_identity=sum(bool(trusted_body(o)) for o in objects),
                   contradictory_identity=sum(bool(o.get('body_name') and o.get('body_name_hint') and normalized_body(o['body_name'])!=normalized_body(o['body_name_hint'])) for o in objects),
                   visible_nondeploying=sum(bool(trusted_body(o) and o.get('visible_hint')=='visible' and o.get('deploying') is False) for o in objects),
                   policy='Contradictory identity, projectiles and unknown visibility are masked, never positive body targets')
        (self.output/'label-audit.json').write_text(json.dumps(audit,indent=2)+'\n')

    def __len__(self):return len(self.examples)

    def subset(self, ep, end):
        frames=self.frames[ep];now=frames[end]['produced_at'];chosen=[end]
        rate=self.rng.uniform(5,30) if self.augment else 20
        gap=self.rng.uniform(.15,1.2) if self.augment and self.rng.random()<.35 else 0
        due=now-1/rate;gap_at=self.rng.randrange(1,15)
        for i in range(end-1,-1,-1):
            if frames[i]['produced_at']<=due+1e-5:
                chosen.append(i);due=frames[i]['produced_at']-1/rate
                if len(chosen)==gap_at:due-=gap
                if len(chosen)==16:break
        return list(reversed(chosen))

    def images(self, ep, indices):
        # Decode only the required contiguous span; no full-video RAM or disk cache.
        key=(ep,tuple(indices))
        if key in self.cache:return self.cache[key]
        cap=cv2.VideoCapture(str(self.paths[ep]));cap.set(cv2.CAP_PROP_POS_FRAMES,indices[0]);selected=set(indices);images=[]
        try:
            for i in range(indices[0],indices[-1]+1):
                ok,img=cap.read()
                if not ok:raise ValueError('Truncated training media')
                if i in selected:images.append(img)
        finally:cap.release()
        self.cache[key]=images
        while len(self.cache)>2:self.cache.popitem(last=False)
        return images

    def sample(self, index):
        ep,end=self.examples[index];indices=self.subset(ep,end);images=self.images(ep,indices)
        arenas=[];hud=None
        quality=self.rng.randrange(50,96) if self.augment and self.rng.random()<.3 else None
        for image in images:
            if quality is not None:
                ok,encoded=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,quality])
                if not ok:raise RuntimeError('Augmentation encoding failed')
                image=cv2.imdecode(encoded,cv2.IMREAD_COLOR)
            arena,hud=pixels(image);arenas.append(arena)
        frames=self.frames[ep];now=frames[end]['produced_at']
        ages=np.asarray([0.]*(16-len(indices))+[(now-frames[i]['produced_at'])*1000 for i in indices],np.float32)
        valid=np.asarray([False]*(16-len(indices))+[True]*len(indices))
        arenas=[np.zeros_like(arenas[-1])]*(16-len(arenas))+arenas
        x=np.stack(arenas).transpose(0,3,1,2).astype(np.float32)/255
        h=hud.transpose(2,0,1).astype(np.float32)/255
        target=self.targets(ep,end)
        if self.augment:
            gain=self.rng.uniform(.85,1.15);gamma=self.rng.uniform(.9,1.1)
            x=np.clip(x*gain,0,1)**gamma;h=np.clip(h*gain,0,1)**gamma
            if self.rng.random()<.5:
                x=x[:,:,:,::-1].copy()
                for key in ('event','age','event_mask','origin','origin_mask','body','body_valid','box','hp','hp_mask','body_mask'):
                    target[key]=target[key][...,::-1].copy()
                target['box'][0]=1-target['box'][0]
            if self.rng.random()<.5:
                scale=self.rng.uniform(.98,1.02);dx=self.rng.uniform(-4,4);dy=self.rng.uniform(-4,4)
                matrix=np.asarray([[scale,0,(1-scale)*224+dx],[0,scale,(1-scale)*416+dy]],np.float32)
                x=np.stack([cv2.warpAffine(frame.transpose(1,2,0),matrix,(448,832)).transpose(2,0,1) for frame in x])
                # Convert this pixel affine into half-tile coordinates with the frozen calibration.
                tile_to_crop=np.vstack((self.geo.matrix,[0,0,1])).copy()
                tile_to_crop=np.diag([448/540,832/800,1])@np.asarray([[1,0,0],[0,1,-200],[0,0,1]])@tile_to_crop
                transform=np.linalg.inv(tile_to_crop)@np.vstack((matrix,[0,0,1]))@tile_to_crop
                grid=np.diag([2,2,1])@transform@np.diag([.5,.5,1])
                for key in ('event','age','event_mask','origin','origin_mask','body','body_valid','box','hp','hp_mask','body_mask'):
                    target[key]=np.stack([cv2.warpAffine(channel,grid[:2].astype(np.float32),(36,64),flags=cv2.INTER_NEAREST) for channel in target[key]])
                target['box'][0]=target['box'][0]*scale+(1-scale)/2+dx/448
                target['box'][1]=target['box'][1]*scale+(1-scale)/2+dy/832
                target['box'][2:]*=scale
            jitter=np.asarray([self.rng.uniform(-10,10) if v and a else 0 for v,a in zip(valid,ages)],np.float32)
            ages=np.maximum(0,ages+jitter)
        target={k:torch.as_tensor(v) for k,v in target.items()}
        return dict(arena=torch.from_numpy(x),hud=torch.from_numpy(h),ages=torch.from_numpy(ages),valid=torch.from_numpy(valid),
                    births=torch.zeros(2,64,36),target=target)

    def targets(self, ep, index):
        f=self.frames[ep][index];tick=(f['tick_lo']+f['tick_hi'])/2;c=len(self.cards)
        heat=np.zeros((2*c,64,36),np.float32);age=np.zeros_like(heat);emask=np.zeros_like(heat)
        origin=np.zeros((10,64,36),np.float32);omask=np.zeros_like(origin)
        yy,xx=np.mgrid[:64,:36]
        for e in self.events[ep]:
            dt=(tick-e['exec_tick'])*50
            if not 0<=dt<=1500:continue
            gx=min(35,max(0,int(e['tile'][0]*2)));gy=min(63,max(0,int(e['tile'][1]*2)))
            cls=e['side']*c+self.cards.index(e['card']);peak=np.exp(-((xx-gx)**2+(yy-gy)**2)/2)
            heat[cls]=np.maximum(heat[cls],peak);age[cls,gy,gx]=dt;emask[cls,gy,gx]=1
            origins=('Rocket','Fireball','Arrows','Log','GoblinBarrel')
            if e['card'] in origins:
                k=origins.index(e['card']);origin[e['side']*5+k,gy,gx]=1
                omask[k,gy,gx]=1;omask[5+k,gy,gx]=1
        b=len(self.bodies);body=np.zeros((2*b,64,36),np.float32);body_valid=np.ones((1,64,36),np.float32)
        box=np.zeros((4,64,36),np.float32);hp=np.zeros((1,64,36),np.float32)
        hp_mask=np.zeros_like(hp);body_mask=np.zeros_like(hp)
        rows=self.objects[ep];times=[r['tick'] for r in rows];j=max(0,bisect.bisect_right(times,tick)-1)
        stale=abs(times[j]-tick)>5
        if stale:body_valid[:]=0
        else:
            # First mask ambiguous objects. Unknown visibility is not a positive or a negative.
            for o in rows[j]['objects']:
                gx=min(35,max(0,int(o['x']/500)));gy=min(63,max(0,int(o['y']/500)))
                known=trusted_body(o) and o['body_name'] in self.bodies and o.get('visible_hint')=='visible' and o.get('deploying') is False
                if not known:body_valid[:,max(0,gy-3):gy+4,max(0,gx-3):gx+4]=0
            for o in rows[j]['objects']:
                if not trusted_body(o) or o['body_name'] not in self.bodies or o.get('visible_hint')!='visible' or o.get('deploying') is not False:continue
                gx=min(35,max(0,int(o['x']/500)));gy=min(63,max(0,int(o['y']/500)))
                cls=o['owner']*b+self.bodies.index(o['body_name'])
                body[cls]=np.maximum(body[cls],np.exp(-((xx-gx)**2+(yy-gy)**2)/2))
                body_valid[0,gy,gx]=1;body_mask[0,gy,gx]=1
                name='Tower' if o['body_name']=='PrincessTower' else o['body_name']
                x1,y1,x2,y2=self.geo.box(name,o['x']/1000,o['y']/1000)
                box[:,gy,gx]=[(x1+x2)/1080,(y1+y2-400)/1600,(x2-x1)/540,(y2-y1)/800]
                if o['hp'] is not None and o['max_hp'] and o['max_hp']>0:
                    hp[0,gy,gx]=np.clip(o['hp']/o['max_hp'],0,1);hp_mask[0,gy,gx]=1
        hud=self.hud[ep][f['seq']]
        cards=np.asarray([self.cards.index(n) if n in self.cards else c for n in (*hud['own_hand'],hud['own_next_card'])],np.int64)
        return dict(event=heat,age=age,event_mask=emask,origin=origin,origin_mask=omask,
                    body=body,body_valid=body_valid,box=box,hp=hp,hp_mask=hp_mask,body_mask=body_mask,
                    hud_cards=cards,elixir_digit=np.int64(hud['displayed_integer_elixir']),
                    elixir_fraction=np.float32(hud['own_elixir']-int(hud['own_elixir'])),
                    clock=np.float32(hud['clock']),phase=np.int64({1:0,2:1,3:2}[hud['phase']]))


def focal(logits, target, mask=None):
    p=logits.float().sigmoid().clamp(1e-5,1-1e-5);positive=target.eq(1)
    loss=-(p.log()*(1-p)**2*positive+(1-p).log()*p**2*(1-target)**4*~positive)
    if mask is not None:loss=loss*mask;positive=positive*mask
    return loss.sum()/positive.sum().clamp_min(1)


def masked_mean(x, mask):return (x*mask).sum()/mask.expand_as(x).sum().clamp_min(1)


def loss_fn(out, t):
    event=focal(out['event_heatmap'],t['event'])
    sigma=out['event_sigma_ms'].float()/1000
    residual=(out['event_age_ms'].float()-t['age'])/1000
    age=masked_mean(.5*(residual/sigma)**2+sigma.log(),t['event_mask'])
    body=focal(out['body_heatmap'],t['body'],t['body_valid'])
    box=masked_mean(F.smooth_l1_loss(out['body_box'].float(),t['box'],reduction='none'),t['body_mask'])
    hp=masked_mean((out['body_hp'].float()-t['hp']).abs(),t['hp_mask'])
    hp_visible=masked_mean(F.binary_cross_entropy_with_logits(out['body_hp_visible'].float(),t['hp_mask'],reduction='none'),t['body_mask'])
    origin=masked_mean(F.binary_cross_entropy_with_logits(out['cast_origin'].float(),t['origin'],reduction='none'),t['origin_mask'])
    hud=F.cross_entropy(out['hud_cards'].flatten(0,1).float(),t['hud_cards'].flatten())
    hud=hud+F.cross_entropy(out['elixir_digit'].float(),t['elixir_digit'])
    hud=hud+F.smooth_l1_loss(out['elixir_fraction'].float(),t['elixir_fraction'])
    hud=hud+F.smooth_l1_loss(out['clock_seconds'].float()/180,t['clock']/180)+F.cross_entropy(out['phase'].float(),t['phase'])
    parts=dict(event=event,age=age,body=body,box=box,hp=hp,hp_visible=hp_visible,origin=origin,hud=hud)
    return sum(parts.values()),parts


def batch(sample,device):
    return {k:({n:x[None].to(device) for n,x in v.items()} if k=='target' else v[None].to(device)) for k,v in sample.items()}
