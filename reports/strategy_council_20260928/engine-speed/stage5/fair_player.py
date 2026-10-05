"""Public v5 C56 search. The player receives no live battle or hidden snapshot.

Combat phases absent from v5 use deterministic template defaults. Only unknown
opponent cards/order and the simulation RNG are sampled. This is a model of the
public board, not a claim to reconstruct hidden combat clocks or targets.
"""
from __future__ import annotations
import copy
from dataclasses import dataclass
import json
import random
from types import SimpleNamespace
import numpy as np
import clasher_core
from c56_controller import CARDS, resources
from differential import config, initial, entity, Position
from clasher.rl.c56_rollout_planner import C56RolloutPlanner, C56SearchConfig
from clasher.rl.contract_v5 import CHAMPION_COOLDOWN_GLOBAL, CHAMPION_DURATION_GLOBAL
from derived_public_state import DerivedPublicState


@dataclass(frozen=True)
class Information:
    tick: int
    seat: int
    packet: object
    own: dict
    events: tuple


def observe(battle,builder,seat,events):
    """Trusted sensor: own HUD, public board and accepted public event stream."""
    own=battle.players[seat]
    return Information(battle.tick,seat,builder.build_public(battle,seat),
        dict(elixir=own.elixir,hand=list(own.hand),cycle=list(own.cycle_queue),refill=own.next_card_refill_cooldown_ms),tuple(events))


class Resources:
    def __init__(self):
        self.builder,self.meta,self.native,self.bots=resources()
        self.config=config(CARDS)
        self.costs={n:c['cost'] for n,c in self.config['cards'].items()}
        self.templates={}
        namespaces={'Troop':'troop_body','Building':'building_body','Projectile':'projectile','RollingProjectile':'projectile','AreaEffect':'area_effect'}
        def register(template,name):
            kind=template['class'];public_kind=('Troop','Building','Projectile','AreaEffect','Entity')[template['entity_kind']];ns=namespaces.get(public_kind,'area_effect')
            statname=template['stats']['name']
            metadata=self.meta['bodies'].get(statname)
            token=metadata['token'] if metadata and kind in ('Troop','Building') else 0
            if not token:
                stats=self.builder.loader.get_card(name) if name else None
                sensor=SimpleNamespace(card_stats=stats,spell_name=template.get('spell_name',name))
                token=self.builder._runtime_entity_token_id(sensor,ns)
            if token>1:
                self.templates.setdefault((token,public_kind),template)
            for alias in (statname,name,template.get('spell_name','')):
                token=self.builder.token_id(alias,namespace=ns)
                if token>1:self.templates.setdefault((token,public_kind),template)
        def walk(value,name=''):
            if isinstance(value,dict):
                if 'class' in value and 'stats' in value:
                    register(value,name)
                else:
                    for key,item in value.items():walk(item,key if key not in ('units','spawns') else name)
            elif isinstance(value,list):
                for item in value:walk(item,name)
        for name,card in self.config['cards'].items():walk(card,name)
        for key,value in self.config.items():
            if key!='cards':walk(value)
        if 'IceGolemite' in self.config['death_areas']:
            token=self.builder.token_id('FreezeIceGolemite',namespace='area_effect')
            self.templates[(token,'AreaEffect')]=self.config['death_areas']['IceGolemite']
        tower_stats={}
        for e in initial().entities.values():
            template=entity(e);register(template,template['stats']['name']);tower_stats[template['stats']['name']]=e.card_stats
        body_templates={t['stats']['name']:t for t in self.templates.values() if t['class'] in ('Troop','Building')}
        for stats in [*self.bots['balanced'].bodies.values(),*tower_stats.values()]:
            shotdata=getattr(stats,'projectile_data',None) or {}
            source=body_templates.get(stats.name)
            if source is None:continue
            shot=copy.deepcopy(source)
            shot.update(hp=1.,king=False,shield=0.,spell_name='',champion=None,production=None,scope=None,**{'class':'Projectile'})
            shot['stats'].update(max_hp=1.,speed=int(shotdata.get('speed',source['stats']['projectile_speed'])),range=0.,radius=0.,ordinary=False,spawner=None)
            token=self.builder.token_id(shotdata.get('name',stats.name),namespace='projectile')
            if token>1:self.templates.setdefault((token,'Projectile'),shot)
            for alias in (stats.name,):
                token=self.builder.token_id(alias,namespace='projectile')
                if token>1:self.templates.setdefault((token,'Projectile'),shot)
        # Fill non-card carriers from isolated, fixed-seed public demonstrations.
        # This runs once at startup, without access to any real game. It captures
        # static carrier metadata for chains, timed payloads and child rays.
        for name in CARDS:
            demo=initial(seed=880601,cards=(name,'Knight','Archers','Fireball'))
            demo.players[0].elixir=demo.players[1].elixir=10.
            demo.deploy_card(0,name,Position(4.5,13.5))
            demo.deploy_card(1,'Knight',Position(4.5,18.5))
            demo.deploy_card(1,'Archers',Position(7.5,20.5))
            for tick in range(201):
                if tick%10==0:
                    for body in demo.entities.values():
                        token,row=self.builder._entity_row(body,0)
                        kind=('Troop','Building','Projectile','AreaEffect','Entity')[int(np.argmax(row[4:9]))]
                        if (token,kind) not in self.templates:
                            self.templates[(token,kind)]=entity(body)
                if tick==60 and demo.can_activate_champion_ability(0):
                    demo.activate_champion_ability(0)
                demo.step()
        # Prior-only setup and first native use belong to pregame warmup.
        self.template_count=len(self.templates)

    def root(self,info,opponent,rng):
        obs=info.packet.observation
        entities=[]
        for token,row in zip(obs.entity_ids[obs.entity_mask],obs.entity_features[obs.entity_mask]):
            kind=('Troop','Building','Projectile','AreaEffect','Entity')[int(np.argmax(row[4:9]))]
            key=(int(token),kind)
            if key not in self.templates:
                raise ValueError(f'no C56 public model template: {self.builder.token_names[int(token)]}/{kind}')
            e=copy.deepcopy(self.templates[key])
            x,y=float(row[0])*18,float(row[1])*32
            fx,fy=float(row[27]),float(row[28])
            if info.seat==1:x,y,fx,fy=18-x,32-y,-fx,-fy
            owner=info.seat if row[2] else 1-info.seat
            e.update(id=len(entities)+1,owner=owner,x=x,y=y,hp=float(row[9])*e['stats']['max_hp'],
                alive=True,target=None,deploy=0.,stagger=0.,facing=[round(fx*1000),round(fy*1000)],
                age=1000,birth=info.tick-1,lane=1 if x<9 else 2,clock=dict(interval=max(1,e['stats']['interval']),
                    load=e['stats']['load'],timeline=0,remaining=0,finish=0),cooldown=0.)
            # No hidden shield, hit-clock, deployment or route value is read.
            if row[9]<1:e['shield']=0.
            if e['king']:
                base=8 if owner==info.seat else 11
                e['active']=bool(row[9]<1 or obs.global_features[base]==0 or obs.global_features[base+1]==0)
            else:e['active']=True
            if e['class']=='Projectile':
                distance=max(1.,e['stats'].get('projectile_range',0),e['stats']['range'])
                e.update(aim=[x+fx*distance,y+fy*distance],shot_target=None)
            c=e.get('champion')
            if c and owner==info.seat:
                a=c['ability'];now=info.tick*50
                remaining=round(float(obs.global_features[CHAMPION_DURATION_GLOBAL])*a['duration'])
                cooldown=round(float(obs.global_features[CHAMPION_COOLDOWN_GLOBAL])*a['cooldown'])
                if remaining>0:
                    a.update(active=True,start=now-a['duration']+remaining,last_use=now-a['duration']+remaining)
                elif cooldown>0:
                    a.update(active=False,start=now-a['duration']-a['cooldown']+cooldown,last_use=now-a['duration']-a['cooldown']+cooldown)
            entities.append(e)
        for e in entities:
            c=e.get('champion')
            if c and c['effect']['kind']=='Goblin':
                monsters=[m for m in entities if m['owner']==e['owner'] and m['stats']['name']=='Goblinstein']
                m=min(monsters,key=lambda m:(m['x']-e['x'])**2+(m['y']-e['y'])**2,default=None)
                c['effect'].update(monster=m['id'] if m else None,anchor=[m['x'],m['y']] if m else [e['x'],e['y']])
        players=[None,None];players[info.seat]=info.own;players[1-info.seat]=opponent
        state=random.Random(int(rng.integers(2**63))).getstate()[1]
        payload=json.dumps(dict(tick=info.tick,next_id=len(entities)+1,players=players,entities=entities,
            pending_casts=[],sudden_death=bool(obs.global_features[4]),rng=dict(state=state[:-1],index=state[-1]),
            game_over=False,winner=None,config=self.config))
        return clasher_core.BattleState(payload)


class PublicPlanner:
    def __init__(self,resources,prior,seed):
        self.resources=resources
        self.belief=DerivedPublicState(prior,resources.costs)
        self.core=C56RolloutPlanner(resources.builder,resources.bots,backend='native',seed=seed,
            native=resources.native,native_config=resources.config)
        self.rng=np.random.default_rng(seed+1)
        self.last=None

    def decide(self,info,decision):
        self.belief.update(info.tick,info.events)
        candidates,mask=self.core.candidates(info.packet)
        if decision%2 or len(candidates)==1:
            return 2304,False
        opponent=self.belief.sample(self.rng)
        root=self.resources.root(info,opponent,self.rng)
        action=self.core.score_candidates(root,info.seat,candidates)
        self.last=self.core.last
        return action,True
