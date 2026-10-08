"""TorchScript export on fleet; CoreML is a separate Mac qualification step."""
import argparse
import json
from pathlib import Path
import torch
from torch import nn
from clasher.vision.l1_v4 import PerceptionV4

FRAME_KEYS=('features','body_heatmap','body_box','body_hp','body_hp_visible','hud_cards','elixir_digit','elixir_fraction','clock_seconds','phase')
EVENT_KEYS=('event_heatmap','event_age_ms','event_sigma_ms','cast_origin')

class FrameExport(nn.Module):
    def __init__(self, model):super().__init__();self.model=model
    def forward(self, arena, hud):
        out=self.model.encode(arena,hud);return tuple(out[k] for k in FRAME_KEYS)

class EventExport(nn.Module):
    def __init__(self, head):super().__init__();self.head=head
    def forward(self, cache, ages_ms, valid, births):
        out=self.head(cache,ages_ms,valid,births);return tuple(out[k] for k in EVENT_KEYS)


def main():
    p=argparse.ArgumentParser();p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);torch.set_num_threads(1)
    state=torch.load(a.checkpoint,map_location='cpu',weights_only=True)
    model=PerceptionV4(len(state['cards']),len(state['bodies'])).eval();model.load_state_dict(state['model'])
    frame=FrameExport(model).eval();event=EventExport(model.temporal).eval()
    inputs=(torch.rand(1,3,832,448),torch.rand(1,3,64,448))
    args=(torch.rand(1,16,64,52,28),torch.arange(15,-1,-1)[None]*50.,torch.ones(1,16,dtype=torch.bool),torch.zeros(1,2,64,36))
    traces=[]
    with torch.inference_mode():
        for name,wrapper,example in [('frame',frame,inputs),('event',event,args)]:
            traced=torch.jit.trace(wrapper,example,strict=True);traced.save(str(a.output/f'{name}.pt'))
            loaded=torch.jit.load(str(a.output/f'{name}.pt'));err=0.
            for variant in range(3):
                test=tuple(x.clone() for x in example)
                if name=='event':
                    if variant==1:test[2][:,:8]=False;test[1][:,:8]=9000
                    if variant==2:test[1][:,:8]+=1200
                else:test=(test[0]*(.5+variant*.25),test[1]*(.5+variant*.25))
                for eager,script in zip(wrapper(*test),loaded(*test)):
                    torch.testing.assert_close(eager,script,atol=1e-4,rtol=1e-4)
                    err=max(err,float((eager-script).abs().max()))
            traces.append(dict(stage=name,max_abs_error=err,variants=3,bytes=(a.output/f'{name}.pt').stat().st_size))
    (a.output/'parity.json').write_text(json.dumps(dict(passed=True,traces=traces,parameters=model.parameter_counts(),
        frame_outputs=FRAME_KEYS,event_outputs=EVENT_KEYS,mac_run=False,coreml_converted=False),indent=2)+'\n')

if __name__=='__main__':main()
