import json,random
from pathlib import Path
from c56_gate import PLAN,FOLDER,CARDS,battle,config,resources,schedule,recorded
from differential import snapshot
p=json.loads((FOLDER/'c56_games_r65.json').read_text());record=p['results']['0'];ep=json.loads(PLAN.read_text())['episodes'][0]
builder,_,_,_=resources();cfg=config(CARDS);b=battle(ep,builder.loader);rows=schedule(record)
times=set(random.Random(ep['seed'] ^ 610024).sample(range(90,record['ticks']),16))
print('root times',sorted(times),flush=True)
while not b.game_over:
 if b.tick in times:
  packed=json.loads(snapshot(b,cfg))
  areas=[(e['id'],e['class'],e['spell_name'],e['stats']['name']) for e in packed['entities'] if e['class']=='AreaEffect']
  print(b.tick,areas,flush=True)
 recorded(b,rows[b.tick]);b.step()
