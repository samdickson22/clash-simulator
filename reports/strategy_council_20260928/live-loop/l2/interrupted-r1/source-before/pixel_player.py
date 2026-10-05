"""Pixel-only state, uncertain public reconstruction, and bounded fair search.

No probe, native-observation, match configuration, or evaluation truth imports.
"""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import json,time
import numpy as np
import torch
from clasher.rl.live_inference_contract import validate_public_vision_frame
from clasher.rl.structured_obs import ActorObservation
from clasher.rl.public_observation import ConfidenceAwareActorObservation
from clasher.rl.public_action_mask import PublicActionMaskInput
from clasher.vision.l1_derived_v3 import OpponentPosterior,StreamPublicClock
from clasher.vision.l1_hud_v3 import StreamHudReader
from clasher.vision.l1_perception import Perception
from clasher.vision.l1_events_v3 import StreamEventDetector

HERE=Path(__file__).resolve().parent
L1=HERE.parent/'l1'

class PixelSensor:
    def __init__(self):
        selection=json.loads((L1/'v3/evaluation-validation/selection.json').read_text())
        self.body=Perception(L1/'v1/model/detector/weights/best.pt',L1/'v3/model/hud.npz',L1/'calibration.json',imgsz=640)
        self.body.hud=StreamHudReader(L1/'v3/model/hud.npz')
        self.events=StreamEventDetector(L1/'v3/model/last.pt',self.body.geo,thresholds=selection['thresholds'])
    def read(self,pixels,episode,index,timestamp_ms):
        public=self.body.step(pixels,episode,str(index),timestamp_ms)
        frame,cues=self.events.step(pixels,public)
        torch.mps.synchronize()
        return frame,cues

class PacketBuilder:
    """Current pixels and explicit priors; estimates retain low confidence."""
    def __init__(self,builder):
        self.b=builder;self.hp={};self.positions={};self.last_time=None
    def build(self,frame,tick,seat=1,terminal=False):
        validate_public_vision_frame(frame)
        b=self.b;n=b.spec.max_entities
        ids=np.zeros(n,np.int64);features=np.zeros((n,32),np.float32);mask=np.zeros(n,bool)
        confidence=np.zeros_like(features);idc=np.zeros(n,np.float32)
        globals_=np.zeros(18,np.float32);gc=np.zeros(18,np.float32)
        # The calibrated clock identifies a running match. No probe lifecycle enters here.
        globals_[:6]=[min(tick/6000,1),max(0,1-tick/6000),tick>=2400,tick>=4800,tick>=3600,(frame.own_elixir or 0)/10]
        gc[:5]=frame.clock_confidence;gc[5]=frame.own_elixir_confidence
        missing_hp=unknown=0
        rows=[]
        for e in frame.entities:
            ns='tower' if e.card in ('Tower','KingTower') else {'troop':'troop_body','building':'building_body','projectile':'projectile','area_effect':'area_effect'}[e.kind]
            token=b.token_id(e.card,namespace=ns)
            if token<=1:unknown+=1;continue
            kind='building' if ns=='tower' else e.kind
            x,y=(18-e.x_tiles,32-e.y_tiles) if seat else (e.x_tiles,e.y_tiles)
            own=e.player_id==seat;row=np.zeros(32,np.float32);cc=np.zeros(32,np.float32)
            row[:4]=[x/18,y/32,own,not own];row[{'troop':4,'building':5,'projectile':6,'area_effect':7}[kind]]=1;cc[:9]=e.confidence
            key=(e.player_id,e.card,round(e.x_tiles/4),round(e.y_tiles/4)) if ns=='tower' else e.track_id
            if e.hp_fraction is not None:
                self.hp[key]=e.hp_fraction;row[9]=e.hp_fraction;cc[9]=e.hp_confidence
            else:
                # Explicit model prior, not a recovered HP measurement.
                row[9]=self.hp.get(key,1.);cc[9]=.01;missing_hp+=1
            static=b.card_stat_features[token]
            for out,source in [(24,7),(25,8),(26,12),(30,6)]:row[out]=static[source];cc[out]=e.confidence
            if e.track_id in self.positions and self.last_time is not None and frame.timestamp_ms>self.last_time:
                old=self.positions[e.track_id];dx,dy=x-old[0],y-old[1];norm=max(1,np.hypot(dx,dy));row[27:29]=[dx/norm,dy/norm];cc[27:29]=e.confidence
            self.positions[e.track_id]=(x,y)
            if ns=='tower':
                gi=(8 if own else 11)+(2 if e.card=='KingTower' else 0 if x<9 else 1)
                globals_[gi]=row[9];gc[gi]=cc[9]
                if not own and e.card=='KingTower':globals_[17]=1;gc[17]=e.confidence
            rows.append((token,row,cc,e.confidence))
        for i,(token,row,cc,c) in enumerate(rows[:n]):ids[i]=token;features[i]=row;confidence[i]=cc;idc[i]=c;mask[i]=True
        hand=np.array([b.token_id(c,namespace='card_action') if c else 0 for c in (*frame.own_hand,frame.own_next_card)],np.int64)
        hc=np.array([*frame.own_hand_confidence,frame.own_next_card_confidence],np.float32)
        hand[hand<=1]=0;hc[hand==0]=0
        obs=ActorObservation(ids,features,mask,hand,globals_,np.zeros(b.spec.public_history_slots,np.int64),np.zeros(b.spec.public_history_slots,np.float32),np.zeros(b.spec.public_seen_card_slots,np.int64),terminal=terminal,board_rotated=bool(seat))
        # Level 11 is the declared offline match rule, not a hidden measurement.
        obs=replace(obs,entity_levels=np.where(mask,11,0).astype(np.int64),entity_level_confidence=mask.astype(np.float32),hand_levels=np.where(hand>1,11,0).astype(np.int64),hand_level_confidence=(hand>1).astype(np.float32))
        p=ConfidenceAwareActorObservation(obs,idc,confidence,hc,gc,np.zeros(b.spec.public_history_slots,np.float32),np.zeros(b.spec.public_seen_card_slots,np.float32))
        self.last_time=frame.timestamp_ms
        return p,dict(missing_hp=missing_hp,unknown_entities=unknown,visible_entities=len(frame.entities),modeled_entities=len(rows))

def model_hypothesis(packet):
    """Conditional point model for search, separate from measured confidence.

    The original frame/packet is never modified. Missing HP uses PacketBuilder's
    declared prior. This copy describes the resulting hypothetical board, not
    sensor certainty. It must never be logged as a perception prediction.
    """
    o=packet.observation
    features=packet.entity_feature_confidence.copy()
    features[o.entity_mask,:]=1.
    globals_=packet.global_feature_confidence.copy()
    globals_[:14]=1.;globals_[17]=1.
    return replace(packet,entity_id_confidence=o.entity_mask.astype(np.float32),
        entity_feature_confidence=features,hand_id_confidence=(o.hand_ids>1).astype(np.float32),
        global_feature_confidence=globals_)

class PixelPlayer:
    def __init__(self,resources,mode,seed,*,p16_planner=None):
        self.resources=resources;self.mode=mode;self.rng=np.random.default_rng(seed);self.clock=StreamPublicClock()
        self.builder=resources.builder if mode=='c56' else resources.loaded.builder
        self.packets=PacketBuilder(self.builder);self.own_seen=[]
        select=json.loads((L1/'v3/evaluation-validation/selection.json').read_text())
        self.posterior=OpponentPosterior(resources.costs,particles=1024,missed_plays_per_second=select['missed_rate'],seed=seed,
            calibration_residuals=select.get('calibration_residuals'))
        self.prob=select['event_probabilities'];self.started=False;self.decision=0;self.p16=p16_planner
        if mode=='c56':
            from clasher.rl.c56_rollout_planner import C56RolloutPlanner,C56SearchConfig
            self.core=C56RolloutPlanner(resources.builder,resources.bots,backend='native',native=resources.native,native_config=resources.config,
                config=C56SearchConfig(deadline_seconds=.2,threads=2),seed=seed)
    def ingest(self,frame,cues):
        tick=self.clock.update(frame.visible_clock_seconds,frame.timestamp_ms,cues['clock_phase'])
        if not self.started:self.posterior.start_at(tick);self.started=True
        events=[replace(e,confidence=self.prob.get(e.card,.5)) for e in frame.play_events]
        self.posterior.observe(max(tick,self.posterior.tick),events)
        for c in (*frame.own_hand,frame.own_next_card):
            if c in self.resources.costs and c not in self.own_seen:self.own_seen.append(c)
        return tick
    def own_model(self,frame):
        hand=[c if c in self.resources.costs else None for c in frame.own_hand]
        nxt=frame.own_next_card if frame.own_next_card in self.resources.costs else None
        remaining=[c for c in self.own_seen if c not in hand and c!=nxt]
        unknown=[c for c in self.resources.costs if c not in hand and c!=nxt and c not in remaining]
        self.rng.shuffle(unknown)
        cycle=([nxt] if nxt else [])+remaining+unknown
        return dict(elixir=frame.own_elixir or 0.,hand=hand,cycle=cycle[:4],refill=0)
    def decide(self,frame,tick):
        start=time.perf_counter();deadline=start+.2
        packet,diag=self.packets.build(frame,tick)
        diag['search_input']='conditional point-model; original confidence retained in frame'
        packet=model_hypothesis(packet)
        info=SimpleNamespace(tick=tick,seat=1,packet=packet,own=self.own_model(frame))
        if self.mode=='c56':
            candidates,mask=self.core.candidates(packet)
            if len(candidates)==1:return 2304,diag
            if time.perf_counter()>=deadline:action=candidates[0]
            else:
                root=self.resources.root(info,self.posterior.sample(self.rng),self.rng)
                action=self.core.score_candidates(root,1,candidates,deadline=deadline)
            diag['deadline']=self.core.deadline_stats
        else:
            p=self.p16;r=self.resources
            mask=r.mask_builder.build(PublicActionMaskInput.from_confidence_observation(packet))
            top=p.policy_top(info,mask)
            ranked=r.bot._ranked_actions(packet,all_plays=True);script=int(r.bot.decide(packet).action_id)
            candidates=list(dict.fromkeys(a for a in [script,2304]+[int(x.action_id) for x in ranked[:4]]+top if mask[a]))
            action=candidates[0];best=-float('inf');complete=0
            root,_=r.root(info,self.posterior.sample(self.rng),self.rng)
            for a in candidates:
                score=0.;finished=True
                for style in ('balanced','pressure','defense'):
                    if time.perf_counter()>=deadline:finished=False;break
                    other=r.native.select_action(root,0,style)
                    score+=r.native.rollout(root,1,a,other,'balanced',style,160,10,1.)[0]/3
                if not finished:break
                complete+=1
                if score>best+1e-9:best=score;action=a
            p.previous=action;diag['deadline']=dict(completed=complete,total=len(candidates),truncated=complete<len(candidates),fallback=complete==0)
        diag.update(search_ms=(time.perf_counter()-start)*1000,opponent=self.posterior.distribution(),own_cycle_estimated=True)
        return int(action),diag
