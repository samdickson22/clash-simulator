"""Build private visual audit sheets from the already admitted study crops."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np

p = argparse.ArgumentParser()
p.add_argument('root', type=Path)
p.add_argument('--part', choices=['fit','dev'], default='fit')
p.add_argument('--ordinal', choices=['last','first'], default='last')
a = p.parse_args()
manifest = json.loads((a.root/'manifest.json').read_text())
cards = []
for ep in manifest[a.part]:
    if not (a.root/(ep+'.json')).exists():
        continue
    data = np.load(a.root/(ep+'.npz'))
    sprites = data['sprite']
    meta = json.loads((a.root/(ep+'.json')).read_text())['rows']
    ordinal = meta[-1]['ordinal'] if a.ordinal == 'last' else meta[0]['ordinal']
    for i, r in enumerate(meta):
        if r['ordinal'] != ordinal:
            continue
        tile = np.zeros((186,110,3), np.uint8)
        tile[:150,7:103] = sprites[i]
        cv2.putText(tile, f"{ep[-4:]} s{r['slot']} f{ordinal}", (0,162), cv2.FONT_HERSHEY_SIMPLEX,.30,(255,255,255),1)
        cv2.putText(tile, str(r['hp']), (0,177), cv2.FONT_HERSHEY_SIMPLEX,.35,(255,255,255),1)
        cards.append(tile)
canvas = np.zeros((((len(cards)+11)//12)*186, 12*110,3), np.uint8)
for i,t in enumerate(cards):
    canvas[(i//12)*186:(i//12+1)*186,(i%12)*110:(i%12+1)*110] = t
cv2.imwrite(str(a.root/(a.part+'-'+a.ordinal+'-atlas.jpg')), canvas)
