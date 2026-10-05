import sys
from pathlib import Path
import cloudpickle
import qualify
from clasher.rl.action_space import DiscreteTileActionSpace
real=qualify.check

def check(b,seat,builder,bots,scripts,cfg,index,search_cfg):
    if index<19:return dict(index=index,reproduction_skip=True)
    p=Path(__file__).resolve().parent/'failure19.pkl'
    p.write_bytes(cloudpickle.dumps((b,seat),protocol=5))
    return real(b,seat,builder,bots,scripts,cfg,index,search_cfg)

qualify.check=check
qualify.plannerspace=DiscreteTileActionSpace()
sys.argv=[__file__,'--roots','20','--output',str(Path(__file__).resolve().parent/'reproduce.json')]
qualify.main()
