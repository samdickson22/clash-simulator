"""Mac-only timing pilot. No strength endpoint is computed or emitted."""
import bootstrap
from bootstrap import HERE
import json,random,time,copy
from collections import deque
from dataclasses import replace
import numpy as np
from fair_player import Resources,observe
from derived_public_state import DerivedPublicState,PublicEvent
from clasher.battle import BattleState
from clasher.player import PlayerState
from clasher.rl.c56_rollout_planner import C56RolloutPlanner,C56SearchConfig
r=Resources()
prior=json.loads((HERE/'runtime/support/human_deck_catalog.json').read_text())
deck=['HogRider','Musketeer','IceGolem','IceSpirit','Skeletons','Cannon','Fireball','Log']
b=BattleState(players=[PlayerState(i,deck=deck[:],hand=deck[:4],cycle_queue=deque(deck[4:])) for i in (0,1)],rng=random.Random(7610700001),card_loader=r.builder.loader)
p=C56RolloutPlanner(r.builder,r.bots,backend='native',seed=7610700002,native=r.native,native_config=r.config,config=C56SearchConfig(threads=1))
measure=[];rng=np.random.default_rng(7610700003)
for tick in range(1201):
    if tick>=90 and tick%30==0:
        info=observe(b,r.builder,0,())
        # Public development root: fixed known test deck with fresh synthetic completion.
        sample=dict(elixir=5.,hand=deck[:4],cycle=deck[4:],refill=0)
        root=r.root(info,sample,rng);candidates,_=p.candidates(info.packet)
        if len(candidates)>1:
            p.score_candidates(root,0,candidates,deadline=time.perf_counter()+.2)
            measure.append(dict(tick=tick,candidates=len(candidates),completed=p.deadline_stats['completed'],styles=3))
        for seat in (0,1):
            a=int(r.bots['balanced'].select_action(r.builder.build_public(b,seat)));p.space.apply_action(b,seat,a)
    b.step()
    if b.game_over:break
counts=[x['completed']*3 for x in measure]
assert counts
out=dict(candidate_style_rollouts=max(15,int(np.median(counts))),samples=measure,pilot_seeds=[7610700001,7610700002,7610700003],native_threads=1,seconds=.2)
(HERE/'budget.json').write_text(json.dumps(out,indent=2)+'\n');print({k:v for k,v in out.items() if k!='samples'})
