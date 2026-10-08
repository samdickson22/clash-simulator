"""Real pixel-runtime regression for validation-selectable body confidence."""
import json
import math
import numpy as np
import torch
from clasher.vision.l1_v4 import PerceptionV4,PixelPerception


def main():
    torch.set_num_threads(1);torch.manual_seed(6115)
    model=PerceptionV4(2,1)
    with torch.no_grad():
        model.body.heatmap.weight.zero_();model.body.heatmap.bias.fill_(math.log(.6/.4))
    args=(model,['Knight','Zap'],['Knight'],['Zap'],{'default':1.},{})
    image=np.zeros((1140,540,3),np.uint8);checks=0
    for threshold,expected in ((.5,True),(.7,False)):
        runtime=PixelPerception(*args,body_threshold=threshold)
        first=runtime.step(image,'synthetic-validation',0)
        second=runtime.step(image,'synthetic-validation',50)
        assert not first['tracks'];checks+=1
        assert bool(second['tracks'])==expected;checks+=1
        # Episode reset must preserve the configured threshold and clear tracks.
        third=runtime.step(image,'synthetic-validation-next',100)
        assert not third['tracks'] and runtime.tracker.high==threshold;checks+=1
    default=PixelPerception(*args)
    default.step(image,'synthetic-default',0)
    assert default.body_threshold==.5 and default.tracker.high==.5;checks+=1
    for value in (True,None,float('nan'),float('inf'),0,1,.55,'0.5'):
        try:PixelPerception(*args,body_threshold=value)
        except ValueError:checks+=1
        else:raise AssertionError('Invalid body grid value accepted')
    print(json.dumps(dict(checks=checks,passed=True,synthetic_only=True,heldout_payloads_opened=False)),flush=True)


if __name__=='__main__':main()
