from corpus import quotas,stratum

def test_proportional_strata_and_sparse_stratum_minimum():
 q=quotas({(0,0):1,(1,1):1000,(2,2):1000},300)
 assert sum(q.values())==300 and q[(0,0)]==1
 assert abs(q[(1,1)]-q[(2,2)])<=1

def test_exact_bin_boundaries():
 assert stratum(2.99,0)==(0,0)
 assert stratum(3.,1)==(1,1)
 assert stratum(6.,128)==(2,2)

def test_committed_snapshot_clears_private_generator_without_touching_live_state():
 import copy,pickle
 from types import SimpleNamespace
 from corpus import committed_belief
 live=SimpleNamespace(_pending=(x for x in range(2)),states=[1,2],events=['a'])
 sealed=committed_belief(live)
 assert sealed._pending is None and live._pending is not None
 assert pickle.loads(pickle.dumps(sealed)).states==[1,2]
 sealed.states.append(3);assert live.states==[1,2]

def test_resume_and_fresh_committed_history_give_same_complete_belief():
 import numpy as np
 from belief import Belief
 from derived_public_state import PublicEvent
 from corpus import committed_belief
 prior={'decks':[{'cards':list('ABCDEFGH'),'frequency':2},{'cards':list('ABCDEFGI'),'frequency':3}]}
 costs=dict.fromkeys('ABCDEFGHI',3);b=Belief(prior,costs);b.block_rows=17
 events=[PublicEvent(1,'card','A')];now=[0.]
 def clock():now[0]+=.001;return now[0]
 try:b.update(20,events,deadline=.02,clock=clock)
 except TimeoutError:pass
 fresh=committed_belief(b);b.update(40,events,deadline=1e6,clock=lambda:0.);fresh.update(40,events)
 for k in ('states','weights','cumulative'):np.testing.assert_array_equal(getattr(b,k),getattr(fresh,k))
 r1=np.random.default_rng(11);r2=np.random.default_rng(11)
 assert [b.sample(r1) for _ in range(16)]==[fresh.sample(r2) for _ in range(16)]
 assert r1.bit_generator.state==r2.bit_generator.state
