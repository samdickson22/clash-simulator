"""Causal three-frame deployment model and public-cue fusion.

Only sanitized pixels and public v1 predictions enter this module. The temporal
stack contains the current image and differences from two earlier images.
"""
from collections import deque
from dataclasses import replace
import math

import cv2
import numpy as np
import torch
from torch import nn

from clasher.rl.live_inference_contract import PublicPlayEvent
from clasher.vision.l1_perception import ACTION_NAMES
from clasher.vision.l1_temporal import DeploymentTracker

CARDS = ('Archers','Cannon','DarkPrince','Fireball','Giant','Goblins','HogRider',
         'IceGolem','IceSpirit','Knight','Log','Musketeer','Prince','Skeletons','Tesla','Zap')
SPELLS = frozenset(('Fireball','Log','Zap'))


def reduced(image):
    if image.shape != (1140,540,3):
        raise ValueError('Expected sanitized calibrated pixels')
    return cv2.resize(image[200:1000], (272,400), interpolation=cv2.INTER_AREA)


def stack_pixels(images):
    a,b,c = [im.astype(np.float32)/255 for im in images]
    return np.concatenate((c, c-b, c-a), axis=2).transpose(2,0,1)


class EventNet(nn.Module):
    def __init__(self):
        super().__init__()
        layers=[]
        for ci,co,stride,dilation in ((9,24,2,1),(24,48,2,1),(48,64,1,1),
                                     (64,64,1,2),(64,64,1,3),(64,64,1,2)):
            layers.extend((nn.Conv2d(ci,co,3,stride,padding=dilation,dilation=dilation),
                           nn.GroupNorm(8,co),nn.SiLU()))
        self.body=nn.Sequential(*layers)
        self.heatmap=nn.Conv2d(64,32,1)
        nn.init.constant_(self.heatmap.bias,-4)

    def forward(self, x):
        return self.heatmap(self.body(x))


def clock_markers(image):
    """Visible gold-rimmed deploy clocks; never infer card identity here."""
    arena=image[200:1000]
    hsv=cv2.cvtColor(arena,cv2.COLOR_BGR2HSV)
    h,s,v=cv2.split(hsv)
    gold=((h>14)&(h<40)&(s>110)&(v>100)).astype(np.uint8)
    red=(((h<10)|(h>170))&(s>80)&(v>140)).astype(np.uint8)
    blue=((h>88)&(h<113)&(s>50)&(v>140)).astype(np.uint8)
    circles=cv2.HoughCircles(cv2.cvtColor(arena,cv2.COLOR_BGR2GRAY),cv2.HOUGH_GRADIENT,
                            1,22,param1=80,param2=18,minRadius=10,maxRadius=21)
    result=[]
    if circles is None:return result
    for x,y,r in circles[0]:
        x,y,r=round(float(x)),round(float(y)),float(r)
        if x<23 or x>=517 or y<23 or y>=777:continue
        yy,xx=np.mgrid[-23:24,-23:24]
        d=np.hypot(xx,yy)
        ring=(d>.70*r)&(d<1.05*r);inner=d<.60*r
        gold_score=float(gold[y-23:y+24,x-23:x+24][ring].mean())
        colors=[float(c[y-23:y+24,x-23:x+24][inner].mean()) for c in (red,blue)]
        side=int(np.argmax(colors))
        if gold_score>=.28 and colors[side]>=.38:
            result.append(dict(player_id=side,px=float(x),py=float(y+200),radius=r,
                               confidence=min(1.,gold_score*1.6+colors[side]*.5)))
    return result


class TemporalEventDetector:
    def __init__(self, weights, geometry, *, device='mps', threshold=.3, marker_offsets=None):
        self.net=EventNet().to(device)
        payload=torch.load(weights,map_location='cpu',weights_only=True)
        self.net.load_state_dict(payload['model']);self.net.eval()
        self.device=device;self.geo=geometry;self.threshold=threshold
        self.offsets=marker_offsets or {'0':[0.,-8.], '1':[0.,20.]}
        self.episode=None

    def step(self, image, frame):
        now=frame.timestamp_ms
        if frame.episode_id!=self.episode:
            self.episode=frame.episode_id
            self.images=deque(maxlen=3)
            self.tracker=DeploymentTracker()
            self.markers=[];self.recent=[];self.pending=[]
            self.last_time=None
            self.fusion=EventFusion(self.threshold)
        if self.last_time is not None and now<=self.last_time:
            raise ValueError('Noncausal frame time')
        if self.last_time is not None and now-self.last_time>250:
            self.images.clear()
            self.markers=[]
        fresh=not self.images
        self.images.append(reduced(image))
        while len(self.images)<3:self.images.append(self.images[0])
        tracked=self.tracker.update(frame)
        births=list(tracked.play_events)
        self.pending=[p for p in self.pending if now-p['time']<=450]
        for event in births:
            self.pending.append(dict(event=event,time=now))
        self.markers=[m for m in self.markers if now-m['time']<=500]
        current=clock_markers(image)
        for m in current:
            old=next((p for p in self.markers if p['player_id']==m['player_id'] and
                      math.hypot(p['px']-m['px'],p['py']-m['py'])<28),None)
            if old is None:
                m.update(time=now,first=now)
                self.markers.append(m)
            else:
                old['time']=now
        with torch.inference_mode():
            tensor=torch.from_numpy(stack_pixels(list(self.images))[None]).to(self.device)
            scores=self.net(tensor).sigmoid()[0].cpu().numpy()
        candidates=[]
        for cls in range(32):
            values=scores[cls]
            peaks=(values==cv2.dilate(values,np.ones((5,5),np.uint8)))&(values>=.03)
            for gy,gx in zip(*np.where(peaks)):
                px=(gx+.5)*540/68;py=200+(gy+.5)*8
                x,y=self.geo.tile(px,py)
                if 0<=x<=18 and 0<=y<=32:
                    candidates.append(dict(player_id=cls//16,card=CARDS[cls%16],x=float(x),y=float(y),
                                           confidence=float(values[gy,gx]),source='temporal_pixels'))
        for c in list(candidates):
            if c['card'] in SPELLS or c['confidence']<.15:continue
            support=next((p['event'] for p in self.pending if p['event'].card==c['card']
                          and p['event'].player_id==c['player_id'] and p['event'].x_tiles is not None
                          and math.hypot(p['event'].x_tiles-c['x'],p['event'].y_tiles-c['y'])<=1.5),None)
            if support:
                candidates.append(dict(c,confidence=min(.95,c['confidence']+.4),source='birth_and_temporal'))
        for p in self.pending:
            e=p['event']
            if e.player_id==1 and e.card in SPELLS:
                spatial=[c for c in candidates if c['player_id']==1 and c['card']==e.card and c['confidence']>=.5]
                best=max(spatial,key=lambda c:c['confidence']) if spatial else None
                candidates.append(dict(player_id=1,card=e.card,x=best['x'] if best else None,
                    y=best['y'] if best else None,confidence=e.confidence,source='own_hud'))
        # Marker identity comes from v1 bodies or own visible hand transitions.
        for marker in self.markers:
            if now-marker['first']>450:continue
            side=marker['player_id'];ox,oy=self.offsets[str(side)]
            x,y=self.geo.tile(marker['px']+ox,marker['py']+oy)
            nearby=[]
            for e in tracked.entities:
                if e.player_id!=side or e.card in ('Tower','KingTower'):continue
                distance=math.hypot(e.x_tiles-x,e.y_tiles-y)
                if distance<=2.0:
                    nearby.append((distance,ACTION_NAMES.get(e.card,e.card),e.confidence))
            own=[p for p in self.pending if p['event'].player_id==side==1 and p['event'].card not in SPELLS
                 and any(card==p['event'].card for _,card,_ in nearby)
                 and abs(p['time']-marker['first'])<=400]
            if own:
                card=own[-1]['event'].card;conf=own[-1]['event'].confidence
            elif nearby:
                nearby.sort();_,card,conf=nearby[0]
                distinct={c for d,c,s in nearby if d<=nearby[0][0]+.25}
                if len(distinct)>1:continue
            else:continue
            if card not in CARDS or card in SPELLS:continue
            ox,oy=self.offsets.get(f'{side}:{card}',self.offsets[str(side)])
            x,y=self.geo.tile(marker['px']+ox,marker['py']+oy)
            corroborated=any(p['event'].player_id==side and p['event'].card==card
                            and abs(p['time']-marker['first'])<=400 for p in self.pending)
            candidates.append(dict(player_id=side,card=card,x=float(x),y=float(y),
                                   confidence=max(.9,min(marker['confidence'],conf)) if corroborated else min(marker['confidence'],conf),
                                   source='clock_and_v1_identity'))
        events=self.fusion.update(frame.frame_id,now,candidates,fresh=fresh)
        self.last_time=now
        return replace(tracked,play_events=tuple(events)),dict(markers=current,candidates=candidates,fresh=fresh)


class EventFusion:
    """Replayable fusion over public candidates, with no labels or future frames."""
    def __init__(self,threshold=.3,marker_minimum=.4):
        self.threshold=threshold;self.marker_minimum=marker_minimum
        self.recent=[]

    def update(self,frame_id,now,candidates,*,fresh=False):
        events=[]
        self.recent=[e for e in self.recent if now-e['time']<1800]
        for c in sorted(candidates,key=lambda c:(c['source']=='clock_and_v1_identity',c['confidence']),reverse=True):
            if fresh:continue
            minimum=(self.marker_minimum if c['source']=='clock_and_v1_identity' else
                     .8 if c['source']=='own_hud' else self.threshold)
            if c['confidence']<minimum:continue
            if any(e['player_id']==c['player_id'] and e['card']==c['card'] and
                   (now-e['time']<900 or e['x'] is None or c['x'] is None or
                    math.hypot(e['x']-c['x'],e['y']-c['y'])<3) for e in self.recent):
                continue
            events.append(PublicPlayEvent(f'{frame_id}-v2-{len(events)}',c['player_id'],c['card'],
                                          c['confidence'],float(np.clip(c['x'],0,18)) if c['x'] is not None else None,
                                          float(np.clip(c['y'],0,32)) if c['y'] is not None else None))
            self.recent.append(dict(c,time=now))
        return events
