"""L1 YOLO/HUD pixel inference. This module cannot load native observations."""
from __future__ import annotations

from dataclasses import asdict
from types import MappingProxyType, SimpleNamespace

import cv2
import numpy as np

from clasher.rl.live_inference_contract import (
    PublicPlayEvent, PublicVisionFrame, VisionEntity, validate_public_vision_frame,
)
from clasher.rl.tv_royale_public_state import measure_health_bar, _team_fill_mask
from clasher.rl.tv_royale_ui import _prep
from clasher.vision.l1 import ARENA, CLOCK, ELIXIR, ELIXIR_DIGIT, HAND, NEXT, Geometry, crop

BODY_NAMES=MappingProxyType({'Archers':'Archer','IceGolem':'IceGolemite','IceSpirit':'IceSpirits'})
ACTION_NAMES=MappingProxyType({body:action for action,body in BODY_NAMES.items()})


def art_vector(patch):
    # Reuse the existing extractor's smoothing, with a common hand/next scale.
    patch = _prep(cv2.resize(patch, (36, 48)))
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY).astype(np.float32).reshape(-1)
    gray -= gray.mean()
    return gray / max(float(np.linalg.norm(gray)), 1e-6)


def clock_digits(image):
    patch = crop(image, CLOCK)
    b,g,r=np.moveaxis(patch.astype(np.int16),-1,0)
    mask = ((np.min(patch, axis=2)>175) | ((r>175)&(r-g>90)&(r-b>90))).astype(np.uint8)*255
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    boxes = sorted((int(x),int(y),int(w),int(h)) for x,y,w,h,a in stats[1:]
                   if h >= 13 and w >= 4 and a >= 22)
    if len(boxes) != 3:
        return []
    result = []
    for x,y,w,h in boxes:
        v = cv2.resize(mask[y:y+h,x:x+w], (20,28)).astype(np.float32).reshape(-1)/255
        v -= v.mean()
        result.append(v/max(float(np.linalg.norm(v)),1e-6))
    return result


def elixir_feature(image):
    patch = crop(image, ELIXIR).astype(np.int16)
    b,g,r = np.moveaxis(patch,-1,0)
    active = (b > 110) & (r > 125) & (r-g > 55) & (b-g > 35)
    return float(active.mean())


def train_hud(rows, dataset, output, *, max_per_value=None):
    vectors, names, digits, digit_names, elixirs, features, elixir_art = [], [], [], [], [], [], []
    counts = {}
    digit_counts, elixir_counts = {}, {}
    for row in rows:
        if row['split'] != 'train':
            continue
        image = cv2.imread(str(dataset/row['image']))
        t = row['targets']
        for name, box in zip([*t['own_hand'], t['own_next_card']], [*HAND, NEXT]):
            if counts.get(name,0) >= 100:
                continue
            counts[name] = counts.get(name,0)+1
            names.append(name)
            vectors.append(art_vector(crop(image,box)))
        parts = clock_digits(image)
        sec = int(t['visible_clock_seconds'])
        if len(parts)==3:
            for part,name in zip(parts,[sec//60, (sec%60)//10, sec%10]):
                if max_per_value is None or digit_counts.get(name,0)<max_per_value:
                    digits.append(part);digit_names.append(name)
                    digit_counts[name]=digit_counts.get(name,0)+1
        name=t['own_elixir']
        if max_per_value is None or elixir_counts.get(name,0)<max_per_value:
            elixirs.append(name)
            features.append([elixir_feature(image),1.0])
            elixir_art.append(art_vector(crop(image,ELIXIR_DIGIT)))
            elixir_counts[name]=elixir_counts.get(name,0)+1
    if not vectors or not digits:
        raise ValueError('No usable training HUD samples')
    coefficient = np.linalg.lstsq(np.array(features),np.array(elixirs),rcond=None)[0]
    np.savez_compressed(output, art=np.stack(vectors), names=np.array(names),
                        digits=np.stack(digits), digit_names=np.array(digit_names),
                        elixir_coefficients=coefficient, elixir_art=np.stack(elixir_art),
                        elixir_names=np.array(elixirs))
    return dict(cards=counts, digit_samples=len(digits),
                digit_coverage=sorted(set(digit_names)), elixir_coefficients=coefficient.tolist())


class HudReader:
    def __init__(self, weights):
        with np.load(weights, allow_pickle=False) as a:
            self.art = a['art']
            self.names = a['names']
            self.digits = a['digits']
            self.digit_names = a['digit_names']
            self.elixir_coefficients = a['elixir_coefficients']
            self.elixir_art = a['elixir_art']
            self.elixir_names = a['elixir_names']

    def read(self, image):
        vectors = np.stack([art_vector(crop(image,b)) for b in [*HAND,NEXT]])
        scores = vectors @ self.art.T
        indices = scores.argmax(axis=1)
        values = self.names[indices].tolist()
        confidence = np.clip(scores[np.arange(5),indices],0,1).tolist()
        parts = clock_digits(image)
        clock, cc = None, 0.0
        if parts:
            ds = np.stack(parts) @ self.digits.T
            ix = ds.argmax(axis=1)
            d = self.digit_names[ix]
            if d[0] <= 5 and d[1] <= 5:
                clock = float(d[0]*60+d[1]*10+d[2])
                cc = float(np.clip(ds[np.arange(3),ix].min(),.001,1))
        elixir = float(np.clip(np.dot([elixir_feature(image),1],self.elixir_coefficients),0,10))
        es = self.elixir_art @ art_vector(crop(image,ELIXIR_DIGIT))
        if float(es.max()) >= .75:
            elixir=float(self.elixir_names[int(es.argmax())])
        return dict(hand=values[:4], hand_confidence=confidence[:4],
                    next_card=values[4], next_confidence=confidence[4],
                    clock=clock, clock_confidence=cc, elixir=elixir)


def read_hp(image, card, owner, px, py):
    """Locate colored bar fill and reuse the existing bar measurement code.

    Missing bars remain unknown. We never fill them from class maximum HP.
    """
    belonging = 1 if owner==0 else 0
    if card=='KingTower':
        return None,0.0
    if card=='Tower':
        y = py - (73 if owner==0 else 5)
        box = (round(px-22),round(y-2),round(px+45),round(y+4))
    else:
        x1,x2 = max(0,round(px-38)),min(540,round(px+38))
        y1,y2 = max(200,round(py-90)),min(1000,round(py-12))
        patch = image[y1:y2,x1:x2]
        if patch.size==0:
            return None,0.0
        mask = _team_fill_mask(patch,belonging).astype(np.uint8)
        _,_,stats,_ = cv2.connectedComponentsWithStats(mask)
        candidates = [(x,y,w,h) for x,y,w,h,a in stats[1:] if w>=8 and 2<=h<=8 and w>h*2]
        if not candidates:
            return None,0.0
        x,y,w,h = min(candidates,key=lambda b: abs(x1+b[0]+24-px)+abs(y1+b[1]-(py-45)))
        if abs(x1+x+24-px)>20:
            return None,0.0
        box=(x1+x-1,y1+y-1,x1+x+49,y1+y+h+1)
    result=measure_health_bar(image,SimpleNamespace(class_name='bar',belonging=belonging,
                              confidence=.8,x1=box[0],y1=box[1],x2=box[2],y2=box[3]))
    return (None,0.0) if result is None else (result.fill_fraction,result.confidence)


class Perception:
    def __init__(self, model_path, hud_path, calibration, *, device='mps', confidence=.2, imgsz=416):
        from ultralytics import YOLO
        self.model = YOLO(str(model_path))
        self.hud = HudReader(hud_path)
        self.geo = Geometry(calibration)
        self.device, self.confidence = device,confidence
        self.imgsz = imgsz
        self.episode = None
        self.tracks = []
        self.sequence = 0

    def step(self, image, episode_id, frame_id, timestamp_ms):
        if image.shape != (1140,540,3):
            raise ValueError('Perception requires calibrated public JPEG pixels')
        if episode_id != self.episode:
            self.episode, self.tracks, self.sequence = episode_id, [], 0
        hud = self.hud.read(image)
        result = self.model.predict(crop(image,ARENA),device=self.device,imgsz=self.imgsz,
                                    conf=self.confidence,verbose=False)[0]
        entities, events, used = [], [], set()
        for b in result.boxes:
            name = self.model.names[int(b.cls.item())]
            owner_s,card = name.split(':',1)
            owner = int(owner_s)
            body_card=BODY_NAMES.get(card,card)
            box = b.xyxy[0].detach().cpu().numpy().tolist()
            box[1]+=ARENA[1]; box[3]+=ARENA[1]
            x,y = self.geo.anchor(card,box)
            x,y = float(np.clip(x,0,18)),float(np.clip(y,0,32))
            candidates = [(np.hypot(t.x_tiles-x,t.y_tiles-y),i,t) for i,t in enumerate(self.tracks)
                          if i not in used and t.card==body_card and t.player_id==owner]
            nearest = min(candidates,key=lambda v:v[0]) if candidates else None
            is_new = nearest is None or nearest[0]>4
            if is_new:
                self.sequence+=1
                track_id=f'visual-{self.sequence}'
            else:
                used.add(nearest[1]); track_id=nearest[2].track_id
            score=float(b.conf.item())
            px,py=self.geo.pixel(x,y)
            hp,hpc=read_hp(image,card,owner,px,py)
            kind='building' if card in ('Tower','KingTower','Tesla','Cannon') else 'troop'
            entity=VisionEntity(track_id,body_card,kind,owner,x,y,score,hp,hpc)
            entities.append(entity)
            # v0 deployment evidence is a newly seen body on its own half.
            # Swarm bodies are grouped; spell-only plays remain unobserved.
            if self.tracks and is_new and card not in ('Tower','KingTower') and ((owner==0 and y<15) or (owner==1 and y>17)):
                if not any(e.card==card and e.player_id==owner for e in events):
                    events.append(PublicPlayEvent(f'{frame_id}-{track_id}',owner,card,score,x,y))
        frame=PublicVisionFrame(episode_id,str(frame_id),timestamp_ms,hud['clock'],hud['clock_confidence'],
                                hud['elixir'],.8,tuple(hud['hand']),tuple(hud['hand_confidence']),
                                hud['next_card'],hud['next_confidence'],tuple(entities),tuple(events))
        validate_public_vision_frame(frame)
        self.tracks=entities
        return frame


def serialize_frame(frame):
    public=asdict(frame)
    identity={k:public.pop(k) for k in ('episode_id','frame_id','timestamp_ms')}
    return dict(schema_version=1,**identity,public=public)
