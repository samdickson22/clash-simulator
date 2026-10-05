import json,sys,time
from pathlib import Path
from bootstrap import setup,HERE
r,_=setup('c56')
from pixel_player import PixelSensor,PixelPlayer
from clasher.vision.l1 import public_pixels
import cv2
sensor=PixelSensor();player=PixelPlayer(r,'c56',690131)
pixels=public_pixels(cv2.imread(str(HERE/'preflight.png')))
frame,cues=sensor.read(pixels,'smoke',0,100)
tick=player.ingest(frame,cues)
action,diag=player.decide(frame,tick)
(HERE/'player-smoke.json').write_text(json.dumps(dict(action=action,diag=diag,frame=__import__('dataclasses').asdict(frame)),indent=2))
print(action,diag,flush=True)
