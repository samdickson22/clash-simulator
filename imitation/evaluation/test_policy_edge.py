"""Light real-engine edge checks, not complete smoke games."""
from collections import deque
import random
import unittest
import torch
from .paths import setup
setup()
from clasher.battle import BattleState
from clasher.player import PlayerState
from clasher.rl.contract_v5 import ContractV5ObservationBuilder
from clasher.rl.action_space import DiscreteTileActionSpace
from imitation.model.synthetic import model
from imitation.model.inference import Policy
from .events import PublicRecorder
from .standalone import StandalonePlayer


class PolicyEdgeTest(unittest.TestCase):
    def test_two_seats_public_masks_and_event_updates(self):
        torch.set_num_threads(1)
        torch.manual_seed(19)
        builder=ContractV5ObservationBuilder()
        deck=['HogRider','Musketeer','IceGolem','IceSpirit','Skeletons','Cannon','Fireball','Log']
        b=BattleState(players=[PlayerState(i,deck=deck,hand=deck[:4],cycle_queue=deque(deck[4:]))
                               for i in (0,1)],rng=random.Random(44),card_loader=builder.loader)
        costs={n:float(builder.loader.get_card(n).mana_cost) for n in deck}
        policy=Policy(model())
        players=[StandalonePlayer(policy,builder,costs,i,deck,99+i) for i in (0,1)]
        space=DiscreteTileActionSpace()
        with PublicRecorder(builder) as recorder:
            recorder.bind(b)
            for _ in range(90):b.step()
            for tick in (90,95):
                actions=[]
                for seat in (0,1):
                    action,mask=players[seat].decide(b.tick,builder.build_public(b,seat),recorder.public_events)
                    self.assertTrue(mask[action]);actions.append(action)
                for seat,action in enumerate(actions):
                    self.assertTrue(space.apply_action(b,seat,action))
                for _ in range(5):b.step()
            self.assertTrue(recorder.public_events)


class P16ShimTest(unittest.TestCase):
    def test_eval_dispatch_keeps_v4_protocol_and_v5_actor(self):
        import json
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import patch
        from clasher.rl import eval as ev
        from clasher.rl.structured_obs import StructuredObservationBuilder
        from clasher.rl.selfplay_env import SelfPlayBattleEnv
        from .p16_adapter import installed
        from imitation.model.inference import Policy
        deck=['HogRider','Musketeer','IceGolem','IceSpirit','Skeletons','Cannon','Fireball','Log']
        folder=tempfile.mkdtemp(prefix='t6t8-edge-')
        if folder:  # Retain owned fixture data under the task's no-delete rule.
            path=Path(folder)/'decks.json'
            path.write_text(json.dumps({'cards':deck,'decks':[{'cards':deck}]}))
            builder=StructuredObservationBuilder(decks_path=path,card_semantics_version=4,
                canonical_perspective=True,canonical_lane_globals=True,public_history_slots=4,
                public_seen_card_slots=8,public_entity_levels=True,public_hand_levels=True)
            builder.public_contract_version=4
            cfg=SimpleNamespace(public_contract_version=4,canonical_lane_globals=True)
            legacy=SimpleNamespace(builder=builder,model=SimpleNamespace(config=cfg))
            with patch.object(ev,'load_policy_checkpoint',return_value=legacy), \
                 patch('imitation.evaluation.p16_adapter.load_policy',return_value=Policy(model())):
                with installed(Path(folder)/'synthetic.pt',Path(folder)/'legacy.pt',fixed_world=True):
                    facade=ev.load_policy_checkpoint(Path(folder)/'synthetic.pt')
                    self.assertEqual(facade.builder.public_contract_version,4)
                    env=SelfPlayBattleEnv(decks_path=path,decision_interval_ticks=5,
                        max_ticks=6001,public_contract_version=4,learner_player_id=1)
                    other=list(reversed(deck))
                    env.reset(seed=345,ordered_decks=(other,deck))
                    # Fixed-world swap undoes P16's candidate-deck-following-seat convention.
                    self.assertEqual(list(env.battle.players[0].hand),deck[:4])
                    for _ in range(90):env.battle.step()
                    a,_,mask,_=ev._policy_step(facade,env,1,state=(torch.zeros(1),torch.zeros(1)),
                        previous_action=2304,previous_reward=0.,episode_start=True,
                        deterministic=False,device=torch.device('cpu'))
                    self.assertTrue(mask[a])


if __name__=='__main__': unittest.main()
