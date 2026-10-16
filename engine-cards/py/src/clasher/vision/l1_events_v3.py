"""Causal stream event fusion with explicit secondary-spawn suppression."""
from collections import deque
from dataclasses import replace
import math

import cv2
import numpy as np
import torch
from torch import nn

from clasher.rl.live_inference_contract import PublicPlayEvent
from clasher.vision.l1_events_v2 import EventNet as V2Net, reduced, stack_pixels, clock_markers
from clasher.vision.l1_perception import ACTION_NAMES
from clasher.vision.l1_temporal import DeploymentTracker
from clasher.vision.l1_hud_v3 import visible_clock_phase


SPAWN_SOURCES={
    'Skeletons':frozenset({'Witch','Tombstone','SkeletonKing','Graveyard'}),
    'Goblins':frozenset({'GoblinHut','GoblinBarrel','GoblinGang'}),
    'SpearGoblins':frozenset({'GoblinHut','GoblinGang'}),
    'FireSpirits':frozenset({'FirespiritHut','Furnace'}),
    'Bats':frozenset({'NightWitch'}),
    'Golemite':frozenset({'Golem'}),
    'LavaPups':frozenset({'LavaHound'}),
    'Barbarians':frozenset({'BarbarianHut','BarbLog'}),
    'GoblinBrawler':frozenset({'GoblinCage'}),
    # The frozen P16 body model can confuse expanded-roster children with
    # these classes. Suppress only their weak birth boost, never visual events.
    'IceSpirit':frozenset({'FirespiritHut','Furnace'}),
    'IceGolem':frozenset({'Golem'}),
    'Knight':frozenset({'BarbLog','BarbarianHut'}),
}
STATIC_SOURCES=frozenset({'GoblinHut','FirespiritHut','Furnace','Tombstone','BarbarianHut','GoblinCage','Graveyard'})

GROUP_COUNTS={'SkeletonArmy':(8,30),'GoblinGang':(4,8),'MinionHorde':(4,8),
    'Barbarians':(4,6),'RoyalHogs':(3,5),'Skeletons':(2,4),'Goblins':(2,5),
    'Archers':(2,3),'Minions':(2,4),'Bats':(3,6),'AngryBarbarians':(2,3)}
GROUP_BODIES={'SkeletonArmy':frozenset({'Skeletons'}),
    'GoblinGang':frozenset({'Goblins','SpearGoblins'}),'MinionHorde':frozenset({'Minions'}),
    'RoyalHogs':frozenset({'RoyalHogs','RoyalHog'})}


def secondary_birth(card,side,x,y,sources,now):
    """Visible source or recent visible death near a child suppresses birth evidence.

    This only removes a weak body cue. Independent spell or temporal deployment
    evidence remains eligible, so a play beside a spawner is not blindly banned.
    """
    source_cards=SPAWN_SOURCES.get(card,frozenset())
    return any(s['card'] in source_cards and s['side']==side and now-s['time']<=1600
        and math.hypot(s['x']-x,s['y']-y)<=s.get('radius',4) for s in sources)


class StreamEventNet(V2Net):
    def __init__(self,cards):
        super().__init__()
        self.cards=tuple(cards)
        if len(set(self.cards))!=len(self.cards):raise ValueError('Duplicate cards')
        self.heatmap=nn.Conv2d(64,2*len(self.cards),1)
        nn.init.constant_(self.heatmap.bias,-4)
        layers=[]
        for dilation in (8,24,48):
            layers.extend((nn.Conv2d(64,64,3,padding=dilation,dilation=dilation),nn.GroupNorm(8,64),nn.SiLU()))
        self.context=nn.Sequential(*layers)
        self.context_scale=nn.Parameter(torch.zeros(()))

    def forward(self,x):
        features=self.body(x)
        # A projectile can be far from the deployment point it identifies.
        # The added receptive field spans the arena; zero initial gain retains
        # the P16 warm start while the new context branch learns stream cues.
        return self.heatmap(features+self.context_scale*self.context(features))


class StreamFusion:
    def __init__(self,thresholds):
        self.thresholds=dict(thresholds);self.recent=[]

    def update(self,frame_id,now,candidates):
        self.recent=[c for c in self.recent if now-c['time']<1800]
        result=[]
        for c in sorted(candidates,key=lambda c:c['confidence'],reverse=True):
            threshold=self.thresholds.get(c['card'],self.thresholds.get('default',.7))
            if c['confidence']<threshold:continue
            duplicate=any(p['card']==c['card'] and p['side']==c['side'] and
                (now-p['time']<700 or p['x'] is None or c['x'] is None or
                 math.hypot(p['x']-c['x'],p['y']-c['y'])<2) for p in self.recent)
            if duplicate:continue
            result.append(PublicPlayEvent(f'{frame_id}-v3-{len(result)}',c['side'],c['card'],
                float(c['confidence']),None if c['x'] is None else float(np.clip(c['x'],0,18)),
                None if c['y'] is None else float(np.clip(c['y'],0,32))))
            self.recent.append(dict(c,time=now))
        return result


class SpellCueBuffer:
    """Resolve visually identical spell effects using causal own-HUD evidence."""
    def __init__(self):
        self.pending=[];self.own=[]

    def update(self,now,candidates,own_cards,*,hud_reliable):
        self.own=[e for e in self.own if now-e[1]<=600]
        self.own.extend((card,now) for card in own_cards)
        for candidate in candidates:
            old=next((c for c in self.pending if c['card']==candidate['card'] and
                math.hypot(c['x']-candidate['x'],c['y']-candidate['y'])<2),None)
            if old is None:self.pending.append(dict(candidate,first=now))
            elif candidate['confidence']>old['confidence']:
                first=old['first'];old.update(candidate);old['first']=first
        result=[];waiting=[]
        for candidate in self.pending:
            own=any(card==candidate['card'] and abs(t-candidate['first'])<=600 for card,t in self.own)
            if not own and now-candidate['first']<150:
                waiting.append(candidate);continue
            c={k:v for k,v in candidate.items() if k!='first'}
            c['side']=1 if own else 0
            if not own and not hud_reliable:c['confidence']*=.7
            c['source']='spell_pixels + own_hud' if own else 'spell_pixels + no_own_play'
            result.append(c)
        self.pending=waiting
        return result


class StreamEventDetector:
    def __init__(self,weights,geometry,*,thresholds=None,device='mps'):
        payload=torch.load(weights,map_location='cpu',weights_only=True)
        self.cards=tuple(payload['cards']);self.spells=frozenset(payload['spells'])
        self.marker_offsets=payload.get('marker_offsets',{})
        self.net=StreamEventNet(self.cards).to(device)
        self.net.load_state_dict(payload['model']);self.net.eval()
        self.geo=geometry;self.device=device;self.thresholds=thresholds or {'default':.7}
        self.episode=None

    def step(self,image,frame):
        now=frame.timestamp_ms
        if frame.episode_id!=self.episode:
            self.episode=frame.episode_id;self.images=deque(maxlen=3)
            self.tracker=DeploymentTracker();self.known_tracks=set();self.sources=[]
            self.births=[];self.fusion=StreamFusion(self.thresholds);self.last=None;self.spell_buffer=SpellCueBuffer()
        if self.last is not None and now<=self.last:raise ValueError('Noncausal stream time')
        gap=self.last is None or now-self.last>300
        if gap:self.images.clear();self.births=[];self.spell_buffer=SpellCueBuffer()
        self.images.append(reduced(image))
        while len(self.images)<3:self.images.append(self.images[0])
        tracked=self.tracker.update(frame)
        self.sources=[s for s in self.sources if now<s.get('expires',s['time']+1600)]
        entities_by_track={e.track_id:e for e in tracked.entities}
        for s in self.sources:
            observed=entities_by_track.get(s.get('track_id'))
            if observed is not None:
                s.update(x=observed.x_tiles,y=observed.y_tiles,time=now,expires=now+1600)
            elif s['card'] in STATIC_SOURCES:
                # An inferred static source is uncertain. Retaining it only
                # suppresses a weak boost; temporal/HUD evidence can override.
                s['time']=now
            elif s.get('track_id') is None and now-s.get('first',now)<=1500:
                nearby=[e for e in tracked.entities if e.player_id==s['side'] and
                    e.card not in ('Tower','KingTower') and math.hypot(e.x_tiles-s['x'],e.y_tiles-s['y'])<2]
                if nearby:
                    closest=min(nearby,key=lambda e:math.hypot(e.x_tiles-s['x'],e.y_tiles-s['y']))
                    s.update(track_id=closest.track_id,x=closest.x_tiles,y=closest.y_tiles,time=now,expires=now+1600)
        visible_sources={s for values in SPAWN_SOURCES.values() for s in values}
        for e in tracked.entities:
            card=ACTION_NAMES.get(e.card,e.card)
            if card in visible_sources:
                self.sources.append(dict(card=card,side=e.player_id,x=e.x_tiles,y=e.y_tiles,time=now))
        self.births=[b for b in self.births if now-b['time']<=300]
        suppressed=0
        for e in tracked.entities:
            if e.track_id in self.known_tracks or gap:continue
            card=ACTION_NAMES.get(e.card,e.card)
            if card in ('Tower','KingTower'):continue
            if secondary_birth(card,e.player_id,e.x_tiles,e.y_tiles,self.sources,now):
                suppressed+=1;continue
            self.births.append(dict(card=card,side=e.player_id,x=e.x_tiles,y=e.y_tiles,time=now))
        self.known_tracks.update(e.track_id for e in tracked.entities)
        # Only tracker events with side=1 come from corroborated own HUD changes.
        hud=[e for e in tracked.play_events if e.player_id==1]
        with torch.inference_mode():
            scores=self.net(torch.from_numpy(stack_pixels(list(self.images))[None]).to(self.device)).sigmoid()[0].cpu().numpy()
        candidates=[];spell_candidates=[]
        markers=clock_markers(image)
        if not gap:
            for cls,values in enumerate(scores):
                side=cls//len(self.cards);card=self.cards[cls%len(self.cards)]
                if card in self.spells:
                    if side==1:continue
                    # Ownership can be invisible in the arena. Marginalize the
                    # two learned heads, then use the separately read own HUD.
                    values=np.minimum(.995,scores[cls]+scores[cls+len(self.cards)])
                peaks=(values==cv2.dilate(values,np.ones((5,5),np.uint8)))&(values>=.15)
                for gy,gx in zip(*np.where(peaks)):
                    x,y=self.geo.tile((gx+.5)*540/68,200+(gy+.5)*8)
                    if not (0<=x<=18 and 0<=y<=32):continue
                    confidence=float(values[gy,gx]);source='spell_pixels' if card in self.spells else 'temporal_pixels'
                    if card in self.spells:
                        spell_candidates.append(dict(card=card,side=0,x=x,y=y,confidence=confidence,source=source))
                        continue
                    births=[b for b in self.births if b['side']==side and b['card'] in GROUP_BODIES.get(card,{card})
                        and math.hypot(x-b['x'],y-b['y'])<=2]
                    minimum,maximum=GROUP_COUNTS.get(card,(1,1))
                    if minimum<=len(births)<=maximum:
                        confidence=min(.995,confidence+.15);source+=' + grouped_births'
                    if any(e.card==card and side==1 for e in hud):
                        confidence=min(.995,confidence+.15);source+=' + own_hud'
                    offset=self.marker_offsets.get(f'{side}:{card}')
                    if offset is not None and card not in self.spells and confidence>=.3:
                        positions=[self.geo.tile(m['px']+offset[0],m['py']+offset[1]) for m in markers if m['player_id']==side]
                        if positions:
                            mx,my=min(positions,key=lambda p:math.hypot(p[0]-x,p[1]-y))
                            if math.hypot(mx-x,my-y)<=1.5 and not secondary_birth(card,side,mx,my,self.sources,now):
                                x,y=mx,my;confidence=min(.995,confidence+.1);source+=' + deploy_clock'
                    candidates.append(dict(card=card,side=side,x=x,y=y,confidence=confidence,source=source))
            own_cards=[e.card for e in hud]+[p['card'] for p in self.tracker.pending]
            candidates.extend(self.spell_buffer.update(now,spell_candidates,own_cards,
                hud_reliable=min(frame.own_hand_confidence)>=.7))
            for e in hud:
                if e.card not in self.cards:continue
                same=[c for c in candidates if c['card']==e.card and c['side']==1 and c['confidence']>=.3]
                best=max(same,key=lambda c:c['confidence']) if same else None
                candidates.append(dict(card=e.card,side=1,x=best['x'] if best else e.x_tiles,
                    y=best['y'] if best else e.y_tiles,confidence=e.confidence,source='own_hud'))
        candidates=sorted(candidates,key=lambda c:c['confidence'],reverse=True)[:80]
        self.last=now
        events=self.fusion.update(frame.frame_id,now,candidates)
        for event in events:
            if event.card in visible_sources and event.x_tiles is not None:
                duration=12000 if event.card=='Graveyard' else 60000 if event.card in STATIC_SOURCES else 1600
                self.sources.append(dict(card=event.card,side=event.player_id,x=event.x_tiles,
                    y=event.y_tiles,time=now,first=now,expires=now+duration,
                    radius=7 if event.card=='BarbLog' else 4,track_id=None))
        return replace(tracked,play_events=tuple(events)),dict(candidates=candidates,
            suppressed_secondary_births=suppressed,clock_markers=markers,clock_phase=visible_clock_phase(image))
