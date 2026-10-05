"""Import frozen experiment players without changing their source trees."""
from pathlib import Path
import os,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];COUNCIL=ROOT/'reports/strategy_council_20260928';ES=COUNCIL/'engine-speed'
def setup(mode):
    paths=([ES/'stage5b-r3/native',ES/'stage5b-r3',ES/'stage5',HERE/'runtime/helpers'] if mode=='c56' else [COUNCIL/'search-tuning/native',COUNCIL/'search-tuning',HERE/'runtime/helpers'])
    sys.path[:0]=list(map(str,[*paths,HERE/'runtime/src',ROOT/'scripts']))
    os.environ['CLASHER_ROOT']=str(ROOT)
    import torch
    torch.set_num_threads(1)
    if mode=='c56':
        from fair_player import Resources
        return Resources(),None
    from support import Context
    from public_planner import Resources
    return Resources(Context()),None
