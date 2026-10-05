"""Public clock reading on both regulation and red overtime backgrounds."""
import cv2
import numpy as np

from clasher.vision.l1 import CLOCK,crop
from clasher.vision.l1_perception import HudReader,clock_digits


def visible_clock_phase(image):
    patch=crop(image,CLOCK).astype(np.int16)
    border=np.concatenate((patch[:,:4].reshape(-1,3),patch[:,-4:].reshape(-1,3)))
    b,g,r=border.T
    red=(r>120)&(r>g*1.45)&(r>b*1.3)
    return 'overtime' if float(red.mean())>=.5 else 'regulation'


def clock_digits_v3(image):
    patch=crop(image,CLOCK)
    # The old red-text mask also selected the solid overtime background.
    # White glyphs isolate cleanly there; red regulation glyphs use the old path.
    mask=(np.min(patch,axis=2)>175).astype(np.uint8)*255
    _,_,stats,_=cv2.connectedComponentsWithStats(mask)
    boxes=sorted((int(x),int(y),int(w),int(h)) for x,y,w,h,area in stats[1:]
        if h>=13 and w>=4 and area>=22)
    if len(boxes)!=3:return clock_digits(image)
    result=[]
    for x,y,w,h in boxes:
        v=cv2.resize(mask[y:y+h,x:x+w],(20,28)).astype(np.float32).ravel()/255
        v-=v.mean();result.append(v/max(float(np.linalg.norm(v)),1e-6))
    return result


class StreamHudReader(HudReader):
    def read(self,image):
        result=super().read(image)
        parts=clock_digits_v3(image)
        if parts:
            scores=np.stack(parts)@self.digits.T;indices=scores.argmax(axis=1)
            digits=self.digit_names[indices]
            if digits[0]<=5 and digits[1]<=5:
                result['clock']=float(digits[0]*60+digits[1]*10+digits[2])
                result['clock_confidence']=float(np.clip(scores[np.arange(3),indices].min(),.001,1))
        result['clock_phase']=visible_clock_phase(image)
        return result
