from stage2 import focused_case
from differential import CARDS,config
cfg=config((*CARDS,'Valkyrie'))
for tick in (1220,1221,1222,1223,1224,1225):
 p=focused_case('Valkyrie',0,cfg,trace_tick=tick)
 for phase in ('before','combat'):
  a=next((e for e in p[phase]['python']['entities'] if e['id']==173),None)
  b=next((e for e in p[phase]['rust']['entities'] if e['id']==173),None)
  if a and b:print(tick,phase,'p',a['cooldown'],a['target'],'r',b['cooldown'],b['target'], 'deploy',a['deploy'],b['deploy'],flush=True)
