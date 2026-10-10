import unittest
import numpy as np
import torch
from proposals import calibrate,rank_actions,outputs
from exit_r3.network import ModelConfig,SetPolicy,AdvantagePolicy

class Tests(unittest.TestCase):
    def test_calibration_prevalence_and_ties(self):
        p=np.arange(1000)/1000;mask=np.ones(1000,bool)
        t=calibrate(p,mask);self.assertEqual(np.count_nonzero(p>=t),346)
        p=np.array([.1,.1,.9,.9]);t=calibrate(p,np.ones(4,bool),.25)
        self.assertEqual(t,.5) # equal distance chooses smaller threshold
        t=calibrate(p,np.zeros(4,bool));self.assertEqual(t,1.)
    def test_legal_rank_and_deterministic_ties(self):
        mask=np.zeros(2306,bool);mask[[2,5,10,2304]]=True
        values=np.zeros(2304);values[10]=2;values[100]=100
        np.testing.assert_array_equal(rank_actions(values,mask),[10,2,5])
    def test_one_pass_and_advantage_ranking(self):
        torch.set_num_threads(1);c=ModelConfig(width=24,heads=6,layers=1,ffn=48,tile_width=16,dropout=0)
        assets=(torch.zeros(360,57),torch.zeros(576,12),torch.ones(360))
        model=AdvantagePolicy(c,*assets).eval();calls=[];original=model.encode
        def encode(b):calls.append(1);return original(b)
        model.encode=encode
        b=dict(ids=torch.ones(1,5,dtype=torch.long),types=torch.ones(1,5,dtype=torch.long),numeric=torch.zeros(1,5,24),valid=torch.ones(1,5,dtype=torch.bool),action_mask=torch.ones(1,2306,dtype=torch.bool))
        p,r=outputs(model,b);self.assertEqual(len(calls),1);self.assertEqual(r.shape,(1,2304));self.assertTrue(0<=float(p[0])<=1)
if __name__=='__main__':unittest.main()
