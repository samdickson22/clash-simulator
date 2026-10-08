import bootstrap
import copy
import unittest
from types import SimpleNamespace
import numpy as np
from tracker_v2 import TrackerV2, shift, regen, Evidence
from elt import Candidate
from derived_d1 import DerivedD1, PublicEvent as D1Event
from derived_public_state import DerivedPublicState, PublicEvent
DECK=['HogRider','Musketeer','IceGolem','IceSpirit','Skeletons','Cannon','Fireball','Log']
COSTS=dict(zip(DECK,[4,4,2,1,1,3,4,2]));PRIOR={'decks':[{'cards':DECK,'frequency':1}]}
def event(t,n,key):return SimpleNamespace(tick=t,name=n,kind='card',amount=0.,event_id=key)
class Tests(unittest.TestCase):
 def test_body_map_empty_groups_and_multiple_bodies(self):
  from board import body_card_map
  r=SimpleNamespace(config={'cards':{'HogRider':{'units':[[],[{'class':'Troop','stats':{'name':'HogRider'}}]]}}},meta={'bodies':{'HogRider':{'token':7}}})
  self.assertEqual(body_card_map(r),{7:(('HogRider',1.),)})
 def test_exact_d1_and_finite_reference(self):
  ref=DerivedPublicState(PRIOR,COSTS);d1=DerivedD1(COSTS);t2=TrackerV2(PRIOR,COSTS)
  rng=np.random.default_rng(123)
  history=[]
  for t in range(90,6001,30):
   ref.advance(t);s=ref.sample(rng);legal=[n for n in s['hand'] if n and COSTS[n]<=s['elixir']]
   if legal:
    n=str(rng.choice(legal));history.append(PublicEvent(t,'card',n));ref.update(t,history)
    d1.accept(D1Event(t,'card',n));t2.observe(Candidate(t,((n,1.),),1.))
   d1.advance(t);t2.advance(t);got=t2.exact.projected()[0]
   self.assertEqual(got.elixir,ref.elixir);self.assertEqual(got.elixir,d1.elixir)
   self.assertEqual(got.refill,d1.refill);self.assertEqual(got.derived(),ref.derived())
   np.testing.assert_array_equal(got.states,ref.states)
 def test_lattice_phase_and_cap(self):
  for a in (0,2399,2400,4799,4800):
   for b in (a+1,a+20,6000):
    for u in (0,34567,99999,100000):
     d=DerivedD1(COSTS);d.tick=a;d.elixir=u/10000;d.advance(b)
     p=np.zeros(100001);p[u]=1
     got=shift(p,regen(a,b));self.assertEqual(np.argmax(got),d.elixir_units);self.assertEqual(got.sum(),1.)
 def test_missed_and_spurious_support_both_directions(self):
  tr=TrackerV2(PRIOR,COSTS,recall=.9,precision=.9)
  tr.advance(100);p=tr._p
  self.assertGreater(p[round((6+100*.0178-4)*10000)],0.)
  tr.update_public(106,[event(106,'HogRider','spurious')]);p=tr._p
  # Both zero-spend (spurious) and accepted-play states have positive support.
  self.assertGreater(p[77800],0.);self.assertGreater(p[37800],0.)
  self.assertAlmostEqual(p.sum(),1.,places=10)
 def test_board_event_fusion(self):
  tr=TrackerV2(PRIOR,COSTS,recall=.9,precision=.9,body_cards={4:(('HogRider',1.),)})
  for t in (100,102,104):tr.update_public(t,[],[(4,4.,20.)])
  self.assertEqual(tr.metrics['unmatched_board_births'],1)
  tr.update_public(106,[event(106,'HogRider','x')],[(4,4.,20.)])
  self.assertEqual(tr.metrics['event_board_matches'],1)
  self.assertEqual(len(tr.pending),1)
 def test_confused_and_recovery(self):
  costs={**COSTS,'Knight':3};prior={'decks':[{'cards':DECK,'frequency':1}]}
  tr=TrackerV2(prior,costs,recall=.9,precision=.9)
  tr.update_public(106,[event(106,'HogRider','confusion')])
  self.assertIn('Knight',dict(tr.pending[0].cards))
  tr.advance(2000)
  self.assertGreater(tr._p[100000],.5)
 def test_pruning_reserves_abstract_mass(self):
  tr=TrackerV2(PRIOR,COSTS,recall=.9,precision=.9,beam=4)
  for i,n in enumerate(DECK):tr.observe(Candidate(100+i*50,((n,1.),),.7))
  tr.advance(500)
  self.assertLessEqual(len(tr._hands),4)
  self.assertTrue(any(not d.revealed and w>0 for d,w in tr._hands))
  self.assertEqual(np.count_nonzero(tr._p),100001)
 def test_fairness_hidden_cards_and_rng_invariance(self):
  # Hidden environments differ, but the adapter exposes the same public tokens.
  a=TrackerV2(PRIOR,COSTS,recall=.9,precision=.9)
  b=TrackerV2(PRIOR,COSTS,recall=.9,precision=.9)
  env_a={'unrevealed':DECK,'rng':np.random.default_rng(1)}
  env_b={'unrevealed':list(reversed(DECK)),'rng':np.random.default_rng(919)}
  for t in (100,102,120,200):
   env_a['rng'].random(7);env_b['rng'].random(11)
   es=[event(106,'HogRider','one')] if t>=120 else []
   a.update_public(t,es);b.update_public(t,es)
   np.testing.assert_array_equal(a._p,b._p);self.assertEqual(a.distribution(),b.distribution())
   self.assertEqual(a.sample(np.random.default_rng(t)),b.sample(np.random.default_rng(t)))
if __name__=='__main__':unittest.main()
