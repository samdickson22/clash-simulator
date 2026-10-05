import bootstrap
from bootstrap import HERE
import copy,hashlib,json,time,unittest
from dataclasses import replace
import numpy as np
from evaluate import Resources,observe,BattleState,PlayerState,deque,random,write,game
from noise import Sensor,SeenEvent,VARIANTS,MODEL
from player import Player
from differential import battle_digest

class Boundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r=Resources();cls.prior=json.loads((HERE/'runtime/support/human_deck_catalog.json').read_text())
        cls.deck=['HogRider','Musketeer','IceGolem','IceSpirit','Skeletons','Cannon','Fireball','Log']
    def battle(self):
        return BattleState(players=[PlayerState(i,deck=self.deck[:],hand=self.deck[:4],cycle_queue=deque(self.deck[4:])) for i in (0,1)],rng=random.Random(3926710401),card_loader=self.r.builder.loader)
    def test_sensor_purity_and_clean_identity(self):
        b=self.battle();b.deploy_card(1,'HogRider',__import__('clasher.arena',fromlist=['Position']).Position(4.5,20.5))
        info=observe(b,self.r.builder,0,());before=battle_digest(b);raw=copy.deepcopy(info)
        for v in VARIANTS:
            sensor=Sensor(v,3926710403,self.r.builder);out=sensor.capture(info)
            self.assertEqual(before,battle_digest(b))
            for key in ('entity_ids','entity_features','entity_mask','hand_ids','global_features'):
                np.testing.assert_array_equal(getattr(info.packet.observation,key),getattr(raw.packet.observation,key))
                if v=='A':np.testing.assert_array_equal(getattr(info.packet.observation,key),getattr(out.packet.observation,key))
            self.assertEqual(info.own,raw.own)
    def test_noise_rates(self):
        events=[SeenEvent(i*20,'card','HogRider',x=9,y=16,event_id=str(i)) for i in range(50000)]
        result={}
        for v,recall,precision in [('B',MODEL['recall'],MODEL['precision']),('D',.9,.9)]:
            sensor=Sensor(v,3926710404,self.r.builder);sensor.ingest(events);c=sensor.counts
            r=c['matched_events']/c['truth_events'];p=c['matched_events']/(c['matched_events']+c['confused_events']+c['spurious_events'])
            self.assertAlmostEqual(r,recall,delta=.012);self.assertAlmostEqual(p,precision,delta=.012)
            self.assertAlmostEqual(c['placement_hits']/c['matched_events'],.9,delta=.015)
            self.assertTrue(all(e.name for e in sensor.pending));result[v]=dict(c,recall=r,precision=p)
        write(HERE/'noise-rate-test.json',result)
    def test_coordinates_do_not_enter_player(self):
        b=self.battle()
        for _ in range(100):b.step()
        info=observe(b,self.r.builder,0,())
        events=(SeenEvent(96,'card','HogRider',x=2,y=10,event_id='a'),)
        moved=(replace(events[0],x=17,y=31),)
        a=Player(self.r,self.prior,3926710405,'B');c=Player(self.r,self.prior,3926710405,'B')
        # Unlimited test deadline removes scheduling as a confound.
        ax=a.decide(replace(info,events=events),0,time.perf_counter()+30)
        cx=c.decide(replace(info,events=moved),0,time.perf_counter()+30)
        self.assertEqual(ax,cx);self.assertEqual(a.core.last,c.core.last)
        self.assertEqual(a.belief.distribution(),c.belief.distribution())
    def test_hidden_state_does_not_reach_packet_or_noise(self):
        b=self.battle();info=observe(b,self.r.builder,0,())
        b.players[1].elixir=.123;b.players[1].hand=list(reversed(b.players[1].hand));b.players[1].cycle_queue=deque(reversed(b.players[1].cycle_queue));b.rng.seed(333)
        poisoned=observe(b,self.r.builder,0,())
        left=Sensor('B',3926710406,self.r.builder).capture(info);right=Sensor('B',3926710406,self.r.builder).capture(poisoned)
        self.assertEqual(left.own,right.own)
        for key in ('entity_ids','entity_features','entity_mask','hand_ids','global_features'):
            np.testing.assert_array_equal(getattr(left.packet.observation,key),getattr(right.packet.observation,key))
    def test_derived_scoring_cannot_change_rng_or_belief(self):
        p=Player(self.r,self.prior,3926710407,'B')
        before=copy.deepcopy(p.belief.__dict__);rng=copy.deepcopy(p.rng.bit_generator.state)
        p.diagnostic(.5,['HogRider']*4);p.diagnostic(10.,['Log']*4)
        self.assertEqual(rng,p.rng.bit_generator.state)
        for key in ('elixir','cards','hand','queue','weights'):np.testing.assert_array_equal(before[key],p.belief.__dict__[key])
        self.assertEqual(before['rng'].bit_generator.state,p.belief.rng.bit_generator.state)

if __name__=='__main__':unittest.main()
