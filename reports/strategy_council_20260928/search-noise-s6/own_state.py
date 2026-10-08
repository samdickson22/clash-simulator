"""Optimistic own command state; reconciliation accepts only public own HUD cues."""
import copy
from dataclasses import replace

class OwnState:
    def __init__(self):
        self.pending=None
        self.verified=None

    def submit(self,info,action,costs,builder=None):
        if self.pending is not None:raise ValueError('one command may be outstanding')
        own=copy.deepcopy(info.own)
        if action<2304:
            slot=action//576;name=own['hand'][slot]
            if name is None:raise ValueError('empty submitted slot')
            own['elixir']=max(0.,own['elixir']-costs[name]);own['hand'][slot]=None;own['cycle'].append(name)
        elif action==2305:
            if builder is None:raise ValueError('ability submission requires public token costs')
            obs=info.packet.observation
            visible=[builder.ability_cost_for_token(int(obs.entity_ids[i])) for i in range(len(obs.entity_ids))
                     if obs.entity_mask[i] and obs.entity_features[i,2]>.5 and obs.entity_features[i,4]>.5
                     and info.packet.entity_id_confidence[i]>0]
            visible=[cost for cost in visible if cost is not None]
            if not visible:raise ValueError('no publicly identified own ability')
            own['elixir']=max(0.,own['elixir']-max(visible))
        self.pending=(info.tick,own)

    def reconcile(self,info):
        # Acknowledgment is an own-HUD observation. It never carries opponent state.
        self.pending=None
        self.verified=(info.tick,copy.deepcopy(info.own))

    def packet(self,info,builder):
        anchor=self.pending or self.verified
        if anchor is None or (self.pending is None and anchor[0]<info.tick-16):return info
        tick,own=anchor;own=copy.deepcopy(own)
        while tick<info.tick:
            tick+=1;rate=.93 if tick>4800 else 1.4 if tick>2400 else 2.8
            own['elixir']=min(10.,(round(own['elixir']*10000)+int(500/rate))/10000)
            own['refill']=max(0,own['refill']-50)
            if not own['refill'] and None in own['hand'] and own['cycle']:
                own['hand'][own['hand'].index(None)]=own['cycle'].pop(0)
                own['refill']=1000 if tick<2400 else 500 if tick<4800 else 350
        packet=copy.deepcopy(info.packet);obs=packet.observation
        for i,name in enumerate(own['hand']):obs.hand_ids[i]=builder.token_id(name) if name else 0
        if len(obs.hand_ids)>4:obs.hand_ids[4]=builder.token_id(own['cycle'][0]) if own['cycle'] else 0
        present=obs.hand_ids!=0
        packet.hand_id_confidence[:]=present.astype('float32')
        if obs.hand_levels is not None:
            obs.hand_levels[:]=present.astype('int64')*11
            obs.hand_level_confidence[:]=present.astype('float32')
        obs.global_features[5]=own['elixir']/10
        return replace(info,own=own,packet=packet)
