"""Native/S6 parity and all-pending execution; exploration-only smoke."""
import copy,json,sys
from pathlib import Path
import numpy as np
from clasher.analysis.loss_review import delay_simulate as harness
from clasher.analysis.loss_review.delay_fixes import CommandQueue,planner_class,hypothetical_packet,imitation_candidates
from clasher.rl.c56_rollout_planner import C56SearchConfig
harness.OPTIONS=dict(checkpoint=sys.argv[2]);harness.initialize()
sys.path.insert(0,str(harness.COUNCIL/'search-noise-s6'))
from delay import DelayAwarePlanner
from fair_player import observe,PublicPlanner
from stage2_matches import battle
from imitation.evaluation.d1 import D1Tracker
r=harness.RES;deck=['HogRider','Knight','Archers','Fireball','Log','Cannon','Skeletons','IceSpirit']
checks=[]
for seat in (0,1):
 b=battle(dict(seed=2**48+59000,decks=[deck,deck]),r.builder.loader)
 for player in b.players:player.elixir=10
 info=observe(b,r.builder,seat,[])
 p=PublicPlanner(r,harness.PRIOR,2**48+59001);p.belief.update(info.tick,())
 root=r.root(info,p.belief.sample(p.rng),p.rng);digest=root.digest()
 config=C56SearchConfig(samples=2,horizon=60,threads=1)
 base=DelayAwarePlanner(r.builder,r.bots,backend='native',native=r.native,native_config=r.config,config=config,seed=7,command_delay=27,delay_aware=True)
 core=planner_class(DelayAwarePlanner)(r.builder,r.bots,backend='native',native=r.native,native_config=r.config,config=config,seed=7,command_delay=27,delay_aware=True)
 for c in (base,core):c.info=info;c.costs=r.costs
 a,mask=base.candidates(info.packet);a=[v for v in a if v!=2305]
 aa,mm=core.candidates(info.packet);aa=[v for v in aa if v!=2305]
 assert a==aa and np.array_equal(mask,mm)
 assert base.score_candidates(root,seat,a)==core.score_candidates(root,seat,aa)
 assert base.last==core.last
 core.forward_prior=True
 assert base.score_candidates(root,seat,a)==core.score_candidates(root,seat,a)
 assert np.allclose(base.last['scores'],core.last['scores'],rtol=0,atol=1e-12),(base.last,core.last)
 projected=hypothetical_packet(r,root,info)
 assert np.array_equal(projected.observation.hand_ids,info.packet.observation.hand_ids)
 assert np.array_equal(projected.observation.entity_ids,info.packet.observation.entity_ids)
 assert np.allclose(projected.observation.global_features,info.packet.observation.global_features,atol=1e-7)
 assert np.allclose(projected.observation.entity_features,info.packet.observation.entity_features,atol=1e-7)
 core.max_outstanding=2;core.symmetric_opponent=True
 q=CommandQueue(27,2);first=next(v for v in a if v<2304 and v//576==0)
 q.submit(info,int(first),r.costs);core.pending=tuple(q.pending)
 reserved=q.own_packet(info,r.builder)
 second=next(v for v in core.candidates(reserved.packet)[0] if v<2304 and v//576!=first//576)
 _,events,sim=core.simulate_commands(root,seat,int(second),'balanced',28,trace=True)
 own=[e for e in events if e[0]=='execute' and e[2]==seat]
 assert len(own)==2 and all(e[1]==27 and e[4] for e in own),own
 expected=10-r.costs[deck[first//576]]-r.costs[deck[second//576]]
 own_state=json.loads(sim.snapshot())['players'][seat]
 assert abs(own_state['elixir']-(expected+.0178))<1e-6,own_state
 assert root.digest()==digest
 submissions={(e[2],e[3],e[1]+22) for e in events if e[0]=='submit' and e[2]!=seat}
 enemy_executions=[e for e in events if e[0]=='execute' and e[2]!=seat]
 assert enemy_executions and all((e[2],e[3],e[1]) in submissions for e in enemy_executions)
 # Distinct execution ticks: all four reservations reach the engine once.
 cheap=['Skeletons','IceSpirit','Log','Cannon','HogRider','Knight','Archers','Fireball']
 cb=battle(dict(seed=2**48+59002,decks=[cheap,cheap]),r.builder.loader)
 for player in cb.players:player.elixir=10
 ci=observe(cb,r.builder,seat,[])
 cr=r.root(ci,p.belief.sample(p.rng),p.rng);cdigest=cr.digest()
 due=[10,20,27,35]
 pending=[(due[j],j*576+first%576,cheap[j],r.costs[cheap[j]]) for j in range(4)]
 _,cev,cs=r.native.rollout_commands(cr,seat,2304,pending,'balanced',27,22,4,4,36,10,10,0.25,False,False,True)
 executed=[e for e in cev if e[0]=='execute' and e[2]==seat]
 assert [e[1] for e in executed]==due and all(e[4] for e in executed),executed
 assert len({e[3] for e in executed})==4 and cr.digest()==cdigest
 cown=json.loads(cs.snapshot())['players'][seat]
 assert sorted([card for card in cown['hand'] if card]+cown['cycle'])==sorted(cheap)
 assert abs(cown['elixir']-(10-sum(r.costs[c] for c in cheap[:4])+26*.0178))<1e-6,cown
 # Exact endpoint and hypothetical/public adapter validity.
 forward,ev=core.forward_state(root,seat)
 assert json.loads(forward.snapshot())['tick']==27
 assert any(e[0]=='execute' and e[2]==seat and e[1]==27 for e in ev)
 packet=hypothetical_packet(r,forward,info)
 assert packet.observation.hand_ids[first//576]==0
 # Prior proposals are legal now, matched count, and CPU fp32 read-only.
 core.pending=();core.max_outstanding=1
 d1=D1Tracker(r.builder,r.costs,seat,deck);d1.update(0,[]);d1._exploration_events=[]
 for future in (False,True):
  candidates,audit=imitation_candidates(core,r,root,info,d1,harness.POLICY,forward=future)
  assert len(candidates)==audit['baseline_candidates']
  assert all(mask[a] for a in candidates)
 assert d1.last_tick==0 and root.digest()==digest
 checks.append(dict(seat=seat,legacy_parity=True,native_single_channel_score_parity=True,two_pending_exact_tick=True,four_pending_distinct_ticks=True,forward_endpoint=True,prior_matched_legal=True))
Path(sys.argv[1]).parent.mkdir(parents=True,exist_ok=True)
Path(sys.argv[1]).write_text(json.dumps(dict(passed=True,checks=checks),indent=2)+'\n')
print(json.dumps(dict(passed=True,checks=checks)))
