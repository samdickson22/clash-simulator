import bootstrap
import copy,json,random,unittest
from collections import deque
from dataclasses import replace
import numpy as np
from fair_player import Resources,observe
from clasher.battle import BattleState
from clasher.player import PlayerState
from noise import Sensor,SeenEvent
from player import Player
from cells import QUALITIES
from test_elt import DECK,PRIOR

class Boundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.r=Resources()
    def battle(self):
        return BattleState(players=[PlayerState(i,deck=DECK[:],hand=DECK[:4],cycle_queue=deque(DECK[4:])) for i in (0,1)],rng=random.Random(7611000001),card_loader=self.r.builder.loader)
    def test_only_nonderivable_state_invariance(self):
        b=self.battle();info=observe(b,self.r.builder,0,())
        # No opponent plays yet: hand and cycle identities are unresolved.
        # Starting elixir is exactly derivable and is deliberately preserved.
        alternate_deck=['Giant','Knight','Archers','MiniPekka','Minions','Zap','Fireball','Skeletons']
        fair_prior={'decks':[{'cards':DECK,'frequency':1},{'cards':alternate_deck,'frequency':1}]}
        b.players[1].deck=alternate_deck[:]
        b.players[1].hand=alternate_deck[:4]
        b.players[1].cycle_queue=deque(alternate_deck[4:])
        b.rng.seed(7611000002)
        alternate=observe(b,self.r.builder,0,())
        for key in ('entity_ids','entity_features','entity_mask','hand_ids','global_features'):
            np.testing.assert_array_equal(getattr(info.packet.observation,key),getattr(alternate.packet.observation,key))
        for arm in ('B','E1','E4','E4R'):
            a=Player(self.r,fair_prior,7611000003,arm+'-N64');c=Player(self.r,fair_prior,7611000003,arm+'-N64')
            self.assertEqual(a.decide(info,0),c.decide(alternate,0))
            self.assertEqual(a.core.last,c.core.last)
    def test_noise_rates(self):
        events=[SeenEvent(i*20,'card','HogRider',x=9,y=16,event_id=str(i)) for i in range(10000)]
        for q,(recall,precision) in QUALITIES.items():
            s=Sensor('E4-'+q,7611000004,self.r.builder);s.ingest(events);c=s.counts
            self.assertAlmostEqual(c['matched_events']/c['truth_events'],recall,delta=.015)
            self.assertAlmostEqual(c['matched_events']/(c['matched_events']+c['confused_events']+c['spurious_events']),precision,delta=.015)
    def test_scoring_does_not_update_tracker(self):
        p=Player(self.r,PRIOR,7611000005,'E4-N64')
        before=copy.deepcopy(p.rng.bit_generator.state);weights=p.belief.weights.copy()
        p.diagnostic(0,[]);p.diagnostic(10,DECK[:4])
        self.assertEqual(before,p.rng.bit_generator.state);np.testing.assert_array_equal(weights,p.belief.weights)
    def test_four_root_scores_choose_shared_action_mean(self):
        from unittest.mock import patch
        p=Player(self.r,PRIOR,7611000007,'E4-N64')
        info=observe(self.battle(),self.r.builder,0,())
        inputs=[]
        def score(root,seat,candidates):
            inputs.append(tuple(candidates))
            p.core.last={'scores':([9,0,8,0,0] if root%2==0 else [0,9,8,0,0])}
        with patch.object(p.belief,'roots',return_value=[0,1,2,3]), patch.object(self.r,'root',side_effect=lambda info,sample,rng:sample), patch.object(p.core,'candidates',return_value=(list(range(10)),None)), patch.object(p.core,'score_candidates',side_effect=score):
            action,searched=p.decide(info,0)
        self.assertEqual(action,2);self.assertTrue(searched)
        self.assertEqual(inputs,[(0,1,2,3,4)]*4)
        self.assertEqual(p.diagnostics['rollouts'],60)

    def test_shared_initial_prior_matches_uncached(self):
        from derived_public_state import DerivedPublicState
        a=Player(self.r,PRIOR,7611000008,'E4-N64')
        self.r.initial_belief=DerivedPublicState(PRIOR,self.r.costs)
        try:
            b=Player(self.r,PRIOR,7611000008,'E4-N64')
            info=observe(self.battle(),self.r.builder,0,())
            info=replace(info,tick=100,events=(SeenEvent(90,'card','HogRider',event_id='x'),))
            self.assertEqual(a.decide(info,0),b.decide(info,0))
            self.assertEqual(a.core.last,b.core.last)
            self.assertEqual(self.r.initial_belief.tick,0)
            self.assertEqual(self.r.initial_belief.events,[])
            self.assertEqual(self.r.initial_belief.elixir,6.)
        finally:del self.r.initial_belief

    def test_identity_noise_remains_in_script_support(self):
        b=self.battle()
        from clasher.arena import Position
        b.deploy_card(1,'HogRider',Position(4.5,20.5))
        info=observe(b,self.r.builder,0,())
        sensor=Sensor('E4-N90-identity',7611000009,self.r.builder)
        sensor.identity_templates={key:value for key,value in self.r.templates.items() if key[0] in self.r.bots['balanced'].bodies}
        for _ in range(100):
            packet=sensor.capture(info).packet
            self.r.bots['balanced']._bodies(packet)
        self.assertGreater(sensor.counts['identity_confusions'],0)

    def test_pending_reconciliation(self):
        p=Player(self.r,PRIOR,7611000006,'E4-N64');info=observe(self.battle(),self.r.builder,0,())
        p.own_state.submit(info,0,self.r.costs)
        predicted=p.own_state.packet(info,self.r.builder)
        predicted.packet.validate()
        self.assertEqual(predicted.own['elixir'],2.)
        self.assertIsNone(predicted.own['hand'][0]);self.assertEqual(info.own['elixir'],6.)
        with self.assertRaises(ValueError):p.own_state.submit(info,0,self.r.costs)
        p.own_state.reconcile(info);self.assertEqual(p.own_state.packet(info,self.r.builder).own,info.own)
        packet=copy.deepcopy(info.packet);obs=packet.observation
        i=int(np.flatnonzero(~obs.entity_mask)[0])
        obs.entity_mask[i]=True;obs.entity_ids[i]=self.r.builder.token_id('ArcherQueen',namespace='troop_body')
        obs.entity_features[i,2]=1;obs.entity_features[i,4]=1;packet.entity_id_confidence[i]=1
        public=replace(info,packet=packet)
        p.own_state.submit(public,2305,self.r.costs,self.r.builder)
        self.assertEqual(p.own_state.pending[1]['elixir'],6.-self.r.builder.ability_cost_for_token(int(obs.entity_ids[i])))


if __name__=='__main__':unittest.main()
