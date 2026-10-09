import copy
import unittest
import numpy as np
import torch
from imitation.model.synthetic import model,batch
from imitation.model.network import ModelConfig
from imitation.model.losses import loss_parts,total_loss
from imitation.model import train as qualified
from .student import mixed_loss,mixed_indices,teacher_loss,screen,ValuePolicy
from .train import step
from .capacity import config,kill_scan


class StudentTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1);torch.manual_seed(711)

    def test_ratio_zero_exact_loss_gradient_and_optimizer(self):
        m=model(ModelConfig(width=48,heads=6,layers=1,ffn=96,dropout=0))
        b,y=batch(6);m.eval()
        o=m(b,(y['action']//576).clamp(0,3))
        ref=total_loss(loss_parts(o,y))['loss'];actual=mixed_loss(o,y,ratio=0)
        self.assertTrue(torch.equal(ref,actual))
        g1=torch.autograd.grad(ref,tuple(m.parameters()),retain_graph=True,allow_unused=True)
        g2=torch.autograd.grad(actual,tuple(m.parameters()),allow_unused=True)
        for x,z in zip(g1,g2):
            if x is not None:self.assertTrue(torch.equal(x,z))
        other=copy.deepcopy(m)
        opts=[torch.optim.AdamW(x.parameters(),lr=3e-4) for x in (m,other)]
        r1=qualified.optimizer_step(m,opts[0],b,y,3,torch.device('cpu'))
        r2=step(other,opts[1],(b,y),None,0.,3,torch.device('cpu'),.1,4.,0.)
        self.assertEqual(r1,r2)
        for k,v in m.state_dict().items():self.assertTrue(torch.equal(v,other.state_dict()[k]),k)

    def test_timed_wait_probability_aggregation_and_soft_gradients(self):
        m=model(ModelConfig(width=48,heads=6,layers=1,ffn=96,dropout=0))
        b,y=batch(3);y.update(root_actions=torch.tensor([[0,2304,2401]]*3),
            root_scores=torch.tensor([[1.,0.,0.]]*3),root_valid=torch.ones(3,3,dtype=torch.bool),outcome=torch.zeros(3))
        o=m(b,torch.empty(0,dtype=torch.long));loss=teacher_loss(o,y,temperature=1.)
        self.assertTrue(torch.isfinite(loss));loss.backward()
        self.assertGreater(float(m.gate[-1].weight.grad.abs().sum()),0.)
        self.assertGreater(float(m.tile_score[-1].weight.grad.abs().sum()),0.)
        z=dict(y);z['root_actions']=torch.tensor([[0,2304]]*3)
        z['root_scores']=torch.tensor([[1.,np.log(2.)]]*3);z['root_valid']=torch.ones(3,2,dtype=torch.bool)
        self.assertTrue(torch.allclose(loss,teacher_loss(o,z,temperature=1.),atol=1e-6))

    def test_sampler_and_kill_rules(self):
        h,t=mixed_indices(100,40,20,.25,7,1)
        self.assertEqual((len(h),len(t)),(15,5))
        for x,z in zip((h,t),mixed_indices(100,40,20,.25,7,1)):np.testing.assert_array_equal(x,z)
        self.assertFalse(screen(.49,.01)['survives'])
        self.assertFalse(screen(.8,0.)['survives'])
        self.assertTrue(screen(.5,.01)['survives'])
        self.assertTrue(kill_scan(.4,.399,25,100))
        self.assertFalse(kill_scan(.4,.394,25,100))
        self.assertEqual(config(384).ffn,1536)

    def test_value_and_microbatch_normalization(self):
        c=ModelConfig(width=48,heads=6,layers=1,ffn=96,dropout=0)
        base=model(c)
        m=ValuePolicy(c,base.descriptors,base.tile_features,base.costs)
        b,y=batch(6)
        y.update(root_actions=torch.tensor([[0,2304]]*6),root_scores=torch.zeros(6,2),
                 root_valid=torch.ones(6,2,dtype=torch.bool),outcome=torch.ones(6))
        o=m(b,torch.empty(0,dtype=torch.long))
        full=teacher_loss(o,y,value_weight=.5)
        w=y['weight']*torch.where(y['action']<2304,4.,1.)
        den=(float(w.sum()),float(w.sum()/2))
        parts=[]
        for i in range(0,6,2):
            oo={k:v[i:i+2] for k,v in o.items()};yy={k:v[i:i+2] for k,v in y.items()}
            parts.append(teacher_loss(oo,yy,value_weight=.5,denominators=den))
        self.assertTrue(torch.allclose(full,sum(parts),atol=1e-6))
        full.backward()
        self.assertGreater(float(m.value_head.weight.grad.abs().sum()),0.)


if __name__=='__main__':unittest.main()
