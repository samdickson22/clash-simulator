from pathlib import Path
import numpy as np
from fair_player import Resources,observe
from differential import initial,Position
from c56_controller import CARDS
from qualify import write
r=Resources();rng=np.random.default_rng(880600);seen=set();checks=0;failures=[]
for name in CARDS:
    b=initial(seed=880601,cards=(name,'Knight','Archers','Fireball'))
    b.players[0].elixir=10;b.players[1].elixir=10
    b.deploy_card(0,name,Position(4.5,13.5));b.deploy_card(1,'Knight',Position(4.5,18.5));b.deploy_card(1,'Archers',Position(7.5,20.5))
    for tick in range(201):
        if tick%20==0:
            for seat in (0,1):
                info=observe(b,r.builder,seat,[])
                seen.update(r.builder.token_names[int(i)] for i in info.packet.observation.entity_ids[info.packet.observation.entity_mask])
                opp=dict(elixir=6.,hand=['Knight','Archers','Fireball',None],cycle=['Knight']*5,refill=500)
                try:
                    root=r.root(info,opp,rng);root.step(10)
                    checks+=1
                except BaseException as e:
                    failures.append(dict(card=name,tick=tick,seat=seat,error=str(e)))
        b.step()
write(Path(__file__).resolve().parent/'public-templates.json',dict(checks=checks,tokens=sorted(seen),failures=failures,complete=not failures))
print(checks,sorted(seen),failures)
assert not failures
