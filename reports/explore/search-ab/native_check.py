"""Small public/native d27 parity checks; no registrations or result sets."""
import copy,json,sys,time
from pathlib import Path
import numpy as np
from clasher.analysis.loss_review import simulate as harness
from clasher.analysis.loss_review.search_ab import planner_class
harness.initialize()
sys.path.insert(0,str(harness.COUNCIL/'search-noise-s6'))
from delay import DelayAwarePlanner
from fair_player import PublicPlanner,observe
from stage2_matches import battle
from clasher.rl.c56_rollout_planner import C56SearchConfig
r=harness.RES;deck=['Cannon','Fireball','HogRider','IceGolem','IceSpirit','Log','Musketeer','Skeletons']
b=battle(dict(seed=2**48+90000,decks=[deck,deck]),r.builder.loader)
for player in b.players:player.elixir=10
p=PublicPlanner(r,harness.PRIOR,2**48+90001)
info=observe(b,r.builder,0,[]);p.belief.update(info.tick,info.events)
root=r.root(info,p.belief.sample(p.rng),p.rng)
base=DelayAwarePlanner(r.builder,r.bots,backend='native',seed=2**48+90002,native=r.native,native_config=r.config,config=C56SearchConfig(samples=4,horizon=60,threads=1),command_delay=27,delay_aware=True)
changed=planner_class(DelayAwarePlanner)(r.builder,r.bots,backend='native',seed=2**48+90002,native=r.native,native_config=r.config,config=base.config,command_delay=27,delay_aware=True,catalog=harness.CAT)
for core in (base,changed):core.info=info;core.costs=r.costs
bc,bm=base.candidates(info.packet);cc,cm=changed.candidates(info.packet)
assert bc==cc and np.array_equal(bm,cm)
bc=[a for a in bc if a!=2305];cc=[a for a in cc if a!=2305]
original=root.digest()
ba=base.score_candidates(root,0,bc,trace=True);ca=changed.score_candidates(root,0,cc,trace=True)
assert (ba,base.last)==(ca,changed.last)
fixed=copy.deepcopy(changed.last)
da=changed.score_candidates(root,0,cc,trace=True,deadline=time.perf_counter()+30)
assert da==ca and np.allclose(changed.last['scores'],fixed['scores'],rtol=0,atol=1e-12)
assert sorted(changed.last['traces'])==sorted(fixed['traces'])
assert root.digest()==original
changed.coverage=True
# Use a synthetic missing slot through the pure helper in unit tests; here
# all four affordable slots must survive the real mask and real ranking.
covered,mask=changed.candidates(info.packet)
assert len(covered)==len(cc)
assert 2304 in covered and {a//576 for a in covered if a<2304}==set(range(4))
start=time.perf_counter();action=changed.score_candidates(root,0,covered,deadline=start+.18);elapsed=time.perf_counter()-start
assert elapsed<.2 and action in covered
out=dict(passed=True,candidate_mask_parity=True,flags_off_scores_and_traces_identical=True,budget_nontruncated_scores_and_traces_identical=True,root_unchanged=True,all_affordable_slots_covered=True,bounded_score_seconds=elapsed,budget_counts=dict(changed.budget_counts),seed=2**48+90000)
Path(sys.argv[1]).parent.mkdir(parents=True,exist_ok=True)
Path(sys.argv[1]).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
