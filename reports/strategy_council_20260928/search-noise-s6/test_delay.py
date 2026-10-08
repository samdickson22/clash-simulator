import bootstrap
from bootstrap import HERE
import copy,hashlib,json,unittest
from dataclasses import replace
from types import SimpleNamespace
from delay import CommandChannel,DelayedRoot,PendingCommand,DelayAwarePlanner
from cells import CELLS


class FakeNative:
    def apply_discrete(self,sim,seat,action):
        if action==2304:return False
        sim.actions.append((sim.tick,seat,action));return True
    def select_action(self,sim,seat,style):return 0
    def evaluate(self,sim,seat,weight):return len(sim.actions)

class FakeSim:
    def __init__(self):self.tick=100;self.actions=[]
    def clone(self):return copy.deepcopy(self)
    def step(self,n):self.tick+=n


class DelayTests(unittest.TestCase):
    def test_frozen_tracker(self):
        for n,h in json.loads((HERE/'frozen-s4-inputs.json').read_text()).items():
            self.assertEqual(hashlib.sha256((HERE/n).read_bytes()).hexdigest(),h,n)

    def test_configuration(self):
        self.assertEqual(len(CELLS),5)
        for d in (-1,1.1,True):
            with self.assertRaises(ValueError):CommandChannel(d)
        self.assertEqual(CommandChannel().delay,22)

    def test_channel_one_spend_and_cycle(self):
        from own_state import OwnState
        info=SimpleNamespace(tick=100,own=dict(elixir=8.,hand=['HogRider','Knight','Archers','Fireball'],cycle=['Log','Cannon','Skeletons','IceSpirit'],refill=0))
        original=copy.deepcopy(info.own)
        ch=CommandChannel();ch.submit(info,0,{'HogRider':4},None)
        self.assertEqual(ch.ledger.pending[1]['elixir'],4)
        self.assertEqual(ch.ledger.pending[1]['hand'][0],None)
        self.assertEqual(ch.ledger.pending[1]['cycle'][-1],'HogRider')
        self.assertEqual(info.own,original)
        with self.assertRaises(ValueError):ch.submit(info,0,{'HogRider':4},None)
        self.assertFalse(ch.ready(121));self.assertTrue(ch.ready(122))
        ch.finish(True)
        self.assertEqual(ch.diagnostics(),dict(submitted=1,executed=1,rejected=0,blocked_polls=0,pending_at_end=0))
        with self.assertRaises(ValueError):ch.finish(True)
        ch.submit(info,0,{'HogRider':4},None);ch.finish(False)
        self.assertEqual(ch.rejected,1);self.assertIsNone(ch.ledger.pending)
        ch.submit(info,2304,{},None);self.assertIsNone(ch.pending)

    def test_rollout_due_horizon_and_seats(self):
        for seat in (0,1):
            p=object.__new__(DelayAwarePlanner);p.native=FakeNative();p.info=SimpleNamespace(tick=100)
            p.config=SimpleNamespace(horizon=60,interval=10,elixir_weight=1.)
            p.command_delay=22
            physical=FakeSim();root=DelayedRoot(physical,{'elixir':4},PendingCommand(100,122,7))
            value,events,sim=p.delayed_rollout(root,seat,1,'balanced',True)
            own=[a for a in sim.actions if a[1]==seat]
            self.assertEqual(own,[(122,seat,7),(152,seat,0)])
            self.assertEqual(sim.tick,160);self.assertEqual(physical.tick,100)
            self.assertEqual(physical.actions,[])
            p.config.horizon=22
            _,_,sim=p.delayed_rollout(root,seat,1,'balanced')
            self.assertFalse(any(a[1]==seat for a in sim.actions))


class NativeDelayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fair_player import Resources,observe
        from differential import initial
        from derived_public_state import DerivedPublicState
        from player import Player
        cls.r=Resources()
        cls.prior=json.loads((HERE/'runtime/support/human_deck_catalog.json').read_text())
        cls.r.initial_belief=DerivedPublicState(cls.prior,cls.r.costs)
        from clasher.battle import BattleState
        from clasher.player import PlayerState
        from collections import deque
        import random
        deck=['HogRider','Musketeer','IceGolem','IceSpirit','Skeletons','Cannon','Fireball','Log']
        b=BattleState(players=[PlayerState(i,deck=list(deck),hand=deck[:4],cycle_queue=deque(deck[4:])) for i in (0,1)],rng=random.Random(9780800001),card_loader=cls.r.builder.loader)
        b.players[0].elixir=b.players[1].elixir=10
        cls.info=observe(b,cls.r.builder,0,())
        cls.player=Player(cls.r,cls.prior,9780900001,'clean-d22-aware')
        cls.player.core.info=cls.info;cls.player.core.costs=cls.r.costs

    def test_pending_visible_past_16_ticks_and_single_native_debit(self):
        import numpy as np
        from clasher.rl.c56_rollout_planner import C56SearchConfig
        p=self.player.core;info=self.info
        actions,_=p.candidates(info.packet);action=next(a for a in actions if a<2304)
        name=info.own['hand'][action//576];cost=self.r.costs[name]
        root=self.r.root(info,self.r.initial_belief.sample(np.random.default_rng(1)),np.random.default_rng(2))
        channel=CommandChannel();channel.submit(info,action,self.r.costs,self.r.builder)
        after=channel.own_packet(replace(info,tick=info.tick+20),self.r.builder)
        self.assertLess(after.own['elixir'],10)
        self.assertEqual(after.own['cycle'].count(name),1)
        pending=p.candidate_root(root,action)
        self.assertEqual(pending.own['elixir'],10-cost)
        self.assertEqual(json.loads(root.snapshot())['players'][0]['elixir'],10)
        p.config=C56SearchConfig(horizon=23,interval=10)
        _,events,sim=p.delayed_rollout(pending,0,2304,'balanced',True)
        executions=[e for e in events if e[0]=='execute']
        self.assertEqual(len(executions),1);self.assertEqual(executions[0][1],info.tick+22)
        self.assertTrue(executions[0][-1])
        own=json.loads(sim.snapshot())['players'][0]
        self.assertAlmostEqual(own['elixir'],10-cost+.0178,places=7)
        self.assertEqual(own['cycle'].count(name),1)
        self.assertEqual(json.loads(root.snapshot())['players'][0]['elixir'],10)

if __name__=='__main__':unittest.main()
