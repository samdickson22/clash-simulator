"""Causal deployment cues from pixel detections and the player's HUD."""
from dataclasses import replace
import math

import numpy as np
from scipy.optimize import linear_sum_assignment

from clasher.rl.live_inference_contract import PublicPlayEvent
from clasher.vision.l1_perception import ACTION_NAMES


class DeploymentTracker:
    def __init__(self):
        self.episode = None

    def update(self, frame):
        if frame.episode_id != self.episode:
            self.episode = frame.episode_id
            self.tracks = {}
            self.sequence = 0
            self.previous = frame
            self.recent = []
            self.pending = []
            self.own_births = []
            first = True
        else:
            if frame.timestamp_ms <= self.previous.timestamp_ms:
                raise ValueError('Temporal inference requires strictly increasing media time')
            first = False
        now = frame.timestamp_ms
        self.tracks = {k:v for k,v in self.tracks.items() if now-v[1] <= 750}
        old = list(self.tracks.items())
        costs = np.full((len(frame.entities), len(old)), 1e6)
        for i,e in enumerate(frame.entities):
            for j,(_, (p,t)) in enumerate(old):
                if (e.card,e.player_id) == (p.card,p.player_id):
                    distance = math.hypot(e.x_tiles-p.x_tiles,e.y_tiles-p.y_tiles)
                    if distance <= .8 + 4*(now-t)/1000:
                        costs[i,j] = distance
        matches = {}
        if costs.size:
            ii,jj = linear_sum_assignment(costs)
            matches = {int(i):old[j][0] for i,j in zip(ii,jj) if costs[i,j]<1e6}
        entities, births = [], []
        for i,e in enumerate(frame.entities):
            track_id = matches.get(i)
            if track_id is None:
                self.sequence += 1
                track_id = f'v1-{self.sequence}'
                if not first and e.card not in ('Tower','KingTower'):
                    if (e.player_id==0 and e.y_tiles<=15.5) or (e.player_id==1 and e.y_tiles>=16.5):
                        births.append(e)
            e = replace(e,track_id=track_id)
            self.tracks[track_id] = (e,now)
            entities.append(e)
        # A disappearing card needs an elixir spend or a confident refill by
        # the previous next card. A submitted action is never an input.
        if not first:
            p = self.previous
            changed=[slot for slot,(before,after) in enumerate(zip(p.own_hand,frame.own_hand))
                     if p.own_hand_confidence[slot]>=.7 and (before!=after or frame.own_hand_confidence[slot]<.45)]
            spent=p.own_elixir is not None and frame.own_elixir is not None and p.own_elixir-frame.own_elixir>=1
            for slot,(before,after) in enumerate(zip(p.own_hand,frame.own_hand)):
                refill=(before != after and before is not None and after == p.own_next_card
                        and p.own_hand_confidence[slot]>=.7 and frame.own_hand_confidence[slot]>=.7
                        and p.own_next_card_confidence>=.7)
                immediate=spent and changed==[slot]
                if (before not in (None,'empty','unknown') and (refill or immediate)
                        and not any(q['card']==before for q in self.pending)):
                    self.pending.append(dict(card=before,time=now,source='hud',x=None,y=None,confidence=.85))
        clusters = []
        for e in births:
            card = ACTION_NAMES.get(e.card,e.card)
            group = next((g for g in clusters if g['card']==card and g['owner']==e.player_id
                          and math.hypot(g['x']-e.x_tiles,g['y']-e.y_tiles)<3),None)
            if group is None:
                clusters.append(dict(card=card,owner=e.player_id,x=e.x_tiles,y=e.y_tiles,n=1,confidence=e.confidence))
            else:
                n=group['n']; group['x']=(group['x']*n+e.x_tiles)/(n+1)
                group['y']=(group['y']*n+e.y_tiles)/(n+1);group['n']+=1
        events = []
        self.recent = [e for e in self.recent if now-e[0]<=1000]
        self.own_births=[g for g in self.own_births if now-g['time']<=500]
        self.own_births.extend(dict(g,time=now) for g in clusters if g['owner']==1)
        for p in self.pending:
            birth=next((g for g in self.own_births if g['card']==p['card'] and abs(g['time']-p['time'])<=500),None)
            if birth:p.update(x=birth['x'],y=birth['y'])
        for g in clusters:
            if any(card==g['card'] and owner==g['owner'] for _,card,owner in self.recent):
                continue
            if g['owner']==1:
                pending = next((p for p in self.pending if p['card']==g['card'] and now-p['time']<=500),None)
                if pending:
                    pending.update(x=g['x'],y=g['y'])
                else:
                    # Own body births need an independent HUD cue.
                    continue
            else:
                events.append(PublicPlayEvent(f'{frame.frame_id}-birth-{len(events)}',g['owner'],
                    g['card'],g['confidence'],g['x'],g['y']))
                self.recent.append((now,g['card'],g['owner']))
        waiting=[]
        for p in self.pending:
            if any(card==p['card'] and owner==1 for _,card,owner in self.recent):
                continue
            if p['x'] is not None or now-p['time']>=150:
                # Spells can be known from HUD while placement remains unknown.
                events.append(PublicPlayEvent(f'{frame.frame_id}-hud-{len(events)}',1,p['card'],
                                              p['confidence'],p['x'],p['y']))
                self.recent.append((now,p['card'],1))
            else:
                waiting.append(p)
        self.pending=waiting
        self.previous=frame
        return replace(frame,entities=tuple(entities),play_events=tuple(events))
