import bootstrap
from bootstrap import HERE
import copy,json,random,unittest
from collections import Counter,deque
from dataclasses import replace
import numpy as np
from fair_player import Resources,observe
from clasher.battle import BattleState
from clasher.player import PlayerState
from clasher.arena import Position
from noise import Sensor,SeenEvent,VARIANTS
from cells import CELLS,CHANNELS,configuration
from player import Player
from test_elt import DECK,PRIOR
from trace import snapshot,trajectory

class SwitchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.r=Resources()
    def info(self):
        b=BattleState(players=[PlayerState(i,deck=DECK[:],hand=DECK[:4],cycle_queue=deque(DECK[4:])) for i in (0,1)],rng=random.Random(9710800001),card_loader=self.r.builder.loader)
        b.deploy_card(1,'HogRider',Position(4.5,20.5))
        for _ in range(20):b.step()
        return observe(b,self.r.builder,0,())
    def test_cell_contract(self):
        self.assertEqual(len(CELLS),14)
        self.assertEqual(CELLS['Full'],configuration(CHANNELS))
        self.assertEqual(CELLS['Full'],CELLS['R-taps'])
        self.assertEqual(CELLS['A'],configuration(()))
        self.assertEqual(CELLS['R-events']['tracker'],'elt')
        self.assertEqual(CELLS['A+derived']['tracker'],'elt')
        for c in ('board','hp','own','latency'):
            self.assertEqual(CELLS['R-'+c],configuration(set(CHANNELS)-{c}))
    def test_exact_sensor(self):
        info=self.info();s=Sensor('A',9810800001,self.r.builder);out=s.capture(info)
        for key in ('entity_ids','entity_mask','entity_features','hand_ids','global_features'):
            np.testing.assert_array_equal(getattr(out.packet.observation,key),getattr(info.packet.observation,key))
        self.assertEqual(out.own,info.own)
    def test_repair_board_and_hp(self):
        info=self.info();o=info.packet.observation
        board=Sensor('R-board',9810800001,self.r.builder)
        hp=Sensor('R-hp',9810800001,self.r.builder)
        for _ in range(20):
            a=board.capture(info).packet.observation;b=hp.capture(info).packet.observation
            np.testing.assert_array_equal(a.entity_mask,o.entity_mask)
            np.testing.assert_array_equal(a.entity_ids,o.entity_ids)
            np.testing.assert_array_equal(a.entity_features[:,:2],o.entity_features[:,:2])
            retained=o.entity_mask & b.entity_mask
            np.testing.assert_array_equal(b.entity_features[retained,9],o.entity_features[retained,9])
        self.assertEqual(board.counts['phantom_entities'],0);self.assertEqual(board.counts['dropped_entities'],0)
        self.assertEqual(hp.counts['hp_imputed'],0)
    def test_own_repair(self):
        info=self.info();sensor=Sensor('R-own',9810800001,self.r.builder)
        for _ in range(40):
            out=sensor.capture(info);self.assertEqual(out.own,info.own)
            np.testing.assert_array_equal(out.packet.observation.hand_ids,info.packet.observation.hand_ids)
    def test_n97_and_perfect_events(self):
        events=[SeenEvent(i*20,'card','HogRider',x=9,y=16,event_id=str(i)) for i in range(10000)]
        s=Sensor('Full',9810800001,self.r.builder);s.ingest(events);c=s.counts
        self.assertAlmostEqual(c['matched_events']/c['truth_events'],.97,delta=.006)
        self.assertAlmostEqual(c['matched_events']/(c['matched_events']+c['confused_events']+c['spurious_events']),.97,delta=.006)
        exact=Sensor('R-events',9810800001,self.r.builder);exact.ingest(events)
        self.assertEqual(exact.deliver(200000),tuple(events))
    def test_truth_diagnostic_no_rng_or_belief_update(self):
        p=Player(self.r,PRIOR,9710800001,'A+derived')
        rng=copy.deepcopy(p.rng.bit_generator.state);weights=p.belief.weights.copy()
        snapshot(p.belief,0,1,[]);snapshot(p.belief,0,10,DECK[:4])
        p.diagnostic(1,[])
        self.assertEqual(rng,p.rng.bit_generator.state);np.testing.assert_array_equal(weights,p.belief.weights)
    def test_trace_preserves_actions(self):
        from derived_public_state import DerivedPublicState
        info=self.info()
        for cell in ('A+derived','R-events'):
            a=Player(self.r,PRIOR,9710800001,cell);b=Player(self.r,PRIOR,9710800001,cell)
            for tick in (100,110,120):
                packet=replace(info,tick=tick)
                snapshot(a.belief,tick,3.,DECK[:4])
                self.assertEqual(a.decide(packet,0),b.decide(packet,0))
                self.assertEqual(a.core.last,b.core.last)

    def test_public_only_boundary(self):
        battle=BattleState(players=[PlayerState(i,deck=DECK[:],hand=DECK[:4],cycle_queue=deque(DECK[4:])) for i in (0,1)],rng=random.Random(9710800001),card_loader=self.r.builder.loader)
        info=observe(battle,self.r.builder,0,())
        battle.players[1].hand=list(reversed(DECK[4:]));battle.players[1].cycle_queue=deque(reversed(DECK[:4]))
        battle.rng.seed(9710801010)
        alternate=observe(battle,self.r.builder,0,())
        for key in ('entity_ids','entity_mask','entity_features','hand_ids','global_features'):
            np.testing.assert_array_equal(getattr(info.packet.observation,key),getattr(alternate.packet.observation,key))
        for cell in CELLS:
            a=Player(self.r,PRIOR,9710800001,cell);b=Player(self.r,PRIOR,9710800001,cell)
            self.assertEqual(a.decide(info,0),b.decide(alternate,0))
            self.assertEqual(a.core.last,b.core.last)
    def test_trajectory_censoring(self):
        rows=[dict(tick=i,covered=v) for i,v in enumerate([True,False,True,False,False])]
        self.assertEqual(trajectory(rows,'covered',1),dict(first_loss_tick=1,recovered=True,terminal_loss_tick=3,last_decision_tick=4))

class ProtocolTests(unittest.TestCase):
    def test_jobs_and_seed_pairs(self):
        from worker import jobs
        schedule=json.loads((HERE/'schedule.json').read_text());rows=jobs(schedule)
        self.assertEqual(len(rows),3584)
        self.assertEqual(set(Counter(c for ep,c,s in rows).values()),{256})
        self.assertEqual(set(Counter((ep['pair'],c) for ep,c,s in rows).values()),{2})
        self.assertEqual(len({ep['seed'] for ep in schedule['pairs']}),128)
        self.assertEqual(sorted(i for w in range(152) for i in range(3584) if i%152==w),list(range(3584)))
    def test_bootstrap(self):
        from analyze import ci
        self.assertEqual(ci([.5]*128),[.5,.5,.5])
        x=ci([-.5,0,.5,1]*32);y=ci([.5,0,-.5,-1]*32)
        self.assertEqual(x[0],-y[0]);self.assertAlmostEqual(x[1],-y[2]);self.assertAlmostEqual(x[2],-y[1])

if __name__=='__main__':unittest.main()
