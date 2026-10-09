"""Private fit-only OCR/activation atlas, never committed as pixels."""
import json
from pathlib import Path
import sys
import cv2
import numpy as np
root=Path(sys.argv[1]); m=json.loads((root/'manifest.json').read_text());cards=[]; kings=[]
for ep in m['fit'][:24]:
    data=np.load(root/(ep+'.npz')); panels=data['panel'];sprites=data['sprite']; rows=json.loads((root/(ep+'.json')).read_text())['rows']
    for s in range(6):
        candidates=[i for i,r in enumerate(rows) if r['slot']==s and r['hp'] is not None and r['hp']>0]
        for i in candidates[::max(1,len(candidates)//2)][:2]:
            tile=np.zeros((110,110,3),np.uint8);tile[:80]=panels[i];cv2.putText(tile,f"{ep[-4:]} s{s} {rows[i]['hp']}",(0,100),0,.33,(255,255,255));cards.append(tile)
        if s%3==0:
            for active in (False,True):
                ids=[i for i,r in enumerate(rows) if r['slot']==s and r['active'] is active]
                if ids:
                    i=ids[len(ids)//2];tile=np.zeros((180,110,3),np.uint8);tile[:150,7:103]=sprites[i];cv2.putText(tile,f"{ep[-4:]} s{s} {active}",(0,168),0,.33,(255,255,255));kings.append(tile)
for name, tiles,h in [('panels',cards,110),('kings',kings,180)]:
    canvas=np.zeros((((len(tiles)+11)//12)*h,1320,3),np.uint8)
    for i,t in enumerate(tiles):canvas[(i//12)*h:(i//12+1)*h,(i%12)*110:(i%12+1)*110]=t
    cv2.imwrite(str(root/(name+'.jpg')),canvas)
