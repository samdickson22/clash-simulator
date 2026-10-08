import bootstrap
import unittest
from types import SimpleNamespace
import numpy as np
from tracker_v3 import TrackerV3
from tracker_v2 import TrackerV2
DECK=['HogRider','Musketeer','IceGolem','IceSpirit','Skeletons','Cannon','Fireball','Log']
COSTS=dict(zip(DECK,[4,4,2,1,1,3,4,2]));PRIOR={'decks':[{'cards':DECK,'frequency':1}]}
def event(t,n,k):return SimpleNamespace(tick=t,name=n,kind='card',amount=0.,event_id=k)
class Tests(unittest.TestCase):
 def test_resource_lattice_unchanged(self):
  a=TrackerV2(PRIOR,COSTS,recall=.97,precision=.97);b=TrackerV3(PRIOR,COSTS,recall=.97,precision=.97)
  for t in range(100,501,10):
   es=[event(t,'HogRider',str(t))] if t in (100,400) else []
   a.update_public(t,es);b.update_public(t,es)
   np.testing.assert_array_equal(a._p,b._p)
 def test_recovers_after_miss_spurious_confusion(self):
  for error in ('miss','spurious','confused'):
   tr=TrackerV3(PRIOR,{**COSTS,'Knight':3},recall=.97,precision=.97)
   for i in range(40):
    name=DECK[i%8];t=100+i*100
    es=[] if i==6 and error=='miss' else [event(t+6,'Knight' if i==6 and error=='confused' else name,str(i))]
    if i==6 and error=='spurious':es.append(event(t+7,'Knight','fake'))
    tr.update_public(t+8,es);tr.advance(t+50)
   d=tr.distribution();self.assertEqual(set(d['best_hand']),set(DECK[:4]),(error,d));self.assertGreater(d['hand90_mass'],.80,(error,d))
if __name__=='__main__':unittest.main()
