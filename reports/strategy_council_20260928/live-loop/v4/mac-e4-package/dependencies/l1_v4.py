"""Pixel-only v4 body/HUD backbone, irregular temporal head and public fusion.

Tensor layouts use H,W: arena 832,448; cache 52,28; tile grid 64,36.
No native/training label imports. A cache survives gaps; masks mark absent tokens.
"""
from collections import deque
from dataclasses import dataclass
import math

import torch
from torch import nn
from torch.nn import functional as F


def conv(cin, cout, stride=1, dilation=1):
    return nn.Sequential(nn.Conv2d(cin, cout, 3, stride, dilation, dilation=dilation, bias=False),
                         nn.GroupNorm(8, cout), nn.SiLU())


class Residual(nn.Module):
    def __init__(self, channels):
        super().__init__();self.layers=nn.Sequential(conv(channels, channels),conv(channels, channels))
    def forward(self, x):return x+self.layers(x)


class Backbone(nn.Module):
    def __init__(self):
        super().__init__()
        self.stem=nn.Sequential(conv(3,32,2),conv(32,64,2))
        self.arena=nn.Sequential(Residual(64),conv(64,128,2),Residual(128),
                                 conv(128,256,2),Residual(256),conv(256,64))
    def forward(self, x):return self.arena(self.stem(x))


class HudHead(nn.Module):
    """Shared stem, spatially ordered atlas: four slots, next, elixir, clock.

The first five cells use one shared card classifier; no opponent HUD exists.
"""
    def __init__(self, cards):
        super().__init__();self.features=nn.Sequential(conv(64,64,2),conv(64,64,2))
        self.cards=nn.Linear(64,cards+1);self.elixir_digit=nn.Linear(64,11)
        self.elixir_fraction=nn.Linear(64,1);self.clock=nn.Linear(64,1);self.phase=nn.Linear(64,3)
    def forward(self, stem):
        x=F.adaptive_avg_pool2d(self.features(stem),(1,7)).squeeze(2).transpose(1,2)
        return dict(hud_cards=self.cards(x[:,:5]),elixir_digit=self.elixir_digit(x[:,5]),
                    elixir_fraction=self.elixir_fraction(x[:,5]).sigmoid().squeeze(-1),
                    clock_seconds=F.softplus(self.clock(x[:,6])).squeeze(-1),phase=self.phase(x[:,6]))


class BodyHead(nn.Module):
    def __init__(self, identities):
        super().__init__();self.features=conv(64,64)
        self.heatmap=nn.Conv2d(64,identities*2,1)
        self.box=nn.Conv2d(64,4,1);self.hp=nn.Conv2d(64,1,1);self.hp_visible=nn.Conv2d(64,1,1)
        nn.init.constant_(self.heatmap.bias,-4)
    def forward(self, x):
        x=F.interpolate(self.features(x),size=(64,36),mode='bilinear',align_corners=False)
        return dict(body_heatmap=self.heatmap(x),body_box=self.box(x).sigmoid(),
                    body_hp=self.hp(x).sigmoid(),body_hp_visible=self.hp_visible(x))


class TemporalHead(nn.Module):
    def __init__(self, cards, channels=64):
        super().__init__();self.cards=cards;self.spatial=conv(channels,channels)
        self.time=nn.Sequential(nn.Linear(2,channels),nn.SiLU(),nn.Linear(channels,channels))
        self.qkv=nn.Linear(channels,channels*3);self.proj=nn.Linear(channels,channels)
        self.norm=nn.LayerNorm(channels);self.ff=nn.Sequential(nn.Linear(channels,128),nn.SiLU(),nn.Linear(128,channels))
        # Two dilated layers + pooled arena context give global cue access.
        self.context=nn.Sequential(conv(channels,channels,dilation=8),conv(channels,channels,dilation=24))
        self.global_context=nn.Conv2d(channels,channels,1)
        self.classifier=conv(channels+8,64) # birth maps (2) projected to 8
        self.birth=nn.Conv2d(2,8,1)
        self.heatmap=nn.Conv2d(64,2*cards,1);self.age=nn.Conv2d(64,2*cards,1)
        self.sigma=nn.Conv2d(64,2*cards,1);self.origin=nn.Conv2d(64,2*5,1)
        nn.init.constant_(self.heatmap.bias,-4)
    def forward(self, cache, ages_ms, valid, births):
        b,t,c,h,w=cache.shape
        # Mask before every operation: changing padding pixels/timestamps cannot
        # change valid features, even if a caller supplies NaN padding.
        cache=torch.where(valid[:,:,None,None,None],cache,torch.zeros_like(cache))
        ages_ms=torch.where(valid,ages_ms,torch.zeros_like(ages_ms))
        x=self.spatial(cache.reshape(b*t,c,h,w)).reshape(b,t,c,h,w)
        seconds=ages_ms.clamp(min=0)/1000
        time=self.time(torch.stack((seconds,torch.log1p(seconds)),dim=-1))
        x=x+time[:,:,:,None,None]
        x=x.permute(0,3,4,1,2).reshape(b*h*w,t,c)
        mask=valid[:,None,None,:].expand(b,h,w,t).reshape(b*h*w,t)
        q,k,v=self.qkv(x).reshape(-1,t,3,4,c//4).permute(2,0,3,1,4).unbind(0)
        logits=(q@k.transpose(-2,-1))/math.sqrt(c//4)
        logits=logits.masked_fill(~mask[:,None,None,:],-10000.)
        weights=logits.softmax(-1)*mask[:,None,None,:].to(logits.dtype)
        weights=weights/weights.sum(-1,keepdim=True).clamp_min(1e-6)
        mixed=(weights@v).transpose(1,2).reshape(-1,t,c)
        mixed=self.norm(x+self.proj(mixed));mixed=mixed+self.ff(mixed)
        # Query = valid token with minimum age. Padding position is irrelevant.
        latest=ages_ms.masked_fill(~valid,float('inf')).argmin(1)
        idx=latest[:,None,None].expand(b,h,w).reshape(-1)
        mixed=mixed.gather(1,idx[:,None,None].expand(-1,1,c)).squeeze(1)
        mixed=mixed.reshape(b,h,w,c).permute(0,3,1,2)
        mixed=mixed+self.context(mixed)+self.global_context(mixed.mean((2,3),keepdim=True))
        mixed=F.interpolate(mixed,size=(64,36),mode='bilinear',align_corners=False)
        mixed=self.classifier(torch.cat((mixed,self.birth(births)),dim=1))
        present=valid.any(1)[:,None,None,None]
        return dict(event_heatmap=torch.where(present,self.heatmap(mixed),torch.full_like(self.heatmap(mixed),-10000)),
                    event_age_ms=self.age(mixed).sigmoid()*1500,
                    event_sigma_ms=F.softplus(self.sigma(mixed))*100+10,
                    cast_origin=self.origin(mixed))


class PerceptionV4(nn.Module):
    def __init__(self, cards, bodies):
        super().__init__();self.backbone=Backbone();self.hud=HudHead(cards)
        self.body=BodyHead(bodies);self.temporal=TemporalHead(cards)
    def encode(self, arena, hud):
        features=self.backbone(arena)
        result=self.body(features);result.update(self.hud(self.backbone.stem(hud)))
        result['features']=features
        return result
    def forward(self, arena, hud, ages_ms, valid, births):
        b,t,c,h,w=arena.shape
        arena=torch.where(valid[:,:,None,None,None],arena,torch.zeros_like(arena))
        features=self.backbone(arena.reshape(b*t,c,h,w))
        cache=features.reshape(b,t,*features.shape[1:])
        latest=ages_ms.masked_fill(~valid,float('inf')).argmin(1)
        current=cache[torch.arange(b,device=arena.device),latest]
        result=self.body(current);result.update(self.hud(self.backbone.stem(hud)))
        if self.training:
            # Self-generated visual births, never native IDs or truth counts.
            # Compare latest and previous valid detections of the same identity.
            with torch.no_grad():
                previous=ages_ms.masked_fill(~valid | (ages_ms<=0),float('inf')).argmin(1)
                old=self.body(cache[torch.arange(b,device=arena.device),previous])['body_heatmap'].sigmoid()
                scores=result['body_heatmap'].detach().sigmoid()
                peaks=(scores==F.max_pool2d(scores,3,1,1)) & (scores>=.5)
                fresh=peaks & (F.max_pool2d(old,7,1,3)<.3)
                visual_births=fresh.reshape(b,2,-1,64,36).sum(2).to(births.dtype)
                births=births+F.max_pool2d(visual_births,7,1,3).clamp(max=8)
        result.update(self.temporal(cache,ages_ms,valid,births));return result
    def parameter_counts(self):
        count=lambda m:sum(p.numel() for p in m.parameters())
        return dict(total=count(self),backbone=count(self.backbone),body=count(self.body),hud=count(self.hud),temporal=count(self.temporal))


class FeatureRing:
    """32 cached frames; never reset for elapsed gaps, only new episode."""
    def __init__(self, capacity=32):self.frames=deque(maxlen=capacity)
    def append(self, timestamp_ms, feature):
        if self.frames and timestamp_ms<=self.frames[-1][0]:raise ValueError('Noncausal frame')
        self.frames.append((timestamp_ms,feature.detach()))
    def window(self, length=16):
        if not self.frames:raise ValueError('Empty feature ring')
        rows=list(self.frames)[-length:];now=rows[-1][0];sample=rows[-1][1]
        cache=torch.stack([torch.zeros_like(sample)]*(length-len(rows))+[f for _,f in rows])
        ages=sample.new_tensor([0.]*(length-len(rows))+[now-t for t,_ in rows])
        valid=torch.arange(length,device=sample.device)>=length-len(rows)
        return cache[None],ages[None],valid[None]


def fit_isotonic(scores, labels):
    """Pooled-adjacent-violators; validation only, serializable monotone knots."""
    if len(scores)!=len(labels) or not scores:raise ValueError('Calibration samples required')
    groups={}
    for s,y in zip(scores,labels):
        if not 0<=s<=1 or y not in (0,1):raise ValueError('Invalid calibration')
        total,n=groups.get(float(s),(0,0));groups[float(s)]=(total+y,n+1)
    blocks=[]
    for x,(total,n) in sorted(groups.items()):
        blocks.append([x,x,total,n])
        while len(blocks)>1 and blocks[-2][2]/blocks[-2][3]>blocks[-1][2]/blocks[-1][3]:
            b=blocks.pop();a=blocks.pop();blocks.append([a[0],b[1],a[2]+b[2],a[3]+b[3]])
    return [[b[1],b[2]/b[3]] for b in blocks]


def calibrated(score, knots):
    for x,y in knots:
        if score<=x:return float(y)
    return float(knots[-1][1]) if knots else float(score)


@dataclass(frozen=True)
class EventCandidate:
    card: str
    side: int
    x_tiles: float
    y_tiles: float
    available_timestamp_ms: float
    execution_timestamp_ms: float
    execution_sigma_ms: float
    existence_q: float
    card_distribution: tuple
    cast_origin_probability: float | None = None


class EventFusion:
    def __init__(self, cards, spells, thresholds, calibration):
        self.cards=tuple(cards);self.spells=set(spells);self.thresholds=thresholds
        self.calibration=calibration;self.recent=[]
    def update(self, outputs, frame_ms, available_ms, own_hud_cards=()):
        scores=outputs['event_heatmap'][0].detach().float().sigmoid()
        peaks=(scores==F.max_pool2d(scores[None],3,1,1)[0])
        result=[];n=len(self.cards)
        self.recent=[e for e in self.recent if frame_ms-e.execution_timestamp_ms<=3300]
        origin_cards=('Rocket','Fireball','Arrows','Log','GoblinBarrel')
        # Bound pathological startup peaks before CPU decoding.
        values,indices=(scores*peaks).flatten().topk(min(256,scores.numel()))
        for score,index in zip(values.tolist(),indices.tolist()):
            cls,cell=divmod(index,64*36);gy,gx=divmod(cell,36);side,k=divmod(cls,n);card=self.cards[k]
            if score<self.thresholds.get(card,self.thresholds.get('default',.5)):continue
            if side==1 and card in self.spells and card not in own_hud_cards:continue
            age=float(outputs['event_age_ms'][0,cls,gy,gx]);sigma=float(outputs['event_sigma_ms'][0,cls,gy,gx])
            exec_ms=frame_ms-age;x=(gx+.5)/2;y=(gy+.5)/2
            if any(e.card==card and e.side==side and abs(e.execution_timestamp_ms-exec_ms)<=300
                   and math.hypot(e.x_tiles-x,e.y_tiles-y)<=1.5 for e in self.recent):continue
            dist=outputs['event_heatmap'][0,side*n:(side+1)*n,gy,gx].float().softmax(0)
            ps,ks=dist.topk(min(3,n))
            # Keep full-normalized probabilities for the top three; residual mass is explicit by subtraction.
            distribution=tuple((self.cards[i],float(p)) for i,p in zip(ks.tolist(),ps.tolist()))
            origin=None
            if card in origin_cards:origin=float(outputs['cast_origin'][0,side*5+origin_cards.index(card),gy,gx].sigmoid())
            e=EventCandidate(card,side,x,y,available_ms,exec_ms,sigma,
                             calibrated(score,self.calibration.get(card,self.calibration.get('default',[]))),distribution,origin)
            result.append(e);self.recent.append(e)
        return result


def decode_bodies(outputs, bodies, threshold=.5):
    scores=outputs['body_heatmap'][0].detach().float().sigmoid()
    peaks=scores==F.max_pool2d(scores[None],3,1,1)[0]
    values,indices=(scores*peaks).flatten().topk(min(128,scores.numel()));result=[]
    for q,index in zip(values.tolist(),indices.tolist()):
        if q<threshold:continue
        cls,cell=divmod(index,64*36);y,x=divmod(cell,36);owner,identity=divmod(cls,len(bodies))
        hp_known=float(outputs['body_hp_visible'][0,0,y,x].sigmoid())>=.5
        box=outputs['body_box'][0,:,y,x].detach().float().tolist()
        result.append(dict(identity=bodies[identity],owner=owner,x=(x+.5)/2,y=(y+.5)/2,
                           confidence=q,box=box,hp_fraction=float(outputs['body_hp'][0,0,y,x]) if hp_known else None))
    return result


class BodyTracker:
    """Two-pass high/low confidence association; confirmed births only.

Keeps weak detections for association without admitting them as new phantom tracks.
Positions/identity/owner come only from pixel detections. Missing HP is retained.
"""
    def __init__(self, high=.5, low=.1, max_age_ms=600):
        self.high=high;self.low=low;self.max_age=max_age_ms;self.tracks={};self.next_id=0
    def update(self, detections, now):
        from scipy.optimize import linear_sum_assignment
        import numpy as np
        self.tracks={i:t for i,t in self.tracks.items() if now-t['seen']<=self.max_age}
        unmatched=set(self.tracks);births=[];observed=[]
        for high in (True,False):
            ds=[d for d in detections if (d['confidence']>=self.high if high else self.low<=d['confidence']<self.high)]
            ids=sorted(unmatched);cost=np.full((len(ids),len(ds)),1e6)
            for i,tid in enumerate(ids):
                t=self.tracks[tid]
                for j,d in enumerate(ds):
                    if (t['identity'],t['owner'])==(d['identity'],d['owner']):cost[i,j]=math.hypot(t['x']-d['x'],t['y']-d['y'])
            paired=set()
            if cost.size:
                ii,jj=linear_sum_assignment(cost)
                for i,j in zip(ii,jj):
                    if cost[i,j]>1.5:continue
                    tid=ids[i];old=self.tracks[tid];d=dict(ds[j]);paired.add(j);unmatched.discard(tid)
                    if d['hp_fraction'] is None:d['hp_fraction']=old['hp_fraction']
                    d.update(track_id=tid,seen=now,hits=old['hits']+1)
                    self.tracks[tid]=d;observed.append(d)
                    if d['hits']==2:births.append(d)
            if high:
                for j,d in enumerate(ds):
                    if j in paired:continue
                    tid=self.next_id;self.next_id+=1
                    self.tracks[tid]=dict(d,track_id=tid,seen=now,hits=1)
        return [d for d in observed if d['hits']>=2],births


def body_action(identity):
    return {'Archer':'Archers','IceGolemite':'IceGolem','IceSpirits':'IceSpirit',
            'Skeleton':'Skeletons','Goblin':'Goblins','SpearGoblin':'SpearGoblins',
            'Minion':'Minions','Bat':'Bats','Barbarian':'Barbarians','RoyalHog':'RoyalHogs',
            'GoblinHut_Rework':'GoblinHut','Furnace_rework':'FirespiritHut'}.get(identity,identity)


def birth_maps(births, sources, now, device='cpu'):
    from clasher.vision.l1_events_v3 import secondary_birth, GROUP_COUNTS
    result=torch.zeros(1,2,64,36,device=device)
    sources=[dict(s,card=body_action(s['card'])) for s in sources]
    for b in births:
        card=body_action(b['identity'])
        if secondary_birth(card,b['owner'],b['x'],b['y'],sources,now):continue
        x=min(35,max(0,int(b['x']*2)));y=min(63,max(0,int(b['y']*2)))
        minimum,_=GROUP_COUNTS.get(card,(1,1))
        result[0,b['owner'],y,x]+=1/minimum
    return F.max_pool2d(result,7,1,3).clamp(max=8)


def prepare_pixels(image):
    """Accept only the sanitizer's 540x1140 canvas; copy allowlisted regions."""
    import cv2
    import numpy as np
    from clasher.vision.l1 import HAND, NEXT, CLOCK, ELIXIR_DIGIT, ELIXIR, crop
    if image.shape!=(1140,540,3):raise ValueError('Expected sanitized 540x1140 BGR pixels')
    arena=cv2.resize(image[200:1000],(448,832))
    cells=[cv2.resize(crop(image,box),(64,64)) for box in (*HAND,NEXT,ELIXIR_DIGIT,CLOCK)]
    cells[5][48:64]=cv2.resize(crop(image,ELIXIR),(64,16))
    return arena,np.concatenate(cells,axis=1)


class PixelPerception:
    """Reference streaming inference ABI for P1; only pixels and public time.

Returns board tracks, raw HUD and calibrated candidates for P2. Episode changes
reset state, elapsed gaps do not. Native objects, own truth and decks are absent.
"""
    def __init__(self,model,cards,bodies,spells,thresholds,calibration,device='cpu',*,body_threshold=.5):
        if type(body_threshold) not in (int,float) or body_threshold not in [i/10 for i in range(1,10)]:
            raise ValueError('Body threshold must use the registered 0.1..0.9 grid')
        self.model=model.to(device).eval();self.cards=cards;self.bodies=bodies;self.spells=spells
        self.thresholds=thresholds;self.calibration=calibration;self.device=device;self.episode=None
        self.body_threshold=body_threshold
    @torch.inference_mode()
    def step(self,image,episode,timestamp_ms,available_timestamp_ms=None):
        from dataclasses import asdict
        import time
        started=time.perf_counter()
        if episode!=self.episode:
            self.episode=episode;self.ring=FeatureRing();self.tracker=BodyTracker(high=self.body_threshold)
            self.fusion=EventFusion(self.cards,self.spells,self.thresholds,self.calibration)
            self.last_hand=None;self.last_elixir=None;self.sources=[];self.own_plays=[];self.ready_ms=timestamp_ms
        arena,hud=prepare_pixels(image)
        tensor=lambda x:torch.from_numpy(x.copy()).permute(2,0,1)[None].to(self.device).float()/255
        out=self.model.encode(tensor(arena),tensor(hud));self.ring.append(timestamp_ms,out['features'][0])
        tracks,births=self.tracker.update(decode_bodies(out,self.bodies,.1),timestamp_ms)
        sources=[dict(card=t['identity'],side=t['owner'],x=t['x'],y=t['y'],time=timestamp_ms) for t in tracks]
        self.sources=[s for s in self.sources if timestamp_ms-s['time']<=1600]+sources
        cache,ages,valid=self.ring.window()
        event=self.model.temporal(cache,ages,valid,birth_maps(births,self.sources,timestamp_ms,self.device))
        probs=out['hud_cards'][0].float().softmax(-1);ids=probs.argmax(-1).tolist()
        names=[self.cards[i] if i<len(self.cards) else None for i in ids]
        elixir=int(out['elixir_digit'][0].argmax())+float(out['elixir_fraction'][0])
        self.own_plays=[p for p in self.own_plays if timestamp_ms-p[1]<=600]
        if self.last_hand is not None and self.last_elixir-elixir>=.5 and float(probs[:4].max(-1).values.min())>=.7:
            for old,new in zip(self.last_hand,names[:4]):
                if old and old!=new:self.own_plays.append((old,timestamp_ms))
        self.last_hand=names[:4];self.last_elixir=elixir
        if self.device.startswith('cuda'):torch.cuda.synchronize()
        candidates=self.fusion.update(event,timestamp_ms,available_timestamp_ms if available_timestamp_ms is not None else self.ready_ms,
                                      [c for c,_ in self.own_plays])
        result=dict(episode_id=episode,timestamp_ms=timestamp_ms,tracks=tracks,
                    own_hand=names[:4],next_card=names[4],own_elixir=min(10,elixir),
                    hud_card_probabilities=probs.cpu().tolist(),clock_seconds=float(out['clock_seconds'][0]),
                    phase=int(out['phase'][0].argmax())+1,event_candidates=[asdict(e) for e in candidates])
        # Stamp after CPU fusion and serialization too, not merely GPU completion.
        self.ready_ms=max(self.ready_ms,timestamp_ms)+(time.perf_counter()-started)*1000
        available=self.ready_ms if available_timestamp_ms is None else available_timestamp_ms
        result['available_timestamp_ms']=available
        for candidate in result['event_candidates']:candidate['available_timestamp_ms']=available
        return result
