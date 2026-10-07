"""Perception acts on detached public packets. No live engine is accepted here."""
import bootstrap
from bootstrap import HERE
import copy,json,math
from dataclasses import dataclass,replace
from collections import Counter
import numpy as np
from fair_player import Information
from derived_public_state import PublicEvent

MODEL=json.loads((HERE/'noise-model.json').read_text())
# Repair one source at a time against B, with the same noise streams.
from cells import CELLS
VARIANTS = {name: (set() if cell['arm']=='A' else {'board','hp','hud','events','latency'}) for name,cell in CELLS.items()}


@dataclass(frozen=True)
class SeenEvent:
    tick:int
    kind:str
    name:str
    amount:float=0.
    x:float|None=None
    y:float|None=None
    event_id:str=''

class Sensor:
    def __init__(self,variant,seed,builder):
        self.variant=variant;self.flags=VARIANTS[variant];self.builder=builder;self.cell=CELLS[variant]
        self.rng={s:np.random.default_rng(np.random.SeedSequence([seed,i])) for i,s in enumerate(('board','hp','hud','events'))}
        self.counts=Counter();self.pending=[];self.events=[];self.seen=0
        self.names=list(MODEL['false_positive_card_counts'])
        self.weights=np.array(list(MODEL['false_positive_card_counts'].values()),dtype=float);self.weights/=self.weights.sum()

    def ingest(self,events):
        """Only accepted public events, never private elixir or hand."""
        for index,event in enumerate(events[self.seen:],self.seen):
            if 'events' not in self.flags:
                self.pending.append(event);continue
            rng=self.rng['events'];self.counts['truth_events']+=event.kind=='card'
            if event.kind!='card':
                # No measured champion/Collector cue rate: same recall assumption.
                if rng.random()<self.cell['recall']:self.pending.append(event)
                continue
            recall=self.cell['recall']
            precision=self.cell['precision']
            confusion=MODEL['confusion_rate']*((1-recall)/(1-MODEL['recall']))
            u=rng.random();name=event.name;kind=None
            if u<recall:kind='matched_events'
            elif u<recall+confusion:
                choices=[p['predicted'] for p in MODEL['confusion_pairs'] if p['truth']==name]
                choices=choices or [p['predicted'] for p in MODEL['confusion_pairs'] if p['predicted']!=name]
                name=str(rng.choice(choices));kind='confused_events'
            else:self.counts['missed_events']+=1
            if kind:
                self.counts[kind]+=1
                delay=int(math.ceil(float(rng.choice(MODEL['event_delays_ms']))/50))
                # Delay includes inference as in L1 scorer; 10 FPS delivery quantizes below.
                residual=MODEL['event_xy_residuals'][int(rng.integers(len(MODEL['event_xy_residuals'])))];x=event.x;y=event.y
                if residual is None:x=y=None
                elif x is not None:
                    dx,dy=residual;x=float(np.clip(x+dx,0,18));y=float(np.clip(y+dy,0,32))
                if kind=='matched_events':self.counts['placement_hits']+=x is not None and math.hypot(x-event.x,y-event.y)<=1
                arrival=min(2*math.ceil((event.tick+delay)/2),2*math.floor((event.tick+10)/2))
                self.pending.append(SeenEvent(arrival,'card',name,x=x,y=y,event_id=f'{index}-det'))
            # Confusions already contribute false positives. Remaining FP counts
            # are event-proportional insertions, an explicit temporal assumption.
            extra=max(0.,recall*(1-precision)/precision-confusion)
            for k in range(int(rng.poisson(extra))):
                name=str(rng.choice(self.names,p=self.weights));delay=int(rng.integers(1,11))
                self.pending.append(SeenEvent(event.tick+delay,'card',name,x=float(rng.uniform(0,18)),y=float(rng.uniform(0,32)),event_id=f'{index}-fp{k}'))
                self.counts['spurious_events']+=1
        self.seen=len(events)

    def deliver(self,tick):
        ready=sorted((e for e in self.pending if e.tick<=tick),key=lambda e:e.tick)
        self.pending=[e for e in self.pending if e.tick>tick]
        # No timestamps from the underlying real deployment are exposed on noisy events.
        self.events.extend(ready)
        return tuple(self.events)

    def capture(self,info):
        packet=copy.deepcopy(info.packet);obs=packet.observation;own=copy.deepcopy(info.own)
        rng=self.rng['board'];hp_rng=self.rng['hp'];hud_rng=self.rng['hud']
        real=np.flatnonzero(obs.entity_mask).copy()
        for i in real:
            row=obs.entity_features[i];token=int(obs.entity_ids[i])
            name=self.builder.token_names[token];tower=name.split(':')[-1] in ('Tower','KingTower') or ('Tower'==name or 'KingTower'==name)
            # Template kind and fixed tower positions provide a public tower test.
            tower=tower or bool(row[5] and (abs(row[1]*32-6.5)<.1 or abs(row[1]*32-25.5)<.1 or abs(row[1]*32-3)<.1 or abs(row[1]*32-29)<.1) and ('Tower' in name))
            self.counts['entities']+=1
            if 'hp' in self.flags and not tower:self.counts['hp_trials']+=1
            if 'board' in self.flags:
                recall=1. if tower else .9411
                self.counts['non_tower_entities']+=not tower
                if rng.random()>recall:
                    obs.entity_mask[i]=False;obs.entity_ids[i]=0;row[:]=0
                    packet.entity_id_confidence[i]=0;packet.entity_feature_confidence[i,:]=0
                    if obs.entity_levels is not None:obs.entity_levels[i]=0;obs.entity_level_confidence[i]=0
                    self.counts['dropped_entities']+=1;continue
                dx,dy=rng.normal(0,.015 if tower else .11,2)
                if not tower and rng.random()>.9962:
                    angle=rng.uniform(0,2*np.pi);radius=rng.uniform(1.01,2.8);dx=radius*np.cos(angle);dy=radius*np.sin(angle)
                row[0]=np.clip(row[0]+dx/18,0,1);row[1]=np.clip(row[1]+dy/32,0,1)
                self.counts['position_hits']+=math.hypot(dx,dy)<=1
            if 'hp' in self.flags and not tower:
                if hp_rng.random()<MODEL['hp_coverage']/.9411:
                    # Laplace signed noise before clipping has MAE .0498.
                    old=float(row[9]);magnitude=min(float(hp_rng.exponential(MODEL['hp_mae'])),.49)
                    directions=[d for d in (-1,1) if .001<=old+d*magnitude<=1]
                    row[9]=np.clip(old+int(hp_rng.choice(directions or [1]))*magnitude,.001,1)
                    self.counts['hp_observed']+=1;self.counts['hp_abs_error']+=abs(float(row[9])-old)
                else:
                    row[9]=.5;packet.entity_feature_confidence[i,9]=1. # Point-estimate adapter required by existing script API
                    self.counts['hp_imputed']+=1
        if 'board' in self.flags:
            all_visible=[i for i in np.flatnonzero(obs.entity_mask) if obs.entity_features[i,4] or obs.entity_features[i,5]]
            visible=[i for i in all_visible if self.builder.token_names[int(obs.entity_ids[i])].split(':')[-1] not in ('Tower','KingTower')]
            # Precision calibrated on all detections; towers are never hallucinated.
            free=list(np.flatnonzero(~obs.entity_mask))
            for _ in range(min(len(free),int(rng.poisson(len(all_visible)*(1-.922)/.922)))):
                if not visible:break
                src=int(rng.choice(visible));i=free.pop();name=self.builder.token_names[int(obs.entity_ids[src])]
                if name.split(':')[-1] in ('Tower','KingTower'):continue
                obs.entity_ids[i]=obs.entity_ids[src];obs.entity_mask[i]=True;obs.entity_features[i]=obs.entity_features[src]
                obs.entity_features[i,0]=np.clip(obs.entity_features[i,0]+rng.normal(0,1.5)/18,0,1)
                obs.entity_features[i,1]=np.clip(obs.entity_features[i,1]+rng.normal(0,1.5)/32,0,1)
                packet.entity_id_confidence[i]=1.;packet.entity_feature_confidence[i]=packet.entity_feature_confidence[src]
                if obs.entity_levels is not None:obs.entity_levels[i]=obs.entity_levels[src];obs.entity_level_confidence[i]=obs.entity_level_confidence[src]
                self.counts['phantom_entities']+=1
        if 'hud' in self.flags:
            for slot in range(min(5,len(obs.hand_ids))):
                rate=MODEL['hand_correct'] if slot<4 else MODEL['next_correct']
                self.counts['hand_trials']+=slot<4
                if hud_rng.random()>rate and obs.hand_ids[slot]:
                    # Confuse with a different publicly known own-deck card.
                    pool=[n for n in own['hand']+own['cycle'] if n and self.builder.token_id(n)!=obs.hand_ids[slot]]
                    if pool:
                        name=str(hud_rng.choice(pool));obs.hand_ids[slot]=self.builder.token_id(name)
                        if slot<4:own['hand'][slot]=name;self.counts['hand_errors']+=1
                        elif own['cycle']:own['cycle'][0]=name
            self.counts['elixir_trials']+=1
            if hud_rng.random()>MODEL['elixir_correct']:
                # Conditional |error| mean 1.1986 matches 0.035/.0292 before bounds.
                magnitude=1+int(hud_rng.random()<MODEL['elixir_mae']/(1-MODEL['elixir_correct'])-1)
                own['elixir']=float(np.clip(own['elixir']+hud_rng.choice([-1,1])*magnitude,0,10));self.counts['elixir_errors']+=1
                obs.global_features[5]=own['elixir']/10
        if 'events' not in self.flags:
            return Information(info.tick,info.seat,packet,own,tuple(self.events))
        # Prevent clean event histories from bypassing the event corruption channel.
        obs.opponent_history_ids[:]=0;obs.opponent_history_ages[:]=0;obs.opponent_seen_card_ids[:]=0
        packet.opponent_history_confidence[:]=0;packet.opponent_seen_card_confidence[:]=0
        names=[]
        for e in self.events:
            if e.kind=='card':names.append(e.name)
        for i,name in enumerate(reversed(names[-len(obs.opponent_history_ids):])):
            if i>=len(obs.opponent_history_ids):break
            obs.opponent_history_ids[i]=self.builder.token_id(name);packet.opponent_history_confidence[i]=1
        for i,name in enumerate(dict.fromkeys(names)):
            if i>=len(obs.opponent_seen_card_ids):break
            obs.opponent_seen_card_ids[i]=self.builder.token_id(name);packet.opponent_seen_card_confidence[i]=1
        if self.cell['identity']:
            for i in np.flatnonzero(obs.entity_mask):
                row=obs.entity_features[i]
                kind=('Troop','Building','Projectile','AreaEffect','Entity')[int(np.argmax(row[4:9]))]
                name=self.builder.token_names[int(obs.entity_ids[i])]
                if 'Tower' in name or kind not in ('Troop','Building'):continue
                if self.rng['board'].random()<self.cell['identity']:
                    choices=sorted(token for token,k in self.identity_templates if k==kind and token!=int(obs.entity_ids[i]) and 'Tower' not in self.builder.token_names[token])
                    if choices:
                        obs.entity_ids[i]=int(self.rng['board'].choice(choices));self.counts['identity_confusions']+=1
        return Information(info.tick,info.seat,packet,own,tuple(self.events))
