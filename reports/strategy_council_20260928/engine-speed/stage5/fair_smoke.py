import json
from pathlib import Path
import time
import numpy as np
from fair_player import Resources,PublicPlanner,observe
from derived_public_state import PublicEvent
from stage2_matches import battle
from qualify import write

here=Path(__file__).resolve().parent
r=Resources()
prior=json.loads((here.parent.parent/'c56/engine/root-v3/human_deck_catalog.json').read_text())
chosen=sorted(prior['decks'],key=lambda d:-d['frequency'])
ep=dict(seed=880400,decks=[chosen[0]['cards'],chosen[1]['cards']])
b=battle(ep,r.builder.loader);p=PublicPlanner(r,prior,seed=880401);events=[];times=[];searches=0
for tick in range(800):
    if b.game_over:break
    if tick>=90 and tick%5==0:
        start=time.perf_counter();a,search=p.decide(observe(b,r.builder,0,events),(tick-90)//5);times.append(time.perf_counter()-start);searches+=search
        other=r.bots['pressure'].select_action(r.builder.build_public(b,1))
        p.core.space.apply_action(b,0,a)
        if other<2304:
            name=b.players[1].hand[other//576]
            if p.core.space.apply_action(b,1,other):events.append(PublicEvent(tick,'card',name))
    b.step()
write(here/'fair-smoke.json',dict(ticks=b.tick,searches=searches,timing=times,max=max(times),templates=r.template_count))
print(b.tick,searches,max(times))
