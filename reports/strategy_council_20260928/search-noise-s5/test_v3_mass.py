import bootstrap
import itertools,math,unittest
from collections import Counter
from tracker_v3 import TrackerV3
from tracker_v2 import Evidence
from test_tracker_v3 import DECK,COSTS,PRIOR
class Tests(unittest.TestCase):
 def test_mass_is_conservative(self):
  tr=TrackerV3(PRIOR,COSTS,recall=.97,precision=.97)
  for i,name in enumerate(DECK):
   tr.observe(__import__('elt').Candidate(100+100*i,((name,1.),),.97));tr.advance(150+100*i)
   full=Counter()
   for state,w in tr._hands:
    d=tr._clone_hand(state);d.advance(tr.tick)
    known=set(d.queue)-{None};n=d.queue.count(None)
    for deck,p in tr.support(tuple(sorted(d.revealed))):
     remaining=sorted(deck-d.revealed)
     for latent in itertools.combinations(remaining,n):
      hand=tuple(sorted(deck-known-set(latent)))+(None,)*(len(d.queue)-4)
      full[hand]+=w*p/math.comb(len(remaining),n)
   for hand,mass in tr.hand_masses().items():self.assertLessEqual(mass,full[hand]+1e-12)
 def test_presence_factorization(self):
  tr=TrackerV3(PRIOR,COSTS,recall=.97,precision=.97);d=tr._hands[0][0]
  for name in DECK:
   old=sum(p for deck,p in tr.support(tuple(sorted(d.revealed))) if name in deck)
   self.assertAlmostEqual(old,tr.presence(tuple(sorted(d.revealed))).get(name,0.))
if __name__=='__main__':unittest.main()
