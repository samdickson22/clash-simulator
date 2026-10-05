import bootstrap
from bootstrap import HERE,RUNTIME
import json,sys
from evaluate import Resources,game,write
r=Resources();prior=json.loads((HERE/'runtime/support/human_deck_catalog.json').read_text())
schedule=json.loads((HERE/'schedule.json').read_text())['pairs'];seen=set();out=[]
for ep in schedule:
    if ep['family'] in seen:continue
    seen.add(ep['family']);ep=ep.copy();ep['seed']=3926720001+1009*len(seen);ep['noise_seed']=3926740001+1009*len(seen);ep['mode']='scripts'
    row=game(r,prior,ep,0,'B',max_tick=1000);out.append(row);print(ep['family'],row['ticks'],round(row['elapsed'],2),flush=True)
for name,module in list(sys.modules.items()):
    path=getattr(module,'__file__',None)
    if path and (name=='clasher' or name.startswith('clasher.') or name=='clasher_core'):
        assert str(RUNTIME) in path,(name,path)
write(HERE/'preflight.json',dict(complete=True,rows=out,private_imports=True))
