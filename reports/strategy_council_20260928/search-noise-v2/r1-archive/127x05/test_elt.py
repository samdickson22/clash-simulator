import bootstrap
import copy
import unittest
import numpy as np
from elt import ELT, Candidate, elixir_at
from derived_public_state import DerivedPublicState, PublicEvent

DECK=['HogRider','Musketeer','IceGolem','IceSpirit','Skeletons','Cannon','Fireball','Log']
COSTS=dict(zip(DECK,[4,4,2,1,1,3,4,2]))
PRIOR={'decks':[{'cards':DECK,'frequency':1}]}

class TrackerTests(unittest.TestCase):
    def test_exact_public_ledger_and_cycle(self):
        exact=DerivedPublicState(PRIOR,COSTS)
        elt=ELT(PRIOR,COSTS)
        events=[]
        rng=np.random.default_rng(867012)
        for tick in range(90,6001,30):
            exact.advance(tick)
            sample=exact.sample(rng)
            legal=[n for n in sample['hand'] if n and COSTS[n]<=sample['elixir']]
            if legal:
                name=legal[int(rng.integers(len(legal)))];events.append(PublicEvent(tick,'card',name))
                exact.update(tick,events)
                elt.observe(Candidate(tick,((name,1.),),1.))
            elt.advance(tick)
            state=elt.projected()[0]
            self.assertEqual(len(elt.hypotheses),1)
            self.assertEqual(exact.elixir,state.elixir)
            self.assertEqual(exact.refill,state.refill)
            np.testing.assert_array_equal(exact.states,state.states)
            self.assertEqual(exact.derived(),state.derived())

    def test_reject_and_second_card(self):
        elt=ELT(PRIOR,COSTS,beam=128)
        elt.observe(Candidate(100,(('Missing',.8),('HogRider',.2)),.9))
        self.assertEqual(len(elt.hypotheses),2)
        self.assertAlmostEqual(sum(elt.weights),1)
        self.assertEqual({len(h.state.events) for h in elt.hypotheses},{0,1})

    def test_noisy_path_preserves_parent(self):
        elt=ELT(PRIOR,COSTS)
        before=copy.deepcopy(elt.hypotheses[0].state)
        elt.observe(Candidate(100,(('HogRider',1.),),.7))
        rejected=next(h.state for h in elt.hypotheses if not h.state.events)
        np.testing.assert_array_equal(before.states,rejected.states)
        self.assertEqual(before.tick,rejected.tick)
        elt.advance(120)
        a=elt.roots(np.random.default_rng(1),4,True)
        b=elt.roots(np.random.default_rng(1),4,True)
        self.assertEqual(a,b)
        self.assertEqual(len(a),5)
        self.assertGreaterEqual(a[-1]['elixir'],elt.distribution()['elixir_q90'])

    def test_batched_elixir_equals_framewise_reference(self):
        for start in (0,90,2399,2400,2401,4799,4800,4801,5999):
            for amount in (0.,.0001,3.4567,9.9999,10.):
                state=DerivedPublicState(PRIOR,COSTS);state.tick=start;state.elixir=amount
                for end in (start,start+1,start+20,6001):
                    expected=elixir_at(state,end)
                    reference=copy.copy(state);reference.advance(end)
                    self.assertEqual(expected,reference.elixir)

    def test_q1_impossible_fails(self):
        elt=ELT(PRIOR,COSTS)
        with self.assertRaises(ValueError):elt.observe(Candidate(0,(('Missing',1.),),1.))

if __name__=='__main__':unittest.main()
