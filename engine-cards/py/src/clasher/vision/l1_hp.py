"""Associate public level markers and adjacent HP bars once per image."""
from dataclasses import replace
import json
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

from clasher.rl.tv_royale_public_state import _team_fill_mask
from clasher.vision.l1_perception import ACTION_NAMES


class MarkerHealthReader:
    def __init__(self, model, geometry):
        self.geometry = geometry
        model = Path(model)
        self.settings = json.loads((model/'hp.json').read_text())
        self.templates = [cv2.imread(str(model/f'hp-icon-{i}.png')) for i in (0,1)]
        if any(t is None for t in self.templates):
            raise ValueError('Missing training-only level marker templates')

    def markers(self, image, entities=None):
        found=[]
        regions=[]
        if entities is None:
            regions=[(owner,0,200,540,1000) for owner in (0,1)]
        else:
            for e in entities:
                if e.card in ('Tower','KingTower'):continue
                card=ACTION_NAMES.get(e.card,e.card);px,py=self.geometry.pixel(e.x_tiles,e.y_tiles)
                y=py-self.settings['offsets'].get(card,55)
                regions.append((e.player_id,max(0,round(px-50)),max(200,round(y-45)),
                                min(540,round(px+35)),min(1000,round(y+45))))
        for owner,x1,y1,x2,y2 in regions:
            template=self.templates[owner]
            if y2-y1<template.shape[0] or x2-x1<template.shape[1]:continue
            scores=cv2.matchTemplate(image[y1:y2,x1:x2],template,cv2.TM_CCOEFF_NORMED)
            while True:
                _,score,_,(x,y)=cv2.minMaxLoc(scores)
                if score<self.settings.get('marker_confidence',.68):break
                marker=(owner,x+x1+template.shape[1]/2,y+y1+template.shape[0]/2,score)
                if not any(m[0]==owner and abs(m[1]-marker[1])<10 and abs(m[2]-marker[2])<12 for m in found):
                    found.append(marker)
                scores[max(0,y-12):y+13,max(0,x-10):x+11]=-1
        return found

    def measure(self, image, marker, card, px):
        owner,x,y,confidence=marker
        width=49 if card in ('Cannon','Tesla') else 32
        start=round(x+7)
        patch=image[round(y)-2:round(y)+3,start:start+width]
        if patch.shape[:2]!=(5,width):return None,0.
        active=_team_fill_mask(patch,1 if owner==0 else 0).mean(axis=0)>=.4
        # A healthy unit has its level marker centered over its body and no
        # adjoining colored bar. This visual cue is checked, not assumed for
        # every missing bar. Retracted buildings have no certified cue.
        if np.count_nonzero(active[:12])<3:
            if (card not in ('Cannon','Tesla','DarkPrince')
                    and abs(x-px)<=self.settings.get('healthy_horizontal_tolerance',6)
                    and confidence>=self.settings.get('healthy_marker_confidence',.78)):
                return 1.,float(confidence*.85)
            return None,0.
        blue,green,red=np.moveaxis(patch.astype(np.int16),-1,0)
        background=((red>green*1.25)&(red>blue*1.05)) if owner==0 else ((blue>red*1.25)&(green>red*1.1))
        if np.mean(background.mean(axis=0)>=.4)<.65:return None,0.
        gaps=0;end=0
        for i,filled in enumerate(active):
            if filled:end=i+1;gaps=0
            else:gaps+=1
            if gaps>2:break
        return min(1.,end/width),float(confidence)

    def read(self,image,entities):
        markers=self.markers(image,entities)
        indices=[i for i,e in enumerate(entities) if e.card not in ('Tower','KingTower')]
        costs=np.full((len(indices),len(markers)),1e6)
        for k,i in enumerate(indices):
            e=entities[i];card=ACTION_NAMES.get(e.card,e.card)
            px,py=self.geometry.pixel(e.x_tiles,e.y_tiles)
            offset=self.settings['offsets'].get(card,55)
            for j,(owner,x,y,score) in enumerate(markers):
                if owner!=e.player_id:continue
                hp,hpc=self.measure(image,markers[j],card,px)
                expected_x=px if hp==1. and abs(x-px)<10 else px-(24 if card in ('Cannon','Tesla') else 14)
                cost=abs(x-expected_x)/12+abs(y-(py-offset))/20
                if cost<2.5:costs[k,j]=cost
        result=list(entities)
        for i in indices:result[i]=replace(result[i],hp_fraction=None,hp_confidence=0.)
        if costs.size:
            ii,jj=linear_sum_assignment(costs)
            for k,j in zip(ii,jj):
                if costs[k,j]>=2.5:continue
                alternatives=np.delete(costs[:,j],k)
                if alternatives.size and alternatives.min()-costs[k,j]<.25:continue
                i=indices[k];e=result[i];card=ACTION_NAMES.get(e.card,e.card)
                px,_=self.geometry.pixel(e.x_tiles,e.y_tiles)
                hp,confidence=self.measure(image,markers[j],card,px)
                result[i]=replace(e,hp_fraction=hp,hp_confidence=confidence)
        return tuple(result)
