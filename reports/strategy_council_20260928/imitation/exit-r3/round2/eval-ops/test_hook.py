import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import torch
from game import TimedPolicy
class HookTest(unittest.TestCase):
    def test_v1_sampler_and_proposer_unchanged(self):
        marker=object();calls=[]
        base=SimpleNamespace(model=None,costs=None,sample=lambda p,d,g:(calls.append(g) or 2304),propose=lambda p,d,k:[dict(action=7)])
        policy=TimedPolicy(base,None,lambda *a:None);self.assertEqual(policy.sample({},None,marker),2304);self.assertEqual(calls,[marker]);self.assertEqual(policy.propose({},None),[dict(action=7)])
    def test_calibrated_legal_choice_and_cached_top8(self):
        mask=np.zeros(2306,bool);mask[[2,5,2304]]=True;packet={'action_mask':mask};d1=object();ranks=torch.zeros(1,2304);ranks[0,5]=2;ranks[0,7]=10
        policy=TimedPolicy(SimpleNamespace(model=None,costs=None),.5,lambda *a:None)
        with patch('game.single_features',return_value={}),patch('game.outputs',return_value=(torch.tensor([.6]),ranks)) as infer:
            self.assertEqual(policy.sample(packet,d1),5);self.assertEqual([v['action'] for v in policy.propose(packet,d1)],[5,2]);self.assertEqual(infer.call_count,1)
            with self.assertRaises(AssertionError):policy.propose(packet,object())
        with patch('game.single_features',return_value={}),patch('game.outputs',return_value=(torch.tensor([.4]),ranks)):self.assertEqual(policy.sample(packet,d1),2304)
if __name__=='__main__':unittest.main()
