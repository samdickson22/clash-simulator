import sys,json,time
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[3];sys.path[:0]=[str(R/'src')]
from pixel_player import PixelSensor
from clasher.vision.l1 import public_pixels
import cv2
from dataclasses import asdict
s=PixelSensor();rows=[]
for name in ['preflight.png','terminal-preflight.png']:
 f,c=s.read(public_pixels(cv2.imread(str(H/name))),name,0,100)
 rows.append(dict(image=name,frame=asdict(f),cues=c))
(H/'pixel-diagnostics.json').write_text(json.dumps(rows,indent=2))
print(json.dumps(rows,indent=2))
