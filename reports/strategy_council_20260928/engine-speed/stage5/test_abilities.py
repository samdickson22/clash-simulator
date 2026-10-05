import copy
import json
from pathlib import Path
import random
import numpy as np
from fair_player import Resources,observe
from differential import initial,Position
from clasher.rl.c56_rollout_planner import C56RolloutPlanner
from clasher.rl.public_action_mask import PublicActionMaskInput
from qualify import write

r=Resources();rows=[]
for name in ('ArcherQueen','MightyMiner','Goblinstein'):
    for seat in (0,1):
        b=initial(seed=880700,cards=(name,'Knight','Archers','Fireball'))
        b.players[seat].elixir=10
        b.deploy_card(seat,name,Position(4.5,13.5 if seat==0 else 18.5))
        b.deploy_card(1-seat,'Knight',Position(4.5,18.5 if seat==0 else 13.5))
        for _ in range(30):b.step()
        assert b.can_activate_champion_ability(seat),(name,seat)
        p=C56RolloutPlanner(r.builder,r.bots)
        n=C56RolloutPlanner(r.builder,r.bots,backend='native',native=r.native,native_config=r.config)
        pa=p.score_candidates(b,seat,[2304,2305],trace=True)
        na=n.score_candidates(n.import_root(b),seat,[2304,2305],trace=True)
        assert (pa,p.last)==(na,n.last),(name,seat)
        info=observe(b,r.builder,seat,[])
        other=dict(elixir=6.,hand=['Knight','Archers','Fireball',None],cycle=[name]*5,refill=500)
        model=r.root(info,other,np.random.default_rng(880701))
        assert model.can_activate_champion_ability(seat),(name,seat,'public model ability')
        assert r.native.apply_discrete(model,seat,2305)
        for _ in range(100):model.step()
        # Poison only forbidden hidden values. The public sensor and model output
        # must stay identical for the same public input and planner RNG.
        changed=b.clone();enemy=changed.players[1-seat]
        enemy.elixir=.123;enemy.hand=['Fireball','Archers','Knight',name];enemy.cycle_queue.clear();enemy.cycle_queue.extend([name,'Knight','Fireball','Archers'])
        changed.rng=random.Random(991230)
        after=observe(changed,r.builder,seat,[])
        for field in vars(info.packet.observation):
            x=getattr(info.packet.observation,field);y=getattr(after.packet.observation,field)
            assert np.array_equal(x,y),('hidden sensor leak',field)
        m1=r.root(info,other,np.random.default_rng(991231));m2=r.root(after,other,np.random.default_rng(991231))
        assert m1.snapshot()==m2.snapshot(),'hidden model leak'
        rows.append(dict(champion=name,seat=seat,action=pa,candidate_scores=p.last['scores'],rollouts=len(p.last['traces']),hidden_poison_equal=True))
write(Path(__file__).resolve().parent/'abilities.json',dict(complete=True,results=rows))
print(rows)
